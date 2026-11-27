"""Sweep 1: reproduce the winner and test drawdown gates on top of it."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ddlib as L

START10, START5 = L.START10, L.START5


def main():
    t0 = time.time()
    ts, opens, closes = L.load_panel()
    dctx = L.daily_context(ts, closes)
    print(f"panel {len(ts):,} bars, {dctx['n']} sessions, load {time.time()-t0:.1f}s")

    base_frac = np.ones(dctx["n"])
    w, diag = L.render(ts, opens, closes, dctx, base_frac)
    out = L.summary(ts, opens, closes, w)
    L.fmt("winner (repro)", out)
    print("  diag", diag["stop_events"], "stop events")

    print("\n== full de-risk to BIL, exit at dd<=-X, re-enter at various rec ==")
    for x in (0.05, 0.10, 0.15):
        for rec in (0.02, x / 2, max(x - 0.05, 0.005), 0.0):
            frac = L.dd_state(dctx, x, rec, scale=0.0)
            w, d = L.render(ts, opens, closes, dctx, frac)
            L.fmt(f"BIL exit {x:.0%} rec {rec:.1%}", L.summary(ts, opens, closes, w))
        print()

    print("== partial de-risk (50% TQQQ / 50% BIL) ==")
    for x in (0.05, 0.10, 0.15):
        for rec in (0.02, x / 2, max(x - 0.05, 0.005), 0.0):
            frac = L.dd_state(dctx, x, rec, scale=0.5)
            w, d = L.render(ts, opens, closes, dctx, frac)
            L.fmt(f"50% exit {x:.0%} rec {rec:.1%}", L.summary(ts, opens, closes, w))
        print()

    print("== underwater duration (sessions since 52w high) ==")
    for n in (60, 120, 180, 250):
        for rec in (0, 10, 30):
            frac = L.dd_state(dctx, n, rec, scale=0.0, kind="uw")
            w, d = L.render(ts, opens, closes, dctx, frac)
            L.fmt(f"UW>={n} rec<={rec}", L.summary(ts, opens, closes, w))
        print()

    print(f"done {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
