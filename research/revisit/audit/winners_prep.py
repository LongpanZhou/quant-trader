"""Build the shared 2016-2026 1-minute OHLC panel for the winners audit.

Same construction as research/bt.py `panel(..., "1min", warmup_days=0)`,
plus the highs/lows needed by the ATR stop.  Cached in audit/cache so the
analysis scripts do not re-read the parquet files.

    python research/revisit/audit/winners_prep.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

START, END = "2016-01-04", "2026-10-23"
SYMS = ("QQQ", "TQQQ", "BIL")
CACHE = Path(__file__).resolve().parent / "cache" / "full_panel_ohlc.npz"


def main():
    if CACHE.exists():
        print("exists", CACHE, CACHE.stat().st_size)
        return
    start_ts = pd.Timestamp(START, tz="America/New_York")
    end_ts = pd.Timestamp(END, tz="America/New_York").normalize() + pd.Timedelta(days=1)
    frames = {}
    for s in SYMS:
        df = bt.load_1m(s)
        df = df[(df["ts"] >= start_ts) & (df["ts"] < end_ts)].set_index("ts")
        frames[s] = bt.resample(df, "1min")
    base = frames["QQQ"].index
    cols = {k: [] for k in ("open", "high", "low", "close")}
    for s in SYMS:
        f = frames[s].reindex(base).ffill().bfill()
        for k in cols:
            cols[k].append(f[k].to_numpy())
    a = {k: np.column_stack(v) for k, v in cols.items()}
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(CACHE, ts=base.as_unit("ns").asi8,
                        opens=a["open"], highs=a["high"],
                        lows=a["low"], closes=a["close"])
    print("wrote", CACHE, CACHE.stat().st_size, "bars", len(base),
          base[0], base[-1])


if __name__ == "__main__":
    main()
