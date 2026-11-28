"""Session-timing TQQQ: overnight + opening drive, with a conditional late-day leg.

Standalone strategy, development window only (2016-01-04 .. 2023-12-29).

Rules
-----
Universe: QQQ (volatility input), TQQQ (position), cash.  The position is a
session-window allocation, not a daily trend call:

    r_k = TQQQ close(14:29) / TQQQ open(09:30) - 1

    r_k >  0: enter TQQQ at the 14:30 open, hold through the overnight and
              the next session's first 30 minutes, exit at the 10:00 open.
    r_k <= 0: wait, enter at the 15:59 open, hold the overnight and the next
              session's first 30 minutes, exit at the 10:00 open.

Size: s_k = min(1, 0.25 / sigma_k), where sigma_k is the annualised stdev of
the last 10 completed QQQ daily log returns through session k-1.  The raw
strategy (s=1) is reported separately.

No daily trend SMA, no volatility/drawdown regime as the primary signal, no
relative strength, no drawdown recovery.  Idle weight is cash (0%).

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    $env:BT_THREADS = "1"
    python research/strategies/family-session-timing/strategy.py
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
DEC_MIN = 299        # bar 14:29 (0-based offset from 09:30); entry 14:30
THR = 0.0            # session is "up" if r_k > 0
END_MIN = 30         # exit at the 10:00 open
VOL_TARGET = 0.25    # annualised QQQ vol budget
VOL_LOOK = 10


# --------------------------------------------------------------------------- #
# data / signals
# --------------------------------------------------------------------------- #
def load_panel(start: str = DEV_START, end: str = DEV_END):
    return bt.panel(SYMBOLS, start, end, "1min", warmup_days=0)


def _warm_daily_closes(first_session_date) -> np.ndarray:
    """QQQ total-return daily closes strictly before the intraday archive."""
    daily = pd.read_parquet(bt.DATA_DIR / "QQQ-1d-yahoo.parquet")
    daily["date"] = pd.to_datetime(daily["date"]).dt.date
    pre = daily[daily["date"] < first_session_date].sort_values("date")
    return pre["adjclose"].to_numpy(dtype=float)


def daily_sigma(ts, c, look: int = VOL_LOOK) -> np.ndarray:
    """Annualised stdev of the last `look` completed QQQ daily log returns.

    `sig[k]` uses returns through session k-1, so it is known at the 14:29
    decision of session k.  The 2015 daily warmup makes sig[0] finite.
    """
    dates, first, last = bt.day_bounds(ts)
    q58 = np.asarray(c, dtype=float)[last, CQ]
    pre = _warm_daily_closes(dates[first][0])
    q_all = np.r_[pre, q58]
    lr = np.diff(np.log(q_all))
    s = pd.Series(lr).rolling(look).std().to_numpy() * np.sqrt(252)
    return s[len(pre) - 2: len(pre) - 2 + len(first)]


# --------------------------------------------------------------------------- #
# weights
# --------------------------------------------------------------------------- #
def build_weights(ts, o, c, dec_min: int = DEC_MIN, thr: float = THR,
                  end_min: int = END_MIN, vol_target: float | None = VOL_TARGET,
                  vol_look: int = VOL_LOOK, signal: str = "TQQQ",
                  stale: bool = False, size_override: float | None = None,
                  return_diag: bool = False):
    """Return the (n, 3) weight matrix; column 1 is TQQQ, column 2 cash = 0.

    `dec_min` is the 0-based bar whose close is the signal; the entry is the
    next bar's open.  `end_min` is the offset of the exit bar's open on the
    next session (30 = 10:00).
    """
    dates, first, last = bt.day_bounds(ts)
    n = len(first)
    o = np.asarray(o, dtype=float)
    c = np.asarray(c, dtype=float)
    sig = None if size_override is not None else daily_sigma(ts, c, vol_look)
    w = np.zeros((len(ts), 3))
    early = np.zeros(n, dtype=bool)
    size_arr = np.zeros(n)

    for k in range(n):
        f, l = int(first[k]), int(last[k])
        if size_override is not None:
            size = float(size_override)
        elif vol_target is None:
            size = 1.0
        else:
            s = sig[k]
            size = 0.0 if not np.isfinite(s) else min(1.0, vol_target / s)
        size_arr[k] = size

        col = CT if signal == "TQQQ" else CQ
        kk = k - 1 if stale else k
        if kk < 0:
            r = 0.0
        else:
            fk, lk = int(first[kk]), int(last[kk])
            r = c[min(fk + dec_min, lk), col] / o[fk, col] - 1.0
        early[k] = r > thr

        en = f + dec_min + 1 if early[k] else l
        en = min(max(en, f), l)
        w[en - 1, CT] = size          # fill at `en` open
        w[en:l + 1, CT] = size        # hold through the close

        if k + 1 < n:
            fn, ln = int(first[k + 1]), int(last[k + 1])
            hold_end = min(fn + end_min - 2, ln)
            if hold_end >= fn:
                w[fn:hold_end + 1, CT] = size   # overnight + next open window
            ex = fn + end_min - 1
            if ex <= ln:
                w[ex, CT] = 0.0                 # exit at end_min open

    w[-1] = w[-2]
    assert w.min() >= -1e-12 and w.max() <= 1.0 + 1e-12
    assert w.sum(axis=1).max() <= 1.0 + 1e-9
    if return_diag:
        return w, early, size_arr
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
    s = pd.Series(res["equity"], index=pd.to_datetime(res["ts"]))
    return s.groupby(s.index.date).last().pct_change().dropna()


def daily_close_returns(ts, close) -> pd.Series:
    s = pd.Series(close, index=pd.to_datetime(ts))
    return s.groupby(s.index.date).last().pct_change().dropna()


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
    s = pd.Series(equity, index=pd.to_datetime(ts))
    d = s.groupby(s.index.date).last()
    r = d.pct_change().dropna()
    r = r[np.array([x.year != year for x in r.index])]
    eq = np.cumprod(1.0 + r.to_numpy())
    years = len(r) / 252.0
    peak = np.maximum.accumulate(eq)
    return {"cagr": float(eq[-1] ** (1 / years) - 1),
            "max_drawdown": float(-(eq / peak - 1).min()),
            "years": float(years)}


def clock_exposure(early: np.ndarray, size: np.ndarray) -> dict:
    """Clock-time exposure: held minutes / 1440, weighted by size."""
    # 14:30 entry -> 10:00 next day = 1170 min; 15:59 entry -> 10:00 = 1081 min
    held = np.where(early, 1170.0, 1081.0)
    return {
        "clock_time_held_frac": float(np.mean(held / 1440.0)),
        "clock_time_exposure": float(np.mean(size * held / 1440.0)),
        "early_fraction": float(np.mean(early)),
        "mean_size": float(np.mean(size)),
    }


def segment_decomposition(ts, o, c):
    """Open-to-open segment returns (TQQQ), for the mechanism table."""
    dates, first, last = bt.day_bounds(ts)
    n = len(first)
    o = np.asarray(o, float)
    T = CT

    def seg(a, b):
        ia = np.minimum(first + a, last)
        ib = np.minimum(first + b, last)
        return o[ib, T] / o[ia, T] - 1.0

    night = np.r_[np.nan, o[first[1:], T] / o[last[:-1], T] - 1.0]
    open30 = seg(0, 30)
    mid = seg(30, 300)
    late90 = seg(300, 389)
    late30 = seg(360, 389)
    r1429 = np.array([c[int(first[k]) + min(299, int(last[k]) - int(first[k])), CT]
                      / o[int(first[k]), CT] - 1.0 for k in range(n)])
    up = r1429 > 0
    out = {}
    for lab, x in (("overnight", night[1:]), ("open30", open30),
                   ("midday_1000_1430", mid), ("late90_1430_1559", late90),
                   ("late30_1530_1559", late30)):
        out[lab] = {"mean_bp": float(np.nanmean(x) * 1e4),
                    "log_sum": float(np.nansum(np.log1p(x))),
                    "win": float(np.nanmean(x > 0))}
    out["late90_up"] = {"n": int(up.sum()),
                        "mean_bp": float(late90[up].mean() * 1e4),
                        "log_sum": float(np.log1p(late90[up]).sum()),
                        "win": float(np.mean(late90[up] > 0))}
    out["late90_down"] = {"n": int((~up).sum()),
                          "mean_bp": float(late90[~up].mean() * 1e4),
                          "log_sum": float(np.log1p(late90[~up]).sum()),
                          "win": float(np.mean(late90[~up] > 0))}
    return out


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main():
    ts, o, c = load_panel()
    print(f"panel {len(ts):,} bars, {len(np.unique(ts.date))} sessions, "
          f"{ts[0].date()} .. {ts[-1].date()}")

    w, early, size = build_weights(ts, o, c, return_diag=True)

    out = {
        "strategy": "session-timing-close-open-drive",
        "directory": "research/strategies/family-session-timing",
        "window": {"start": DEV_START, "end": DEV_END, "marks": "1min",
                   "fills": "next-minute open, 2% band", "idle": "cash (0%)"},
        "rules": {
            "signal": "TQQQ close(14:29) / TQQQ open(09:30) - 1",
            "up_session": "enter 14:30, hold overnight + next 09:30-10:00, exit 10:00",
            "down_session": "enter 15:59, hold overnight + next 09:30-10:00, exit 10:00",
            "size": "min(1, 0.25 / QQQ 10-day annualised vol through k-1)",
            "no": "daily trend SMA, vol/drawdown regime, relative strength, recovery",
        },
        "dev": {},
    }

    results = {}
    for slip in (0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 10.0):
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

    ce = clock_exposure(early, size)
    out["exposure"] = {"bar_time": float(np.mean(w[:, CT] > 0)),
                       "bar_time_mean_weight": float(np.mean(w[:, CT])),
                       **ce}
    out["corr_daily_tqqq"] = float(
        daily_returns(res1).corr(daily_close_returns(ts, c[:, CT])))
    db = daily_close_returns(ts, c[:, CT])
    dr = daily_returns(res1)
    out["beta_daily_tqqq"] = float(np.polyfit(db.to_numpy(), dr.to_numpy(), 1)[0])

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
    out["segment_decomposition"] = segment_decomposition(ts, o, c)

    # ---- pre-registered grid (8 cells) --------------------------------------
    grid_specs = [
        ("1 entry14:00 thr0.0", 269, 0.0),
        ("2 entry14:00 thr0.5", 269, 0.005),
        ("3 entry14:30 thr0.0 (centre)", 299, 0.0),
        ("4 entry14:30 thr0.5", 299, 0.005),
        ("5 entry15:00 thr0.0", 329, 0.0),
        ("6 entry15:00 thr0.5", 329, 0.005),
        ("7 entry15:30 thr0.0", 359, 0.0),
        ("8 entry15:30 thr0.5", 359, 0.005),
    ]
    grid = []
    for label, dec, thr in grid_specs:
        wt, et, sz = build_weights(ts, o, c, dec_min=dec, thr=thr,
                                   return_diag=True)
        row = {"cell": label, "dec_min": dec, "entry_offset_min": dec + 1,
               "thr": thr, "early_fraction": float(np.mean(et)),
               "mean_size": float(np.mean(sz))}
        for slip in (1.0, 5.0):
            _, ss = run_weights(ts, o, c, wt, slip=slip)
            row[f"{int(slip)}bp"] = pack(ss)
        grid.append(row)
        print(f"grid {label:34s} 1bp {row['1bp']['cagr']*100:6.2f}% / "
              f"{row['1bp']['max_drawdown']*100:5.2f}%  Sh {row['1bp']['sharpe']:.2f}  "
              f"5bp {row['5bp']['cagr']*100:6.2f}%  early {row['early_fraction']*100:.1f}%")
    out["grid"] = grid

    # ---- neighbours (robustness, not used to choose the centre) -------------
    neigh = []

    def add_neigh(name, **kw):
        wt = build_weights(ts, o, c, **kw)
        _, ss = run_weights(ts, o, c, wt, slip=1.0)
        _, s5 = run_weights(ts, o, c, wt, slip=5.0)
        neigh.append({"name": name, **pack(ss), "5bp_cagr": float(s5["cagr"]),
                      "5bp_dd": float(s5["max_drawdown"])})
        print(f"neigh {name:30s} 1bp {ss['cagr']*100:6.2f}% / {ss['max_drawdown']*100:5.2f}%  "
              f"Sh {ss['sharpe']:4.2f}  5bp {s5['cagr']*100:6.2f}%")

    add_neigh("entry 14:15", dec_min=284)
    add_neigh("entry 14:45", dec_min=314)
    add_neigh("thr -0.25%", thr=-0.0025)
    add_neigh("thr +0.25%", thr=0.0025)
    add_neigh("exit 09:45", end_min=15)
    add_neigh("exit 10:15", end_min=45)
    add_neigh("exit 10:30", end_min=60)
    add_neigh("exit 11:00", end_min=90)
    add_neigh("vol target 0.20", vol_target=0.20)
    add_neigh("vol target 0.30", vol_target=0.30)
    add_neigh("vol target 0.35", vol_target=0.35)
    add_neigh("vol target 0.40", vol_target=0.40)
    add_neigh("vol lookback 5", vol_look=5)
    add_neigh("vol lookback 20", vol_look=20)
    add_neigh("QQQ intraday signal", signal="QQQ")
    add_neigh("raw (no vol target)", vol_target=None)
    add_neigh("stale signal", stale=True)
    out["neighbours"] = neigh

    # ---- controls ------------------------------------------------------------
    controls = {}
    # raw, no vol target
    wraw = build_weights(ts, o, c, vol_target=None)
    _, ss = run_weights(ts, o, c, wraw)
    controls["raw_no_vol_target"] = pack(ss)
    # constant size at the mean of the centre
    wconst = build_weights(ts, o, c, size_override=float(np.mean(size)))
    _, ss = run_weights(ts, o, c, wconst)
    controls["constant_size_at_mean"] = pack(ss)
    # buy & hold
    wb = np.zeros((len(ts), 3)); wb[:, CT] = 1.0
    _, ss = run_weights(ts, o, c, wb)
    controls["buy_hold_tqqq_sim"] = pack(ss)
    # overnight only, same size schedule
    wo = np.zeros((len(ts), 3))
    dates, first, last = bt.day_bounds(ts)
    for k in range(len(first) - 1):
        wo[int(last[k]) - 1, CT] = size[k]
        wo[int(last[k]), CT] = 0.0
    wo[-1] = wo[-2]
    _, ss = run_weights(ts, o, c, wo)
    controls["overnight_only"] = pack(ss)
    # late 90m only (14:30-15:59), same size schedule
    wl = np.zeros((len(ts), 3))
    for k in range(len(first)):
        f, l = int(first[k]), int(last[k])
        if l - f < 300:
            continue
        wl[f + 299, CT] = size[k]          # fill 14:30
        wl[f + 300:l - 1, CT] = size[k]    # hold through 15:57
        wl[l - 1, CT] = 0.0                # fill 15:59
    wl[-1] = wl[-2]
    _, ss = run_weights(ts, o, c, wl)
    controls["late90_only"] = pack(ss)
    out["controls"] = controls
    for k, v in controls.items():
        print(f"control {k:28s} CAGR {v['cagr']*100:6.2f}%  DD {v['max_drawdown']*100:5.2f}%  "
              f"Sh {v['sharpe']:4.2f}")

    # ---- placebos ------------------------------------------------------------
    rng = np.random.default_rng(11)
    nd = len(first)
    n_early = int(early.sum())

    def build_random_entry(entry_draw):
        wt = np.zeros((len(ts), 3))
        for k in range(nd):
            f, l = int(first[k]), int(last[k])
            s = size[k]
            if k + 1 >= nd:
                continue
            en = min(f + int(entry_draw[k]), l)
            wt[en - 1, CT] = s
            wt[en:l + 1, CT] = s
            fn, ln = int(first[k + 1]), int(last[k + 1])
            hold_end = min(fn + 28, ln)
            wt[fn:hold_end + 1, CT] = s
            wt[fn + 29, CT] = 0.0
        wt[-1] = wt[-2]
        return wt

    def build_random_subset(mask):
        wt = np.zeros((len(ts), 3))
        for k in range(nd):
            f, l = int(first[k]), int(last[k])
            s = size[k]
            if k + 1 >= nd:
                continue
            en = f + 300 if mask[k] else l
            en = min(max(en, f), l)
            wt[en - 1, CT] = s
            wt[en:l + 1, CT] = s
            fn, ln = int(first[k + 1]), int(last[k + 1])
            hold_end = min(fn + 28, ln)
            wt[fn:hold_end + 1, CT] = s
            wt[fn + 29, CT] = 0.0
        wt[-1] = wt[-2]
        return wt

    NPL = 100
    real_cagr = float(s1["cagr"])
    real_dd = float(s1["max_drawdown"])
    cagrs = np.empty(NPL); dds = np.empty(NPL)
    for j in range(NPL):
        draw = rng.integers(31, 390, nd)   # 10:01..15:59, after the 10:00 exit
        _, sj = run_weights(ts, o, c, build_random_entry(draw))
        cagrs[j] = sj["cagr"]; dds[j] = sj["max_drawdown"]
    out["placebo_random_entry"] = {
        "n_draws": NPL, "real_cagr": real_cagr, "real_dd": real_dd,
        "mean_cagr": float(cagrs.mean()), "p95_cagr": float(np.percentile(cagrs, 95)),
        "max_cagr": float(cagrs.max()), "p_value_cagr": float((cagrs >= real_cagr).mean()),
        "mean_dd": float(dds.mean()), "p05_dd": float(np.percentile(dds, 5)),
        "min_dd": float(dds.min()), "dd_percentile": float((dds >= real_dd).mean()),
    }
    print("placebo random entry", {k: round(float(v), 4)
                                    for k, v in out["placebo_random_entry"].items()})

    cagrs2 = np.empty(NPL); dds2 = np.empty(NPL)
    for j in range(NPL):
        pick = rng.choice(nd, n_early, replace=False)
        mask = np.zeros(nd, bool); mask[pick] = True
        _, sj = run_weights(ts, o, c, build_random_subset(mask))
        cagrs2[j] = sj["cagr"]; dds2[j] = sj["max_drawdown"]
    out["placebo_random_subset"] = {
        "n_draws": NPL, "n_early": n_early, "real_cagr": real_cagr,
        "real_dd": real_dd,
        "mean_cagr": float(cagrs2.mean()), "p95_cagr": float(np.percentile(cagrs2, 95)),
        "max_cagr": float(cagrs2.max()), "p_value_cagr": float((cagrs2 >= real_cagr).mean()),
        "mean_dd": float(dds2.mean()), "p05_dd": float(np.percentile(dds2, 5)),
        "min_dd": float(dds2.min()), "dd_percentile": float((dds2 >= real_dd).mean()),
    }
    print("placebo random subset", {k: round(float(v), 4)
                                     for k, v in out["placebo_random_subset"].items()})

    wstale = build_weights(ts, o, c, stale=True)
    _, sstale = run_weights(ts, o, c, wstale)
    out["placebo_stale_signal"] = pack(sstale)
    print(f"placebo stale signal  CAGR {sstale['cagr']*100:.2f}%  "
          f"DD {sstale['max_drawdown']*100:.2f}%  Sh {sstale['sharpe']:.2f}")

    # ---- cut tests -----------------------------------------------------------
    cuts = {}
    for year in (2016, 2018, 2019, 2020, 2021, 2022, 2023):
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

    # ---- causality: truncation ----------------------------------------------
    j = bt.start_index(ts, "2022-01-03")
    w_trunc = build_weights(ts[:j], o[:j], c[:j])
    n_cmp = j
    out["causality_day_boundary"] = {
        "truncation_date": "2022-01-03",
        "prior_weights_unchanged": bool(np.allclose(w_trunc[:n_cmp], w[:n_cmp])),
        "max_abs_diff": float(np.max(np.abs(w_trunc[:n_cmp] - w[:n_cmp]))),
    }
    print("causality day boundary", out["causality_day_boundary"])

    j2 = bt.start_index(ts, "2020-03-12 11:07")
    w_trunc2 = build_weights(ts[:j2], o[:j2], c[:j2])
    n_cmp2 = bt.start_index(ts, "2020-03-12")
    out["causality_intraday_cut"] = {
        "truncation_date": "2020-03-12 11:07",
        "prior_weights_unchanged": bool(np.allclose(w_trunc2[:n_cmp2], w[:n_cmp2])),
        "max_abs_diff": float(np.max(np.abs(w_trunc2[:n_cmp2] - w[:n_cmp2]))),
    }
    print("causality intraday cut", out["causality_intraday_cut"])

    (HERE / "result.json").write_text(json.dumps(out, indent=2, default=float))
    print("wrote", HERE / "result.json")


if __name__ == "__main__":
    main()
