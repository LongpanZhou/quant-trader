"""Vol-scaled crash stop — shared-runner adapter.

The original strategy needs per-session OHLC and an ATR series, not just the
shared 3-array open/close panel.  This wrapper loads the full OHLC archive with
a 90-day warm-up, aligns it to the runner's timestamps, and calls the frozen
implementation unchanged.
"""
from __future__ import annotations

import importlib.util
import tempfile
import uuid
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "research" / "revisit" / "vol-scaled-crash-stop" / "strategy.py"
spec = importlib.util.spec_from_file_location("vscs_base", BASE)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


def build_weights(ts, o, c):
    start = str(pd.Timestamp(ts[0]).date())
    end = str(pd.Timestamp(ts[-1]).date())
    # Force a fresh full OHLC load; the dev cache is only 2016-2023.
    base.CACHE = Path(tempfile.gettempdir()) / f"vscs_{uuid.uuid4().hex}.npz"
    pts, po, ph, pl, pc = base.load_dev_panel(
        start=start, end=end, warmup_days=90)
    idx = np.searchsorted(pts, ts)
    idx = np.clip(idx, 0, len(pts) - 1)
    if len(idx) != len(ts) or not np.array_equal(pts[idx], pd.DatetimeIndex(ts)):
        raise RuntimeError("VSCS OHLC panel does not align to the shared timestamps")
    dates = base.bt.session_dates(ts)
    first, last = base.day_bounds(dates)
    atr = base.atr_series(ph[idx], pl[idx], pc[idx], first, last)
    return base.build_weights(ts, po[idx], pc[idx], first, last, atr)
