"""Build a cached 1-minute QQQ/TQQQ/BIL panel (OHLCV) for the re-entry study.

Writes only inside this folder.  Mirrors the round-1 winner's cache layout so the
results are directly comparable.
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
CACHE = HERE / "panel_cache.npz"
START10, START5, END = "2017-01-03", "2021-10-25", "2026-10-23"
SYMBOLS = ("QQQ", "TQQQ", "BIL")


def build(force: bool = False):
    if CACHE.exists() and not force:
        z = np.load(CACHE)
        ts = pd.DatetimeIndex(pd.to_datetime(z["ts"], unit="ns", utc=True).tz_convert("America/New_York"))
        return ts, z["opens"], z["highs"], z["lows"], z["closes"], z["vols"]

    ts, opens, closes = bt.panel(SYMBOLS, START10, END, "1min", warmup_days=500)
    highs, lows, vols = [], [], []
    for j, sym in enumerate(SYMBOLS):
        df = bt.load_1m(sym).set_index("ts")
        highs.append(df["high"].reindex(ts).ffill().bfill().to_numpy())
        lows.append(df["low"].reindex(ts).ffill().bfill().to_numpy())
        vols.append(df["volume"].reindex(ts).fillna(0.0).to_numpy())
        assert np.allclose(df["close"].reindex(ts).ffill().bfill().to_numpy(), closes[:, j],
                           rtol=1e-6, atol=1e-6), sym
    highs = np.column_stack(highs)
    lows = np.column_stack(lows)
    vols = np.column_stack(vols)
    np.savez_compressed(
        CACHE,
        ts=ts.tz_convert("UTC").tz_localize(None).to_numpy(dtype="datetime64[ns]").astype("int64"),
        opens=opens, highs=highs, lows=lows, closes=closes, vols=vols,
    )
    return ts, opens, highs, lows, closes, vols


def day_bounds(dates: np.ndarray):
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(dates) - 1]
    return first, last


if __name__ == "__main__":
    ts, o, h, l, c, v = build(force=True)
    print(len(ts), "bars", len(np.unique(ts.date)), "sessions", ts[0], "->", ts[-1], CACHE.stat().st_size)
