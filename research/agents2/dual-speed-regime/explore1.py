"""Exploration 1: dual-speed daily regime (165-day slow gate + fast MA gate).

Uses the round-1 winner's cached 1-minute panel (read-only) for speed.
All signals use bars <= i; the harness fills at i+1's open.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

CACHE = ROOT / "research/agents/daily-regime-minute-entry/panel_cache.npz"
START10, START5, END = "2017-01-03", "2021-10-25", "2026-10-23"
BPY = 252 * 390


def load():
    z = np.load(CACHE)
    ts = pd.DatetimeIndex(
        pd.to_datetime(z["ts"], unit="ns", utc=True).tz_convert("America/New_York")
    )
    return ts, z["opens"], z["closes"]


def day_index(ts):
    dates = np.array([t.date() for t in ts])
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(dates) - 1]
    day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, len(dates)]))
    return dates, first, last, day_id


def daily_state(ts, qqq_daily, n_slow=165, n_fast=None, buf_exit=0.0, buf_entry=0.0):
    """Per-session hold-TQQQ state from prior daily closes (state machine)."""
    sma = pd.Series(qqq_daily).rolling(n_slow).mean().to_numpy()
    if n_fast:
        fast = pd.Series(qqq_daily).rolling(n_fast).mean().to_numpy()
    else:
        fast = np.full(len(qqq_daily), np.nan)
    n = len(qqq_daily)
    state = np.zeros(n, bool)
    on = False
    for k in range(1, n):
        c, s, f = qqq_daily[k - 1], sma[k - 1], fast[k - 1]
        if not np.isfinite(s):
            continue
        if on:
            if c < s * (1.0 - buf_exit) or (np.isfinite(f) and c < f * (1.0 - buf_exit)):
                on = False
        else:
            if c > s * (1.0 + buf_entry) and (
                not np.isfinite(f) or c > f * (1.0 + buf_entry)
            ):
                on = True
        state[k] = on
    return state


def weights_from_daily(state_day, day_id):
    hold = state_day[day_id]
    w = np.zeros((len(day_id), 3))
    w[:, 1] = hold.astype(float)
    w[:, 2] = 1.0 - w[:, 1]
    return w


def apply_stop(ts, opens, closes, w, state_day, day_id, first, last, ma20, n_slow=165,
               stop=0.04, arm_buf=0.01):
    """Winner-style 4% stop from session open, armed by prior-close MA20."""
    dates = np.array([t.date() for t in ts])
    qqq_c = closes[:, 0]
    tq_c = closes[:, 1]
    hold = w[:, 1].astype(bool)
    stops = 0
    for k, (f, l) in enumerate(zip(first, last)):
        if not state_day[k]:
            continue
        # ma20 argument is per-day rolling mean incl. day k; use prior day
        ref = ma20[k - 1] if k > 0 else np.nan
        armed = bool(np.isfinite(ref) and qqq_c[f] < ref * (1.0 + arm_buf))
        base = opens[f, 1]
        state = True
        for i in range(f, l + 1):
            if armed and state and tq_c[i] < base * (1.0 - stop):
                state = False
                stops += 1
            hold[i] = state and state_day[k]
    w2 = np.zeros_like(w)
    w2[:, 1] = hold.astype(float)
    w2[:, 2] = 1.0 - w2[:, 1]
    return w2, stops


def metrics(w, ts, opens, closes, slip=1.0):
    out = {}
    for label, start in (("10y", START10), ("5y", START5)):
        r = bt.run(ts, opens, closes, w, start, band=0.02, slippage_bps=slip)
        s = bt.stats(r, BPY)
        i = bt.start_index(ts, start)
        b = bt.benchmark(closes[i:, 1], ts[i:], BPY)
        out[label] = dict(cagr=s["cagr"], dd=s["max_drawdown"], sharpe=s["sharpe"],
                          fills=s["fills"], turn=s["turnover"], exp=s["exposure"],
                          bcagr=b["cagr"], bdd=b["max_drawdown"])
    return out


def show(name, m, slip=1.0):
    a, b = m["10y"], m["5y"]
    print(f"{name:26s} {slip:4.0f}bp  10y {a['cagr']*100:6.2f}/{a['dd']*100:5.2f} "
          f"sh {a['sharpe']:4.2f} fl {a['fills']:5d} | 5y {b['cagr']*100:6.2f}/{b['dd']*100:5.2f} "
          f"sh {b['sharpe']:4.2f} fl {b['fills']:5d}")


def main():
    ts, opens, closes = load()
    dates, first, last, day_id = day_index(ts)
    qqq_c = closes[:, 0]
    dc = qqq_c[last]
    ma20 = pd.Series(dc).rolling(20).mean().to_numpy()
    print(f"bars {len(ts):,}  days {len(first)}  {ts[0]} .. {ts[-1]}")

    reg165 = daily_state(ts, dc, 165)
    w_base = weights_from_daily(reg165, day_id)
    m = metrics(w_base, ts, opens, closes)
    show("baseline 165", m)

    w_stop, nstop = apply_stop(ts, opens, closes, w_base, reg165, day_id, first, last, ma20)
    m = metrics(w_stop, ts, opens, closes)
    show(f"WINNER 165+stop({nstop})", m)

    for nf in (20, 50, 100):
        st = daily_state(ts, dc, 165, nf)
        w = weights_from_daily(st, day_id)
        m = metrics(w, ts, opens, closes)
        show(f"165+MA{nf}", m)
        ws, ns = apply_stop(ts, opens, closes, w, st, day_id, first, last, ma20)
        m = metrics(ws, ts, opens, closes)
        show(f"165+MA{nf}+stop({ns})", m)

    for nf, be in ((20, 0.01), (50, 0.01), (50, 0.02)):
        st = daily_state(ts, dc, 165, nf, buf_entry=be)
        w = weights_from_daily(st, day_id)
        m = metrics(w, ts, opens, closes)
        show(f"165+MA{nf}+entry{be:.0%}", m)


if __name__ == "__main__":
    main()
