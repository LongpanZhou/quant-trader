"""Walk-forward test: choose the carve threshold using only data before year Y,
then apply it to year Y.  This tests the *selection procedure*, not a single
lucky grid point.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/agents2/intraday-seasonality/walkforward.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import lib  # noqa: E402

OUT = Path(__file__).resolve().parent

ts, opens, closes = lib.load_panel()
cal = lib.calendar(ts)
first, last = cal["first"], cal["last"]
w_base, _ = lib.build_base(ts, opens, closes)
i1500 = lib.time_index(ts, first, last, 15, 0)
sig = closes[i1500, 0] / opens[first, 0] - 1.0
years = cal["year"]
dyear = np.array([t.year for t in ts])

THR = [0.0, -0.0025, -0.005, -0.0075, -0.010, -0.0125, -0.015, -0.020]

# yearly return of each variant and of the base
eq = {}
for thr in THR:
    w = lib.carve(w_base, cal, (15, 0), (15, 30), ts, sig < thr)
    eq[thr] = lib.simulate(ts, opens, closes, w, 1.0)["equity"]
eq_base = lib.simulate(ts, opens, closes, w_base, 1.0)["equity"]
last_of_year = {y: int(np.flatnonzero(dyear == y)[-1]) for y in range(2017, 2027)}
first_of_year = {y: int(np.flatnonzero(dyear == y)[0]) for y in range(2017, 2027)}


def ret(e, y):
    a, b = first_of_year[y], last_of_year[y]
    prev = a - 1 if a > 0 else a
    return e[b] / e[prev] - 1.0


print("yearly returns")
print("year  base   " + "  ".join(f"{t*100:6.2f}" for t in THR))
for y in range(2017, 2027):
    print(f"{y} {ret(eq_base,y)*100:7.2f}  " + "  ".join(f"{ret(eq[t],y)*100:6.2f}" for t in THR))

print("\nwalk-forward: threshold picked on all years < Y")
rows = []
wf_ret, base_ret = 1.0, 1.0
for y in range(2019, 2027):
    prior = [yy for yy in range(2017, y)]
    scores = {}
    for t in THR:
        e = 1.0
        for yy in prior:
            e *= 1 + ret(eq[t], yy)
        scores[t] = e ** (1 / len(prior)) - 1
    best = max(scores, key=scores.get)
    r = ret(eq[best], y)
    wf_ret *= 1 + r
    base_ret *= 1 + ret(eq_base, y)
    rows.append({"year": y, "chosen_thr": best, "cagr": r, "base": ret(eq_base, y),
                 "is_score": scores[best]})
    print(f"  {y}: choose {best*100:6.2f}% (prior CAGR {scores[best]*100:6.2f}%) "
          f"-> year {r*100:7.2f}%  base {ret(eq_base,y)*100:7.2f}%")

n = len(rows)
print(f"\nwalk-forward {2019}-2026: variant {(wf_ret**(1/n)-1)*100:.2f}% CAGR  "
      f"base {(base_ret**(1/n)-1)*100:.2f}% CAGR  "
      f"excess {((wf_ret/base_ret)**(1/n)-1)*100:+.2f}pp")

# also report each fixed threshold over the same 2019-2026 block
print("\nfixed thresholds over 2019-2026:")
e0 = 1.0
for yy in range(2019, 2027):
    e0 *= 1 + ret(eq_base, yy)
print(f"  base {(e0**(1/8)-1)*100:7.2f}%")
for t in THR:
    e = 1.0
    for yy in range(2019, 2027):
        e *= 1 + ret(eq[t], yy)
    print(f"  thr {t*100:6.2f}%  {(e**(1/8)-1)*100:7.2f}%")
