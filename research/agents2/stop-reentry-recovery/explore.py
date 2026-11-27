"""Event study: what happens after the winner's 4% stop, and does a reclaim pay?"""
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
ema5b = S.session_ema(c, first, last, 5, 20)
ema15 = S.session_ema(c, first, last, 15, 9)

rows = []
for k, (f, z) in enumerate(zip(first, last)):
    if not reg[f]:
        continue
    armed = bool(np.isfinite(ma20[f]) and c[f, 0] < ma20[f] * (1 + S.ARM_BUF))
    if not armed:
        continue
    base = o[f, 1]
    for i in range(f, z + 1):
        if c[i, 1] < base * (1 - S.STOP):
            # first stop of the day
            rec = dict(date=dates[f], k=k, f=f, z=z, i=i, minute=i - f,
                       stop_close=c[i, 1], day_open=base, day_close=c[z, 1],
                       vwap_stop=vwap[i], next_open=o[first[k + 1], 1] if k + 1 < len(first) else np.nan)
            rec["stop_to_close"] = c[z, 1] / c[i, 1] - 1
            rec["stop_to_next"] = rec["next_open"] / c[i, 1] - 1
            rec["close_ret"] = c[z, 1] / base - 1
            rec["close_above_stoplevel"] = c[z, 1] > base * (1 - S.STOP)
            rec["close_above_vwap"] = c[z, 1] > vwap[z]
            rec["close_above_open"] = c[z, 1] > base
            # first reclaim of each line after the stop, with one confirmation bar
            for name, arr in (("vwap", vwap), ("ema5", ema5), ("ema15", ema15)):
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
                rec[f"{name}_bar"] = hit
                if hit > 0:
                    fill = o[hit + 1, 1]
                    rec[f"{name}_to_close"] = c[z, 1] / fill - 1
                    rec[f"{name}_to_next"] = rec["next_open"] / fill - 1
            hit = -1
            for j in range(i + 1, z):
                if np.isfinite(ma20[f]) and c[j, 0] > ma20[f]:
                    hit = j
                    break
            rec["qqqma_bar"] = hit
            if hit > 0:
                fill = o[hit + 1, 1]
                rec["qqqma_to_close"] = c[z, 1] / fill - 1
                rec["qqqma_to_next"] = rec["next_open"] / fill - 1
            rows.append(rec)
            break

ev = pd.DataFrame(rows)
print(f"stop events (armed, 2016-2026): {len(ev)}")
print("by year:", ev.groupby(ev["date"].astype(str).str[:4]).size().to_dict())
print("\nbaseline after stop:")
for col in ("stop_to_close", "stop_to_next", "close_ret"):
    x = ev[col].dropna()
    print(f"  {col:16s} mean {x.mean()*100:+7.3f}%  median {x.median()*100:+7.3f}%  "
          f"share<0 {np.mean(x<0)*100:5.1f}%  n={len(x)}")
print("\nclose recovery shares:",
      {k: round(float(ev[k].mean()) * 100, 1) for k in
       ("close_above_stoplevel", "close_above_vwap", "close_above_open")})

for name in ("vwap", "ema5", "ema15", "qqqma"):
    b = ev[f"{name}_bar"]
    n = int((b > 0).sum())
    print(f"\n{name}: reclaim events {n}/{len(ev)} ({n/len(ev)*100:.1f}%)  "
          f"median minute {ev.loc[b>0, f'{name}_bar'].sub(ev.loc[b>0,'f']).median():.0f}")
    if n:
        for col in (f"{name}_to_close", f"{name}_to_next"):
            x = ev[col].dropna()
            print(f"  {col:16s} mean {x.mean()*100:+7.3f}%  median {x.median()*100:+7.3f}%  "
                  f"share<0 {np.mean(x<0)*100:5.1f}%  n={len(x)}")

print("\nconditional stop_to_next:")
for flag in ("close_above_stoplevel", "close_above_vwap", "close_above_open"):
    x = ev.loc[ev[flag], "stop_to_next"].dropna()
    y = ev.loc[~ev[flag], "stop_to_next"].dropna()
    print(f"  {flag:22s} true n={len(x):3d} mean {x.mean()*100:+7.3f}%   "
          f"false n={len(y):3d} mean {y.mean()*100:+7.3f}%")

print("\nstop->next by hour:")
ev["hour"] = [ts[i].hour for i in ev["i"]]
print(ev.groupby("hour")["stop_to_next"].agg(["size", "mean", "median"]).round(4).to_string())

print("\nworst 10 stop->next:")
cols = ["date", "minute", "stop_to_close", "stop_to_next", "vwap_bar", "close_above_stoplevel"]
print(ev.sort_values("stop_to_next")[cols].head(10).to_string(index=False))
print("\nbest 10 stop->next:")
print(ev.sort_values("stop_to_next")[cols].tail(10).to_string(index=False))

ev.drop(columns=["k", "f", "z", "i"]).to_csv(HERE / "stop_events.csv", index=False)
print("\nwrote stop_events.csv")
