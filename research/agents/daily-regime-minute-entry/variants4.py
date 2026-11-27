"""Variant 4: stress the intraday stop (yearly, 5bp, variants, attribution)."""
import numpy as np
import pandas as pd

import strat_lib as sl
import bt

A = sl.load_arrays()
ts, dates, first, last = A["ts"], A["dates"], A["first"], A["last"]
oc, oo, oh = A["closes"], A["opens"], A["highs"]
reg, dc, sma, _, _, _ = sl.daily_regime(ts, oc[:, 0], 165)
n = len(ts)
c = oc[:, 1]


def make_weights(hold):
    w = np.zeros((n, 3))
    w[:, 1] = hold.astype(float)
    w[:, 2] = 1.0 - w[:, 1]
    return w


def stop_rule(x=0.04, ref="open", reenter="close", after_open=0, before_close=0):
    hold = np.zeros(n, bool)
    prev_close = np.r_[np.nan, c[:-1]]
    for f, l in zip(first, last):
        state = bool(reg[f])
        stopped = False
        base = oo[f, 1] if ref == "open" else prev_close[f]
        for i in range(f, l + 1):
            mi = i - f
            if state and after_open <= mi < (l - f - before_close) and c[i] < base * (1 - x):
                state = False
                stopped = True
            if stopped and reenter == "vwap_then":
                pass
            hold[i] = state
        if reg[l] and reenter != "never":
            hold[l - 1:l + 1] = True
    return hold


def report(name, hold, slip=1.0):
    w = make_weights(hold)
    out = {}
    for start in (sl.START10, sl.START5):
        r = bt.run(ts, A["opens"], oc, w, start, band=0.02, slippage_bps=slip)
        s = bt.stats(r, 252 * 390)
        i = bt.start_index(ts, start)
        b = bt.benchmark(oc[i:, 1], ts[i:], 252 * 390)
        out[start] = (s, r, b)
        print(f"  {start[:4]}@{slip}bp  CAGR {s['cagr']*100:6.2f}%  DD {s['max_drawdown']*100:5.2f}%  "
              f"Sharpe {s['sharpe']:4.2f}  fills {s['fills']:5,d}  turn {s['turnover']:8.0f}x")
    return out


ctrl = np.zeros(n, bool)
ctrl[:] = reg
h4 = stop_rule(0.04)
h4_never = stop_rule(0.04, reenter="never")
h5_never = stop_rule(0.05, reenter="never")
h4_trail = None

# trailing stop from the day's high
def trailing_rule(x=0.04):
    hold = np.zeros(n, bool)
    for f, l in zip(first, last):
        state = bool(reg[f])
        hi = -np.inf
        for i in range(f, l + 1):
            hi = max(hi, oh[i, 1])
            if state and c[i] < hi * (1 - x):
                state = False
            hold[i] = state
        if reg[l]:
            hold[l - 1:l + 1] = True
    return hold


print("CONTROL")
out_c = report("ctrl", ctrl)
print("STOP4 close re-entry")
out_4 = report("stop4", h4)
print("STOP4 5bp")
report("stop4-5bp", h4, slip=5.0)
print("STOP5 5bp")
report("stop5-5bp", stop_rule(0.05), slip=5.0)
print("STOP4 no overnight re-entry")
report("stop4never", h4_never)
print("STOP5 no overnight re-entry")
report("stop5never", h5_never)
print("TRAILING 4% from day high")
report("trail4", trailing_rule(0.04))

# yearly
i = bt.start_index(ts, sl.START10)
eqc = out_c[sl.START10][1]["equity"]
eq4 = out_4[sl.START10][1]["equity"]
yc = bt.yearly(ts[i:], eqc, oc[i:, 1])
y4 = bt.yearly(ts[i:], eq4, oc[i:, 1])
print("\nyear   control   stop4    diff    tqqq")
for y in yc:
    print(f"{y}  {yc[y]['strategy']*100:8.2f}% {y4[y]['strategy']*100:8.2f}% {100*(y4[y]['strategy']-yc[y]['strategy']):7.2f}%  {yc[y]['benchmark']*100:8.2f}%")
