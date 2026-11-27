r"""Exact 1-minute test of the GPU-screen candidate.

Daily screen winner: QQQ SMA 105, 2% band, 20-day TQQQ vol cap 55%,
QQQ defensive. This script adds the round-1 armed 4% minute stop and tests
defensive QQQ vs BIL and stop-to-QQQ vs stop-to-BIL.

Run from the repo root:

    $env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
    python research/verification/gpu_candidate.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402
import fastbt  # noqa: E402

START10, START5, END = "2017-01-03", "2021-10-25", "2026-10-23"
BARS = 252 * 390


def build(ts, opens, closes, sma_n=105, band=0.02, cap=0.55,
          defensive="QQQ", stop_to="QQQ", stop=0.04, arm_buf=0.01):
    dates = np.array([t.date() for t in ts])
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(dates) - 1]
    qc, tc = closes[:, 0], closes[:, 1]
    dclose = qc[last]
    dret = np.r_[np.nan, dclose[1:] / dclose[:-1] - 1.0]
    sma = pd.Series(dclose).rolling(sma_n).mean().to_numpy()
    ma20 = pd.Series(dclose).rolling(20).mean().to_numpy()
    vol = pd.Series(dret).rolling(20).std().to_numpy() * np.sqrt(252.0)
    sma_prev = np.r_[np.nan, sma[:-1]]
    ma20_prev = np.r_[np.nan, ma20[:-1]]
    vol_prev = np.r_[np.nan, vol[:-1]]

    w = np.zeros((len(ts), 3))
    for k, (f, l) in enumerate(zip(first, last)):
        risk_on = bool(k > 0 and np.isfinite(sma_prev[k])
                       and dclose[k - 1] > sma_prev[k] * (1 + band)
                       and (not np.isfinite(vol_prev[k]) or vol_prev[k] <= cap))
        armed = bool(risk_on and np.isfinite(ma20_prev[k])
                     and qc[f] < ma20_prev[k] * (1 + arm_buf))
        base = opens[f, 1]
        state = risk_on
        for i in range(f, l + 1):
            if armed and state and tc[i] < base * (1 - stop):
                state = False
            if state:
                w[i, 1] = 1.0
            elif defensive == "QQQ":
                w[i, 0] = 1.0
            else:
                w[i, 2] = 1.0
            if not state and stop_to == "BIL" and defensive == "QQQ":
                w[i, 0] = 0.0
                w[i, 2] = 1.0
    return w


def main():
    ts, op, cl = bt.panel(("QQQ", "TQQQ", "BIL"), START10, END, "1min")
    variants = {
        "SMA105 cap55 QQQ def, stop->QQQ": dict(defensive="QQQ", stop_to="QQQ"),
        "SMA105 cap55 QQQ def, stop->BIL": dict(defensive="QQQ", stop_to="BIL"),
        "SMA105 cap55 BIL def, stop->BIL": dict(defensive="BIL", stop_to="BIL"),
        "SMA105 cap55 QQQ def, no stop": dict(defensive="QQQ", stop_to="QQQ", stop=1.0),
    }
    for name, kw in variants.items():
        w = build(ts, op, cl, **kw)
        print(f"\n{name}")
        for label, start in (("10y", START10), ("5y", START5)):
            vals = []
            for slip in (1.0, 5.0, 10.0):
                r = fastbt.run(ts, op, cl, w, start, band=0.02, slippage_bps=slip)
                s = bt.stats(r, BARS)
                vals.append(f"{slip:.0f}bp {s['cagr']*100:.2f}/{s['max_drawdown']*100:.2f}")
            print(f"  {label}: " + "  ".join(vals))


if __name__ == "__main__":
    main()
