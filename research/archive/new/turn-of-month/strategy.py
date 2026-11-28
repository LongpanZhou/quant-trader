"""Turn-of-month TQQQ with a causal volatility throttle.

Standalone strategy, development window only (2016-01-04 .. 2023-12-29).

Rules
-----
Universe: QQQ (volatility input), TQQQ (position), BIL (idle).

For each session k, with pe(k) = sessions from the end of its month
(0 = last session) and ps(k) = sessions from the start (0 = first):

    in_window(k) = (pe(k) <= LAST_SESSIONS - 1) or (ps(k) <= FIRST_SESSIONS - 1)
    w(k)         = 1.0 if in_window(k) else 0.0

An optional throttle (VOL_TARGET) replaces the 1.0 with
min(1, VOL_TARGET / sigma(k-1)), where sigma is the annualised stdev of the
last 20 completed TQQQ daily log returns.  It is tested but not used in the
delivered centre.

The decision for session k is taken at the 15:59 close of session k-1 and
filled at the next open (09:30 for the first session of a block; the 15:59
bar's weight fills at the next session's open).  The harness's next-open rule
is used unchanged.  Idle weight is BIL; QQQ is never held.

Centre: LAST_SESSIONS=5, FIRST_SESSIONS=6, no volatility throttle.
The window is 11 sessions out of a typical 19-23 session month.  The optional
throttle (VOL_TARGET) is tested in the grid and reported, but is not used in
the delivered centre: on the warmup-corrected data it costs more CAGR than the
drawdown it saves.

The 20-day vol is warmed with TQQQ daily closes from 2015-01-02..2015-12-31 so
the strategy is live on 2016-01-04.  The panel is physically truncated at
2023-12-29; no 2024+ bar is loaded.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

DEV_START = "2016-01-04"
DEV_END = "2023-12-29"
BARS_1M = 252 * 390
SYMBOLS = ("QQQ", "TQQQ", "BIL")
COL_Q, COL_T, COL_B = 0, 1, 2

# pre-registered centre
LAST_SESSIONS = 5
FIRST_SESSIONS = 6
VOL_TARGET = None          # no throttle in the delivered centre
VOL_WINDOW = 20

BAR = {"cagr": 0.3672, "max_drawdown": 0.8229, "sharpe": 0.82}


# --------------------------------------------------------------------------- #
# calendar and signals
# --------------------------------------------------------------------------- #
def session_offsets(session_dates) -> tuple[np.ndarray, np.ndarray]:
    """pe (0 = last session of month) and ps (0 = first) for each session."""
    months = np.array([d.month for d in session_dates])
    years = np.array([d.year for d in session_dates])
    change = (months[1:] != months[:-1]) | (years[1:] != years[:-1])
    first = np.flatnonzero(np.r_[True, change])
    last = np.r_[first[1:] - 1, len(months) - 1]
    pe = np.zeros(len(months), dtype=int)
    ps = np.zeros(len(months), dtype=int)
    for a, b in zip(first, last):
        ps[a:b + 1] = np.arange(b - a + 1)
        pe[a:b + 1] = np.arange(b - a, -1, -1)
    return pe, ps


def _warm_tqqq_closes(first_session_date) -> np.ndarray:
    """TQQQ total-return daily closes strictly before the intraday archive."""
    daily = pd.read_parquet(bt.DATA_DIR / "TQQQ-1d-yahoo.parquet")
    daily["date"] = pd.to_datetime(daily["date"]).dt.date
    pre = daily[daily["date"] < first_session_date].sort_values("date")
    return pre["adjclose"].to_numpy(dtype=float)


def _sigma(daily_closes: np.ndarray, warm: np.ndarray, window: int) -> np.ndarray:
    """Annualised stdev of log returns through each session's close."""
    allc = np.r_[warm, daily_closes]
    r = np.zeros(len(allc))
    r[1:] = np.log(allc[1:] / allc[:-1])
    vol = pd.Series(r).rolling(window, min_periods=window).std(ddof=0).to_numpy()
    return vol[len(warm):] * np.sqrt(252.0)


