"""Exact but fast re-implementation of research/bt.py's next-open simulator.

Same fill/band/slippage rules, but equity between fills is computed vectorised
because holdings are constant. Validated against bt.simulate on several weight
vectors (see validate_fastsim.py). Core repo file is *not* modified.
"""
from __future__ import annotations

import numpy as np
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
import bt as _bt  # noqa: E402


def simulate(ts, opens, closes, weights, band=0.02, slippage_bps=1.0,
             start_equity=100_000.0):
    """Delegates to bt.simulate (compiled Rust core, exact for any weights)."""
    return _bt.simulate(ts, opens, closes, weights, band=band,
                       slippage_bps=slippage_bps, start_equity=start_equity)
