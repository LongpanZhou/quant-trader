"""Shared helpers for the daily-regime + minute-entry research agent.

Loads a cached 1-minute panel (QQQ/TQQQ/BIL opens, closes, volumes) warmed up
500 calendar days before 2017-01-03, and provides signal helpers. All signals
use only bars <= i; the harness fills at i+1 open.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

CACHE = Path(__file__).resolve().parent / "panel_cache.npz"
START10, START5, END = "2017-01-03", "2021-10-25", "2026-10-23"


def load_panel(force: bool = False):
    """Return ts, opens, highs, lows, closes, vols (each n x 3) for QQQ,TQQQ,BIL."""
    if CACHE.exists() and not force:
        z = np.load(CACHE)
        ts = pd.DatetimeIndex(pd.to_datetime(z["ts"], unit="ns", utc=True).tz_convert("America/New_York"))
        return ts, z["opens"], z["highs"], z["lows"], z["closes"], z["vols"]

    symbols = ("QQQ", "TQQQ", "BIL")
    ts, opens, closes = bt.panel(symbols, START10, END, "1min", warmup_days=500)
    highs, lows, vols = [], [], []
    for sym in symbols:
        df = bt.load_1m(sym)
        df = df.set_index("ts")
        highs.append(df["high"].reindex(ts).ffill().bfill().to_numpy())
        lows.append(df["low"].reindex(ts).ffill().bfill().to_numpy())
        vols.append(df["volume"].reindex(ts).fillna(0.0).to_numpy())
        # sanity: closes must agree with bt.panel
        assert np.allclose(df["close"].reindex(ts).ffill().bfill().to_numpy(), closes[:, len(highs) - 1],
                           rtol=1e-6, atol=1e-6), sym
    np.savez_compressed(CACHE, ts=ts.tz_convert("UTC").tz_localize(None).to_numpy(dtype="datetime64[ns]").astype("int64"), opens=opens, highs=np.column_stack(highs),
                        lows=np.column_stack(lows), closes=closes,
                        vols=np.column_stack(vols))
    return ts, opens, np.column_stack(highs), np.column_stack(lows), closes, np.column_stack(vols)


def load_arrays(force: bool = False):
    ts, opens, highs, lows, closes, vols = load_panel(force=force)
    dates = np.array([d for d in ts.date])
    first, last = day_bounds(dates)
    return dict(ts=ts, dates=dates, first=first, last=last,
                opens=opens, highs=highs, lows=lows, closes=closes, vols=vols)


def day_bounds(dates: np.ndarray):
    """First/last bar index arrays, one entry per trading day."""
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(dates) - 1]
    return first, last


def daily_regime(ts, qqq_close, n: int = 165, lag: int = 1):
    """Boolean per minute: QQQ daily close > n-day SMA as of `lag` days back.

    lag=1 reproduces 'signal at previous close, hold next day'.
    """
    dates = ts.date
    first, last = day_bounds(dates)
    dc = qqq_close[last]
    sma = pd.Series(dc).rolling(n).mean().to_numpy()
    reg_day = np.zeros(len(dc), bool)
    if lag == 1:
        reg_day[1:] = dc[:-1] > sma[:-1]
    else:
        reg_day[lag:] = dc[:-lag] > sma[:-lag]
    day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, len(dates)]))
    return reg_day[day_id], dc, sma, dates, first, last


def session_vwap(high, low, close, vol, dates, first, last):
    """Cumulative session VWAP per bar (includes current bar)."""
    tp = (high + low + close) / 3.0
    pv = tp * vol
    out = np.empty(len(close))
    for f, l in zip(first, last):
        cs = np.cumsum(pv[f:l + 1])
        cv = np.cumsum(vol[f:l + 1])
        with np.errstate(invalid="ignore", divide="ignore"):
            v = np.where(cv > 0, cs / cv, np.nan)
        # if no volume at all use typical price
        v = np.where(np.isfinite(v), v, tp[f:l + 1])
        out[f:l + 1] = v
    return out


def ema(x, span):
    return pd.Series(x).ewm(span=span, adjust=False).mean().to_numpy()


def apply_intraday_rule(ts, closes, vols, regime, rule_fn, **kw):
    """Generic per-day state machine -> weights (n,3) with TQQQ/BIL split.

    rule_fn(day_slice_arrays, regime_on, params) -> bool array 'hold TQQQ'.
    """
    dates = ts.date
    first, last = day_bounds(dates)
    n = len(closes)
    hold = np.zeros(n, bool)
    for k, (f, l) in enumerate(zip(first, last)):
        hold[f:l + 1] = rule_fn(k, f, l, regime[f], closes[:, 1], vols[:, 1], **kw)
    w = np.zeros((n, 3))
    w[:, 1] = hold.astype(float)
    w[:, 2] = 1.0 - w[:, 1]
    return w


def summarize(label, ts, opens, closes, w, slippage_bps=1.0, bars_per_year=252 * 390):
    out = {}
    for start in (START10, START5):
        r = bt.run(ts, opens, closes, w, start, band=0.02, slippage_bps=slippage_bps)
        s = bt.stats(r, bars_per_year)
        i = bt.start_index(ts, start)
        b = bt.benchmark(closes[i:, 1], ts[i:], bars_per_year)
        s["bench"] = b
        out[start] = s
        print(f"{label:34s} {start[:4]}  CAGR {s['cagr']*100:6.2f}%  DD {s['max_drawdown']*100:5.2f}%  "
              f"Sharpe {s['sharpe']:4.2f}  fills {s['fills']:6,d}  turn {s['turnover']:7.1f}x  "
              f"exp {s['exposure']*100:5.1f}%")
    return out
