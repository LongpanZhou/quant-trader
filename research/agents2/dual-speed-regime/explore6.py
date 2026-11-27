"""Exploration 6: anatomy of the finalists, yearly, rolling 3y, TQQQ-signal ablation."""
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
from explore5 import build_armed  # noqa: E402
from explore4 import all_episodes, monthly  # noqa: E402


def get_curve(w, ts, opens, closes, start, slip=1.0):
    r = bt.run(ts, opens, closes, w, start, band=0.02, slippage_bps=slip)
    return r


def yearly(eq, ts, bench):
    out = {}
    for y in sorted(set(ts.year)):
        m = np.array([t.year == y for t in ts])
        if m.sum() < 2:
            continue
        out[y] = (eq[m][-1] / eq[m][0] - 1.0, bench[m][-1] / bench[m][0] - 1.0)
    return out


def rolling3(eq, bench, ts, months=3):
    """Quarterly-start 3-year windows."""
    idx = pd.Series(eq, index=ts)
    b = pd.Series(bench, index=ts)
    starts = pd.date_range(ts[0].normalize(), ts[-1].normalize(), freq="QS")
    rows = []
    for s in starts:
        e = s + pd.DateOffset(years=3)
        if e > ts[-1]:
            break
        a = idx.loc[s:e]
        c = b.loc[s:e]
        if len(a) < 100 or len(c) < 100:
            continue
        yrs = (a.index[-1] - a.index[0]).total_seconds() / (365.25 * 86400)
        ca = (a.iloc[-1] / a.iloc[0]) ** (1 / yrs) - 1
        cb = (c.iloc[-1] / c.iloc[0]) ** (1 / yrs) - 1
        da = float(-(a / a.cummax() - 1).min())
        db = float(-(c / c.cummax() - 1).min())
        rows.append(dict(start=str(s.date()), end=str(a.index[-1].date()),
                         cagr=ca, dd=da, bcagr=cb, bdd=db))
    return rows


def main():
    ts, opens, closes = load()
    dates, first, last, day_id = day_index(ts)
    dc = closes[last, 0]
    ma20 = pd.Series(dc).rolling(20).mean().to_numpy()
    reg165 = daily_state(ts, dc, 165)
    w_base = weights_from_daily(reg165, day_id)
    w_stop, _ = apply_stop(ts, opens, closes, w_base, reg165, day_id, first, last, ma20)

    s60_40 = sixty_min_bars(closes[:, 0], first, last, 40)[0]
    s60_35 = sixty_min_bars(closes[:, 0], first, last, 35)[0]
    s60_45 = sixty_min_bars(closes[:, 0], first, last, 45)[0]
    s60_40_tq = sixty_min_bars(closes[:, 1], first, last, 40)[0]

    cands = {
        "WINNER": w_stop,
        "C4-40": build_armed(ts, opens, closes, reg165, s60_40, first, last, ma20, stop=0.04)[0],
        "C4-40-FC": build_armed(ts, opens, closes, reg165, s60_40, first, last, ma20, stop=0.04,
                                force_close=True)[0],
        "C4-35": build_armed(ts, opens, closes, reg165, s60_35, first, last, ma20, stop=0.04)[0],
        "C4-45": build_armed(ts, opens, closes, reg165, s60_45, first, last, ma20, stop=0.04)[0],
        "C4-40-TQQsig": build_armed(ts, opens, closes, reg165, s60_40_tq, first, last, ma20, stop=0.04)[0],
    }

    i0 = bt.start_index(ts, START10)
    bench = closes[:, 1]
    for name, w in cands.items():
        r = get_curve(w, ts, opens, closes, START10)
        eq, ets = r["equity"], r["ts"]
        s = bt.stats(r, BPY)
        print(f"\n=== {name} 10y CAGR {s['cagr']*100:.2f} DD {s['max_drawdown']*100:.2f} ===")
        for e in all_episodes(ts[i0:], eq, 4):
            print(f"   DD {e[0]*100:5.2f}%  {e[1]} -> {e[2]}  rec {e[3]}")
        yr = yearly(eq, ets, bench[i0:])
        print("   yearly " + "  ".join(f"{y}:{v[0]*100:6.1f}/{v[1]*100:6.1f}" for y, v in yr.items()))
        print("   2020 " + monthly(eq, ets, "2020-01-01", "2020-06-30"))
        print("   2026 " + monthly(eq, ets, "2026-01-01", "2026-10-31"))
        rows = rolling3(eq, bench[i0:], ets)
        beatb = sum(1 for r in rows if r["cagr"] > r["bcagr"] and r["dd"] < r["bdd"])
        print(f"   rolling3y n={len(rows)} beat TQQQ both={beatb} "
              f"worstDD={max(r['dd'] for r in rows)*100:.1f}% "
              f"minCAGR={min(r['cagr'] for r in rows)*100:.1f}%")

    # winner rolling rows for comparison
    rw = get_curve(w_stop, ts, opens, closes, START10)
    rows_w = rolling3(rw["equity"], bench[i0:], rw["ts"])
    print("\nwinner rolling3y starts:", [r["start"] for r in rows_w][:3], "...", len(rows_w))


if __name__ == "__main__":
    main()
