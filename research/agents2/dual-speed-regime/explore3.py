"""Exploration 3: drawdown anatomy and yearly returns for the promising variants."""
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


def episodes(ts, eq, top=5):
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    out = []
    i = 0
    n = len(eq)
    while i < n and len(out) < top:
        if dd[i] >= -1e-9:
            i += 1
            continue
        # find peak before i
        p = int(np.argmax(eq[: i + 1]))
        # trough is min dd until recovery
        j = i
        while j < n and dd[j] < -1e-9:
            j += 1
        seg = dd[p:j]
        t = p + int(np.argmin(seg))
        out.append((str(ts[p])[:16], str(ts[t])[:16], str(ts[min(j, n - 1)])[:16],
                    float(-seg.min()), int(j - p)))
        i = j + 1
    return out


def yearly(ts, eq, bench_close):
    i0 = bt.start_index(ts, START10)
    yrs = {}
    for y in sorted(set(ts[i0:].year)):
        m = np.array([t.year == y for t in ts[i0:]])
        e = eq[m]
        b = bench_close[i0:][m]
        yrs[y] = (e[-1] / e[0] - 1.0, b[-1] / b[0] - 1.0)
    return yrs


def main():
    ts, opens, closes = load()
    dates, first, last, day_id = day_index(ts)
    dc = closes[last, 0]
    ma20 = pd.Series(dc).rolling(20).mean().to_numpy()
    reg165 = daily_state(ts, dc, 165)
    w_base = weights_from_daily(reg165, day_id)
    w_stop, _ = apply_stop(ts, opens, closes, w_base, reg165, day_id, first, last, ma20)

    variants = {"WINNER": w_stop}
    for span in (20, 50, 100):
        state60, _, _, _ = sixty_min_bars(closes[:, 0], first, last, span)
        w3, _ = armed_reclaim_state(ts, opens, closes, reg165, state60, first, last, ma20)
        variants[f"C3-{span}"] = w3
        w4, _ = armed_reclaim_state(ts, opens, closes, reg165, state60, first, last, ma20,
                                    stop=0.04)
        variants[f"C4-{span}"] = w4

    i0 = bt.start_index(ts, START10)
    for name, w in variants.items():
        r = bt.run(ts, opens, closes, w, START10, band=0.02, slippage_bps=1.0)
        eq = r["equity"]
        print(f"\n=== {name} ===")
        for p, t, rec, dd, nb in episodes(ts[i0:], eq):
            print(f"  DD {dd*100:5.2f}%  {p} -> {t}  (recovered {rec})  {nb/390:.0f} sessions")
        yr = yearly(ts, eq, closes[:, 1])
        print("  yearly: " + "  ".join(f"{y}:{v[0]*100:6.1f}/{v[1]*100:6.1f}" for y, v in yr.items()))
        # 2018 monthly detail
        ser = pd.Series(eq, index=ts[i0:])
        mret = ser.resample("ME").last().pct_change()
        bad = mret.sort_values().head(6)
        print("  worst months: " + "  ".join(f"{k.strftime('%Y-%m')}:{v*100:.1f}%" for k, v in bad.items()))
        ex = float(np.mean((r["equity"] - r["cash"]) / r["equity"]))
        print(f"  exposure {ex*100:.1f}%  fills {r['fills']}")


if __name__ == "__main__":
    main()
