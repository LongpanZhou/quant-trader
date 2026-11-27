"""Ablations: no-ORB controls, failed-breakdown reclaim, stop structure.

All run through the same harness (`bt.run`, next-open fills, band 0.02) on the
development window only. Scratch/report support; the headline is strategy.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "research"))
sys.path.insert(0, str(HERE))
import bt  # noqa: E402
import strategy as S  # noqa: E402

ts, o, c, bars = S.load_dev()
st = S.session_tables(ts, bars, 30)
hi = bars["high"].to_numpy()
lo = bars["low"].to_numpy()
cl = bars["close"].to_numpy()
op = bars["open"].to_numpy()
tod = np.asarray(ts.hour * 60 + ts.minute)


def finish(w, slip=1.0):
    res = bt.run(ts, o, c, w, S.DEV_START, band=0.02, slippage_bps=slip)
    s = bt.stats(res, S.BARS_1M)
    return s


def drive_weights(stop_atr=0.55, entry_min=600):
    """No ORB: buy at `entry_min` on gap-up days, ATR stop, EOD flat."""
    w = np.zeros((len(ts), 3))
    for k in range(len(st["starts"])):
        s, e = st["starts"][k], st["ends"][k]
        if not np.isfinite(st["atr14"][k]) or not (st["gap"][k] > 0):
            continue
        i0 = int(np.searchsorted(tod[s:e], entry_min))
        if i0 < 1 or s + i0 >= e - 2:
            continue
        entry_i = s + i0 - 1          # weight set at prior close, fill at entry_min open
        entry_px = op[s + i0]
        stop = entry_px - stop_atr * st["atr14"][k] if stop_atr else -np.inf
        w[entry_i, 1] = 1.0
        exited = False
        for j in range(s + i0, e - 2):
            if lo[j] <= stop:
                w[j, 1] = 0.0
                exited = True
                break
            w[j, 1] = 1.0
        if not exited:
            w[e - 2, 1] = 0.0
    return w


def orb_nostop():
    return S._build(ts, o, c, dict(S.CFG, stop_atr=0.0), bars)[0]


def orb_fixed(stop=0.015):
    w = np.zeros((len(ts), 3))
    for k in range(len(st["starts"])):
        s, e = st["starts"][k], st["ends"][k]
        if not np.isfinite(st["or_hi"][k]):
            continue
        i0 = int(np.searchsorted(tod[s:e], 600))
        brk = -1
        for i in range(s + i0, e - 2):
            if cl[i] > st["or_hi"][k]:
                brk = i
                break
        if brk < 0:
            continue
        entry = op[brk + 1]
        stp = entry * (1 - stop)
        w[brk, 1] = 1.0
        exited = False
        for j in range(brk + 1, e - 2):
            if lo[j] <= stp:
                w[j, 1] = 0.0
                exited = True
                break
            w[j, 1] = 1.0
        if not exited:
            w[e - 2, 1] = 0.0
    return w


def reclaim_weights(gap_filter=False, vol_filter=False, stop_mode="sweep",
                    target="orh"):
    """Failed OR-low breakdown then reclaim; long-only intraday."""
    w = np.zeros((len(ts), 3))
    for k in range(len(st["starts"])):
        s, e = st["starts"][k], st["ends"][k]
        if not np.isfinite(st["or_lo"][k]):
            continue
        if gap_filter and not (st["gap"][k] < 0):
            continue
        if vol_filter:
            rv = st["rvol"][k]
            if not np.isfinite(rv) or not (1.0 <= rv <= 1.6):
                continue
        orl, orh = st["or_lo"][k], st["or_hi"][k]
        i0 = int(np.searchsorted(tod[s:e], 600))
        sweep = np.inf
        rec = -1
        for i in range(s + i0, e - 2):
            if lo[i] < orl * 0.9995:
                sweep = min(sweep, lo[i])
                if cl[i] > orl * 1.0005:
                    rec = i
                    break
        if rec < 0:
            continue
        entry = op[rec + 1]
        stop = sweep if stop_mode == "sweep" else entry * 0.985
        tgt = orh if target == "orh" else np.inf
        w[rec, 1] = 1.0
        exited = False
        for j in range(rec + 1, e - 2):
            if lo[j] <= stop:
                w[j, 1] = 0.0
                exited = True
                break
            if hi[j] >= tgt:
                w[j, 1] = 0.0
                exited = True
                break
            w[j, 1] = 1.0
        if not exited:
            w[e - 2, 1] = 0.0
    return w


def show(label, w, slip=1.0):
    s = finish(w, slip)
    print(f"{label:52s} CAGR {s['cagr']*100:6.2f}%  DD {s['max_drawdown']*100:6.2f}%  "
          f"Sharpe {s['sharpe']:5.2f}  fills {s['fills']:5d}  exp {s['exposure']*100:5.1f}%")


print("=== core ===")
show("ORB core (strategy.py)", S.build_weights(ts, o, c))

print("\n=== no-ORB controls ===")
show("gap-up drive at 10:00, 0.55ATR stop", drive_weights(0.55, 600))
show("gap-up drive at 10:30, 0.55ATR stop", drive_weights(0.55, 630))
show("gap-up drive at 10:00, no stop", drive_weights(0.0, 600))

print("\n=== stop structure ===")
show("ORB no stop", orb_nostop())
show("ORB fixed 1.5% stop", orb_fixed(0.015))
show("ORB fixed 2.0% stop", orb_fixed(0.020))

print("\n=== failed-breakdown reclaim (mandate asks to consider) ===")
show("reclaim, no filters, sweep stop, ORH target", reclaim_weights(False, False))
show("reclaim, gap<0, sweep stop, ORH target", reclaim_weights(True, False))
show("reclaim, gap<0 & rvol 1.0-1.6", reclaim_weights(True, True))
show("reclaim, no filters, 1.5% stop, ORH target", reclaim_weights(False, False, "fixed"))
show("reclaim, no filters, sweep stop, EOD", reclaim_weights(False, False, "sweep", "eod"))

print("\n=== cost sensitivity of core (cash flat) ===")
core = S.build_weights(ts, o, c)
for slip in (1.0, 5.0, 10.0):
    show(f"core {slip:.0f}bp", core, slip)

print("\n=== BIL-flat core (extra fills) ===")
w_bil = S._build(ts, o, c, dict(S.CFG, flat="BIL"), bars)[0]
for slip in (1.0, 5.0, 10.0):
    show(f"BIL-flat {slip:.0f}bp", w_bil, slip)
