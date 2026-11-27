"""Proper fixed-time / cooldown re-entry: only after the stop has happened."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import srlib as S  # noqa: E402

A = S.arrays()
ts, first, last = A["ts"], A["first"], A["last"]
o, c = A["o"], A["c"]
ev = pd.read_csv(HERE / "reclaim_events.csv")
ev["i"] = ev["i"].astype(int); ev["z"] = ev["z"].astype(int); ev["f"] = ev["f"].astype(int)

print("A) enter at fixed clock time T only if the stop already happened before T:")
for mins in (60, 90, 120, 180, 240, 300, 330, 360):
    vals, n = [], 0
    for _, r in ev.iterrows():
        i, z, f = int(r["i"]), int(r["z"]), int(r["f"])
        j = f + mins
        if i < j <= z:   # stopped before T; enter at T
            vals.append(c[z, 1] / o[j, 1] - 1)
            n += 1
    v = np.array(vals)
    print(f"  T={mins//60:02d}:{mins%60:02d}  n={n:3d}  mean {v.mean()*100:+7.3f}%  "
          f"median {np.median(v)*100:+6.3f}%  share<0 {np.mean(v<0)*100:4.0f}%")

print("\nB) enter `d` minutes after the stop bar (cooldown), hold to close:")
for d in (15, 30, 60, 90, 120, 180):
    vals = []
    for _, r in ev.iterrows():
        i, z = int(r["i"]), int(r["z"])
        j = i + d
        if j <= z:
            vals.append(c[z, 1] / o[j, 1] - 1)
    v = np.array(vals)
    print(f"  +{d:3d}m  n={len(v):3d}  mean {v.mean()*100:+7.3f}%  median {np.median(v)*100:+6.3f}%  "
          f"share<0 {np.mean(v<0)*100:4.0f}%")

print("\nC) same, but only early stops (first hour):")
for d in (15, 30, 60, 90, 120, 180):
    vals = []
    for _, r in ev.iterrows():
        i, z = int(r["i"]), int(r["z"])
        if int(r["minute"]) > 60:
            continue
        j = i + d
        if j <= z:
            vals.append(c[z, 1] / o[j, 1] - 1)
    v = np.array(vals)
    if len(v):
        print(f"  +{d:3d}m  n={len(v):3d}  mean {v.mean()*100:+7.3f}%  median {np.median(v)*100:+6.3f}%  "
              f"share<0 {np.mean(v<0)*100:4.0f}%")

print("\nD) early-stop days only: return from stop+1 open to close, by year:")
sub = ev[ev["minute"] <= 60]
rows = []
for _, r in sub.iterrows():
    i, z = int(r["i"]), int(r["z"])
    if i + 1 <= z:
        rows.append((str(r["date"])[:4], c[z, 1] / o[i + 1, 1] - 1))
t = pd.DataFrame(rows, columns=["year", "ret"])
print(t.groupby("year")["ret"].agg(["size", "mean", "median"]).round(4).to_string())
print(f"  overall mean {t['ret'].mean()*100:+.3f}%  n={len(t)}")
