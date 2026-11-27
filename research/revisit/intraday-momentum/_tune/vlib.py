"""Generic weekly-ladder builder used for the tuning sweep (mirrors strategy.build_weights)."""
import numpy as np
from common import *  # noqa

STATE_W = {"TQQQ": [0, 1, 0], "QQQ": [1, 0, 0], "BIL": [0, 0, 1], "HALF": [0, 0.5, 0.5]}


def feats(ts, o, c, fh_bars=60):
    a, b = S._sessions(ts)
    q0 = o[a, 0]; q1 = c[b - 1, 0]
    nd = len(a)
    on = np.full(nd, np.nan); on[1:] = q0[1:] / q1[:-1] - 1
    idr = q1 / q0 - 1
    fh = c[a + fh_bars - 1, 0] / q0 - 1
    return a, b, on, idr, fh, q1


def build(ts, o, c, legs=(("sp", +1), ("fh", +1)), ladder=("BIL", "QQQ", "TQQQ"), step=5,
          med_n=26, min_hist=13, fh_bars=60, incl=True, vol_caps=(0.60, 0.80), states_override=None,
          offset=0):
    """legs: (feature, sign) -- favourable if sign*(x - median) > 0. ladder[k] = state for k favourable legs."""
    a, b, on, idr, fh, q1 = feats(ts, o, c, fh_bars)
    nd = len(a); n = len(ts)
    w = np.zeros((n, 3)); w[:, 2] = 1
    hist = {f: [] for f, _ in legs}
    states = []
    rebs = list(range(2 * step - 1 + offset, nd, step))
    for r in rebs:
        win = np.arange(r - step + 1, r + 1)
        x = {"sp": np.sum(on[win] - idr[win]), "on": np.sum(on[win]), "idr": np.sum(idr[win]),
             "fh": np.sum(fh[win]), "ret5": q1[r] / q1[r - step] - 1}
        fav = 0
        ready = True
        for f, sg in legs:
            h = hist[f]
            if incl:
                h.append(x[f]); ref = h[-med_n:]
            else:
                ref = h[-med_n:]; 
            if len(ref) < min_hist:
                ready = False
            else:
                fav += sg * (x[f] - np.median(ref)) > 0
            if not incl:
                h.append(x[f])
        if not ready:
            continue
        st = ladder[fav]
        if vol_caps is not None:
            vw = np.arange(max(0, r - 19), r + 1)
            v = np.nanstd(on[vw]) * np.sqrt(252)
            if v > vol_caps[1]: st = "BIL"
            elif v > vol_caps[0] and st == "TQQQ": st = "QQQ"
        states.append(st)
        if states_override is not None:
            st = states_override[len(states) - 1]
        w[b[r] - 1] = STATE_W[st]
        nl = min(r + step, nd - 1)
        if r + 1 < nd:
            w[a[r + 1]: b[nl]] = STATE_W[st]
    return w, states
