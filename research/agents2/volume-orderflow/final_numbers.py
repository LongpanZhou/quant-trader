"""Step 22: all report numbers in one place."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine  # noqa: E402
from strategy import build_weights  # noqa: E402

pd.set_option("display.width", 200)


def ddpts(D, w, start, slip=1.0):
    i = engine.bt.start_index(D.ts, start)
    r = engine.fastsim.fast_sim(D.op[i:], D.cl[i:], w[i:], slippage_bps=slip)
    eq, ts = r["equity"], D.ts[i:]
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1
    j = int(np.argmin(dd))
    p = int(np.argmax(eq[:j + 1]))
    return str(ts[p]), str(ts[j]), float(-dd[j])


def main():
    D = engine.Data()
    w, ev = build_weights(D)
    wb, _ = engine.winner_weights(D)

    print("== headline")
    for slip in (1.0, 5.0, 10.0):
        for lab, ww in (("final", w), ("winner", wb)):
            r = engine.evaluate(D, ww, "", slip=slip)
            print(f"  {slip:2.0f}bp {lab:6s}: 10y {r['10y']['cagr']*100:6.2f}/"
                  f"{r['10y']['max_drawdown']*100:5.2f}  Sharpe {r['10y']['sharpe']:.2f} | "
                  f"5y {r['5y']['cagr']*100:6.2f}/{r['5y']['max_drawdown']*100:5.2f} "
                  f"Sharpe {r['5y']['sharpe']:.2f}")

    print("\n== drawdown points")
    for lab, start in (("10y", engine.START10), ("5y", engine.START5)):
        a, b, v = ddpts(D, w, start)
        a2, b2, v2 = ddpts(D, wb, start)
        print(f"  {lab}: final {v*100:5.2f}%  {a} -> {b}")
        print(f"       winner {v2*100:5.2f}%  {a2} -> {b2}")

    print("\n== yearly (1bp)")
    r = engine.evaluate(D, w)["10y"]
    yw = engine.evaluate(D, wb)["10y"]
    print("  year   final      winner     tqqq")
    for y in r["yearly"]:
        print(f"  {y}  {r['yearly'][y]['strategy']*100:8.2f}% "
              f"{yw['yearly'][y]['strategy']*100:8.2f}% "
              f"{r['yearly'][y]['benchmark']*100:8.2f}%")

    print("\n== rolling 3y: final vs winner vs tqqq")
    r3 = engine.rolling3y(D, w)
    r3w = engine.rolling3y(D, wb)
    print("  window                    final CAGR/DD    winner CAGR/DD   tqqq CAGR/DD")
    for a, b in zip(r3, r3w):
        print(f"  {a['start']}..{a['end']}  {a['cagr']*100:6.1f}/{a['dd']*100:5.1f}   "
              f"{b['cagr']*100:6.1f}/{b['dd']*100:5.1f}   "
              f"{a['bench_cagr']*100:6.1f}/{a['bench_dd']*100:5.1f}")
    n = len(r3)
    print(f"  beat tqqq CAGR {sum(a['cagr']>a['bench_cagr'] for a in r3)}/{n}, "
          f"lower DD {sum(a['dd']<a['bench_dd'] for a in r3)}/{n}, "
          f"beat winner CAGR {sum(a['cagr']>b['cagr'] for a,b in zip(r3,r3w))}/{n}, "
          f"lower DD than winner {sum(a['dd']<b['dd'] for a,b in zip(r3,r3w))}/{n}")

    print("\n== worst 8 strategy days (10y)")
    i = engine.bt.start_index(D.ts, engine.START10)
    res = engine.fastsim.fast_sim(D.op[i:], D.cl[i:], w[i:], slippage_bps=1.0)
    idx = D.ts[i:]
    eq = pd.Series(res["equity"], index=idx).groupby(idx.date).last()
    worst = eq.pct_change().nsmallest(8)
    for d, v in worst.items():
        print(f"   {d} {v*100:7.2f}%")

    print("\n== exposure / stop stats")
    print(f"  stops {len(ev)}  (winner 160)  re-armed by volume alone: "
          f"{sum(e['rearmed_by_volume'] for e in ev)}")


if __name__ == "__main__":
    main()
