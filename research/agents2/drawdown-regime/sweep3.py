"""Sweep 3: neighborhood of the conditional-stop rule; DD episode attribution."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ddlib as L


def cond_stop(ts, opens, closes, dctx, dd_thr, stop2, base_stop=0.04,
              scale2=1.0):
    """Winner stop, tighter (and optionally smaller) when QQQ dd <= -dd_thr."""
    first, last = dctx["first"], dctx["last"]
    n = len(ts)
    qqq_close, tqqq_close = closes[:, 0], closes[:, 1]
    hold = np.zeros(n)
    per_day = np.zeros(len(first))
    stops = 0
    for k, (f, l) in enumerate(zip(first, last)):
        if not dctx["reg"][k]:
            continue
        deep = dctx["dd_prev"][k] <= -dd_thr
        stop = stop2 if deep else base_stop
        sc = scale2 if deep else 1.0
        armed = bool(np.isfinite(dctx["arm_ma20"][k])
                     and qqq_close[f] < dctx["arm_ma20"][k] * 1.01)
        base = opens[f, 1]
        on = True
        for i in range(f, l + 1):
            if on and armed and tqqq_close[i] < base * (1 - stop):
                on = False
                stops += 1
            hold[i] = sc if on else 0.0
        per_day[k] = hold[l] if l >= f else 0.0
    w = np.zeros((n, 3))
    w[:, 1] = hold
    w[:, 2] = 1 - hold
    return w, stops, per_day


def episodes(ts, equity, start):
    i = L.bt.start_index(ts, start)
    eq = equity
    # equity is already sliced from start by fastsim
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1
    order = np.argsort(dd)
    tsx = ts[i:]
    out = []
    last_trough = -10**9
    for j in order[:4000]:
        if j - last_trough < 200:
            continue
        p = int(np.argmax(eq[: j + 1]))
        out.append((float(dd[j]), str(tsx[p]), str(tsx[j])))
        last_trough = j
        if len(out) >= 5:
            break
    return out


def main():
    t0 = time.time()
    ts, opens, closes = L.load_panel()
    dctx = L.daily_context(ts, closes)
    print(f"loaded {time.time()-t0:.1f}s")

    print("\n== grid: dd threshold x tighter stop ==")
    results = {}
    for thr in (0.05, 0.06, 0.07, 0.08, 0.09, 0.10, 0.12, 0.15):
        for s2 in (0.015, 0.02, 0.025, 0.03):
            w, nst, pday = cond_stop(ts, opens, closes, dctx, thr, s2)
            o = L.summary(ts, opens, closes, w)
            results[(thr, s2)] = o
            L.fmt(f"dd<={-thr:.0%} stop{s2:.1%} n{nst:3d}", o)
        print()

    print("== same but 25% BIL in the deep state ==")
    for thr in (0.08, 0.10):
        for s2 in (0.02, 0.025):
            w, nst, pday = cond_stop(ts, opens, closes, dctx, thr, s2, scale2=0.75)
            L.fmt(f"dd<={-thr:.0%} stop{s2:.1%} 75%", L.summary(ts, opens, closes, w))

    print("\n== DD episodes of dd<=-8% / stop 2% vs winner ==")
    base_frac = np.ones(dctx["n"])
    wb, _ = L.render(ts, opens, closes, dctx, base_frac)
    ob = L.summary(ts, opens, closes, wb)
    wc, _, _ = cond_stop(ts, opens, closes, dctx, 0.08, 0.02)
    oc = L.summary(ts, opens, closes, wc)
    for label, o in (("winner", ob), ("dd8stop2", oc)):
        for st in (L.START10, L.START5):
            print(f"  {label} {st}:")
            for dd, p, t in episodes(ts, o[st]["result"]["equity"], st):
                print(f"     {dd*100:7.2f}%  {p} -> {t}")

    print("\n== yearly comparison ==")
    print("year   winner        dd8stop2")
    for y in sorted(ob[L.START10]["yearly"]):
        print(f"{y}  {ob[L.START10]['yearly'][y]['strategy']*100:8.2f}  "
              f"{oc[L.START10]['yearly'][y]['strategy']*100:8.2f}")

    print(f"\ndone {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
