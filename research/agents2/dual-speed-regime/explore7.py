"""Exploration 7: bar-close timing / last-bar conventions, finalist anatomy."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402
import core as C  # noqa: E402
from explore4 import all_episodes, monthly  # noqa: E402


def run(w, ts, opens, closes, start, slip=1.0):
    r = bt.run(ts, opens, closes, w, start, band=0.02, slippage_bps=slip)
    return r, bt.stats(r, C.BPY)


def show(name, w, ts, opens, closes, slip=1.0):
    out = {}
    for label, start in (("10y", C.START10), ("5y", C.START5)):
        r, s = run(w, ts, opens, closes, start, slip)
        out[label] = (s["cagr"], s["max_drawdown"], s["sharpe"], s["fills"], r)
    print(f"{name:34s} {slip:4.0f}bp  10y {out['10y'][0]*100:6.2f}/{out['10y'][1]*100:5.2f} "
          f"sh{out['10y'][2]:4.2f} fl{out['10y'][3]:5d} | 5y {out['5y'][0]*100:6.2f}/"
          f"{out['5y'][1]*100:5.2f} sh{out['5y'][2]:4.2f} fl{out['5y'][3]:5d}", flush=True)
    return out


def main():
    ts, opens, closes = C.load_cached()
    dates, first, last, day_id = C.day_index(ts)
    dc = closes[last, 0]
    ma20 = pd.Series(dc).rolling(20).mean().to_numpy()
    reg = C.daily_gate(dc, 165)
    w_win, _ = C.winner_weights(ts, opens, closes, first, last, day_id, ma20)
    show("WINNER", w_win, ts, opens, closes)

    bar_up, ends, day_of = C.sixty_min_bars(closes[:, 0], first, last, 40)
    print("\n-- timing conventions (span 40, stop 4%, arm 1%) --")
    combos = {}
    for at_close in (True, False):
        for lastbar in (True, False):
            fs = C.map_bar_state(len(ts), first, last, bar_up, ends, day_of,
                                 at_close=at_close, last_bar_overnight=lastbar)
            w, ev = C.armed_overlay(ts, opens, closes, reg, fs, first, last, ma20,
                                    arm_buf=0.01, stop=0.04)
            key = f"close{int(at_close)}_last{int(lastbar)}"
            combos[key] = w
            show(key, w, ts, opens, closes)
    # forced close variant on the correct-timing mapping
    fs = C.map_bar_state(len(ts), first, last, bar_up, ends, day_of, at_close=True,
                         last_bar_overnight=False)
    wfc, ev = C.armed_overlay(ts, opens, closes, reg, fs, first, last, ma20,
                              arm_buf=0.01, stop=0.04, force_close=True)
    show("close1_last0_force", wfc, ts, opens, closes)

    print("\n-- anatomy of close1_last0 --")
    w = combos["close1_last0"]
    for label, start in (("10y", C.START10), ("5y", C.START5)):
        r, s = run(w, ts, opens, closes, start)
        i = bt.start_index(ts, start)
        print(f" {label} CAGR {s['cagr']*100:.2f} DD {s['max_drawdown']*100:.2f} fills {s['fills']}")
        for e in all_episodes(ts[i:], r["equity"], 4):
            print(f"   DD {e[0]*100:5.2f}%  {e[1]} -> {e[2]}  rec {e[3]}")
    r, s = run(w, ts, opens, closes, C.START10)
    i0 = bt.start_index(ts, C.START10)
    print(" yearly " + "  ".join(
        f"{y}:{r['equity'][np.array([t.year==y for t in ts[i0:]])][-1]/r['equity'][np.array([t.year==y for t in ts[i0:]])][0]-1:.3f}"
        for y in range(2017, 2027)))
    print(" 2026 " + monthly(r["equity"], r["ts"], "2026-01-01", "2026-10-31"))
    print(" 2021 " + monthly(r["equity"], r["ts"], "2021-01-01", "2021-06-30"))


if __name__ == "__main__":
    main()
