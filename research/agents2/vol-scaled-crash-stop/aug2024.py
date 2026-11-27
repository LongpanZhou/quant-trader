"""Why did the uncapped ATR stop draw down 39% in Jul-Aug 2024? Look at the
stop distance and the session path on 2024-08-01/02. No backtests.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/agents2/vol-scaled-crash-stop/aug2024.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))

from sweep1 import build_measures, load_cache, regime_arrays  # noqa: E402


def main():
    ts, opens, highs, lows, closes, _ = load_cache()
    m = build_measures(ts, opens, highs, lows, closes)
    first, last, dates = m["first"], m["last"], m["dates"]
    risk_on, armed, _ = regime_arrays(ts, closes, first, last)
    a = m["atr14"]
    days = [str(d) for d in dates[last]]
    for d in ("2024-07-30", "2024-07-31", "2024-08-01", "2024-08-02", "2024-08-05"):
        k = days.index(d)
        f, l = first[k], last[k]
        base = opens[f, 1]
        low = lows[f:l + 1, 1].min()
        print(f"{d} risk_on {risk_on[k]} armed {armed[k]}  ATR14 {a[k]*100:5.2f}%  "
              f"0.7xATR {0.7*a[k]*100:5.2f}%  cap4 {np.clip(0.7*a[k],0.025,0.04)*100:4.2f}%  "
              f"open {base:6.2f} low {low:6.2f} ({(low/base-1)*100:5.2f}% from open) "
              f"close {closes[l,1]:6.2f} ({(closes[l,1]/base-1)*100:5.2f}%)  "
              f"next open {opens[min(l+1,len(ts)-1),1]:6.2f}")

    # all stop triggers in Jul-Aug 2024 for the two distances
    for name, dist in (("cap4", np.clip(0.70 * a, 0.025, 0.040)),
                       ("cap6", np.clip(0.70 * a, 0.025, 0.060))):
        ev = []
        for k, (f, l) in enumerate(zip(first, last)):
            if not (2024 == dates[last][k].year and 7 <= dates[last][k].month <= 8):
                continue
            if not risk_on[k] or not armed[k]:
                continue
            base = opens[f, 1]
            for i in range(f, l + 1):
                if closes[i, 1] < base * (1 - dist[k]):
                    ev.append((str(ts[i])[:16], round(float(dist[k]) * 100, 2)))
                    break
        print(f"\n{name} stops Jul-Aug 2024: {ev}")


if __name__ == "__main__":
    main()
