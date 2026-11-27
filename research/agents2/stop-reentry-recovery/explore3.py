"""Which re-entry conditions, if any, have positive forward returns after a stop?"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import srlib as S  # noqa: E402

A = S.arrays()
ts, first, last = A["ts"], A["first"], A["last"]
o, c, h, l, v = A["o"], A["c"], A["h"], A["l"], A["v"]
reg, ma20 = S.regime(ts, c[:, 0], first, last)
vwap_t = S.session_vwap(h, l, c, v, first, last)

# QQQ session VWAP / EMAs
hq = h.copy(); lq = l.copy(); cq = c.copy()
vwap_q = np.empty(len(c))
for f, z in zip(first, last):
    tp = (h[f:z + 1, 0] + l[f:z + 1, 0] + c[f:z + 1, 0]) / 3
    pv = np.cumsum(tp * v[f:z + 1, 0])
    cv = np.cumsum(v[f:z + 1, 0])
    vwap_q[f:z + 1] = np.where(cv > 0, pv / np.maximum(cv, 1e-12), tp)
ema5_q = S.session_ema(c, first, last, 5, 9, col=0)
ema5_t = S.session_ema(c, first, last, 5, 9, col=1)

rows = []
for k, (f, z) in enumerate(zip(first, last)):
    if not reg[f] or k + 1 >= len(first):
        continue
    if not (np.isfinite(ma20[f]) and c[f, 0] < ma20[f] * (1 + S.ARM_BUF)):
        continue
    base = o[f, 1]
    for i in range(f, z + 1):
        if c[i, 1] < base * (1 - S.STOP):
            depth = c[i, 1] / base - 1
            nf = first[k + 1]
            rec = dict(date=A["dates"][f], k=k, i=i, z=z, f=f, minute=i - f,
                       depth=depth, next_open=o[nf, 1], day_close=c[z, 1],
                       close_ret=c[z, 1] / base - 1)
            # simple conditions known at each bar; find first true bar after stop
            conds = {
                "t_vwap": lambda j: np.isfinite(vwap_t[j]) and c[j, 1] > vwap_t[j],
                "q_vwap": lambda j: np.isfinite(vwap_q[j]) and c[j, 0] > vwap_q[j],
                "both_vwap": lambda j: (np.isfinite(vwap_t[j]) and c[j, 1] > vwap_t[j]
                                        and np.isfinite(vwap_q[j]) and c[j, 0] > vwap_q[j]),
                "t_e5": lambda j: np.isfinite(ema5_t[j]) and c[j, 1] > ema5_t[j],
                "q_e5": lambda j: np.isfinite(ema5_q[j]) and c[j, 0] > ema5_q[j],
                "t_vwap_q_ma": lambda j: (np.isfinite(vwap_t[j]) and c[j, 1] > vwap_t[j]
                                          and np.isfinite(ma20[f]) and c[j, 0] > ma20[f]),
                "t_vwap_q_up": lambda j: (np.isfinite(vwap_t[j]) and c[j, 1] > vwap_t[j]
                                          and c[j, 0] > o[f, 0]),
            }
            for name, fn in conds.items():
                hit, conf = -1, 0
                for j in range(i + 1, z):
                    if fn(j):
                        conf += 1
                    else:
                        conf = 0
                    if conf >= 3:
                        hit = j
                        break
                rec[name] = hit
            rows.append(rec)
            break

ev = pd.DataFrame(rows)
print("n", len(ev))
print("depth buckets:", pd.cut(ev["depth"], [-0.20, -0.06, -0.05, -0.045, -0.04]).value_counts().to_dict())
print("minute buckets:", pd.cut(ev["minute"], [-1, 60, 120, 240, 390]).value_counts().to_dict())


def fwd(name, hit_col, delay=1):
    """Return from fill at open[hit+delay] to close and next open."""
    out = []
    for _, r in ev.iterrows():
        j = int(r[hit_col])
        if j < 0:
            continue
        z = int(r["z"])
        fill_i = j + delay
        if fill_i > z:
            continue
        fill = o[fill_i, 1]
        # tight 2% stop, close-based, exit next open
        ex, why = o[z, 1], "close"
        for m in range(fill_i, z + 1):
            if c[m, 1] < fill * 0.98:
                ex, why = o[min(m + 1, z), 1], "stop"
                break
        out.append(dict(to_close=c[z, 1] / fill - 1, to_next=r["next_open"] / fill - 1,
                        tight2=ex / fill - 1, why=why, depth=r["depth"], minute=r["minute"],
                        date=r["date"]))
    t = pd.DataFrame(out)
    if len(t) == 0:
        return
    print(f"  {name:12s} n={len(t):3d}  to_close {t['to_close'].mean()*100:+7.3f}% "
          f"(med {t['to_close'].median()*100:+6.3f})  to_next {t['to_next'].mean()*100:+7.3f}% "
          f"(med {t['to_next'].median()*100:+6.3f})  tight2 {t['tight2'].mean()*100:+7.3f}% "
          f"({(t['why']=='stop').mean()*100:.0f}% stopped)")


print("\nAll conditions, 3-bar confirm, fill next open:")
for name in ("t_vwap", "q_vwap", "both_vwap", "t_e5", "q_e5", "t_vwap_q_ma", "t_vwap_q_up"):
    fwd(name, name)

print("\nBy stop depth (all stop days, hold from next open to close):")
for lab, sub in ev.groupby(pd.cut(ev["depth"], [-0.30, -0.06, -0.05, -0.045, -0.04]), observed=True):
    print(f"  depth {str(lab):20s} n={len(sub):3d} next_open->close "
          f"{np.mean([c[int(r['z']),1]/o[int(r['i'])+1,1]-1 for _,r in sub.iterrows()])*100:+.3f}%")

print("\nBy stop minute (all stop days, next_open->close):")
for lab, sub in ev.groupby(pd.cut(ev["minute"], [-1, 60, 120, 240, 390]), observed=True):
    vals = []
    for _, r in sub.iterrows():
        j = int(r["i"]) + 1
        if j <= int(r["z"]):
            vals.append(c[int(r["z"]), 1] / o[j, 1] - 1)
    print(f"  minute {str(lab):12s} n={len(sub):3d} mean {np.mean(vals)*100:+.3f}%")

print("\nVWAP reclaim conditional on depth:")
for name in ("t_vwap", "both_vwap"):
    for lab, sub in ev.groupby(pd.cut(ev["depth"], [-0.30, -0.06, -0.05, -0.045, -0.04]), observed=True):
        hits = sub[sub[name] >= 0]
        if len(hits) < 5:
            continue
        vals = []
        for _, r in hits.iterrows():
            j = int(r[name]) + 1
            if j <= int(r["z"]):
                vals.append(c[int(r["z"]), 1] / o[j, 1] - 1)
        print(f"  {name:10s} depth {str(lab):20s} n={len(hits):3d} mean {np.mean(vals)*100:+.3f}%")

ev.to_csv(HERE / "reclaim_events.csv", index=False)
print("\nwrote reclaim_events.csv")
