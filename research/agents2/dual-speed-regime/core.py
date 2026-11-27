"""Core helpers for the dual-speed regime research (round 2, agent 13).

Conventions
-----------
* `weights[i]` is the target set from the close of bar i and fills at bar i+1's
  open (the bt.py simulator contract).
* Daily signals use the prior session's close only.
* 60-minute bars are aligned to the 09:30 session open: 09:30-10:29, ...,
  14:30-15:29, 15:30-15:59 (last bar 30 minutes). A bar's close is known at its
  last minute; the position may change at that bar (fill next minute).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))

START10, START5, END = "2017-01-03", "2021-10-25", "2026-10-23"
BPY = 252 * 390
CACHE = ROOT / "research/agents/daily-regime-minute-entry/panel_cache.npz"


def load_cached():
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


def daily_gate(qqq_daily, n_slow=165, n_fast=None, buf_entry=0.0):
    """Per-session TQQQ state from prior daily closes (state machine)."""
    sma = pd.Series(qqq_daily).rolling(n_slow).mean().to_numpy()
    fast = (pd.Series(qqq_daily).rolling(n_fast).mean().to_numpy()
            if n_fast else np.full(len(qqq_daily), np.nan))
    n = len(qqq_daily)
    state = np.zeros(n, bool)
    on = False
    for k in range(1, n):
        c, s, f = qqq_daily[k - 1], sma[k - 1], fast[k - 1]
        if not np.isfinite(s):
            continue
        if on:
            if c < s or (np.isfinite(f) and c < f):
                on = False
        else:
            if c > s * (1.0 + buf_entry) and (
                not np.isfinite(f) or c > f * (1.0 + buf_entry)
            ):
                on = True
        state[k] = on
    return state


def sixty_min_bars(price, first, last, span):
    """EMA over session-aligned 60-minute bars.

    Returns (bar_up, ends, day_of_bar). bar_up[j] = bar close > EMA(span).
    """
    alpha = 2.0 / (span + 1.0)
    ends, closes, day_of = [], [], []
    for k, (f, l) in enumerate(zip(first, last)):
        for e in (f + 59, f + 119, f + 179, f + 239, f + 299, f + 359, l):
            if e <= l:
                ends.append(e)
                closes.append(price[e])
                day_of.append(k)
    ends = np.asarray(ends)
    closes = np.asarray(closes)
    day_of = np.asarray(day_of)
    ema = np.empty(len(closes))
    e = np.nan
    for j, c in enumerate(closes):
        e = c if not np.isfinite(e) else alpha * c + (1.0 - alpha) * e
        ema[j] = e
    bar_up = closes > ema
    return bar_up, ends, day_of


def map_bar_state(n, first, last, bar_up, ends, day_of, at_close=True, last_bar_overnight=True):
    """Per-minute fast-filter state.

    at_close=True applies a bar's state at the bar's last minute, so the
    harness fills it at the next minute's open (correct timing). False delays
    it by one minute (the exploration default).
    """
    state = np.ones(n, bool)
    counts = np.bincount(day_of, minlength=len(first))
    j = 0
    prev = False
    for k, (f, l) in enumerate(zip(first, last)):
        nb = counts[k]
        ends_k = ends[j:j + nb]
        ups = bar_up[j:j + nb]
        state[f:ends_k[0]] = prev
        shift = 0 if at_close else 1
        for m in range(nb - 1):
            s = ends_k[m] + shift
            state[s:ends_k[m + 1]] = ups[m]
        if last_bar_overnight:
            state[ends_k[-1]:l + 1] = ups[-1]
        else:
            state[ends_k[-2] + shift:l + 1] = ups[-2]
        prev = ups[-1]
        j += nb
    return state


def bar_end_flags(n, ends):
    flag = np.zeros(n, bool)
    flag[np.asarray(ends, dtype=int)] = True
    return flag


def armed_overlay(ts, opens, closes, day_state, fast_state, first, last, ma_ref,
                  arm_buf=0.01, stop=None, force_close=False,
                  arm_always=False, stop_only=False, bar_end=None, mode="cross"):
    """Armed fast-filter exit + reclaim re-entry + optional stop.

    day_state : per-session slow-gate bool
    fast_state: per-minute bool (True = fast trend up)
    ma_ref    : per-session MA of QQQ closes *including* that day; the arm test
                uses the prior day's value.
    mode      : 'cross' toggles only when the fast state flips; 'level' sets the
                state to the fast state at every 60m bar close.
    """
    n = len(ts)
    hold = np.zeros(n, bool)
    qqq_c, tq_c = closes[:, 0], closes[:, 1]
    ev = dict(early=0, reclaim=0, stops=0, days_armed=0, days_exited=0)
    for k, (f, l) in enumerate(zip(first, last)):
        if not day_state[k]:
            continue
        ref = ma_ref[k - 1] if k > 0 else np.nan
        armed = arm_always or bool(np.isfinite(ref) and qqq_c[f] < ref * (1.0 + arm_buf))
        if armed:
            ev["days_armed"] += 1
        base = opens[f, 1]
        state = True
        exited = False
        stopped = False
        for i in range(f, l + 1):
            if armed and not stop_only and i > f:
                if mode == "level" and bar_end is not None and bar_end[i]:
                    if state and not fast_state[i]:
                        state = False
                        ev["early"] += 1
                        exited = True
                    elif (not state) and fast_state[i]:
                        state = True
                        stopped = False
                        ev["reclaim"] += 1
                elif mode == "cross":
                    prev_up, cur_up = fast_state[i - 1], fast_state[i]
                    if cur_up != prev_up:
                        if state and not cur_up:
                            state = False
                            ev["early"] += 1
                            exited = True
                        elif (not state) and cur_up:
                            state = True
                            stopped = False
                            ev["reclaim"] += 1
            if stop is not None and armed and state and tq_c[i] < base * (1.0 - stop):
                state = False
                stopped = True
                ev["stops"] += 1
                exited = True
            hold[i] = state
        if force_close:
            hold[l] = True
        if exited:
            ev["days_exited"] += 1
    w = np.zeros((n, 3))
    w[:, 1] = hold.astype(float)
    w[:, 2] = 1.0 - hold
    return w, ev


def weights_daily(state_day, day_id):
    hold = state_day[day_id]
    w = np.zeros((len(day_id), 3))
    w[:, 1] = hold.astype(float)
    w[:, 2] = 1.0 - w[:, 1]
    return w


def winner_weights(ts, opens, closes, first, last, day_id, ma20):
    """Round-1 winner: 165 gate + 4% stop armed by prior MA20*1.01."""
    dc = closes[last, 0]
    reg = daily_gate(dc, 165)
    w, _ = armed_overlay(ts, opens, closes, reg, np.ones(len(ts), bool), first, last,
                         ma20, arm_buf=0.01, stop=0.04, stop_only=True)
    return w, reg
