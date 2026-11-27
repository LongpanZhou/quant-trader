"""Decompose TQQQ/QQQ returns into overnight vs intraday; daily-regime diagnostics."""
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, "research")
import bt

ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), "2017-01-03", "2026-10-23", "1min")
print("minute bars", len(ts), ts[0], ts[-1])

dates = ts.date
# first/last bar index per day
df = pd.DataFrame({"date": dates, "o": opens[:, 1], "c": closes[:, 1],
                   "qo": opens[:, 0], "qc": closes[:, 0]})
g = df.groupby("date", sort=True)
day = pd.DataFrame({
    "open": g["o"].first(), "close": g["c"].last(),
    "qopen": g["qo"].first(), "qclose": g["qc"].last(),
})
day["intraday"] = day["close"] / day["open"] - 1
day["overnight"] = day["open"] / day["close"].shift(1) - 1
day = day.iloc[1:]
start = pd.Timestamp("2017-01-03").date()
d = day[day.index >= start]
n = len(d)
print("days", n, d.index[0], d.index[-1])
on = d["overnight"].to_numpy()
intr = d["intraday"].to_numpy()
print(f"TQQQ intraday : total {np.prod(1+intr)-1:8.1%}  mean {intr.mean()*100:.3f}%/d  vol {intr.std()*100:.2f}%")
print(f"TQQQ overnight: total {np.prod(1+on)-1:8.1%}  mean {on.mean()*100:.3f}%/d  vol {on.std()*100:.2f}%")
qon = (d["qopen"] / d["qclose"].shift(1) - 1).to_numpy()[1:]
qintr = (d["qclose"] / d["qopen"] - 1).to_numpy()
print(f"QQQ intraday  : total {np.prod(1+qintr)-1:8.1%}  mean {qintr.mean()*100:.3f}%/d  vol {qintr.std()*100:.2f}%")
print(f"QQQ overnight : total {np.prod(1+qon)-1:8.1%}  mean {qon.mean()*100:.3f}%/d  vol {qon.std()*100:.2f}%")

# distribution by weekday
d2 = d.copy()
d2["wd"] = pd.to_datetime(d2.index).dayofweek
print("\nmean overnight by weekday (%):")
print((d2.groupby("wd")["overnight"].mean() * 100).round(3))
print("mean intraday by weekday (%):")
print((d2.groupby("wd")["intraday"].mean() * 100).round(3))

# minute-of-day average return pattern TQQQ (open->close path), 2017+
sub = df[df["date"] >= start].copy()
sub["minute"] = sub.groupby("date").cumcount()
sub["ret"] = sub.groupby("date")["c"].pct_change()
prof = sub.groupby("minute")["ret"].agg(["mean", "std"])
prof["mean_bp"] = prof["mean"] * 1e4
print("\nmean 1m return by minute (bp), first 15 / last 15:")
print(prof["mean_bp"].head(15).round(2).to_string())
print(prof["mean_bp"].tail(15).round(2).to_string())
cum = (1 + prof["mean"]).cumprod()
print("\ncumulative intraday drift by minute (end/start):", f"{cum.iloc[-1]-1:.1%}")
print("at 10:00", f"{cum.iloc[29]-1:.1%}", "at 11:30", f"{cum.iloc[119]-1:.1%}", "at 15:00", f"{cum.iloc[329]-1:.1%}")
