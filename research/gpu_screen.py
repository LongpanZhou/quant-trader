r"""GPU-accelerated screen of daily QQQ/TQQQ/BIL regime variants.

This is a coarse screen, not a promotion test. It sweeps SMA length, band,
volatility cap and defensive asset on daily bars using CuPy, then prints the
top candidates. The best few are re-tested on the exact 1-minute harness.

Run from the repo root:

    $env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
    python research/gpu_screen.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

try:
    import cupy as cp

    XP = cp
    GPU = True
except Exception:
    cp = None
    XP = np
    GPU = False


def main() -> None:
    ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), "2017-01-03", "2026-10-23", "1D")
    i0 = bt.start_index(ts, "2017-01-03")
    q, tq, bil = closes[:, 0], closes[:, 1], closes[:, 2]
    r_tq = np.r_[np.nan, tq[1:] / tq[:-1] - 1.0]
    r_qqq = np.r_[np.nan, q[1:] / q[:-1] - 1.0]
    r_bil = np.r_[np.nan, bil[1:] / bil[:-1] - 1.0]
    vol20 = pd.Series(r_tq).rolling(20).std().to_numpy() * np.sqrt(252.0)

    sma_lengths = list(range(60, 251, 5))
    bands = [0.0, 0.01, 0.02, 0.03]
    vol_caps = [None, 0.45, 0.55, 0.65, 0.80]
    defensives = [("BIL", r_bil), ("QQQ", r_qqq)]

    rows = []
    labels = []
    for n in sma_lengths:
        sma = pd.Series(q).rolling(n).mean().to_numpy()
        base = q[:-1] > sma[:-1]
        base = np.r_[False, base]  # align with r_tq index
        for band in bands:
            on = q[:-1] > sma[:-1] * (1.0 + band)
            on = np.r_[False, on]
            for cap in vol_caps:
                vok = np.ones_like(on, dtype=bool) if cap is None else (vol20 <= cap)
                for dname, rdef in defensives:
                    w = (on & vok).astype(float)
                    rets = w * r_tq + (1.0 - w) * rdef
                    rets = rets[i0:]
                    rows.append(rets)
                    labels.append((n, band, cap, dname))
    R = np.vstack(rows).astype(np.float32)
    X = XP.asarray(R)
    eq = XP.cumprod(1.0 + X, axis=1)
    years = R.shape[1] / 252.0
    cagr = (eq[:, -1] / eq[:, 0]) ** (1.0 / years) - 1.0
    peak = eq[:, 0].copy()
    maxdd = XP.zeros(eq.shape[0], dtype=eq.dtype)
    for t in range(eq.shape[1]):
        peak = XP.maximum(peak, eq[:, t])
        maxdd = XP.maximum(maxdd, 1.0 - eq[:, t] / peak)
    mean = X.mean(axis=1)
    std = X.std(axis=1)
    sharpe = XP.where(std > 0, mean / std * np.sqrt(252.0), 0.0)

    cagr_h, dd_h, sh_h = cp.asnumpy(cagr), cp.asnumpy(maxdd), cp.asnumpy(sharpe)
    order = np.argsort(-cagr_h)
    print(f"GPU={GPU} variants={len(labels)} bars={R.shape[1]}")
    print(f"{'rank':>4} {'SMA':>4} {'band':>5} {'volcap':>6} {'def':>4} "
          f"{'CAGR':>7} {'DD':>6} {'Sharpe':>6} {'Calmar':>6}")
    for rank, j in enumerate(order[:20], 1):
        n, band, cap, dname = labels[j]
        calmar = cagr_h[j] / dd_h[j] if dd_h[j] > 0 else 0.0
        print(f"{rank:4d} {n:4d} {band:5.2f} {str(cap):>6} {dname:>4} "
              f"{cagr_h[j]*100:6.2f}% {dd_h[j]*100:5.2f}% {sh_h[j]:6.2f} {calmar:6.2f}")

    # Best Calmar among variants with CAGR >= 45%.
    mask = cagr_h >= 0.45
    cand = np.flatnonzero(mask)
    if len(cand):
        best = cand[np.argmax(cagr_h[cand] / np.maximum(dd_h[cand], 1e-9))]
        n, band, cap, dname = labels[best]
        print("\nbest Calmar with CAGR>=45%:")
        print(f"  SMA={n} band={band} volcap={cap} defensive={dname} "
              f"CAGR={cagr_h[best]*100:.2f}% DD={dd_h[best]*100:.2f}% "
              f"Sharpe={sh_h[best]:.2f}")


if __name__ == "__main__":
    main()
