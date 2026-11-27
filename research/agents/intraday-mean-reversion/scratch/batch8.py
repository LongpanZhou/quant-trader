"""Batch 8: what does the stop avoid? Conditional continuation after trigger."""
import numpy as np
import pandas as pd

import engine3 as E

ts, o, c, feats = E.load_cached()
n = len(ts)
qqq, tqqq = feats["qqq"], feats["tqqq"]
date, bars, reg = feats["date"], feats["bars"], feats["regime"]
qpc = feats["qpc"]
i0 = E.bt.start_index(ts, E.START10)
mv = qqq / qpc - 1.0

# last bar index per day and next-day first bar
day_last = {}
first_bar = {}
for i in range(n):
    day_last[date[i]] = i
    first_bar.setdefault(date[i], i)
days = sorted(day_last)

print("=== after first trigger of QQQ <= -X% from prior close (regime on), first trigger of day ===")
for X in (0.015, 0.02, 0.025, 0.03, 0.035, 0.04, 0.05):
    rows = []
    seen = set()
    for i in range(i0, n - 2):
        if reg[i] <= 0.5 or date[i] in seen or not np.isfinite(mv[i]):
            continue
        if mv[i] <= -X:
            seen.add(date[i])
            j = day_last[date[i]]
            if j <= i + 1:
                continue
            to_close = c[j, 1] / o[i + 1, 1] - 1.0
            # next day open->close
            d_idx = days.index(date[i])
            if d_idx + 1 < len(days):
                k0 = first_bar[days[d_idx + 1]]
                k1 = day_last[days[d_idx + 1]]
                nxt = c[k1, 1] / o[k0, 1] - 1.0
                gap = o[k0, 1] / c[j, 1] - 1.0
            else:
                nxt = np.nan
                gap = np.nan
            rows.append((to_close, nxt, gap))
    a = np.array(rows)
    print(f"  X={X*100:.1f}%  n={len(a):3d}  rest-of-day {np.nanmean(a[:,0])*100:+.3f}% "
          f"(win {np.nanmean(a[:,0]>0)*100:4.1f}%)  next-day {np.nanmean(a[:,1])*100:+.3f}%  "
          f"overnight gap {np.nanmean(a[:,2])*100:+.3f}%")

print("\n=== same, but unconditional (all regime-on days): rest of day from first bar ===")
rows = []
for d in days:
    i = first_bar[d]
    j = day_last[d]
    if reg[i] > 0.5 and j > i + 1:
        rows.append(c[j, 1] / o[i + 1, 1] - 1.0)
print(f"  n={len(rows)} mean {np.mean(rows)*100:+.3f}%")
