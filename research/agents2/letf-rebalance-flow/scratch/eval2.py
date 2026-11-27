"""Leaner robustness eval: 1bp/5bp only."""
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
n_sess = len(wd["dates"]); starts, ends = wd["starts"], wd["ends"]; mins = wd["mins"]
base = lib.base_winner_weights(ts, wd)
prev_c = pd.Series(wd["qclose"]).shift(1).to_numpy()
def ss(minute, asset=0):
    return lib.session_series(closes[:, asset], wd["sess"], mins, n_sess, minute)
p1459, p1529, p1558 = ss(329), ss(359), ss(388)
run60 = p1459 / prev_c - 1.0
qret = pd.Series(wd["qclose"]).pct_change()
sig20 = qret.rolling(20).std().shift(1).to_numpy()

def apply(w, mask, long, entry, exit_):
    for k in np.where(mask)[0]:
        a, b = starts[k], ends[k]
        if b <= a: continue
        m = mins[a:b]
        sel = (m >= entry) & (m < exit_)
        if sel.any():
            if long:
                w[a:b][sel, 1] = 1.0; w[a:b][sel, 2] = 0.0
            else:
                w[a:b][sel, 1] = 0.0; w[a:b][sel, 2] = 1.0
        ii = np.where(m == exit_)[0]
        if len(ii):
            i0 = a + ii[0]
            w[i0, 1] = 0.0; w[i0, 2] = 1.0; w[b - 1, 1] = 0.0; w[b - 1, 2] = 1.0
    return w

def ev(w, tag):
    row = {}
    for start, win in [("2017-01-03", "10y"), ("2021-10-25", "5y")]:
        for bp in (1.0, 5.0):
            r = bt.run(ts, opens, closes, w, start, band=0.02, slippage_bps=bp)
            row[(win, bp)] = bt.stats(r, 252 * 390)
    a, b, c, d = row[("10y",1.0)], row[("10y",5.0)], row[("5y",1.0)], row[("5y",5.0)]
    print(f"{tag:40s} 1bp {a['cagr']*100:6.2f}/{a['max_drawdown']*100:5.2f} {c['cagr']*100:6.2f}/{c['max_drawdown']*100:5.2f}"
          f" | 5bp {b['cagr']*100:6.2f}/{b['max_drawdown']*100:5.2f} {d['cagr']*100:6.2f}/{d['max_drawdown']*100:5.2f}"
          f" [{time.time()-T0:.0f}s]", flush=True)
    return row

print("30m entry with 15:00-15:30 confirmation")
for th in [0.015, 0.02]:
    m = (~wd["risk_on"]) & (run60 > th)
    w = apply(base.copy(), m, True, 359, 388)
    ev(w, f"rally30 >{th*100:.1f}% n={m.sum()}")

print("\nVol-scaled")
for k in [0.75, 1.0, 1.25]:
    m = (~wd["risk_on"]) & (run60 > k * sig20)
    w = apply(base.copy(), m, True, 329, 388)
    ev(w, f"rally >{k:.2f}*sig20 n={m.sum()}")

print("\nAblations")
m = run60 > 0.02
w = apply(base.copy(), m, True, 329, 388)
ev(w, f"all days >2% n={m.sum()} (no regime)")
m = (~wd["risk_on"]) & (run60 > 0.02)
wq = base.copy()
for k in np.where(m)[0]:
    a, b = starts[k], ends[k]
    mm = mins[a:b]
    sel = (mm >= 329) & (mm < 388)
    wq[a:b][sel, 0] = 1.0; wq[a:b][sel, 1] = 0.0
    ii = np.where(mm == 388)[0]
    if len(ii):
        i0 = a + ii[0]
        wq[i0, 0] = 0.0; wq[i0, 2] = 1.0; wq[b - 1, 0] = 0.0; wq[b - 1, 2] = 1.0
ev(wq, "rally >2% held in QQQ")
