"""Final validation: grid, walk-forward, DD anatomy for the shipped strategy."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import strategy as S  # noqa: E402

RULE = "5min"
S.RULE = RULE
ts, o, c, feats = S.prepare(RULE)
n = len(ts)
print("bars", n, "regime-on share", round(feats["regime_on"], 3))

rows = []
for stop in (0.010, 0.015, 0.020, 0.0225, 0.025, 0.0275, 0.030, 0.0325, 0.035, 0.040, 0.050, 1.0):
    w, stops = S.make_weights(feats, n, stop)
    row = {"stop": stop, "stops": stops}
    for slip in (1.0, 5.0):
        for start, key in ((S.START10, "10y"), (S.START5, "5y")):
            s, b, res, i0 = S.metrics(ts, o, c, w, start, slip)
            row[f"{key}_{slip:.0f}bp"] = (s["cagr"], s["max_drawdown"], s["sharpe"], s["fills"], s["turnover"])
    rows.append(row)
    r = row
    print(f"stop {stop*100:5.2f}% events {stops:3d} | 10y {r['10y_1bp'][0]*100:6.2f}/{r['10y_1bp'][1]*100:5.2f}"
          f" sh {r['10y_1bp'][2]:.2f} 5bp {r['10y_5bp'][0]*100:6.2f}/{r['10y_5bp'][1]*100:5.2f}"
          f" | 5y {r['5y_1bp'][0]*100:6.2f}/{r['5y_1bp'][1]*100:5.2f} sh {r['5y_1bp'][2]:.2f}"
          f" 5bp {r['5y_5bp'][0]*100:6.2f}/{r['5y_5bp'][1]*100:5.2f}", flush=True)

print("\n=== walk-forward sub-periods (stop 3%, 1bp) ===")
w, _ = S.make_weights(feats, n, 0.030)
for a, bnd in (("2017-01-03", "2019-12-31"), ("2020-01-01", "2022-12-31"), ("2023-01-01", "2026-10-23")):
    dates_arr = np.array([d for d in ts.date])
    i0 = int(np.searchsorted(dates_arr, pd.Timestamp(a).date(), "left"))
    i0 = max(0, i0 - 1)
    i1 = int(np.searchsorted(dates_arr, pd.Timestamp(bnd).date(), "right")) - 1
    res = S.bt.simulate(ts[i0:i1 + 1], o[i0:i1 + 1], c[i0:i1 + 1], w[i0:i1 + 1], band=0.0, slippage_bps=1.0)
    st = S.bt.stats(res, S.BARS_PER_YEAR[RULE])
    bm = S.bt.benchmark(c[i0:i1 + 1, 1], ts[i0:i1 + 1], S.BARS_PER_YEAR[RULE])
    print(f"  {a}..{bnd}: strat {st['cagr']*100:6.2f}%/{st['max_drawdown']*100:5.2f}% sh {st['sharpe']:.2f}"
          f"   tqqq {bm['cagr']*100:6.2f}%/{bm['max_drawdown']*100:5.2f}%")

print("\n=== DD episodes (stop 3%) ===")
s, b, res, i0 = S.metrics(ts, o, c, w, S.START10, 1.0)
eq, t = res["equity"], res["ts"]
peak = np.maximum.accumulate(eq)
dd = eq / peak - 1
in_dd, st, eps = False, 0, []
for i in range(len(eq)):
    if not in_dd and dd[i] < -0.02:
        in_dd, st = True, i
    elif in_dd and dd[i] >= -1e-9:
        in_dd = False
        j = st + int(np.argmin(dd[st:i]))
        eps.append((dd[st:i].min(), t[st], t[j], t[i]))
for v, a, bb, cc in sorted(eps)[:6]:
    print(f"  {v*100:6.1f}%  {a.date()} -> {bb.date()} -> {cc.date()}")

print("\n=== yearly (stop 3%, 1bp) ===")
y = S.bt.yearly(res["ts"], res["equity"], c[i0:, 1])
for k, v in y.items():
    print(f"  {k}: strategy {v['strategy']*100:+8.1f}%   tqqq {v['benchmark']*100:+8.1f}%")
