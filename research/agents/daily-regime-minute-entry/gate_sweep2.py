"""Corrected gate sweep: MA20/MA50 on daily CLOSES (through prior close)."""
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
qqq_d = oc[last, 0]                      # daily CLOSES (correct)
ma20 = pd.Series(qqq_d).rolling(20).mean().to_numpy()
ma50 = pd.Series(qqq_d).rolling(50).mean().to_numpy()
day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, n]))
ma20_min = np.r_[np.nan, ma20[:-1]][day_id]
ma50_min = np.r_[np.nan, ma50[:-1]][day_id]


def make_weights(hold):
    w = np.zeros((n, 3))
    w[:, 1] = hold.astype(float)
    w[:, 2] = 1.0 - w[:, 1]
    return w


def rule(x=0.04, ma=None, buf=0.0):
    hold = np.zeros(n, bool)
    for f, l in zip(first, last):
        state = bool(reg[f])
        base = oo[f, 1]
        if ma is None:
            armed = True
        else:
            level = (ma20_min if ma == 20 else ma50_min)[f]
            armed = bool(level == level and qqq_c[f] < level * (1 + buf))
        for i in range(f, l + 1):
            if armed and state and c[i] < base * (1 - x):
                state = False
            hold[i] = state
    return hold


def line(name, hold):
    w = make_weights(hold)
    out = []
    for start in (sl.START10, sl.START5):
        r = bt.run(ts, A["opens"], oc, w, start, band=0.02, slippage_bps=1.0)
        s = bt.stats(r, 252 * 390)
        out.append(f"{s['cagr']*100:6.2f}%/{s['max_drawdown']*100:5.2f}% sh{s['sharpe']:4.2f} f{s['fills']:4d}")
    print(f"{name:26s} 10y {out[0]} | 5y {out[1]}")


print("control (no stop): 46.63/58.76 | 36.14/42.17")
print("\nungated:")
for x in (0.03, 0.035, 0.04, 0.045, 0.05, 0.06):
    line(f"stop {x*100:.1f}%", rule(x))
print("\nMA20 gate (close-based):")
for x in (0.03, 0.035, 0.04, 0.045, 0.05):
    line(f"stop {x*100:.1f}% ma20", rule(x, 20))
print("\nMA20 gate buffer:")
for buf in (0.01, 0.02, 0.03):
    line(f"stop4 ma20 buf{buf*100:.0f}%", rule(0.04, 20, buf))
print("\nMA50 gate:")
for x in (0.035, 0.04, 0.045):
    line(f"stop {x*100:.1f}% ma50", rule(x, 50))
print("\nMA20 gate + 5bp:")
for buf in (0.0, 0.01, 0.02):
    w = make_weights(rule(0.04, 20, buf))
    out = []
    for start in (sl.START10, sl.START5):
        r = bt.run(ts, A["opens"], oc, w, start, band=0.02, slippage_bps=5.0)
        s = bt.stats(r, 252 * 390)
        out.append(f"{s['cagr']*100:6.2f}%/{s['max_drawdown']*100:5.2f}%")
    print(f"  buf{buf*100:.0f}% 10y {out[0]} | 5y {out[1]}")
