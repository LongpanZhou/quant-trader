"""Step 17: is the quiet-floor gain really volume, or just 'no early stops'?"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine  # noqa: E402
from arming_grid import winner_vol  # noqa: E402


def winner_t0(D, stop=0.04, ma_n=20, buf=0.01, t0=0):
    """Round-1 winner but the stop is only active from minute t0 onward."""
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
        if not a_ma:
            continue
        c = D.cl[f:l + 1, 1]
        hit = np.zeros(m, bool)
        hit[t0:] = c[t0:] < D.to[d] * (1 - stop)
        if hit.any():
            j = int(np.argmax(hit))
            hold[f + j: l + 1] = False
            nev += 1
    w[:, 1] = hold.astype(float)
    w[:, 2] = 1 - w[:, 1]
    return w, nev


def main():
    D = engine.Data()
    base, _ = engine.winner_weights(D)
    b = engine.evaluate(D, base, "winner")
    W = {k: (v["cagr"], v["max_drawdown"]) for k, v in b.items()}

    print("\n-- winner, stop only active after minute t0 (t0=0 is the winner)")
    for t0 in (0, 5, 10, 15, 20, 30, 45, 60):
        w, n = winner_t0(D, t0=t0)
        r = engine.evaluate(D, w)
        print(f"  t0={t0:3d}: 10y {r['10y']['cagr']*100:5.2f}/"
              f"{r['10y']['max_drawdown']*100:5.2f} | 5y "
              f"{r['5y']['cagr']*100:5.2f}/{r['5y']['max_drawdown']*100:5.2f} | {n}")

    print("\n-- fine quiet floor (hi=1.5)")
    for q in (0.80, 0.85, 0.88, 0.90, 0.92, 0.95, 1.00):
        w, n = winner_vol(D, hi=1.5, quiet=q)
        r = engine.evaluate(D, w)
        print(f"  quiet={q:<5}: 10y {r['10y']['cagr']*100:5.2f}/"
              f"{r['10y']['max_drawdown']*100:5.2f} | 5y "
              f"{r['5y']['cagr']*100:5.2f}/{r['5y']['max_drawdown']*100:5.2f} | {n}")

    print("\n-- stop level x quiet (hi=1.5)")
    for stop in (0.030, 0.035, 0.040, 0.045, 0.050):
        for q in (0.8, 0.9):
            w, n = winner_vol(D, stop=stop, hi=1.5, quiet=q)
            r = engine.evaluate(D, w)
            print(f"  stop={stop:.3f} quiet={q}: 10y "
                  f"{r['10y']['cagr']*100:5.2f}/{r['10y']['max_drawdown']*100:5.2f} | 5y "
                  f"{r['5y']['cagr']*100:5.2f}/{r['5y']['max_drawdown']*100:5.2f} | {n}")


if __name__ == "__main__":
    main()
