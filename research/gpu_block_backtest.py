r"""GPU block-return backtester for the first-hour / crash-stop family.

The CPU-heavy way to test a parameter grid is to replay 1,057,023 minute bars
for every variant. This engine instead precomputes, once per session:

    overnight return, first-hour return, afternoon return,
    stop-in-first-hour return, stop-in-afternoon return

for a small grid of stop thresholds. A whole parameter grid is then evaluated
as a batch of daily return matrices on the GPU. Only the top candidates need an
exact `bt.run` replay.

This is a screening engine, not a replacement for the exact harness.

Run from the repo root:

    $env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
    python research/gpu_block_backtest.py
"""

from __future__ import annotations

import sys
import time
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


START = "2017-01-03"
END = "2026-10-23"


def prepare(ts, op, cl):
    dates = np.array([t.date() for t in ts])
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(dates) - 1]
    D = len(first)
    mid = np.minimum(first + 60, last)

    r_night = np.zeros(D)
    r_first = np.zeros(D)
    r_after = np.zeros(D)
    b_night = np.zeros(D)
    b_first = np.zeros(D)
    b_after = np.zeros(D)
    first_signal = np.zeros(D)
    for d in range(D):
        f, m, l = first[d], mid[d], last[d]
        if d > 0:
            r_night[d] = op[f, 1] / op[last[d - 1], 1] - 1.0
            b_night[d] = op[f, 2] / op[last[d - 1], 2] - 1.0
        if m > f:
            r_first[d] = op[m, 1] / op[f, 1] - 1.0
            b_first[d] = op[m, 2] / op[f, 2] - 1.0
            first_signal[d] = cl[m - 1, 0] / op[f, 0] - 1.0
        if l > m:
            r_after[d] = op[l, 1] / op[m, 1] - 1.0
            b_after[d] = op[l, 2] / op[m, 2] - 1.0

    stops = [0.025, 0.03, 0.035, 0.04, 0.045, 0.05, 0.06]
    sf_ret = np.zeros((len(stops), D))
    sa_ret = np.zeros((len(stops), D))
    sf_flag = np.zeros((len(stops), D), bool)
    sa_flag = np.zeros((len(stops), D), bool)
    for k, stop in enumerate(stops):
        for d in range(D):
            f, m, l = first[d], mid[d], last[d]
            base = op[f, 1]
            # first hour
            sf_ret[k, d] = r_first[d]
            if m > f:
                for i in range(f, m):
                    if cl[i, 1] < base * (1.0 - stop):
                        j = min(i + 1, m)
                        r_tq = op[j, 1] / base - 1.0
                        r_b = op[m, 2] / op[j, 2] - 1.0 if j < m else 0.0
                        sf_ret[k, d] = (1.0 + r_tq) * (1.0 + r_b) - 1.0
                        sf_flag[k, d] = True
                        break
            # afternoon, entry at 10:30, stop base is the session open
            sa_ret[k, d] = r_after[d]
            if l > m:
                for i in range(m, l):
                    if cl[i, 1] < base * (1.0 - stop):
                        j = min(i + 1, l)
                        r_tq = op[j, 1] / op[m, 1] - 1.0
                        r_b = op[l, 2] / op[j, 2] - 1.0 if j < l else 0.0
                        sa_ret[k, d] = (1.0 + r_tq) * (1.0 + r_b) - 1.0
                        sa_flag[k, d] = True
                        break
    return (first, last, mid, r_night, r_first, r_after,
            b_night, b_first, b_after, first_signal, stops,
            sf_ret, sa_ret, sf_flag, sa_flag)


