"""Overnight-only crash hedge: decide at 15:50, sell TQQQ into the close,
re-enter at 09:31 next session.  Base = the winner."""
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


def build_overnight(ts, o, c, thr=-0.015, q=0.90, mode="bil"):
    w_win, opened, stopped, last, first = winner_daily(ts, o, c)
    dates = np.array([t.date() for t in ts])
    times = ts.time
    dts = pd.DatetimeIndex([pd.Timestamp(x) for x in dates[last]])
    f = pd.read_pickle(Path(__file__).parent / "features1550.pkl")
    f.index = pd.to_datetime(f.index)
    f = f.reindex(dts).ffill()
    # label: TQQQ 15:50 close -> next 09:31 open
    tqo = pd.Series(o[:, 1], index=ts)
    tc = pd.Series(c[:, 1], index=ts)
    lab = np.full(len(dts), np.nan)
    for k, dt in enumerate(dates[last]):
        if k + 1 >= len(dts):
            continue
        nxt = dates[first[k + 1]]
        idx = np.flatnonzero(dates == nxt)
        i931 = idx[times[idx] >= pd.Timestamp("09:31").time()][0]
        lab[k] = np.log(tqo.iloc[i931] / tc.iloc[last[k]])
    y = (lab < thr).astype(float)
    y[~np.isfinite(lab)] = np.nan
    x = f.to_numpy()
    p = walk_forward(dts, x, y, 1)
    rank = pd.Series(p).rolling(252, min_periods=60).rank(pct=True).to_numpy()

    w = w_win.copy()
    flag = np.isfinite(rank) & (rank >= q)
    n_flag = 0
    for k in range(len(dts) - 1):
        if not flag[k] or not opened[k]:
            continue
        n_flag += 1
        idx = np.flatnonzero(dates == dates[last[k]])
        cut = idx[times[idx] >= pd.Timestamp("15:50").time()]
        if mode == "bil":
            w[cut, 1] = 0.0
            w[cut, 2] = 1.0
        elif mode == "qqq":
            w[cut, 1] = 0.0
            w[cut, 0] = 1.0
            w[cut, 2] = 0.0
        # re-enter at the 09:30 bar of the next session: inherit the base state
        i930 = first[k + 1]
        w[i930] = w_win[i930]
    return w, flag, n_flag, dts, f, p, rank, y, lab


def main():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1min")
    for thr, q in ((-0.015, 0.85), (-0.015, 0.90), (-0.015, 0.95),
                   (-0.010, 0.90), (-0.020, 0.90)):
        for mode in ("bil", "qqq"):
            w, flag, n_flag, dts, f, p, rank, y, lab = build_overnight(ts, o, c, thr, q, mode)
            print(f"\nthr {thr} q{q} {mode}: flags {n_flag}")
            for lab_, st in (("10y", "2017-01-03"), ("5y", "2021-10-25")):
                for slip in (1.0, 5.0):
                    r = bt.run(ts, o, c, w, st, band=0.02, slippage_bps=slip)
                    s = bt.stats(r, BARS)
                    print(f"  {lab_} {slip:2.0f}bp: {s['cagr']*100:5.2f}/{s['max_drawdown']*100:5.2f}/"
                          f"{s['sharpe']:.2f} fills {s['fills']}")


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    main()
