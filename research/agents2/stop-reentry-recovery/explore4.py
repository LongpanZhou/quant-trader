"""Next-day gap behaviour and post-stop tighter stops.

NOTE: the fixed-time section A/B at the top is superseded by explore5.py.
It could enter before the stop on late-stop days (a look-ahead bug); the
corrected, stop-after-only tables are in explore5.py.  The gap and tighter-stop
sections below are valid.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import srlib as S  # noqa: E402

A = S.arrays()
ts, dates, first, last = A["ts"], A["dates"], A["first"], A["last"]
o, c = A["o"], A["c"]
reg, ma20 = S.regime(ts, c[:, 0], first, last)

ev = pd.read_csv(HERE / "reclaim_events.csv")
ev["i"] = ev["i"].astype(int); ev["z"] = ev["z"].astype(int); ev["f"] = ev["f"].astype(int)
ev["k"] = ev["k"].astype(int)

# fixed-time same-day re-entry
print("Fixed-time re-entry after a stop (fill at that bar's open, hold to close):")
for mins in (30, 60, 90, 120, 180, 240, 300, 330):
    vals, vals_early = [], []
    for _, r in ev.iterrows():
        j = int(r["f"]) + mins
        if j >= int(r["z"]):
            continue
        vals.append(c[int(r["z"]), 1] / o[j, 1] - 1)
        if int(r["minute"]) <= 60:
            vals_early.append(c[int(r["z"]), 1] / o[j, 1] - 1)
    print(f"  {mins//60:02d}:{mins%60:02d}  n={len(vals):3d} mean {np.mean(vals)*100:+7.3f}% "
          f"med {np.median(vals)*100:+6.3f}%  share<0 {np.mean(np.array(vals)<0)*100:4.0f}%  | "
          f"early-stop n={len(vals_early):2d} mean {np.mean(vals_early)*100 if vals_early else 0:+7.3f}%")

# next-day gap and continuation
print("\nNext-day gap after a stop (next_open / stop-day close - 1):")
gaps, oc = [], []
for _, r in ev.iterrows():
    k = int(r["k"])
    if k + 1 >= len(first):
        continue
    nf, nz = first[k + 1], last[k + 1]
    gap = o[nf, 1] / c[int(r["z"]), 1] - 1
    gaps.append(gap); oc.append(c[nz, 1] / o[nf, 1] - 1)
gaps = np.array(gaps); oc = np.array(oc)
print(f"  gap mean {gaps.mean()*100:+.3f}%  median {np.median(gaps)*100:+.3f}%  share<0 {np.mean(gaps<0)*100:.0f}%")
for lab, m in (("gap<-2%", gaps < -0.02), ("-2..-1%", (gaps >= -0.02) & (gaps < -0.01)),
               ("-1..0%", (gaps >= -0.01) & (gaps < 0)), ("gap>=0", gaps >= 0)):
    if m.sum():
        print(f"  {lab:10s} n={m.sum():3d} same-day open->close mean {oc[m].mean()*100:+.3f}% "
              f"median {np.median(oc[m])*100:+.3f}%")
print("  correlation(gap, day return):", round(float(np.corrcoef(gaps, oc)[0, 1]), 3))

# next-day entry at 09:31 (winner) vs skip if first-minute close < prior close
print("\nNext-day first-minute filter (enter at 09:31 only if 09:30 close > prior close):")
keep, skip = [], []
for _, r in ev.iterrows():
    k = int(r["k"])
    if k + 1 >= len(first):
        continue
    nf, nz = first[k + 1], last[k + 1]
    ret = c[nz, 1] / o[nf + 1, 1] - 1 if nf + 1 < nz else np.nan
    (keep if c[nf, 1] > c[int(r["z"]), 1] else skip).append(ret)
for lab, x in (("first min up", keep), ("first min down", skip)):
    x = np.array([v for v in x if np.isfinite(v)])
    print(f"  {lab:15s} n={len(x):3d} mean {x.mean()*100:+.3f}%  median {np.median(x)*100:+.3f}%")

# post-stop tighter stop on the re-entry day
print("\nNext-day open->close with a tight stop from the next open (close-based, exit next open):")
for tight in (0.01, 0.015, 0.02, 0.03, 0.04):
    vals = []
    for _, r in ev.iterrows():
        k = int(r["k"])
        if k + 1 >= len(first):
            continue
        nf, nz = first[k + 1], last[k + 1]
        entry = o[nf + 1, 1]
        ex = o[nz, 1]
        for m in range(nf + 1, nz + 1):
            if c[m, 1] < entry * (1 - tight):
                ex = o[min(m + 1, nz), 1]
                break
        vals.append(ex / entry - 1)
    v = np.array(vals)
    print(f"  tight {tight*100:4.1f}%  mean {v.mean()*100:+7.3f}%  median {np.median(v)*100:+6.3f}%  "
          f"share<0 {np.mean(v<0)*100:4.0f}%")
