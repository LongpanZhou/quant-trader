"""Robustness suite: rolling 3y, sub-periods, walk-forward for the candidates."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ddlib as L


def cond_stop(ts, opens, closes, dctx, dd_thr, stop2, base_stop=0.04, scale2=1.0):
    first, last = dctx["first"], dctx["last"]
    n = len(ts)
    qqq_close, tqqq_close = closes[:, 0], closes[:, 1]
    hold = np.zeros(n)
    for k, (f, l) in enumerate(zip(first, last)):
        if not dctx["reg"][k]:
            continue
        deep = dctx["dd_prev"][k] <= -dd_thr
        stop = stop2 if deep else base_stop
        sc = scale2 if deep else 1.0
        armed = bool(np.isfinite(dctx["arm_ma20"][k])
                     and qqq_close[f] < dctx["arm_ma20"][k] * 1.01)
        base = opens[f, 1]
        on = True
        for i in range(f, l + 1):
            if on and armed and tqqq_close[i] < base * (1 - stop):
                on = False
            hold[i] = sc if on else 0.0
    w = np.zeros((n, 3))
    w[:, 1] = hold
    w[:, 2] = 1 - hold
    return w


def subperiod(ts, opens, closes, w, a, b):
    i = L.bt.start_index(ts, a)
    j = int(np.searchsorted(ts, pd.Timestamp(b, tz="America/New_York")))
    import fastsim
    r = fastsim.simulate(ts[i:j], opens[i:j], closes[i:j], w[i:j], band=0.02,
                         slippage_bps=1.0)
    return L._stats_from_equity(r["equity"], ts[i:j]), r


def main():
    ts, opens, closes = L.load_panel()
    dctx = L.daily_context(ts, closes)

    variants = {}
    variants["winner"] = L.render(ts, opens, closes, dctx, np.ones(dctx["n"]))[0]
    variants["dd8stop2"] = cond_stop(ts, opens, closes, dctx, 0.08, 0.02)
    variants["dd8stop2_75"] = cond_stop(ts, opens, closes, dctx, 0.08, 0.02, scale2=0.75)
    variants["dd10_bil"] = L.render(ts, opens, closes, dctx,
                                    L.dd_state(dctx, 0.10, 0.05, scale=0.0))[0]
    variants["dd5_half"] = L.render(ts, opens, closes, dctx,
                                    L.dd_state(dctx, 0.05, 0.02, scale=0.5))[0]

    print("== sub-periods (1bp) ==")
    periods = [("2017-2019", "2017-01-03", "2019-12-31"),
               ("2020-2022", "2020-01-01", "2022-12-31"),
               ("2023-2026", "2023-01-01", "2026-10-23"),
               ("half1", "2017-01-03", "2021-10-22"),
               ("half2", "2021-10-25", "2026-10-23")]
    hdr = f"{'period':10s}" + "".join(f"{k:>22s}" for k in variants)
    print(hdr)
    for name, a, b in periods:
        row = f"{name:10s}"
        for k, w in variants.items():
            s, _ = subperiod(ts, opens, closes, w, a, b)
            row += f"{s['cagr']*100:10.2f}/{s['max_drawdown']*100:5.2f}  "
        print(row)

    print("\n== rolling 3-year windows (monthly step, 1bp) ==")
    for name, w in variants.items():
        rows = L.rolling3y(ts, opens, closes, w)
        beat_tq = sum(1 for r in rows if r["cagr"] > r["bcagr"] and r["dd"] < r["bdd"])
        beat_w = None
        print(f"{name:14s} n={len(rows)}  beat TQQQ (cagr&dd) {beat_tq}/{len(rows)}  "
              f"median CAGR {np.median([r['cagr'] for r in rows])*100:.1f}%  "
              f"worst DD {max(r['dd'] for r in rows)*100:.1f}%")

    # winner-relative rolling comparison
    rows_w = L.rolling3y(ts, opens, closes, variants["winner"])
    for name in ("dd8stop2", "dd8stop2_75", "dd10_bil", "dd5_half"):
        rows = L.rolling3y(ts, opens, closes, variants[name])
        both = sum(1 for a, b in zip(rows, rows_w)
                   if a["cagr"] > b["cagr"] and a["dd"] < b["dd"])
        cagr_up = sum(1 for a, b in zip(rows, rows_w) if a["cagr"] > b["cagr"])
        dd_dn = sum(1 for a, b in zip(rows, rows_w) if a["dd"] < b["dd"])
        print(f"{name:14s} vs winner: beats both {both}/{len(rows)}, "
              f"higher CAGR {cagr_up}/{len(rows)}, lower DD {dd_dn}/{len(rows)}")
        worst = max(range(len(rows)), key=lambda i: rows[i]["cagr"] - rows_w[i]["cagr"])
        print(f"   worst relative window {rows[worst]['start']}..{rows[worst]['end']}: "
              f"{rows[worst]['cagr']*100:.1f}% vs {rows_w[worst]['cagr']*100:.1f}%")

    print("\n== walk-forward: pick (dd_thr, stop2) on one half, apply to the other ==")
    grid = [(t, s) for t in (0.05, 0.06, 0.07, 0.08, 0.10, 0.12)
            for s in (0.015, 0.02, 0.025, 0.03)]
    cache = {}
    for t, s in grid + [(0.04, 0.04)]:
        cache[(t, s)] = cond_stop(ts, opens, closes, dctx, t, s) if t != 0.04 else variants["winner"]
    for fit_name, fit_a, fit_b, test_name, test_a, test_b in [
        ("2017-2021", "2017-01-03", "2021-10-22", "2022-2026", "2021-10-25", "2026-10-23"),
        ("2022-2026", "2021-10-25", "2026-10-23", "2017-2021", "2017-01-03", "2021-10-22"),
    ]:
        best, best_score = None, -9
        for (t, s), w in cache.items():
            st, _ = subperiod(ts, opens, closes, w, fit_a, fit_b)
            score = st["cagr"] - 0.5 * st["max_drawdown"]
            if score > best_score:
                best_score, best = score, (t, s)
        t, s = best
        st, _ = subperiod(ts, opens, closes, cache[(t, s)], test_a, test_b)
        sw, _ = subperiod(ts, opens, closes, variants["winner"], test_a, test_b)
        print(f"fit {fit_name} -> best ({t:.0%},{s:.1%})  test {test_name}: "
              f"{st['cagr']*100:.2f}/{st['max_drawdown']*100:.2f}  "
              f"vs winner {sw['cagr']*100:.2f}/{sw['max_drawdown']*100:.2f}")

    print("\n== cost sensitivity of dd8stop2 ==")
    for bp in (1.0, 5.0, 10.0):
        o = L.summary(ts, opens, closes, variants["dd8stop2"], slippage_bps=bp)
        L.fmt(f"dd8stop2 {bp:.0f}bp", o)


if __name__ == "__main__":
    main()
