"""Variant 7: ATR-scaled stop, short-MA arming gate, sub-period stability."""
import numpy as np
import pandas as pd

import strat_lib as sl
import bt

A = sl.load_arrays()
ts, dates, first, last = A["ts"], A["dates"], A["first"], A["last"]
oc, oo, oh, ol = A["closes"], A["opens"], A["highs"], A["lows"]
reg, dc, sma, dts, dfirst, dlast = sl.daily_regime(ts, oc[:, 0], 165)
n = len(ts)
c = oc[:, 1]

# daily TQQQ series (from minute panel) to compute ATR20 / MA20 / MA50
tq_d = c[dlast]
tr = np.maximum(oh[dlast, 1] - ol[dlast, 1],
                np.maximum(np.abs(oh[dlast, 1] - np.r_[np.nan, tq_d[:-1]]),
                           np.abs(ol[dlast, 1] - np.r_[np.nan, tq_d[:-1]])))
atr20 = pd.Series(tr).rolling(20).mean().to_numpy()
ma20 = pd.Series(tq_d).rolling(20).mean().to_numpy()
ma50 = pd.Series(tq_d).rolling(50).mean().to_numpy()

day_id = np.repeat(np.arange(len(dfirst)), np.diff(np.r_[dfirst, n]))
atr_min = np.r_[np.nan, atr20[:-1]][day_id]
ma20_min = np.r_[np.nan, ma20[:-1]][day_id]
ma50_min = np.r_[np.nan, ma50[:-1]][day_id]
qqq_c = oc[:, 0]
qqq_d = qqq_c[dlast]
q_ma20 = np.r_[np.nan, pd.Series(qqq_d).rolling(20).mean().to_numpy()[:-1]][day_id]
q_ma50 = np.r_[np.nan, pd.Series(qqq_d).rolling(50).mean().to_numpy()[:-1]][day_id]


def make_weights(hold):
    w = np.zeros((n, 3))
    w[:, 1] = hold.astype(float)
    w[:, 2] = 1.0 - w[:, 1]
    return w


def stop_rule(x=None, atr_k=None, arm=None, arm_buf=0.0):
    hold = np.zeros(n, bool)
    for f, l in zip(first, last):
        state = bool(reg[f])
        base = oo[f, 1]
        thr = x if x is not None else atr_k * atr_min[f]
        if arm is None:
            armed = True
        elif arm == "qma20":
            armed = qqq_c[f] < q_ma20[f] * (1 + arm_buf)
        elif arm == "qma50":
            armed = qqq_c[f] < q_ma50[f] * (1 + arm_buf)
        elif arm == "tma20":
            armed = c[f] < ma20_min[f] * (1 + arm_buf)
        if not np.isfinite(thr):
            thr = 0.05
        for i in range(f, l + 1):
            if armed and state and c[i] < base * (1 - thr):
                state = False
            hold[i] = state
    return hold


def line(name, hold, slip=1.0):
    w = make_weights(hold)
    row = []
    for start in (sl.START10, sl.START5):
        r = bt.run(ts, A["opens"], oc, w, start, band=0.02, slippage_bps=slip)
        s = bt.stats(r, 252 * 390)
        row.append(f"{s['cagr']*100:6.2f}%/{s['max_drawdown']*100:5.2f}% sh{s['sharpe']:4.2f} f{s['fills']:5d}")
    print(f"{name:28s} 10y {row[0]} | 5y {row[1]}")


print("== fixed stop ==  (control 46.63/58.76 | 36.14/42.17)")
for x in (0.03, 0.035, 0.04, 0.045, 0.05):
    line(f"fixed {x*100:.1f}%", stop_rule(x=x))

print("\n== ATR20-scaled stop ==")
for k in (0.8, 1.0, 1.2, 1.5):
    line(f"atr {k:.1f}x", stop_rule(atr_k=k))

print("\n== fixed 4% + arming gate ==")
for arm, buf in (("qma20", 0.0), ("qma20", 0.02), ("qma50", 0.0), ("qma50", 0.02), ("tma20", 0.0)):
    line(f"4% arm {arm}+{buf:.2f}", stop_rule(x=0.04, arm=arm, arm_buf=buf))

print("\n== atr 1.2 + arming ==")
for arm, buf in (("qma20", 0.0), ("qma50", 0.0)):
    line(f"atr1.2 arm {arm}", stop_rule(atr_k=1.2, arm=arm))
