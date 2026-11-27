"""Drawdown anatomy of the 1m-marked daily-regime control."""
import numpy as np
import pandas as pd

import strat_lib as sl
import bt

A = sl.load_arrays()
ts, dates, first, last = A["ts"], A["dates"], A["first"], A["last"]
c = A["closes"][:, 1]
reg, dc, sma, _, _, _ = sl.daily_regime(ts, A["closes"][:, 0], 165)
n = len(ts)
w = np.zeros((n, 3))
w[:, 1] = reg.astype(float)
w[:, 2] = 1 - w[:, 1]
r = bt.run(ts, A["opens"], A["closes"], w, sl.START10, band=0.02, slippage_bps=1.0)
eq = r["equity"]
i0 = bt.start_index(ts, sl.START10)
tsx = ts[i0:]
eqx = eq

peak = np.maximum.accumulate(eqx)
dd = eqx / peak - 1
j = int(np.argmin(dd))
p = int(np.argmax(eqx[:j + 1]))
print(f"max DD {dd[j]*100:.2f}%  peak {tsx[p]} eq {eqx[p]:,.0f}  trough {tsx[j]} eq {eqx[j]:,.0f}")

# all dd episodes deeper than 20%
print("\nepisodes > 18%:")
in_ep = False
for k in range(len(dd)):
    if dd[k] < -0.18 and not in_ep:
        in_ep = True
        start = k
    elif dd[k] >= -0.02 and in_ep:
        in_ep = False
        seg = dd[start:k]
        t = int(np.argmin(seg)) + start
        print(f"  {tsx[start].date()} -> trough {tsx[t].date()} {seg.min()*100:6.2f}%  recover {tsx[k].date()}"
              f"  len {(k-start)} bars")

# worst 12 days
d_eq = pd.Series(eqx, index=tsx)
day_last_eq = d_eq.groupby(d_eq.index.date).last()
day_ret = day_last_eq.pct_change()
print("\nworst 12 close-to-close days:")
print((day_ret.sort_values().head(12) * 100).round(2).to_string())
print("\nbest 8 days:")
print((day_ret.sort_values().tail(8) * 100).round(2).to_string())

# intraday trough depth from prior close on regime-on days, for days where eq fell > 5%
print("\ndays with close-to-close < -5% and their intraday minimum:")
for t, v in day_ret[day_ret < -0.05].items():
    k = int(np.flatnonzero(np.array([d == t for d in dates[i0:]]) | False)[0]) if False else None
print("(skipped)")

# overnight vs intraday contribution of the control equity: use daily open marks
# reconstruct: equity at each day's open (before trade) vs close
o = A["opens"][:, 1]
day_open_eq = pd.Series(eqx, index=tsx).groupby(pd.Series(tsx).dt.date).first()
day_close_eq = pd.Series(eqx, index=tsx).groupby(pd.Series(tsx).dt.date).last()
print("\nidentity check: eq at first bar vs last bar per day equal?", np.allclose(day_open_eq, day_close_eq, rtol=1e-9))
