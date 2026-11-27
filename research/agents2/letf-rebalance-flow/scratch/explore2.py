"""Build daily table from the 1m panel and run the late-day event study."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "research")
import bt

HERE = Path(__file__).resolve().parents[1]
CACHE = HERE / "panel_cache.npz"
z = np.load(CACHE)
ts = pd.DatetimeIndex(z["ts"]).tz_localize("UTC").tz_convert("America/New_York")
opens = z["opens"]
closes = z["closes"]

# session index
dates = ts.normalize()
uniq = pd.DatetimeIndex(sorted(set(dates)))
# map each bar to session number
sess = np.searchsorted(uniq.values, dates.values)
n_sess = len(uniq)
# bar offset within session (0..389); data is complete 390 bars/session except rare
mins = (ts.hour * 60 + ts.minute) - (9 * 60 + 30)
assert mins.min() == 0 and mins.max() == 389

# Build daily arrays using explicit per-session lookups (robust to missing bars)
def per_session(col, minute):
    out = np.full(n_sess, np.nan)
    sel = mins == minute
    out[sess[sel]] = col[sel]
    return out

def last_of_session(col):
    out = np.full(n_sess, np.nan)
    for k in range(n_sess):
        idx = np.where(sess == k)[0]
        if len(idx):
            out[k] = col[idx[-1]]
    return out

o0930 = per_session(opens[:, 0], 0)
c0930 = per_session(closes[:, 0], 0)
p1459 = per_session(closes[:, 0], 329)   # 14:59 bar close = 15:00:00
o1500 = per_session(opens[:, 0], 330)
p1529 = per_session(closes[:, 0], 359)
o1530 = per_session(opens[:, 0], 360)
p1558 = per_session(closes[:, 0], 388)   # 15:58 close = 15:59:00
c1559 = per_session(closes[:, 0], 389)   # 16:00 close
c_last = last_of_session(closes[:, 0])
qc_last = last_of_session(closes[:, 1])
oq0930 = per_session(opens[:, 1], 0)
cq0930 = per_session(closes[:, 1], 0)
q1459 = per_session(closes[:, 1], 329)
qo1500 = per_session(opens[:, 1], 330)
q1529 = per_session(closes[:, 1], 359)
qo1530 = per_session(opens[:, 1], 360)
q1558 = per_session(closes[:, 1], 388)
qc1559 = per_session(closes[:, 1], 389)
b0930 = per_session(closes[:, 2], 0)

df = pd.DataFrame({
    "date": uniq,
    "o": o0930, "c1": c0930, "p1459": p1459, "o1500": o1500,
    "p1529": p1529, "o1530": o1530, "p1558": p1558, "c": c_last,
    "t_o": oq0930, "t_c1": cq0930, "t_p1459": q1459, "t_o1500": qo1500,
    "t_p1529": q1529, "t_o1530": qo1530, "t_p1558": q1558, "t_c": qc_last,
    "bil": b0930,
})
df = df.dropna(subset=["c", "p1459"]).reset_index(drop=True)

# regime: prior close vs 165-day SMA of prior closes (QQQ)
df["sma165"] = df["c"].rolling(165).mean().shift(1)
df["ma20"] = df["c"].rolling(20).mean().shift(1)
df["risk_on"] = df["c"].shift(1) > df["sma165"]
df["prev_c"] = df["c"].shift(1)

# ex-ante runup known at 14:59 close (QQQ) and tradable late windows
df["run60"] = df["p1459"] / df["prev_c"] - 1.0
df["run30"] = df["p1529"] / df["prev_c"] - 1.0
df["late60"] = df["p1558"] / df["o1500"] - 1.0     # enter 15:00 open, exit 15:59 open
df["late30"] = df["p1558"] / df["o1530"] - 1.0     # enter 15:30 open, exit 15:59 open
df["late60_full"] = df["c"] / df["o1500"] - 1.0    # includes final minute (not sellable in harness)
df["late30_full"] = df["c"] / df["o1530"] - 1.0
df["on_next"] = df["o"].shift(-1) / df["c"] - 1.0   # 16:00 close -> next open
df["day"] = df["c"] / df["prev_c"] - 1.0

for col in ["late60", "late30", "late60_full", "late30_full"]:
    df["t_" + col] = df["t_p1558" if col.startswith("late60") else "t_p1558"] / (
        df["t_o1500" if col.startswith("late60") else "t_o1530"]) - 1.0

df.to_pickle(HERE / "daily.pkl")

test = df[df["date"] >= pd.Timestamp("2017-01-03", tz="America/New_York")].copy()
print("sessions", len(df), "test sessions", len(test), test["date"].min(), test["date"].max())
print("risk_on share", test["risk_on"].mean())

def bucket_report(frame, name, retcol="late60"):
    r = frame[retcol].dropna()
    if len(r) < 3:
        return None
    t = r.mean() / (r.std(ddof=1) / np.sqrt(len(r)))
    return dict(bucket=name, n=len(r), mean_bp=r.mean()*1e4, med_bp=r.median()*1e4,
                hit=(r > 0).mean(), t=t)

rows = []
print("\n=== Last 60m (15:00->15:59) by runup decile, all days ===")
q = pd.qcut(test["run60"], 10, labels=False, duplicates="drop")
for k in range(10):
    m = q == k
    for col, tag in [("late60", "QQQ"), ("t_late60", "TQQQ")]:
        b = bucket_report(test[m], f"d{k}", col)
        if b:
            b["asset"] = tag
            b["run_lo"] = test.loc[m, "run60"].min()*100
            b["run_hi"] = test.loc[m, "run60"].max()*100
            rows.append(b)
print(pd.DataFrame(rows).to_string(index=False))

print("\n=== Last 60m by runup sign and regime ===")
for regime in [True, False]:
    for sgn in [1, -1]:
        m = (test["risk_on"] == regime) & (np.sign(test["run60"]) == sgn)
        for col, tag in [("late60", "QQQ"), ("t_late60", "TQQQ")]:
            b = bucket_report(test[m], f"regime={regime},sign={sgn}", col)
            if b:
                b["asset"] = tag
                rows.append(b)
print(pd.DataFrame(rows[-8:]).to_string(index=False))

print("\n=== Last 60m mean by runup bucket and regime ===")
tab = []
for regime in [True, False]:
    sub = test[test["risk_on"] == regime]
    qq = pd.qcut(sub["run60"], 5, labels=False, duplicates="drop")
    for k in range(5):
        m = qq == k
        tab.append(dict(regime=regime, q=k, n=m.sum(),
                        run_lo=sub.loc[m, "run60"].min()*100,
                        run_hi=sub.loc[m, "run60"].max()*100,
                        qqq_bp=sub.loc[m, "late60"].mean()*1e4,
                        tqqq_bp=sub.loc[m, "t_late60"].mean()*1e4,
                        qqq_hit=(sub.loc[m, "late60"] > 0).mean(),
                        tqqq_hit=(sub.loc[m, "t_late60"] > 0).mean()))
print(pd.DataFrame(tab).to_string(index=False))

print("\n=== Next overnight by runup quintile ===")
tab = []
for regime in [True, False]:
    sub = test[test["risk_on"] == regime]
    qq = pd.qcut(sub["run60"], 5, labels=False, duplicates="drop")
    for k in range(5):
        m = qq == k
        r = sub.loc[m, "on_next"].dropna()
        tab.append(dict(regime=regime, q=k, n=len(r),
                        run_lo=sub.loc[m, "run60"].min()*100,
                        run_hi=sub.loc[m, "run60"].max()*100,
                        qqq_on_bp=r.mean()*1e4, hit=(r > 0).mean()))
print(pd.DataFrame(tab).to_string(index=False))

print("\n=== Last 60m by year: mean bp (QQQ / TQQQ), n ===")
tab = []
for y, sub in test.groupby(test["date"].dt.year):
    r = sub["late60"].dropna()
    t = sub["t_late60"].dropna()
    tab.append(dict(year=y, n=len(r), qqq_bp=r.mean()*1e4, tqqq_bp=t.mean()*1e4,
                    qqq_hit=(r > 0).mean(), t_hit=(t > 0).mean()))
print(pd.DataFrame(tab).to_string(index=False))
