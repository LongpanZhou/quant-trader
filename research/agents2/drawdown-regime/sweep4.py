"""Sweep 4: controls for the conditional-stop result.

1. Always-tight stop (no drawdown condition) -- is the DD state doing work?
2. Placebo bands: tight stop in a *different* drawdown range, same frequency.
3. Event study: marginal stops (fired at 2% but not 4%) and their P&L.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ddlib as L


def stop_with_condition(ts, opens, closes, dctx, cond, stop2, base_stop=0.04):
    """cond: bool array per session -> use stop2 that session."""
    first, last = dctx["first"], dctx["last"]
    n = len(ts)
    qqq_close, tqqq_close = closes[:, 0], closes[:, 1]
    hold = np.zeros(n)
    events = []
    for k, (f, l) in enumerate(zip(first, last)):
        if not dctx["reg"][k]:
            continue
        stop = stop2 if cond[k] else base_stop
        armed = bool(np.isfinite(dctx["arm_ma20"][k])
                     and qqq_close[f] < dctx["arm_ma20"][k] * 1.01)
        base = opens[f, 1]
        on = True
        for i in range(f, l + 1):
            if on and armed and tqqq_close[i] < base * (1 - stop):
                on = False
                events.append((k, i, stop, base))
            hold[i] = 1.0 if on else 0.0
    w = np.zeros((n, 3))
    w[:, 1] = hold
    w[:, 2] = 1 - hold
    return w, events


def main():
    ts, opens, closes = L.load_panel()
    dctx = L.daily_context(ts, closes)
    dd = dctx["dd_prev"]
    reg = dctx["reg"]
    first, last = dctx["first"], dctx["last"]

    print("== always-tight stop (no DD condition) ==")
    for s in (0.02, 0.025, 0.03):
        cond = np.ones(dctx["n"], bool)
        w, ev = stop_with_condition(ts, opens, closes, dctx, cond, s)
        L.fmt(f"always {s:.1%} n{len(ev):4d}", L.summary(ts, opens, closes, w))

    print("\n== placebo bands (tight 2% in a different DD range) ==")
    conditions = {
        "dd -0..-5%": (dd < 0) & (dd > -0.05),
        "dd -3..-8%": (dd <= -0.03) & (dd > -0.08),
        "dd -5..-8%": (dd <= -0.05) & (dd > -0.08),
        "dd -8..-20%": (dd <= -0.08) & (dd > -0.20),
        "dd <= -8%": dd <= -0.08,
        "dd <= -6%": dd <= -0.06,
        "uw >= 30": dctx["uw"] >= 30,
        "uw >= 60": dctx["uw"] >= 60,
        "reg on only": reg,
    }
    for name, cond in conditions.items():
        w, ev = stop_with_condition(ts, opens, closes, dctx, cond & reg, 0.02)
        o = L.fmt(f"{name:14s} n{len(ev):4d}", L.summary(ts, opens, closes, w))

    print("\n== event study: marginal stops (2% fires, 4% would not) ==")
    w4, ev4 = stop_with_condition(ts, opens, closes, dctx, np.zeros(dctx["n"], bool), 0.04)
    w2, ev2 = stop_with_condition(ts, opens, closes, dctx, dd <= -0.08, 0.02)
    set4 = {(k, i) for k, i, _, _ in ev4}
    marginal = [(k, i, s, b) for k, i, s, b in ev2 if (k, i) not in set4]
    print(f"base 4% events {len(ev4)}, conditional events {len(ev2)}, marginal {len(marginal)}")
    print("  date        time   TQQQ_stop  next_open  saving_to_next_open  day_close_move")
    savings = []
    for k, i, s, b in marginal:
        f, l = first[k], last[k]
        if i + 1 >= len(closes):
            continue
        nxt = opens[i + 1, 1] if i + 1 <= l else opens[l + 1, 1] if l + 1 < len(opens) else np.nan
        px = closes[i, 1]
        if not np.isfinite(nxt):
            continue
        # what the position would have earned from px to next open (negative = avoided loss)
        save = nxt / px - 1
        savings.append(save)
        daymove = closes[l, 1] / opens[f, 1] - 1
        print(f"  {dctx['dates'][k]}  {ts[i].time()}  {px:8.3f}  {nxt:8.3f}  "
              f"{save*100:8.2f}%  {daymove*100:6.2f}")
    sv = np.array(savings)
    print(f"  n={len(sv)}  mean {sv.mean()*100:6.2f}%  median {np.median(sv)*100:6.2f}%  "
          f"min {sv.min()*100:6.2f}%  max {sv.max()*100:6.2f}%  "
          f"pct<0 {np.mean(sv<0)*100:.0f}%")

    # aggregate: sum of log-savings vs number of events
    print(f"  sum of savings {sv.sum()*100:7.1f} pp over {len(sv)} events")


if __name__ == "__main__":
    main()
