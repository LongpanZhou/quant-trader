import sys
import numpy as np
import pandas as pd
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, "research")
sys.path.insert(0, str(HERE / "scratch"))
import bt
import lib

ts, opens, closes = lib.load_panel()
wd = lib.winner_daily(ts, opens, closes)
n_sess = len(wd["dates"]); starts, ends = wd["starts"], wd["ends"]; mins = wd["mins"]
base = lib.base_winner_weights(ts, wd)
prev_c = pd.Series(wd["qclose"]).shift(1).to_numpy()
p1459 = lib.session_series(closes[:, 0], wd["sess"], mins, n_sess, 329)
run60 = p1459 / prev_c - 1.0

def apply(w, mask, long, entry, exit_):
    for k in np.where(mask)[0]:
        a, b = starts[k], ends[k]
        if b <= a: continue
        m = mins[a:b]
        sel = (m >= entry) & (m < exit_)
        if sel.any():
            w[a:b][sel, 1] = 1.0; w[a:b][sel, 2] = 0.0
        ii = np.where(m == exit_)[0]
        if len(ii):
            i0 = a + ii[0]
            w[i0, 1] = 0.0; w[i0, 2] = 1.0
            w[b - 1, 1] = 0.0; w[b - 1, 2] = 1.0
    return w

for th in [0.015, 0.02]:
    m = (~wd["risk_on"]) & (run60 > th)
    w = apply(base.copy(), m, True, 329, 388)
    print("threshold", th, "events", m.sum())
    for bp in (1.0, 5.0, 10.0):
        r = bt.run(ts, opens, closes, w, "2017-01-03", band=0.02, slippage_bps=bp)
        s = bt.stats(r, 252 * 390)
        print(f"  {bp:4.0f}bp CAGR {s['cagr']*100:6.2f} DD {s['max_drawdown']*100:5.2f} fills {s['fills']:5d} turnover {s['turnover']:.0f}x")
