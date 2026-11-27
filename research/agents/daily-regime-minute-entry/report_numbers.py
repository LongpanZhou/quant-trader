"""Numbers for the report: sub-periods, event counts, worst months, exposure."""
import numpy as np
import pandas as pd

import strat_lib as sl
import bt

A = sl.load_arrays()
ts, dates, first, last = A["ts"], A["dates"], A["first"], A["last"]
oc, oo = A["closes"], A["opens"]
reg, dc, sma, _, _, _ = sl.daily_regime(ts, oc[:, 0], 165)
n = len(ts)
c = oc[:, 1]
qqq_c = oc[:, 0]
ma20 = pd.Series(oc[last, 0]).rolling(20).mean().to_numpy()
day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, n]))
ma20_min = np.r_[np.nan, ma20[:-1]][day_id]

hold = np.zeros(n, bool)
stops = []
for f, l in zip(first, last):
    state = bool(reg[f])
    base = oo[f, 1]
    armed = bool(qqq_c[f] < ma20_min[f] * 1.01)
    for i in range(f, l + 1):
        if armed and state and c[i] < base * 0.96:
            state = False
            stops.append(dates[f])
        hold[i] = state
w = np.zeros((n, 3)); w[:, 1] = hold.astype(float); w[:, 2] = 1 - hold
wc = np.zeros((n, 3)); wc[:, 1] = reg.astype(float); wc[:, 2] = 1 - reg

i0 = bt.start_index(ts, sl.START10)
r = bt.run(ts, oo, oc, w, sl.START10, band=0.02, slippage_bps=1.0)
rc = bt.run(ts, oo, oc, wc, sl.START10, band=0.02, slippage_bps=1.0)
s = pd.Series(r["equity"], index=ts[i0:])
sc = pd.Series(rc["equity"], index=ts[i0:])

sy = pd.Series([d for d in stops if d.year >= 2017])
print("stop events by year (test window):", sy.astype(str).str[:4].value_counts().sort_index().to_dict())
print("total stops in test window:", len(sy))

print("\nsub-periods (final vs control):")
for a, z in (("2017-01-03", "2019-12-31"), ("2020-01-02", "2022-12-30"), ("2023-01-03", "2026-10-23")):
    row = []
    for ser in (s, sc):
        seg = ser.loc[a:z]
        yrs = (seg.index[-1] - seg.index[0]).total_seconds() / (365.25 * 86400)
        dd = float(-(seg / seg.cummax() - 1).min())
        row.append(f"CAGR {(seg.iloc[-1]/seg.iloc[0])**(1/yrs)-1:6.2f}%  DD {dd*100:5.1f}%")
    print(f"  {a[:4]}-{z[:4]}:  final {row[0]}   |  control {row[1]}")

print("\nhalves (final vs control):")
for a, z in (("2017-01-03", "2021-12-31 23:59"), ("2022-01-03", "2026-10-23 23:59")):
    row = []
    for ser in (s, sc):
        seg = ser.loc[a:z]
        yrs = (seg.index[-1] - seg.index[0]).total_seconds() / (365.25 * 86400)
        dd = float(-(seg / seg.cummax() - 1).min())
        row.append(f"CAGR {(seg.iloc[-1]/seg.iloc[0])**(1/yrs)-1:6.2f}%  DD {dd*100:5.1f}%")
    print(f"  {a[:4]}-{z[:4]}:  final {row[0]}   |  control {row[1]}")

sr = s.resample("ME").last().pct_change().dropna()
print("\nmonthly: positive share", f"{(sr>0).mean()*100:.1f}%", " mean", f"{sr.mean()*100:.2f}%")
print("worst 6:", [f"{k.strftime('%Y-%m')} {v*100:.1f}%" for k, v in sr.sort_values().head(6).items()])
print("best 4:", [f"{k.strftime('%Y-%m')} {v*100:.1f}%" for k, v in sr.sort_values().tail(4).items()])

ex = pd.Series((r["equity"] - r["cash"]) / r["equity"], index=ts[i0:])
print("\nexposure to TQQQ+BIL:", f"{ex.mean()*100:.1f}%", " (TQQQ share of days:",
      f"{hold[i0:][::390].mean()*100:.1f}%)")
