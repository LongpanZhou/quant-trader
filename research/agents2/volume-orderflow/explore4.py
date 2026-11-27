"""Step 4: causal versions only.  (a) 15:00 state -> last hour,
(b) capitulation-bar reversal, (c) close volume spike -> overnight."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import vlib  # noqa: E402
from explore1 import day_matrices, cum_features, rolling_rvol  # noqa: E402
from explore2 import last_valid, at_time  # noqa: E402

pd.set_option("display.width", 200)


def main():
    ts, op, cl, hi, lo, vo = vlib.build_panel()
    dates, first, last, _ = vlib.session_index(ts)
    Q = day_matrices(ts, op, cl, hi, lo, vo, k=0)[3]
    T = day_matrices(ts, op, cl, hi, lo, vo, k=1)[3]
    cvQ, FQ, devQ, _ = cum_features(Q)
    cvT, FT, devT, _ = cum_features(T)
    rvolQ = rolling_rvol(Q)
    tc, to = last_valid(T["c"]), T["o"][:, 0]
    qc, qo = last_valid(Q["c"]), Q["o"][:, 0]
    nd = len(qc)
    sma = pd.Series(qc).rolling(165).mean().to_numpy()
    reg = np.zeros(nd, bool)
    reg[1:] = qc[:-1] > sma[:-1]
    t_ov = np.r_[np.nan, to[1:] / tc[:-1] - 1]

    # ---- (a) causal: state at 15:00 -> 15:00..close
    c1500Q, c1500T = at_time(Q["c"], 299), at_time(T["c"], 299)
    lastQ, lastT = qc, tc
    t_last60 = lastT / c1500T - 1
    q_last60 = lastQ / c1500Q - 1
    r_upto_1500 = c1500T / to - 1

    def buck(x, y, label, q=5, sub=None):
        m = np.isfinite(x) & np.isfinite(y)
        if sub is not None:
            m &= sub
        x, y = x[m], y[m]
        if len(x) < 40:
            print(f"  {label}: n={len(x)} too few")
            return
        e = np.quantile(x, np.linspace(0, 1, q + 1)[1:-1])
        idx = np.searchsorted(e, x)
        print(f"  {label}: n={len(x)} r={np.corrcoef(x, y)[0,1]:+.3f}")
        print("     " + " | ".join(
            f"q{b} {y[idx==b].mean()*1e4:+6.1f}/{np.median(y[idx==b])*1e4:+6.1f}bp "
            f"w{100*(y[idx==b]>0).mean():4.1f}%" for b in range(q)))

    def cells(conds, y, labels):
        print(f"  {' / '.join(labels):38s}")
        for lab, c in conds:
            yy = y[np.isfinite(y) & c]
            if len(yy) == 0:
                print(f"    {lab:34s} n=0")
                continue
            print(f"    {lab:34s} n={len(yy):4d} mean {yy.mean()*1e4:+7.1f}bp "
                  f"med {np.median(yy)*1e4:+6.1f}bp win {100*(yy>0).mean():4.1f}% "
                  f"p05 {np.quantile(yy,0.05)*1e4:+7.0f}")

    print("== (a) causal state at 15:00 -> TQQQ 15:00-close (risk-on)")
    buck(r_upto_1500, t_last60, "ret_to_15:00", sub=reg)
    buck(at_time(FQ, 299), t_last60, "flow@15:00", sub=reg)
    buck(at_time(rvolQ, 299), t_last60, "rvol@15:00", sub=reg)

    print("\n== (a2) down >2% by 15:00: split by flow@15:00")
    dn = reg & (r_upto_1500 < -0.02)
    print(f"  n down={dn.sum()}  mean last60 {t_last60[dn].mean()*1e4:+.1f}bp "
          f"med {np.median(t_last60[dn])*1e4:+.1f}bp win {100*(t_last60[dn]>0).mean():.1f}%")
    buck(at_time(FQ, 299), t_last60, "flow@15:00|down2%", sub=dn)
    buck(at_time(devT, 299), t_last60, "tqqq vwapdev@15:00|down2%", sub=dn)

    print("\n== (b) capitulation bars: QQQ 1m ret < -0.5% and bar rvol > 10")
    qr = np.full_like(Q["c"], np.nan)
    qr[:, 1:] = Q["c"][:, 1:] / Q["c"][:, :-1] - 1
    fwd30 = np.full_like(T["c"], np.nan)
    fwd30[:, :-30] = T["c"][:, 30:] / T["c"][:, :-30] - 1
    rv1 = rolling_rvol(Q)
    cond = reg[:, None] & (qr < -0.005) & (rv1 > 10) & (np.arange(390) < 350)[None, :]
    print(f"  n events {int(np.nansum(cond))}")
    cells([("all", cond)], fwd30, ["next 30m"])
    print("\n   by VWAP position at the bar:")
    below = cond & (devQ < -0.004)
    above = cond & (devQ >= -0.004)
    cells([("below vwap", below), ("at/above vwap", above)], fwd30, ["next 30m"])
    print("\n   by TQQQ 1m return bucket:")
    for lo_, hi_ in ((-0.02, -0.01), (-0.01, -0.005), (-0.005, 0.0)):
        c = cond & (T["c"] / np.r_[np.nan, T["c"][:, :-1]] - 1 > lo_) & \
            (T["c"] / np.r_[np.nan, T["c"][:, :-1]] - 1 <= hi_)
        cells([(f"TQQQ {lo_*100:.1f}..{hi_*100:.1f}%", c)], fwd30, ["next 30m"])

    print("\n== (c) close-window volume share -> overnight")
    tot = np.nan_to_num(Q["v"]).sum(1)
    last30 = np.nansum(Q["v"][:, 330:], axis=1)
    share = last30 / np.maximum(tot, 1)
    buck(share, t_ov, "last30 vol share", sub=reg)
    last10 = np.nansum(Q["v"][:, 350:], axis=1)
    buck(last10 / np.maximum(tot, 1), t_ov, "last10 vol share", sub=reg)


if __name__ == "__main__":
    main()
