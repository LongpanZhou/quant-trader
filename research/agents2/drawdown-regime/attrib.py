"""Attribution: where does the conditional-stop variant differ from the winner?

Computes the daily log-return difference between two weight vectors and lists
the top contributing sessions and the yearly totals.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ddlib as L
import fastsim


def daily_eq(ts, opens, closes, w, start):
    i = L.bt.start_index(ts, start)
    r = fastsim.simulate(ts[i:], opens[i:], closes[i:], w[i:], band=0.02,
                         slippage_bps=1.0)
    ser = pd.Series(r["equity"], index=ts[i:])
    return ser.groupby(ser.index.date).last()


def cond_stop(dctx, dd_thr, stop2, base_stop=0.04):
    first, last = dctx["first"], dctx["last"]
    n = dctx["n"]
    hold = np.zeros(len(dctx["first"]) * 0 + len(dctx["dates"]) * 0 + 0)
    hold = np.zeros(len(dctx["ma20"]) * 0)  # placeholder
    return None


def build(dctx, ts, opens, closes, dd_thr, stop2, base_stop=0.04):
    first, last = dctx["first"], dctx["last"]
    n = len(ts)
    qqq_close, tqqq_close = closes[:, 0], closes[:, 1]
    hold = np.zeros(n)
    for k, (f, l) in enumerate(zip(first, last)):
        if not dctx["reg"][k]:
            continue
        stop = stop2 if dctx["dd_prev"][k] <= -dd_thr else base_stop
        armed = bool(np.isfinite(dctx["arm_ma20"][k])
                     and qqq_close[f] < dctx["arm_ma20"][k] * 1.01)
        base = opens[f, 1]
        on = True
        for i in range(f, l + 1):
            if on and armed and tqqq_close[i] < base * (1 - stop):
                on = False
            hold[i] = 1.0 if on else 0.0
    w = np.zeros((n, 3))
    w[:, 1] = hold
    w[:, 2] = 1 - hold
    return w


def main():
    ts, opens, closes = L.load_panel()
    dctx = L.daily_context(ts, closes)
    wa, _ = L.render(ts, opens, closes, dctx, np.ones(dctx["n"]))
    wb = build(dctx, ts, opens, closes, 0.08, 0.02)

    for st in (L.START10, L.START5):
        ea = daily_eq(ts, opens, closes, wa, st)
        eb = daily_eq(ts, opens, closes, wb, st)
        ra = np.log(ea).diff().fillna(0)
        rb = np.log(eb).diff().fillna(0)
        d = rb - ra
        print(f"\n=== {st} ===  total log diff {d.sum()*100:6.2f} pp")
        by_year = d.groupby([x.year for x in d.index]).sum() * 100
        print("year  diff_pp")
        for y, v in by_year.items():
            print(f"{y}  {v:7.2f}")
        print("top |diff| days:")
        top = d.reindex(d.abs().sort_values(ascending=False).index[:20])
        for dt, v in top.items():
            print(f"  {dt}  {v*100:7.2f} pp")
        print(f"sum of top 5 {d.abs().sort_values(ascending=False).head(5).sum()*100:.2f} pp"
              f"  ; positive days {int((d>0).sum())}, negative {int((d<0).sum())}")


if __name__ == "__main__":
    main()
