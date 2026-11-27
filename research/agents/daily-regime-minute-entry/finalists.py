"""Finalist comparison: yearly, 5bp/10bp, sub-periods."""
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
qqq_d = oc[dlast, 0]
q_ma20 = np.r_[np.nan, pd.Series(qqq_d).rolling(20).mean().to_numpy()[:-1]]
day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, n]))
q_ma20_min = q_ma20[day_id]
qqq_c = oc[:, 0]


def make_weights(hold):
    w = np.zeros((n, 3))
    w[:, 1] = hold.astype(float)
    w[:, 2] = 1.0 - w[:, 1]
    return w


def stop_rule(x=0.04, arm_ma20=False):
    hold = np.zeros(n, bool)
    for f, l in zip(first, last):
        state = bool(reg[f])
        base = oo[f, 1]
        armed = (not arm_ma20) or (qqq_c[f] < q_ma20_min[f])
        for i in range(f, l + 1):
            if armed and state and c[i] < base * (1 - x):
                state = False
            hold[i] = state
    return hold


def full(name, hold):
    w = make_weights(hold)
    print(f"\n===== {name} =====")
    res = {}
    for slip in (1.0, 5.0, 10.0):
        for start in (sl.START10, sl.START5):
            r = bt.run(ts, A["opens"], oc, w, start, band=0.02, slippage_bps=slip)
            s = bt.stats(r, 252 * 390)
            i = bt.start_index(ts, start)
            b = bt.benchmark(oc[i:, 1], ts[i:], 252 * 390)
            res[(slip, start)] = (s, r, b)
            print(f"  {start[:4]} @{slip:4.1f}bp  CAGR {s['cagr']*100:6.2f}%  DD {s['max_drawdown']*100:5.2f}%  "
                  f"Sharpe {s['sharpe']:4.2f}  Sortino {s['sortino']:4.2f}  fills {s['fills']:5,d}  "
                  f"turn {s['turnover']:7.0f}x  end ${s['ending_equity']/1e6:.2f}M")
    return res


r_ctrl = full("control (no stop)", reg)
r_u = full("stop 4% ungated, out overnight", stop_rule(0.04))
r_g = full("stop 4% gated QQQ<MA20, out overnight", stop_rule(0.04, True))

# yearly for 1bp 10y
i = bt.start_index(ts, sl.START10)
for name, res in (("control", r_ctrl), ("stop4", r_u), ("stop4-gate", r_g)):
    s, r, b = res[(1.0, sl.START10)]
    y = bt.yearly(ts[i:], r["equity"], oc[i:, 1])
    print(f"\n{name} yearly:")
    print("  " + "  ".join(f"{k}:{v['strategy']*100:6.1f}/{v['benchmark']*100:6.1f}" for k, v in y.items()))

# sub-period stability: 2017-2019, 2020-2022, 2023-2026 (daily equity slices)
print("\nsub-period CAGR (geometric, using equity endpoints):")
for name, res in (("control", r_ctrl), ("stop4", r_u), ("stop4-gate", r_g)):
    s, r, b = res[(1.0, sl.START10)]
    eq = pd.Series(r["equity"], index=ts[i:])
    out = []
    for a, z in (("2017-01-03", "2019-12-31"), ("2020-01-02", "2022-12-30"), ("2023-01-03", "2026-10-23")):
        seg = eq[(eq.index >= pd.Timestamp(a, tz="America/New_York")) & (eq.index <= pd.Timestamp(z, tz="America/New_York"))]
        yrs = (seg.index[-1] - seg.index[0]).total_seconds() / (365.25 * 86400)
        out.append(f"{a[:4]}-{z[:4]}: {(seg.iloc[-1]/seg.iloc[0])**(1/yrs)-1:6.1%}")
    print(f"  {name:12s} " + "  ".join(out))
