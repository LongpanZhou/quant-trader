r"""Robustness checks for the Agent 1 winner.

Adds three things the agent report only summarises:

  1. a small parameter grid (stop level, arm gate, regime length);
  2. one extra bar of execution delay;
  3. rolling 3-year windows vs TQQQ, to test consistency rather than just the
     two headline windows.

Run from the repo root:

    $env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
    python research/verification/robustness_agent1.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

START10, START5, END = "2017-01-03", "2021-10-25", "2026-10-23"
BARS_PER_YEAR = 252 * 390


def build_weights(
    ts: pd.DatetimeIndex,
    opens: np.ndarray,
    closes: np.ndarray,
    sma_n: int = 165,
    ma_fast: int = 20,
    stop: float = 0.04,
    arm_buf: float = 0.01,
) -> np.ndarray:
    dates = np.array([t.date() for t in ts])
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(dates) - 1]
    qqq_close = closes[:, 0]
    tqqq_close = closes[:, 1]

    dclose = qqq_close[last]
    sma = pd.Series(dclose).rolling(sma_n).mean().to_numpy()
    ma = pd.Series(dclose).rolling(ma_fast).mean().to_numpy()

    hold = np.zeros(len(ts), dtype=bool)
    for k, (f, l) in enumerate(zip(first, last)):
        if k == 0 or not np.isfinite(sma[k - 1]) or not dclose[k - 1] > sma[k - 1]:
            continue
        armed = np.isfinite(ma[k - 1]) and qqq_close[f] < ma[k - 1] * (1.0 + arm_buf)
        base = opens[f, 1]
        state = True
        for i in range(f, l + 1):
            if armed and state and tqqq_close[i] < base * (1.0 - stop):
                state = False
            hold[i] = state

    weights = np.zeros((len(ts), 3))
    weights[:, 1] = hold
    weights[:, 2] = 1.0 - weights[:, 1]
    return weights


def metrics(result: dict) -> dict:
    return bt.stats(result, BARS_PER_YEAR)


def daily_series(ts: pd.DatetimeIndex, values: np.ndarray):
    s = pd.Series(values, index=ts)
    d = s.groupby(s.index.date).last()
    return pd.DatetimeIndex(pd.to_datetime(d.index)), d.to_numpy(dtype=float)


def window_cagr_dd(values: np.ndarray, i: int, j: int) -> tuple[float, float]:
    v = values[i:j]
    years = (j - i) / 252.0
    cagr = (v[-1] / v[0]) ** (1.0 / years) - 1.0
    peak = np.maximum.accumulate(v)
    dd = float(-(v / peak - 1.0).min())
    return float(cagr), dd


def rolling_3y(ts, equity, tqqq_close) -> None:
    dts, deq = daily_series(ts, equity)
    _, dtq = daily_series(ts, tqqq_close)
    starts = pd.date_range("2017-01-03", "2023-10-01", freq="QS")
    rows = []
    for start in starts:
        i = int(dts.searchsorted(start))
        j = int(dts.searchsorted(start + pd.DateOffset(years=3)))
        if i >= j or j > len(dts) or j - i < 500:
            continue
        c_s, d_s = window_cagr_dd(deq, i, j)
        c_b, d_b = window_cagr_dd(dtq, i, j)
        rows.append((start.date(), c_s, d_s, c_b, d_b))
    both = sum(c_s > c_b and d_s < d_b for _, c_s, d_s, c_b, d_b in rows)
    ret = sum(c_s > c_b for _, c_s, _, c_b, _ in rows)
    dd = sum(d_s < d_b for _, _, d_s, _, d_b in rows)
    print(f"\nrolling 3y windows: {len(rows)} starts")
    print(f"  return beats TQQQ: {ret}/{len(rows)}; drawdown lower: {dd}/{len(rows)}; both: {both}/{len(rows)}")
    for start, c_s, d_s, c_b, d_b in rows:
        mark = "both" if c_s > c_b and d_s < d_b else ("ret" if c_s > c_b else ("dd" if d_s < d_b else "lag"))
        print(f"  {start}: {c_s*100:6.2f}%/{d_s*100:5.2f}%  vs {c_b*100:6.2f}%/{d_b*100:5.2f}%  {mark}")


def main() -> None:
    ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), START10, END, "1min")
    print(f"panel {ts[0]} .. {ts[-1]}  bars {len(ts):,}")

    grid = [
        ("base 4% stop, MA20", dict(stop=0.04, ma_fast=20, sma_n=165)),
        ("stop 2.5%", dict(stop=0.025, ma_fast=20, sma_n=165)),
        ("stop 3%", dict(stop=0.03, ma_fast=20, sma_n=165)),
        ("stop 5%", dict(stop=0.05, ma_fast=20, sma_n=165)),
        ("stop 6%", dict(stop=0.06, ma_fast=20, sma_n=165)),
        ("arm MA50", dict(stop=0.04, ma_fast=50, sma_n=165)),
        ("regime SMA150", dict(stop=0.04, ma_fast=20, sma_n=150)),
        ("regime SMA180", dict(stop=0.04, ma_fast=20, sma_n=180)),
    ]

    for label, params in grid:
        w = build_weights(ts, opens, closes, **params)
        out = []
        for start in (START10, START5):
            s = metrics(bt.run(ts, opens, closes, w, start, band=0.02, slippage_bps=1.0))
            out.append(f"{s['cagr']*100:6.2f}%/{s['max_drawdown']*100:5.2f}%")
        print(f"{label:22s} 10y {out[0]}  5y {out[1]}")

    w = build_weights(ts, opens, closes)
    w_delay = np.vstack([np.zeros((1, 3)), w[:-1]])
    print("\nexecution delay: signal fills one extra bar later")
    for start in (START10, START5):
        s = metrics(bt.run(ts, opens, closes, w_delay, start, band=0.02, slippage_bps=1.0))
        print(f"  {start}: CAGR {s['cagr']*100:.2f}%  DD {s['max_drawdown']*100:.2f}%  Sharpe {s['sharpe']:.2f}")

    r = bt.run(ts, opens, closes, w, START10, band=0.02, slippage_bps=1.0)
    i = bt.start_index(ts, START10)
    rolling_3y(ts[i:], r["equity"], closes[i:, 1])


if __name__ == "__main__":
    main()
