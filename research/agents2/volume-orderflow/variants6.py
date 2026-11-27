"""Step 15: surface of the volume-conditioned arming rule for the 4% stop."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine  # noqa: E402


def run(D, stop, ma_n, rv, quiet, col=60):
    ma = pd.Series(D.qc).rolling(ma_n).mean().to_numpy()
    prev = np.r_[np.nan, ma[:-1]]
    rvq = D.rvol_cum_q[:, col]
    w = np.zeros((D.n, 3))
    hold = np.zeros(D.n, bool)
    nev = 0
    for d in range(D.nd):
        if not D.reg[d]:
            continue
        a_ma = bool(np.isfinite(prev[d]) and D.qc_m[d, 0] < prev[d] * 1.01)
        v = rvq[d]
        a_vol = bool(np.isfinite(v) and v > rv) if rv else False
        armed = a_ma or a_vol
        if quiet and np.isfinite(v) and v <= quiet:
            armed = False
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
    b = engine.evaluate(D, base, "winner baseline")
    W = {k: (v["cagr"], v["max_drawdown"]) for k, v in b.items()}

    print("\nrows: arm MA / rvol OR threshold / quiet floor -> 10y CAGR,DD | 5y CAGR,DD | stops")
    for ma_n in (10, 20, 30):
        for rv in (1.2, 1.4, 1.6, 2.0, 99):
            r = engine.evaluate(D, run(D, 0.04, ma_n, rv, None)[0])
            n = run(D, 0.04, ma_n, rv, None)[1]
            d10 = r["10y"]["cagr"] - W["10y"][0]
            d5 = r["5y"]["cagr"] - W["5y"][0]
            print(f"  MA{ma_n:2d} rv>{rv:<4} none    : "
                  f"{r['10y']['cagr']*100:5.2f}/{r['10y']['max_drawdown']*100:5.2f} "
                  f"({d10*100:+5.2f}) | {r['5y']['cagr']*100:5.2f}/"
                  f"{r['5y']['max_drawdown']*100:5.2f} ({d5*100:+5.2f}) | {n}")

    print("\n-- with quiet floor 0.8")
    for ma_n in (20,):
        for rv in (1.2, 1.4, 1.6, 99):
            w, n = run(D, 0.04, ma_n, rv, 0.8)
            r = engine.evaluate(D, w)
            print(f"  MA{ma_n:2d} rv>{rv:<4} q0.8    : "
                  f"{r['10y']['cagr']*100:5.2f}/{r['10y']['max_drawdown']*100:5.2f} | "
                  f"{r['5y']['cagr']*100:5.2f}/{r['5y']['max_drawdown']*100:5.2f} | {n}")


if __name__ == "__main__":
    main()
