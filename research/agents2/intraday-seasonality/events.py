"""How many masked days actually trade, and what does each executed carve earn?

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/agents2/intraday-seasonality/events.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import lib  # noqa: E402

ts, opens, closes = lib.load_panel()
cal = lib.calendar(ts)
first, last = cal["first"], cal["last"]
w_base, _ = lib.build_base(ts, opens, closes)
i1500 = lib.time_index(ts, first, last, 15, 0)
i1530 = lib.time_index(ts, first, last, 15, 30)
sig = closes[i1500, 0] / opens[first, 0] - 1.0
dow = cal["dow"]

# base holding at the 15:00 bar (weight applied to bar 15:00, i.e. filled at 15:01)
held = w_base[i1500, 1] > 0.5
print(f"sessions where the winner is long TQQQ at 15:00: {held.sum()} / {len(held)}")

# block actually skipped: open 15:01 -> open 15:30
blk = opens[i1530, 1] / opens[i1500 + 1, 1] - 1.0
blk_c2c = closes[i1530, 1] / closes[i1500, 1] - 1.0

cands = {
    "q<-1.0": sig < -0.01,
    "q<-0.5": sig < -0.005,
    "q<0": sig < 0,
    "opex only": cal["opex"],
    "q<0 & opex": (sig < 0) & cal["opex"],
    "q<-1.0 & opex": (sig < -0.01) & cal["opex"],
    "q<-1.0 & (opex|wed)": (sig < -0.01) & (cal["opex"] | (dow == 2)),
}

print("\nname                    masked  executed   mean    median    t     win%")
for name, mask in cands.items():
    ex = mask & held & (blk == blk)
    a = blk[ex]
    if len(a) < 3:
        print(f"{name:24s} {mask.sum():6d} {len(a):9d}")
        continue
    # P&L of the carve = -(skipped block), since we are flat instead of long
    gain = -a
    t = gain.mean() / (gain.std(ddof=1) / np.sqrt(len(gain)))
    print(f"{name:24s} {mask.sum():6d} {len(a):9d} {gain.mean()*1e4:7.2f} {np.median(gain)*1e4:8.2f} "
          f"{t:6.2f} {np.mean(gain>0)*100:6.1f}")

print("\nby year, q<-1.0 executed events:")
ex = (sig < -0.01) & held & (blk == blk)
df = pd.DataFrame({"date": cal["dates"][ex], "gain": -blk[ex] * 1e4})
df["year"] = df["date"].dt.year
for y, g in df.groupby("year"):
    print(f"  {y}: n={len(g):2d} sum {g['gain'].sum():8.1f}bp mean {g['gain'].mean():8.2f}bp "
          f"win {np.mean(g['gain']>0)*100:5.1f}%")

print("\nby year, opex-only executed events:")
ex2 = cal["opex"] & held & (blk == blk)
df2 = pd.DataFrame({"date": cal["dates"][ex2], "gain": -blk[ex2] * 1e4})
df2["year"] = df2["date"].dt.year
for y, g in df2.groupby("year"):
    print(f"  {y}: n={len(g):2d} sum {g['gain'].sum():8.1f}bp mean {g['gain'].mean():8.2f}bp "
          f"win {np.mean(g['gain']>0)*100:5.1f}%")

print("\nstop events before 15:00 on masked days (why so few execute):")
stops = set(pd.Timestamp(d).date() for d, _ in lib.build_base(ts, opens, closes)[1]["stops"])
mask = sig < -0.01
dts = [d.date() for d in cal["dates"]]
stopped = np.array([d in stops for d in dts])
print(f"  q<-1.0 masked days: {mask.sum()}, of which stop fired that day: {(mask & stopped).sum()}")
print(f"  masked & held: {(mask & held).sum()}   masked & not held: {(mask & ~held).sum()}")
