"""Variant sweep 2: froth throttle applied on top of the winner's stop."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bt_lib as L  # noqa: E402


def main():
    ts, opens, closes = L.load_panel()
    d = L.add_ratio_features(L.daily_frame(ts, opens, closes))
    dates, first, last = L.day_bounds(ts)
    nd = len(first)
    hold, risk_on, _, _ = L.winner_state(ts, opens, closes)

    def run(label, tgt, slip=1.0, start=L.START10):
        w = L.weights_from_daily(ts, tgt, first, last, stopped=~hold)
        s = L.metrics(ts, opens, closes, w, slip=slip, start=start)
        L.show(label, s)
        return s

    base = np.zeros((nd, 3))
    base[risk_on, 1] = 1
    base[~risk_on, 2] = 1
    print("baseline check")
    run("winner (with stop mask)", base)
    run("winner 5y", base, start=L.START5)

    print("\n-- ext200 froth -> QQQ, on top of winner stop")
    for n_ in (120, 200, 250):
        ext = d[f"ext{n_}"].shift(1).to_numpy()
        for theta in (0.15, 0.18, 0.20, 0.22, 0.25, 0.28):
            froth = np.nan_to_num(ext, nan=-9) > theta
            tgt = np.zeros((nd, 3))
            tgt[risk_on & ~froth, 1] = 1
            tgt[risk_on & froth, 0] = 1
            tgt[~risk_on, 2] = 1
            run(f"ext{n_}>{theta:.2f} -> QQQ ({froth.mean()*100:4.1f}%)", tgt)
            run("   5y", tgt, start=L.START5)

    print("\n-- ext200 froth -> half TQQQ / half QQQ")
    ext = d["ext200"].shift(1).to_numpy()
    for theta in (0.15, 0.18, 0.20, 0.22, 0.25):
        froth = np.nan_to_num(ext, nan=-9) > theta
        tgt = np.zeros((nd, 3))
        tgt[risk_on & ~froth, 1] = 1
        tgt[risk_on & froth, 1] = 0.5
        tgt[risk_on & froth, 0] = 0.5
        tgt[~risk_on, 2] = 1
        run(f"ext200>{theta:.2f} -> 50/50 ({froth.mean()*100:4.1f}%)", tgt)
        run("   5y", tgt, start=L.START5)

    print("\n-- ext200 froth -> BIL")
    for theta in (0.20, 0.22, 0.25, 0.28):
        froth = np.nan_to_num(ext, nan=-9) > theta
        tgt = np.zeros((nd, 3))
        tgt[risk_on & ~froth, 1] = 1
        tgt[~risk_on | froth, 2] = 1
        run(f"ext200>{theta:.2f} -> BIL ({froth.mean()*100:4.1f}%)", tgt)
        run("   5y", tgt, start=L.START5)


if __name__ == "__main__":
    main()
