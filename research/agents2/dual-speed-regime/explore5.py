"""Exploration 5: clean armed 60m filter, surface, costs, forced-close re-entry."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402
from explore1 import (START10, START5, BPY, load, day_index, daily_state,
                      weights_from_daily, apply_stop)  # noqa: E402
from explore2 import sixty_min_bars  # noqa: E402


def build_armed(ts, opens, closes, day_state, state60, first, last, ma20,
                arm_buf=0.01, stop=None, force_close=False, arm_kind="ma20"):
    """Armed 60m exit / reclaim re-entry, optional stop, optional close re-entry."""
    n = len(ts)
    hold = np.zeros(n, bool)
    qqq_c, tq_c = closes[:, 0], closes[:, 1]
    ev = dict(early=0, reclaim=0, stops=0, days_armed=0, days_exited=0)
    for k, (f, l) in enumerate(zip(first, last)):
        if not day_state[k]:
            continue
        if arm_kind == "ma20":
            ref = ma20[k - 1] if k > 0 else np.nan
            armed = bool(np.isfinite(ref) and qqq_c[f] < ref * (1.0 + arm_buf))
        elif arm_kind == "ma50":
            ref = ma20[k - 1] if k > 0 else np.nan  # caller passes ma50 here
            armed = bool(np.isfinite(ref) and qqq_c[f] < ref)
        else:
            armed = True
        if armed:
            ev["days_armed"] += 1
        base = opens[f, 1]
        state = True
        exited_today = False
        for i in range(f, l + 1):
            if i > f:
                prev_up = state60[i - 1]
                cur_up = state60[i]
                if cur_up != prev_up:
                    if armed and state and not cur_up:
                        state = False
                        ev["early"] += 1
                        exited_today = True
                    elif armed and (not state) and cur_up:
                        state = True
                        ev["reclaim"] += 1
            if stop is not None and armed and state and tq_c[i] < base * (1.0 - stop):
                state = False
                ev["stops"] += 1
                exited_today = True
            hold[i] = state
        if force_close:
            hold[l] = True  # weight at last bar -> filled at next session open
        if exited_today:
            ev["days_exited"] += 1
    w = np.zeros((n, 3))
    w[:, 1] = hold.astype(float)
    w[:, 2] = 1.0 - hold
    return w, ev


def met(w, ts, opens, closes, slip=1.0, both=True):
    out = {}
    wins = (("10y", START10), ("5y", START5)) if both else (("10y", START10),)
    for label, start in wins:
        r = bt.run(ts, opens, closes, w, start, band=0.02, slippage_bps=slip)
        s = bt.stats(r, BPY)
        out[label] = (s["cagr"], s["max_drawdown"], s["sharpe"], s["fills"], s["turnover"],
                      r["equity"], r["ts"])
    return out


def line(name, m, slip=1.0):
    parts = []
    for k in ("10y", "5y"):
        if k in m:
            c, d, s, f, t, _, _ = m[k]
            parts.append(f"{k} {c*100:6.2f}/{d*100:5.2f} sh{s:4.2f} fl{f:5d}")
    print(f"{name:30s} {slip:4.0f}bp  " + " | ".join(parts), flush=True)


def main():
    ts, opens, closes = load()
    dates, first, last, day_id = day_index(ts)
    dc = closes[last, 0]
    ma20 = pd.Series(dc).rolling(20).mean().to_numpy()
    ma50 = pd.Series(dc).rolling(50).mean().to_numpy()
    reg165 = daily_state(ts, dc, 165)
    w_base = weights_from_daily(reg165, day_id)
    w_stop, _ = apply_stop(ts, opens, closes, w_base, reg165, day_id, first, last, ma20)
    line("WINNER", met(w_stop, ts, opens, closes))

    cache = {sp: sixty_min_bars(closes[:, 0], first, last, sp)[0] for sp in (25, 30, 35, 40, 45, 50)}

    print("\n-- span surface, stop 4%, arm MA20*1.01 --")
    for sp in (25, 30, 35, 40, 45, 50):
        w, ev = build_armed(ts, opens, closes, reg165, cache[sp], first, last, ma20, stop=0.04)
        line(f"C4 span{sp}", met(w, ts, opens, closes))

    print("\n-- stop surface, span 35/40 --")
    for sp in (35, 40):
        for stop in (0.030, 0.035, 0.040, 0.045, 0.050):
            w, ev = build_armed(ts, opens, closes, reg165, cache[sp], first, last, ma20, stop=stop)
            line(f"span{sp} stop{stop*100:.1f}", met(w, ts, opens, closes))

    print("\n-- arm buffer, span 40, stop 4% --")
    for buf in (0.000, 0.005, 0.010, 0.020, 0.030):
        w, ev = build_armed(ts, opens, closes, reg165, cache[40], first, last, ma20,
                            arm_buf=buf, stop=0.04)
        line(f"span40 arm+{buf*100:.1f}%", met(w, ts, opens, closes))

    w, ev = build_armed(ts, opens, closes, reg165, cache[40], first, last, ma50,
                        stop=0.04, arm_kind="ma50")
    line("span40 arm MA50", met(w, ts, opens, closes))

    print("\n-- forced close re-entry, span 40 --")
    for stop in (None, 0.04):
        w, ev = build_armed(ts, opens, closes, reg165, cache[40], first, last, ma20,
                            stop=stop, force_close=True)
        line(f"forceclose stop{stop}", met(w, ts, opens, closes))

    print("\n-- costs for C4 span 40 stop 4% --")
    w, ev = build_armed(ts, opens, closes, reg165, cache[40], first, last, ma20, stop=0.04)
    print("events", ev, flush=True)
    for slip in (1.0, 5.0, 10.0):
        line("C4-40", met(w, ts, opens, closes, slip=slip), slip)


if __name__ == "__main__":
    main()
