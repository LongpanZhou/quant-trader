"""Exit-structure tests: time of exit, trailing stop, breakeven, re-entry."""
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
op = bars["open"].to_numpy()
cl = bars["close"].to_numpy()
tod = np.asarray(ts.hour * 60 + ts.minute)


def entries():
    out = []
    for k in range(len(st["starts"])):
        s, e = st["starts"][k], st["ends"][k]
        if not np.isfinite(st["or_hi"][k]) or not np.isfinite(st["atr14"][k]):
            continue
        if not (st["gap"][k] > 0):
            continue
        rv = st["rvol"][k]
        if not np.isfinite(rv) or not (0.7 <= rv <= 1.6):
            continue
        if (st["or_hi"][k] - st["or_lo"][k]) > 0.6 * st["atr14"][k]:
            continue
        j0 = int(np.searchsorted(tod[s:e], 600))
        for i in range(s + j0, e - 2):
            if tod[i] > tod[e - 1] - 60:
                break
            if cl[i] > st["or_hi"][k]:
                out.append((k, i))
                break
    return out


E = entries()
print(f"entries {len(E)}")


def sim(k, entry_i, stop_atr=.55, trail_atr=None, be_atr=None, exit_min=959,
        reentry=False):
    s, e = st["starts"][k], st["ends"][k]
    entry = op[entry_i + 1]
    atr = st["atr14"][k]
    stop = entry - stop_atr * atr
    high = entry
    n_trades = 1
    for j in range(entry_i + 1, e - 1):
        if tod[j] >= exit_min:
            return op[min(j + 1, e - 1)] / entry - 1.0, "time", n_trades
        if lo[j] <= stop:
            # stop hit; optional re-entry later on a new ORH break
            r1 = op[j + 1] / entry - 1.0
            if reentry and n_trades < 2:
                for r in range(j + 2, e - 2):
                    if tod[r] > tod[e - 1] - 60:
                        break
                    if cl[r] > st["or_hi"][k]:
                        entry2 = op[r + 1]
                        stop2 = entry2 - stop_atr * atr
                        for q in range(r + 1, e - 1):
                            if tod[q] >= exit_min:
                                r2 = op[min(q + 1, e - 1)] / entry2 - 1.0
                                return (1 + r1) * (1 + r2) - 1.0, "time2", 2
                            if lo[q] <= stop2:
                                r2 = op[q + 1] / entry2 - 1.0
                                return (1 + r1) * (1 + r2) - 1.0, "stop2", 2
                        r2 = op[e - 1] / entry2 - 1.0
                        return (1 + r1) * (1 + r2) - 1.0, "eod2", 2
            return r1, "stop", n_trades
        high = max(high, hi[j])
        if be_atr and high >= entry + be_atr * atr:
            stop = max(stop, entry)
        if trail_atr:
            stop = max(stop, high - trail_atr * atr)
    return op[e - 1] / entry - 1.0, "eod", n_trades


def test(label, **kw):
    rets, kinds = [], []
    for k, i in E:
        r, kind, nt = sim(k, i, **kw)
        rets.append(r)
        kinds.append(kind)
    rets = np.array(rets)
    cg = np.prod(1 + rets) ** (1 / 7.984) - 1
    print(f"{label:52s} mean {rets.mean()*100:6.3f}%  win {np.mean(rets>0)*100:4.1f}%  "
          f"cagr {cg*100:6.2f}%  stop {kinds.count('stop')+kinds.count('stop2'):3d}  "
          f"eod {kinds.count('eod')+kinds.count('eod2'):3d}")


print("\n=== exit time ===")
for m, lab in ((959, "15:59"), (930, "15:30"), (900, "15:00"), (840, "14:00"), (780, "13:00")):
    test(f"time exit {lab}", exit_min=m)

print("\n=== stops ===")
for k in (.35, .55, .75, 1.0):
    test(f"fixed stop {k}ATR", stop_atr=k)
for k in (.55, .75, 1.0, 1.5):
    test(f"trailing stop {k}ATR (plus 0.55 disaster)", trail_atr=k)

print("\n=== breakeven ===")
for k in (.5, 1.0, 1.5):
    test(f"breakeven after +{k}ATR", be_atr=k)

print("\n=== re-entry after stop (max 2) ===")
test("reentry, 0.55ATR stop", reentry=True)

print("\n=== combinations ===")
test("trail 0.75 + exit 15:30", trail_atr=.75, exit_min=930)
test("trail 0.75 + exit 15:00", trail_atr=.75, exit_min=900)
test("be 1.0 + exit 15:30", be_atr=1.0, exit_min=930)
test("reentry + exit 15:30", reentry=True, exit_min=930)
