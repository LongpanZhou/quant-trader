"""Exploration: volatility/ATR measures for the crash-stop overlay.

Reads the round-1 winner's cached 1-minute panel (read-only) to save the
~2 minute panel build, rebuilds the winner's weights, and prints the
distribution of candidate stop-distance measures.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/agents2/vol-scaled-crash-stop/explore.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

CACHE = ROOT / "research" / "agents" / "daily-regime-minute-entry" / "panel_cache.npz"
START10, START5, END = "2017-01-03", "2021-10-25", "2026-10-23"
BARS = 252 * 390


def load_cache():
    z = np.load(CACHE)
    ts = pd.DatetimeIndex(
        pd.to_datetime(z["ts"], unit="ns", utc=True).tz_convert("America/New_York")
    )
    return (ts, z["opens"], z["highs"], z["lows"], z["closes"], z["vols"])


def day_bounds(dates):
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(dates) - 1]
    return first, last


def daily_regime(ts, qqq_close, n=165, lag=1):
    dates = np.array([t.date() for t in ts])
    first, last = day_bounds(dates)
    dc = qqq_close[last]
    sma = pd.Series(dc).rolling(n).mean().to_numpy()
    reg_day = np.zeros(len(dc), bool)
    reg_day[lag:] = dc[:-lag] > sma[:-lag]
    day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, len(dates)]))
    return reg_day, dc, sma, dates, first, last, day_id


def winner_weights(ts, opens, closes, stop=0.04, ma_fast=20, arm_buf=0.01,
                   sma_n=165, post=None):
    """Winner rules, parameterised post-stop allocation.

    post: None -> all BIL after stop (winner). Otherwise callable
    (i, f, l) -> (w_qqq, w_tqqq, w_bil) for bars i..l.
    """
    reg_day, dc, sma, dates, first, last, day_id = daily_regime(ts, closes[:, 0], sma_n)
    ma20 = pd.Series(dc).rolling(ma_fast).mean().to_numpy()
    ma20_prev = np.r_[np.nan, ma20[:-1]]
    n = len(ts)
    w = np.zeros((n, 3))
    stops = []
    for k, (f, l) in enumerate(zip(first, last)):
        if not reg_day[k]:
            w[f:l + 1, 2] = 1.0
            continue
        armed = bool(ma20_prev[k] == ma20_prev[k] and closes[f, 0] < ma20_prev[k] * (1 + arm_buf))
        base = opens[f, 1]
        state = 1.0  # fraction still in TQQQ
        stop_i = None
        for i in range(f, l + 1):
            if armed and state > 0 and closes[i, 1] < base * (1 - stop):
                state = 0.0
                stop_i = i
                stops.append((str(dates[f]), str(ts[i].time())))
                break
        if stop_i is None:
            w[f:l + 1, 1] = 1.0
        else:
            w[f:stop_i + 1, 1] = 1.0
            if post is None:
                w[stop_i + 1:l + 1, 2] = 1.0
            else:
                w[stop_i + 1:l + 1, :] = post
    return w, len(stops), dates, first, last, dc


def summarize(label, ts, opens, closes, w, slippage_bps=1.0):
    out = {}
    for start in (START10, START5):
        r = bt.run(ts, opens, closes, w, start, band=0.02, slippage_bps=slippage_bps)
        s = bt.stats(r, BARS)
        i = bt.start_index(ts, start)
        b = bt.benchmark(closes[i:, 1], ts[i:], BARS)
        s["bench"] = b
        out[start] = s
        print(f"{label:40s} {start[:4]}  CAGR {s['cagr']*100:6.2f}%  DD {s['max_drawdown']*100:5.2f}%  "
              f"Sharpe {s['sharpe']:4.2f}  fills {s['fills']:5,d}  exp {s['exposure']*100:5.1f}%")
    return out


def main():
    t0 = time.time()
    ts, opens, highs, lows, closes, vols = load_cache()
    print(f"panel {len(ts):,} bars {ts[0]} .. {ts[-1]}  load {time.time()-t0:.1f}s")
    dates = np.array([t.date() for t in ts])
    first, last = day_bounds(dates)
    n_days = len(first)

    # ---- daily OHLC of TQQQ from the 1m panel -----------------------------
    t_high = np.maximum.reduceat(highs[:, 1], first)
    t_low = np.minimum.reduceat(lows[:, 1], first)
    t_close = closes[last, 1]
    t_open = opens[first, 1]
    q_close = closes[last, 0]

    # daily ATR(14) through prior close
    prev_close = np.r_[np.nan, t_close[:-1]]
    tr = np.maximum.reduce([t_high - t_low, np.abs(t_high - prev_close), np.abs(t_low - prev_close)])
    atr14 = pd.Series(tr).rolling(14).mean().to_numpy()
    atr14_pct = atr14 / t_close

    # 20-day realized vol of TQQQ daily log returns
    r1 = np.diff(np.log(t_close), prepend=np.nan)
    vol20 = pd.Series(r1).rolling(20).std(ddof=0).to_numpy()

    # 60-day vol for reference
    vol60 = pd.Series(r1).rolling(60).std(ddof=0).to_numpy()

    # ---- 1m realized vol of the prior session, scaled to a day ------------
    # per-session std of 1m log returns (intraday only), floored by a small n
    r1m = np.zeros(len(ts))
    r1m[1:] = np.diff(np.log(closes[:, 1]))
    # zero out first bar of each day (overnight jump)
    r1m[first] = 0.0
    sess_var = np.add.reduceat(r1m ** 2, first) / np.maximum(np.diff(np.r_[first, len(ts)]), 1)
    sess_sigma_day = np.sqrt(sess_var * 390.0)  # intraday daily vol
    sess_sigma_prev = np.r_[np.nan, sess_sigma_day[:-1]]

    # ---- 5m ATR(14) of the prior session, last 14 bars --------------------
    # Build 5m bars per session from 1m, take ATR(14) at the end of session.
    atr5_prev = np.full(n_days, np.nan)
    for k, (f, l) in enumerate(zip(first, last)):
        nb = (l - f + 1) // 5
        if nb < 15:
            continue
        h = highs[f:f + nb * 5, 1].reshape(nb, 5).max(axis=1)
        lo = lows[f:f + nb * 5, 1].reshape(nb, 5).min(axis=1)
        c = closes[f:f + nb * 5, 1].reshape(nb, 5)[:, -1]
        pc = np.r_[np.nan, c[:-1]]
        t5 = np.maximum.reduce([h - lo, np.abs(h - pc), np.abs(lo - pc)])
        a = pd.Series(t5).rolling(14).mean().to_numpy()[-1]
        atr5_prev[k] = a / c[-1]
    atr5_prev = np.r_[np.nan, atr5_prev[:-1]]

    print("\nStop-distance candidates (% of TQQQ price, per day, through prior close)")
    rows = {
        "daily ATR(14)%": atr14_pct,
        "20d realized daily vol": vol20,
        "60d realized daily vol": vol60,
        "1m realized vol (prior session, x sqrt390)": sess_sigma_prev,
        "5m ATR(14) last 70min (prior session)": atr5_prev,
    }
    print(f"{'measure':44s} {'p5':>6s} {'p25':>6s} {'med':>6s} {'p75':>6s} {'p95':>6s}")
    for name, x in rows.items():
        x = x[np.isfinite(x)]
        q = np.percentile(x, [5, 25, 50, 75, 95]) * 100
        print(f"{name:44s} " + " ".join(f"{v:6.2f}" for v in q))

    # yearly medians to see regime dependence
    print("\nyearly median (%), 20d vol / daily ATR / 1m vol")
    yrs = np.array([d.year for d in dates[last]])
    for y in sorted(set(yrs)):
        m = (yrs == y)
        print(f"  {y}  vol20 {np.nanmedian(vol20[m])*100:5.2f}   "
              f"atr14 {np.nanmedian(atr14_pct[m])*100:5.2f}   "
              f"1mvol {np.nanmedian(sess_sigma_prev[m])*100:5.2f}   "
              f"atr5 {np.nanmedian(atr5_prev[m])*100:5.2f}")

    # ---- reproduce the winner --------------------------------------------
    print("\n--- reproduction ---")
    t0 = time.time()
    w, nstops, *_ = winner_weights(ts, opens, closes, 0.04)
    print(f"weights built {time.time()-t0:.1f}s stops={nstops}")
    t0 = time.time()
    res = summarize("WINNER 4% stop -> BIL", ts, opens, closes, w, 1.0)
    print(f"bt.run+stats {time.time()-t0:.1f}s per pair")
    print("winner target: 10y 58.80/44.56  5y 49.88/33.49")


if __name__ == "__main__":
    main()
