"""Exploration 1: rebuild the winner, inspect vol/corr, test first risk-parity ideas."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

HERE = Path(__file__).resolve().parent
START10, START5, END = "2017-01-03", "2021-10-25", "2026-10-23"
BARS = 252 * 390
SMA_N = 165
MA20 = 20
STOP = 0.04
ARM = 0.01


def load():
    z = np.load(HERE / "panel_1m.npz")
    ts = pd.DatetimeIndex(z["ts"], tz="UTC").tz_convert("America/New_York")
    return ts, z["opens"], z["closes"]


def day_bounds(ts):
    dates = np.array([t.date() for t in ts])
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(ts) - 1]
    return dates, first, last


def daily_from_1m(ts, closes, first, last):
    """Daily close (last bar) and daily open (first bar) for each session."""
    return closes[last], closes[first]


def build_winner(ts, opens, closes, first, last, dates):
    n = len(ts)
    dclose = closes[last, 0]
    sma = pd.Series(dclose).rolling(SMA_N).mean().to_numpy()
    ma20 = pd.Series(dclose).rolling(MA20).mean().to_numpy()
    sma_prev = np.r_[np.nan, sma[:-1]]
    ma20_prev = np.r_[np.nan, ma20[:-1]]
    day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, n]))
    hold = np.zeros(n, bool)
    for f, l in zip(first, last):
        k = int(day_id[f])
        if k == 0:
            continue
        if not (sma_prev[k] == sma_prev[k] and dclose[k - 1] > sma_prev[k]):
            continue
        armed = bool(ma20_prev[k] == ma20_prev[k] and closes[f, 0] < ma20_prev[k] * (1 + ARM))
        base = opens[f, 1]
        state = True
        for i in range(f, l + 1):
            if armed and state and closes[i, 1] < base * (1 - STOP):
                state = False
            hold[i] = state
    w = np.zeros((n, 3))
    w[:, 1] = hold
    w[:, 2] = 1 - hold
    return w


def report(label, ts, opens, closes, w, slip=1.0):
    out = {}
    for lab, start in (("10y", START10), ("5y", START5)):
        r = bt.run(ts, opens, closes, w, start, band=0.02, slippage_bps=slip)
        s = bt.stats(r, BARS)
        out[lab] = (s["cagr"], s["max_drawdown"], s["sharpe"], s["fills"], s["turnover"])
        print(f"  {lab}: CAGR {s['cagr']*100:6.2f}%  DD {s['max_drawdown']*100:6.2f}%  "
              f"Sharpe {s['sharpe']:5.2f}  Calmar {s['cagr']/s['max_drawdown']:5.2f}  fills {s['fills']}")
    return out


def main():
    ts, opens, closes = load()
    dates, first, last = day_bounds(ts)
    print("sessions", len(first), dates[0], dates[-1])
    w = build_winner(ts, opens, closes, first, last, dates)
    print("WINNER reproduction")
    report("winner", ts, opens, closes, w)

    dclose, dopen = daily_from_1m(ts, closes, first, last)
    rets = np.diff(dclose, axis=0) / dclose[:-1]
    for j, name in enumerate(("QQQ", "TQQQ", "BIL")):
        r = rets[:, j]
        print(f"{name}: ann vol 20y {np.std(r[-252*10:])*np.sqrt(252)*100:.1f}%  "
              f"mean {r[-252*10:].mean()*100:.4f}%/d")
    print("corr QQQ/TQQQ", np.corrcoef(rets[-2520:, 0], rets[-2520:, 1])[0, 1])
    print("corr QQQ/BIL", np.corrcoef(rets[-2520:, 0], rets[-2520:, 2])[0, 1])


if __name__ == "__main__":
    main()
