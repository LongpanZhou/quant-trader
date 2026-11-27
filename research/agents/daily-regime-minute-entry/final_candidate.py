"""Final candidate: yearly, costs, sub-periods, event stats, re-entry variants."""
import numpy as np
import pandas as pd

import strat_lib as sl
import bt

A = sl.load_arrays()
ts, dates, first, last = A["ts"], A["dates"], A["first"], A["last"]
oc, oo = A["closes"], A["opens"]
reg, dc, sma, dts, dfirst, dlast = sl.daily_regime(ts, oc[:, 0], 165)
n = len(ts)
c = oc[:, 1]
qqq_c = oc[:, 0]
qqq_d = oc[dlast, 0]
ma20 = pd.Series(qqq_d).rolling(20).mean().to_numpy()
day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, n]))
ma20_min = np.r_[np.nan, ma20[:-1]][day_id]


def make_weights(hold):
    w = np.zeros((n, 3))
    w[:, 1] = hold.astype(float)
    w[:, 2] = 1.0 - w[:, 1]
    return w


def rule(x=0.04, buf=0.01, recover=False, lockdays=0):
    hold = np.zeros(n, bool)
    lock = 0
    for f, l in zip(first, last):
        state = bool(reg[f]) and lock == 0
        base = oo[f, 1]
        armed = qqq_c[f] < ma20_min[f] * (1 + buf)
        stopped = False
        for i in range(f, l + 1):
            if armed and state and c[i] < base * (1 - x):
                state = False
                stopped = True
            if stopped and recover and c[i] > base:
                state = True
                stopped = False
            hold[i] = state
        if lock > 0:
            lock -= 1
        if stopped and lockdays:
            lock = lockdays
    return hold


def full(name, hold, mark="1m"):
    w = make_weights(hold)
    print(f"\n===== {name} =====")
    out = {}
    for slip in (1.0, 5.0, 10.0):
        for start in (sl.START10, sl.START5):
            r = bt.run(ts, A["opens"], oc, w, start, band=0.02, slippage_bps=slip)
            s = bt.stats(r, 252 * 390)
            i = bt.start_index(ts, start)
            b = bt.benchmark(oc[i:, 1], ts[i:], 252 * 390)
            eq = pd.Series(r["equity"], index=ts[i:])
            deq = eq.groupby(eq.index.date).last().to_numpy()
            peak = np.maximum.accumulate(deq)
            ddd = float(-(deq / peak - 1).min())
            out[(slip, start)] = (s, r, b)
            print(f"  {start[:4]} @{slip:4.1f}bp  CAGR {s['cagr']*100:6.2f}%  DD {s['max_drawdown']*100:5.2f}% (daily {ddd*100:5.2f}%)  "
                  f"Sharpe {s['sharpe']:4.2f}  fills {s['fills']:5,d}  turn {s['turnover']:7.0f}x  end ${s['ending_equity']/1e6:.2f}M")
    return out


base = rule()
out = full("FINAL: 4% stop, QQQ<MA20+1% armed, out overnight", base)

i = bt.start_index(ts, sl.START10)
for start in (sl.START10, sl.START5):
    s, r, b = out[(1.0, start)]
    j = bt.start_index(ts, start)
    y = bt.yearly(ts[j:], r["equity"], oc[j:, 1])
    print(f"\nyearly {start[:4]}:")
    for k, v in y.items():
        print(f"  {k}: strat {v['strategy']*100:8.2f}%  tqqq {v['benchmark']*100:8.2f}%")

s, r, b = out[(1.0, sl.START10)]
eq = pd.Series(r["equity"], index=ts[i:])
print("\nsub-periods:")
for a, z in (("2017-01-03", "2019-12-31"), ("2020-01-02", "2022-12-30"), ("2023-01-03", "2026-10-23")):
    seg = eq[(eq.index >= pd.Timestamp(a, tz="America/New_York")) & (eq.index <= pd.Timestamp(z, tz="America/New_York"))]
    yrs = (seg.index[-1] - seg.index[0]).total_seconds() / (365.25 * 86400)
    dd = float(-(seg / seg.cummax() - 1).min())
    print(f"  {a[:4]}-{z[:4]}: CAGR {(seg.iloc[-1]/seg.iloc[0])**(1/yrs)-1:6.1%}  DD {dd*100:5.1f}%")

print("\nvariants:")
full("recover re-entry same day", rule(recover=True))
full("2-day lockout", rule(lockdays=2))
full("no gate (ungated 4%)", rule(buf=99))
