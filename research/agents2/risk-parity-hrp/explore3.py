"""Exploration 3: where does the stopped TQQQ sleeve go, and do vol brakes help?

Engine: per-session target weights from a daily risk model, then a minute-level
4% stop that zeroes the TQQQ sleeve and sends it to a destination
(BIL / QQQ / mix). Next-bar fills throughout.
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
SMA_N, MA20, STOP, ARM = 165, 20, 0.04, 0.01


def load():
    z = np.load(HERE / "panel_1m.npz")
    return pd.DatetimeIndex(z["ts"], tz="UTC").tz_convert("America/New_York"), z["opens"], z["closes"]


def bounds(ts):
    dates = np.array([t.date() for t in ts])
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    return dates, first, np.r_[first[1:] - 1, len(ts) - 1]


def day_setup(ts, opens, closes, first, last):
    n = len(ts)
    dclose = closes[last, 0]
    sma = pd.Series(dclose).rolling(SMA_N).mean().to_numpy()
    ma20 = pd.Series(dclose).rolling(MA20).mean().to_numpy()
    sma_prev, ma20_prev = np.r_[np.nan, sma[:-1]], np.r_[np.nan, ma20[:-1]]
    day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, n]))
    d = len(first)
    risk_on = np.zeros(d, bool)
    risk_on[1:] = dclose[:-1] > sma_prev[1:]
    # armed per session
    armed = np.zeros(d, bool)
    for k in range(d):
        if k == 0 or not risk_on[k]:
            continue
        armed[k] = bool(ma20_prev[k] == ma20_prev[k] and closes[first[k], 0] < ma20_prev[k] * (1 + ARM))
    stopped = np.zeros(n, bool)
    for k in range(d):
        if not armed[k]:
            continue
        f, l = first[k], last[k]
        base = opens[f, 1]
        dead = False
        for i in range(f, l + 1):
            if not dead and closes[i, 1] < base * (1 - STOP):
                dead = True
            stopped[i] = dead
    return risk_on, armed, stopped, day_id, closes[last]


def build(risk_on, stopped, day_id, n, wt_day, dest):
    """wt_day: (d,) TQQQ weight on risk-on days (rest QQQ). dest: 0=BIL,1=QQQ,2=50/50."""
    w = np.zeros((n, 3))
    on = risk_on[day_id]
    tq = wt_day[day_id]
    w[:, 1] = np.where(on & ~stopped, tq, 0.0)
    q = np.where(on & ~stopped, 1.0 - tq, 0.0)
    if dest == 0:
        w[:, 2] = np.where(on & ~stopped, 0.0, 1.0)
    elif dest == 1:
        q = q + np.where(on & stopped, tq, 0.0)
        w[:, 2] = np.where(~on, 1.0, 0.0)
    else:
        q = q + np.where(on & stopped, 0.5 * tq, 0.0)
        w[:, 2] = np.where(on & stopped, 0.5 * tq, np.where(~on, 1.0, 0.0))
    w[:, 0] = q
    return w


def met(ts, opens, closes, w, slip=1.0):
    out = {}
    for lab, start in (("10y", START10), ("5y", START5)):
        r = bt.run(ts, opens, closes, w, start, band=0.02, slippage_bps=slip)
        s = bt.stats(r, BARS)
        out[lab] = (s["cagr"], s["max_drawdown"], s["sharpe"], s["fills"], s["turnover"])
    return out


def show(label, m):
    a, b = m["10y"], m["5y"]
    print(f"{label:<36} 10y {a[0]*100:6.2f}/{a[1]*100:5.2f} C{a[0]/a[1]:4.2f} "
          f"| 5y {b[0]*100:6.2f}/{b[1]*100:5.2f} C{b[0]/b[1]:4.2f} | fills {a[3]:4d}")


def main():
    ts, opens, closes = load()
    dates, first, last = bounds(ts)
    risk_on, armed, stopped, day_id, dcl = day_setup(ts, opens, closes, first, last)
    n, d = len(ts), len(first)
    rets = np.diff(dcl, axis=0) / dcl[:-1]
    vol20 = pd.DataFrame(rets).rolling(20).std().to_numpy() * np.sqrt(252)
    vol20 = np.vstack([np.full((1, 3), np.nan), vol20])
    dclose = dcl[:, 0]

    print("stop events (sessions)", int((np.diff(np.r_[0, stopped.astype(int)]) == 1).sum()))
    base1 = np.ones(d)
    for dest, nm in ((0, "BIL (winner)"), (1, "QQQ"), (2, "50/50 QQQ/BIL")):
        show(f"stop->{nm}", met(ts, opens, closes, build(risk_on, stopped, day_id, n, base1, dest)))

    print("\n=== vol brake on top of stop->QQQ, wT=min(1, tv/vol20T) ===")
    for tv in (0.9, 0.8, 0.7, 0.6):
        wt = np.clip(tv / vol20[:, 1], 0.0, 1.0)
        wt = np.nan_to_num(wt, nan=1.0)
        show(f"tv={tv:.2f} wT mean {wt.mean():.2f}", met(ts, opens, closes, build(risk_on, stopped, day_id, n, wt, 1)))

    print("\n=== vol brake, stop->BIL ===")
    for tv in (0.8, 0.7, 0.6):
        wt = np.clip(tv / vol20[:, 1], 0.0, 1.0)
        wt = np.nan_to_num(wt, nan=1.0)
        show(f"tv={tv:.2f} wT mean {wt.mean():.2f}", met(ts, opens, closes, build(risk_on, stopped, day_id, n, wt, 0)))

    print("\n=== QQQ drawdown throttle, stop->QQQ ===")
    qqq = dclose[:, 0]
    hi = pd.Series(qqq).rolling(252).max().to_numpy()
    dd = qqq / hi - 1
    for thr, wtc in ((0.05, 0.5), (0.08, 0.5), (0.10, 0.5), (0.08, 0.7), (0.12, 0.3)):
        wt = np.where(dd < -thr, wtc, 1.0)
        wt = np.nan_to_num(wt, nan=1.0)
        show(f"dd<{-thr:.0%} -> wT {wtc}", met(ts, opens, closes, build(risk_on, stopped, day_id, n, wt, 1)))


if __name__ == "__main__":
    main()
