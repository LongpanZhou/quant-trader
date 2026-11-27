"""Per-year stability of the last-30-minute block conditional on the day move."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import lib  # noqa: E402

ts, o, c = lib.load_panel()
cal = lib.calendar(ts)
first, last = cal["first"], cal["last"]
i1500 = lib.time_index(ts, first, last, 15, 0)
i1530 = lib.time_index(ts, first, last, 15, 30)
sig = c[i1500, 0] / o[first, 0] - 1.0
blk = o[i1530, 1] / o[i1500 + 1, 1] - 1.0
on, _, _ = lib.regime_on(ts, c)
df = pd.DataFrame({"date": cal["dates"], "sig": sig, "blk": blk, "on": on})
df["year"] = df["date"].dt.year
df = df[df["date"] >= "2017-01-03"]

for thr in (-0.01, -0.005, 0.0):
    print(f"threshold {thr*100:.1f}%")
    sub = df[df["on"] & (df["sig"] < thr)]
    for y, g in sub.groupby("year"):
        a = -g["blk"].to_numpy()
        if len(a) > 2:
            t = a.mean() / (a.std(ddof=1) / np.sqrt(len(a)))
        else:
            t = float("nan")
        print(f"  {y}: n={len(a):3d} mean {a.mean()*1e4:8.2f}bp t={t:6.2f} win {np.mean(a>0)*100:5.1f}%")
    allm, allt = sub.shape[0], None
    a = -sub["blk"].to_numpy()
    print(f"  ALL: n={len(a)} mean {a.mean()*1e4:.2f}bp"
          f" t={a.mean()/(a.std(ddof=1)/np.sqrt(len(a))):.2f}")
