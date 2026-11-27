"""Parameter surface, yearly and cost robustness for the late-rally overlay."""
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
qclose = wd["qclose"]
prev_c = pd.Series(qclose).shift(1).to_numpy()

def ss(minute, asset=0):
    return lib.session_series(closes[:, asset], wd["sess"], mins, n_sess, minute)

p1459 = ss(329); p1529 = ss(359); p1558 = ss(388)
run60 = p1459 / prev_c - 1.0
run30 = p1529 / prev_c - 1.0
# prior 20-day realized vol of daily QQQ returns (through prior close)
qret = pd.Series(qclose).pct_change()
sig20 = qret.rolling(20).std().shift(1).to_numpy()

def apply(w, mask, long, entry, exit_, overnight="flat"):
    for k in np.where(mask)[0]:
        a, b = starts[k], ends[k]
        if b <= a:
            continue
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
            if overnight == "flat":
                w[i0, 1] = 0.0; w[i0, 2] = 1.0; w[b - 1, 1] = 0.0; w[b - 1, 2] = 1.0
            elif overnight == "long":
                w[i0, 1] = 1.0; w[i0, 2] = 0.0; w[b - 1, 1] = 1.0; w[b - 1, 2] = 0.0
    return w

def evalw(w, tag, full=False):
    out = {}
    for start, win in [("2017-01-03", "10y"), ("2021-10-25", "5y")]:
        for bp in (1.0, 5.0, 10.0):
            r = bt.run(ts, opens, closes, w, start, band=0.02, slippage_bps=bp)
            out[(win, bp)] = (bt.stats(r, 252 * 390), r)
    s10 = out[("10y", 1.0)][0]; s5 = out[("5y", 1.0)][0]
    print(f"{tag:42s} 1bp {s10['cagr']*100:6.2f}/{s10['max_drawdown']*100:5.2f} "
          f"{s5['cagr']*100:6.2f}/{s5['max_drawdown']*100:5.2f} | "
          f"5bp {out[('10y',5.0)][0]['cagr']*100:6.2f}/{out[('10y',5.0)][0]['max_drawdown']*100:5.2f} "
          f"{out[('5y',5.0)][0]['cagr']*100:6.2f}/{out[('5y',5.0)][0]['max_drawdown']*100:5.2f} | "
          f"10bp {out[('10y',10.0)][0]['cagr']*100:6.2f}/{out[('10y',10.0)][0]['max_drawdown']*100:5.2f} "
          f"{out[('5y',10.0)][0]['cagr']*100:6.2f}/{out[('5y',10.0)][0]['max_drawdown']*100:5.2f} "
          f"[{time.time()-T0:.0f}s]", flush=True)
    if full:
        return out
    return out

def yearly_table(w, tag):
    r = bt.run(ts, opens, closes, w, "2017-01-03", band=0.02, slippage_bps=1.0)
    y = bt.yearly(ts, r["equity"], closes[:, 1])
    print(f"  yearly {tag}: " + " ".join(f"{k}:{v['strategy']*100:+.1f}" for k, v in y.items()))
    return y

print("base")
evalw(base, "winner")

print("\nThreshold surface (60m, 15:00 entry, exit 15:59)")
for th in [0.005, 0.01, 0.015, 0.02, 0.025, 0.03]:
    m = (~wd["risk_on"]) & (run60 > th)
    w = apply(base.copy(), m, True, 329, 388, "flat")
    evalw(w, f"rally60 >{th*100:.1f}% n={m.sum()}")

print("\n30m entry with 15:00-15:30 confirmation")
for th in [0.01, 0.015, 0.02, 0.025]:
    m = (~wd["risk_on"]) & (run60 > th)
    w = apply(base.copy(), m, True, 359, 388, "flat")
    evalw(w, f"rally30 >{th*100:.1f}% n={m.sum()}")

print("\nVol-scaled threshold (run60 > k * sigma20)")
for k in [0.5, 0.75, 1.0, 1.25, 1.5]:
    m = (~wd["risk_on"]) & (run60 > k * sig20)
    w = apply(base.copy(), m, True, 329, 388, "flat")
    evalw(w, f"rally60 >{k:.2f}*sig20 n={m.sum()}")

print("\nAblations")
m = (run60 > 0.02)
w = apply(base.copy(), m, True, 329, 388, "flat")
evalw(w, "all days >2% (no regime gate)")
m = (~wd["risk_on"]) & (run60 > 0.02)
w = apply(base.copy(), m, True, 329, 388, "flat")
# QQQ leg instead of TQQQ: rebuild by hand
wq = base.copy()
for k in np.where(m)[0]:
    a, b = starts[k], ends[k]
    mm = mins[a:b]
    sel = (mm >= 329) & (mm < 388)
    wq[a:b][sel, 1] = 0.0; wq[a:b][sel, 0] = 1.0
    ii = np.where(mm == 388)[0]
    if len(ii):
        wq[a + ii[0], 0] = 0.0; wq[a + ii[0], 2] = 1.0
        wq[b - 1, 0] = 0.0; wq[b - 1, 2] = 1.0
evalw(wq, "rally >2% in QQQ")

print("\nYearly tables")
for tag, m in [("winner", np.zeros(n_sess, bool))]:
    pass
yearly_table(base, "winner")
for th in [0.015, 0.02, 0.025]:
    m = (~wd["risk_on"]) & (run60 > th)
    w = apply(base.copy(), m, True, 329, 388, "flat")
    yearly_table(w, f"rally >{th*100:.1f}%")
