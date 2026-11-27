"""First batch of minute-timing overlays on the 165d daily regime."""
import numpy as np
import pandas as pd

import strat_lib as sl

A = sl.load_arrays()
ts, dates, first, last = A["ts"], A["dates"], A["first"], A["last"]
oc, oh, ol, ov = A["closes"], A["highs"], A["lows"], A["vols"]
reg, dc, sma, _, _, _ = sl.daily_regime(ts, oc[:, 0], 165)
n = len(ts)

vwap = sl.session_vwap(oh[:, 1], ol[:, 1], oc[:, 1], ov[:, 1], dates, first, last)
ema20 = sl.ema(oc[:, 1], 20)
ema60 = sl.ema(oc[:, 1], 60)
ema50 = sl.ema(oc[:, 1], 50)
ema200 = sl.ema(oc[:, 1], 200)


def make_weights(hold):
    w = np.zeros((n, 3))
    w[:, 1] = hold.astype(float)
    w[:, 2] = 1.0 - w[:, 1]
    return w


def rule_vwap(buf=0.0, confirm=1, overnight="state"):
    c = oc[:, 1]
    hold = np.zeros(n, bool)
    for f, l in zip(first, last):
        state = False
        cnt = 0
        for i in range(f, l + 1):
            if not reg[i]:
                state = False
                cnt = 0
            elif c[i] > vwap[i] * (1 + buf):
                cnt += 1
                if cnt >= confirm:
                    state = True
            elif c[i] < vwap[i] * (1 - buf):
                cnt = 0
                state = False
            hold[i] = state
        if overnight == "always":
            hold[l - 1:l + 1] = reg[l]
        elif overnight == "never":
            hold[l - 1:l + 1] = False
    return hold


def rule_ema(fast, slow, buf=0.0):
    hold = np.zeros(n, bool)
    up = fast > slow * (1 + buf)
    dn = fast < slow * (1 - buf)
    state = False
    for f, l in zip(first, last):
        for i in range(f, l + 1):
            if not reg[i]:
                state = False
            elif up[i]:
                state = True
            elif dn[i]:
                state = False
            hold[i] = state
    return hold


def rule_stop(x=0.03, reentry="next_day"):
    """Hold TQQQ when regime on; exit rest of day if drawdown from day high > x."""
    c = oc[:, 1]
    hold = np.zeros(n, bool)
    for f, l in zip(first, last):
        state = bool(reg[f])
        hi = -np.inf
        for i in range(f, l + 1):
            hi = max(hi, oh[i, 1])
            if state and c[i] < hi * (1 - x):
                state = False
            if reentry == "vwap" and not state and c[i] > vwap[i]:
                state = True
            hold[i] = state
        hold[l - 1:l + 1] = reg[l]  # back in for the night
    return hold


def rule_orb(or_min=30, stop_vwap=True, overnight="state"):
    c, h, lo = oc[:, 1], oh[:, 1], ol[:, 1]
    hold = np.zeros(n, bool)
    for f, l in zip(first, last):
        state = False
        orh = h[f:f + or_min].max()
        orl = lo[f:f + or_min].min()
        for i in range(f, l + 1):
            if not reg[i]:
                state = False
            elif i >= f + or_min and c[i] > orh:
                state = True
            elif state and stop_vwap and c[i] < vwap[i]:
                state = False
            elif state and not stop_vwap and c[i] < orl:
                state = False
            hold[i] = state
        if overnight == "always":
            hold[l - 1:l + 1] = reg[l]
        elif overnight == "never":
            hold[l - 1:l + 1] = False
    return hold


def rule_first30(thr=0.0, overnight="state"):
    """Trade only if the first 30 minutes are up; hold to close."""
    c = oc[:, 1]
    hold = np.zeros(n, bool)
    for f, l in zip(first, last):
        state = False
        for i in range(f, l + 1):
            if not reg[i]:
                state = False
            elif i == f + 29:
                state = c[i] > A["opens"][f, 1] * (1 + thr)
            hold[i] = state
        if overnight == "always":
            hold[l - 1:l + 1] = reg[l]
    return hold


variants = {}
variants["V1 vwap buf0 confirm1"] = rule_vwap(0.0, 1)
variants["V1b vwap buf5bp confirm3"] = rule_vwap(0.0005, 3)
variants["V1c vwap buf0 confirm1 overnight=always"] = rule_vwap(0.0, 1, "always")
variants["V2 ema20/60"] = rule_ema(ema20, ema60)
variants["V2b ema50/200"] = rule_ema(ema50, ema200)
variants["V3 stop3% reentry next"] = rule_stop(0.03)
variants["V3b stop2% reentry vwap"] = rule_stop(0.02, "vwap")
variants["V4 orb30 hold-overnight"] = rule_orb(30, True, "state")
variants["V5 first30 up only"] = rule_first30(0.0)

for name, hold in variants.items():
    print(f"\n{name}: days held {hold[first].mean()*100:.1f}%")
    sl.summarize(name, ts, A["opens"], oc, make_weights(hold))
