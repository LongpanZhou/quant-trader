"""Fast, exact re-implementation of bt.simulate for switching portfolios.

bt.simulate calls trade() on every bar.  For weights that are always "100% of
one asset or cash" the band never triggers a rebalance while the target is
unchanged (the target is a fraction of book, so holding 100% of one asset is
self-consistent).  Hence only bars where the *target vector changes* can trade;
between those bars the share count is constant and the equity path is a single
matrix-vector product.  Verified to match bt.run exactly (0.0 diff) on the
round-1 winner, including fills and turnover.
"""
from __future__ import annotations

import numpy as np
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
import bt as _bt  # noqa: E402


def _trade(opens_row, target, cash, shares, band, slip, state):
    px = opens_row
    book = cash + float(np.dot(shares, px))
    if not (book > 0):
        return cash, shares
    k = len(shares)
    for s in range(k):
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
    for s in range(k):
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
    r = _bt.simulate(None, opens, closes, weights, band=band,
                    slippage_bps=slippage_bps, start_equity=start_equity)
    r.pop("ts")
    return r
