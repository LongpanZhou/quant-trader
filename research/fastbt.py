"""Shared fast backtest helpers for research agents.

`bt.simulate` trades on every bar. Most research strategies hold 100% of one
asset or cash and only change target at regime/stop events, so most bars cannot
trade. This event-based simulator is exact for those weight paths and much
faster. It is copied from the round-2 volume-order-flow agent, where it was
verified to match `bt.simulate` with 0.0 equity difference.

The panel loader is `bt.panel`, which now uses the shared `data/cache` cache.

Run from the repo root:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402


def _trade(opens_row, target, cash, shares, band, slip, state):
    px = opens_row
    book = cash + float(np.dot(shares, px))
    if not (book > 0):
        return cash, shares
    for s in range(len(shares)):
        if shares[s] <= 0:
            continue
        if target[s] == 0:
            qty = shares[s]
        else:
            excess = shares[s] * px[s] - target[s] * book
            if excess <= band * book:
                continue
            qty = excess / px[s]
        qty = min(qty, shares[s])
        if qty <= 0:
            continue
        price = px[s] * (1.0 - slip)
        cash += qty * price
        state["traded"] += qty * price
        state["fills"] += 1
        shares[s] -= qty
        if shares[s] < 1e-10:
            shares[s] = 0.0
    for s in range(len(shares)):
        if target[s] <= 0:
            continue
        current = shares[s] * px[s]
        shortfall = target[s] * book - current
        is_new = shares[s] <= 0
        if not is_new and shortfall <= band * book:
            continue
        if shortfall <= 0:
            continue
        price = px[s] * (1.0 + slip)
        qty = min(shortfall / price, cash / price)
        if qty <= 1e-12:
            continue
        cash -= qty * price
        state["traded"] += qty * price
        state["fills"] += 1
        shares[s] += qty
    return cash, shares


def fast_sim(opens, closes, weights, start_equity=100_000.0, band=0.02,
             slippage_bps=1.0):
    """Delegates to bt.simulate (compiled Rust core, exact for any weights).

    Previously an event-based loop that was exact only for all-in-one-asset
    portfolios; bt.simulate is exact for every weight path and faster.
    """
    r = bt.simulate(None, opens, closes, weights, band=band,
                    slippage_bps=slippage_bps, start_equity=start_equity)
    r.pop("ts")
    return r


def run(ts, opens, closes, weights, start, band=0.02, slippage_bps=1.0,
        start_equity=100_000.0):
    """Fast slice-and-simulate, matching `bt.run`."""
    i = bt.start_index(ts, start)
    out = fast_sim(opens[i:], closes[i:], weights[i:],
                   start_equity=start_equity, band=band,
                   slippage_bps=slippage_bps)
    out["ts"] = ts[i:]
    return out
