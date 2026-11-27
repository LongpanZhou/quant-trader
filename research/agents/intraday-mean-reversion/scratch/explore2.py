"""Exploration 2: overreaction buckets, time-of-day, baseline drawdown anatomy."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

START, END = "2017-01-03", "2026-10-23"


def load(rule):
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, rule)
    return ts, o, c


ts, o, c = load("5min")
i0 = bt.start_index(ts, START)
qqq, tqqq = c[:, 0], c[:, 1]
dates = pd.Series(ts.date)
df = pd.DataFrame({"ts": ts, "date": dates, "qqq": qqq, "tqqq": tqqq})
g = df.groupby("date", sort=True)
daily = pd.DataFrame({"o": g["qqq"].first(), "c": g["qqq"].last()})
daily["sma165"] = daily["c"].rolling(165).mean()
daily["regime"] = (daily["c"] > daily["sma165"]).astype(float)
reg_prev = daily["regime"].shift(1).reindex(dates).to_numpy()
in_test = np.arange(len(ts)) >= i0

# ---- 30-min momentum buckets -> next 30 min TQQQ
bars = df.groupby("date").cumcount().to_numpy()
r30 = qqq / pd.Series(qqq).shift(6).to_numpy() - 1.0
fwd30 = np.full(len(tqqq), np.nan)
fwd30[:-12] = o[7:-5, 1] / o[1:-11, 1] - 1.0  # entry next open, hold 6 bars
fwd60 = np.full(len(tqqq), np.nan)
fwd60[:-13] = o[13:, 1] / o[1:-12, 1] - 1.0

print("=== prior 30m QQQ move -> next 30m TQQQ (regime-on, test) ===")
m0 = in_test & (reg_prev == 1)
for lo, hi in [(-9, -0.6), (-0.6, -0.4), (-0.4, -0.25), (-0.25, -0.1), (-0.1, 0.1), (0.1, 0.25), (0.25, 0.4), (0.4, 0.6), (0.6, 9)]:
    m = m0 & (r30 >= lo) & (r30 < hi) & np.isfinite(fwd30)
    if m.sum() > 50:
        print(f"  r30 [{lo:5.2f},{hi:5.2f}) n={m.sum():6d} fwd30 {fwd30[m].mean()*100:+.4f}% win {np.mean(fwd30[m]>0)*100:4.1f}%"
              f"   fwd60 {np.nanmean(np.where(m, fwd60, np.nan))*100:+.4f}%")

print("\n=== large 60m drawdown -> next 30m TQQQ ===")
r60 = qqq / pd.Series(qqq).shift(12).to_numpy() - 1.0
for lo, hi in [(-9, -1.2), (-1.2, -0.9), (-0.9, -0.7), (-0.7, -0.5), (-0.5, -0.3), (-0.3, 0.3)]:
    m = m0 & (r60 >= lo) & (r60 < hi) & np.isfinite(fwd30)
    if m.sum() > 50:
        print(f"  r60 [{lo:5.2f},{hi:5.2f}) n={m.sum():6d} fwd30 {fwd30[m].mean()*100:+.4f}% win {np.mean(fwd30[m]>0)*100:4.1f}%")

# ---- time of day: avg QQQ 5m return by bar index (regime-on)
print("\n=== time-of-day QQQ 5m mean return (bp) and TQQQ 5m vol, regime-on test ===")
r5 = qqq / pd.Series(qqq).shift(1).to_numpy() - 1.0
rows = []
for b in range(0, 77, 4):
    m = in_test & (reg_prev == 1) & (bars >= b) & (bars < b + 4)
    rows.append((b, np.mean(r5[m]) * 1e4, np.std(r5[m]) * 1e4))
for b, mu, sd in rows:
    print(f"  bar {b:2d} ({9*60+30+b*5:4d}m) mean {mu:+7.3f}bp  sd {sd:6.2f}bp")

# ---- baseline daily regime equity and drawdown anatomy
tsd, od, cd = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1D")
d0 = bt.start_index(tsd, START)
dd = pd.DataFrame({"ts": tsd, "qqq": cd[:, 0]})
dg = dd.groupby(dd["ts"].dt.date)
day = pd.DataFrame({"o": dg["qqq"].first(), "c": dg["qqq"].last()})
day["sma165"] = day["c"].rolling(165).mean()
day["reg"] = (day["c"] > day["sma165"]).astype(float)
day["sig"] = day["reg"].shift(1)  # weight set at close of d fills next open
w = np.zeros((len(day), 3))
w[:, 1] = day["sig"].fillna(0).to_numpy()
w[:, 2] = 1 - w[:, 1]
res = bt.run(tsd, od, cd, w, START, band=0.02, slippage_bps=1.0)
s = bt.stats(res, 252)
print("\n=== daily SMA165 baseline recompute ===")
print({k: round(v, 4) if isinstance(v, float) else v for k, v in s.items()})
eq = res["equity"]
peak = np.maximum.accumulate(eq)
ddown = eq / peak - 1
j = int(np.argmin(ddown))
print("min at", tsd[j], "dd", ddown[j])
# top 5 dd troughs
troughs = []
for j2 in range(1, len(eq) - 1):
    if ddown[j2] < -0.10 and ddown[j2] <= ddown[j2 - 1] and ddown[j2] <= ddown[j2 + 1]:
        troughs.append((ddown[j2], tsd[j2]))
for v, t in sorted(troughs)[:8]:
    print("  trough", t.date(), f"{v*100:.1f}%")
