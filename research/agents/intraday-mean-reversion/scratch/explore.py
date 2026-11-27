"""Exploration: intraday mean reversion statistics on QQQ/TQQQ 5m bars."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

START, END = "2017-01-03", "2026-10-23"
ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "5min")
i0 = bt.start_index(ts, START)
print("5m bars", len(ts), "test", len(ts) - i0)

qqq, tqqq = c[:, 0], c[:, 1]
dates = pd.Series(ts.date, index=range(len(ts)))

# daily series
df = pd.DataFrame({"ts": ts, "date": ts.date, "qqq": qqq, "tqqq": tqqq, "bilo": o[:, 2], "bilc": c[:, 2]})
g = df.groupby("date", sort=True)
daily = pd.DataFrame({
    "o": g["qqq"].first(),
    "c": g["qqq"].last(),
    "hi": g["qqq"].max(),
    "lo": g["qqq"].min(),
})
daily["sma165"] = daily["c"].rolling(165).mean()
daily["regime"] = (daily["c"] > daily["sma165"]).astype(float)
print("regime on frac", daily["regime"].iloc[252:].mean().round(3))

# overnight vs intraday decomposition (QQQ)
d_open = daily["o"].to_numpy()
d_close = daily["c"].to_numpy()
on = np.concatenate([[0.0], d_close[:-1]])
ov = d_open / on - 1
intr = d_close / d_open - 1
print("\nQQQ overnight mean %.4f%% ann %.2f%%  intraday mean %.4f%% ann %.2f%%" % (
    ov[1:].mean() * 100, (1 + ov[1:]).prod() ** (252 / len(ov[1:])) * 100 - 100,
    intr[1:].mean() * 100, (1 + intr[1:]).prod() ** (252 / len(intr[1:])) * 100 - 100))
print("TQQQ close-to-close ann %.2f%%" % ((daily['c'].iloc[-1] / daily['c'].iloc[251]) ** (252 / (len(daily) - 251)) * 100 - 100))

# autocorrelation of 5m returns within day (per-day, pooled)
qqq_r = pd.Series(qqq).pct_change()
print("\n5m return autocorr lag1:", qqq_r.autocorr(1).round(4), "lag2:", qqq_r.autocorr(2).round(4))

# build intraday features
idx = np.arange(len(ts))
# minutes since day start
day_start = df.groupby("date")["ts"].transform("first")
mins = ((ts - pd.DatetimeIndex(day_start)).total_seconds() / 60).astype(int)
print("minutes per day max", mins.max())

# RSI(2) on 5m closes
delta = np.diff(qqq, prepend=qqq[0])
up = np.where(delta > 0, delta, 0.0)
dn = np.where(delta < 0, -delta, 0.0)
a = 1.0 / 2
au = pd.Series(up).ewm(alpha=a, adjust=False).mean().to_numpy()
ad = pd.Series(dn).ewm(alpha=a, adjust=False).mean().to_numpy()
rsi2 = 100 * au / np.where(au + ad > 0, au + ad, np.nan)

# Bollinger z on 20 bars
s = pd.Series(qqq)
m20 = s.rolling(20).mean().to_numpy()
sd20 = s.rolling(20).std(ddof=0).to_numpy()
z20 = (qqq - m20) / np.where(sd20 > 0, sd20, np.nan)

# intraday VWAP
tp = (df["qqq"].to_numpy())
vol = df.groupby("date")["qqq"].transform("count").to_numpy() * 0 + 1.0  # no volume col here; use equal weight
cum_tp = pd.Series(tp).groupby(df["date"]).cumsum()
n_in = df.groupby("date").cumcount().to_numpy() + 1
vwap = cum_tp.to_numpy() / n_in
dev_vwap = qqq / vwap - 1

# forward TQQQ returns (next open -> open after k bars)
# signal at close of bar i -> entry at open i+1, exit at open i+1+k
tq = tqqq
def fwd(k):
    r = np.full(len(tq), np.nan)
    ent = o[:, 1]
    r[: len(tq) - k - 1] = ent[k + 1: len(tq)] / ent[1: len(tq) - k] - 1.0
    return r

reg = daily["regime"].reindex(df["date"]).to_numpy()  # regime of that day's close (LAGGED below)
# shift regime by one day: for intraday bars of day d use regime from day d-1
reg_prev = daily["regime"].shift(1).reindex(df["date"]).to_numpy()

mask = (idx >= i0) & (reg_prev == 1.0) & np.isfinite(rsi2)
print("\nregime-on bars:", int(mask.sum()))

for k in (1, 3, 6, 12):
    y = fwd(k)
    print(f"\n--- horizon {k} bars (= {k*5} min), TQQQ fwd ret, regime-on ---")
    for lo, hi in [(0, 5), (5, 10), (10, 25), (25, 50), (50, 75), (75, 90), (90, 100)]:
        m = mask & (rsi2 >= lo) & (rsi2 < hi) & np.isfinite(y)
        if m.sum() > 30:
            print(f"  RSI2 [{lo:3d},{hi:3d}) n={m.sum():6d} mean={y[m].mean()*100:+.4f}%  win={np.mean(y[m]>0)*100:4.1f}%")

print("\n--- z20 buckets, horizon 6 bars ---")
y = fwd(6)
for lo, hi in [(-9, -2.5), (-2.5, -1.5), (-1.5, -0.5), (-0.5, 0.5), (0.5, 1.5), (1.5, 2.5), (2.5, 9)]:
    m = mask & (z20 >= lo) & (z20 < hi) & np.isfinite(y)
    if m.sum() > 30:
        print(f"  z [{lo:5.1f},{hi:5.1f}) n={m.sum():6d} mean={y[m].mean()*100:+.4f}% win={np.mean(y[m]>0)*100:4.1f}%")

print("\n--- vwap dev buckets, horizon 6 bars ---")
for lo, hi in [(-9, -1.0), (-1.0, -0.5), (-0.5, -0.2), (-0.2, 0.0), (0.0, 0.2), (0.2, 0.5), (0.5, 9)]:
    m = mask & (dev_vwap >= lo) & (dev_vwap < hi) & np.isfinite(y)
    if m.sum() > 30:
        print(f"  dev [{lo:5.1f},{hi:5.1f}) n={m.sum():6d} mean={y[m].mean()*100:+.4f}% win={np.mean(y[m]>0)*100:4.1f}%")
