"""Step 13: volume-confirmed regime exits and distribution-day counting."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine  # noqa: E402


def state_machine(enter, exit_, init=False):
    """Daily state from enter/exit conditions evaluated at the prior close."""
    n = len(enter)
    st = np.zeros(n, bool)
    cur = init
    for d in range(n):
        st[d] = cur
        if cur and exit_[d]:
            cur = False
        elif (not cur) and enter[d]:
            cur = True
    return st


def weights_from_reg(D, reg):
    w = np.zeros((D.n, 3))
    w[:, 1] = reg[D.day_id]
    w[:, 2] = 1 - w[:, 1]
    return w


def dist_days(D, look=25, thr=-0.002):
    r = np.r_[np.nan, D.qc[1:] / D.qc[:-1] - 1]
    v = D.qv_day
    up_vol = v > np.r_[np.nan, v[:-1]]
    flag = (r < thr) & up_vol
    f = pd.Series(flag.astype(float))
    return f.rolling(look, min_periods=look).sum().to_numpy()


def main():
    D = engine.Data()
    sma = pd.Series(D.qc).rolling(165).mean().to_numpy()
    qc = D.qc
    reg0 = np.zeros(D.nd, bool)
    reg0[1:] = qc[:-1] > sma[:-1]
    engine.evaluate(D, weights_from_reg(D, reg0), "SMA165 base (no stop)")

    print("\n-- volume-confirmed exit: leave risk-on only on a high-volume break")
    for k in (0.9, 1.1, 1.3, 1.6):
        ex = (qc < sma) & (D.rvol_day > k)
        en = qc > sma
        # shift: signals at close d are usable for session d+1
        st = state_machine(np.r_[False, en[:-1]], np.r_[False, ex[:-1]], init=False)
        engine.evaluate(D, weights_from_reg(D, st), f"exit if close<SMA & rvol>{k}")

    print("\n-- volume-confirmed exit OR 2% below SMA (belt and braces)")
    for k in (1.1, 1.3):
        ex = ((qc < sma) & (D.rvol_day > k)) | (qc < sma * 0.98)
        en = qc > sma
        st = state_machine(np.r_[False, en[:-1]], np.r_[False, ex[:-1]])
        engine.evaluate(D, weights_from_reg(D, st), f"rvol>{k} or -2%")

    print("\n-- distribution-day count (IBD style) on top of SMA165")
    for look in (20, 25, 30):
        dd = dist_days(D, look=look)
        for thr in (4, 5, 6):
            ok = np.isfinite(dd) & (dd < thr)
            st = reg0 & np.r_[True, ok[:-1]]
            engine.evaluate(D, weights_from_reg(D, st),
                            f"dd{look}<{thr} (off {100*(1-st.mean()):.0f}%)")

    print("\n-- distribution days alone as the regime")
    for look, thr in ((25, 5), (25, 4), (20, 4)):
        dd = dist_days(D, look=look)
        ok = np.isfinite(dd) & (dd < thr) & (qc > sma)
        st = np.r_[False, ok[:-1]]
        engine.evaluate(D, weights_from_reg(D, st), f"dd{look}<{thr} & SMA")

    print("\n-- same but with the winner's 4% stop overlay")
    base_w, _ = engine.winner_weights(D)
    for look, thr in ((25, 5), (25, 4)):
        dd = dist_days(D, look=look)
        ok = np.isfinite(dd) & (dd < thr)
        mask = np.r_[True, ok[:-1]]
        w = base_w.copy()
        off = ~mask[D.day_id]
        w[off, 1] = 0.0
        w[off, 2] = 1.0
        engine.evaluate(D, w, f"winner x dd{look}<{thr}")


if __name__ == "__main__":
    main()
