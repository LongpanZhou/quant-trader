"""Exploration 6: volume-expansion definitions (quiet OR + breakout surge) and OR windows."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

from explore4 import min_arrays  # noqa: E402

df = pd.read_pickle(Path(__file__).resolve().parent / "_events4.pkl")
df = df[df["date"] >= pd.Timestamp("2016-01-04").date()].reset_index(drop=True)
b = df[df["brk_px"].notna()].reset_index(drop=True)
M = min_arrays()
to, tl, th = M["to"], M["tl"], M["th"]


def walk(g, stop_atr=.55, target=None):
    out = []
    for _, r in g.iterrows():
        k = M["day_of"][r["date"]]
        e = M["ends"][k]
        i0 = int(r["brk_i"]) + 1
        entry = r["brk_px"]
        stop = entry - stop_atr * r["atr14"]
        tgt = entry * (1 + target) if target else np.inf
        px = np.nan
        for i in range(i0, e - 1):
            if tl[i] <= stop:
                px = to[i + 1]; break
            if th[i] >= tgt:
                px = to[i + 1]; break
        if not np.isfinite(px):
            px = to[e - 1]
        out.append(px / entry - 1.0)
    return np.array(out)


def rep(x, label):
    x = x[np.isfinite(x)]
    if len(x) < 8:
        print(f"{label:66s} n={len(x):3d} (thin)")
        return
    gm = np.exp(np.mean(np.log1p(x))) - 1
    print(f"{label:66s} n={len(x):3d} ({len(x)/7.984:4.1f}/y) mean={x.mean()*100:6.3f}% "
          f"win={np.mean(x>0)*100:4.1f}% gm={gm*100:6.3f}% "
          f"cagr={((1+gm)**(len(x)/7.984)-1)*100:6.2f}%")


base = (b["gap"] > 0)
print("=== quiet OR + breakout volume surge (2-3x OR bars) ===")
combos = {
    "gap>0": base,
    "rvol<0.9": base & (b["rvol"] < 0.9),
    "rvol<0.9 & brkvol 1.5-3": base & (b["rvol"] < 0.9) & b["brk_vol_ratio"].between(1.5, 3),
    "rvol<0.9 & brkvol>3": base & (b["rvol"] < 0.9) & (b["brk_vol_ratio"] > 3),
    "rvol 0.9-1.3 & brkvol 2-3": base & b["rvol"].between(.9, 1.3) &
        b["brk_vol_ratio"].between(2, 3),
    "rvol>1 & brkvol 2-3": base & (b["rvol"] > 1) & b["brk_vol_ratio"].between(2, 3),
    "brkvol 2-3": base & b["brk_vol_ratio"].between(2, 3),
    "brkvol>2": base & (b["brk_vol_ratio"] > 2),
    "rvol 1.0-1.5": base & b["rvol"].between(1.0, 1.5),
    "rvol 1.0-1.5 & or/atr<.5": base & b["rvol"].between(1.0, 1.5) & (b["or_atr"] < .5),
    "rvol<1 & or/atr<.4": base & (b["rvol"] < 1) & (b["or_atr"] < .4),
    "or/atr<.35": base & (b["or_atr"] < .35),
    "or/atr<.35 & brkvol>2": base & (b["or_atr"] < .35) & (b["brk_vol_ratio"] > 2),
    "or/atr .3-.45 & brkvol 2-3": base & b["or_atr"].between(.3, .45) &
        b["brk_vol_ratio"].between(2, 3),
}
for name, m in combos.items():
    rep(walk(b[m.fillna(False)]), name)

print("\n=== stop plateau on broad gap-up ===")
for k in (.15, .25, .35, .45, .55, .65, .75, .9):
    rep(walk(b[base.fillna(False)], stop_atr=k), f"stop {k}xATR14")

print("\n=== same, rvol 0.9-1.3 ===")
m = (base & b["rvol"].between(.9, 1.3)).fillna(False)
for k in (.25, .35, .45, .55, .65, .75):
    rep(walk(b[m], stop_atr=k), f"stop {k}xATR14")

print("\n=== OR window length (needs a rebuild; event table is 30m) ===")
print("  placeholder: OR15/45/60 are rebuilt in the final strategy grid")
