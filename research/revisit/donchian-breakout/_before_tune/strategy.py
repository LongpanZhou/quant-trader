"""Donchian Alignment Ladder (DAL) — standalone rebuild of `donchian-breakout`.

This is a **dev-only spec** (2016-01-04 .. 2023-12-29).  Backtests are paused
until the lead/user authorizes them; do not run this file yet.

The old strategy was a 55-bar 5-minute QQQ breakout sitting on the shared
base "100% TQQQ above the 165-day QQQ SMA, else BIL".  This rebuild removes
that base entirely.  The position is driven by the *alignment of three
Donchian breakout horizons* on QQQ 5-minute bars:

    fast    20-bar high entry / 10-bar low exit + 2.5 x ATR(14) trailing stop
    medium  55-bar high entry / 20-bar low exit
    slow   390-bar high entry / 156-bar low exit   (5-day / 2-day channel)

Alignment A = fast + medium + slow (0..3):

    A = 0 or 1  ->  100% BIL
    A = 2       ->  100% QQQ
    A = 3       ->   TQQQ at a volatility-targeted weight, remainder BIL

There is no moving-average gate of any kind on QQQ/TQQQ/SPY/NDX.  The slow
390-bar channel is a five-day price channel, not a 100-250-day moving average.
The 165-day baseline is used **only** to compute the benchmark correlation
number, never as an input to `build_weights`.

Signals are evaluated at the close of a 5-minute bar and filled at the next
bar's open (bt.py convention).  Equity is marked on 1-minute bars by mapping
the 5-minute weights through `research/minute_marks.py:to_minutes`.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "research")
import bt  # noqa: E402
from minute_marks import to_minutes  # noqa: E402

DEV_START = "2016-01-04"
DEV_END = "2023-12-29"          # subagents must not load 2024-2026
SYMS = ("QQQ", "TQQQ", "BIL")
BARS_1M = 252 * 390

# Core parameters (canonical Turtle lengths; not optimised).
FAST_ENTRY, FAST_EXIT = 20, 10
MED_ENTRY, MED_EXIT = 55, 20
SLOW_ENTRY, SLOW_EXIT = 390, 156
ATR_N = 14
ATR_K = 2.5
TARGET_VOL = 0.30
MIN_TQQQ = 0.20

# Planned one-at-a-time neighbourhood for the ±1-step stability table.
# The authorised sweep will consume these; the default `--dev` run does not.
NEIGHBOURS = {
    "fast_entry": (15, 20, 25),
    "med_entry": (45, 55, 65),
    "slow_entry": (300, 390, 480),
    "atr_k": (2.0, 2.5, 3.0),
    "target_vol": (0.25, 0.30, 0.35),
}


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, n: int = ATR_N) -> np.ndarray:
    """Wilder ATR on the signal bars."""
    pc = np.roll(close, 1)
    pc[0] = close[0]
    tr = np.maximum(high - low, np.maximum(np.abs(high - pc), np.abs(low - pc)))
    return pd.Series(tr).ewm(alpha=1 / n, adjust=False).mean().to_numpy()


def _prior_max(x: np.ndarray, n: int) -> np.ndarray:
    """Highest high of the n bars BEFORE bar i (current bar excluded)."""
    return pd.Series(x).rolling(n).max().shift(1).to_numpy()


def _prior_min(x: np.ndarray, n: int) -> np.ndarray:
    """Lowest low of the n bars BEFORE bar i (current bar excluded)."""
    return pd.Series(x).rolling(n).min().shift(1).to_numpy()


def load_5m(start: str = DEV_START, end: str = DEV_END):
    """Aligned 5-minute panel plus QQQ OHLC and QQQ/TQQQ ATRs."""
    ts, opens, closes = bt.panel(SYMS, start, end, "5min")
    frames = {}
    for sym in ("QQQ", "TQQQ"):
        df = bt.load_1m(sym)
        lo = pd.Timestamp(start, tz="America/New_York")
        hi = pd.Timestamp(end, tz="America/New_York") + pd.Timedelta(days=1)
        df = df[(df["ts"] >= lo) & (df["ts"] < hi)].set_index("ts")
        frames[sym] = bt.resample(df, "5min").reindex(ts).ffill().bfill()
    q = frames["QQQ"]
    t = frames["TQQQ"]
    qh = q["high"].to_numpy()
    ql = q["low"].to_numpy()
    qc = q["close"].to_numpy()
    tc = t["close"].to_numpy()
    atr_q = atr(qh, ql, qc, ATR_N)
    atr_t = atr(t["high"].to_numpy(), t["low"].to_numpy(), tc, ATR_N)
    return ts, opens, closes, qh, ql, qc, tc, atr_q, atr_t


def build_weights(ts, qhigh, qlow, qclose, tclose, atr_q, atr_t,
                  params: dict | None = None):
    """Return (weights, info) for the three-sleeve alignment ladder.

    `weights[i]` is the target set from the close of 5-minute bar i and is
    filled at the open of bar i+1.  Rows are non-negative and sum to 1.
    """
    p = dict(fast_entry=FAST_ENTRY, fast_exit=FAST_EXIT,
             med_entry=MED_ENTRY, med_exit=MED_EXIT,
             slow_entry=SLOW_ENTRY, slow_exit=SLOW_EXIT,
             atr_k=ATR_K, target_vol=TARGET_VOL, min_tqqq=MIN_TQQQ)
    if params:
        p.update(params)

    n = len(ts)
    u_fast = _prior_max(qhigh, p["fast_entry"])
    u_med = _prior_max(qhigh, p["med_entry"])
    u_slow = _prior_max(qhigh, p["slow_entry"])
    l_fast = _prior_min(qlow, p["fast_exit"])
    l_med = _prior_min(qlow, p["med_exit"])
    l_slow = _prior_min(qlow, p["slow_exit"])
    ann_atr_q = atr_q / np.maximum(qclose, 1e-9) * np.sqrt(252 * 78)
    ann_atr_t = atr_t / np.maximum(tclose, 1e-9) * np.sqrt(252 * 78)

    states = np.zeros((n, 3), dtype=bool)       # fast, medium, slow
    in_fast = in_med = in_slow = False
    peak_fast = 0.0
    for i in range(n):
        # --- fast sleeve: 20-bar high entry, 10-bar low or 2.5xATR stop ---
        if in_fast:
            peak_fast = max(peak_fast, qclose[i])
            stop = peak_fast - p["atr_k"] * atr_q[i]
            if (np.isfinite(l_fast[i]) and qclose[i] < l_fast[i]) or qclose[i] < stop:
                in_fast = False
        if (not in_fast) and np.isfinite(u_fast[i]) and qclose[i] > u_fast[i]:
            in_fast = True
            peak_fast = qclose[i]
        # --- medium sleeve: 55/20 ---
        if in_med and np.isfinite(l_med[i]) and qclose[i] < l_med[i]:
            in_med = False
        if (not in_med) and np.isfinite(u_med[i]) and qclose[i] > u_med[i]:
            in_med = True
        # --- slow sleeve: 390/156 (5-day / 2-day) ---
        if in_slow and np.isfinite(l_slow[i]) and qclose[i] < l_slow[i]:
            in_slow = False
        if (not in_slow) and np.isfinite(u_slow[i]) and qclose[i] > u_slow[i]:
            in_slow = True
        states[i] = (in_fast, in_med, in_slow)

    align = states.sum(axis=1).astype(int)
    w = np.zeros((n, 3))
    tqqq_w = 0.0
    last_align = -1
    changes = 0
    for i in range(n):
        a = int(align[i])
        if a != last_align:
            changes += 1
            if a == 3:
                frac = p["target_vol"] / max(float(np.nan_to_num(ann_atr_t[i], nan=1.0)), 1e-6)
                tqqq_w = float(np.clip(frac, p["min_tqqq"], 1.0))
            last_align = a
        if a <= 1:
            w[i, 2] = 1.0
        elif a == 2:
            w[i, 0] = 1.0
        else:
            w[i, 1] = tqqq_w
            w[i, 2] = 1.0 - tqqq_w

    info = {
        "params": p,
        "align_counts": np.bincount(align, minlength=4).tolist(),
        "align_changes": int(changes),
        "avg_align": float(align.mean()),
        "last_tqqq_weight": float(tqqq_w),
    }
    return w, info


def load_1m(start: str = DEV_START, end: str = DEV_END):
    return bt.panel(SYMS, start, end, "1min")


def baseline_daily_returns():
    """The 165-day baseline, used ONLY for the correlation benchmark.

    This function is never called by `build_weights`; it exists solely to
    compute the correlation number required by the brief.  It is not a gate,
    not a filter, and not an input to the strategy.  Removing it would make
    the correlation unverifiable.
    """
    def y(sym):
        d = pd.read_parquet(f"data/intraday-hf/{sym}-1d-yahoo.parquet")
        d["date"] = pd.to_datetime(d["date"])
        d = d.set_index("date")
        f = d["adjclose"] / d["close"]
        return pd.DataFrame({"open": d["open"] * f, "close": d["adjclose"]})

    q, t, b = y("QQQ"), y("TQQQ"), y("BIL")
    idx = q.index.intersection(t.index).intersection(b.index)
    q, t, b = q.loc[idx], t.loc[idx], b.loc[idx]
    sma = q["close"].rolling(165).mean()  # BENCHMARK ONLY — never called from build_weights
    reg = ((q["close"] > sma) & sma.notna()).to_numpy()
    w = np.zeros((len(idx), 3))
    w[:, 1] = reg
    w[:, 2] = ~reg
    ts = pd.DatetimeIndex(idx).tz_localize("America/New_York")
    o = np.column_stack([q["open"], t["open"], b["open"]])
    c = np.column_stack([q["close"], t["close"], b["close"]])
    r = bt.run(ts, o, c, w, DEV_START, band=0.02, slippage_bps=1.0)
    return bt.daily_last(r["equity"], r["ts"]).pct_change().dropna()


def evaluate(ts1, o1, c1, w1, bps: float):
    r = bt.run(ts1, o1, c1, w1, start=DEV_START, band=0.02,
               slippage_bps=bps)
    s = bt.stats(r, BARS_1M)
    out = {
        "cagr": float(s["cagr"]),
        "max_drawdown": float(s["max_drawdown"]),
        "sharpe": float(s["sharpe"]),
        "sortino": float(s["sortino"]),
        "volatility": float(s["volatility"]),
        "fills": int(s["fills"]),
        "turnover": float(s["turnover"]),
        "exposure": float(s["exposure"]),
        "ending_equity": float(s["ending_equity"]),
        "years": float(s["years"]),
    }
    return out, r


def _daily_returns(r):
    return bt.daily_last(r["equity"], r["ts"]).pct_change().dropna()


def _bench(ts1, c1, col: int) -> dict:
    i = bt.start_index(ts1, DEV_START)
    b = bt.benchmark(c1[i:, col], ts1[i:], BARS_1M)
    return {k: (float(v) if isinstance(v, (float, np.floating)) else v)
            for k, v in b.items()}


def run_dev():
    """Dev-only 1/5/10 bp evaluation.  Not to be run until authorised."""
    here = Path(__file__).resolve().parent
    ts5, o5, c5, qh, ql, qc, tc, atr_q, atr_t = load_5m()
    w5, info = build_weights(ts5, qh, ql, qc, tc, atr_q, atr_t)
    ts1, o1, c1 = load_1m()
    w1 = to_minutes(ts5, w5, ts1, "5min")

    dev = {}
    r1 = None
    for bps in (1, 5, 10):
        m, r = evaluate(ts1, o1, c1, w1, bps)
        dev[f"{bps}bp"] = m
        if bps == 1:
            r1 = r

    strat_ret = _daily_returns(r1)
    base_ret = baseline_daily_returns()
    joined = pd.concat([strat_ret.rename("s"), base_ret.rename("b")], axis=1).dropna()
    corr = float(joined["s"].corr(joined["b"]))

    result = {
        "agent": "donchian-breakout",
        "original": "research/agents/donchian-breakout",
        "status": "pending_audit",
        "idea": ("A Donchian breakout is only worth leveraging when short, medium "
                 "and long breakout horizons agree; the alignment count is the "
                 "trend/sizing signal."),
        "hypothesis": ("Scaling from BIL to QQQ to TQQQ with three-horizon "
                       "breakout alignment captures trend persistence while "
                       "cutting whipsaw exposure, with low correlation to the "
                       "old 165-day MA base."),
        "universe": ["QQQ", "TQQQ", "BIL"],
        "frozen_commit": None,
        "variants_tried": 0,
        "corr_vs_165d_baseline": corr,
        "max_corr_vs_other_rebuilds": None,
        "windows": {
            "dev": dev,
            "holdout": {},
            "10y": {},
            "5y": {},
        },
        "marks": "1m",
        "info": info,
        "benchmarks": {
            "tqqq": _bench(ts1, c1, 1),
            "qqq": _bench(ts1, c1, 0),
            "spy": {"available": False,
                    "reason": "no 2016-2023 SPY daily/1-minute data locally; "
                              "dukascopy cache is 2026 only"},
            "original": {"note": "compare after the frozen run; original "
                                 "result.json carries the 10y/5y windows"},
        },
    }
    out = here / "result.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result["windows"]["dev"], indent=2))
    print("corr vs 165d baseline:", round(corr, 4))
    print("wrote", out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", action="store_true",
                    help="run dev-only 1/5/10 bp evaluation (requires authorisation)")
    args = ap.parse_args()
    if not args.dev:
        raise SystemExit("Backtests are paused. Pass --dev only after authorisation.")
    run_dev()
