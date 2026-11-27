"""Vectorised volume-armed stop variants (fast grid search)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine  # noqa: E402


def winner_vol(D, stop=0.04, ma_n=20, buf=0.01, quiet=0.8, hi=1.6, sticky=False,
               no_ma=False, stop_hi=None):
    """4% intraday stop armed by participation, fully vectorised per session.

    armed_i = (a_ma or rv_i > hi) and rv_i > quiet, with rv_i the causal
    same-time-of-day cumulative relative volume at bar i.
    """
    ma = pd.Series(D.qc).rolling(ma_n).mean().to_numpy()
    mprev = np.r_[np.nan, ma[:-1]]
    w = np.zeros((D.n, 3))
    hold = np.ones(D.n, bool)
    hold[~D.reg_bar] = False
    nev = 0
    for d in range(D.nd):
        if not D.reg[d]:
            continue
        f, l = int(D.first[d]), int(D.last[d])
        m = l - f + 1
        a_ma = bool(np.isfinite(mprev[d]) and D.qc_m[d, 0] < mprev[d] * (1 + buf))
        if no_ma:
            a_ma = False
        rv = D.rvol_cum_q[d, :m]
        c = D.cl[f:l + 1, 1]
        base = D.to[d]
        ok = np.isfinite(rv)
        with np.errstate(invalid="ignore"):
            vol_ok = ok & (rv > quiet)
            if sticky:
                latch = np.maximum.accumulate(np.where(ok & (rv > hi), 1.0, 0.0)) > 0
                latch = latch | a_ma
                armed = latch & vol_ok
            else:
                armed = ((a_ma | (ok & (rv > hi))) & vol_ok)
        if stop_hi is not None:
            thr = np.where(ok & (rv > hi), 1 - stop_hi, 1 - stop)
        else:
            thr = np.full(m, 1 - stop)
        hit = armed & (c < base * thr)
        if hit.any():
            j = int(np.argmax(hit))
            hold[f + j: l + 1] = False
            nev += 1
    w[:, 1] = hold.astype(float)
    w[:, 2] = 1 - w[:, 1]
    return w, nev


def main():
    D = engine.Data()
    base, n0 = engine.winner_weights(D)
    b = engine.evaluate(D, base, f"winner ({n0})")
    W = {k: (v["cagr"], v["max_drawdown"]) for k, v in b.items()}
    print("\nhi    quiet  stop  10y CAGR/DD (d)       5y CAGR/DD (d)      stops")
    for hi in (1.2, 1.3, 1.4, 1.5, 1.6, 1.8):
        for quiet in (0.0, 0.7, 0.8, 0.9):
            w, n = winner_vol(D, hi=hi, quiet=quiet)
            r = engine.evaluate(D, w)
            print(f"{hi:<4} {quiet:<5} 0.04  "
                  f"{r['10y']['cagr']*100:5.2f}/{r['10y']['max_drawdown']*100:5.2f} "
                  f"({(r['10y']['cagr']-W['10y'][0])*100:+5.2f},"
                  f"{(r['10y']['max_drawdown']-W['10y'][1])*100:+5.2f})  "
                  f"{r['5y']['cagr']*100:5.2f}/{r['5y']['max_drawdown']*100:5.2f} "
                  f"({(r['5y']['cagr']-W['5y'][0])*100:+5.2f},"
                  f"{(r['5y']['max_drawdown']-W['5y'][1])*100:+5.2f})  {n}")


if __name__ == "__main__":
    main()
