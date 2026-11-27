"""Exploration 4: fixed DD episodes + monthly path + parameter surface for C4."""
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


def all_episodes(ts, eq, top=4):
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    out = []
    i = 0
    n = len(eq)
    while i < n:
        if dd[i] >= -1e-9:
            i += 1
            continue
        j = i
        while j < n and dd[j] < -1e-9:
            j += 1
        p = int(np.argmax(eq[: i + 1]))
        seg = dd[p:j]
        t = p + int(np.argmin(seg))
        out.append((float(-seg.min()), str(ts[p])[:16], str(ts[t])[:16],
                    str(ts[min(j, n - 1)])[:16]))
        i = j + 1
    out.sort(reverse=True)
    return out[:top]


def monthly(eq, ts, start, end):
    s = pd.Series(eq, index=ts).loc[start:end].resample("ME").last().pct_change().dropna()
    return " ".join(f"{k.strftime('%y-%m')}:{v*100:5.1f}" for k, v in s.items())


def main():
    ts, opens, closes = load()
    dates, first, last, day_id = day_index(ts)
    dc = closes[last, 0]
    ma20 = pd.Series(dc).rolling(20).mean().to_numpy()
    reg165 = daily_state(ts, dc, 165)
    w_base = weights_from_daily(reg165, day_id)
    w_stop, _ = apply_stop(ts, opens, closes, w_base, reg165, day_id, first, last, ma20)
    i0 = bt.start_index(ts, START10)

    def report(name, w, slip=1.0):
        r = bt.run(ts, opens, closes, w, START10, band=0.02, slippage_bps=slip)
        s = bt.stats(r, BPY)
        eps = all_episodes(ts[i0:], r["equity"], 3)
        print(f"{name:28s} CAGR {s['cagr']*100:6.2f} DD {s['max_drawdown']*100:5.2f} "
              f"fl {s['fills']:5d} | worst: " +
              " ; ".join(f"{e[0]*100:.1f}% {e[1][:10]}->{e[2][:10]}" for e in eps))
        return r

    report("WINNER", w_stop)
    state_cache = {}
    for span in (20, 30, 40, 50):
        state_cache[span] = sixty_min_bars(closes[:, 0], first, last, span)[0]

    for span in (20, 30, 40, 50):
        w, _ = armed_reclaim_state(ts, opens, closes, reg165, state_cache[span], first, last, ma20)
        report(f"C3-{span}", w)

    print("\n-- monthly 2018-02..2019-07 (winner then variants) --")
    r = report("WINNER", w_stop)
    print("  WINNER " + monthly(r["equity"], ts[i0:], "2018-02-01", "2019-07-31"))
    for span in (20, 30, 40):
        w, _ = armed_reclaim_state(ts, opens, closes, reg165, state_cache[span], first, last, ma20, stop=0.04)
        r = report(f"C4-{span}", w)
        print(f"  C4-{span} " + monthly(r["equity"], ts[i0:], "2018-02-01", "2019-07-31"))

    print("\n-- surface: C4 stop x span (10y CAGR/DD) --")
    for span in (20, 30, 40, 50):
        row = []
        for stop in (0.030, 0.035, 0.040, 0.045, 0.050):
            w, ev = armed_reclaim_state(ts, opens, closes, reg165, state_cache[span], first, last,
                                        ma20, stop=stop)
            r = bt.run(ts, opens, closes, w, START10, band=0.02, slippage_bps=1.0)
            s = bt.stats(r, BPY)
            r5 = bt.run(ts, opens, closes, w, START5, band=0.02, slippage_bps=1.0)
            s5 = bt.stats(r5, BPY)
            row.append(f"{stop*100:.1f}:{s['cagr']*100:5.1f}/{s['max_drawdown']*100:5.1f}"
                       f"|{s5['cagr']*100:5.1f}/{s5['max_drawdown']*100:5.1f}")
        print(f"span{span:3d}  " + "  ".join(row))


if __name__ == "__main__":
    main()
