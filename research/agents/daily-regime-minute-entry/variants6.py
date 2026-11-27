"""Variant 6: minute-level entry timing on regime flip-on days."""
import numpy as np
import pandas as pd

import strat_lib as sl

A = sl.load_arrays()
ts, dates, first, last = A["ts"], A["dates"], A["first"], A["last"]
oc, oo, oh = A["closes"], A["opens"], A["highs"]
reg, dc, sma, _, _, _ = sl.daily_regime(ts, oc[:, 0], 165)
n = len(ts)
c = oc[:, 1]
vwap = sl.session_vwap(oh[:, 1], A["lows"][:, 1], c, A["vols"][:, 1], dates, first, last)


def make_weights(hold):
    w = np.zeros((n, 3))
    w[:, 1] = hold.astype(float)
    w[:, 2] = 1.0 - w[:, 1]
    return w


def base_hold():
    return reg.copy()


def entry_rule(mode, hold=None):
    """Delay the first buy of each regime-on episode."""
    h = base_hold() if hold is None else hold.copy()
    flips = []
    for k, (f, l) in enumerate(zip(first, last)):
        if reg[f] and (k == 0 or not reg[first[k - 1]]):
            flips.append((k, f, l))
    print(f"  {mode}: {len(flips)} entry episodes")
    for k, f, l in flips:
        if mode == "open":
            continue
        if mode == "close":
            h[f:l - 1] = False
        elif mode == "10am":
            h[f:f + 30] = False
        elif mode == "1130":
            h[f:f + 120] = False
        elif mode == "touch_open":
            idx = np.flatnonzero(c[f:l + 1] <= oo[f, 1])
            cut = f + idx[0] if len(idx) else l - 1
            h[f:cut] = False
        elif mode == "vwap_reclaim":
            below = c[f:l + 1] < vwap[f:l + 1]
            idx = np.flatnonzero(~below)
            cut = f + idx[0] if len(idx) else l - 1
            h[f:cut] = False
        elif mode == "orb30":
            orh = oh[f:f + 30, 1].max()
            idx = np.flatnonzero(c[f + 30:l + 1] > orh)
            cut = f + 30 + idx[0] if len(idx) else l - 1
            h[f:min(cut, l - 1)] = False
        elif mode == "pullback1":
            idx = np.flatnonzero(c[f:l + 1] < oo[f, 1] * 0.99)
            cut = f + idx[0] if len(idx) else l - 1
            h[f:cut] = False
    return h


print("entry timing (control, no stop):")
sl.summarize("control", ts, A["opens"], oc, make_weights(base_hold()))
for mode in ("close", "10am", "1130", "touch_open", "vwap_reclaim", "orb30", "pullback1"):
    h = entry_rule(mode)
    sl.summarize(f"entry {mode}", ts, A["opens"], oc, make_weights(h))
