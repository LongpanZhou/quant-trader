"""Loading helpers for the volume / order-flow family.

Wraps research/bt.py without modifying it: bt.panel() returns only opens and
closes, so this module repeats its alignment for high/low/volume and keeps a
cached npz next to the script (the cache is a pure copy of the parquet data,
regenerated in ~8 s if deleted).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

HERE = Path(__file__).resolve().parent
CACHE = HERE / "panel_1m.npz"


def build_panel(start="2017-01-03", end="2026-10-23", warmup_days=500):
    """Aligned 1m OHLCV for QQQ/TQQQ/BIL on QQQ's minute grid."""
    if CACHE.exists():
        z = np.load(CACHE, allow_pickle=True)
        ts = pd.DatetimeIndex(z["ts_ns"], dtype="datetime64[ns]").tz_localize("UTC").tz_convert("America/New_York")
        return ts, z["opens"], z["closes"], z["highs"], z["lows"], z["volumes"]

    start_ts = pd.Timestamp(start, tz="America/New_York")
    load_start = start_ts - pd.Timedelta(days=warmup_days)
    end_ts = pd.Timestamp(end, tz="America/New_York").normalize() + pd.Timedelta(days=1)
    syms = ("QQQ", "TQQQ", "BIL")
    frames = {}
    for s in syms:
        df = bt.load_1m(s)
        frames[s] = df[(df["ts"] >= load_start) & (df["ts"] < end_ts)].set_index("ts")
    base = frames["QQQ"].index
    out = {k: [] for k in ("open", "close", "high", "low", "volume")}
    for s in syms:
        f = frames[s].reindex(base)
        for col, fill in (("open", "ffill"), ("close", "ffill"),
                          ("high", "ffill"), ("low", "ffill"), ("volume", "zero")):
            if fill == "ffill":
                v = f[col].ffill().bfill().to_numpy()
            else:
                v = f[col].fillna(0.0).to_numpy()
            out[col].append(v)
    ts = base
    arrays = {k: np.column_stack(v) for k, v in out.items()}
    np.savez_compressed(
        CACHE, ts_ns=ts.tz_convert("UTC").as_unit("ns").asi8, opens=arrays["open"],
        closes=arrays["close"], highs=arrays["high"], lows=arrays["low"],
        volumes=arrays["volume"],
    )
    return (ts, arrays["open"], arrays["close"], arrays["high"],
            arrays["low"], arrays["volume"])


def session_index(ts: pd.DatetimeIndex):
    dates = np.array([t.date() for t in ts])
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(ts) - 1]
    day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, len(ts)]))
    return dates, first, last, day_id


def tod_minutes(ts: pd.DatetimeIndex) -> np.ndarray:
    """Minutes since 09:30 for each bar (0..389)."""
    mins = ts.hour.to_numpy() * 60 + ts.minute.to_numpy() - (9 * 60 + 30)
    return mins.astype(np.int32)


def daily_close(closes: np.ndarray, first: np.ndarray, last: np.ndarray) -> np.ndarray:
    return closes[last]
