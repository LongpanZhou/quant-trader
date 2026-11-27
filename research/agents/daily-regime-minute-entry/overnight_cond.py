"""Conditional overnight returns: does the day's close strength predict the night?"""
import numpy as np
import pandas as pd

import strat_lib as sl

A = sl.load_arrays()
ts, dates, first, last = A["ts"], A["dates"], A["first"], A["last"]
oc, oo = A["closes"], A["opens"]
reg, dc, sma, _, _, _ = sl.daily_regime(ts, oc[:, 0], 165)
n = len(ts)
qc, tc = oc[:, 0], oc[:, 1]

rows = []
for k, (f, l) in enumerate(zip(first, last)):
    if k == 0:
        continue
    day_ret = tc[l] / oo[f, 1] - 1          # intraday (open->close)
    on = tc[l] / tc[last[k - 1]] - 1        # overnight into this day
    last30 = tc[l] / tc[l - 30] - 1
    last60 = tc[l] / tc[l - 60] - 1
    vwap = np.sum(((A["highs"][f:l + 1, 1] + A["lows"][f:l + 1, 1] + tc[f:l + 1]) / 3) * A["vols"][f:l + 1, 1]) / max(A["vols"][f:l + 1, 1].sum(), 1)
    rows.append(dict(date=dates[f], day=day_ret, night=on, last30=last30, last60=last60,
                     above_vwap=tc[l] > vwap, reg=reg[f],
                     night_next=tc[last[k]] / tc[l] - 1 if k + 1 < len(first) else np.nan))
df = pd.DataFrame(rows)
df["night_next"] = df["night"].shift(-1)  # night after this day
d = df.iloc[1:].dropna(subset=["night_next"])
d = d[d["reg"]]
print("regime-on days:", len(d))

print("\novernight AFTER a day, by day's intraday return bucket:")
for lo, hi in ((-1, -0.03), (-0.03, -0.02), (-0.02, -0.01), (-0.01, 0), (0, 0.01), (0.01, 0.02), (0.02, 0.03), (0.03, 1)):
    m = (d["day"] > lo) & (d["day"] <= hi)
    if m.sum() > 10:
        print(f"  day {lo*100:5.1f}..{hi*100:5.1f}%: n={m.sum():4d}  mean night {d.loc[m,'night_next'].mean()*100:6.3f}%  "
              f"median {d.loc[m,'night_next'].median()*100:6.3f}%  win {np.mean(d.loc[m,'night_next']>0)*100:4.1f}%  "
              f"worst {d.loc[m,'night_next'].min()*100:6.1f}%")

print("\nby close vs VWAP:")
for v in (True, False):
    m = d["above_vwap"] == v
    print(f"  above_vwap={v}: n={m.sum():4d}  mean night {d.loc[m,'night_next'].mean()*100:6.3f}%  "
          f"median {d.loc[m,'night_next'].median()*100:6.3f}%  win {np.mean(d.loc[m,'night_next']>0)*100:4.1f}%")

print("\nby last-30min return bucket:")
for lo, hi in ((-1, -0.01), (-0.01, -0.005), (-0.005, 0), (0, 0.005), (0.005, 0.01), (0.01, 1)):
    m = (d["last30"] > lo) & (d["last30"] <= hi)
    if m.sum() > 10:
        print(f"  last30 {lo*100:5.2f}..{hi*100:5.2f}%: n={m.sum():4d}  mean night {d.loc[m,'night_next'].mean()*100:6.3f}%  win {np.mean(d.loc[m,'night_next']>0)*100:4.1f}%")

print("\nby weekday of the night (day before):")
d2 = d.copy()
d2["wd"] = pd.to_datetime(d2["date"]).dt.dayofweek
print((d2.groupby("wd")["night_next"].agg(["mean", "median", "count"]) * [100, 100, 1]).round(3))

# combined weak-close filter
for thr in (-0.03, -0.02, -0.015, -0.01, -0.005, 0.0):
    m = d["day"] < thr
    print(f"skip night when day < {thr*100:5.1f}%: n={m.sum():4d} ({m.mean()*100:4.1f}%)  "
          f"mean night skipped {d.loc[m,'night_next'].mean()*100:6.3f}%  vs kept {d.loc[~m,'night_next'].mean()*100:6.3f}%")

# what if we skip the night after a day below vwap
m = ~d["above_vwap"]
print(f"\nskip night when close<vwap: n={m.sum()} ({m.mean()*100:.1f}%) mean skipped {d.loc[m,'night_next'].mean()*100:.3f}% "
      f"vs kept {d.loc[~m,'night_next'].mean()*100:.3f}%")
