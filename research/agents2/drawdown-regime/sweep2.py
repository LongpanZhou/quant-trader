"""Sweep 2: structural alternatives -- continuous throttle, conditional stop,
intraday drawdown exit, recovery filters."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ddlib as L


def throttle_frac(dctx, lo, hi, floor, deadband=None):
    dd = np.abs(np.minimum(dctx["dd_prev"], 0.0))
    f = 1.0 - (dd - lo) / (hi - lo)
    f = np.clip(f, floor, 1.0)
    f[~dctx["reg"]] = 0.0
    if deadband is not None:
        out = f.copy()
        cur = f[0]
        for k in range(1, len(f)):
            if not dctx["reg"][k]:
                cur = 0.0
                continue
            if abs(f[k] - cur) >= deadband or cur == 0.0:
                cur = f[k]
            out[k] = cur
        f = out
    return f


def conditional_stop(ts, opens, closes, dctx, dd_thr, stop2, base_stop=0.04):
    """Winner stop, but a tighter stop when QQQ dd <= -dd_thr."""
    first, last = dctx["first"], dctx["last"]
    n = len(ts)
    qqq_close, tqqq_close = closes[:, 0], closes[:, 1]
    hold = np.zeros(n)
    stops = 0
    for k, (f, l) in enumerate(zip(first, last)):
        if not dctx["reg"][k]:
            continue
        stop = stop2 if dctx["dd_prev"][k] <= -dd_thr else base_stop
        armed = bool(np.isfinite(dctx["arm_ma20"][k])
                     and qqq_close[f] < dctx["arm_ma20"][k] * 1.01)
        base = opens[f, 1]
        on = True
        for i in range(f, l + 1):
            if on and armed and tqqq_close[i] < base * (1 - stop):
                on = False
                stops += 1
            hold[i] = 1.0 if on else 0.0
    w = np.zeros((n, 3))
    w[:, 1] = hold
    w[:, 2] = 1 - hold
    return w, stops


def main():
    t0 = time.time()
    ts, opens, closes = L.load_panel()
    dctx = L.daily_context(ts, closes)
    print(f"loaded {time.time()-t0:.1f}s")

    print("\n== continuous drawdown throttle (frac linear in |dd|) ==")
    for lo, hi, floor, db in [
        (0.05, 0.20, 0.25, None), (0.05, 0.20, 0.25, 0.10),
        (0.05, 0.15, 0.50, 0.10), (0.05, 0.15, 0.25, 0.10),
        (0.08, 0.20, 0.25, 0.10), (0.10, 0.25, 0.25, 0.10),
        (0.05, 0.25, 0.25, 0.10), (0.05, 0.10, 0.50, 0.10),
        (0.00, 0.15, 0.50, 0.10), (0.10, 0.20, 0.50, 0.10),
    ]:
        frac = throttle_frac(dctx, lo, hi, floor, db)
        w, _ = L.render(ts, opens, closes, dctx, frac)
        o = L.summary(ts, opens, closes, w)
        L.fmt(f"thr lo{lo:.0%} hi{hi:.0%} fl{floor:.0%}", o)
        print(f"      mean frac {frac.mean():.3f}  fills {o[L.START10]['fills']}")

    print("\n== conditional tighter stop when dd <= -X ==")
    for thr in (0.03, 0.05, 0.08):
        for s2 in (0.02, 0.025, 0.03):
            w, nst = conditional_stop(ts, opens, closes, dctx, thr, s2)
            o = L.summary(ts, opens, closes, w)
            L.fmt(f"dd<={-thr:.0%} stop{s2:.1%} (n={nst})", o)

    print("\n== intraday dd exit + recovery re-entry ==")
    for thr in (0.06, 0.07, 0.08, 0.09, 0.10):
        for rec in (0.02, 0.03, 0.05):
            frac = np.ones(dctx["n"])
            w, d = L.render(ts, opens, closes, dctx, frac,
                            dd_intraday=thr, rec_thr=rec)
            o = L.summary(ts, opens, closes, w)
            L.fmt(f"intraday {thr:.0%} rec {rec:.0%} (n={d['dd_intraday_exits']})", o)

    print(f"\ndone {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
