"""Exploration for the standalone 60-minute EMA rebuild (development only).

Period: 2016-01-04 .. 2023-12-29. No holdout inspection.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

DEV_START, DEV_END = "2016-01-04", "2023-12-29"
BPY = 252 * 390
SYMS = ("QQQ", "TQQQ", "BIL")


def day_index(ts):
    dates = bt.session_dates(ts)
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(dates) - 1]
    day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, len(dates)]))
    return dates, first, last, day_id


def bars_60m(price, first, last):
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


def ema(x, span):
    a = 2.0 / (span + 1.0)
    out = np.empty(len(x))
    e = np.nan
    for i, v in enumerate(x):
        e = v if not np.isfinite(e) else a * v + (1 - a) * e
        out[i] = e
    return out


def map_state(n, ends, day_of, bar_state, first):
    """state[e] = bar state; applies from the bar's last minute (fill next minute)."""
    state = np.zeros(n, bool)
    prev = False
    j = 0
    counts = np.bincount(day_of, minlength=len(first))
    for k, f in enumerate(first):
        nb = counts[k]
        state[f:ends[j]] = prev
        for m in range(nb - 1):
            state[ends[j + m]:ends[j + m + 1]] = bar_state[j + m]
        state[ends[j + nb - 1]:] = bar_state[j + nb - 1] if False else state[ends[j + nb - 1]:]
        # the last bar's state only matters at the next open; set it at l
        state[ends[j + nb - 1]] = bar_state[j + nb - 1]
        prev = bar_state[j + nb - 1]
        j += nb
    return state


def weights_from_state(state, asset=1):
    w = np.zeros((len(state), 3))
    if asset == 1:
        w[:, 1] = state.astype(float)
    elif asset == 0:
        w[:, 0] = state.astype(float)
    else:  # 3-state: QQQ when state, BIL otherwise is same as asset 0
        w[:, 0] = state.astype(float)
    w[:, 2] = 1.0 - w.sum(axis=1)
    return w


def baseline_165(ts, closes, first, last, day_id):
    dc = closes[last, 0]
    sma = pd.Series(dc).rolling(165).mean().to_numpy()
    reg = np.zeros(len(dc), bool)
    reg[1:] = dc[:-1] > sma[:-1]
    w = np.zeros((len(ts), 3))
    w[:, 1] = reg[day_id].astype(float)
    w[:, 2] = 1.0 - w[:, 1]
    return w


def stats_dev(w, ts, opens, closes, slip=1.0):
    r = bt.run(ts, opens, closes, w, DEV_START, band=0.02, slippage_bps=slip)
    s = bt.stats(r, BPY)
    return s, r


def daily_corr(eq_a, ts_a, eq_b, ts_b):
    a = pd.Series(eq_a, index=ts_a).resample("1D").last().pct_change().dropna()
    b = pd.Series(eq_b, index=ts_b).resample("1D").last().pct_change().dropna()
    j = pd.concat([a, b], axis=1, join="inner").dropna()
    return float(j.iloc[:, 0].corr(j.iloc[:, 1]))


def main():
    ts, opens, closes = bt.panel(SYMS, DEV_START, DEV_END, "1min", warmup_days=500)
    dates, first, last, day_id = day_index(ts)
    print(f"bars {len(ts):,} days {len(first)} {ts[0]} .. {ts[-1]}", flush=True)
    ends, bar_close, day_of = bars_60m(closes[:, 0], first, last)
    print(f"60m bars {len(ends):,}", flush=True)

    w_base = baseline_165(ts, closes, first, last, day_id)
    s, r = stats_dev(w_base, ts, opens, closes)
    print(f"165d baseline dev: CAGR {s['cagr']*100:.2f} DD {s['max_drawdown']*100:.2f} "
          f"Sharpe {s['sharpe']:.2f} fills {s['fills']}", flush=True)
    base_daily = pd.Series(r["equity"], index=r["ts"]).resample("1D").last().pct_change().dropna()

    pairs = [(10, 30), (15, 45), (20, 50), (20, 60), (25, 75), (30, 90), (40, 120),
             (50, 150), (60, 180), (20, 100), (10, 60)]
    ws, labels = [], []
    for fast, slow in pairs:
        ef = ema(bar_close, fast)
        es = ema(bar_close, slow)
        state = map_state(len(ts), ends, day_of, ef > es, first)
        ws.append(weights_from_state(state, 1))
        labels.append(f"TQ {fast}/{slow}")
        ws.append(weights_from_state(state, 0))
        labels.append(f"QQ {fast}/{slow}")
    rs = bt.run_many(ts, opens, closes, ws, start=DEV_START, band=0.02, slippage_bps=1.0)
    for lab, rr in zip(labels, rs):
        s = bt.stats(rr, BPY)
        a = pd.Series(rr["equity"], index=rr["ts"]).resample("1D").last().pct_change().dropna()
        corr = float(pd.concat([a, base_daily], axis=1, join="inner").dropna().corr().iloc[0, 1])
        print(f"{lab:12s} CAGR {s['cagr']*100:6.2f} DD {s['max_drawdown']*100:5.2f} "
              f"Sharpe {s['sharpe']:5.2f} fills {s['fills']:6d} corr {corr:.3f}", flush=True)


if __name__ == "__main__":
    main()
