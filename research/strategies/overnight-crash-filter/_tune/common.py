"""Shared helpers for the 2026-11-27 tuning pass (dev window only)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
SLUG = HERE.parent
ROOT = SLUG.parents[2]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

DEV_START, DEV_END = "2016-01-04", "2023-12-29"
BARS = 252 * 390


def load_strategy(path=None, name="ocf_strategy"):
    path = Path(path or SLUG / "strategy.py")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def panel():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END, "1min", warmup_days=0)
    end = pd.Timestamp(DEV_END, tz="America/New_York") + pd.Timedelta(days=1)
    assert ts[-1] < end, "panel extends past dev"
    return ts, o, c


def daily_rets(ts, eq):
    s = pd.Series(eq, index=ts)
    return s.groupby(s.index.date).last().pct_change().dropna()


def stats(r):
    s = bt.stats(r, BARS)
    return {k: float(s[k]) for k in ("cagr", "max_drawdown", "sharpe", "volatility")} | {
        "fills": int(s["fills"])}


def sub_cagr(ts, eq):
    s = pd.Series(eq, index=ts)
    out = {}
    for tag, a, b in (("16-19", "2016-01-04", "2020-01-01"),
                      ("20-21", "2020-01-01", "2022-01-01"),
                      ("22-23", "2022-01-01", "2023-12-30")):
        m = (s.index >= pd.Timestamp(a, tz="America/New_York")) & (
            s.index < pd.Timestamp(b, tz="America/New_York"))
        x = s[m].to_numpy()
        yrs = (s.index[m][-1] - s.index[m][0]).days / 365.25
        pk = np.maximum.accumulate(x)
        out[tag] = ((x[-1] / x[0]) ** (1 / yrs) - 1, float(-(x / pk - 1).min()))
    return out
