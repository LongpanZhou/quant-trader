"""Exploration 8: cross vs level fast-filter state, finalist selection."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402
import core as C  # noqa: E402
from explore4 import all_episodes  # noqa: E402


def show(name, w, ts, opens, closes, slip=1.0, both=True):
    out = {}
    wins = (("10y", C.START10), ("5y", C.START5)) if both else (("10y", C.START10),)
    for label, start in wins:
        r = bt.run(ts, opens, closes, w, start, band=0.02, slippage_bps=slip)
        s = bt.stats(r, C.BPY)
        out[label] = (s["cagr"], s["max_drawdown"], s["sharpe"], s["fills"], r)
    txt = " | ".join(f"{k} {v[0]*100:6.2f}/{v[1]*100:5.2f} sh{v[2]:4.2f} fl{v[3]:5d}"
                     for k, v in out.items())
    print(f"{name:30s} {slip:4.0f}bp  {txt}", flush=True)
    return out


def main():
    ts, opens, closes = C.load_cached()
    dates, first, last, day_id = C.day_index(ts)
    dc = closes[last, 0]
    ma20 = pd.Series(dc).rolling(20).mean().to_numpy()
    reg = C.daily_gate(dc, 165)
    w_win, _ = C.winner_weights(ts, opens, closes, first, last, day_id, ma20)
    show("WINNER", w_win, ts, opens, closes)

    for span in (35, 40, 45):
        bar_up, ends, day_of = C.sixty_min_bars(closes[:, 0], first, last, span)
        flags = C.bar_end_flags(len(ts), ends)
        for lastbar in (False, True):
            fs = C.map_bar_state(len(ts), first, last, bar_up, ends, day_of,
                                 at_close=True, last_bar_overnight=lastbar)
            for mode in ("cross", "level"):
                w, ev = C.armed_overlay(ts, opens, closes, reg, fs, first, last, ma20,
                                        stop=0.04, bar_end=flags, mode=mode)
                show(f"s{span} {mode} last{int(lastbar)} e{ev['early']}/r{ev['reclaim']}/st{ev['stops']}",
                     w, ts, opens, closes)


if __name__ == "__main__":
    main()
