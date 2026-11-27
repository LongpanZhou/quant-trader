"""Event study of the 3% stop: what the exit avoids and what the re-entry captures."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import strategy as S  # noqa: E402

RULE = "5min"
S.RULE = RULE
ts, o, c, feats = S.prepare(RULE)
n = len(ts)
w, stops = S.make_weights(feats, n, 0.03)
date, bars, last_bar = feats["dlist"], feats["bars"], feats["last_bar"]
qqq, qpc = feats["qqq"], feats["qpc"]

# find stop bars: weight goes from 1 to 0 while QQQ <= -3% from prior close
stop_idx = [i for i in range(1, n - 1)
            if w[i, 1] == 0 and w[i - 1, 1] == 1 and np.isfinite(qpc[i]) and qqq[i] / qpc[i] - 1 <= -0.03]
print("stop events:", len(stop_idx))

rows = []
for i in stop_idx:
    d = date[i]
    j = max(k for k in range(i, n) if date[k] == d)  # last bar of the day
    nxt = j + 1
    if nxt + 1 >= n or date[nxt] != date[j] and True:
        pass
    # exit fill = open[i+1]; rest of day = close[j]/open[i+1]
    rest = c[j, 1] / o[i + 1, 1] - 1.0
    # overnight: next day open / today's close
    k0 = nxt  # first bar of next day
    gap = o[k0, 1] / c[j, 1] - 1.0
    k1 = max(k for k in range(k0, min(k0 + 100, n)) if date[k] == date[k0])
    nextday = c[k1, 1] / o[k0, 1] - 1.0
    rows.append((d, qqq[i] / qpc[i] - 1.0, rest, gap, nextday, bars[i] * 5 + 570))

a = pd.DataFrame(rows, columns=["date", "qqq_dd", "rest_of_day", "overnight_gap", "next_day", "minute"])
print(f"  mean QQQ drawdown at trigger {a.qqq_dd.mean()*100:.2f}%")
print(f"  rest of session (TQQQ, exit fill -> close): {a.rest_of_day.mean()*100:+.3f}%  "
      f"win {np.mean(a.rest_of_day>0)*100:.0f}%  (n={len(a)})")
print(f"  overnight gap avoided (today close -> next open): {a.overnight_gap.mean()*100:+.3f}%  "
      f"win {np.mean(a.overnight_gap>0)*100:.0f}%")
print(f"  next session open->close (captured on re-entry): {a.next_day.mean()*100:+.3f}%  "
      f"win {np.mean(a.next_day>0)*100:.0f}%")
print(f"  net effect of stop vs holding = -rest_of_day + gap avoided = "
      f"{(-a.rest_of_day.mean()+a.overnight_gap.mean())*100:+.3f}% per event")

print("\n  by trigger time:")
a["bucket"] = pd.cut(a.minute, bins=[569, 660, 750, 840, 960], labels=["09:30-11:00", "11:00-12:30", "12:30-14:00", "14:00-16:00"])
print(a.groupby("bucket", observed=True).agg(n=("rest_of_day", "size"), rest=("rest_of_day", "mean"),
                                             gap=("overnight_gap", "mean"), nxt=("next_day", "mean")).to_string(float_format=lambda x: f"{x*100:+.3f}%"))

print("\n  by year:")
print(a.assign(year=a.date.astype(str).str[:4]).groupby("year").agg(
    n=("rest_of_day", "size"), rest=("rest_of_day", "mean"), gap=("overnight_gap", "mean"),
    nxt=("next_day", "mean")).to_string(float_format=lambda x: f"{x*100:+.3f}%"))
