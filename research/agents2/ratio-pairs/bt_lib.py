"""Shared helpers for the TQQQ/QQQ ratio experiments (research only)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

START10, START5, END = "2017-01-03", "2021-10-25", "2026-10-23"
BARS = 252 * 390
CACHE = ROOT / "research" / "agents" / "daily-regime-minute-entry" / "panel_cache.npz"


def load_panel():
    z = np.load(CACHE)
    ts = pd.DatetimeIndex(
        pd.to_datetime(z["ts"], unit="ns", utc=True).tz_convert("America/New_York")
    )
    return ts, z["opens"], z["closes"]


def day_bounds(ts):
    dates = np.array([t.date() for t in ts])
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(ts) - 1]
    return dates, first, last


def daily_frame(ts, opens, closes):
    dates, first, last = day_bounds(ts)
    d = pd.DataFrame(
        {
            "qqq_o": opens[first, 0],
            "qqq_c": closes[last, 0],
            "tqqq_o": opens[first, 1],
            "tqqq_c": closes[last, 1],
            "bil_c": closes[last, 2],
            "qqq_1m": closes[first, 0],
        },
        index=pd.DatetimeIndex(ts[last]).tz_localize(None).normalize(),
    )
    d["ratio"] = d["tqqq_c"] / d["qqq_c"]
    d["logr"] = np.log(d["ratio"])
    return d


def add_ratio_features(d: pd.DataFrame) -> pd.DataFrame:
    r = d["ratio"]
    for n in (20, 60, 100, 120, 150, 200, 250):
        d[f"ext{n}"] = np.log(r / r.rolling(n).mean())
    lr = d["logr"]
    d["vol20"] = lr.diff().rolling(20).std()
    d["z20"] = np.log(r / r.rolling(20).mean()) / d["vol20"]
    d["dd252"] = r / r.rolling(252).max() - 1.0
    d["mom20"] = lr - lr.shift(20)
    return d


def shifter(s: pd.Series) -> pd.Series:
    """Value known at the prior close (used for same-day decisions)."""
    return s.shift(1)


def winner_state(ts, opens, closes, sma_n=165, stop=0.04, ma_fast=20, arm_buf=0.01):
    """Per-minute TQQQ hold mask and per-day regime for the round-1 winner."""
    dates, first, last = day_bounds(ts)
    n = len(ts)
    qqq_close, tqqq_close = closes[:, 0], closes[:, 1]
    dc = qqq_close[last]
    sma = pd.Series(dc).rolling(sma_n).mean().to_numpy()
    ma20 = pd.Series(dc).rolling(ma_fast).mean().to_numpy()
    sma_prev = np.r_[np.nan, sma[:-1]]
    ma20_prev = np.r_[np.nan, ma20[:-1]]
    hold = np.zeros(n, bool)
    risk_on = np.zeros(len(first), bool)
    for k, (f, l) in enumerate(zip(first, last)):
        if k == 0 or not (sma_prev[k] == sma_prev[k] and dc[k - 1] > sma_prev[k]):
            continue
        risk_on[k] = True
        armed = bool(ma20_prev[k] == ma20_prev[k] and qqq_close[f] < ma20_prev[k] * (1 + arm_buf))
        base = opens[f, 1]
        state = True
        for i in range(f, l + 1):
            if armed and state and tqqq_close[i] < base * (1 - stop):
                state = False
            hold[i] = state
    return hold, risk_on, first, last


def weights_from_daily(ts, day_target: np.ndarray, first, last,
                       stopped: np.ndarray | None = None) -> np.ndarray:
    """Broadcast per-day target weights (n_days, 3) to minutes.

    `stopped` (per-minute bool) forces BIL after an intraday stop.
    """
    n = len(ts)
    w = np.zeros((n, 3))
    for k, (f, l) in enumerate(zip(first, last)):
        w[f:l + 1] = day_target[k]
    if stopped is not None:
        w[stopped] = (0.0, 0.0, 1.0)
    return w


def metrics(ts, opens, closes, w, slip=1.0, start=START10):
    r = bt.run(ts, opens, closes, w, start, band=0.02, slippage_bps=slip)
    s = bt.stats(r, BARS)
    i = bt.start_index(ts, start)
    s["bench_tqqq"] = bt.benchmark(closes[i:, 1], ts[i:], BARS)
    s["fills"] = r["fills"]
    s["turnover"] = r["turnover"]
    return s


def show(label, s):
    print(
        f"{label:44s} CAGR {s['cagr']*100:6.2f}%  DD {s['max_drawdown']*100:5.2f}%  "
        f"Sharpe {s['sharpe']:4.2f}  fills {s['fills']:5d}  turn {s['turnover']:7.1f}x"
    )