def _targets(pe, ps, sigma, last_sessions, first_sessions, vol_target):
    """Target held during session k, decided at the close of k-1."""
    nd = len(pe)
    inwin = (pe <= last_sessions - 1) | (ps <= first_sessions - 1)
    if vol_target is None:
        scale = np.ones(nd)
    else:
        scale = np.minimum(1.0, vol_target / np.maximum(sigma, 1e-12))
        scale = np.where(np.isfinite(scale), scale, 0.0)
    tgt = np.zeros(nd)
    tgt[:-1] = inwin[1:] * scale[:-1]
    return np.clip(tgt, 0.0, 1.0)


def build_weights(ts, o, c, last_sessions: int = LAST_SESSIONS,
                  first_sessions: int = FIRST_SESSIONS,
                  vol_target=VOL_TARGET, vol_window: int = VOL_WINDOW,
                  calendar=None) -> np.ndarray:
    """Return the (n, 3) weight matrix for 1-minute bars (col 1 = TQQQ).

    `calendar` is an optional ex-ante exchange calendar (all session dates).
    When supplied, the month-end offsets are computed on that full calendar
    and mapped onto the panel's sessions, so a truncated panel cannot mistake
    its last session for a month-end.  The default (None) uses the panel's own
    sessions, which is the correct full-panel behaviour.
    """
    dates, first, last = bt.day_bounds(ts)
    nd = len(first)
    session_dates = dates[first]
    if calendar is None:
        pe, ps = session_offsets(session_dates)
    else:
        cal = pd.DatetimeIndex(pd.to_datetime(calendar)).normalize().unique().sort_values()
        pe_cal, ps_cal = session_offsets(cal)
        pos = cal.get_indexer(pd.DatetimeIndex(pd.to_datetime(session_dates)))
        if (pos < 0).any():
            raise ValueError("panel session missing from the ex-ante calendar")
        pe, ps = pe_cal[pos], ps_cal[pos]

    dclose = np.asarray(c, dtype=float)[last, COL_T]
    warm = _warm_tqqq_closes(session_dates[0])
    sigma = _sigma(dclose, warm, vol_window)
    tgt = _targets(pe, ps, sigma, last_sessions, first_sessions, vol_target)

    w = np.zeros((len(ts), 3))
    for k in range(nd):
        f, l = int(first[k]), int(last[k])
        prev = tgt[k - 1] if k > 0 else 0.0
        # bars up to 15:58: position established at this session's open
        w[f:l, COL_T] = prev
        w[f:l, COL_B] = 1.0 - prev
        # 15:59 bar: weight set at the session close, filled at the next open
        w[l, COL_T] = tgt[k]
        w[l, COL_B] = 1.0 - tgt[k]

    assert w.min() >= -1e-12, "negative weight"
    assert np.all(w.sum(axis=1) <= 1.0 + 1e-9), "weights sum > 1"
    return w


def build_weights_daily(ts, o, c, last_sessions: int = LAST_SESSIONS,
                        first_sessions: int = FIRST_SESSIONS,
                        vol_target=VOL_TARGET, vol_window: int = VOL_WINDOW,
                        mask=None) -> np.ndarray:
    """Daily-bar version, used only for the random-window placebo/controls."""
    dates = bt.session_dates(ts)
    pe, ps = session_offsets(dates)
    dclose = np.asarray(c, dtype=float)[:, COL_T]
    warm = _warm_tqqq_closes(dates[0])
    sigma = _sigma(dclose, warm, vol_window)
    if mask is None:
        inwin = (pe <= last_sessions - 1) | (ps <= first_sessions - 1)
    else:
        inwin = mask
    if vol_target is None:
        scale = np.ones(len(dates))
    else:
        scale = np.minimum(1.0, vol_target / np.maximum(sigma, 1e-12))
        scale = np.where(np.isfinite(scale), scale, 0.0)
    tgt = np.zeros(len(dates))
    tgt[:-1] = inwin[1:] * scale[:-1]
    tgt = np.clip(tgt, 0.0, 1.0)
    w = np.zeros((len(ts), 3))
    w[:, COL_T] = tgt
    w[:, COL_B] = 1.0 - tgt
    return w


