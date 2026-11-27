"""Cache the 1m panel, build daily aggregates, replicate the winner baseline."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

HERE = Path(__file__).resolve().parent
START10, START5, END = "2017-01-03", "2021-10-25", "2026-10-23"
BARS_PER_YEAR = 252 * 390
CACHE = HERE / "panel.npz"


def load_panel():
    if CACHE.exists():
        z = np.load(CACHE)
        ts = pd.DatetimeIndex(z["ts"].astype("int64"))
        return ts, z["opens"].astype(float), z["closes"].astype(float)
    ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), START10, END, "1min")
    np.savez_compressed(
        CACHE,
        ts=ts.tz_convert("UTC").tz_localize(None).astype("datetime64[ns]").astype("int64"),
        opens=opens.astype(np.float32),
        closes=closes.astype(np.float32),
    )
    return ts, opens, closes


def day_bounds(dates):
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(dates) - 1]
    return first, last


def daily_rv(closes, dates):
    """Within-day sum of squared 1m log returns, per symbol."""
    n, k = closes.shape
    d = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    r = np.zeros((n, k))
    r[1:] = np.log(np.maximum(closes[1:], 1e-9) / np.maximum(closes[:-1], 1e-9))
    r[d] = 0.0
    out = np.zeros((len(d), k))
    for j in range(k):
        out[:, j] = np.add.reduceat(r[:, j], d)
    return out


def sma(x, n):
    return pd.Series(x).rolling(n).mean().to_numpy()


def winner_weights(ts, opens, closes, stop=0.04, sma_n=165, ma_fast=20,
                   arm_buf=0.01):
    dates = np.array([t.date() for t in ts])
    first, last = day_bounds(dates)
    n = len(ts)
    qc, tc = closes[:, 0], closes[:, 1]
    dclose = qc[last]
    s = sma(dclose, sma_n)
    m = sma(dclose, ma_fast)
    s_prev = np.r_[np.nan, s[:-1]]
    m_prev = np.r_[np.nan, m[:-1]]
    hold = np.zeros(n, dtype=bool)
    stops = []
    for k, (f, l) in enumerate(zip(first, last)):
        risk_on = (k > 0) and (dclose[k - 1] > s_prev[k])
        if not risk_on:
            continue
        armed = m_prev[k] == m_prev[k] and qc[f] < m_prev[k] * (1.0 + arm_buf)
        base = opens[f, 1]
        state = True
        for i in range(f, l + 1):
            if armed and state and tc[i] < base * (1.0 - stop):
                state = False
                stops.append((str(dates[f]), str(ts[i].time())))
            hold[i] = state
    w = np.zeros((n, 3))
    w[:, 1] = hold
    w[:, 2] = 1.0 - w[:, 1]
    return w, dict(stops=stops, first=first, last=last, dclose=dclose)


def main():
    t0 = time.time()
    ts, opens, closes = load_panel()
    dates = np.array([t.date() for t in ts])
    first, last = day_bounds(dates)
    print(f"panel {len(ts):,} bars  {ts[0]} .. {ts[-1]}  load {time.time()-t0:.0f}s")

    w, diag = winner_weights(ts, opens, closes)
    print("stop events", len(diag["stops"]))

    for label, start in (("10y", START10), ("5y", START5)):
        r = bt.run(ts, opens, closes, w, start, band=0.02, slippage_bps=1.0)
        s = bt.stats(r, BARS_PER_YEAR)
        i0 = bt.start_index(ts, start)
        b = bt.benchmark(closes[i0:, 1], ts[i0:], BARS_PER_YEAR)
        print(f"{label} winner cagr {s['cagr']*100:.2f}% dd {s['max_drawdown']*100:.2f}% "
              f"sharpe {s['sharpe']:.2f} fills {s['fills']} "
              f"| tqqq {b['cagr']*100:.2f}% / {b['max_drawdown']*100:.2f}%")

    # vol stats
    rv = daily_rv(closes, dates)
    for j, name in enumerate(("QQQ", "TQQQ", "BIL")):
        v20 = np.sqrt(pd.Series(rv[:, j]).rolling(20).mean().to_numpy() * 252)
        vv = v20[np.isfinite(v20)]
        print(name, "vol20 pct", np.percentile(vv, [5, 25, 50, 75, 95]).round(3))

    dates_u = dates[first]
    dclose = closes[last, 0]
    print("sessions", len(dates_u), dates_u[0], dates_u[-1])
    np.savez_compressed(
        HERE / "daily.npz",
        rv=rv,
        first=first,
        last=last,
        dates=dates_u.astype("datetime64[D]").astype("int64"),
    )


if __name__ == "__main__":
    main()
