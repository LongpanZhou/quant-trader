"""Variant 2: intraday evaluation of the daily 165d SMA regime (minute exit/entry)."""
import numpy as np
import pandas as pd

import strat_lib as sl

A = sl.load_arrays()
ts, dates, first, last = A["ts"], A["dates"], A["first"], A["last"]
qc = A["closes"][:, 0]
n = len(ts)

reg, dc, sma, _, _, _ = sl.daily_regime(ts, qc, 165)
# level of the 165d SMA known during each day = SMA through previous close
sma_level_min = np.empty(n)
# map each day to previous day's SMA
day_sma = np.empty(len(first))
day_sma[0] = np.nan
day_sma[1:] = sma[:-1]
day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, len(ts)]))
sma_level_min = day_sma[day_id]


def make_weights(hold):
    w = np.zeros((n, 3))
    w[:, 1] = hold.astype(float)
    w[:, 2] = 1.0 - w[:, 1]
    return w


def intraday_regime(exit_buf=0.0, entry_buf=None, confirm=1, start_on=True):
    """State machine on QQQ close vs previous-day 165d SMA, evaluated every minute."""
    if entry_buf is None:
        entry_buf = exit_buf
    hold = np.zeros(n, bool)
    state = False
    below = 0
    above = 0
    for i in range(n):
        px, lvl = qc[i], sma_level_min[i]
        if not np.isfinite(lvl):
            hold[i] = False
            continue
        if state:
            if px < lvl * (1 - exit_buf):
                below += 1
                if below >= confirm:
                    state = False
            else:
                below = 0
        else:
            if px > lvl * (1 + entry_buf):
                above += 1
                if above >= confirm:
                    state = True
            else:
                above = 0
        hold[i] = state
    return hold


def daily_close_regime():
    """Control: state decided at prior close (what the daily baseline does)."""
    hold = np.zeros(n, bool)
    for i in range(n):
        f = first[np.searchsorted(first, i, side="right") - 1]
        hold[i] = reg[i]
    return hold


# diagnostics: how often does an intraday cross happen before the close-based flip?
for b in (0.0, 0.0025, 0.005):
    h = intraday_regime(b, confirm=1)
    flips = np.diff(h.astype(int))
    print(f"buf {b*100:.2f}%: entries {np.sum(flips==1)}, exits {np.sum(flips==-1)}, days held {h[first].mean()*100:.1f}%")

ctrl = np.zeros(n, bool)
ctrl[:] = reg
print("\n--- control and intraday-regime variants ---")
sl.summarize("ctrl daily close regime", ts, A["opens"], A["closes"], make_weights(ctrl))
for b, cf in ((0.0, 1), (0.0025, 1), (0.005, 1), (0.01, 1), (0.005, 15)):
    h = intraday_regime(b, confirm=cf)
    sl.summarize(f"intradayX buf{b*100:.2f}% cf{cf}", ts, A["opens"], A["closes"], make_weights(h))

