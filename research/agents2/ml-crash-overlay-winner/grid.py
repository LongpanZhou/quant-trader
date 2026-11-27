"""Robustness grid + ablations for the multi-horizon crash overlay (fast daily sim)."""
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
VOLFEATS = ["rv1", "rv5", "rv20", "rv60", "rv_ratio", "rv_pct", "dvol", "dvol20",
            "range", "range20", "skew20", "vol_ratio", "vol_z20"]
TRENDFEATS = ["sma20", "sma165", "dd20", "dd252", "rsi14", "r5", "r20", "r60", "up20",
              "decay5", "decay20"]
MINFEATS = ["rv_pct", "dvol20", "range20", "vwap_dist", "dd_high", "sma20", "sma165",
            "rsi14", "decay20", "last30"]


def main():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1min")
    w_win, opened, stopped, last, first = winner_daily(ts, o, c)
    dp = DailyPath(ts, o, c)
    dts = dp.dts
    r = bt.run(ts, o, c, w_win, START, band=0.02, slippage_bps=1.0)
    i0 = bt.start_index(ts, START)
    eq1m = pd.Series(r["equity"], index=ts[i0:])
    deq = eq1m.groupby(eq1m.index.date).last()
    deq.index = pd.DatetimeIndex(deq.index)
    base_eq = deq.reindex(dts).to_numpy()
    f = pd.read_pickle(Path(__file__).parent / "features.pkl")
    f.index = pd.to_datetime(f.index)
    f = f.reindex(dts).ffill()
    t = pd.Series(dp.dc[:, 1], index=dts)
    bil = np.tile([0.0, 0.0, 1.0], (len(dts), 1))

    def evaluate(over, rw=None):
        eq, sk = sim_override(dp, base_eq, w_win, over, rw if rw is not None else bil, opened)
        out = []
        for lab, st in STARTS.items():
            j = dts.searchsorted(pd.Timestamp(st)) - sk
            ss = daily_stats(eq[j:] / eq[j] * 100000, dts[j + sk:])
            out += [ss["cagr"], ss["max_drawdown"], ss["sharpe"]]
        return out

    print("winner base:", [f"{v*100:.2f}" for v in evaluate(np.zeros(len(dts), bool))])

    def run_grid(feats, hs, thrs, qs, label=""):
        x = f[feats].to_numpy()
        print(f"\n--- {label} nfeat={len(feats)} ---")
        print(f"{'h':>3s} {'thr':>6s} {'q':>5s}   10y CAGR/DD/Sh  5y CAGR/DD/Sh")
        for h in hs:
            for thr in thrs:
                ft = t.shift(-h) / t - 1.0
                yy = (ft < thr).astype(float)
                yy[~np.isfinite(ft)] = np.nan
                p = walk_forward(dts, x, yy, h)
                rank = pd.Series(p).rolling(252, min_periods=60).rank(pct=True).to_numpy()
                for q in qs:
                    raw = np.isfinite(rank) & (rank >= q)
                    over = np.r_[False, raw[:-1]]
                    v = evaluate(over)
                    print(f"{h:3d} {thr:6.2f} {q:5.2f}   "
                          f"{v[0]*100:5.1f}/{v[1]*100:5.1f}/{v[2]:.2f}  "
                          f"{v[3]*100:5.1f}/{v[4]*100:5.1f}/{v[5]:.2f}")

    run_grid(FEATS, (10, 15, 20, 25), (-0.10, -0.12, -0.15, -0.18), (0.80, 0.85, 0.90, 0.95), "ALL")
    run_grid(VOLFEATS, (20,), (-0.12, -0.15, -0.18), (0.85, 0.90, 0.95), "VOL-ONLY")
    run_grid(TRENDFEATS, (20,), (-0.12, -0.15, -0.18), (0.85, 0.90, 0.95), "TREND-ONLY")
    run_grid(MINFEATS, (20,), (-0.12, -0.15, -0.18), (0.85, 0.90, 0.95), "COMPACT-10")


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    main()
