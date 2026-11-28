"""Standalone intraday 60-minute EMA trend strategy (revisit of `dual-speed-regime`).

This is NOT the old 165-day regime with the overlay removed. The old base is gone.
The 60-minute QQQ EMA cross owns an intraday-only TQQQ position:

  * flat 09:30-10:29 and 15:30-16:00, flat every night;
  * long TQQQ only while QQQ's 60-minute EMA(10) is above EMA(30);
  * 100% TQQQ in a strong trend (spread > +0.30%), 50% otherwise, BIL for the rest;
  * exit on a trend flip, a 2.5 x ATR(14) trailing stop, or the 15:29 hard flat;
  * no re-entry on a day after an ATR stop.

No QQQ/TQQQ/SPY/NDX 100-250-day moving average is used anywhere in the position
logic. The 165-day series appears only in `baseline_165_for_correlation`, a
measurement benchmark required by the brief; `build_weights` never calls it.

Development period: 2016-01-04 .. 2023-12-29. Holdout is not computed here.

Run (only after the lead/user authorizes the new test):
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/strategies/dual-speed-regime/strategy.py
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

DEV_START, DEV_END = "2016-01-04", "2023-12-29"
HOLDOUT_START, HOLDOUT_END = "2024-01-02", "2026-10-23"
BPY = 252 * 390
SYMS = ("QQQ", "TQQQ", "BIL")

# strategy parameters (pre-registered; plateau center, not a fitted peak)
FAST, SLOW = 10, 30
ENTRY_BAND = 0.0
STRONG = 0.003
ATR_K = 2.5
WARMUP_BARS = 60
LAST_ENTRY_OFFSET = 299      # 14:29 bar close is the last entry
EXIT_OFFSET = 359            # 15:29 bar close -> flat at 15:30


# --------------------------------------------------------------------------- #
# bars and indicators
# --------------------------------------------------------------------------- #
def day_index(ts: pd.DatetimeIndex):
    dates = bt.session_dates(ts)
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(dates) - 1]
    day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, len(dates)]))
    return dates, first, last, day_id


def bars_60m(price: np.ndarray, first: np.ndarray, last: np.ndarray):
    """Session-aligned 60-minute bars: 09:30-10:29, ..., last (possibly 30m) bar."""
    ends, closes, day_of = [], [], []
    for k, (f, l) in enumerate(zip(first, last)):
        e = f + 59
        while e < l:
            ends.append(e)
            closes.append(price[e])
            day_of.append(k)
            e += 60
        ends.append(l)
        closes.append(price[l])
        day_of.append(k)
    return np.asarray(ends), np.asarray(closes), np.asarray(day_of)


def ema(x: np.ndarray, span: int) -> np.ndarray:
    a = 2.0 / (span + 1.0)
    out = np.empty(len(x))
    e = np.nan
    for i, v in enumerate(x):
        e = v if not np.isfinite(e) else a * v + (1.0 - a) * e
        out[i] = e
    return out


def atr14(closes: np.ndarray) -> np.ndarray:
    """Close-to-close ATR proxy on 60-minute bars (14-bar mean absolute change)."""
    diff = np.abs(np.diff(closes, prepend=np.nan))
    return pd.Series(diff).rolling(14).mean().to_numpy()


# --------------------------------------------------------------------------- #
# weights
# --------------------------------------------------------------------------- #
def build_weights(ts, opens, closes, fast: int = FAST, slow: int = SLOW,
                  entry_band: float = ENTRY_BAND, strong: float = STRONG,
                  atr_k: float = ATR_K, warmup_bars: int = WARMUP_BARS,
                  last_entry_offset: int = LAST_ENTRY_OFFSET,
                  exit_offset: int = EXIT_OFFSET):
    """Return (weights, info) for the intraday-only 60-minute trend strategy.

    `weights[i]` is set at bar i's close and fills at bar i+1's open. The
    position is flat outside 10:30-15:30 and flat overnight.
    """
    dates, first, last, day_id = day_index(ts)
    ends, bar_close_q, day_of = bars_60m(closes[:, 0], first, last)
    ends_t, bar_close_t, day_of_t = bars_60m(closes[:, 1], first, last)
    if not (np.array_equal(ends, ends_t) and np.array_equal(day_of, day_of_t)):
        raise ValueError("QQQ/TQQQ 60-minute bar grids do not match")
    ef = ema(bar_close_q, fast)
    es = ema(bar_close_q, slow)
    spread = ef / es - 1.0
    atr = atr14(bar_close_t)

    n = len(ts)
    hold = np.zeros(n)
    info = dict(entries=0, exits=0, stops=0, days=len(first), days_traded=0,
                bars=len(ends), fast=fast, slow=slow, entry_band=entry_band,
                strong=strong, atr_k=atr_k)

    counts = np.bincount(day_of, minlength=len(first))
    j = 0
    for k, (f, l) in enumerate(zip(first, last)):
        nb = counts[k]
        in_pos = False
        stopped = False
        size = 0.0
        high = np.nan
        traded_today = False
        for m in range(nb):
            b = j + m
            e = ends[b]
            c = bar_close_q[b]          # QQQ close: signal
            ct = bar_close_t[b]         # TQQQ close: position high/ATR stop
            s = spread[b]

            hard_exit = (e >= f + exit_offset) or (m == nb - 1)
            can_enter = (b >= warmup_bars) and (e <= f + last_entry_offset)

            if in_pos:
                high = max(high, ct)
                stop_hit = bool(np.isfinite(atr[b]) and ct < high - atr_k * atr[b])
                if hard_exit or s < 0.0 or stop_hit:
                    if stop_hit and not hard_exit and s >= 0.0:
                        stopped = True
                        info["stops"] += 1
                    in_pos = False
                    size = 0.0
                    info["exits"] += 1
                else:
                    size = 1.0 if s > strong else 0.5
            elif (not stopped) and can_enter and s > entry_band:
                in_pos = True
                high = ct
                size = 1.0 if s > strong else 0.5
                info["entries"] += 1

            nxt = ends[b + 1] if (b + 1 < len(ends) and day_of[b + 1] == k) else l + 1
            hold[e:nxt] = size
            if size > 0.0:
                traded_today = True

        if traded_today:
            info["days_traded"] += 1
        j += nb

    w = np.zeros((n, 3))
    w[:, 1] = hold
    w[:, 2] = 1.0 - hold
    info["exposure"] = float(np.mean(hold))
    info["avg_size_when_long"] = float(hold[hold > 0].mean()) if (hold > 0).any() else 0.0
    return w, info


# --------------------------------------------------------------------------- #
# measurement only: old 165-day baseline (never used for positions)
# --------------------------------------------------------------------------- #
def baseline_165_for_correlation(ts, closes, first, last, day_id):
    """TQQQ when QQQ prior close > 165-day SMA, else BIL. Benchmark only."""
    dc = closes[last, 0]
    sma = pd.Series(dc).rolling(165).mean().to_numpy()
    reg = np.zeros(len(dc), bool)
    reg[1:] = dc[:-1] > sma[:-1]
    hold = reg[day_id].astype(float)
    w = np.zeros((len(ts), 3))
    w[:, 1] = hold
    w[:, 2] = 1.0 - hold
    return w


# --------------------------------------------------------------------------- #
# reporting helpers
# --------------------------------------------------------------------------- #
def dd_episodes(ts, eq, top=4):
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    out = []
    i, n = 0, len(eq)
    while i < n:
        if dd[i] >= -1e-9:
            i += 1
            continue
        j = i
        while j < n and dd[j] < -1e-9:
            j += 1
        p = int(np.argmax(eq[: i + 1]))
        seg = dd[p:j]
        t = p + int(np.argmin(seg))
        out.append((float(-seg.min()), str(ts[p])[:16], str(ts[t])[:16]))
        i = j + 1
    out.sort(reverse=True)
    return out[:top]


def daily_returns(eq, ts):
    return pd.Series(eq, index=ts).resample("1D").last().pct_change().dropna()


def window_block(r, ts, closes):
    """ts/closes must already be sliced to the window of r."""
    s = bt.stats(r, BPY)
    return {
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
        "benchmark_tqqq": bt.benchmark(closes[:, 1], ts, BPY),
        "yearly": {str(k): {"strategy": float(v["strategy"]),
                            "tqqq": float(v["benchmark"])}
                   for k, v in bt.yearly(ts, r["equity"], closes[:, 1]).items()},
        "dd_episodes": dd_episodes(ts, r["equity"], 4),
    }


def sub_period(r, ts, a, z):
    ser = pd.Series(r["equity"], index=ts).loc[a:z]
    yrs = (ser.index[-1] - ser.index[0]).total_seconds() / (365.25 * 86400)
    return {
        "cagr": float((ser.iloc[-1] / ser.iloc[0]) ** (1 / yrs) - 1),
        "max_drawdown": float(-(ser / ser.cummax() - 1).min()),
    }


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main():
    ts, opens, closes = bt.panel(SYMS, DEV_START, DEV_END, "1min", warmup_days=500)
    w, info = build_weights(ts, opens, closes)
    i0 = bt.start_index(ts, DEV_START)
    ts_dev, closes_dev = ts[i0:], closes[i0:]

    out = {
        "agent": "dual-speed-regime",
        "original": "research/agents2/dual-speed-regime",
        "status": "pending_test",
        "idea": "QQQ's 60-minute EMA cross measures intraday trend persistence; "
                "hold TQQQ only while that trend is up and flat overnight.",
        "hypothesis": "An intraday-only, trend-tiered TQQQ position has development "
                      "correlation below 0.60 with the 165-day overnight base and a "
                      "positive Sharpe after 5 bp costs.",
        "universe": ["QQQ (signal)", "TQQQ (long)", "BIL (cash)"],
        "frozen_commit": None,
        "variants_tried": 0,
        "corr_vs_165d_baseline": None,
        "max_corr_vs_other_rebuilds": None,
        "marks": "1m",
        "parameters": info,
        "windows": {"dev": {}, "holdout": None, "10y": None, "5y": None},
        "benchmarks": {},
        "sub_periods": {},
    }

    curves = {}
    for slip in (1.0, 5.0, 10.0):
        key = f"{slip:.0f}bp"
        r = bt.run(ts, opens, closes, w, DEV_START, band=0.02, slippage_bps=slip)
        out["windows"]["dev"][key] = window_block(r, ts_dev, closes_dev)
        if slip == 1.0:
            curves["strategy"] = r

    # correlation vs the old base, daily returns, development period
    dates, first, last, day_id = day_index(ts)
    wb = baseline_165_for_correlation(ts, closes, first, last, day_id)
    rb = bt.run(ts, opens, closes, wb, DEV_START, band=0.02, slippage_bps=1.0)
    a = daily_returns(curves["strategy"]["equity"], curves["strategy"]["ts"])
    b = daily_returns(rb["equity"], rb["ts"])
    joined = pd.concat([a, b], axis=1, join="inner").dropna()
    corr = float(joined.iloc[:, 0].corr(joined.iloc[:, 1]))
    active = joined[joined.iloc[:, 0] != 0.0]
    corr_active = float(active.iloc[:, 0].corr(active.iloc[:, 1])) if len(active) > 2 else None
    out["corr_vs_165d_baseline"] = corr
    out["corr_vs_165d_baseline_active_days"] = corr_active
    out["active_days"] = int(len(active))
    curves["baseline"] = rb

    # benchmarks
    out["benchmarks"] = {
        "tqqq": bt.benchmark(closes_dev[:, 1], ts_dev, BPY),
        "qqq": bt.benchmark(closes_dev[:, 0], ts_dev, BPY),
        "bil": bt.benchmark(closes_dev[:, 2], ts_dev, BPY),
        "spy": None,
        "original": {
            "source": "research/agents2/dual-speed-regime/result.json (published; "
                      "10y/5y overlap the 2024-2026 holdout)",
            "10y": {"cagr": 0.5880, "max_drawdown": 0.4456},
            "5y": {"cagr": 0.4988, "max_drawdown": 0.3349},
        },
    }
    out["sub_periods"] = {
        "2016-19": sub_period(curves["strategy"], curves["strategy"]["ts"], "2016-01-04", "2019-12-31"),
        "2020-21": sub_period(curves["strategy"], curves["strategy"]["ts"], "2020-01-02", "2021-12-31"),
        "2022-23": sub_period(curves["strategy"], curves["strategy"]["ts"], "2022-01-03", "2023-12-29"),
    }

    # automatic status rules from the pre-registered falsifiers (dev only)
    dev5 = out["windows"]["dev"]["5bp"]
    out["status"] = (
        "passed"
        if (corr < 0.60 and dev5["cagr"] > 0.05 and dev5["sharpe"] > 0.40)
        else "rejected"
    )
    out["falsifiers"] = {
        "corr_below_0.60": corr < 0.60,
        "cagr_5bp_above_0.05": dev5["cagr"] > 0.05,
        "sharpe_5bp_above_0.40": dev5["sharpe"] > 0.40,
        "no_holdout_inspected": True,
    }

    (Path(__file__).resolve().parent / "result.json").write_text(json.dumps(out, indent=2))
    print(f"dev 1bp  CAGR {out['windows']['dev']['1bp']['cagr']*100:6.2f}%  "
          f"DD {out['windows']['dev']['1bp']['max_drawdown']*100:5.2f}%  "
          f"Sharpe {out['windows']['dev']['1bp']['sharpe']:.2f}  "
          f"fills {out['windows']['dev']['1bp']['fills']}")
    print(f"corr vs 165d {corr:.3f}  status {out['status']}")
    print("wrote", Path(__file__).resolve().parent / "result.json")


if __name__ == "__main__":
    main()
