"""Shared helpers for the 2026-11-27 tuning diagnostics (dev window only)."""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402
from minute_marks import to_minutes  # noqa: E402

HERE = Path(__file__).resolve().parent
DEV_START, DEV_END = "2016-01-04", "2023-12-29"
BARS = 252 * 390
SYMS = ("QQQ", "TQQQ", "BIL")


def load_mod(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def panel1():
    ts, o, c = bt.panel(SYMS, DEV_START, DEV_END, "1min")
    end = pd.Timestamp(DEV_END, tz="America/New_York") + pd.Timedelta(days=1)
    assert ts[-1] < end
    return ts, o, c


def daily(r):
    eq = pd.Series(r["equity"], index=r["ts"])
    return eq.resample("1D").last().dropna()


def stats(r):
    s = bt.stats(r, BARS)
    return {k: float(s[k]) for k in ("cagr", "max_drawdown", "sharpe", "fills", "turnover")}


_BASE = None


def baseline_daily():
    """165-day baseline daily returns, dev only (benchmark, never a signal)."""
    global _BASE
    if _BASE is not None:
        return _BASE

    def y(sym):
        d = pd.read_parquet(f"data/intraday-hf/{sym}-1d-yahoo.parquet")
        d["date"] = pd.to_datetime(d["date"])
        d = d.set_index("date")
        d = d[d.index <= pd.Timestamp(DEV_END)]
        f = d["adjclose"] / d["close"]
        return pd.DataFrame({"open": d["open"] * f, "close": d["adjclose"]})

    q, t, b = y("QQQ"), y("TQQQ"), y("BIL")
    idx = q.index.intersection(t.index).intersection(b.index)
    q, t, b = q.loc[idx], t.loc[idx], b.loc[idx]
    sma = q["close"].rolling(165).mean()
    reg = ((q["close"] > sma) & sma.notna()).to_numpy()
    w = np.zeros((len(idx), 3))
    w[:, 1] = reg
    w[:, 2] = ~reg
    ts = pd.DatetimeIndex(idx).tz_localize("America/New_York")
    o = np.column_stack([q["open"], t["open"], b["open"]])
    c = np.column_stack([q["close"], t["close"], b["close"]])
    r = bt.run(ts, o, c, w, DEV_START, band=0.02, slippage_bps=1.0)
    eq = pd.Series(r["equity"], index=r["ts"])
    _BASE = eq.resample("1D").last().dropna().pct_change().dropna()
    return _BASE


def corr_base(r):
    s = daily(r).pct_change().dropna()
    j = pd.concat([s.rename("s"), baseline_daily().rename("b")], axis=1).dropna()
    return float(j["s"].corr(j["b"]))


def sub_periods(r):
    eq = daily(r)
    out = {}
    for lab, a, b in (("2016-19", "2016", "2019"), ("2020-21", "2020", "2021"),
                      ("2022-23", "2022", "2023")):
        e = eq[a:b]
        prev = eq[:str(int(a) - 1)]
        e0 = prev.iloc[-1] if len(prev) else e.iloc[0]
        yrs = len(e) / 252
        out[lab] = (e.iloc[-1] / e0) ** (1 / yrs) - 1
    return out
