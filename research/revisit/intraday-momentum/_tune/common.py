"""Shared helpers for the 2026-11-27 tuning diagnostics (dev window only)."""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(HERE.parent))
import bt  # noqa: E402
import strategy as S  # noqa: E402

DEV_START, DEV_END = S.DEV_START, S.DEV_END
assert DEV_END == "2023-12-29"

_cache = {}


def panel():
    if "p" not in _cache:
        _cache["p"] = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END, "1min")
        ts = _cache["p"][0]
        assert ts[-1] < pd.Timestamp("2023-12-30", tz="America/New_York")
    return _cache["p"]


def daily_eq(res):
    eq = pd.Series(res["equity"], index=res["ts"])
    d = eq.groupby(eq.index.date).last()
    d.index = pd.to_datetime(d.index)
    return d


def stats(res):
    s = bt.stats(res, S.BARS_PER_YEAR)
    return {k: float(s[k]) for k in ("cagr", "max_drawdown", "sharpe", "fills", "turnover", "exposure")}


def baseline_daily_ret():
    if "base" not in _cache:
        _cache["base"] = S._baseline_daily().pct_change()
    return _cache["base"]


def corr_base(res):
    a = daily_eq(res).pct_change()
    b = baseline_daily_ret()
    both = pd.concat([a, b], axis=1).dropna()
    return float(both.corr().iloc[0, 1])


def run(w, slip=1.0):
    ts, o, c = panel()
    return bt.run(ts, o, c, w, DEV_START, band=0.02, slippage_bps=slip)


def run_many(ws, slip=1.0):
    ts, o, c = panel()
    return bt.run_many(ts, o, c, ws, DEV_START, band=0.02, slippage_bps=slip, threads=1)


def sub_cagr(res):
    d = daily_eq(res)
    out = {}
    for lab, (a, b) in {"2016-19": ("2016", "2019"), "2020-21": ("2020", "2021"),
                        "2022-23": ("2022", "2023")}.items():
        x = d[a:b]
        prev = d[:str(int(a) - 1)]
        start = prev.iloc[-1] if len(prev) else x.iloc[0]
        yrs = (x.index[-1] - (prev.index[-1] if len(prev) else x.index[0])).days / 365.25
        out[lab] = float((x.iloc[-1] / start) ** (1 / yrs) - 1)
    return out
