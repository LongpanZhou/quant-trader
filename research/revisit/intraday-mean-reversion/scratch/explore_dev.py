"""Dev-only exploration: standalone capitulation -> next-session re-entry edge.

No 165-day regime. Period: 2016-01-04 .. 2023-12-29 only (holdout never loaded).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

START, END = "2016-01-04", "2023-12-29"
ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "5min")
n = len(ts)
date = bt.session_dates(ts)
first = np.flatnonzero(np.r_[True, date[1:] != date[:-1]])
last = np.r_[first[1:] - 1, n - 1]
ndays = len(first)
print("dev bars", n, "sessions", ndays, ts[0], ts[-1])

qqq, tqqq = c[:, 0], c[:, 1]
prev_close = np.full(n, np.nan)
prev_close[first[1:]] = qqq[last[:-1]]
# forward fill prev_close within a day
for k in range(1, ndays):
    a, b = first[k], last[k] + 1
    prev_close[a:b] = qqq[last[k - 1]]

ddown = qqq / prev_close - 1.0
# session min drawdown (bar index of the minimum)
day_min = np.array([ddown[first[k]:last[k] + 1].min() for k in range(ndays)])
day_argmin = np.array([first[k] + int(np.argmin(ddown[first[k]:last[k] + 1])) for k in range(ndays)])
day_close_dd = np.array([ddown[last[k]] for k in range(ndays)])

# session opens (next open = the first bar of the next session)
sopen = np.array([o[first[k], 1] for k in range(ndays)])
sclose = np.array([c[last[k], 1] for k in range(ndays)])
qopen = np.array([o[first[k], 0] for k in range(ndays)])
qclose = np.array([c[last[k], 0] for k in range(ndays)])

def fwd_sessions(k0, nhold):
    """TQQQ return from the open of session k0 to the close of session k0+nhold-1."""
    if k0 + nhold - 1 >= ndays:
        return np.nan
    return sclose[k0 + nhold - 1] / sopen[k0] - 1.0


print("\n=== unconditional next-session TQQQ open->close ===")
r1 = np.array([fwd_sessions(k + 1, 1) for k in range(ndays - 1)])
print("all days n=%d mean %+.4f%% median %+.4f%% win %.1f%% sd %.3f%%" % (
    len(r1), np.nanmean(r1) * 100, np.nanmedian(r1) * 100, np.nanmean(r1 > 0) * 100, np.nanstd(r1) * 100))

print("\n=== event: session min QQQ drawdown <= -X ; buy TQQQ next open ===")
for X in (0.015, 0.02, 0.025, 0.03, 0.035, 0.04, 0.05, 0.06):
    ev = np.flatnonzero(day_min <= -X)
    ev = ev[ev + 6 < ndays]  # need forward room
    if len(ev) < 5:
        continue
    hold = {}
    for h in (1, 2, 3, 5):
        rr = np.array([fwd_sessions(k + 1, h) for k in ev])
        hold[h] = (np.nanmean(rr), np.nanmedian(rr), np.nanmean(rr > 0), np.nanstd(rr) / np.sqrt(len(rr)))
    # trigger -> close of trigger day (what a stop would skip)
    trig = np.array([c[last[k], 1] / o[day_argmin[k] + 1, 1] - 1.0 for k in ev])
    # overnight gap trigger-close -> next open
    gap = np.array([sopen[k + 1] / sclose[k] - 1.0 for k in ev])
    line = f"X={X*100:4.1f}% n={len(ev):3d} | rest_trig {np.mean(trig)*100:+.2f}% gap {np.mean(gap)*100:+.2f}% |"
    for h in (1, 2, 3, 5):
        m, med, w, se = hold[h]
        line += f" h{h}: {m*100:+.3f}% (med {med*100:+.2f}, w{w*100:.0f})"
    print(line)

print("\n=== X=3% events by sub-period, 1-session hold ===")
ev = np.flatnonzero(day_min <= -0.03)
ev = ev[ev + 6 < ndays]
yrs = np.array([date[first[k]].year for k in range(ndays)])
for lo, hi in ((2016, 2019), (2020, 2021), (2022, 2023)):
    sel = np.array([lo <= yrs[k] <= hi for k in ev])
    rr = np.array([fwd_sessions(k + 1, 1) for k in ev[sel]])
    print(f"  {lo}-{hi}: n={sel.sum():3d} mean {np.nanmean(rr)*100:+.3f}% median {np.nanmedian(rr)*100:+.3f}% win {np.nanmean(rr>0)*100:.0f}%")

print("\n=== X=3% events by year, 1-session hold ===")
for y in range(2016, 2024):
    sel = np.array([yrs[k] == y for k in ev])
    if sel.sum() == 0:
        continue
    rr = np.array([fwd_sessions(k + 1, 1) for k in ev[sel]])
    print(f"  {y}: n={sel.sum():3d} mean {np.nanmean(rr)*100:+.3f}% win {np.nanmean(rr>0)*100:.0f}%")

print("\n=== cluster count: distinct 5-day clusters for X=3% ===")
clusters = []
for k in ev:
    if not clusters or k - clusters[-1][-1] > 5:
        clusters.append([k])
    else:
        clusters[-1].append(k)
print("events", len(ev), "clusters(<=5d apart)", len(clusters), "sizes", [len(x) for x in clusters])
