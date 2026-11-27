import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ddlib as L

ts, opens, closes = L.load_panel()
d = L.daily_context(ts, closes)
dd, reg, dates = d["dd_prev"], d["reg"], d["dates"]


def window(a, b):
    i0 = int(np.searchsorted(dates, a))
    i1 = int(np.searchsorted(dates, b))
    m = reg[i0:i1 + 1]
    x = dd[i0:i1 + 1]
    print(f"{a}..{b}: sessions {i1-i0+1}, regime ON {m.sum()} ({m.mean()*100:.0f}%), "
          f"max |dd| while ON {(-x[m]).max()*100:.2f}%, "
          f"ON days dd<=-5% {int(((x<=-0.05)&m).sum())}, "
          f"<=-8% {int(((x<=-0.08)&m).sum())}, <=-10% {int(((x<=-0.10)&m).sum())}")


import datetime as dt
window(dt.date(2018, 3, 13), dt.date(2019, 6, 6))
window(dt.date(2026, 6, 22), dt.date(2026, 7, 31))

print("\nON sessions by dd bucket and year:")
on = reg & (dd <= -0.08)
for y in range(2016, 2027):
    m = on & np.array([x.year == y for x in dates])
    if m.sum():
        print(f"  {y}: {int(m.sum())}")

print("\nall sessions with dd<=-10%: ON vs OFF")
for thr in (0.05, 0.08, 0.10, 0.15):
    tot = (dd <= -thr).sum()
    onn = ((dd <= -thr) & reg).sum()
    print(f"  dd<=-{thr:.0%}: total {tot}, ON {onn} ({onn/tot*100:.0f}%), OFF {tot-onn}")

print("\nuw distribution (sessions since 52w high), regime ON:")
for n in (60, 120, 180, 250):
    print(f"  uw>={n}: {int((d['uw']>=n).sum())} total, {int(((d['uw']>=n)&reg).sum())} ON")
