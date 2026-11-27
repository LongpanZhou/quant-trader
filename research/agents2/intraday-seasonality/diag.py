"""Diagnose the P&L of a carve directly: compare daily log-equity differences."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import lib  # noqa: E402

ts, opens, closes = lib.load_panel()
cal = lib.calendar(ts)
first, last = cal["first"], cal["last"]
w_base, _ = lib.build_base(ts, opens, closes)
dates = cal["dates"]

r0 = lib.simulate(ts, opens, closes, w_base, 1.0)
i1530 = lib.time_index(ts, first, last, 15, 30)
i1559 = lib.time_index(ts, first, last, 15, 59)
i1500 = lib.time_index(ts, first, last, 15, 0)

d = np.array([t.date() for t in ts])
dayid = np.repeat(np.arange(len(first)), np.diff(np.r_[first, len(ts)]))
eq_day = r0["equity"][last]

for name, mask in (("wed", cal["dow"] == 2), ("opex", cal["opex"]),
                   ("qqq<-1", None)):
    if mask is None:
        q_open = opens[first, 0]
        q_c1530 = closes[i1530, 0]
        mask = (q_c1530 / q_open - 1.0) < -0.01
    w = lib.carve(w_base, cal, (15, 30), (15, 59), ts, mask)
    r1 = lib.simulate(ts, opens, closes, w, 1.0)
    eq1 = r1["equity"][last]
    # same-day difference and next-day difference (log)
    dlog = np.log(eq1 / eq_day)
    # attribute to the masked day and to the following day
    dm = dlog * mask
    dn = np.r_[dlog[1:] * mask[:-1], 0.0]
    print(f"\n{name}: n={mask.sum()}  sum log-diff on day={dm.sum()*100:8.2f}%  "
          f"on next day={dn.sum()*100:8.2f}%  total={dlog.sum()*100:8.2f}%")
    # per-unit: mean bp of the skipped block measured open-to-open
    a = i1530[mask]
    b = i1559[mask]
    blk = closes[b, 1] / opens[a, 1] - 1.0
    print(f"  skipped block (15:31 open -> 15:59 open) mean {blk.mean()*1e4:7.2f}bp  "
          f"sd {blk.std()*1e4:6.1f}bp  geo-mean {np.mean(np.log1p(blk))*1e4:7.2f}bp")
    base_blk = closes[b, 1] / closes[a, 1] - 1.0
    print(f"  same block close-to-close           mean {base_blk.mean()*1e4:7.2f}bp  "
          f"sd {base_blk.std()*1e4:6.1f}bp")

# where does the Wednesday loss come from?
w = lib.carve(w_base, cal, (15, 30), (15, 59), ts, cal["dow"] == 2)
r1 = lib.simulate(ts, opens, closes, w, 1.0)
dl = np.log(r1["equity"][last] / eq_day)
tab = pd.DataFrame({"date": pd.to_datetime(list(dates)), "dlog": dl * 1e4,
                    "skip_ret": (closes[i1559, 1] / opens[i1530, 1] - 1) * 1e4})
sub = tab[cal["dow"] == 2].nsmallest(10, "dlog")
print("\nworst Wednesday equity-diff days:")
print(sub.to_string(index=False, float_format=lambda v: f"{v:9.2f}"))
sub = tab[cal["dow"] == 2].nlargest(10, "dlog")
print("\nbest Wednesday equity-diff days:")
print(sub.to_string(index=False, float_format=lambda v: f"{v:9.2f}"))
