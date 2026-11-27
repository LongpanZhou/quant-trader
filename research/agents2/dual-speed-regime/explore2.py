"""Exploration 2: slow 165-day gate + 60-minute QQQ EMA fast filter.

Variants
  C1  continuous 60m EMA filter (overnight included)
  C2  intraday-only 60m filter: exit on a 60m close below EMA, always
      re-enter at the next session open (keeps overnight drift)
  C3  armed early exit: on slow-gate days armed by MA20 (same arming as the
      winner's stop), exit when a 60m close is below EMA, re-enter when a
      60m close is back above EMA
  C4  C3 plus the winner's 4% stop
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402
from explore1 import (CACHE, START10, START5, BPY, load, day_index, daily_state,
                      weights_from_daily, apply_stop, metrics, show)  # noqa: E402


def sixty_min_bars(qqq_close, first, last, span):
    """Return per-bar state (close > EMA) and per-minute mapping."""
    alpha = 2.0 / (span + 1.0)
    ends_all, close_all, day_of_bar = [], [], []
    for k, (f, l) in enumerate(zip(first, last)):
        ends = [f + 59, f + 119, f + 179, f + 239, f + 299, f + 359, l]
        for e in ends:
            if e <= l:
                ends_all.append(e)
                close_all.append(qqq_close[e])
                day_of_bar.append(k)
    close_all = np.asarray(close_all)
    ends_all = np.asarray(ends_all)
    ema = np.empty(len(close_all))
    e = np.nan
    for j, c in enumerate(close_all):
        e = c if not np.isfinite(e) else alpha * c + (1.0 - alpha) * e
        ema[j] = e
    bar_up = close_all > ema
    # bars per day
    counts = np.bincount(day_of_bar, minlength=len(first))
    state60 = np.zeros(len(qqq_close), bool)
    prev = False
    j = 0
    for k, (f, l) in enumerate(zip(first, last)):
        nb = counts[k]
        state60[f:min(f + 60, l + 1)] = prev
        for m in range(min(6, nb - 1)):
            s = f + 60 * (m + 1)
            state60[s:min(s + 60, l + 1)] = bar_up[j + m]
        prev = bar_up[j + nb - 1] if nb else prev
        j += nb
    return state60, bar_up, ends_all, day_of_bar


def intraday_only_state(day_state, state60, first, last):
    """Exit intraday on first completed 60m bar below EMA; reset each session."""
    hold = np.zeros(len(state60), bool)
    for k, (f, l) in enumerate(zip(first, last)):
        if not day_state[k]:
            continue
        state = True
        hold[f:l + 1] = True
        # bar 0 completes at f+59 -> applies from f+60
        for m in range(6):
            s = f + 60 * (m + 1)
            if s > l:
                break
            state = state and state60[s]
            hold[s:min(s + 60, l + 1)] = state
    return hold


def armed_reclaim_state(ts, opens, closes, day_state, state60, first, last, ma20,
                        arm_buf=0.01, stop=None):
    """Armed 60m exit + 60m reclaim re-entry, optional 4% stop."""
    n = len(ts)
    hold = np.zeros(n, bool)
    qqq_c, tq_c = closes[:, 0], closes[:, 1]
    events = dict(early=0, reclaim=0, stops=0)
    for k, (f, l) in enumerate(zip(first, last)):
        if not day_state[k]:
            continue
        ref = ma20[k - 1] if k > 0 else np.nan
        armed = bool(np.isfinite(ref) and qqq_c[f] < ref * (1.0 + arm_buf))
        base = opens[f, 1]
        state = True
        stopped = False
        for i in range(f, l + 1):
            if state60[i] is not None and i > f:
                # state60 already reflects the last completed 60m bar
                pass
            if stop is not None and armed and state and tq_c[i] < base * (1.0 - stop):
                state = False
                stopped = True
                events["stops"] += 1
            elif armed and not stopped:
                # evaluate only at 60m boundaries (state60 changes at those bars)
                if state and i > f and not state60[i] and state60[i - 1]:
                    state = False
                    events["early"] += 1
                elif (not state) and i > f and state60[i] and not state60[i - 1]:
                    state = True
                    events["reclaim"] += 1
            hold[i] = state
    w = np.zeros((n, 3))
    w[:, 1] = hold.astype(float)
    w[:, 2] = 1.0 - hold
    return w, events


def main():
    ts, opens, closes = load()
    dates, first, last, day_id = day_index(ts)
    dc = closes[last, 0]
    ma20 = pd.Series(dc).rolling(20).mean().to_numpy()
    reg165 = daily_state(ts, dc, 165)
    w_base = weights_from_daily(reg165, day_id)
    w_stop, nstop = apply_stop(ts, opens, closes, w_base, reg165, day_id, first, last, ma20)
    show(f"WINNER 165+stop({nstop})", metrics(w_stop, ts, opens, closes))

    for span in (20, 50, 100):
        state60, bar_up, ends, day_of_bar = sixty_min_bars(closes[:, 0], first, last, span)
        # C1 continuous
        w = weights_from_daily(reg165, day_id)
        w[:, 1] = (w[:, 1] > 0) & state60
        w[:, 2] = 1.0 - w[:, 1]
        show(f"C1 165+60mEMA{span}", metrics(w, ts, opens, closes))

        # C2 intraday-only
        hold2 = intraday_only_state(reg165, state60, first, last)
        w2 = np.zeros_like(w)
        w2[:, 1] = hold2.astype(float)
        w2[:, 2] = 1.0 - w2[:, 1]
        show(f"C2 intraday 60mEMA{span}", metrics(w2, ts, opens, closes))

        # C3 armed early exit + reclaim
        w3, ev = armed_reclaim_state(ts, opens, closes, reg165, state60, first, last, ma20)
        m3 = metrics(w3, ts, opens, closes)
        show(f"C3 armed 60m{span} {ev['early']}/{ev['reclaim']}", m3)

        # C4 armed early exit + reclaim + 4% stop
        w4, ev4 = armed_reclaim_state(ts, opens, closes, reg165, state60, first, last, ma20,
                                      stop=0.04)
        m4 = metrics(w4, ts, opens, closes)
        show(f"C4 armed60m{span}+stop {ev4['stops']}", m4)


if __name__ == "__main__":
    main()
