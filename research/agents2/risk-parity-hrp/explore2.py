"""Exploration 2: static QQQ/TQQQ mixes with the 165d regime (+/- the 4% stop).

QQQ/TQQQ daily correlation is 0.9995, so a QQQ/TQQQ mix is a pure leverage
choice. This maps the CAGR/DD frontier before adding any risk model.
"""
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


def regime_and_stop(ts, opens, closes, first, last):
    n = len(ts)
    dclose = closes[last, 0]
    sma = pd.Series(dclose).rolling(SMA_N).mean().to_numpy()
    ma20 = pd.Series(dclose).rolling(MA20).mean().to_numpy()
    sma_prev = np.r_[np.nan, sma[:-1]]
    ma20_prev = np.r_[np.nan, ma20[:-1]]
    day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, n]))
    d = len(first)
    risk_on = np.zeros(d, bool)
    risk_on[1:] = dclose[:-1] > sma_prev[1:]
    stopper = np.zeros(n, bool)          # True => stop fired this bar
    for f, l in zip(first, last):
        k = int(day_id[f])
        if k == 0 or not risk_on[k]:
            continue
        armed = bool(ma20_prev[k] == ma20_prev[k] and closes[f, 0] < ma20_prev[k] * (1 + ARM))
        base = opens[f, 1]
        state = True
        for i in range(f, l + 1):
            if armed and state and closes[i, 1] < base * (1 - STOP):
                state = False
                stopper[i] = True
            if not state:
                stopper[i] = True
    return risk_on, stopper, day_id


def weights_mix(risk_on, stopper, day_id, n, x_tqqq, use_stop=True):
    """x_tqqq of the equity sleeve in TQQQ, rest QQQ; BIL when regime off."""
    w = np.zeros((n, 3))
    on = risk_on[day_id]
    dead = stopper if use_stop else np.zeros(n, bool)
    equity = on & ~dead
    w[equity, 1] = x_tqqq
    w[equity, 0] = 1 - x_tqqq
    w[~on, 2] = 1.0
    w[on & dead, 2] = 1.0
    return w


def metrics(ts, opens, closes, w, slip=1.0):
    out = {}
    for lab, start in (("10y", START10), ("5y", START5)):
        r = bt.run(ts, opens, closes, w, start, band=0.02, slippage_bps=slip)
        s = bt.stats(r, BARS)
        out[lab] = dict(cagr=s["cagr"], dd=s["max_drawdown"], sharpe=s["sharpe"],
                        calmar=s["cagr"] / s["max_drawdown"],
                        fills=s["fills"], turnover=s["turnover"],
                        exposure=s["exposure"])
    return out


def show(label, m):
    a, b = m["10y"], m["5y"]
    print(f"{label:<34} 10y {a['cagr']*100:6.2f}/{a['dd']*100:5.2f} C{a['calmar']:4.2f} "
          f"| 5y {b['cagr']*100:6.2f}/{b['dd']*100:5.2f} C{b['calmar']:4.2f} "
          f"| fills {a['fills']:4d}")


def main():
    ts, opens, closes = load()
    dates, first, last = day_bounds(ts)
    risk_on, stopper, day_id = regime_and_stop(ts, opens, closes, first, last)
    n = len(ts)
    print(f"risk-on days {risk_on.mean()*100:.1f}%")
    for use_stop in (True, False):
        print(f"\n=== static mixes, stop={use_stop} ===")
        for x in (1.0, 0.95, 0.9, 0.85, 0.8, 0.7, 0.6, 0.5, 0.35, 0.25):
            w = weights_mix(risk_on, stopper, day_id, n, x, use_stop)
            show(f"x_tqqq={x:.2f}", metrics(ts, opens, closes, w))


if __name__ == "__main__":
    main()
