"""Small facts for the report: stop-distance distribution, per-year stops, and
the 2024-08 gap that the uncapped stop missed. No backtests.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/agents2/vol-scaled-crash-stop/facts.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))

from sweep1 import build_measures, load_cache, regime_arrays  # noqa: E402


def events(ts, opens, closes, first, last, risk_on, armed, dist):
    ev = []
    for k, (f, l) in enumerate(zip(first, last)):
        if not risk_on[k] or not armed[k]:
            continue
        base = opens[f, 1]
        for i in range(f, l + 1):
            if dist[k] == dist[k] and closes[i, 1] < base * (1 - dist[k]):
                ev.append((str(ts[i])[:16], round(float(dist[k]) * 100, 2)))
                break
    return ev


def main():
    ts, opens, highs, lows, closes, _ = load_cache()
    m = build_measures(ts, opens, highs, lows, closes)
    first, last, dates = m["first"], m["last"], m["dates"]
    risk_on, armed, _ = regime_arrays(ts, closes, first, last)
    a = m["atr14"]
    nd = len(first)
    cap4 = np.clip(0.70 * a, 0.025, 0.040)
    ev4 = events(ts, opens, closes, first, last, risk_on, armed, np.full(nd, 0.04))
    evc = events(ts, opens, closes, first, last, risk_on, armed, cap4)
    y4 = pd.Series([e[0][:4] for e in ev4]).value_counts().sort_index()
    yc = pd.Series([e[0][:4] for e in evc]).value_counts().sort_index()
    print("stops per year (test window)")
    print(pd.DataFrame({"fixed4": y4, "cap4k70": yc}).fillna(0).astype(int).to_string())
    print(f"\ntotal fixed4 {len(ev4)}  cap4k70 {len(evc)}")

    yrs = np.array([d.year for d in dates[last]])
    print("\ncap4 k0.70 effective stop distance by year (armed risk-on days)")
    for y in sorted(set(yrs)):
        mm = (yrs == y) & risk_on & armed & np.isfinite(cap4)
        if mm.sum() == 0:
            continue
        print(f"  {y}  median {np.median(cap4[mm])*100:4.2f}%  floor {np.mean(cap4[mm] <= 0.0251)*100:3.0f}%"
              f"  cap {np.mean(cap4[mm] >= 0.0399)*100:3.0f}%")

    # the August 2024 gap the uncapped stop rode through
    i = pd.Timestamp("2024-08-01 15:59", tz="America/New_York")
    j = pd.Timestamp("2024-08-05 09:30", tz="America/New_York")
    i0 = int(ts.searchsorted(i))
    j0 = int(ts.searchsorted(j))
    print(f"\nTQQQ 2024-08-01 15:59 close {closes[i0,1]:.2f} -> 2024-08-05 09:30 open "
          f"{opens[j0,1]:.2f}  = {(opens[j0,1]/closes[i0,1]-1)*100:+.2f}%")
    # 2024-07-10 .. 2024-08-05 TQQQ path
    p = int(ts.searchsorted(pd.Timestamp("2024-07-10 15:54", tz="America/New_York")))
    q = int(ts.searchsorted(pd.Timestamp("2024-08-05 09:30", tz="America/New_York")))
    print(f"TQQQ 2024-07-10 close {closes[p,1]:.2f} -> 2024-08-05 open {opens[q,1]:.2f}"
          f" = {(opens[q,1]/closes[p,1]-1)*100:+.2f}%")


if __name__ == "__main__":
    main()
