"""Overnight + intraday trend TQQQ.

Standalone strategy, development window only (2016-01-04 .. 2023-12-29).

Rules
-----
Universe: QQQ (signal), TQQQ (position), BIL (defensive sleeve).  The daily
20/50-session trend owns the overnight position; a fast QQQ intraday stop owns
the session; a weak close skips the night.

    q58[k]     QQQ close of the 15:58 bar of session k
    SMA20/50   means of QQQ daily closes through q58[k]
    trend[k]   (SMA20 > SMA50) OR (q58 > SMA50)      # cross or 50-day reclaim

    session k+1 starts long TQQQ iff trend[k], else BIL all session.
    checks at 10:00, 10:30, ..., 15:30 (close of each 30-minute bar):
        long  and QQQ <= session_open * (1 - 0.006)  -> BIL next minute
        BIL   and QQQ >= session_open                -> TQQQ next minute
    at 15:30 the session state is frozen for the night:
        long at 15:30 and trend at 15:58 up          -> hold TQQQ overnight
        BIL at 15:30 (stopped, not reclaimed)        -> stay BIL overnight
        fresh trend-up at 15:58 from a down day      -> buy TQQQ at 15:59
        trend down at 15:58                          -> BIL overnight
    after a skipped night, re-enter at 09:31 the next session if trend is up.

Fills are next-minute opens (`bt.py` convention: weights[i] is set at bar i's
close and executed at bar i+1's open).  No 2024+ data is loaded.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    $env:BT_THREADS = "1"
    python research/new/overnight-intraday-trend/strategy.py
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

DEV_START, DEV_END = "2016-01-04", "2023-12-29"
BPY = 252 * 390
SYMBOLS = ("QQQ", "TQQQ", "BIL")
CQ, CT, CB = 0, 1, 2

# pre-registered centre
STOP = 0.006
STEP = 30
FIRST_CHECK = 30
NIGHT_AT = 360
TREND_FAST = 20
TREND_SLOW = 50
GATE = "reclaim"          # SMA20>SMA50 OR close>SMA50
SKIP_WEAK_NIGHT = True


# --------------------------------------------------------------------------- #
# panel / signals
# --------------------------------------------------------------------------- #
def load_panel(start: str = DEV_START, end: str = DEV_END):
    return bt.panel(SYMBOLS, start, end, "1min", warmup_days=0)


def _warm_daily_closes(first_session_date) -> np.ndarray:
    """QQQ total-return daily closes strictly before the intraday archive."""
    daily = pd.read_parquet(bt.DATA_DIR / "QQQ-1d-yahoo.parquet")
    daily["date"] = pd.to_datetime(daily["date"]).dt.date
    pre = daily[daily["date"] < first_session_date].sort_values("date")
    return pre["adjclose"].to_numpy(dtype=float)


def _sma(x: np.ndarray, n: int) -> np.ndarray:
    return pd.Series(x).rolling(n, min_periods=n).mean().to_numpy()


def compute_state(ts, o, c, trend_fast: int = TREND_FAST,
                  trend_slow: int = TREND_SLOW, gate: str = GATE):
    """Causal per-session trend state, decided at the 15:58 close."""
    dates, first, last = bt.day_bounds(ts)
    q58 = np.asarray(c, dtype=float)[np.maximum(last - 1, first), CQ]
    pre = _warm_daily_closes(dates[first][0])
    npre = len(pre)
    q_all = np.r_[pre, q58]
    s_fast = _sma(q_all, trend_fast)[npre:]
    s_slow = _sma(q_all, trend_slow)[npre:]
    ok = np.isfinite(s_fast) & np.isfinite(s_slow)
    if gate == "reclaim":
        state = (s_fast > s_slow) | (q58 > s_slow)
    elif gate == "cross":
        state = s_fast > s_slow
    elif gate == "close20":
        state = q58 > s_fast
    elif gate == "close50":
        state = q58 > s_slow
    else:
        raise ValueError(gate)
    state = np.where(ok, state, False).astype(bool)
    return state, {"q58": q58, "s_fast": s_fast, "s_slow": s_slow,
                   "dates": dates, "first": first, "last": last}


# --------------------------------------------------------------------------- #
# per-session intraday path (independent of the daily state)
# --------------------------------------------------------------------------- #
def prepare_session_paths(ts, o, c, stop: float = STOP, step: int = STEP,
                          first_check: int = FIRST_CHECK, night_at: int = NIGHT_AT,
                          close_check: int | None = None,
                          stale_stop: bool = False):
    """For every session, the `on` state from open to close assuming day_on=True.

    A check at offset `off` uses the close of bar off-1 and fills at open[off].
    `stale_stop` uses the prior session's same-minute QQQ path (placebo).
    """
    dates, first, last = bt.day_bounds(ts)
    q = np.asarray(c, dtype=float)[:, CQ]
    paths = []
    for k in range(len(first)):
        f, l = int(first[k]), int(last[k])
        nbar = l - f
        base = float(o[f, CQ])
        if stale_stop and k > 0:
            ref = q[int(first[k - 1]):int(last[k - 1]) + 1]
        else:
            ref = q[f:l + 1]
        checks = [x for x in range(max(first_check, 1), min(376, nbar), step)
                  if x <= night_at]
        if close_check is not None and close_check <= nbar - 1 and close_check not in checks:
            checks.append(close_check)
            checks.sort()
        on = True
        path = np.zeros(nbar + 1, dtype=bool)
        ci = 0
        for i in range(f, l + 1):
            off = i - f
            if stop > 0 and i > f and ci < len(checks) and off == checks[ci]:
                ci += 1
                rj = off - 1
                qv = ref[rj] if 0 <= rj < len(ref) else q[i - 1]
                if on and qv <= base * (1.0 - stop):
                    on = False
                elif (not on) and qv >= base:
                    on = True
            path[off] = on
        paths.append((path, bool(on)))
    return paths


def weights_from_state(ts, o, c, state, paths, skip_weak_night: bool = True):
    """Assemble the (n, 3) weight matrix from a daily trend state."""
    dates, first, last = bt.day_bounds(ts)
    w = np.zeros((len(ts), 3))
    for k in range(len(first)):
        f, l = int(first[k]), int(last[k])
        day_on = bool(state[k - 1]) if k > 0 else False
        path, final_on = paths[k]
        target = path.astype(float) if day_on else np.zeros(len(path))
        if skip_weak_night:
            night_on = bool(state[k]) and (final_on or not day_on)
        else:
            night_on = bool(state[k])
        target[-2] = 1.0 if night_on else 0.0
        target[-1] = 1.0 if night_on else 0.0
        w[f:l + 1, CT] = target
        w[f:l + 1, CB] = 1.0 - target
    w[-1] = w[-2]
    return w


def build_weights(ts, o, c, stop: float = STOP, step: int = STEP,
                  first_check: int = FIRST_CHECK, night_at: int = NIGHT_AT,
                  trend_fast: int = TREND_FAST, trend_slow: int = TREND_SLOW,
                  gate: str = GATE, skip_weak_night: bool = True,
                  close_check: int | None = None,
                  stale_stop: bool = False) -> np.ndarray:
    """Return the (n, 3) weight matrix: column 1 is TQQQ, column 2 is BIL."""
    state, _ = compute_state(ts, o, c, trend_fast, trend_slow, gate)
    paths = prepare_session_paths(ts, o, c, stop, step, first_check, night_at,
                                  close_check, stale_stop)
    w = weights_from_state(ts, o, c, state, paths, skip_weak_night)
    assert (w >= 0).all() and (w.sum(axis=1) <= 1.0 + 1e-9).all()
    return w


# --------------------------------------------------------------------------- #
# evaluation helpers
# --------------------------------------------------------------------------- #
def pack(s: dict) -> dict:
    keys = ("cagr", "max_drawdown", "sharpe", "sortino", "volatility",
            "exposure", "turnover", "fills", "ending_equity", "years")
    return {k: (int(s[k]) if k == "fills" else float(s[k])) for k in keys}


def run_weights(ts, o, c, w, start=DEV_START, slip=1.0):
    r = bt.run(ts, o, c, w, start, band=0.02, slippage_bps=slip)
    return r, bt.stats(r, BPY)


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
            "max_drawdown": float(-(x / peak - 1).min())}


def calendar_year_cut(ts, equity, year: int) -> dict:
    s = pd.Series(equity, index=ts)
    d = s.groupby(ts.date).last()
    r = d.pct_change().dropna()
    r = r[np.array([x.year != year for x in r.index])]
    eq = np.cumprod(1.0 + r.to_numpy())
    years = len(r) / 252.0
    peak = np.maximum.accumulate(eq)
    return {"cagr": float(eq[-1] ** (1 / years) - 1),
            "max_drawdown": float(-(eq / peak - 1).min()),
            "years": float(years)}


def attribution(ts, o, c, w, years):
    """Night P&L (15:59 open -> next 09:30 open) and the residual day P&L."""
    dates, first, last = bt.day_bounds(ts)
    to = np.asarray(o, dtype=float)[:, CT]
    night = to[first[1:]] / to[last[:-1]] - 1.0      # next open / today's 15:59 open
    night_w = np.asarray(w, dtype=float)[last[:-1], CT]  # set at 15:58, fills 15:59
    c_night = float(np.nansum(np.log1p(night_w * night)))
    b_night = float(np.nansum(np.log1p(night)))
    held = night_w > 0.5
    order = np.argsort(night)
    worst = order[:10]
    return {
        "ann_night_strategy": float(np.exp(c_night / years) - 1),
        "ann_night_buy_hold": float(np.exp(b_night / years) - 1),
        "night_log_strategy": c_night,
        "night_log_buy_hold": b_night,
        "nights_held": int(held.sum()),
        "nights_skipped": int((~held).sum()),
        "mean_night_bp_held": float(np.nanmean(night[held]) * 1e4),
        "mean_night_bp_skipped": float(np.nanmean(night[~held]) * 1e4),
        "worst_night_tqqq": float(np.nanmin(night)),
        "worst_night_at_strategy_weight": float(np.nanmin(night_w * night)),
        "worst_10_nights": [
            {"date": str(dates[first][int(i)])[:10], "tqqq_night": float(night[i]),
             "strategy_weight": float(night_w[i])} for i in worst
        ],
    }


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main():
    ts, o, c = load_panel()
    print(f"panel {len(ts):,} bars, {len(np.unique(ts.date))} sessions, "
          f"{ts[0].date()} .. {ts[-1].date()}")

    state, sig = compute_state(ts, o, c)
    paths = prepare_session_paths(ts, o, c)
    w = weights_from_state(ts, o, c, state, paths)

    out = {
        "strategy": "overnight-intraday-trend",
        "directory": "research/new/overnight-intraday-trend",
        "window": {"start": DEV_START, "end": DEV_END, "marks": "1min",
                   "fills": "next-minute open, 2% band",
                   "defensive_sleeve": "BIL"},
        "rules": {
            "trend": "QQQ SMA20 > SMA50 OR QQQ 15:58 close > SMA50",
            "trend_clock": "15:58 ET; owns the overnight and the next session",
            "stop": "QQQ 0.6% below session open -> BIL; reclaim of session open -> TQQQ",
            "check_clock": "10:00, 10:30, ..., 15:30 (30-minute bars)",
            "night": "hold TQQQ only if long at 15:30 and trend up at 15:58; "
                     "weak close skips the night; fresh trend-up buys at 15:59",
            "reentry_after_skip": "09:31 next session if trend still up",
            "warmup": "QQQ daily closes 2015-01-02..2015-12-31",
        },
        "dev": {},
    }

    results = {}
    for slip in (0.0, 1.0, 5.0, 10.0):
        res, s = run_weights(ts, o, c, w, slip=slip)
        results[slip] = (res, s)
        if slip == 0.0:
            out["gross_0bp"] = pack(s)
        else:
            out["dev"][f"{int(slip)}bp"] = pack(s)
        print(f"centre {slip:2.0f}bp  CAGR {s['cagr']*100:6.2f}%  DD {s['max_drawdown']*100:5.2f}%  "
              f"Sharpe {s['sharpe']:4.2f}  expo {s['exposure']*100:.1f}%  fills {s['fills']:,}  "
              f"turnover {s['turnover']:.0f}")

    res1, s1 = results[1.0]
    i0 = bt.start_index(ts, DEV_START)
    bench = bt.benchmark(c[i0:, CT], ts[i0:], BPY)
    out["benchmark_tqqq_sim"] = {k: float(v) for k, v in bench.items()}
    out["benchmark_tqqq_brief"] = {"cagr": 0.3672, "max_drawdown": 0.8229,
                                   "sharpe": 0.82,
                                   "note": "brief's official dev bar, daily-close marks"}

    out["exposure_tqqq"] = float(np.mean(w[:, CT]))
    out["exposure_bil"] = float(np.mean(w[:, CB]))
    out["corr_daily_tqqq"] = float(
        daily_returns(res1).corr(daily_returns({"equity": c[i0:, CT], "ts": ts[i0:]})))

    out["yearly"] = {
        str(k): {"strategy": float(v["strategy"]), "benchmark": float(v["benchmark"])}
        for k, v in bt.yearly(res1["ts"], res1["equity"], c[i0:, CT]).items()
    }
    out["dd_window"] = dd_window(res1["ts"], res1["equity"])
    out["subperiods"] = {
        "2016_2019": subperiod(res1["ts"], res1["equity"], "2016-01-04", "2019-12-31"),
        "2020_2021": subperiod(res1["ts"], res1["equity"], "2020-01-02", "2021-12-31"),
        "2022_2023": subperiod(res1["ts"], res1["equity"], "2022-01-03", "2023-12-29"),
    }
    out["attribution"] = attribution(ts, o, c, w, s1["years"])

    # ---- pre-registered grid (8 cells) --------------------------------------
    grid_specs = [
        ("1 stop0.5 step30 skip reclaim", dict(stop=0.005, step=30, first_check=30, skip_weak_night=True, gate="reclaim")),
        ("2 stop0.6 step30 skip reclaim (centre)", dict(stop=0.006, step=30, first_check=30, skip_weak_night=True, gate="reclaim")),
        ("3 stop0.7 step30 skip reclaim", dict(stop=0.007, step=30, first_check=30, skip_weak_night=True, gate="reclaim")),
        ("4 stop0.6 step15 skip reclaim", dict(stop=0.006, step=15, first_check=15, skip_weak_night=True, gate="reclaim")),
        ("5 stop0.6 step60 skip reclaim", dict(stop=0.006, step=60, first_check=60, skip_weak_night=True, gate="reclaim")),
        ("6 stop0.6 step30 close-reenter reclaim", dict(stop=0.006, step=30, first_check=30, skip_weak_night=False, gate="reclaim")),
        ("7 stop0.6 step30 skip pure-cross", dict(stop=0.006, step=30, first_check=30, skip_weak_night=True, gate="cross")),
        ("8 no stop skip reclaim", dict(stop=0.0, step=30, first_check=30, skip_weak_night=True, gate="reclaim")),
    ]
    grid = []
    path_cache = {}
    for label, kw in grid_specs:
        key = (kw["stop"], kw["step"], kw["first_check"])
        if key not in path_cache:
            path_cache[key] = prepare_session_paths(
                ts, o, c, stop=kw["stop"], step=kw["step"], first_check=kw["first_check"])
        st, _ = compute_state(ts, o, c, gate=kw["gate"])
        wt = weights_from_state(ts, o, c, st, path_cache[key], kw["skip_weak_night"])
        row = {"cell": label, "stop": kw["stop"], "step": kw["step"],
               "first_check": kw["first_check"],
               "skip_weak_night": kw["skip_weak_night"], "gate": kw["gate"],
               "exposure_tqqq": float(np.mean(wt[:, CT]))}
        for slip in (1.0, 5.0, 10.0):
            _, ss = run_weights(ts, o, c, wt, slip=slip)
            row[f"{int(slip)}bp"] = pack(ss)
        grid.append(row)
        print(f"grid {label:40s} 1bp {row['1bp']['cagr']*100:6.2f}% / "
              f"{row['1bp']['max_drawdown']*100:5.2f}%  Sh {row['1bp']['sharpe']:.2f}  "
              f"5bp {row['5bp']['cagr']*100:6.2f}%  10bp {row['10bp']['cagr']*100:6.2f}%  "
              f"exp {row['exposure_tqqq']*100:.1f}%")
    out["grid"] = grid

    # ---- neighbours (robustness, not used to choose the centre) -------------
    neigh = []
    specs = [
        ("stop0.55 step30", dict(stop=0.0055, step=30)),
        ("stop0.65 step30", dict(stop=0.0065, step=30)),
        ("step15 first45", dict(stop=0.006, step=15, first_check=45)),
        ("step30 first15", dict(stop=0.006, step=30, first_check=15)),
        ("step30 first60", dict(stop=0.006, step=30, first_check=60)),
        ("night 15:00", dict(stop=0.006, step=30, night_at=300)),
        ("night 15:15", dict(stop=0.006, step=30, night_at=330)),
        ("night 15:45 step15", dict(stop=0.006, step=15, night_at=375)),
        ("true 15:55 close check", dict(stop=0.006, step=30, close_check=385)),
        ("gate close20", dict(stop=0.006, step=30, gate="close20")),
        ("gate close50", dict(stop=0.006, step=30, gate="close50")),
    ]
    for label, kw in specs:
        kw = dict(kw)
        gate = kw.pop("gate", "reclaim")
        st, _ = compute_state(ts, o, c, gate=gate)
        wt = weights_from_state(ts, o, c, st, prepare_session_paths(ts, o, c, **kw))
        _, ss = run_weights(ts, o, c, wt, slip=1.0)
        _, s5 = run_weights(ts, o, c, wt, slip=5.0)
        neigh.append({"name": label, **pack(ss), "5bp_cagr": float(s5["cagr"])})
        print(f"neigh {label:24s} 1bp {ss['cagr']*100:6.2f}% / {ss['max_drawdown']*100:5.2f}%  "
              f"Sh {ss['sharpe']:4.2f}  5bp {s5['cagr']*100:6.2f}%")
    out["neighbours"] = neigh

    # ---- controls ------------------------------------------------------------
    controls = {}
    # no stop
    wt = weights_from_state(ts, o, c, state, prepare_session_paths(ts, o, c, stop=0.0))
    _, ss = run_weights(ts, o, c, wt)
    controls["no_stop"] = pack(ss)
    # always long, same stop/skip
    al = np.ones(len(sig["q58"]), dtype=bool)
    wt = weights_from_state(ts, o, c, al, paths)
    _, ss = run_weights(ts, o, c, wt)
    controls["always_long_stop"] = pack(ss)
    # no skip
    wt = weights_from_state(ts, o, c, state, paths, skip_weak_night=False)
    _, ss = run_weights(ts, o, c, wt)
    controls["no_skip_night"] = pack(ss)
    # cash idle instead of BIL
    wt = w.copy()
    wt[:, CB] = 0.0
    _, ss = run_weights(ts, o, c, wt)
    controls["cash_idle"] = pack(ss)
    # overnight only (TQQQ from 15:59 to next open when trend up)
    wo = np.zeros((len(ts), 3))
    for k in range(len(sig["first"])):
        f, l = int(sig["first"][k]), int(sig["last"][k])
        on = 1.0 if state[k] else 0.0
        wo[l - 1, CT] = on
        wo[l - 1, CB] = 1.0 - on
        wo[l, CT] = 0.0
        wo[l, CB] = 1.0 - on if on == 0 else 0.0
    wo[-1] = wo[-2]
    _, ss = run_weights(ts, o, c, wo)
    controls["overnight_only"] = pack(ss)
    # buy & hold simulated
    wb = np.zeros((len(ts), 3))
    wb[:, CT] = 1.0
    _, ss = run_weights(ts, o, c, wb)
    controls["buy_hold_tqqq_sim"] = pack(ss)
    out["controls"] = controls
    for k, v in controls.items():
        print(f"control {k:28s} CAGR {v['cagr']*100:6.2f}%  DD {v['max_drawdown']*100:5.2f}%  "
              f"Sh {v['sharpe']:4.2f}")

    # ---- placebo A: shifted daily trend state -------------------------------
    rng = np.random.default_rng(11)
    nd = len(sig["q58"])
    real = s1["cagr"]
    cagrs = []
    dds = []
    for _ in range(100):
        shift = int(rng.integers(20, nd - 20))
        st = np.roll(state, shift)
        wt = weights_from_state(ts, o, c, st, paths)
        _, ss = run_weights(ts, o, c, wt)
        cagrs.append(ss["cagr"])
        dds.append(ss["max_drawdown"])
    cagrs = np.array(cagrs)
    dds = np.array(dds)
    out["placebo_trend_shift"] = {
        "n_draws": 100, "real_cagr": float(real),
        "real_dd": float(s1["max_drawdown"]),
        "mean_cagr": float(cagrs.mean()), "p95_cagr": float(np.percentile(cagrs, 95)),
        "p_value_cagr": float((cagrs >= real).mean()),
        "max_cagr": float(cagrs.max()),
        "mean_dd": float(dds.mean()), "p05_dd": float(np.percentile(dds, 5)),
        "dd_percentile": float((dds >= s1["max_drawdown"]).mean()),
    }
    print("placebo trend shift", {k: round(float(v), 4) for k, v in out["placebo_trend_shift"].items()})

    # ---- placebo B: stale intraday stop signal ------------------------------
    stale_paths = prepare_session_paths(ts, o, c, stale_stop=True)
    wt = weights_from_state(ts, o, c, state, stale_paths)
    _, ss = run_weights(ts, o, c, wt)
    out["placebo_stale_stop"] = pack(ss)
    print(f"placebo stale stop  CAGR {ss['cagr']*100:6.2f}%  DD {ss['max_drawdown']*100:5.2f}%  "
          f"Sh {ss['sharpe']:.2f}")

    # ---- cut tests -----------------------------------------------------------
    cuts = {}
    for year in (2016, 2019, 2020, 2022, 2023):
        cuts[str(year)] = {
            "strategy": calendar_year_cut(res1["ts"], res1["equity"], year),
            "benchmark_ex_year": calendar_year_cut(ts[i0:], c[i0:, CT], year),
        }
    out["cut_tests"] = cuts
    for y, v in cuts.items():
        print(f"cut ex-{y}: strat {v['strategy']['cagr']*100:6.2f}% / "
              f"{v['strategy']['max_drawdown']*100:5.2f}%  "
              f"bench {v['benchmark_ex_year']['cagr']*100:6.2f}% / "
              f"{v['benchmark_ex_year']['max_drawdown']*100:5.2f}%")

    # ---- causality: truncation at 2022-01-03 --------------------------------
    j = bt.start_index(ts, "2022-01-03")
    w_trunc = build_weights(ts[:j], o[:j], c[:j])
    n_cmp = j - 1  # exclude the 1-bar partial session at the cut
    out["causality"] = {
        "truncation_date": "2022-01-03",
        "prior_weights_unchanged": bool(np.allclose(w_trunc[:n_cmp], w[:n_cmp])),
        "max_abs_diff": float(np.max(np.abs(w_trunc[:n_cmp] - w[:n_cmp]))),
    }
    print("causality", out["causality"])

    (HERE / "result.json").write_text(json.dumps(out, indent=2, default=float))
    print("wrote", HERE / "result.json")


if __name__ == "__main__":
    main()
