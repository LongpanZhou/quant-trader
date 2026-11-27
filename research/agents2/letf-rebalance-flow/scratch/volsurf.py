"""Vol-scaled threshold robustness: multiplier and lookback."""
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
p1459 = lib.session_series(closes[:, 0], wd["sess"], mins, n_sess, 329)
run60 = p1459 / prev_c - 1.0
qret = pd.Series(wd["qclose"]).pct_change()

def apply(w, mask):
    for k in np.where(mask)[0]:
        a, b = starts[k], ends[k]
        if b <= a: continue
        m = mins[a:b]
        sel = (m >= 329) & (m < 388)
        if sel.any():
            w[a:b][sel, 1] = 1.0; w[a:b][sel, 2] = 0.0
        ii = np.where(m == 388)[0]
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
    print(f"{tag:36s} 1bp {a['cagr']*100:6.2f}/{a['max_drawdown']*100:5.2f} {c['cagr']*100:6.2f}/{c['max_drawdown']*100:5.2f}"
          f" | 5bp {b['cagr']*100:6.2f}/{b['max_drawdown']*100:5.2f} {d['cagr']*100:6.2f}/{d['max_drawdown']*100:5.2f}"
          f" [{time.time()-T0:.0f}s]", flush=True)

for look in [10, 20, 60]:
    sig = qret.rolling(look).std().shift(1).to_numpy()
    for k in ([0.5, 0.75, 1.0] if look == 20 else [0.75, 1.0]):
        m = (~wd["risk_on"]) & (run60 > k * sig)
        w = apply(base.copy(), m)
        ev(w, f"vol{look} k={k} n={m.sum()}")
