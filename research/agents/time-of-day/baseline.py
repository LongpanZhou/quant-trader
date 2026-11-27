"""Reproduce the README daily baseline and attribute the differences."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import strategy as S  # noqa: E402

import bt  # noqa: E402


def daily_weights(cl, lo, hi, n=165, lag=0, band=0.0):
    dcl = pd.Series(cl[:, 0], index=lo)
    sma = dcl.rolling(n).mean().shift(1)
    px = dcl if lag == 0 else dcl.shift(1)
    up = (px > sma * (1 + band)).to_numpy()
    dn = (px < sma * (1 - band)).to_numpy()
    on = np.zeros(len(dcl), bool)
    cur = False
    for i in range(len(dcl)):
        if up[i]:
            cur = True
        elif dn[i]:
            cur = False
        on[i] = cur
    w = np.zeros((len(dcl), 3))
    w[:, 1] = np.where(on, 1.0, 0.0)
    w[:, 2] = np.where(on, 0.0, 1.0)
    return w


def main():
    ts, op, cl = bt.panel(("QQQ", "TQQQ", "BIL"), "2017-01-03", "2026-10-23", "1D")
    print(f"daily bars {len(ts)}")
    for lag in (0, 1):
        for band in (0.0, 0.02):
            w = daily_weights(cl, ts, 165, lag=lag, band=band)
            out = S.run_all(w, ts, op, cl, 1.0)
            print(f"  daily lag{lag} band{band:.2f}: 10y "
                  f"{out['10y']['stats']['cagr']*100:6.2f}%/"
                  f"{out['10y']['stats']['max_drawdown']*100:5.2f}% "
                  f"sh {out['10y']['stats']['sharpe']:4.2f} f{out['10y']['stats']['fills']:3d} | "
                  f"5y {out['5y']['stats']['cagr']*100:6.2f}%/"
                  f"{out['5y']['stats']['max_drawdown']*100:5.2f}% "
                  f"sh {out['5y']['stats']['sharpe']:4.2f}")

    # same regime but executed on 1m bars at 15:59 (one minute before the close)
    df = pd.DataFrame({"date": ts.date, "minute": ts.hour * 60 + ts.minute})
    print("\n(README reference: 45.31%/58.71% 10y, 34.61%/36.86% 5y)")


if __name__ == "__main__":
    main()