def main():
    t0 = time.time()
    ts, op, cl = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1min")
    (first, last, mid, r_night, r_first, r_after, b_night, b_first, b_after,
     first_signal, stops, sf_ret, sa_ret, sf_flag, sa_flag) = prepare(ts, op, cl)
    dclose = cl[last, 0]
    dret = np.r_[np.nan, dclose[1:] / dclose[:-1] - 1.0]
    vol20 = pd.Series(dret).rolling(20).std().shift(1).to_numpy() * np.sqrt(252.0)
    D = len(first)

    sma_lengths = [105, 120, 135, 150, 165, 180, 195, 210]
    bands = [0.0, 0.01, 0.02, 0.03]
    caps = [0.35, 0.45, 0.55, 0.65, 99.0]
    thresholds = [-0.01, -0.005, 0.0, 0.005]
    stop_idx = [stops.index(x) for x in (0.03, 0.04, 0.05)]

    regime_rows = []
    labels = []
    for n in sma_lengths:
        sma = pd.Series(dclose).rolling(n).mean().to_numpy()
        for band in bands:
            reg = np.zeros(D, bool)
            state = False
            for k in range(1, D):
                if not np.isfinite(sma[k - 1]):
                    state = False
                elif dclose[k - 1] > sma[k - 1] * (1.0 + band):
                    state = True
                elif dclose[k - 1] < sma[k - 1] * (1.0 - band):
                    state = False
                reg[k] = state
            regime_rows.append(reg)
            labels.append((n, band))
    regime = np.vstack(regime_rows)
    print(f"prepared {D} sessions, {len(labels)} regime rows, {len(stops)} stops "
          f"in {time.time()-t0:.1f}s")

    # GPU batch evaluation
    Rreg = XP.asarray(regime)
    Rvol = XP.asarray(vol20)
    Rnight = XP.asarray(r_night)
    Rfirst = XP.asarray(r_first)
    Rafter = XP.asarray(r_after)
    Rbn = XP.asarray(b_night)
    Rbf = XP.asarray(b_first)
    Rba = XP.asarray(b_after)
    Rsig = XP.asarray(first_signal)
    Rsf = XP.asarray(sf_ret)
    Rsa = XP.asarray(sa_ret)
    Rsf_flag = XP.asarray(sf_flag)
    Rsa_flag = XP.asarray(sa_flag)

    variants = []
    for ri in range(len(labels)):
        for cap in caps:
            for thr in thresholds:
                for si in stop_idx:
                    variants.append((ri, cap, thr, si))
    V = len(variants)
    out = XP.zeros((V, D), dtype=XP.float32)
    for j, (ri, cap, thr, si) in enumerate(variants):
        night_ok = Rreg[ri] & (Rvol <= cap)
        after_ok = Rreg[ri] & (Rsig >= thr)
        r = XP.where(night_ok, Rnight, Rbn)
        r = r + XP.where(night_ok,
                         XP.where(Rsf_flag[si], Rsf[si], Rfirst), Rbf)
        r = r + XP.where(after_ok,
                         XP.where(Rsa_flag[si], Rsa[si], Rafter), Rba)
        out[j] = r
    eq = XP.cumprod(1.0 + out, axis=1)
    years = D / 252.0
    cagr = (eq[:, -1] / eq[:, 0]) ** (1.0 / years) - 1.0
    peak = eq[:, 0].copy()
    maxdd = XP.zeros(V, dtype=eq.dtype)
    for t in range(eq.shape[1]):
        peak = XP.maximum(peak, eq[:, t])
        maxdd = XP.maximum(maxdd, 1.0 - eq[:, t] / peak)
    mean = out.mean(axis=1)
    std = out.std(axis=1)
    sharpe = XP.where(std > 0, mean / std * np.sqrt(252.0), 0.0)

    cagr_h, dd_h, sh_h = cp.asnumpy(cagr), cp.asnumpy(maxdd), cp.asnumpy(sharpe)
    print(f"GPU={GPU} variants={V} evaluation={time.time()-t0:.1f}s")
    order = np.argsort(-cagr_h)
    print(f"{'rank':>4} {'SMA':>4} {'band':>5} {'cap':>5} {'thr':>6} {'stop':>5} "
          f"{'CAGR':>7} {'DD':>6} {'Sharpe':>6} {'Calmar':>6}")
    for rank, j in enumerate(order[:25], 1):
        ri, cap, thr, si = variants[j]
        n, band = labels[ri]
        calmar = cagr_h[j] / dd_h[j] if dd_h[j] > 0 else 0.0
        print(f"{rank:4d} {n:4d} {band:5.2f} {cap:5.2f} {thr:6.3f} {stops[si]:5.3f} "
              f"{cagr_h[j]*100:6.2f}% {dd_h[j]*100:5.2f}% {sh_h[j]:6.2f} {calmar:6.2f}")

    # Best Calmar with CAGR >= 60%.
    mask = cagr_h >= 0.60
    cand = np.flatnonzero(mask)
    if len(cand):
        best = cand[np.argmax(cagr_h[cand] / np.maximum(dd_h[cand], 1e-9))]
        ri, cap, thr, si = variants[best]
        n, band = labels[ri]
        print("\nbest Calmar with CAGR>=60%:")
        print(f"  SMA={n} band={band} cap={cap} thr={thr} stop={stops[si]} "
              f"CAGR={cagr_h[best]*100:.2f}% DD={dd_h[best]*100:.2f}% "
              f"Sharpe={sh_h[best]:.2f}")


if __name__ == "__main__":
    main()
