"""Deeper event study: fixed thresholds, stability by year, 30m windows, beta."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parents[1]
df = pd.read_pickle(HERE / "daily.pkl")
test = df[df["date"] >= pd.Timestamp("2017-01-03", tz="America/New_York")].copy()

def stats(r):
    r = r.dropna()
    if len(r) < 3:
        return dict(n=len(r), mean_bp=np.nan, med_bp=np.nan, hit=np.nan, t=np.nan)
    return dict(n=len(r), mean_bp=r.mean()*1e4, med_bp=r.median()*1e4,
                hit=(r > 0).mean(), t=r.mean()/(r.std(ddof=1)/np.sqrt(len(r))))

bins = [-99, -2, -1, -0.5, -0.25, 0, 0.25, 0.5, 1, 2, 99]
labels = ["<-2", "-2..-1", "-1..-.5", "-.5..-.25", "-.25..0", "0...25", ".25...5", ".5..1", "1..2", ">2"]

for retcol, runcol in [("late60", "run60"), ("late30", "run30")]:
    print(f"\n==== {retcol} by runup bin ====")
    rows = []
    for regime in [True, False]:
        sub = test[test["risk_on"] == regime]
        b = pd.cut(sub[runcol]*100, bins=bins, labels=labels)
        for lab in labels:
            m = b == lab
            s = stats(sub.loc[m, retcol])
            s.update(regime=regime, bin=lab)
            rows.append(s)
    out = pd.DataFrame(rows)[["regime", "bin", "n", "mean_bp", "med_bp", "hit", "t"]]
    print(out.to_string(index=False, float_format=lambda x: f"{x:7.2f}"))

print("\n==== late60 by year x sign(run60), QQQ mean bp (n) ====")
rows = []
for y, sub in test.groupby(test["date"].dt.year):
    row = dict(year=int(y))
    for regime in [True, False]:
        for sgn, tag in [(1, "up"), (-1, "dn")]:
            m = (sub["risk_on"] == regime) & (np.sign(sub["run60"]) == sgn)
            r = sub.loc[m, "late60"].dropna()
            row[f"{'on' if regime else 'off'}_{tag}_bp"] = r.mean()*1e4 if len(r) else np.nan
            row[f"{'on' if regime else 'off'}_{tag}_n"] = len(r)
    rows.append(row)
print(pd.DataFrame(rows).to_string(index=False, float_format=lambda x: f"{x:7.2f}"))

print("\n==== late30 by year x sign(run30), QQQ mean bp (n) ====")
rows = []
for y, sub in test.groupby(test["date"].dt.year):
    row = dict(year=int(y))
    for regime in [True, False]:
        for sgn, tag in [(1, "up"), (-1, "dn")]:
            m = (sub["risk_on"] == regime) & (np.sign(sub["run30"]) == sgn)
            r = sub.loc[m, "late30"].dropna()
            row[f"{'on' if regime else 'off'}_{tag}_bp"] = r.mean()*1e4 if len(r) else np.nan
            row[f"{'on' if regime else 'off'}_{tag}_n"] = len(r)
    rows.append(row)
print(pd.DataFrame(rows).to_string(index=False, float_format=lambda x: f"{x:7.2f}"))

# More refined: does the last 30m predict the final 30m?
test["r1500_1530"] = test["p1529"] / test["o1500"] - 1.0
test["late30_full"] = test["c"] / test["o1530"] - 1.0
test["late_1530_1559"] = test["p1558"] / test["o1530"] - 1.0
print("\n==== final 30m (15:30->15:59) by prior 30m decile ====")
q = pd.qcut(test["r1500_1530"], 8, labels=False, duplicates="drop")
rows = []
for k in range(8):
    m = q == k
    s = stats(test.loc[m, "late30"])
    s["bucket"] = k
    s["lo_bp"] = test.loc[m, "r1500_1530"].min()*1e4
    s["hi_bp"] = test.loc[m, "r1500_1530"].max()*1e4
    rows.append(s)
print(pd.DataFrame(rows)[["bucket", "lo_bp", "hi_bp", "n", "mean_bp", "med_bp", "hit", "t"]]
      .to_string(index=False, float_format=lambda x: f"{x:7.2f}"))

print("\n==== final 30m by prior 30m sign AND day sign ====")
rows = []
for rs in [True, False]:
    for ds in [1, -1]:
        for s2 in [1, -1]:
            m = (test["risk_on"] == rs) & (np.sign(test["run60"]) == ds) & (np.sign(test["r1500_1530"]) == s2)
            s = stats(test.loc[m, "late30"])
            s.update(regime=rs, day=ds, last30=s2)
            rows.append(s)
print(pd.DataFrame(rows)[["regime", "day", "last30", "n", "mean_bp", "med_bp", "hit", "t"]]
      .to_string(index=False, float_format=lambda x: f"{x:7.2f}"))

# beta of TQQQ late return on QQQ late return, split by |run60|
print("\n==== TQQQ late60 beta on QQQ late60, by day-move size ====")
for lo, hi in [(0, 0.5), (0.5, 1.0), (1.0, 2.0), (2.0, 99)]:
    m = test["run60"].abs().between(lo/100, hi/100, inclusive="left")
    x = test.loc[m, "late60"].dropna()
    y = test.loc[m, "t_late60"].reindex(x.index)
    beta = np.polyfit(x, y, 1)
    print(f"|run| {lo}-{hi}%  n={len(x)}  beta={beta[0]:.2f}  alpha={beta[1]*1e4:.1f}bp  corr={np.corrcoef(x,y)[0,1]:.3f}")

# event counts for risk-off strong rally
print("\n==== risk-off strong late-day rally events (run60 > 1.5%) ====")
m = (~test["risk_on"]) & (test["run60"] > 0.015)
print("n", m.sum())
print(test.loc[m, ["date", "run60", "late60", "t_late60", "on_next", "day"]]
      .assign(run60=lambda d: (d.run60*100).round(2), late60=lambda d: (d.late60*100).round(2),
              t_late60=lambda d: (d.t_late60*100).round(2), on_next=lambda d: (d.on_next*100).round(2),
              day=lambda d: (d.day*100).round(2))
      .to_string(index=False))
