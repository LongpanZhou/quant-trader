"""Sweep 5: de-lever to QQQ (beta 1) in drawdown states, and blends."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ddlib as L


def render_delever(ts, opens, closes, dctx, exit_thr, reenter_thr,
                   qqq_frac=1.0, stop=0.04, arm_buf=0.01):
    """Winner stop; in the deep-DD state hold qqq_frac in QQQ, rest BIL,
    instead of TQQQ."""
    first, last = dctx["first"], dctx["last"]
    n = len(ts)
    qqq_close, tqqq_close = closes[:, 0], closes[:, 1]
    hold_t = np.zeros(n)
    hold_q = np.zeros(n)
    blocked = False
    for k, (f, l) in enumerate(zip(first, last)):
        if not dctx["reg"][k]:
            blocked = False
            continue
        if blocked:
            if dctx["dd_prev"][k] >= -reenter_thr:
                blocked = False
        else:
            if dctx["dd_prev"][k] <= -exit_thr:
                blocked = True
        if blocked:
            hold_q[f:l + 1] = qqq_frac
            continue
        armed = bool(np.isfinite(dctx["arm_ma20"][k])
                     and qqq_close[f] < dctx["arm_ma20"][k] * (1 + arm_buf))
        base = opens[f, 1]
        on = True
        for i in range(f, l + 1):
            if on and armed and tqqq_close[i] < base * (1 - stop):
                on = False
            hold_t[i] = 1.0 if on else 0.0
    w = np.zeros((n, 3))
    w[:, 0] = hold_q
    w[:, 1] = hold_t
    w[:, 2] = 1 - hold_q - hold_t
    return w


def main():
    ts, opens, closes = L.load_panel()
    dctx = L.daily_context(ts, closes)

    print("== de-lever to QQQ (100% QQQ) in deep DD ==")
    for x in (0.05, 0.08, 0.10, 0.15):
        for rec in (0.02, 0.04, 0.05):
            w = render_delever(ts, opens, closes, dctx, x, rec, 1.0)
            L.fmt(f"QQQ exit {x:.0%} rec {rec:.0%}", L.summary(ts, opens, closes, w))
        print()

    print("== de-lever 50% QQQ / 50% BIL in deep DD ==")
    for x in (0.05, 0.08, 0.10, 0.15):
        for rec in (0.02, 0.04):
            w = render_delever(ts, opens, closes, dctx, x, rec, 0.5)
            L.fmt(f"50QQQ exit {x:.0%} rec {rec:.0%}", L.summary(ts, opens, closes, w))
        print()

    print("== de-lever 50% QQQ / 50% TQQQ (beta ~2) ==")
    for x in (0.05, 0.08, 0.10, 0.15):
        w = render_delever(ts, opens, closes, dctx, x, 0.04, 0.5)
        L.fmt(f"50QQQ+50TQQQ {x:.0%}", L.summary(ts, opens, closes, w))


if __name__ == "__main__":
    main()
