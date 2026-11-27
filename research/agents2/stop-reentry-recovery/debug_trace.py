"""Trace the combo around a few stop events to verify no look-ahead / correct fills."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import srlib as S  # noqa: E402

A = S.arrays()
ts, dates, first, last = A["ts"], A["dates"], A["first"], A["last"]
o, c = A["o"], A["c"]
reg, ma20 = S.regime(ts, c[:, 0], first, last)
vwap = S.session_vwap(A["h"], A["l"], A["c"], A["v"], first, last)
ema5 = S.session_ema(c, first, last, 5, 9)
ema5b = S.session_ema(c, first, last, 5, 20)
ema15 = S.session_ema(c, first, last, 15, 9)

wb, db = S.make_weights(A, reg, ma20, vwap, ema5, ema5b, ema15, mode="base")
wc, dc = S.make_weights(A, reg, ma20, vwap, ema5, ema5b, ema15, mode="nextday",
                        block_next_on_weak_close=True, block_frac=0.5, next_day_tight=0.02)
print(f"base stops {len(db['stops'])}  combo stops {len(dc['stops'])}  tight days {dc['tight_days']} "
      f"tight stops {dc['tight_stops']}  blocked {dc['blocked_days']}")

for day in ("2018-02-02", "2018-02-05", "2018-02-06", "2020-03-11", "2020-03-12",
            "2025-02-24", "2025-02-25", "2025-11-13", "2025-11-14"):
    idx = np.flatnonzero(dates.astype(str) == day)
    if not len(idx):
        continue
    f, z = idx[0], idx[-1]
    print(f"\n{day}  open {o[f,1]:8.3f} close {c[z,1]:8.3f} dayret {c[z,1]/o[f,1]-1:+.2%}")
    prev = None
    for i in range(f, z + 1):
        v = (round(wb[i, 1], 2), round(wc[i, 1], 2))
        if v != prev:
            print(f"   {str(ts[i].time())[:5]}  TQQQ {c[i,1]:8.3f}  base_w {v[0]:.2f}  combo_w {v[1]:.2f}")
            prev = v
