"""Test overnight reversal overlays and entry timing."""
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, "research")
sys.path.insert(0, str(HERE / "scratch"))
import bt
import lib

T0 = time.time()
ts, opens, closes = lib.load_panel()
wd = lib.winner_daily(ts, opens, closes)
n_sess = len(wd["dates"])
starts, ends = wd["starts"], wd["ends"]
mins = wd["mins"]
base = lib.base_winner_weights(ts, wd)
print(f"loaded {time.time()-T0:.1f}s", flush=True)

qclose = wd["qclose"]
prev_c = pd.Series(qclose).shift(1).to_numpy()
p1459 = lib.session_series(closes[:, 0], wd["sess"], mins, n_sess, 329)
p1529 = lib.session_series(closes[:, 0], wd["sess"], mins, n_sess, 359)
p1439 = lib.session_series(closes[:, 0], wd["sess"], mins, n_sess, 269)
p1409 = lib.session_series(closes[:, 0], wd["sess"], mins, n_sess, 239)
p1429 = lib.session_series(closes[:, 0], wd["sess"], mins, n_sess, 299)
p1359 = lib.session_series(closes[:, 0], wd["sess"], mins, n_sess, 269)
p1329 = lib.session_series(closes[:, 0], wd["sess"], mins, n_sess, 239)
p1558 = lib.session_series(closes[:, 0], wd["sess"], mins, n_sess, 388)
run60 = p1459 / prev_c - 1.0
run30 = p1529 / prev_c - 1.0
run1429 = p1429 / prev_c - 1.0
run1359 = p1359 / prev_c - 1.0
run1329 = p1329 / prev_c - 1.0
late60 = p1558 / p1459 - 1.0   # QQQ, 15:00->15:59 approx (uses closes 14:59/15:58)

def run_one(w, tag):
    row = {}
    for start, win in [("2017-01-03", "10y"), ("2021-10-25", "5y")]:
        r = bt.run(ts, opens, closes, w, start, band=0.02, slippage_bps=1.0)
        row[win] = bt.stats(r, 252 * 390)
    print(f"{tag:52s} 10y {row['10y']['cagr']*100:6.2f}/{row['10y']['max_drawdown']*100:5.2f}"
          f" 5y {row['5y']['cagr']*100:6.2f}/{row['5y']['max_drawdown']*100:5.2f}"
          f" fills {row['10y']['fills']:5d}  [{time.time()-T0:.0f}s]", flush=True)
    return row

def apply(w, mask, long, entry, exit_, overnight):
    for k in np.where(mask)[0]:
        a, b = starts[k], ends[k]
        if b <= a:
            continue
        m = mins[a:b]
        sel = (m >= entry) & (m < exit_)
        if sel.any():
            if long:
                w[a:b][sel, 1] = 1.0
                w[a:b][sel, 2] = 0.0
            else:
                w[a:b][sel, 1] = 0.0
                w[a:b][sel, 2] = 1.0
        ii = np.where(m == exit_)[0]
        if len(ii):
            i0 = a + ii[0]
            if overnight == "flat":
                w[i0, 1] = 0.0; w[i0, 2] = 1.0
                w[b - 1, 1] = 0.0; w[b - 1, 2] = 1.0
            elif overnight == "long_next_open":
                w[i0, 1] = 1.0; w[i0, 2] = 0.0
                w[b - 1, 1] = 1.0; w[b - 1, 2] = 0.0
            elif overnight == "flat_then_long":
                # sell at 15:59, re-enter next session open (weight at last bar)
                w[i0, 1] = 0.0; w[i0, 2] = 1.0
                w[b - 1, 1] = 1.0; w[b - 1, 2] = 0.0
            elif overnight == "long_now":
                w[i0, 1] = 1.0; w[i0, 2] = 0.0
                w[b - 1, 1] = 1.0; w[b - 1, 2] = 0.0
    return w

print("\n=== A. risk-on: skip overnight after a strong last hour (sell 15:59, re-enter next open) ===")
for x in [0.005, 0.01, 0.015, 0.02, 0.025]:
    m = wd["risk_on"] & (late60 > x)
    w = apply(base.copy(), m, False, 329, 388, "flat_then_long")
    run_one(w, f"skip overnight late60>{x*100:.1f}% n={m.sum()}")

print("\n=== B. risk-on: skip overnight after a strong day (run60) ===")
for x in [0.01, 0.015, 0.02, 0.025, 0.03]:
    m = wd["risk_on"] & (run60 > x)
    w = apply(base.copy(), m, False, 329, 388, "flat_then_long")
    run_one(w, f"skip overnight run60>{x*100:.1f}% n={m.sum()}")

print("\n=== C. risk-off: buy overnight after a down day (last hour and overnight) ===")
for lo in [-0.03, -0.02, -0.015, -0.01, -0.005]:
    m = (~wd["risk_on"]) & (run60 < lo)
    w = apply(base.copy(), m, True, 329, 388, "long_next_open")
    run_one(w, f"buy from 15:00+overnight run60<{lo*100:.1f}% n={m.sum()}")

print("\n=== D. risk-off: buy only the overnight after a down day (enter 15:59) ===")
for lo in [-0.03, -0.02, -0.015, -0.01, -0.005]:
    m = (~wd["risk_on"]) & (run60 < lo)
    w = apply(base.copy(), m, True, 388, 388, "long_next_open")
    run_one(w, f"overnight only run60<{lo*100:.1f}% n={m.sum()}")

print("\n=== E. entry-time comparison for risk-off rally (>2%) ===")
for entry, sig, tag in [(329, run60, "15:00"), (299, run1429, "14:30"),
                        (269, run1359, "14:00"), (239, run1329, "13:30")]:
    m = (~wd["risk_on"]) & (sig > 0.02)
    w = apply(base.copy(), m, True, entry, 388, "flat")
    run_one(w, f"rally >2% from {tag} n={m.sum()}")

print("\n=== F. combined: rally >2.5% last hour + skip overnight after risk-on late60>1.5% ===")
m1 = (~wd["risk_on"]) & (run60 > 0.025)
w = apply(base.copy(), m1, True, 329, 388, "flat")
m2 = wd["risk_on"] & (late60 > 0.015)
w = apply(w, m2, False, 329, 388, "flat_then_long")
run_one(w, "combo")

print("\n=== G. standalone rally trade (BIL base) ===")
w = np.zeros_like(base); w[:, 2] = 1.0
m = (~wd["risk_on"]) & (run60 > 0.02)
w = apply(w, m, True, 329, 388, "flat")
run_one(w, "standalone rally >2%")
m = (~wd["risk_on"]) & (run60 > 0.03)
w = np.zeros_like(base); w[:, 2] = 1.0
w = apply(w, m, True, 329, 388, "flat")
run_one(w, "standalone rally >3%")
