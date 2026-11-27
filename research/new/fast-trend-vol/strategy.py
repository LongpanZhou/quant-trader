"""Fast adaptive trend + volatility-targeted TQQQ allocator.

DEVELOPMENT WINDOW ONLY: 2016-01-04 .. 2023-12-29.  The 2024-2026 holdout is
never loaded by this script.

Idea
----
TQQQ's 3x daily reset makes multi-month bear markets catastrophic and makes
high realised volatility expensive.  A two-speed daily EMA trend owns TQQQ in
uptrends and sits in BIL otherwise; an 85% volatility target cuts exposure when
TQQQ's own realised volatility is high; a QQQ 2.5% intraday crash brake and a
QQQ -3.5% daily crash cooldown cut the first days of a shock.

No 165-day (or any 100-250 day) moving average is used.  No 4% TQQQ stop.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/new/fast-trend-vol/strategy.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

DEV_START, DEV_END = "2016-01-04", "2023-12-29"
BARS = 252 * 390
SYMBOLS = ("QQQ", "TQQQ", "BIL")
TZ = "America/New_York"

# Frozen base (centre of the pre-registered grid, not the best cell).
BASE = dict(
    entry=20,
    exit_=50,
    buffer=0.025,
    target_vol=0.85,
    vol_window=20,
    crash_thr=-0.035,
    crash_cd=5,
    intraday_stop=0.025,
)

GRID = {
    "base": dict(BASE),
    "buf_2.0": dict(BASE, buffer=0.020),
    "buf_3.0": dict(BASE, buffer=0.030),
    "entry_15": dict(BASE, entry=15),
    "entry_25": dict(BASE, entry=25),
    "tv_0.70": dict(BASE, target_vol=0.70),
    "istop_2.0": dict(BASE, intraday_stop=0.020),
    "istop_3.0": dict(BASE, intraday_stop=0.030),
}

_DAILY_CACHE: dict = {}


# --------------------------------------------------------------------------- #
# daily signal data
# --------------------------------------------------------------------------- #
def load_prehistory(before_date):
    """Adjusted QQQ/TQQQ daily closes strictly before the first 1m session.

    Used only to warm the EMAs/volatility before 2016-01-04.  The signal for
    every session in the panel uses that session's 15:59 1-minute close, not
    the official 16:00 daily close, so the decision is made with the price
    actually known at 15:59.
    """
    key = ("pre", before_date)
    if key in _DAILY_CACHE:
        return _DAILY_CACHE[key]
    q = pd.read_parquet(ROOT / "data" / "intraday-hf" / "QQQ-1d-yahoo.parquet")
    q["date"] = pd.to_datetime(q["date"]).dt.date
    q = q[q["date"] < before_date].sort_values("date")
    t = pd.read_parquet(ROOT / "data" / "intraday-hf" / "TQQQ-1d-yahoo.parquet")
    t["date"] = pd.to_datetime(t["date"]).dt.date
    t = t[t["date"] < before_date].sort_values("date")
    if not (q["date"].to_numpy() == t["date"].to_numpy()).all():
        raise RuntimeError("QQQ/TQQQ daily calendars differ")
    out = (q["date"].to_numpy(),
           q["adjclose"].astype(float).to_numpy(),
           t["adjclose"].astype(float).to_numpy())
    _DAILY_CACHE[key] = out
    return out


def panel_daily(ts, o, c):
    """Daily closes from the 1m panel's 15:59 bars, plus pre-2016 warmup."""
    dates, first, last = bt.day_bounds(ts)
    sess = dates[last]
    pre_dates, pre_q, pre_t = load_prehistory(sess[0])
    return (np.concatenate([pre_dates, sess]),
            np.concatenate([pre_q, c[last, 0]]),
            np.concatenate([pre_t, c[last, 1]]))


