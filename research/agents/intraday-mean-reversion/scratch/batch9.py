"""Batch 9: intraday trigger vs close-only; gap effect by year."""
import numpy as np
import pandas as pd

import engine3 as E

ts, o, c, feats = E.load_cached()
n = len(ts)
qqq, tqqq = feats["qqq"], feats["tqqq"]
date, bars, reg = feats["date"], feats["bars"], feats["regime"]
qpc, dopen = feats["qpc"], feats["dopen"]
i0 = E.bt.start_index(ts, E.START10)
mv = qqq / qpc - 1.0
gap = dopen / qpc - 1.0

print("=== overnight gap (TQQQ open/prev close) after QQQ close-down days, regime-on ===")
day_last = {d: i for i, d in enumerate(date)}
days = sorted(day_last)
rows = []
for k, d in enumerate(days[:-1]):
    i = day_last[d]
    if reg[i] <= 0.5:
        continue
    nd = days[k + 1]
    j = [x for x in range(i + 1, n) if date[x] == nd][0]
    mv_close = qqq[i] / qpc[i] - 1.0
    rows.append((mv_close, o[j, 1] / c[i, 1] - 1.0, c[[x for x in range(j, n) if date[x] == nd][-1], 1] / o[j, 1] - 1.0, d.year))
a = pd.DataFrame(rows, columns=["mv_close", "gap", "intraday_next", "year"])
for lo in (-0.05, -0.04, -0.035, -0.03, -0.025, -0.02, -0.015):
    m = a["mv_close"] <= lo
    print(f"  close <= {lo*100:5.1f}%  n={m.sum():4d}  gap {a.loc[m,'gap'].mean()*100:+.3f}%  "
          f"next intraday {a.loc[m,'intraday_next'].mean()*100:+.3f}%")
print("\n  by year for close <= -3%:")
mm = a["mv_close"] <= -0.03
for y, g in a[mm].groupby("year"):
    print(f"   {y}: n={len(g):2d} gap {g['gap'].mean()*100:+.3f}% next_intraday {g['intraday_next'].mean()*100:+.3f}%")

print("\n=== stop_bar_min sweep (stop 3%) ===")
for k in (0, 24, 48, 66, 70, 74):
    p = dict(signal="none", base=1.0, entry=0, exit=0, stop_prev=0.03, stop_bar_min=k)
    out, _ = E.run_one(ts, o, c, feats, p, slip=1.0, verbose=False)
    s10, s5 = out["10y"]["stats"], out["5y"]["stats"]
    print(f"  from bar {k:2d} ({9*60+30+k*5:4d} ET)  10y {s10['cagr']*100:6.2f}/{s10['max_drawdown']*100:5.2f} "
          f"sh {s10['sharpe']:.2f} fills {s10['fills']:4d} | 5y {s5['cagr']*100:6.2f}/{s5['max_drawdown']*100:5.2f}")

print("\n=== threshold sweep with close-only (bar>=74) ===")
for x in (0.02, 0.025, 0.03, 0.035, 0.04):
    p = dict(signal="none", base=1.0, entry=0, exit=0, stop_prev=x, stop_bar_min=74)
    out, _ = E.run_one(ts, o, c, feats, p, slip=1.0, verbose=False)
    s10, s5 = out["10y"]["stats"], out["5y"]["stats"]
    print(f"  {x*100:4.1f}%  10y {s10['cagr']*100:6.2f}/{s10['max_drawdown']*100:5.2f} fills {s10['fills']:4d}"
          f" | 5y {s5['cagr']*100:6.2f}/{s5['max_drawdown']*100:5.2f}")
