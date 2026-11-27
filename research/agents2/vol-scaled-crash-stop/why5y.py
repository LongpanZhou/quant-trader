"""Why is the 5y max drawdown unchanged? Check stops in the 2026 episode and
the uncapped variant's drawdown dates. No backtests.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/agents2/vol-scaled-crash-stop/why5y.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

from sweep1 import build_measures, load_cache, regime_arrays  # noqa: E402


def events(ts, opens, closes, first, last, risk_on, armed, dist):
    ev = []
    for k, (f, l) in enumerate(zip(first, last)):
        if not risk_on[k] or not armed[k]:
            continue
        base = opens[f, 1]
        for i in range(f, l + 1):
            if dist[k] == dist[k] and closes[i, 1] < base * (1 - dist[k]):
                ev.append((str(ts[i]), round(float(dist[k]) * 100, 2)))
                break
    return ev


def main():
    ts, opens, highs, lows, closes, _ = load_cache()
    m = build_measures(ts, opens, highs, lows, closes)
    first, last = m["first"], m["last"]
    risk_on, armed, _ = regime_arrays(ts, closes, first, last)
    a = m["atr14"]
    ev4 = events(ts, opens, closes, first, last, risk_on, armed, np.full(len(first), 0.04))
    evc = events(ts, opens, closes, first, last, risk_on, armed, np.clip(0.70 * a, 0.025, 0.040))
    print("2026-06-01..2026-08-01 stop events")
    print("  fixed4 :", [x for x in ev4 if "2026-06" <= x[0][:7] <= "2026-08"])
    print("  cap4k70:", [x for x in evc if "2026-06" <= x[0][:7] <= "2026-08"])
    print(f"\ntotal events fixed4 {len(ev4)}  cap4k70 {len(evc)}")

    s4 = json.loads((HERE / "sweep4.json").read_text())
    for k in ("winner_fixed4", "atr070", "atr085", "vol120"):
        if k in s4:
            print(k, "10y dd", s4[k]["windows"]["10y"]["dd_peak"], "->",
                  s4[k]["windows"]["10y"]["dd_trough"],
                  "| 5y dd", s4[k]["windows"]["5y"]["dd_peak"], "->",
                  s4[k]["windows"]["5y"]["dd_trough"])
    # armed-day count in the 2026 drawdown
    dates = np.array([t.date() for t in ts])
    y = np.array([d.year for d in dates[last]])
    print("\narmed share by year:")
    for yy in sorted(set(y)):
        mm = y == yy
        print(f"  {yy} armed {np.mean((risk_on & armed)[mm])*100:4.1f}%  "
              f"risk_on {np.mean(risk_on[mm])*100:4.1f}%  "
              f"median stop cap4 {np.nanmedian(np.clip(0.7*a, 0.025, 0.04)[mm])*100:.2f}%")


if __name__ == "__main__":
    main()