def daily_target(dates, q, tq, entry=20, exit_=50, buffer=0.025,
                 target_vol=0.85, vol_window=20, crash_thr=-0.035, crash_cd=5):
    """Daily TQQQ target and its components, all through the current close."""
    e_entry = pd.Series(q).ewm(span=entry, adjust=False).mean().to_numpy()
    e_exit = pd.Series(q).ewm(span=exit_, adjust=False).mean().to_numpy()
    rq = np.diff(np.log(q), prepend=np.log(q[0]))

    state = np.zeros(len(q))
    on = 0
    for k in range(len(q)):
        if on == 0 and q[k] > e_entry[k]:
            on = 1
        elif on == 1 and q[k] < e_exit[k] * (1.0 - buffer):
            on = 0
        state[k] = float(on)

    crash = np.zeros(len(q))
    left = 0
    for k in range(len(q)):
        if rq[k] <= crash_thr:
            left = crash_cd
        crash[k] = 1.0 if left > 0 else 0.0
        left = max(0, left - 1)

    rt = np.diff(np.log(tq), prepend=np.log(tq[0]))
    vol = pd.Series(rt).rolling(vol_window, min_periods=vol_window).std().to_numpy() * np.sqrt(252.0)
    vt = np.clip(target_vol / np.maximum(vol, 1e-6), 0.0, 1.0)
    w = state * (1.0 - crash) * vt
    return dict(w=np.nan_to_num(w, nan=0.0), state=state, crash=crash,
                vol=vol, vt=np.nan_to_num(vt, nan=0.0),
                e20=e_entry, e50=e_exit)


# --------------------------------------------------------------------------- #
# daily target -> 1-minute weights
# --------------------------------------------------------------------------- #
def map_to_minute(ts, daily_dates, w_daily, o, c, intraday_stop=0.025):
    """Causal daily-target -> 1m weight mapping.

    For each session k:
      * bars except the last carry the target known at the previous close;
      * the last bar carries the target computed at session k's close, which
        fills at session k+1's open.
    The intraday QQQ stop overrides the rest of the session and the night;
    the next open re-enters at the daily target if it is still on.
    """
    dates, first, last = bt.day_bounds(ts)
    wd = pd.Series(w_daily, index=pd.Index(daily_dates))
    wd = wd[~wd.index.duplicated(keep="last")]
    ws = wd.reindex(pd.Index(dates[last])).ffill().fillna(0.0).to_numpy()

    W = np.zeros((len(ts), 3))
    for k in range(len(first)):
        prev = ws[k - 1] if k > 0 else 0.0
        f, l = first[k], last[k]
        W[f:l, 1] = prev
        W[l, 1] = ws[k]
        W[f:l, 2] = 1.0 - prev
        W[l, 2] = 1.0 - ws[k]

    n_stops = 0
    if intraday_stop and intraday_stop > 0:
        for k in range(len(first)):
            f, l = first[k], last[k]
            if W[f, 1] <= 0:
                continue
            trigger = o[f, 0] * (1.0 - intraday_stop)
            idx = np.flatnonzero(c[f:l + 1, 0] < trigger)
            if len(idx) == 0:
                continue
            i = f + int(idx[0])
            W[i:l, 1] = 0.0
            W[i:l, 2] = 1.0
            if i < l:
                # re-enter at the next open at the target known at this close
                W[l, 1] = ws[k]
                W[l, 2] = 1.0 - ws[k]
            else:
                # a last-bar trigger can only fill at the next open; stay BIL
                # for that open and let the next session's first bar re-enter.
                W[l, 1] = 0.0
                W[l, 2] = 1.0
            n_stops += 1
    return W, n_stops


def target_from_params(dates, q, tq, p):
    return daily_target(dates, q, tq, entry=p["entry"], exit_=p["exit_"],
                        buffer=p["buffer"], target_vol=p["target_vol"],
                        vol_window=p.get("vol_window", 20),
                        crash_thr=p["crash_thr"], crash_cd=p["crash_cd"])


def build_weights(ts, o, c, params=None):
    """Required entry point: QQQ/TQQQ/BIL 1m panel -> (n,3) weights."""
    p = dict(BASE)
    if params:
        p.update(params)
    dates, q, tq = panel_daily(ts, o, c)
    d = target_from_params(dates, q, tq, p)
    W, _ = map_to_minute(ts, dates, d["w"], o, c, p["intraday_stop"])
    return W