# --------------------------------------------------------------------------- #
# evaluation helpers
# --------------------------------------------------------------------------- #
def pack(s: dict) -> dict:
    keys = ("cagr", "max_drawdown", "sharpe", "sortino", "volatility",
            "exposure", "turnover", "fills", "ending_equity", "years")
    return {k: (int(s[k]) if k == "fills" else float(s[k])) for k in keys}


def run_weights(ts, o, c, w, slip: float = 1.0, start: str = DEV_START):
    res = bt.run(ts, o, c, w, start, band=0.02, slippage_bps=slip)
    return res, bt.stats(res, BARS_1M)


def daily_returns(res: dict) -> pd.Series:
    s = pd.Series(res["equity"], index=res["ts"])
    return s.groupby(res["ts"].date).last().pct_change().dropna()


def dd_window(ts, equity):
    peak = np.maximum.accumulate(equity)
    dd = equity / peak - 1.0
    j = int(np.argmin(dd))
    i = int(np.argmax(equity[: j + 1]))
    return {"peak": str(ts[i])[:10], "trough": str(ts[j])[:10], "dd": float(-dd[j])}


def subperiod(ts, equity, lo, hi):
    m = ((ts >= pd.Timestamp(lo, tz="America/New_York"))
         & (ts < pd.Timestamp(hi, tz="America/New_York") + pd.Timedelta(days=1)))
    x, tt = equity[m], ts[m]
    if len(x) < 2:
        return None
    years = (tt[-1] - tt[0]).total_seconds() / (365.25 * 86400)
    peak = np.maximum.accumulate(x)
    return {"cagr": float((x[-1] / x[0]) ** (1 / years) - 1),
            "max_drawdown": float(-(x / peak - 1).min()), "years": float(years)}


def _compound(r: np.ndarray):
    eq = np.cumprod(1.0 + r)
    years = len(r) / 252.0
    peak = np.maximum.accumulate(eq)
    return {"cagr": float(eq[-1] ** (1 / years) - 1),
            "max_drawdown": float(-(eq / peak - 1).min()),
            "years": float(years)}


def calendar_year_cut(ts, equity, year: int) -> dict:
    s = pd.Series(equity, index=ts)
    d = s.groupby(ts.date).last()
    r = d.pct_change().dropna()
    r = r[np.array([x.year != year for x in r.index])]
    return _compound(r.to_numpy())


def drop_month(ts, equity, year: int, month: int) -> dict:
    s = pd.Series(equity, index=ts)
    d = s.groupby(ts.date).last()
    r = d.pct_change().dropna()
    keep = np.array([not (x.year == year and x.month == month) for x in r.index])
    return _compound(r[keep].to_numpy())


