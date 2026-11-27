"""Screen late-day overlay rules on top of the round-1 winner (correct bar timing)."""
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
print(f"loaded {time.time()-T0:.1f}s")

qclose = wd["qclose"]
prev_c = pd.Series(qclose).shift(1).to_numpy()
p1459 = lib.session_series(closes[:, 0], wd["sess"], mins, n_sess, 329)
p1529 = lib.session_series(closes[:, 0], wd["sess"], mins, n_sess, 359)
run60 = p1459 / prev_c - 1.0
run30 = p1529 / prev_c - 1.0

# tradable windows: weights[329..387] -> 15:00 open .. 15:59 open
ENTRY, EXIT = 329, 388

def apply(w, mask, long, entry=ENTRY, exit_=EXIT, overnight=True, protect=True):
    for k in np.where(mask)[0]:
        a, b = starts[k], ends[k]
        if b <= a:
            continue
        m = mins[a:b]
        if not ((m >= entry) & (m < exit_)).any():
            continue
        sel = (m >= entry) & (m < exit_)
        if long:
            w[a:b][sel, 1] = 1.0
            w[a:b][sel, 2] = 0.0
        else:
            w[a:b][sel, 1] = 0.0
            w[a:b][sel, 2] = 1.0
        stopped = protect and base[b - 1, 1] < 0.5
        last_ok = (m == exit_).any()
        if overnight and not stopped:
            # set weight at exit_ and at final bar to long
            ii = np.where(m == exit_)[0]
            if len(ii):
                w[a + ii[0], 1] = 1.0
                w[a + ii[0], 2] = 0.0
            w[b - 1, 1] = 1.0
            w[b - 1, 2] = 0.0
        elif not overnight:
            ii = np.where(m == exit_)[0]
            if len(ii):
                w[a + ii[0], 1] = 0.0
                w[a + ii[0], 2] = 1.0
            w[b - 1, 1] = 0.0
            w[b - 1, 2] = 1.0
    return w

def run_one(w, tag):
    row = {}
    for start, win in [("2017-01-03", "10y"), ("2021-10-25", "5y")]:
        r = bt.run(ts, opens, closes, w, start, band=0.02, slippage_bps=1.0)
        row[win] = bt.stats(r, 252 * 390)
    print(f"{tag:46s} 10y {row['10y']['cagr']*100:6.2f}/{row['10y']['max_drawdown']*100:5.2f}"
          f" 5y {row['5y']['cagr']*100:6.2f}/{row['5y']['max_drawdown']*100:5.2f}"
          f" fills {row['10y']['fills']:5d}  [{time.time()-T0:.0f}s]", flush=True)
    return row

print("base winner")
run_one(base, "winner")

print("\n--- skip last hour when down into the close (keep overnight) ---")
for x in [0.0, 0.005, 0.01, 0.015, 0.02]:
    m = wd["risk_on"] & (run60 < -x)
    w = apply(base.copy(), m, False, overnight=True)
    run_one(w, f"skip60 run60<-{x*100:.2f}% n={m.sum()}")

print("\n--- skip last hour when down (flat overnight too) ---")
for x in [0.0, 0.01, 0.02]:
    m = wd["risk_on"] & (run60 < -x)
    w = apply(base.copy(), m, False, overnight=False)
    run_one(w, f"skip60+night run60<-{x*100:.2f}%")

print("\n--- risk-off: buy last hour after late rally (flat overnight) ---")
for x in [0.0, 0.005, 0.01, 0.015, 0.02, 0.025, 0.03]:
    m = (~wd["risk_on"]) & (run60 > x)
    w = apply(base.copy(), m, True, overnight=False)
    run_one(w, f"offrally60 run60>{x*100:.2f}% n={m.sum()}")

print("\n--- risk-off: buy last hour after late rally (hold overnight) ---")
for x in [0.01, 0.015, 0.02, 0.03]:
    m = (~wd["risk_on"]) & (run60 > x)
    w = apply(base.copy(), m, True, overnight=True)
    run_one(w, f"offrally60+night run60>{x*100:.2f}%")

print("\n--- risk-off: buy last 30m after late rally (flat overnight) ---")
for x in [0.01, 0.015, 0.02, 0.025, 0.03]:
    m = (~wd["risk_on"]) & (run30 > x)
    w = apply(base.copy(), m, True, entry=359, exit_=388, overnight=False)
    run_one(w, f"offrally30 run30>{x*100:.2f}% n={m.sum()}")

print("\n--- reversed controls ---")
m = wd["risk_on"] & (run60 > 0)
w = apply(base.copy(), m, False, overnight=True)
run_one(w, "skip last hour on UP days")
m = (~wd["risk_on"]) & (run60 < -0.01)
w = apply(base.copy(), m, True, overnight=False)
run_one(w, "buy last hour on DOWN risk-off days")