# --------------------------------------------------------------------------- #
# metrics
# --------------------------------------------------------------------------- #
def _ts(x):
    return pd.Timestamp(x, tz=TZ)


def daily_returns(ts, equity):
    _, _, last = bt.day_bounds(ts)
    eq = equity[last]
    dates = bt.session_dates(ts)[last]
    return pd.Series(np.diff(eq) / eq[:-1], index=pd.Index(dates[1:]))


def seg_stats(r, a, b):
    """CAGR / max DD / Sharpe on the [a, b) slice of a simulation result."""
    t, e = r["ts"], r["equity"]
    m = (t >= _ts(a)) & (t < _ts(b))
    e = e[m]
    t = t[m]
    if len(e) < 2:
        return None
    years = (t[-1] - t[0]).total_seconds() / (365.25 * 86400.0)
    rets = np.diff(e) / e[:-1]
    peak = np.maximum.accumulate(e)
    return dict(
        cagr=float((e[-1] / e[0]) ** (1.0 / years) - 1.0),
        max_drawdown=float(-(e / peak - 1.0).min()),
        sharpe=float(np.mean(rets) / np.std(rets) * np.sqrt(BARS)) if np.std(rets) > 0 else 0.0,
    )


def metrics(ts, o, c, W, start=DEV_START, slip=1.0):
    r = bt.run(ts, o, c, W, start, band=0.02, slippage_bps=slip)
    s = bt.stats(r, BARS)
    i0 = bt.start_index(ts, start)
    eq = r["equity"]

    # daily correlation to TQQQ buy-and-hold
    _, _, last = bt.day_bounds(r["ts"])
    deq = eq[last]
    dtq = c[i0:][last, 1]
    dr = np.diff(deq) / deq[:-1]
    tr = np.diff(dtq) / dtq[:-1]
    corr = float(np.corrcoef(dr, tr)[0, 1]) if len(dr) > 2 else 0.0

    # max-drawdown episode
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    trough = int(np.argmin(dd))
    peak_i = int(np.argmax(eq[:trough + 1]))

    # worst 5 days
    daily = daily_returns(r["ts"], eq)
    worst = daily.nsmallest(5)

    yearly = {}
    y = r["ts"].year
    for yy in range(2016, 2024):
        m = y == yy
        if m.any():
            yearly[str(yy)] = float(eq[m][-1] / eq[m][0] - 1.0)

    return dict(
        cagr=float(s["cagr"]),
        max_drawdown=float(s["max_drawdown"]),
        sharpe=float(s["sharpe"]),
        sortino=float(s["sortino"]),
        volatility=float(s["volatility"]),
        calibrated_exposure=float(s["exposure"]),  # 1.0 when BIL is an asset
        tqqq_exposure=float(np.mean(W[i0:, 1])),
        time_in_tqqq=float(np.mean(W[i0:, 1] > 1e-9)),
        fills=int(s["fills"]),
        turnover=float(s["turnover"]),
        corr_tqqq=corr,
        yearly=yearly,
        max_dd_peak=str(r["ts"][peak_i]),
        max_dd_trough=str(r["ts"][trough]),
        worst_days={str(k): float(v) for k, v in worst.items()},
        ending_equity=float(s["ending_equity"]),
        years=float(s["years"]),
    )


# --------------------------------------------------------------------------- #
# robustness helpers
# --------------------------------------------------------------------------- #
def shuffle_runs(state, rng):
    """Permute the run-length sequence; preserve on/off days and persistence."""
    idx = np.flatnonzero(np.r_[True, state[1:] != state[:-1]])
    lengths = np.diff(np.r_[idx, len(state)])
    vals = state[idx]
    order = rng.permutation(len(lengths))
    out = np.concatenate([np.full(int(lengths[j]), float(vals[j])) for j in order])
    return out[:len(state)]


def baseline_165d(ts, o, c):
    """Old daily 165-day QQQ SMA regime, benchmark only (never an input)."""
    dates, q, _ = panel_daily(ts, o, c)
    sma = pd.Series(q).rolling(165).mean().to_numpy()
    reg = np.where(np.isfinite(sma) & (q > sma), 1.0, 0.0)
    W, _ = map_to_minute(ts, dates, reg, o, c, intraday_stop=0.0)
    return W


