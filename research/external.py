"""Helpers for cross-asset daily series used by the new families.

Signals are computed on daily closes from `data/external/`; execution is on the
local 1-minute QQQ/TQQQ/BIL panel.  `daily_targets_to_weights` writes each
target at the last bar of its signal session, so `bt.run` fills it at the next
session's open.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "data" / "external"


def load(symbol: str, field: str = "adjclose", end=None) -> pd.Series:
    """Daily series indexed by tz-naive normalized date.

    `end`, when supplied, is pushed into the parquet reader so later rows are
    never materialised (used by development runs to exclude 2024-2026).
    """
    name = symbol.replace("^", "").replace("=", "_")
    p = EXT / f"{name}.parquet"
    if not p.exists():
        raise FileNotFoundError(p)
    if end is None:
        df = pd.read_parquet(p)
    else:
        df = pd.read_parquet(p, filters=[("date", "<=", pd.Timestamp(end))])
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.normalize()
    s = df.set_index("date")[field].astype(float).sort_index()
    return s[~s.index.duplicated(keep="last")]


def session_index(ts) -> pd.DatetimeIndex:
    import bt
    dates, first, _ = bt.day_bounds(ts)
    return pd.DatetimeIndex(dates[first]).tz_localize(None).normalize()


def align(ts, symbols: list[str], field: str = "adjclose",
          end=None) -> pd.DataFrame:
    """External closes reindexed/ffilled to the QQQ session calendar.

    `end` is forwarded to `load`, so a development run can prevent post-window
    parquet rows from being read at all.
    """
    idx = session_index(ts)
    cols = {}
    for sym in symbols:
        cols[sym] = load(sym, field, end=end).reindex(idx).ffill()
    return pd.DataFrame(cols, index=idx)


def daily_targets_to_weights(ts, targets, cols=(0, 1, 2)) -> np.ndarray:
    """Map one target row per session to minute weights.

    `targets[k]` is the target written at the close of session k; it fills at
    the next session's open.  Columns default to QQQ/TQQQ/BIL.
    """
    import bt
    dates, first, last = bt.day_bounds(ts)
    nd = len(first)
    t = np.asarray(targets, dtype=float)
    if t.ndim == 1:
        t2 = np.zeros((nd, 3))
        t2[:, cols[1]] = t
        t2[:, cols[2]] = 1.0 - t
        t = t2
    if t.shape != (nd, 3):
        raise ValueError(f"targets shape {t.shape}, expected {(nd, 3)}")
    w = np.zeros((len(ts), 3))
    prev = np.zeros(3)
    for k in range(nd):
        a, b = int(first[k]), int(last[k])
        w[a:b] = prev
        w[b] = t[k]
        prev = t[k]
    w[-1] = w[-2]
    return w
