r"""Relative Nasdaq flow dip (RN Flow) -- design draft.

STATUS: BACKTESTS PAUSED (2026-11-26). This file is written but not run.
Do not execute it until the lead/user authorizes the development test.
It intentionally does not write result.json on import.

Idea
----
Leveraged-ETF rebalancing and options delta-hedging are concentrated in the
Nasdaq-100 complex and near the close. When QQQ underperforms SPY by a large
standardized amount on a given day, part of that relative move is temporary
flow pressure, not information. Buy TQQQ at the next open and hold for three
sessions to capture the relative reversal; otherwise hold BIL.

This is NOT the old 165-day QQQ/TQQQ trend base:
  * no 100-250 day moving average on QQQ/TQQQ/SPY/NDX;
  * no round-1 4% stop or old base weights;
  * the signal is the relative QQQ-SPY daily return, not an absolute trend;
  * the risk asset is held only on event days.

Data
----
Traded/marked on the local 1-minute QQQ/TQQQ/BIL panel.
Signal uses daily adjusted closes for QQQ and SPY. There is no 1-minute SPY
history for the development period, so the daily close-to-close relative move
is the flow proxy. See HYPOTHESIS.md and provenance.md.

Run (only after authorization):
    $env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
    python research/strategies/letf-rebalance-flow/strategy.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

# --------------------------------------------------------------------------
# Frozen base parameters (pre-registered; neighbours are robustness checks)
# --------------------------------------------------------------------------
DEV_START = "2016-01-04"
DEV_END = "2023-12-29"
Z_WINDOW = 20
Z_ENTRY = -1.25
HOLD_SESSIONS = 3
STOP = None          # base has no stop; -0.10 is a pre-registered variant
RISK_COL = 1         # TQQQ column in the QQQ/TQQQ/BIL panel
BARS_1M = 252 * 390

QQQ_DAILY = ROOT / "data" / "intraday-hf" / "QQQ-1d-yahoo.parquet"
SPY_DAILY = ROOT / "data" / "round3" / "yahoo" / "SPY-1d-yahoo.parquet"


# --------------------------------------------------------------------------
# Daily signal
# --------------------------------------------------------------------------
def load_daily_signal() -> pd.DataFrame:
    """QQQ-SPY relative daily return, its 20-day scale, and the z-score.

    The rolling scale is shifted one day, so z_t uses only data through t-1
    for the scale and the close of t for the return. No look-ahead.
    """
    q = pd.read_parquet(QQQ_DAILY)
    s = pd.read_parquet(SPY_DAILY)
    q["date"] = pd.to_datetime(q["date"]).dt.normalize()
    s["date"] = pd.to_datetime(s["date"]).dt.normalize()
    q = q.set_index("date")["adjclose"].rename("qqq")
    s = s.set_index("date")["adjclose"].rename("spy")
    df = pd.concat([q, s], axis=1).dropna().sort_index()
    df["rel"] = df["qqq"].pct_change() - df["spy"].pct_change()
    df["sigma"] = df["rel"].rolling(Z_WINDOW).std().shift(1)
    df["z"] = df["rel"] / df["sigma"]
    return df


def daily_weights(z: np.ndarray, hold: int = HOLD_SESSIONS,
                  z_entry: float = Z_ENTRY, stop: float | None = STOP,
                  tqqq_open: np.ndarray | None = None,
                  tqqq_close: np.ndarray | None = None) -> np.ndarray:
    """Daily targets set at each close, filled at the next open.

    State machine: one position at a time; ignore new signals while holding.
    hold=3 means the fill day and the next two sessions are held, then BIL.
    The optional stop is checked on daily closes and exits at the next open.
    """
    n = len(z)
    w = np.zeros((n, 3))
    w[:, 2] = 1.0
    in_pos = False
    remaining = 0
    entry_day = -1
    entry_px = np.nan

    for t in range(n):
        # The position held during day t was set at day t-1's close.
        if in_pos and t == entry_day and tqqq_open is not None:
            entry_px = tqqq_open[t]  # known at day t's close

        if in_pos:
            if (stop is not None and tqqq_close is not None
                    and np.isfinite(entry_px)
                    and tqqq_close[t] < entry_px * (1.0 + stop)):
                w[t, :] = 0.0
                w[t, 2] = 1.0          # sell at next open
                in_pos = False
                remaining = 0
                continue
            if remaining <= 0:
                w[t, :] = 0.0
                w[t, 2] = 1.0          # last held session -> sell next open
                in_pos = False
            else:
                w[t, :] = 0.0
                w[t, RISK_COL] = 1.0   # keep holding
                remaining -= 1
        else:
            if np.isfinite(z[t]) and z[t] < z_entry:
                w[t, :] = 0.0
                w[t, RISK_COL] = 1.0   # buy at next open
                in_pos = True
                remaining = hold - 1
                entry_day = t + 1
            else:
                w[t, :] = 0.0
                w[t, 2] = 1.0
    return w


# --------------------------------------------------------------------------
# Daily -> 1-minute mapping (same fill times as the daily run)
# --------------------------------------------------------------------------
def to_minutes(ts: pd.DatetimeIndex, w_daily: np.ndarray,
               daily_dates: pd.DatetimeIndex) -> np.ndarray:
    """Last minute of day t carries w_daily[t]; other minutes carry t-1.

    Identical to research/minute_marks.py:to_minutes for rule='1D'.
    """
    bucket = pd.DatetimeIndex(ts).tz_convert("America/New_York").normalize()
    bucket = bucket.tz_localize(None)
    k = daily_dates.get_indexer(bucket)
    if (k < 0).all():
        raise ValueError("no overlap between 1m sessions and daily signal dates")
    # Tuning fix (2026-11-27): a session with no daily row yet (the live
    # session, or data truncated mid-day) must carry the last known daily
    # target instead of dropping to BIL. Before this fix such a session was
    # forced to BIL for the whole day, so a live run would have sold every
    # open position at the open. Sessions that do have a daily row map
    # exactly as before (headline numbers unchanged).
    prev = daily_dates.searchsorted(bucket, side="right") - 1
    last = np.r_[bucket[1:] != bucket[:-1], True]
    src = np.where(k >= 0, np.where(last, k, k - 1), prev)
    w = np.empty((len(ts), 3))
    w[src >= 0] = w_daily[src[src >= 0]]
    w[src < 0] = (0.0, 0.0, 1.0)
    return w


def session_ohlc(ts: pd.DatetimeIndex, opens: np.ndarray, closes: np.ndarray,
                 dates: pd.DatetimeIndex):
    """First open / last close of each requested date on the 1m panel."""
    sess_dates = pd.DatetimeIndex(ts).tz_convert("America/New_York").normalize()
    sess_dates = sess_dates.tz_localize(None)
    uniq = pd.DatetimeIndex(sorted(set(sess_dates)))
    sess = np.searchsorted(uniq.values, sess_dates.values)
    starts = np.searchsorted(sess, np.arange(len(uniq)), side="left")
    ends = np.searchsorted(sess, np.arange(len(uniq)), side="right")
    o = np.full(len(uniq), np.nan)
    c = np.full(len(uniq), np.nan)
    ok = ends > starts
    o[ok] = opens[starts[ok], RISK_COL]
    c[ok] = closes[ends[ok] - 1, RISK_COL]
    o = pd.Series(o, index=uniq).reindex(dates).to_numpy()
    c = pd.Series(c, index=uniq).reindex(dates).to_numpy()
    return o, c


# --------------------------------------------------------------------------
# Public builder used by the harness / auditor
# --------------------------------------------------------------------------
def build_weights(ts: pd.DatetimeIndex, opens: np.ndarray, closes: np.ndarray,
                  z_entry: float = Z_ENTRY, hold: int = HOLD_SESSIONS,
                  stop: float | None = STOP, signal: pd.DataFrame | None = None):
    """Return (1m weights, info). The strategy is long TQQQ or BIL only."""
    if signal is None:
        signal = load_daily_signal()
    dates = pd.DatetimeIndex(signal.index)
    z = signal["z"].to_numpy()
    if stop is not None:
        tq_open, tq_close = session_ohlc(ts, opens, closes, dates)
    else:
        tq_open, tq_close = None, None
    w_daily = daily_weights(z, hold=hold, z_entry=z_entry, stop=stop,
                            tqqq_open=tq_open, tqqq_close=tq_close)
    w = to_minutes(ts, w_daily, dates)
    info = {
        "dates": dates,
        "z": z,
        "w_daily": w_daily,
        "n_signals": int(np.sum((z < z_entry) & np.isfinite(z))),
        "params": {"z_window": Z_WINDOW, "z_entry": z_entry, "hold": hold,
                   "stop": stop},
    }
    return w, info


# --------------------------------------------------------------------------
# Benchmark helpers (not part of the strategy)
# --------------------------------------------------------------------------
def baseline_daily_weights(qqq_close: np.ndarray) -> np.ndarray:
    """Old 165-day baseline, used only for the correlation benchmark.

    w[t] is the target set at day t's close for day t+1: TQQQ if the close of
    day t is above the 165-day SMA through day t, else BIL.
    """
    s = pd.Series(qqq_close)
    sma = s.rolling(165).mean().to_numpy()
    on = s.to_numpy() > sma
    w = np.zeros((len(s), 3))
    w[:, 2] = 1.0
    w[on, 2] = 0.0
    w[on, 1] = 1.0
    return w


def daily_equity(ts: pd.DatetimeIndex, equity: np.ndarray):
    """Last equity mark of each session."""
    d = pd.DatetimeIndex(ts).tz_convert("America/New_York").normalize()
    uniq = d.unique().sort_values()   # == DatetimeIndex(sorted(set(d)))
    sess = np.searchsorted(uniq.values, d.values)
    starts = np.searchsorted(sess, np.arange(len(uniq)), side="left")
    ends = np.searchsorted(sess, np.arange(len(uniq)), side="right")
    out = np.full(len(uniq), np.nan)
    ok = ends > starts
    out[ok] = equity[ends[ok] - 1]
    return uniq, out


# --------------------------------------------------------------------------
# Authorized-run entry point (not run while backtests are paused)
# --------------------------------------------------------------------------
def main() -> None:
    ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END,
                                 "1min", warmup_days=0)
    w, info = build_weights(ts, opens, closes)
    print(f"dev bars {len(ts):,}  signals {info['n_signals']}")

    result = {
        "agent": "letf-rebalance-flow",
        "original": "research/agents2/letf-rebalance-flow",
        "status": "design_only",   # becomes passed/retired/rejected after audit
        "idea": ("Nasdaq underperformance vs SPY at the close is temporary "
                 "LETF/flow pressure; buy TQQQ for a three-session reversal."),
        "hypothesis": ("z(QQQ-SPY daily relative return) < -1.25 predicts "
                       "positive next-three-session TQQQ returns with <0.60 "
                       "correlation to the old 165-day baseline."),
        "universe": ["TQQQ", "BIL", "QQQ (signal)", "SPY (signal)"],
        "frozen_commit": None,
        "variants_tried": 0,
        "corr_vs_165d_baseline": None,
        "max_corr_vs_other_rebuilds": None,
        "windows": {"dev": {}, "holdout": {}, "10y": {}, "5y": {}},
        "marks": "1m",
        "benchmarks": {},
    }

    # Strategy and baseline, dev only.
    for bp in (1.0, 5.0, 10.0):
        r = bt.run(ts, opens, closes, w, DEV_START, band=0.02, slippage_bps=bp)
        result["windows"]["dev"][f"{bp:g}bp"] = bt.stats(r, BARS_1M)

    # Correlation to the old daily 165-day baseline, on daily marks.
    qd = pd.read_parquet(QQQ_DAILY)
    qd["date"] = pd.to_datetime(qd["date"]).dt.normalize()
    qd = qd.set_index("date")["close"].sort_index()
    wb_daily = baseline_daily_weights(qd.to_numpy())
    wb = to_minutes(ts, wb_daily, pd.DatetimeIndex(qd.index))
    rb = bt.run(ts, opens, closes, wb, DEV_START, band=0.02, slippage_bps=1.0)
    rs = bt.run(ts, opens, closes, w, DEV_START, band=0.02, slippage_bps=1.0)
    _, eq_s = daily_equity(ts, rs["equity"])
    _, eq_b = daily_equity(ts, rb["equity"])
    corr = pd.Series(eq_s).pct_change().corr(pd.Series(eq_b).pct_change())
    result["corr_vs_165d_baseline"] = float(corr)

    # Benchmarks on the same dev window.
    i = bt.start_index(ts, DEV_START)
    result["benchmarks"]["tqqq"] = bt.benchmark(closes[i:, 1], ts[i:], BARS_1M)
    result["benchmarks"]["qqq"] = bt.benchmark(closes[i:, 0], ts[i:], BARS_1M)

    out = ROOT / "research" / "revisit" / "letf-rebalance-flow" / "result.json"
    out.write_text(json.dumps(result, indent=2, default=float), encoding="utf-8")
    print("wrote", out)


if __name__ == "__main__":
    main()
