"""Screen 2: multi-horizon underperformance models on the winner + vol-target benchmark."""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
from analyze2 import winner_daily  # noqa: E402
from proto import walk_forward  # noqa: E402
from screen import DailyPath, sim_override, daily_stats  # noqa: E402

START, END = "2017-01-03", "2026-10-23"
STARTS = {"10y": "2017-01-03", "5y": "2021-10-25"}
FEATS = ["rv1", "rv5", "rv20", "rv60", "rv_ratio", "rv_pct", "skew1", "skew20",
         "dvol", "dvol20", "vwap_dist", "dd_high", "first30", "last30", "close_loc",
         "gap", "gap20", "intraday", "up20", "dd20", "dd252", "sma20", "sma165",
         "rsi14", "decay5", "decay20", "bil5", "dow", "range", "range20",
         "vol_ratio", "vol_z20", "rv_x_trend", "skew_x_dd"]
REPL = {
    "bil": np.array([0.0, 0.0, 1.0]),
    "qqq": np.array([1.0, 0.0, 0.0]),
    "half": np.array([0.0, 0.5, 0.5]),
    "third": np.array([0.5, 0.0, 0.5]),
}


def fwd_excess(dp, dts, h):
    t = pd.Series(dp.dc[:, 1], index=dts)
    b = pd.Series(dp.dc[:, 2], index=dts)
    ft = np.log(t.shift(-h) / t) - np.log(b.shift(-h) / b)
    return ft


def main():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1min")
    w_win, opened, stopped, last, first = winner_daily(ts, o, c)
    dp = DailyPath(ts, o, c)
    dts = dp.dts
    r = bt.run(ts, o, c, w_win, START, band=0.02, slippage_bps=1.0)
    i_start = bt.start_index(ts, START)
    eq1m = pd.Series(r["equity"], index=ts[i_start:])
    deq = eq1m.groupby(eq1m.index.date).last()
    deq.index = pd.DatetimeIndex(deq.index)
    base_eq = deq.reindex(dts).to_numpy()

    f = pd.read_pickle(Path(__file__).parent / "features.pkl")
    f.index = pd.to_datetime(f.index)
    f = f.reindex(dts).ffill()
    x = f[FEATS].to_numpy()

    def report(tag, over):
        parts = []
        rw = np.tile(REPL[MODE], (len(dts), 1))
        for lab, st in STARTS.items():
            eq, sk = sim_override(dp, base_eq, w_win, over, rw, opened)
            j = dts.searchsorted(pd.Timestamp(st)) - sk
            ss = daily_stats(eq[j:] / eq[j] * 100000, dts[j + sk:])
            parts.append(f"{ss['cagr']*100:5.1f}/{ss['max_drawdown']*100:5.1f}/{ss['sharpe']:.2f}")
        print(f"{tag:38s} " + "  ".join(parts))

    global MODE
    print(f"winner fast: 58.7/41.6/1.23  (1m 58.8/44.6/1.24)")

    # --- multi-horizon underperformance ---
    probs = {}
    for h in (5, 10, 20):
        y = (fwd_excess(dp, dts, h) < 0).astype(float)
        y[~np.isfinite(fwd_excess(dp, dts, h))] = np.nan
        probs[h] = walk_forward(dts, x, y, h)
        print(f"h{h}: base {np.nanmean(y[dts>=pd.Timestamp('2017-01-03')]):.3f}")
    ranks = np.column_stack([
        pd.Series(probs[h]).rolling(252, min_periods=60).rank(pct=True).to_numpy()
        for h in (5, 10, 20)])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        avg = np.nanmean(ranks, axis=1)
    avg = np.where(np.isfinite(avg), avg, 1.0)

    print("\nmulti-horizon underperformance: bottom-q rank -> risk-off")
    for MODE in ("bil", "qqq", "half", "third"):
        for q in (0.10, 0.15, 0.20, 0.30):
            raw = avg < q
            over = np.r_[False, raw[:-1]]
            report(f"MH under q{q:.2f} {MODE}", over)

    # --- multi-horizon crash ---
    print("\nmulti-horizon crash: TQQQ h-day return below -6/-9/-12%")
    for h, thr in ((5, -0.06), (5, -0.09), (10, -0.12), (20, -0.15)):
        t = pd.Series(dp.dc[:, 1], index=dts)
        ft = (t.shift(-h) / t - 1.0)
        y = (ft < thr).astype(float)
        y[~np.isfinite(ft)] = np.nan
        p = walk_forward(dts, x, y, h)
        rk = pd.Series(p).rolling(252, min_periods=60).rank(pct=True).to_numpy()
        for MODE in ("bil", "qqq"):
            for q in (0.80, 0.90):
                raw = np.isfinite(rk) & (rk >= q)
                over = np.r_[False, raw[:-1]]
                report(f"MH crash h{h} {thr} q{q:.2f} {MODE}", over)

    # --- vol target benchmark (not ML) ---
    print("\nvol-target benchmark: w_TQQQ = min(1, target/realized20), rest BIL")
    rv20 = f["rv20"].to_numpy() * np.sqrt(390)  # daily vol from 1m rv
    for tgt in (0.35, 0.45, 0.55):
        wv = np.clip(tgt / np.where(rv20 > 1e-6, rv20, tgt), 0, 1)
        over = np.ones(len(dts), bool)
        rwt = np.zeros((len(dts), 3))
        rwt[:, 1] = wv
        rwt[:, 2] = 1 - wv
        parts = []
        for lab, st in STARTS.items():
            eq, sk = sim_override(dp, base_eq, w_win, over, rwt, opened)
            j = dts.searchsorted(pd.Timestamp(st)) - sk
            ss = daily_stats(eq[j:] / eq[j] * 100000, dts[j + sk:])
            parts.append(f"{ss['cagr']*100:5.1f}/{ss['max_drawdown']*100:5.1f}/{ss['sharpe']:.2f}")
        print(f"  vol target {tgt:.2f}                     " + "  ".join(parts))


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    main()
