"""Hindsight timing decomposition on the selected days (NOT a strategy).

The 572 days are selected with filters that are only known at 10:00 (opening
volume, opening-range width). Entering those same days at 09:31 or 10:00 is
therefore look-ahead; this file only measures how much of the day's move the
10:00+ breakout entry gives up. It is not used for any result.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "research"))
sys.path.insert(0, str(HERE))
import strategy as S  # noqa: E402

ts, o, c, bars = S.load_dev()
st = S.session_tables(ts, bars, 30)
hi = bars["high"].to_numpy()
lo = bars["low"].to_numpy()
op = bars["open"].to_numpy()
tod = np.asarray(ts.hour * 60 + ts.minute)
log = []
S._build(ts, o, c, S.CFG, bars, log=log)
tr = pd.DataFrame(log)
day_of = {d: k for k, d in enumerate(st["date"])}


def sim(k, entry_i, stop_atr=.55):
    s, e = st["starts"][k], st["ends"][k]
    entry = op[entry_i]
    stop = entry - stop_atr * st["atr14"][k]
    seg = lo[entry_i:e - 1]
    hit = np.flatnonzero(seg <= stop)
    if len(hit):
        return op[entry_i + int(hit[0]) + 1] / entry - 1.0
    return op[e - 1] / entry - 1.0


rows = []
for _, r in tr.iterrows():
    k = day_of[r["date"]]
    s, e = st["starts"][k], st["ends"][k]
    i931 = s + 1
    i1000 = s + int(np.searchsorted(tod[s:e], 600))
    rets = dict(open931=sim(k, i931), ten=sim(k, i1000), orb=r["ret"])
    rows.append(rets)
z = pd.DataFrame(rows)


def rep(x, label):
    x = x.to_numpy()
    gm = np.exp(np.mean(np.log1p(x))) - 1
    print(f"{label:28s} mean {x.mean()*100:6.3f}%  win {np.mean(x>0)*100:5.1f}%  "
          f"cagr(joint) {((1+gm)**(len(x)/7.984)-1)*100:6.2f}%")


print("Hindsight timing on the same 572 selected days (look-ahead; diagnostic only)")
rep(z["open931"], "entry 09:31")
rep(z["ten"], "entry 10:00")
rep(z["orb"], "entry at ORB (actual)")
print("\nmean give-up 09:31 -> ORB: %.3f pp per trade" %
      ((z["open931"].mean() - z["orb"].mean()) * 100))
