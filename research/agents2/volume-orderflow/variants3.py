"""Step 12: volume-gated overnight de-risking, conditioned on short-term trend."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine  # noqa: E402


def overnight_gate(D, w, k=1.5, size=0.0, ma=None, m=388, below=True):
    """Cut overnight exposure after a high-relative-volume session.

    ma: None or a per-day moving average array; the gate only applies when
    QQQ's close is below (above) that average by `below`.
    """
    w = w.copy()
    nev = 0
    rv = D.rvol_cum_q[:, m]
    for d in range(D.nd - 1):
        if not D.reg[d]:
            continue
        if not np.isfinite(rv[d]) or rv[d] <= k:
            continue
        if ma is not None:
            ref = ma[d]
            if not np.isfinite(ref):
                continue
            if below and not (D.qc_m[d, m] < ref):
                continue
            if (not below) and not (D.qc_m[d, m] > ref):
                continue
        nev += 1
        l = D.last[d]
        if l - 1 <= D.first[d]:
            continue
        w[l - 1, 1] = size
        w[l - 1, 2] = 1.0 - size
        w[l, 1] = float(D.reg[d + 1])
        w[l, 2] = 1.0 - w[l, 1]
    return w, nev


def main():
    D = engine.Data()
    base, _ = engine.winner_weights(D)
    engine.evaluate(D, base, "winner")
    ma20 = np.r_[np.nan, pd.Series(D.qc).rolling(20).mean().to_numpy()[:-1]]
    ma50 = np.r_[np.nan, pd.Series(D.qc).rolling(50).mean().to_numpy()[:-1]]

    print("\n-- gate rvol>k, QQQ below MA20 at 15:58, full exit")
    for k in (1.2, 1.5, 1.8, 2.2):
        w, n = overnight_gate(D, base, k=k, ma=ma20)
        engine.evaluate(D, w, f"rvol>{k} & QQQ<MA20 (n={n})")

    print("\n-- gate rvol>k, QQQ below MA50, full exit")
    for k in (1.2, 1.5, 1.8, 2.2):
        w, n = overnight_gate(D, base, k=k, ma=ma50)
        engine.evaluate(D, w, f"rvol>{k} & QQQ<MA50 (n={n})")

    print("\n-- partial: keep 50% TQQQ overnight")
    for k in (1.2, 1.5, 2.0):
        w, n = overnight_gate(D, base, k=k, ma=ma20, size=0.5)
        engine.evaluate(D, w, f"rvol>{k} & QQQ<MA20, 50% (n={n})")
    for k in (1.5, 2.0):
        w, n = overnight_gate(D, base, k=k, ma=None, size=0.5)
        engine.evaluate(D, w, f"rvol>{k}, 50% (n={n})")

    print("\n-- no MA condition, full exit (reproduce step 5)")
    for k in (1.5, 1.8, 2.0):
        w, n = overnight_gate(D, base, k=k)
        engine.evaluate(D, w, f"rvol>{k} (n={n})")


if __name__ == "__main__":
    main()
