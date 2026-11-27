"""Third screen: ATR multiplier surface, lookback/cap robustness, literal
5m-ATR stop (documented negative). 10y, 1 bp.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/agents2/vol-scaled-crash-stop/sweep3.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

from sweep1 import (  # noqa: E402
    build_measures, build_weights, day_bounds, fmt, load_cache, regime_arrays,
    run_one,
)


def atr_daily(highs, lows, closes, first, last, n):
    t_high = np.maximum.reduceat(highs[:, 1], first)
    t_low = np.minimum.reduceat(lows[:, 1], first)
    t_close = closes[last, 1]
    pc = np.r_[np.nan, t_close[:-1]]
    tr = np.maximum.reduce([t_high - t_low, np.abs(t_high - pc), np.abs(t_low - pc)])
    x = pd.Series(tr).rolling(n).mean().to_numpy() / t_close
    return np.r_[np.nan, x[:-1]]


def main():
    t0 = time.time()
    ts, opens, highs, lows, closes, vols = load_cache()
    m = build_measures(ts, opens, highs, lows, closes)
    dates, first, last = m["dates"], m["first"], m["last"]
    risk_on, armed, dc = regime_arrays(ts, closes, first, last)
    nd = len(first)
    cl = np.clip
    a14 = m["atr14"]
    a30 = atr_daily(highs, lows, closes, first, last, 30)
    print(f"setup {time.time()-t0:.1f}s")

    variants = []
    for k in (0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90):
        variants.append((f"ATR14 x{k:.2f} [2.5,6]", cl(k * a14, 0.025, 0.06)))
    variants += [
        ("ATR30 x0.70 [2.5,6]", cl(0.70 * a30, 0.025, 0.06)),
        ("ATR30 x1.00 [2.5,6]", cl(1.00 * a30, 0.025, 0.06)),
        ("ATR14 x0.70 [1.5,6] no floor", cl(0.70 * a14, 0.015, 0.06)),
        ("ATR14 x0.70 [2.5,8] wide cap", cl(0.70 * a14, 0.025, 0.08)),
        ("ATR5m x3 (literal 3x) floor 0.8%", cl(3.0 * m["atr5"], 0.008, 0.03)),
    ]

    out = {}
    print(f"\n{'variant':36s} {'stops':>5s}  10y @1bp")
    for label, d in variants:
        t1 = time.time()
        w, ns = build_weights(ts, opens, closes, first, last, risk_on, armed, d,
                              alloc1=(0, 0, 1))
        s = run_one(label, ts, opens, closes, w, "10y", 1.0)
        out[label] = dict(stops=ns, cagr=s["cagr"], dd=s["max_drawdown"],
                          sharpe=s["sharpe"], fills=s["fills"])
        print(f"{label:36s} {ns:5d}  {fmt(s)}   [{time.time()-t1:.0f}s]")

    (HERE / "sweep3.json").write_text(json.dumps(out, indent=2))

    # where does the stop distance actually sit? distribution per year for x0.70
    d = cl(0.70 * a14, 0.025, 0.06)
    yrs = np.array([x.year for x in dates[last]])
    print("\nATR x0.70 stop distance: share at floor/cap, by year")
    for y in sorted(set(yrs)):
        mm = yrs == y
        print(f"  {y}  median {np.nanmedian(d[mm])*100:4.2f}%  "
              f"floor {np.mean(d[mm] <= 0.0251)*100:3.0f}%  cap {np.mean(d[mm] >= 0.0599)*100:3.0f}%")


if __name__ == "__main__":
    main()
