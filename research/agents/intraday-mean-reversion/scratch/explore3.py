"""Exploration 3: correct conditional edges. Units are fractions."""
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

import engine as E

CACHE = Path(__file__).with_name("panel5.pkl")
ts, o, c, feats = pickle.loads(CACHE.read_bytes())
feats = E.precompute_day_ref(feats, ts, c)
n = len(ts)
qqq, tqqq = feats["qqq"], feats["tqqq"]
bars, date, reg = feats["bars"], feats["date"], feats["regime"]
i0 = E.bt.start_index(ts, E.START10)

# forward TQQQ return: enter next open, exit after k bars (same day only)
def fwd(k):
    r = np.full(n, np.nan)
    e = o[:, 1]
    idx = np.arange(n - k - 1)
    same = date[idx + k + 1] == date[idx + 1]
    r[idx[same]] = e[idx[same] + k + 1] / e[idx[same] + 1] - 1.0
    return r


def to_close():
    r = np.full(n, np.nan)
    e = o[:, 1]
    lastofday = {}
    for i in range(n):
        lastofday[date[i]] = i
    for i in range(n - 1):
        j = lastofday[date[i]]
        if j > i:
            r[i] = c[j, 1] / e[i + 1] - 1.0
    return r


r30 = qqq / pd.Series(qqq).shift(6).to_numpy() - 1.0
r60 = qqq / pd.Series(qqq).shift(12).to_numpy() - 1.0
dopen = pd.Series(qqq).groupby(date).transform("first").to_numpy()
from_open = qqq / dopen - 1.0
from_prev = qqq / feats["qqq_prev_close"] - 1.0

m0 = (np.arange(n) >= i0) & (reg > 0.5)
print("regime-on test bars", int(m0.sum()))

for name, sig, edges in [
    ("r30 (30-min QQQ)", r30, [-0.010, -0.007, -0.005, -0.003, -0.002, -0.001, 0.001, 0.002, 0.003, 0.005, 0.007, 0.010]),
    ("from_open", from_open, [-0.020, -0.015, -0.010, -0.007, -0.005, -0.003, -0.001, 0.001, 0.003, 0.005, 0.010]),
    ("from_prev_close", from_prev, [-0.030, -0.025, -0.020, -0.015, -0.010, -0.005, -0.002, 0.002, 0.005, 0.010]),
]:
    print(f"\n=== {name}: forward TQQQ 30min / hold-to-close, regime-on ===")
    f30, ftc = fwd(6), to_close()
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = m0 & (sig >= lo) & (sig < hi) & np.isfinite(f30) & np.isfinite(ftc)
        if m.sum() > 40:
            print(f"  [{lo*100:+5.2f}%,{hi*100:+5.2f}%) n={m.sum():6d}  fwd30 {np.nanmean(f30[m])*100:+.4f}% "
                  f"win {np.mean(f30[m]>0)*100:4.1f}%  to_close {np.nanmean(ftc[m])*100:+.4f}% "
                  f"win {np.mean(ftc[m]>0)*100:4.1f}%")

# time-of-day split for the biggest dip bucket
print("\n=== 'from_open < -1%' by time of day, hold to close ===")
ftc = to_close()
for b in range(0, 78, 6):
    m = m0 & (from_open < -0.01) & (bars >= b) & (bars < b + 6) & np.isfinite(ftc)
    if m.sum() > 20:
        print(f"  bars {b:2d}-{b+5:2d} n={m.sum():5d} to_close {np.nanmean(ftc[m])*100:+.4f}% win {np.mean(ftc[m]>0)*100:4.1f}%")

# after a -1.5% from-prev-close stop triggers, what happens next 60 min?
print("\n=== first time QQQ <= -1.5% from prev close in a day: fwd 60m / to close ===")
f60 = fwd(12)
first = np.zeros(n, bool)
seen = set()
for i in range(n):
    if reg[i] <= 0.5 or not np.isfinite(from_prev[i]) or from_prev[i] > -0.015:
        continue
    if date[i] in seen:
        continue
    seen.add(date[i])
    first[i] = True
m = first & np.isfinite(f60) & np.isfinite(ftc)
print("  n days", m.sum(), " fwd60", np.nanmean(f60[m]) * 100, "%  to_close", np.nanmean(ftc[m]) * 100, "% win",
      np.mean(ftc[m] > 0) * 100)
for i in np.flatnonzero(m)[:0]:
    pass
# by year
yrs = np.array([d.year for d in date])
for y in range(2017, 2027):
    mm = m & (yrs == y)
    if mm.sum():
        print(f"   {y}: n={mm.sum():3d} fwd60 {np.nanmean(f60[mm])*100:+.3f}% to_close {np.nanmean(ftc[mm])*100:+.3f}%")
