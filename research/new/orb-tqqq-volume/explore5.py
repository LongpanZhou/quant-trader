"""Exploration 5: compact combination scan around the gap-up + stop ORB.

Scratch. Uses the event table from explore4 and the minute path walker to test
whether volume/ATR confirmation plus an ATR stop can lift CAGR toward the bar.
"""
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
to, th, tl, tc = M["to"], M["th"], M["tl"], M["tc"]


def walk(g, stop_mode, stop_val, target=None):
    out = []
    for _, r in g.iterrows():
        k = M["day_of"][r["date"]]
        s, e = M["starts"][k], M["ends"][k]
        i0 = int(r["brk_i"]) + 1
        entry = r["brk_px"]
        if stop_mode == "fixed":
            stop = entry * (1 - stop_val)
        elif stop_mode == "atr":
            stop = entry - stop_val * r["atr14"]
        elif stop_mode == "orlo":
            stop = r["or_lo"]
        else:
            stop = -np.inf
        tgt = entry * (1 + target) if target else np.inf
        px = np.nan
        for i in range(i0, e - 1):
            if tl[i] <= stop:
                px = to[i + 1]
                break
            if th[i] >= tgt:
                px = to[i + 1]
                break
        if not np.isfinite(px):
            px = to[e - 1]
        out.append(px / entry - 1.0)
    return np.array(out)


def rep(x, label):
    x = x[np.isfinite(x)]
    if len(x) < 10:
        print(f"{label:62s} n={len(x):4d} (thin)")
        return
    gm = np.exp(np.mean(np.log1p(x))) - 1
    print(f"{label:62s} n={len(x):4d} ({len(x)/7.984:5.1f}/y) mean={x.mean()*100:6.3f}% "
          f"med={np.median(x)*100:6.3f}% win={np.mean(x>0)*100:5.1f}% gm={gm*100:6.3f}% "
          f"cagr={((1+gm)**(len(x)/7.984)-1)*100:6.2f}%")


base = (b["gap"] > 0)
filt = {
    "+base": base,
    "+rvol .9-1.3": base & b["rvol"].between(.9, 1.3),
    "+or/atr .25-.5": base & b["or_atr"].between(.25, .5),
    "+or/atr .3-.45": base & b["or_atr"].between(.3, .45),
    "+or_ret>0": base & (b["or_ret"] > 0),
    "+or_ret>.3%": base & (b["or_ret"] > .003),
    "+q_confirm": base & b["q_confirm"],
    "+early (<=10:30)": base & (b["brk_min"] <= 630),
    "+rvol & or/atr": base & b["rvol"].between(.9, 1.3) & b["or_atr"].between(.25, .5),
    "+rvol & or_ret>0": base & b["rvol"].between(.9, 1.3) & (b["or_ret"] > 0),
    "+rvol & or/atr & or_ret": base & b["rvol"].between(.9, 1.3) &
        b["or_atr"].between(.25, .5) & (b["or_ret"] > 0),
    "+all incl early": base & b["rvol"].between(.9, 1.3) & b["or_atr"].between(.25, .5) &
        (b["or_ret"] > 0) & (b["brk_min"] <= 630),
}

print("=== fixed 1.5% stop ===")
for name, m in filt.items():
    rep(walk(b[m.fillna(False)], "fixed", .015), name)

print("\n=== ATR stops (0.35 / 0.45 x ATR14) ===")
for name in ("+base", "+rvol .9-1.3", "+or/atr .25-.5", "+rvol & or/atr",
             "+rvol & or/atr & or_ret"):
    m = filt[name].fillna(False)
    for k in (.25, .35, .45, .55):
        rep(walk(b[m], "atr", k), f"{name} stop={k}xATR")

print("\n=== stop x target on the best confirm ===")
m = filt["+rvol & or/atr & or_ret"].fillna(False)
for stop in (.01, .0125, .015, .02):
    for tgt in (None, .03, .05):
        rep(walk(b[m], "fixed", stop, tgt), f"confirm stop={stop} tgt={tgt}")

print("\n=== early-only variants ===")
for name in ("+base", "+rvol .9-1.3", "+or/atr .25-.5", "+rvol & or/atr"):
    m = (filt[name] & (b["brk_min"] <= 630)).fillna(False)
    rep(walk(b[m], "fixed", .015), name + " & early")

print("\n=== per-year for the leading variant ===")
m = filt["+rvol & or/atr"].fillna(False)
g = b[m]
x = walk(g, "fixed", .015)
g = g.assign(ret=x)
for y, gg in g.groupby(g["date"].apply(lambda d: d.year)):
    rep(gg["ret"].to_numpy(), f"  {y}")
