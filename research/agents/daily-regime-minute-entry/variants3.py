"""Variant 3: daily regime + rare intraday stop-loss, re-enter at the close (keep overnight)."""
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


def stop_rule(x=0.05, ref="open", reenter="close", lockout_days=0):
    """Exit when TQQQ falls x from day open (or prior close); re-enter per `reenter`."""
    hold = np.zeros(n, bool)
    prev_close = np.r_[np.nan, c[:-1]]
    lock = 0
    for f, l in zip(first, last):
        state = bool(reg[f]) and lock == 0
        base = oo[f, 1] if ref == "open" else prev_close[f]
        stopped = False
        for i in range(f, l + 1):
            if state and c[i] < base * (1 - x):
                state = False
                stopped = True
            if not state and not stopped and reg[i]:
                state = True
            if stopped and reenter == "vwap" and c[i] > vwap[i] and reg[i]:
                state = True
            hold[i] = state
        if reg[l] and reenter != "never":
            hold[l - 1:l + 1] = True
        if lock > 0:
            lock -= 1
        if stopped and lockout_days > 0:
            lock = lockout_days
    return hold


def count_stops(hold):
    flips = np.diff(hold.astype(int))
    return int(np.sum(flips == -1)), int(np.sum(flips == 1))


ctrl = np.zeros(n, bool)
ctrl[:] = reg
print("control")
sl.summarize("ctrl", ts, A["opens"], oc, make_weights(ctrl))

for x, ref, re in ((0.03, "open", "close"), (0.04, "open", "close"), (0.05, "open", "close"),
                   (0.06, "open", "close"), (0.08, "open", "close"),
                   (0.05, "open", "vwap"), (0.05, "prevclose", "close")):
    h = stop_rule(x, ref, re)
    ne, nx = count_stops(h)
    print(f"\nstop {x*100:.0f}% ref={ref} re={re}: exits {ne}, entries {nx}")
    sl.summarize(f"stop{x*100:.0f}{ref[:2]}{re}", ts, A["opens"], oc, make_weights(h))
