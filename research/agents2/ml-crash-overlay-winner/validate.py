"""Validate a multi-horizon crash overlay on the exact 1-minute harness."""
from __future__ import annotations

import json
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
STARTS = {"10y": "2017-01-03", "5y": "2021-10-25"}
FEATS = ["rv1", "rv5", "rv20", "rv60", "rv_ratio", "rv_pct", "skew1", "skew20",
         "dvol", "dvol20", "vwap_dist", "dd_high", "first30", "last30", "close_loc",
         "gap", "gap20", "intraday", "up20", "dd20", "dd252", "sma20", "sma165",
         "rsi14", "decay5", "decay20", "bil5", "dow", "range", "range20",
         "vol_ratio", "vol_z20", "rv_x_trend", "skew_x_dd"]


def build(ts, o, c, horizon=20, crash_thr=-0.15, q=0.90, mode="bil"):
    w_win, opened, stopped, last, first = winner_daily(ts, o, c)
    dates = np.array([t.date() for t in ts])
    dts = pd.DatetimeIndex([pd.Timestamp(x) for x in dates[last]])
    day_of_bar = pd.Index(dates).map({d: k for k, d in enumerate(dts.date)}).to_numpy()
    f = pd.read_pickle(Path(__file__).parent / "features.pkl")
    f.index = pd.to_datetime(f.index)
    f = f.reindex(dts).ffill()
    x = f[FEATS].to_numpy()
    t = pd.Series(c[last, 1], index=dts)
    y = (t.shift(-horizon) / t - 1.0 < crash_thr).astype(float)
    y[~np.isfinite(t.shift(-horizon))] = np.nan
    p = walk_forward(dts, x, y, horizon)
    rank = pd.Series(p).rolling(252, min_periods=60).rank(pct=True).to_numpy()
    raw = np.isfinite(rank) & (rank >= q)
    flag = np.r_[False, raw[:-1]]
    w = w_win.copy()
    over = flag & opened
    fb = over[day_of_bar]
    if mode == "bil":
        w[fb, 1] = 0.0
        w[fb, 2] = 1.0
    elif mode == "qqq":
        w[fb, 1] = 0.0
        w[fb, 2] = 0.0
        w[fb, 0] = 1.0
    elif mode == "half":
        w[fb, 1] = 0.5
        w[fb, 2] = 0.5
    return w, flag, opened, dts, f, p, rank


def main():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1min")
    cfgs = [
        (20, -0.15, 0.90, "bil"),
        (20, -0.15, 0.80, "bil"),
        (10, -0.12, 0.90, "bil"),
        (5, -0.06, 0.90, "bil"),
    ]
    for horizon, thr, q, mode in cfgs:
        w, flag, opened, dts, f, p, rank = build(ts, o, c, horizon, thr, q, mode)
        print(f"\n=== h{horizon} thr{thr} q{q} {mode} ===")
        m = dts >= pd.Timestamp("2017-01-03")
        fl = flag & opened
        print(f"flag days {fl[m].sum()} / held {opened[m].sum()} = {fl[m].sum()/opened[m].sum()*100:.1f}%")
        yr = pd.Series(fl[m], index=dts[m]).groupby(dts[m].year).sum()
        print("flags/yr:", dict(yr))
        for lab, st in STARTS.items():
            r = bt.run(ts, o, c, w, st, band=0.02, slippage_bps=1.0)
            s = bt.stats(r, BARS)
            print(f"  {lab} 1bp: CAGR {s['cagr']*100:6.2f}% DD {s['max_drawdown']*100:5.2f}% "
                  f"Sharpe {s['sharpe']:4.2f} fills {s['fills']}")


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    main()