# --------------------------------------------------------------------------- #
def main():
    t0 = time.time()
    ts, o, c = bt.panel(SYMBOLS, DEV_START, DEV_END, "1min", warmup_days=0)
    i0 = bt.start_index(ts, DEV_START)
    print(f"panel {len(ts):,} bars {ts[0]} .. {ts[-1]}  ({time.time()-t0:.0f}s)")

    dates, q, tq = panel_daily(ts, o, c)
    base_d = target_from_params(dates, q, tq, BASE)
    W_base, n_stops = map_to_minute(ts, dates, base_d["w"], o, c,
                                    BASE["intraday_stop"])
    print(f"base: tqqq time {np.mean(W_base[i0:,1])*100:.1f}%  intraday stops {n_stops}")

    # primary at 1/5/10 bp
    primary = {}
    for slip in (1.0, 5.0, 10.0):
        primary[f"{slip:.0f}bp"] = metrics(ts, o, c, W_base, DEV_START, slip)
    print(f"primary 1bp: CAGR {primary['1bp']['cagr']*100:.2f}%  "
          f"DD {primary['1bp']['max_drawdown']*100:.2f}%  "
          f"Sharpe {primary['1bp']['sharpe']:.2f}  fills {primary['1bp']['fills']}")

    # 8-cell grid
    grid_W, grid_out = [], {}
    for name, p in GRID.items():
        d = target_from_params(dates, q, tq, p)
        W, ns = map_to_minute(ts, dates, d["w"], o, c, p["intraday_stop"])
        grid_W.append(W)
        grid_out[name] = dict(params=p, stops=ns)
    grid_res = bt.run_many(ts, o, c, grid_W, DEV_START, band=0.02,
                           slippage_bps=1.0, threads=1)
    for name, W, r in zip(GRID, grid_W, grid_res):
        s = bt.stats(r, BARS)
        grid_out[name].update(dict(cagr=float(s["cagr"]),
                                   max_drawdown=float(s["max_drawdown"]),
                                   sharpe=float(s["sharpe"]),
                                   tqqq_exposure=float(np.mean(W[i0:, 1])),
                                   fills=int(s["fills"])))
    print("grid done")

    # ablations (all 1 bp)
    ablations = {}
    variants = {
        "no_intraday_stop": dict(intraday_stop=0.0),
        "no_daily_crash": dict(crash_thr=-99.0),
        "no_crash_at_all": dict(intraday_stop=0.0, crash_thr=-99.0),
        "no_vol_target": dict(target_vol=99.0),
        "fast_exit_ema20": dict(exit_=20),
        "slow_entry_ema50": dict(entry=50),
        "wide_intraday_4pct": dict(intraday_stop=0.040),
    }
    for name, over in variants.items():
        p = dict(BASE)
        p.update(over)
        d = target_from_params(dates, q, tq, p)
        W, ns = map_to_minute(ts, dates, d["w"], o, c, p["intraday_stop"])
        ablations[name] = dict(params=p, stops=ns, **{
            k: v for k, v in metrics(ts, o, c, W, DEV_START, 1.0).items()
            if k in ("cagr", "max_drawdown", "sharpe", "tqqq_exposure", "fills",
                     "turnover", "corr_tqqq")})
    print("ablations done")

    # one-step neighbourhoods outside the pre-registered 8-cell grid
    neighbourhood = {}
    extra = {
        "crash_3.0": dict(crash_thr=-0.030),
        "crash_4.0": dict(crash_thr=-0.040),
        "crash_4.5": dict(crash_thr=-0.045),
        "exit_ema40": dict(exit_=40),
        "exit_ema60": dict(exit_=60),
        "volwin_15": dict(vol_window=15),
        "volwin_30": dict(vol_window=30),
    }
    for name, over in extra.items():
        p = dict(BASE)
        p.update(over)
        d = target_from_params(dates, q, tq, p)
        W, ns = map_to_minute(ts, dates, d["w"], o, c, p["intraday_stop"])
        m = metrics(ts, o, c, W, DEV_START, 1.0)
        neighbourhood[name] = dict(params=p, stops=ns, **{
            k: m[k] for k in ("cagr", "max_drawdown", "sharpe",
                              "tqqq_exposure", "fills")})
    print("neighbourhood done")

    # 165-day benchmark (benchmark only)
    W_165 = baseline_165d(ts, o, c)
    bench_165 = metrics(ts, o, c, W_165, DEV_START, 1.0)

    # lag placebo: shift the whole daily target by n sessions
    lag_out = {}
    for lag in (1, 5, 10, 20):
        wl = np.r_[np.zeros(lag), base_d["w"][:-lag]] if lag > 0 else base_d["w"]
        Wl, _ = map_to_minute(ts, dates, wl, o, c, BASE["intraday_stop"])
        m = metrics(ts, o, c, Wl, DEV_START, 1.0)
        lag_out[f"lag_{lag}"] = {k: m[k] for k in
                                 ("cagr", "max_drawdown", "sharpe", "tqqq_exposure")}
    print("lags done")

    # random-run placebo: same on/off days and persistence, random timing
    rng = np.random.default_rng(20261127)
    placebo = []
    for b in range(30):
        st = shuffle_runs(base_d["state"], rng)
        w = st * (1.0 - base_d["crash"]) * base_d["vt"]
        Wp, _ = map_to_minute(ts, dates, w, o, c, BASE["intraday_stop"])
        r = bt.run(ts, o, c, Wp, DEV_START, band=0.02, slippage_bps=1.0)
        s = bt.stats(r, BARS)
        placebo.append(dict(cagr=float(s["cagr"]),
                            max_drawdown=float(s["max_drawdown"]),
                            sharpe=float(s["sharpe"])))
    pc = np.array([x["cagr"] for x in placebo])
    pd_ = np.array([x["max_drawdown"] for x in placebo])
    ps = np.array([x["sharpe"] for x in placebo])
    placebo_summary = dict(
        draws=len(placebo),
        cagr_median=float(np.median(pc)), cagr_p90=float(np.percentile(pc, 90)),
        cagr_max=float(pc.max()),
        dd_median=float(np.median(pd_)), dd_min=float(pd_.min()),
        sharpe_median=float(np.median(ps)), sharpe_max=float(ps.max()),
        base_cagr_percentile=float(np.mean(pc < primary["1bp"]["cagr"])),
        base_sharpe_percentile=float(np.mean(ps < primary["1bp"]["sharpe"])),
    )
    print("placebo done")

    # cut tests: fresh start at later dates
    cuts = {}
    for start in ("2017-01-03", "2018-01-02", "2019-01-02",
                  "2020-01-02", "2021-01-04", "2022-01-03"):
        s = metrics(ts, o, c, W_base, start, 1.0)
        cuts[start] = {k: s[k] for k in
                       ("cagr", "max_drawdown", "sharpe", "tqqq_exposure", "years")}

    # fixed sub-periods
    r = bt.run(ts, o, c, W_base, DEV_START, band=0.02, slippage_bps=1.0)
    sub = {}
    for name, a, b in (("2016_2019", "2016-01-04", "2020-01-01"),
                       ("2020_2021", "2020-01-01", "2022-01-01"),
                       ("2022_2023", "2022-01-01", "2024-01-01")):
        sub[name] = seg_stats(r, a, b)

    # causality / truncation check
    ts_cut, o_cut, c_cut = bt.panel(SYMBOLS, DEV_START, "2020-12-31", "1min",
                                    warmup_days=0)
    dates_cut, q_cut, tq_cut = panel_daily(ts_cut, o_cut, c_cut)
    d_cut = target_from_params(dates_cut, q_cut, tq_cut, BASE)
    full_s = pd.Series(base_d["w"], index=pd.Index(dates))
    cut_s = pd.Series(d_cut["w"], index=pd.Index(dates_cut))
    daily_max_diff = float((full_s.reindex(cut_s.index) - cut_s).abs().max())
    W_cut = build_weights(ts_cut, o_cut, c_cut)
    weight_prefix_equal = bool(np.array_equal(W_base[:len(ts_cut)], W_cut))

    # benchmarks
    tq_bench = bt.benchmark(c[i0:, 1], ts[i0:], BARS)
    qq_bench = bt.benchmark(c[i0:, 0], ts[i0:], BARS)
    bil_bench = bt.benchmark(c[i0:, 2], ts[i0:], BARS)

    out = dict(
        agent="fast-trend-vol",
        status=("dev_pass" if (primary["1bp"]["cagr"] > 0.3672 and
                               primary["1bp"]["max_drawdown"] < 0.8229)
                else "dev_fail"),
        window=dict(start=DEV_START, end=DEV_END, sessions=int(len(bt.day_bounds(ts)[1])),
                    marks="1-minute", fills="next-open", band=0.02),
        verdict=dict(
            bar_cagr=0.3672, bar_max_drawdown=0.8229, bar_sharpe=0.82,
            passes_bar=bool(primary["1bp"]["cagr"] > 0.3672 and
                            primary["1bp"]["max_drawdown"] < 0.8229),
            meets_dd_target=bool(primary["1bp"]["max_drawdown"] < 0.60),
            cagr_minus_bar_pp=float((primary["1bp"]["cagr"] - 0.3672) * 100),
            dd_minus_bar_pp=float((0.8229 - primary["1bp"]["max_drawdown"]) * 100),
        ),
        primary=dict(params=BASE, intraday_stops=int(n_stops),
                     **{"1bp": primary["1bp"], "5bp": primary["5bp"],
                        "10bp": primary["10bp"]}),
        grid=grid_out,
        ablations=ablations,
        neighbourhood=neighbourhood,
        baseline_165d_benchmark_only=bench_165,
        lag_placebo=lag_out,
        random_run_placebo=dict(draws=placebo, summary=placebo_summary),
        cut_tests=cuts,
        subperiods=sub,
        causality=dict(daily_target_max_abs_diff=daily_max_diff,
                       weight_prefix_equal=weight_prefix_equal),
        benchmarks=dict(tqqq_buy_hold=tq_bench, qqq_buy_hold=qq_bench,
                        bil_buy_hold=bil_bench),
        notes=dict(
            tqqq_exposure="mean TQQQ weight over all 1m bars",
            calibrated_exposure="bt.stats exposure; 1.0 because BIL is an asset",
            old_base="165d QQQ SMA + 4% TQQQ stop is deliberately not used",
            holdout="2024-2026 not loaded",
        ),
    )
    (HERE / "result.json").write_text(json.dumps(out, indent=2, default=float))

    # concise console summary
    print("\n== primary ==")
    for k in ("1bp", "5bp", "10bp"):
        m = primary[k]
        print(f"{k:4s} CAGR {m['cagr']*100:6.2f}%  DD {m['max_drawdown']*100:5.2f}%  "
              f"Sharpe {m['sharpe']:4.2f}  TQQQ {m['tqqq_exposure']*100:4.1f}%  "
              f"fills {m['fills']}")
    print("\n== grid ==")
    for name, v in grid_out.items():
        print(f"{name:10s} CAGR {v['cagr']*100:6.2f}%  DD {v['max_drawdown']*100:5.2f}%  "
              f"Sharpe {v['sharpe']:4.2f}")
    print("\n== ablations ==")
    for name, v in ablations.items():
        print(f"{name:22s} CAGR {v['cagr']*100:6.2f}%  DD {v['max_drawdown']*100:5.2f}%  "
              f"Sharpe {v['sharpe']:4.2f}")
    print("\n== neighbourhood ==")
    for name, v in neighbourhood.items():
        print(f"{name:12s} CAGR {v['cagr']*100:6.2f}%  DD {v['max_drawdown']*100:5.2f}%  "
              f"Sharpe {v['sharpe']:4.2f}")
    print("\n== placebo ==")
    print(placebo_summary)
    print("\n== causality ==")
    print(out["causality"])
    print(f"\ndone {time.time()-t0:.0f}s -> {HERE/'result.json'}")


if __name__ == "__main__":
    main()
