"""Exploration: reproduce daily baseline, inspect drawdown episodes, data shape."""
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, "research")
import bt

START10, START5, END = "2017-01-03", "2021-10-25", "2026-10-23"

ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), START10, END, "1D")
print("daily bars", len(ts), ts[0], ts[-1])

q = closes[:, 0]
sma = pd.Series(q).rolling(165).mean().to_numpy()
# regime from prior close
reg = np.zeros(len(ts), dtype=bool)
reg[1:] = (q[:-1] > sma[:-1])

w = np.zeros((len(ts), 3))
w[:, 0] = np.where(reg, 0.0, 0.0)
w[:, 1] = np.where(reg, 1.0, 0.0)
w[:, 2] = np.where(reg, 0.0, 1.0)

for start in (START10, START5):
    r = bt.run(ts, opens, closes, w, start, band=0.02, slippage_bps=1.0)
    s = bt.stats(r, 252)
    i = bt.start_index(ts, start)
    b = bt.benchmark(closes[i:, 1], ts[i:], 252)
    bt.print_summary(f"baseline {start}", s, b)

# Yearly for 10y
r = bt.run(ts, opens, closes, w, START10, band=0.02, slippage_bps=1.0)
i = bt.start_index(ts, START10)
eq = r["equity"]
peak = np.maximum.accumulate(eq)
dd = eq / peak - 1
# worst drawdown windows
print("\nworst dd")
for k in range(5):
    j = int(np.argmin(dd))
    print(ts[j], f"dd {dd[j]*100:.1f}%", f"eq {eq[j]:,.0f}")
    # find preceding peak
    p = int(np.argmax(eq[:j + 1]))
    print("  peak", ts[p], f"{eq[p]:,.0f}")
    dd = dd.copy()
    dd[max(0, p - 5):j + 5] = 0

yr = bt.yearly(ts[i:], eq, closes[i:, 1])
print("\nyear  strat   bench")
for y, v in yr.items():
    print(f"{y}  {v['strategy']*100:7.2f}% {v['benchmark']*100:7.2f}%")

# exposure distribution: fraction of days regime on
print("\nregime on days:", reg[i:].mean())
# monthly return of baseline
sr = pd.Series(eq, index=ts[i:]).resample("ME").last().pct_change().dropna()
print("\nworst months")
print((sr.sort_values().head(10) * 100).round(1))
