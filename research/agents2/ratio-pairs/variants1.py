"""Variant sweep 1: literal ratio rules and the froth throttle."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bt_lib as L  # noqa: E402


def main():
    ts, opens, closes = L.load_panel()
    d = L.add_ratio_features(L.daily_frame(ts, opens, closes))
    dates, first, last = L.day_bounds(ts)
    nd = len(first)
    hold, risk_on, _, _ = L.winner_state(ts, opens, closes)
    print(f"bars {len(ts)}  days {nd}  risk_on {risk_on.mean():.3f}  "
          f"tqqq_hold {hold.mean():.3f}")

    allday = np.ones((nd, 3))
    # date of each session (daily frame is last-bar timestamps, same length)
    idx = d.index
    ext200 = d["ext200"].shift(1).to_numpy()  # known at prior close
    ext60 = d["ext60"].shift(1).to_numpy()
    ext20 = d["ext20"].shift(1).to_numpy()
    dds = d["dd252"].shift(1).to_numpy()
    rma20 = (d["ratio"] / d["ratio"].rolling(20).mean()).shift(1).to_numpy()
    rma60 = (d["ratio"] / d["ratio"].rolling(60).mean()).shift(1).to_numpy()

    w_base = L.weights_from_daily(ts, np.where(risk_on[:, None], [[0, 1, 0]], [[0, 0, 1]]), first, last)
    s = L.metrics(ts, opens, closes, w_base)
    L.show("winner (165d regime + 4% stop)", s)
    for start in (L.START5,):
        L.show("  winner 5y", L.metrics(ts, opens, closes, w_base, start=start))

    print("\n-- literal idea (a): ratio vs its own MA, no QQQ regime")
    for n_, sig in ((20, rma20), (60, rma60)):
        for other, oi in (("QQQ", 0), ("BIL", 2)):
            on = np.nan_to_num(sig, nan=0.0) > 1.0
            tgt = np.zeros((nd, 3))
            tgt[:, 1] = on
            tgt[:, oi] = 1 - on
            w = L.weights_from_daily(ts, tgt, first, last)
            L.show(f"ratio>MA{n_} -> TQQQ else {other}", L.metrics(ts, opens, closes, w))

    print("\n-- ratio filter on the 165d regime (no stop)")
    for n_, sig in ((20, rma20), (60, rma60)):
        on = risk_on & (np.nan_to_num(sig, nan=0.0) > 1.0)
        tgt = np.zeros((nd, 3))
        tgt[:, 1] = on
        tgt[:, 2] = 1 - on
        w = L.weights_from_daily(ts, tgt, first, last)
        L.show(f"regime & ratio>MA{n_}", L.metrics(ts, opens, closes, w))

    print("\n-- froth throttle on the winner: ext200 > theta -> QQQ")
    for theta in (0.15, 0.18, 0.20, 0.22, 0.24, 0.26, 0.30):
        froth = np.nan_to_num(ext200, nan=-9) > theta
        tgt = np.zeros((nd, 3))
        tgt[risk_on, 1] = 1
        tgt[risk_on & froth, 1] = 0
        tgt[risk_on & froth, 0] = 1
        tgt[~risk_on, 2] = 1
        w = L.weights_from_daily(ts, tgt, first, last)
        s = L.metrics(ts, opens, closes, w)
        L.show(f"ext200>{theta:.2f} -> QQQ  ({froth.mean()*100:4.1f}% days)", s)
        s5 = L.metrics(ts, opens, closes, w, start=L.START5)
        L.show("   5y", s5)


if __name__ == "__main__":
    main()
