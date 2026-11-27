"""Evaluate graduated BIL/QQQ crash overlay on the exact harness."""
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

START, END = "2017-01-03", "2026-10-23"
BARS = 252 * 390
FEATS = ["rv1", "rv5", "rv20", "rv60", "rv_ratio", "rv_pct", "skew1", "skew20",
         "dvol", "dvol20", "vwap_dist", "dd_high", "first30", "last30", "close_loc",
         "gap", "gap20", "intraday", "up20", "dd20", "dd252", "sma20", "sma165",
         "rsi14", "decay5", "decay20", "bil5", "dow", "range", "range20",
         "vol_ratio", "vol_z20", "rv_x_trend", "skew_x_dd"]


def main():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1min")
    w_win, opened, stopped, last, first = winner_daily(ts, o, c)
    dates = np.array([t.date() for t in ts])
    dts = pd.DatetimeIndex([pd.Timestamp(x) for x in dates[last]])
    day_of_bar = pd.Index(dates).map({d: k for k, d in enumerate(dts.date)}).to_numpy()
    f = pd.read_pickle(Path(__file__).parent / "features.pkl")
    f.index = pd.to_datetime(f.index)
    f = f.reindex(dts).ffill()
    x = f[FEATS].to_numpy()
    t = pd.Series(c[last, 1], index=dts)
    ft = t.shift(-20) / t - 1.0
    y = (ft < -0.15).astype(float)
    y[~np.isfinite(ft)] = np.nan
    p = walk_forward(dts, x, y, 20)
    rank = pd.Series(p).rolling(252, min_periods=60).rank(pct=True).to_numpy()

    for q_lo, q_hi in ((0.85, 0.95), (0.90, 0.97)):
        raw_hi = np.isfinite(rank) & (rank >= q_hi)
        raw_lo = np.isfinite(rank) & (rank >= q_lo) & (rank < q_hi)
        over = np.r_[False, (raw_hi | raw_lo)[:-1]]
        hi = np.r_[False, raw_hi[:-1]]
        lo = np.r_[False, raw_lo[:-1]]
        w = w_win.copy()
        fb_hi = (hi & opened)[day_of_bar]
        fb_lo = (lo & opened)[day_of_bar]
        w[fb_hi, 0] = 0.0; w[fb_hi, 1] = 0.0; w[fb_hi, 2] = 1.0
        w[fb_lo, 0] = 1.0; w[fb_lo, 1] = 0.0; w[fb_lo, 2] = 0.0
        print(f"\ngrad BIL>={q_hi} QQQ>={q_lo}: hi {int((hi&opened).sum())} lo {int((lo&opened).sum())}")
        for lab, st in (("10y", "2017-01-03"), ("5y", "2021-10-25")):
            for slip in (1.0, 5.0, 10.0):
                r = bt.run(ts, o, c, w, st, band=0.02, slippage_bps=slip)
                s = bt.stats(r, BARS)
                print(f"  {lab} {slip:2.0f}bp: {s['cagr']*100:5.2f}/{s['max_drawdown']*100:5.2f}/"
                      f"{s['sharpe']:.2f} fills {s['fills']}")


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    main()
