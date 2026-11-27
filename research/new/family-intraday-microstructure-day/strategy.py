"""Day-only opening-drive intraday microstructure (family-pure variant).

This wrapper uses the original intraday agent's mechanics with the overnight
reversal sleeve disabled, so the book is flat from 15:59 to 09:30.  The input
is the shared panel sliced to (TQQQ, BIL) columns; the output is the same
2-column shape.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
BASE_PATH = ROOT / "research" / "new" / "family-intraday-microstructure" / "strategy.py"
spec = importlib.util.spec_from_file_location("intraday_base", BASE_PATH)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


def build_weights(ts, o, c):
    """Day sleeve only: no overnight position, no weak-close reversal."""
    return base.build_weights(ts, o, c, night_th=-1.0, bil=True)
