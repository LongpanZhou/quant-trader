"""Exploration 4b: fine grid of the vol-target brake + drawdown throttle (1/5 bp)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402
from explore3 import load, bounds, day_setup, build, met  # noqa: E402


def main():
    ts, opens, closes = load()
    dates, first, last = bounds(ts)
    risk_on, armed, stopped, day_id, dcl = day_setup(ts, opens, closes, first, last)
    n, d = len(ts), len(first)
    rets = np.diff(dcl, axis=0) / dcl[:-1]
    dclose = dcl[:, 0]

    def vol(win):
        v = pd.DataFrame(rets).rolling(win).std().to_numpy() * np.sqrt(252)
        return np.vstack([np.full((1, 3), np.nan), v])

    def run(wt, dest=0, slip=1.0):
        wt = np.nan_to_num(wt, nan=1.0)
        return met(ts, opens, closes, build(risk_on, stopped, day_id, n, wt, dest), slip)

    def line(label, m, m5=None):
        a, b = m["10y"], m["5y"]
        s = (f"{label:<28} 10y {a[0]*100:6.2f}/{a[1]*100:5.2f} C{a[0]/a[1]:4.2f} "
             f"| 5y {b[0]*100:6.2f}/{b[1]*100:5.2f} C{b[0]/b[1]:4.2f} f{a[3]:4d}")
        if m5:
            a5, b5 = m5["10y"], m5["5y"]
            s += f" || 5bp {a5[0]*100:6.2f}/{a5[1]*100:5.2f} | {b5[0]*100:6.2f}/{b5[1]*100:5.2f}"
        print(s, flush=True)

    v20 = vol(20)
    print("=== vol-target brake, stop->BIL, 20d ===", flush=True)
    for tv in (0.85, 0.80, 0.75, 0.70, 0.65, 0.60):
        wt = np.clip(tv / v20[:, 1], 0, 1)
        line(f"tv={tv:.2f} mWt{np.nanmean(wt):.2f}", run(wt), run(wt, slip=5.0))

    print("\n=== vol window @ tv=0.70 ===", flush=True)
    for win in (10, 20, 40, 60):
        v = vol(win)
        wt = np.clip(0.70 / v[:, 1], 0, 1)
        line(f"win={win} mWt{np.nanmean(wt):.2f}", run(wt), run(wt, slip=5.0))

    print("\n=== tv=0.65 window ===", flush=True)
    for win in (10, 20, 40, 60):
        v = vol(win)
        wt = np.clip(0.65 / v[:, 1], 0, 1)
        line(f"win={win} mWt{np.nanmean(wt):.2f}", run(wt), run(wt, slip=5.0))

    print("\n=== drawdown throttle (stop->BIL, no vol brake) ===", flush=True)
    for hin in (126, 252):
        hi = pd.Series(dclose).rolling(hin).max().to_numpy()
        dd = dclose / hi - 1
        for thr, wtc in ((0.05, 0.7), (0.08, 0.7), (0.08, 0.5), (0.10, 0.5), (0.15, 0.3)):
            wt = np.where(dd < -thr, wtc, 1.0)
            line(f"hi{hin} dd<{-thr:.0%} wT{wtc}", run(wt), run(wt, slip=5.0))


if __name__ == "__main__":
    main()
