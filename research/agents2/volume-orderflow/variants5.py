"""Step 14: volume-conditioned arming of the 4% stop, and TQQQ/QQQ volume ratio."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine  # noqa: E402

pd.set_option("display.width", 220)


def winner_custom(D, stop=0.04, arm_buf=0.01, arm_extra=None, ma_n=20):
    ma = pd.Series(D.qc).rolling(ma_n).mean().to_numpy()
    prev = np.r_[np.nan, ma[:-1]]
    w = np.zeros((D.n, 3))
    hold = np.zeros(D.n, bool)
    nev = 0
    for d in range(D.nd):
        if not D.reg[d]:
            continue
        armed = bool(np.isfinite(prev[d]) and D.qc_m[d, 0] < prev[d] * (1 + arm_buf))
        if arm_extra is not None:
            armed = bool(arm_extra(d, armed))
        base = D.to[d]
        st = True
        for i in range(D.first[d], D.last[d] + 1):
            if armed and st and D.cl[i, 1] < base * (1 - stop):
                st = False
                nev += 1
            hold[i] = st
    w[:, 1] = hold.astype(float)
    w[:, 2] = 1 - w[:, 1]
    return w, nev


def main():
    D = engine.Data()
    base, _ = engine.winner_weights(D)
    engine.evaluate(D, base, "winner")
    rv30 = D.rvol_cum_q[:, 30]
    rv60 = D.rvol_cum_q[:, 60]

    print("\n-- OR: also arm when early volume is elevated")
    for k in (1.3, 1.5, 2.0):
        w, n = winner_custom(D, arm_extra=lambda d, a, k=k: a or (np.isfinite(rv60[d]) and rv60[d] > k))
        engine.evaluate(D, w, f"arm = QQQ<MA20*1.01 or rvol60>{k} ({n})")

    print("\n-- AND: require normal-to-high volume to arm")
    for k in (0.6, 0.8, 1.0):
        w, n = winner_custom(D, arm_extra=lambda d, a, k=k: a and (np.isfinite(rv60[d]) and rv60[d] > k))
        engine.evaluate(D, w, f"arm = QQQ<MA20*1.01 and rvol60>{k} ({n})")

    print("\n-- pure volume arming (ignore MA20)")
    for k in (1.2, 1.5, 2.0):
        w, n = winner_custom(D, arm_extra=lambda d, a, k=k: (np.isfinite(rv60[d]) and rv60[d] > k))
        engine.evaluate(D, w, f"arm = rvol60>{k} ({n})")

    # TQQQ/QQQ volume ratio, same-time-of-day normalised
    print("\n== TQQQ/QQQ volume ratio diagnostics")
    tvol = D._mat(D.vo[:, 1])
    ratio = np.log((tvol + 1) / (D.v_q + 1))
    c_ratio = np.nancumsum(np.where(np.isfinite(ratio), ratio, 0), axis=1)
    cnt = np.cumsum(np.isfinite(ratio), axis=1)
    r_sofar = c_ratio / np.maximum(cnt, 1)
    base_r = pd.DataFrame(r_sofar).rolling(20, min_periods=10).mean().shift(1).to_numpy()
    z = r_sofar - base_r
    for m, tag in ((30, "10:00"), (240, "13:30"), (359, "15:59")):
        x = z[:, m]
        sub = D.reg & np.isfinite(x)
        e = np.nanquantile(x[sub], [0, .2, .4, .6, .8, 1.0])
        b = pd.cut(x[sub], bins=np.unique(e), include_lowest=True)
        ov = D.fwd_open_return()[sub]
        intr = (D.tc / D.to - 1)[sub]
        g = pd.DataFrame({"b": b, "ov": ov * 100, "intr": intr * 100}).groupby(
            "b", observed=True).agg(n=("ov", "size"), ov=("ov", "mean"),
                                    med_ov=("ov", "median"), intr=("intr", "mean"))
        print(f"  z(tqqq/qqq vol) at {tag} (n={sub.sum()})")
        print(g.round(3).to_string())

    # day-level: is a high TQQQ/QQQ volume ratio a bad sign for the next day?
    zc = z[:, 359]
    for h, lab in ((1, "next day intraday"), (5, "next 5d")):
        y = np.full(D.nd, np.nan)
        y[:-h] = D.tc[h:] / D.tc[:-h] - 1
        sub = D.reg & np.isfinite(zc) & np.isfinite(y)
        e = np.nanquantile(zc[sub], [0, .2, .4, .6, .8, 1.0])
        b = pd.cut(zc[sub], bins=np.unique(e), include_lowest=True)
        g = pd.DataFrame({"b": b, "y": y[sub] * 100}).groupby("b", observed=True).agg(
            n=("y", "size"), mean=("y", "mean"), med=("y", "median"))
        print(f"  z at close -> {lab}: corr {np.corrcoef(zc[sub], y[sub])[0,1]:+.3f}")
        print(g.round(3).to_string())


if __name__ == "__main__":
    main()
