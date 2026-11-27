"""Exploration 4a: fixed DD episodes + monthly 2018-19 path (no surface)."""
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
from explore2 import sixty_min_bars, armed_reclaim_state  # noqa: E402
from explore4 import all_episodes, monthly  # noqa: E402


def main():
    ts, opens, closes = load()
    dates, first, last, day_id = day_index(ts)
    dc = closes[last, 0]
    ma20 = pd.Series(dc).rolling(20).mean().to_numpy()
    reg165 = daily_state(ts, dc, 165)
    w_base = weights_from_daily(reg165, day_id)
    w_stop, _ = apply_stop(ts, opens, closes, w_base, reg165, day_id, first, last, ma20)
    i0 = bt.start_index(ts, START10)

    def report(name, w):
        r = bt.run(ts, opens, closes, w, START10, band=0.02, slippage_bps=1.0)
        s = bt.stats(r, BPY)
        eps = all_episodes(ts[i0:], r["equity"], 3)
        print(f"{name:12s} CAGR {s['cagr']*100:6.2f} DD {s['max_drawdown']*100:5.2f} "
              f"fl {s['fills']:5d} | " +
              " ; ".join(f"{e[0]*100:.1f}% {e[1][:10]}->{e[2][:10]}" for e in eps), flush=True)
        return r

    rw = report("WINNER", w_stop)
    print("  WINNER 2018-02..2019-07 " + monthly(rw["equity"], ts[i0:], "2018-02-01", "2019-07-31"),
          flush=True)
    print("  WINNER 2026-01..2026-10 " + monthly(rw["equity"], ts[i0:], "2026-01-01", "2026-10-31"),
          flush=True)

    for span in (20, 30, 40, 50):
        s60 = sixty_min_bars(closes[:, 0], first, last, span)[0]
        w3, ev3 = armed_reclaim_state(ts, opens, closes, reg165, s60, first, last, ma20)
        r3 = report(f"C3-{span}", w3)
        print(f"  C3-{span} 2018-02..2019-07 " + monthly(r3["equity"], ts[i0:], "2018-02-01", "2019-07-31"),
              flush=True)
        w4, ev4 = armed_reclaim_state(ts, opens, closes, reg165, s60, first, last, ma20, stop=0.04)
        r4 = report(f"C4-{span}", w4)
        print(f"  C4-{span} 2018-02..2019-07 " + monthly(r4["equity"], ts[i0:], "2018-02-01", "2019-07-31"),
              flush=True)
        print(f"  C4-{span} 2026-01..2026-10 " + monthly(r4["equity"], ts[i0:], "2026-01-01", "2026-10-31"),
              flush=True)


if __name__ == "__main__":
    main()
