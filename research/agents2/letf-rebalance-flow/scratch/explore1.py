"""Load the 1m panel once, cache it, and print basic structure."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "research")
import bt

HERE = Path(__file__).resolve().parents[1]
CACHE = HERE / "panel_cache.npz"

if not CACHE.exists():
    ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), "2017-01-03", "2026-10-23", "1min")
    np.savez_compressed(
        CACHE, ts=ts.values.astype("datetime64[ns]"), opens=opens, closes=closes
    )
else:
    z = np.load(CACHE)
    ts = pd.DatetimeIndex(z["ts"])
    opens = z["opens"]
    closes = z["closes"]

print("bars", len(ts), "first", ts[0], "last", ts[-1])
print("dates", ts.normalize().nunique())
print("first day bars", (ts.normalize() == ts[0].normalize()).sum())
print("last day bars", (ts.normalize() == ts[-1].normalize()).sum())
# bar time counts
times = pd.Series(ts.time)
print(times.value_counts().head(5))
print(times.value_counts().tail(5))
print("unique times", times.nunique())
# a sample session
day = ts.normalize() == pd.Timestamp("2024-06-03", tz="America/New_York")
print(ts[day][:5], ts[day][-5:])
print("close last bar", closes[day][-1], "open first", opens[day][0])
# weekday distribution
print(pd.Series(ts.normalize().dayofweek).value_counts().sort_index())