def monthly_stats(ts, equity, bench_close):
    """Monthly strategy-vs-benchmark excess and concentration."""
    s = pd.Series(equity, index=ts)
    d = s.groupby(ts.date).last()
    d.index = pd.to_datetime(d.index)
    r = d.pct_change().dropna()
    b = pd.Series(bench_close, index=pd.to_datetime(ts))
    bd = b.groupby(b.index.date).last()
    bd.index = pd.to_datetime(bd.index)
    br = bd.pct_change().dropna()
    ms = (1 + r).groupby([r.index.year, r.index.month]).prod() - 1
    mb = (1 + br).groupby([br.index.year, br.index.month]).prod() - 1
    al = pd.concat([ms, mb], axis=1, keys=["s", "b"]).dropna()
    diff = al["s"] - al["b"]
    rn, bn = r.to_numpy(), br.to_numpy()
    top = np.argsort(rn)[-10:]
    return {
        "n_months": int(len(diff)),
        "mean_excess": float(diff.mean()),
        "median_excess": float(diff.median()),
        "t_excess": float(diff.mean() / diff.std(ddof=1) * np.sqrt(len(diff))),
        "win_rate": float((diff > 0).mean()),
        "mean_daily_bp": float(rn.mean() * 1e4),
        "bench_mean_daily_bp": float(bn.mean() * 1e4),
        "total_log": float(np.log1p(rn).sum()),
        "bench_total_log": float(np.log1p(bn).sum()),
        "top10_log": float(np.log1p(rn[top]).sum()),
        "top10_share_of_total": float(np.log1p(rn[top]).sum() / np.log1p(rn).sum()),
        "top10_bench_same_dates_log": float(np.log1p(bn[top]).sum()),
        "best_months": [
            {"month": f"{y}-{m:02d}", "strategy": float(v), "benchmark": float(mb[(y, m)])}
            for (y, m), v in ms.sort_values().tail(5).items()
        ],
        "worst_months": [
            {"month": f"{y}-{m:02d}", "strategy": float(v), "benchmark": float(mb[(y, m)])}
            for (y, m), v in ms.sort_values().head(5).items()
        ],
    }


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main():
    ts, o, c = bt.panel(SYMBOLS, DEV_START, DEV_END, "1min", warmup_days=0)
    dates, first, last = bt.day_bounds(ts)
    print(f"panel {len(ts):,} bars, {len(first)} sessions, "
          f"{ts[0].date()} .. {ts[-1].date()}")

    # sanity: warmup scale continuity
    dclose = np.asarray(c, float)[last, COL_T]
    warm = _warm_tqqq_closes(dates[first][0])
    print(f"warmup last {warm[-1]:.4f} -> first panel close {dclose[0]:.4f} "
          f"({dclose[0]/warm[-1]-1:+.2%})")

    w = build_weights(ts, o, c)
    i0 = bt.start_index(ts, DEV_START)
    bench = bt.benchmark(c[i0:, COL_T], ts[i0:], BARS_1M)

    out = {
        "strategy": "turn-of-month",
        "directory": "research/new/turn-of-month",
        "window": {"start": DEV_START, "end": DEV_END, "marks": "1m",
                   "fills": "next open, 2% band", "idle": "BIL"},
        "rules": {
            "last_sessions": LAST_SESSIONS,
            "first_sessions": FIRST_SESSIONS,
            "vol_target": VOL_TARGET,
            "vol_window": VOL_WINDOW,
            "vol_input": "TQQQ daily log returns, known at the close",
            "optional_throttle": "tested at 0.60/0.75; not used in centre",
            "signal_clock": "15:59 close, fill next open",
            "warmup": "TQQQ daily closes 2015-01-02..2015-12-31",
            "bar": BAR,
        },
        "dev": {},
    }

    results = {}
    for slip in (1.0, 5.0, 10.0):
        res, s = run_weights(ts, o, c, w, slip=slip)
        results[slip] = (res, s)
        out["dev"][f"{int(slip)}bp"] = pack(s)
        print(f"centre {slip:2.0f}bp  CAGR {s['cagr']*100:6.2f}%  "
              f"DD {s['max_drawdown']*100:5.2f}%  Sharpe {s['sharpe']:4.2f}  "
              f"fills {s['fills']:,}  turnover {s['turnover']:.0f}")

    res1, s1 = results[1.0]
    out["benchmark_tqqq"] = {k: float(v) for k, v in bench.items()}
    out["benchmark_tqqq"]["symbol"] = "TQQQ"
    out["benchmark_tqqq"]["bar_from_brief"] = BAR
    print(f"bench  CAGR {bench['cagr']*100:6.2f}%  DD {bench['max_drawdown']*100:5.2f}%  "
          f"Sharpe {bench['sharpe']:4.2f}")

    # exposure / correlation
    wbar = w[:, COL_T]
    wsess = w[first, COL_T]
    out["exposure"] = {
        "mean_tqqq_weight_bar": float(wbar.mean()),
        "mean_tqqq_weight_session": float(wsess.mean()),
        "fraction_sessions_full": float((wsess > 0.99).mean()),
        "fraction_sessions_zero": float((wsess < 0.01).mean()),
        "mean_bil_weight": float(1.0 - wbar.mean()),
    }
    dr = daily_returns(res1)
    dr_bench = daily_returns({"equity": c[i0:, COL_T], "ts": ts[i0:]})
    out["corr_daily_tqqq"] = float(dr.corr(dr_bench))
    print("exposure", {k: round(v, 3) for k, v in out["exposure"].items()},
          "corr", round(out["corr_daily_tqqq"], 3))

    out["yearly"] = {
        str(k): {"strategy": float(v["strategy"]), "benchmark": float(v["benchmark"])}
        for k, v in bt.yearly(res1["ts"], res1["equity"], c[i0:, COL_T]).items()
    }
    out["dd_window"] = dd_window(res1["ts"], res1["equity"])
    out["subperiods"] = {
        "2016_2019": subperiod(res1["ts"], res1["equity"], "2016-01-04", "2019-12-31"),
        "2020_2023": subperiod(res1["ts"], res1["equity"], "2020-01-02", "2023-12-29"),
    }
    out["monthly"] = monthly_stats(res1["ts"], res1["equity"], c[i0:, COL_T])
    print("monthly excess mean %.2f%% median %.2f%% t %.2f win %.1f%%" % (
        out["monthly"]["mean_excess"] * 100, out["monthly"]["median_excess"] * 100,
        out["monthly"]["t_excess"], out["monthly"]["win_rate"] * 100))

    # ---- pre-registered grid (8 cells) --------------------------------------
    grid_spec = [
        (3, 5, 0.75, "narrow"),
        (3, 6, 0.75, "narrow"),
        (4, 6, 0.75, "L neighbour"),
        (5, 5, 0.75, "F neighbour"),
        (5, 6, None, "centre"),
        (5, 7, 0.75, "F neighbour"),
        (5, 6, 0.60, "conservative throttle"),
        (5, 6, 0.75, "pre-registered throttle"),
    ]
    grid = []
    for L, F, tgt, role in grid_spec:
        wt = build_weights(ts, o, c, last_sessions=L, first_sessions=F, vol_target=tgt)
        _, s = run_weights(ts, o, c, wt)
        grid.append({"last": L, "first": F,
                     "vol_target": tgt, "role": role, **pack(s)})
        print(f"grid L={L} F={F} tgt={tgt} {role:22s} CAGR {s['cagr']*100:6.2f}%  "
              f"DD {s['max_drawdown']*100:5.2f}%  Sh {s['sharpe']:4.2f}")
    out["grid"] = grid

    # ---- neighbours: vol-target scan and window ladder ----------------------
    neigh = []
    for tgt in (0.50, 0.60, 0.65, 0.70, 0.75, 0.80, 0.90, None):
        wt = build_weights(ts, o, c, vol_target=tgt)
        _, s = run_weights(ts, o, c, wt)
        neigh.append({"name": f"vol_target {tgt}", **pack(s)})
        print(f"neigh vol {str(tgt):5s}  CAGR {s['cagr']*100:6.2f}%  "
              f"DD {s['max_drawdown']*100:5.2f}%  Sh {s['sharpe']:4.2f}")
    for L, F in [(3, 11), (4, 7), (5, 4), (5, 5), (5, 7), (6, 6), (6, 7)]:
        wt = build_weights(ts, o, c, last_sessions=L, first_sessions=F)
        _, s = run_weights(ts, o, c, wt)
        neigh.append({"name": f"window L{L} F{F}", **pack(s)})
        print(f"neigh L={L} F={F}  CAGR {s['cagr']*100:6.2f}%  "
              f"DD {s['max_drawdown']*100:5.2f}%  Sh {s['sharpe']:4.2f}")
    out["neighbours"] = neigh

    # ---- placebo: random contiguous 11-session block per month -------------
    tsd, od, cd = bt.panel(SYMBOLS, DEV_START, DEV_END, "1D", warmup_days=0)
    datesd = bt.session_dates(tsd)
    pe, ps = session_offsets(datesd)
    mon = np.array([pd.Timestamp(x).month for x in datesd])
    yr = np.array([pd.Timestamp(x).year for x in datesd])
    change = (mon[1:] != mon[:-1]) | (yr[1:] != yr[:-1])
    fi = np.flatnonzero(np.r_[True, change])
    li = np.r_[fi[1:] - 1, len(datesd) - 1]
    lens = li - fi + 1

    real_daily = bt.stats(bt.run(tsd, od, cd,
                                 build_weights_daily(tsd, od, cd), DEV_START), 252)
    rng = np.random.default_rng(20231127)
    draws = []
    for _ in range(300):
        mask = np.zeros(len(datesd), dtype=bool)
        for a, b, ln in zip(fi, li, lens):
            k = min(11, ln)
            st = int(rng.integers(0, ln - k + 1))
            mask[a + st:a + st + k] = True
        wt = build_weights_daily(tsd, od, cd, mask=mask)
        draws.append(bt.stats(bt.run(tsd, od, cd, wt, DEV_START), 252)["cagr"])
    draws = np.array(draws)
    out["placebo"] = {
        "n_draws": len(draws), "marks": "1D",
        "real_cagr_daily": float(real_daily["cagr"]),
        "mean": float(draws.mean()),
        "p95": float(np.quantile(draws, 0.95)),
        "p99": float(np.quantile(draws, 0.99)),
        "max": float(draws.max()),
        "p_value": float((draws >= real_daily["cagr"]).mean()),
    }
    print("placebo", {k: (round(v, 4) if isinstance(v, float) else v)
                      for k, v in out["placebo"].items()})

    # ---- cut tests ----------------------------------------------------------
    cuts = {}
    for year in (2016, 2020, 2022, 2023):
        cuts[str(year)] = {
            "strategy": calendar_year_cut(res1["ts"], res1["equity"], year),
            "benchmark_ex_year": calendar_year_cut(ts[i0:], c[i0:, COL_T], year),
        }
    cuts["drop_best_month_2020_04"] = drop_month(res1["ts"], res1["equity"], 2020, 4)
    cuts["drop_best_month_2022_07"] = drop_month(res1["ts"], res1["equity"], 2022, 7)
    out["cut_tests"] = cuts
    for k, v in cuts.items():
        if "strategy" in v:
            print(f"cut ex-{k}: strat {v['strategy']['cagr']*100:6.2f}% / "
                  f"{v['strategy']['max_drawdown']*100:5.2f}%  bench "
                  f"{v['benchmark_ex_year']['cagr']*100:6.2f}% / "
                  f"{v['benchmark_ex_year']['max_drawdown']*100:5.2f}%")
        else:
            print(f"cut {k}: {v['cagr']*100:6.2f}% / {v['max_drawdown']*100:5.2f}%")

    # ---- controls / decomposition ------------------------------------------
    controls = {}
    # optional throttle (rejected centre)
    wt = build_weights(ts, o, c, vol_target=0.75)
    _, s = run_weights(ts, o, c, wt)
    controls["vol_throttle_0.75"] = pack(s)
    print(f"control vol throttle 0.75   CAGR {s['cagr']*100:6.2f}%  "
          f"DD {s['max_drawdown']*100:5.2f}%  Sh {s['sharpe']:4.2f}")

    # constant exposure equal to the centre's mean weight
    mean_w = float(wbar.mean())
    wc = np.zeros((len(ts), 3))
    wc[:, COL_T] = mean_w
    wc[:, COL_B] = 1.0 - mean_w
    _, s = run_weights(ts, o, c, wc)
    controls["constant_exposure_same_mean"] = {**pack(s), "weight": mean_w}
    print(f"control constant {mean_w:.3f}    CAGR {s['cagr']*100:6.2f}%  "
          f"DD {s['max_drawdown']*100:5.2f}%  Sh {s['sharpe']:4.2f}")

    # decomposition controls on daily bars
    pe5 = pe == 5
    wt = build_weights_daily(tsd, od, cd, mask=pe5)
    s = bt.stats(bt.run(tsd, od, cd, wt, DEV_START), 252)
    controls["only_pe5"] = pack(s)
    wt = build_weights_daily(tsd, od, cd, mask=~pe5)
    s = bt.stats(bt.run(tsd, od, cd, wt, DEV_START), 252)
    controls["all_except_pe5"] = pack(s)
    midmask = ~(((pe <= LAST_SESSIONS - 1) | (ps <= FIRST_SESSIONS - 1)))
    wt = build_weights_daily(tsd, od, cd, mask=midmask)
    s = bt.stats(bt.run(tsd, od, cd, wt, DEV_START), 252)
    controls["only_midmonth"] = pack(s)
    print(f"control only pe=5           CAGR {controls['only_pe5']['cagr']*100:6.2f}%  "
          f"DD {controls['only_pe5']['max_drawdown']*100:5.2f}%")
    print(f"control all except pe=5     CAGR {controls['all_except_pe5']['cagr']*100:6.2f}%  "
          f"DD {controls['all_except_pe5']['max_drawdown']*100:5.2f}%")
    print(f"control only midmonth       CAGR {controls['only_midmonth']['cagr']*100:6.2f}%  "
          f"DD {controls['only_midmonth']['max_drawdown']*100:5.2f}%")
    out["controls"] = controls

    # held / unheld open-to-open statistics
    ro = od[1:, COL_T] / od[:-1, COL_T] - 1.0
    inwin = (pe <= LAST_SESSIONS - 1) | (ps <= FIRST_SESSIONS - 1)
    held = inwin[:-1]
    x, y = ro[held], ro[~held]
    out["decomposition"] = {
        "held_days": len(x),
        "held_mean_bp": float(x.mean() * 1e4),
        "held_sd_bp": float(x.std(ddof=1) * 1e4),
        "held_t": float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))),
        "held_hit_rate": float((x > 0).mean()),
        "unheld_mean_bp": float(y.mean() * 1e4),
        "unheld_t": float(y.mean() / (y.std(ddof=1) / np.sqrt(len(y)))),
        "pe5_mean_bp": float(ro[pe[:-1] == 5].mean() * 1e4),
        "pe5_median_bp": float(np.median(ro[pe[:-1] == 5]) * 1e4),
        "pe5_t": float(ro[pe[:-1] == 5].mean() /
                       (ro[pe[:-1] == 5].std(ddof=1) / np.sqrt((pe[:-1] == 5).sum()))),
    }
    print("decomposition", {k: round(v, 3) for k, v in out["decomposition"].items()})

    # ---- causality: truncation test ----------------------------------------
    j = bt.start_index(ts, "2022-01-03")
    j2 = bt.start_index(ts, "2021-12-30")
    w_trunc = build_weights(ts[:j], o[:j], c[:j])
    out["causality"] = {
        "truncation_date": "2022-01-03",
        "compare_through": "2021-12-29",
        "prior_weights_unchanged": bool(np.allclose(w_trunc[:j2], w[:j2])),
    }
    print("causality", out["causality"])

    (HERE / "result.json").write_text(json.dumps(out, indent=2, default=float))
    print("wrote", HERE / "result.json")


if __name__ == "__main__":
    main()
