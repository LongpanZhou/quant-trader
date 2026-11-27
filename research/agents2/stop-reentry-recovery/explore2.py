"""Conditional forward returns on stop days, measured from investable prices."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import srlib as S  # noqa: E402

A = S.arrays()
ts, dates, first, last = A["ts"], A["dates"], A["first"], A["last"]
o, c = A["o"], A["c"]
reg, ma20 = S.regime(ts, c[:, 0], first, last)
vwap = S.session_vwap(A["h"], A["l"], A["c"], A["v"], first, last)
ema5 = S.session_ema(c, first, last, 5, 9)
ema15 = S.session_ema(c, first, last, 15, 9)

rows = []
for k, (f, z) in enumerate(zip(first, last)):
    if not reg[f]:
        continue
    if not (np.isfinite(ma20[f]) and c[f, 0] < ma20[f] * (1 + S.ARM_BUF)):
        continue
    base = o[f, 1]
    for i in range(f, z + 1):
        if c[i, 1] < base * (1 - S.STOP):
            nxt_f = first[k + 1] if k + 1 < len(first) else None
            if nxt_f is None:
                break
            rec = dict(date=dates[f], k=k, i=i, minute=i - f,
                       stop_close=c[i, 1], day_open=base, day_close=c[z, 1],
                       next_open=o[nxt_f, 1], next_close=c[last[k + 1], 1])
            # investable overnight from the 15:59 open (decision at 15:58 close)
            rec["night"] = o[z, 1] / c[z - 1, 1] - 1   # 15:58 close -> 15:59 open, negligible
            rec["night_true"] = rec["next_open"] / o[z, 1] - 1
            rec["nextday_oc"] = rec["next_close"] / rec["next_open"] - 1
            rec["close_above_stoplevel"] = c[z, 1] > base * (1 - S.STOP)
            rec["close_above_vwap"] = c[z, 1] > vwap[z]
            rec["close_above_open"] = c[z, 1] > base
            rec["close_gt_vwap_gt_stop"] = rec["close_above_vwap"] and rec["close_above_stoplevel"]
            rows.append(rec)
            break
ev = pd.DataFrame(rows)
print("n =", len(ev))
for flag in ("close_above_stoplevel", "close_above_vwap", "close_above_open", "close_gt_vwap_gt_stop"):
    a = ev[ev[flag]]
    b = ev[~ev[flag]]
    print(f"\n{flag}: true n={len(a)}")
    for col in ("night_true", "nextday_oc"):
        if len(a):
            print(f"  {col:12s} true mean {a[col].mean()*100:+7.3f}% median {a[col].median()*100:+7.3f}% | "
                  f"false mean {b[col].mean()*100:+7.3f}% median {b[col].median()*100:+7.3f}%")
print("\nunconditional:")
for col in ("night_true", "nextday_oc"):
    print(f"  {col:12s} mean {ev[col].mean()*100:+7.3f}% median {ev[col].median()*100:+7.3f}%")

# by whether the close is above the stop level, and by stop time (early vs late)
ev["late"] = ev["minute"] >= 180
print("\nnight_true by late/early and recovery:")
print(ev.groupby(["late", "close_above_stoplevel"])["night_true"].agg(["size", "mean", "median"]).round(4).to_string())

# Reclaim -> close and -> next measured from fill, split by tight-stop outcome
for name, arr in (("vwap", vwap), ("ema5", ema5), ("ema15", ema15)):
    recs = []
    for _, r in ev.iterrows():
        k, i, z = int(r["k"]), int(r["i"]), int(r["k"])
        z = last[k]
        hit = -1
        conf = 0
        for j in range(i + 1, z):
            if np.isfinite(arr[j]) and c[j, 1] > arr[j]:
                conf += 1
            else:
                conf = 0
            if conf >= 2:
                hit = j
                break
        if hit < 0:
            continue
        fill = o[hit + 1, 1]
        # what a 2% tight stop from fill would have done (close-based, exit next open)
        exit_px, reason = o[z, 1], "close"
        for j in range(hit + 1, z + 1):
            if c[j, 1] < fill * 0.98:
                exit_px, reason = o[j + 1, 1], "stop"
                break
        recs.append(dict(date=r["date"], to_close=c[z, 1] / fill - 1, to_next=r["next_open"] / fill - 1,
                         tight2=exit_px / fill - 1, reason=reason))
    t = pd.DataFrame(recs)
    print(f"\n{name} reclaims n={len(t)}  tight-2% exits {int((t['reason']=='stop').sum())}")
    for col in ("to_close", "to_next", "tight2"):
        print(f"  {col:10s} mean {t[col].mean()*100:+7.3f}%  median {t[col].median()*100:+7.3f}%  "
              f"share<0 {(t[col]<0).mean()*100:5.1f}%")
