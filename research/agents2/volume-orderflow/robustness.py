"""Step 20: robustness surface for the final rule + 5-minute negative tests."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine  # noqa: E402
from strategy import build_weights  # noqa: E402

pd.set_option("display.width", 240)


def main():
    D = engine.Data()
    base, _ = engine.winner_weights(D)
    b = engine.evaluate(D, base, "winner")
    W = {k: (v["cagr"], v["max_drawdown"]) for k, v in b.items()}

    def show(lab, **kw):
        w, ev = build_weights(D, **kw)
        r = engine.evaluate(D, w)
        print(f"  {lab:34s} 10y {r['10y']['cagr']*100:5.2f}/"
              f"{r['10y']['max_drawdown']*100:5.2f} "
              f"({(r['10y']['cagr']-W['10y'][0])*100:+5.2f},"
              f"{(r['10y']['max_drawdown']-W['10y'][1])*100:+5.2f}) | 5y "
              f"{r['5y']['cagr']*100:5.2f}/{r['5y']['max_drawdown']*100:5.2f} "
              f"({(r['5y']['cagr']-W['5y'][0])*100:+5.2f},"
              f"{(r['5y']['max_drawdown']-W['5y'][1])*100:+5.2f}) | {len(ev)}")

    print("\n== final rule: 4% stop, MA20 arm, rvol>1.5 re-arm, rvol>1.0 floor")
    show("FINAL")
    print("\n-- rvol floor (hi=1.5)")
    for f in (0.90, 0.95, 1.00, 1.05, 1.10):
        show(f"floor {f}", floor=f)
    print("\n-- high-volume re-arm threshold (floor=1.0)")
    for h in (1.2, 1.3, 1.4, 1.5, 1.6, 1.8, 2.0):
        show(f"hi {h}", hi=h)
    print("\n-- stop distance")
    for s in (0.030, 0.035, 0.040, 0.045, 0.050):
        show(f"stop {s}", stop=s)
    print("\n-- arming MA")
    for n in (10, 15, 20, 30, 50):
        show(f"MA{n}", ma_n=n)
    print("\n-- arm buffer")
    for bf in (0.0, 0.005, 0.01, 0.02, 0.03):
        show(f"buf {bf}", buf=bf)

    # ---------- 5-minute negative tests
    print("\n== 5-minute tests (QQQ flow -> TQQQ next 30m, risk-on, 10:00-15:00)")
    b5 = 5
    n5 = 390 // b5
    Qc = D._mat(D.cl[:, 0])[:, :390].reshape(D.nd, n5, b5)
    Qv = D._mat(D.vo[:, 0])[:, :390].reshape(D.nd, n5, b5)
    Tc = D._mat(D.cl[:, 1])[:, :390].reshape(D.nd, n5, b5)
    Qc5 = Qc[:, :, -1]
    Qv5 = np.nansum(Qv, axis=2)
    Tclose5 = Tc[:, :, -1]
    # flow within 5m bar: (close - low)/(high - low) proxy using bar close vs open
    Qo5 = Qc[:, :, 0]
    clv5 = np.sign(Qc5 - Qo5)
    cv5 = np.cumsum(np.nan_to_num(Qv5), axis=1)
    csv5 = np.cumsum(np.nan_to_num(Qv5) * clv5, axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        F5 = np.where(cv5 > 0, csv5 / cv5, np.nan)
    typ5 = (Qc5 + Qo5) / 2
    cpv5 = np.cumsum(np.nan_to_num(typ5) * np.nan_to_num(Qv5), axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        vwap5 = np.where(cv5 > 0, cpv5 / cv5, np.nan)
        dev5 = Qc5 / vwap5 - 1
    rvol5 = cv5 / pd.DataFrame(cv5).rolling(20, min_periods=10).mean().shift(1).to_numpy()
    fwd = np.full_like(Tclose5, np.nan)
    fwd[:, :-6] = Tclose5[:, 6:] / Tclose5[:, :-6] - 1
    ret5 = Qc5 / np.r_[np.nan, Qc5[:, :-1]] - 1 if False else None

    ok = D.reg[:, None] & (np.arange(n5) >= 6)[None, :] & (np.arange(n5) <= 66)[None, :]
    for name, x in (("5m cum flow F", F5), ("5m VWAP dev", dev5), ("5m cum RVOL", rvol5)):
        xx, yy = x[ok], fwd[ok]
        m = np.isfinite(xx) & np.isfinite(yy)
        print(f"  {name:16s} n={m.sum():7,d} corr={np.corrcoef(xx[m], yy[m])[0,1]:+.4f}")

    # volume-confirmed 5m momentum: sign of last 5m return x rvol bucket
    r5 = np.full_like(Qc5, np.nan)
    r5[:, 1:] = Qc5[:, 1:] / Qc5[:, :-1] - 1
    print("  5m momentum x rvol (mean next-30m TQQQ bp):")
    for lo, hi in ((0, 0.8), (0.8, 1.2), (1.2, 2.0), (2.0, 99)):
        for sgn, lab in ((1, "up"), (-1, "dn")):
            m = ok & np.isfinite(r5) & (rvol5 >= lo) & (rvol5 < hi) & (np.sign(r5) == sgn)
            y = fwd[m]
            y = y[np.isfinite(y)]
            print(f"    rvol {lo}-{hi} {lab}: n={len(y):7,d} mean {y.mean()*1e4:+6.2f}bp "
                  f"win {100*(y>0).mean():4.1f}%  (after 1bp+1bp cost = "
                  f"{(y.mean()-2e-4)*1e4:+6.2f}bp)")


if __name__ == "__main__":
    main()
