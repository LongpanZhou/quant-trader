"""Exploration: QQQ drawdown-from-52w-high episodes vs the 165-day SMA regime.

Reads the cached 1m panel produced by the round-1 winner agent (read-only) and
prints the drawdown state per session plus episode tables. No look-ahead:
the drawdown at session k uses QQQ closes through session k-1 only.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

CACHE = ROOT / "research" / "agents" / "daily-regime-minute-entry" / "panel_cache.npz"
START10, START5, END = "2017-01-03", "2021-10-25", "2026-10-23"


def load_panel():
    z = np.load(CACHE)
    ts = pd.DatetimeIndex(
        pd.to_datetime(z["ts"], unit="ns", utc=True).tz_convert("America/New_York")
    )
    return ts, z["opens"], z["highs"], z["lows"], z["closes"], z["vols"]


def day_bounds(dates):
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(dates) - 1]
    return first, last


def main():
    ts, opens, highs, lows, closes, vols = load_panel()
    dates = np.array([d for d in ts.date])
    first, last = day_bounds(dates)
    dates = dates[last]
    dc = closes[last, 0]
    n = len(dc)
    print(f"bars {len(ts):,}  sessions {n}  {dates[0]} -> {dates[-1]}")

    sma = pd.Series(dc).rolling(165).mean().to_numpy()
    high252 = pd.Series(dc).rolling(252).max().to_numpy()

    # state at session k uses closes through k-1
    reg = np.zeros(n, bool)
    reg[1:] = dc[:-1] > sma[:-1]
    hi_prev = np.r_[np.nan, high252[:-1]]
    dd = dc / hi_prev - 1.0  # this session's close vs prior trailing high (desc)
    dd_lag = np.r_[np.nan, dd[:-1]]  # decision-time drawdown (through k-1)

    ok = np.isfinite(dd_lag)
    print(f"\nregime on {reg[ok].mean()*100:.1f}% of sessions")
    print(f"drawdown quantiles (decision time): "
          f"{np.nanpercentile(dd_lag[ok], [1,5,10,25,50,75,90,99]).round(4)}")

    for thr in (0.05, 0.10, 0.15, 0.20):
        below = ok & (dd_lag <= -thr)
        print(f"dd <= -{thr:.0%}: {below.sum():4d} sessions ({below.mean()*100:4.1f}%), "
              f"of which regime ON {int((below & reg).sum()):4d} "
              f"({(below & reg).sum()/max(reg.sum(),1)*100:.1f}% of ON days)")

    # Episode table: runs where dd_lag <= -10%, with regime state
    print("\nEpisodes with drawdown <= -10% (decision time):")
    state = ok & (dd_lag <= -0.10)
    edges = np.flatnonzero(np.diff(np.r_[0, state.astype(int), 0]))
    rows = []
    for a, b in zip(edges[::2], edges[1::2]):
        # a..b-1 sessions in drawdown <= -10%
        k0, k1 = a, b - 1
        trough_i = int(np.argmin(dd[a:b]))
        rows.append(dict(
            start=str(dates[k0]), end=str(dates[k1]), days=int(b - a),
            dd_start=float(dd_lag[k0]), dd_min=float(np.nanmin(dd[a:b])),
            trough=str(dates[a + trough_i]),
            reg_on_pct=float(reg[a:b].mean() * 100),
            qqq_ret=float(dc[min(k1 + 1, n - 1)] / dc[k0 - 1] - 1) if k0 > 0 else np.nan,
        ))
    for r in rows:
        print(f"  {r['start']} -> {r['end']}  {r['days']:3d}d  "
              f"dd@{r['start'][:10]} {r['dd_start']*100:6.1f}%  min {r['dd_min']*100:6.1f}% "
              f"({r['trough']})  regime_on {r['reg_on_pct']:5.1f}%  QQQ fwd {r['qqq_ret']*100:6.1f}%")

    # Drawdown at the winner's max-DD windows
    for label, start, end in (("10y DD", "2018-03-13", "2019-06-05"),
                              ("5y DD", "2026-06-22", "2026-07-30")):
        i0 = int(np.searchsorted(dates, pd.Timestamp(start).date()))
        i1 = int(np.searchsorted(dates, pd.Timestamp(end).date()))
        print(f"\n{label} {start}..{end}: dd_lag from "
              f"{dd_lag[i0]*100:.1f}% to {dd_lag[i1]*100:.1f}%, "
              f"regime_on {reg[i0:i1+1].mean()*100:.0f}%")
        for k in range(i0, min(i1 + 1, i0 + 12)):
            print(f"   {dates[k]}  QQQ {dc[k]:8.2f}  dd {dd_lag[k]*100:7.2f}%  reg {int(reg[k])}")

    # how often is QQQ within 2%/3%/5% of high while regime ON
    for rec in (0.01, 0.02, 0.03, 0.05):
        m = ok & (dd_lag >= -rec)
        print(f"dd >= -{rec:.0%}: {m.sum():4d} sessions, regime ON {int((m & reg).sum())}")


if __name__ == "__main__":
    main()
