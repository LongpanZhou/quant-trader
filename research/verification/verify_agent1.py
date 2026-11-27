r"""Independent replication and causality test for the Agent 1 leader.

Rules replicated from research/agents/daily-regime-minute-entry/report.md:

  * risk-on when QQQ's prior daily close is above its 165-day SMA;
  * on risk-on days, arm a 4% stop from the session open when QQQ's first
    minute close is below its prior 20-day SMA * 1.01;
  * if armed and TQQQ closes 4% below the session open, go to BIL at the
    next minute's open and stay there for the rest of the day and night;
  * otherwise hold TQQQ.

This script deliberately re-implements the rules instead of importing the
agent's code, then checks that truncating the data at 2022-01-03 does not
change any weight before that date (a direct no-look-ahead test).

Run from the repo root:

    $env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
    python research/verification/verify_agent1.py
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
SMA_N, MA_FAST = 165, 20
STOP, ARM_BUF = 0.04, 0.01
BARS_PER_YEAR = 252 * 390


def build_weights(ts: pd.DatetimeIndex, opens: np.ndarray, closes: np.ndarray):
    dates = np.array([t.date() for t in ts])
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(dates) - 1]
    qqq_close = closes[:, 0]
    tqqq_close = closes[:, 1]

    dclose = qqq_close[last]
    sma = pd.Series(dclose).rolling(SMA_N).mean().to_numpy()
    ma20 = pd.Series(dclose).rolling(MA_FAST).mean().to_numpy()

    hold = np.zeros(len(ts), dtype=bool)
    stops = []
    for k, (f, l) in enumerate(zip(first, last)):
        if k == 0 or not np.isfinite(sma[k - 1]) or not dclose[k - 1] > sma[k - 1]:
            continue
        armed = np.isfinite(ma20[k - 1]) and qqq_close[f] < ma20[k - 1] * (1.0 + ARM_BUF)
        base = opens[f, 1]
        state = True
        for i in range(f, l + 1):
            if armed and state and tqqq_close[i] < base * (1.0 - STOP):
                state = False
                stops.append((str(dates[f]), str(ts[i].time())))
            hold[i] = state

    weights = np.zeros((len(ts), 3))
    weights[:, 1] = hold
    weights[:, 2] = 1.0 - weights[:, 1]
    return weights, stops


def year_drawdown(ts: pd.DatetimeIndex, values: np.ndarray) -> dict[int, float]:
    out = {}
    for year in sorted(set(ts.year)):
        mask = ts.year == year
        v = values[mask]
        if len(v) < 2:
            continue
        peak = np.maximum.accumulate(v)
        out[int(year)] = float(-(v / peak - 1.0).min())
    return out


def main() -> None:
    ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), START10, END, "1min")
    weights, stops = build_weights(ts, opens, closes)
    print(f"panel {ts[0]} .. {ts[-1]}  bars {len(ts):,}  stop events {len(stops)}")

    # Causality: the weights before 2022-01-03 must not change when all later
    # bars are removed.
    cutoff = int(ts.searchsorted(pd.Timestamp("2022-01-03", tz="America/New_York")))
    w_short, _ = build_weights(ts[:cutoff], opens[:cutoff], closes[:cutoff])
    same = np.array_equal(w_short, weights[:cutoff])
    print(f"causality: truncation at 2022-01-03 leaves prior weights unchanged = {same}")
    if not same:
        raise SystemExit("look-ahead detected: weights changed when future bars were removed")

    for label, start in (("10y", START10), ("5y", START5)):
        for slip in (1.0, 5.0, 10.0):
            result = bt.run(ts, opens, closes, weights, start, band=0.02, slippage_bps=slip)
            s = bt.stats(result, BARS_PER_YEAR)
            print(
                f"{label} {slip:4.0f}bp  CAGR {s['cagr']*100:6.2f}%  "
                f"DD {s['max_drawdown']*100:5.2f}%  Sharpe {s['sharpe']:4.2f}  "
                f"fills {s['fills']:4.0f}  turnover {s['turnover']:7.1f}x"
            )

        result = bt.run(ts, opens, closes, weights, start, band=0.02, slippage_bps=1.0)
        i = bt.start_index(ts, start)
        eq, tq = result["equity"], closes[i:, 1]
        years = bt.yearly(ts[i:], eq, tq)
        sdd = year_drawdown(ts[i:], eq)
        bdd = year_drawdown(ts[i:], tq)
        print(f"\n{label} yearly return / max drawdown (strategy vs TQQQ)")
        wins = 0
        dd_wins = 0
        for year in sorted(years):
            r = years[year]
            wins += r["strategy"] > r["benchmark"]
            dd_wins += sdd[year] < bdd[year]
            print(
                f"  {year}: {r['strategy']*100:7.2f}% / {sdd[year]*100:5.2f}%  vs "
                f"{r['benchmark']*100:7.2f}% / {bdd[year]*100:5.2f}%  "
                f"return={'win' if r['strategy'] > r['benchmark'] else 'lag'}  "
                f"dd={'lower' if sdd[year] < bdd[year] else 'higher'}"
            )
        print(f"  return beats TQQQ in {wins}/{len(years)} years; "
              f"drawdown lower in {dd_wins}/{len(years)} years\n")


if __name__ == "__main__":
    main()
