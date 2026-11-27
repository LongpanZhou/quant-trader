"""Screen late-day overlay rules on top of the round-1 winner."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, "research")
sys.path.insert(0, str(HERE / "scratch"))
import bt
import lib

ts, opens, closes = lib.load_panel()
uniq, sess, mins = lib.session_info(ts)
n_sess = len(uniq)
wd = lib.winner_daily(ts, opens, closes)
qclose = wd["qclose"]

# session-level prices
def per_session(col, minute):
    out = np.full(n_sess, np.nan)
    sel = mins == minute
    out[sess[sel]] = col[sel]
    return out

prev_c = pd.Series(qclose).shift(1).to_numpy()
p1459 = per_session(closes[:, 0], 329)
o1500 = per_session(opens[:, 0], 330)
p1529 = per_session(closes[:, 0], 359)
o1530 = per_session(opens[:, 0], 360)
p1558 = per_session(closes[:, 0], 388)
run60 = p1459 / prev_c - 1.0
run30 = p1529 / prev_c - 1.0

n = len(ts)
base = lib.weights_from_rules(ts, opens, closes, wd)

def apply_rule(w, mask_sessions, long_side, entry_min, exit_min, overnight, base_w=None,
               protect_stop=True):
    """Override bars in selected sessions: long TQQQ from entry through exit.

    If protect_stop, a session where the base winner had already stopped to BIL
    is not forced back into TQQQ for the overnight.
    """
    for k in np.where(mask_sessions)[0]:
        idx = np.where(sess == k)[0]
        if not len(idx):
            continue
        stopped = base_w is not None and base_w[idx[-1], 1] < 0.5
        sel = (mins[idx] >= entry_min) & (mins[idx] <= exit_min)
        if not sel.any():
            continue
        if long_side:
            w[idx[sel], 1] = 1.0
            w[idx[sel], 2] = 0.0
        else:
            w[idx[sel], 1] = 0.0
            w[idx[sel], 2] = 1.0
        # last bar determines the overnight position (fills next session open)
        if overnight is True and not (protect_stop and stopped):
            w[idx[-1], 1] = 1.0
            w[idx[-1], 2] = 0.0
        elif overnight is False:
            w[idx[-1], 1] = 0.0
            w[idx[-1], 2] = 1.0
    return w

def run_one(w, tag):
    out = {}
    for start, win in [("2017-01-03", "10y"), ("2021-10-25", "5y")]:
        r = bt.run(ts, opens, closes, w, start, band=0.02, slippage_bps=1.0)
        s = bt.stats(r, 252 * 390)
        out[win] = s
    print(f"{tag:48s} 10y {out['10y']['cagr']*100:6.2f}/{out['10y']['max_drawdown']*100:5.2f}"
          f" 5y {out['5y']['cagr']*100:6.2f}/{out['5y']['max_drawdown']*100:5.2f}"
          f" fills {out['10y']['fills']:5d}")
    return out

print("base winner")
run_one(base, "winner")

results = []
print("\n--- risk-on: skip last hour when down into the close (keep overnight) ---")
for x in [0.0, 0.0025, 0.005, 0.0075, 0.01, 0.015, 0.02]:
    m = wd["risk_on"] & (run60 < -x)
    w = apply_rule(base.copy(), m, False, 330, 388, True, base)
    s = run_one(w, f"skip60 run60<-{x*100:.2f}% n={m.sum()}")
    results.append(("skip60_keep", x, s))

print("\n--- risk-on: skip last hour when down (flat overnight too) ---")
for x in [0.0, 0.005, 0.01, 0.02]:
    m = wd["risk_on"] & (run60 < -x)
    w = apply_rule(base.copy(), m, False, 330, 388, False)
    s = run_one(w, f"skip60+night run60<-{x*100:.2f}%")
    results.append(("skip60_flatnight", x, s))

print("\n--- risk-on: skip last 30m when down (keep overnight) ---")
for x in [0.0, 0.0025, 0.005, 0.01, 0.015]:
    m = wd["risk_on"] & (run30 < -x)
    w = apply_rule(base.copy(), m, False, 360, 388, True, base)
    s = run_one(w, f"skip30 run30<-{x*100:.2f}% n={m.sum()}")
    results.append(("skip30_keep", x, s))

print("\n--- risk-off: buy last hour after strong late rally (flat overnight) ---")
for x in [0.0, 0.005, 0.01, 0.015, 0.02, 0.025, 0.03]:
    m = (~wd["risk_on"]) & (run60 > x)
    w = apply_rule(base.copy(), m, True, 330, 388, False)
    s = run_one(w, f"offrally60 run60>{x*100:.2f}% n={m.sum()}")
    results.append(("offrally60", x, s))

print("\n--- risk-off: buy last hour after strong late rally (hold overnight) ---")
for x in [0.01, 0.015, 0.02, 0.03]:
    m = (~wd["risk_on"]) & (run60 > x)
    w = apply_rule(base.copy(), m, True, 330, 388, True)
    s = run_one(w, f"offrally60+night run60>{x*100:.2f}%")
    results.append(("offrally60_night", x, s))

print("\n--- risk-off: buy last 30m after strong rally (flat overnight) ---")
for x in [0.0, 0.01, 0.015, 0.02, 0.025, 0.03]:
    m = (~wd["risk_on"]) & (run30 > x)
    w = apply_rule(base.copy(), m, True, 360, 388, False)
    s = run_one(w, f"offrally30 run30>{x*100:.2f}% n={m.sum()}")
    results.append(("offrally30", x, s))

print("\n--- reversed controls (should be worse) ---")
m = wd["risk_on"] & (run60 > 0)
w = apply_rule(base.copy(), m, False, 330, 388, True, base)
run_one(w, "skip last hour on UP days")
m = (~wd["risk_on"]) & (run60 < 0)
w = apply_rule(base.copy(), m, True, 330, 388, False)
run_one(w, "buy last hour on DOWN risk-off days")

pd.to_pickle({"results": results}, HERE / "screen1.pkl")
