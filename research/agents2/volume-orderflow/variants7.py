"""Step 16: causal per-bar volume-armed 4% stop (fixes the 10:30 look-ahead)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine  # noqa: E402


def winner_vol(D, stop=0.04, ma_n=20, buf=0.01, quiet=0.8, hi=1.6, sticky=False,
               no_ma=False):
    """4% intraday stop, armed by participation.

    At bar i (all inputs known at the close of bar i):
      a_ma  = QQQ 09:30 price < MA20(prev) * (1+buf)      [round-1 gate]
      rv    = cumulative QQQ volume / 20-day same-time-of-day mean
      armed = (a_ma or rv > hi) and rv > quiet
    """
    ma = pd.Series(D.qc).rolling(ma_n).mean().to_numpy()
    mprev = np.r_[np.nan, ma[:-1]]
    w = np.zeros((D.n, 3))
    hold = np.zeros(D.n, bool)
    nev = 0
    for d in range(D.nd):
        if not D.reg[d]:
            continue
        a_ma = bool(np.isfinite(mprev[d]) and D.qc_m[d, 0] < mprev[d] * (1 + buf))
        if no_ma:
            a_ma = False
        base = D.to[d]
        st = True
        latched = a_ma
        for i in range(D.first[d], D.last[d] + 1):
            rv = D.rvol_cum_q[d, min(int(D.tod[i]), 389)]
            vol_ok = bool(np.isfinite(rv) and rv > quiet)
            vol_hi = bool(np.isfinite(rv) and rv > hi)
            if sticky:
                latched = latched or vol_hi
                armed = (latched and vol_ok)
            else:
                armed = ((a_ma or vol_hi) and vol_ok)
            if armed and st and D.cl[i, 1] < base * (1 - stop):
                st = False
                nev += 1
            hold[i] = st
    w[:, 1] = hold.astype(float)
    w[:, 2] = 1 - w[:, 1]
    return w, nev


def main():
    D = engine.Data()
    base, n0 = engine.winner_weights(D)
    b = engine.evaluate(D, base, f"winner ({n0} stops)")
    W = {k: (v["cagr"], v["max_drawdown"]) for k, v in b.items()}

    print("\n-- per-bar, non-sticky: (MA20 or rvol>hi) and rvol>quiet")
    for hi in (1.2, 1.4, 1.6, 2.0, 99):
        for q in (0.0, 0.8):
            w, n = winner_vol(D, hi=hi, quiet=q)
            r = engine.evaluate(D, w)
            print(f"  hi>{hi:<4} quiet>{q:<3}: "
                  f"{r['10y']['cagr']*100:5.2f}/{r['10y']['max_drawdown']*100:5.2f} "
                  f"({(r['10y']['cagr']-W['10y'][0])*100:+5.2f},"
                  f"{(r['10y']['max_drawdown']-W['10y'][1])*100:+5.2f}) | "
                  f"{r['5y']['cagr']*100:5.2f}/{r['5y']['max_drawdown']*100:5.2f} "
                  f"({(r['5y']['cagr']-W['5y'][0])*100:+5.2f},"
                  f"{(r['5y']['max_drawdown']-W['5y'][1])*100:+5.2f}) | {n}")

    print("\n-- sticky arm")
    for hi in (1.2, 1.6, 2.0):
        w, n = winner_vol(D, hi=hi, quiet=0.8, sticky=True)
        r = engine.evaluate(D, w)
        print(f"  hi>{hi:<4} sticky: {r['10y']['cagr']*100:5.2f}/"
              f"{r['10y']['max_drawdown']*100:5.2f} | "
              f"{r['5y']['cagr']*100:5.2f}/{r['5y']['max_drawdown']*100:5.2f} | {n}")

    print("\n-- pure volume arming (no MA20)")
    for hi in (1.0, 1.2, 1.4):
        w, n = winner_vol(D, hi=hi, quiet=0.8, no_ma=True)
        r = engine.evaluate(D, w)
        print(f"  noMA hi>{hi:<4}: {r['10y']['cagr']*100:5.2f}/"
              f"{r['10y']['max_drawdown']*100:5.2f} | "
              f"{r['5y']['cagr']*100:5.2f}/{r['5y']['max_drawdown']*100:5.2f} | {n}")


if __name__ == "__main__":
    main()
