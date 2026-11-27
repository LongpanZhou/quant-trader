"""Diagnostics: daily paths around the winner's two max-drawdown episodes."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ddlib as L


def show(ts, opens, closes, dctx, w, a, b, label):
    r = L.summary(ts, opens, closes, w, starts=(L.START10,))[L.START10]
    eq = r["result"]["equity"]
    j0 = L.bt.start_index(ts, L.START10)
    tsx = ts[j0:]
    ser = pd.Series(eq, index=tsx)
    dser = ser.groupby(ser.index.date).last()
    peak = dser.cummax()
    dd_eq = dser / peak - 1.0

    first, last = dctx["first"], dctx["last"]
    i0 = int(np.searchsorted(dctx["dates"], pd.Timestamp(a).date()))
    i1 = int(np.searchsorted(dctx["dates"], pd.Timestamp(b).date()))
    print(f"\n=== {label}  {a}..{b} ===")
    print("date        QQQ     dd52   reg  TQQQ   TqqqDD  strat_eq   eqDD   w")
    for k in range(i0, i1 + 1):
        d = dctx["dates"][k]
        f = first[k]
        tq = closes[f, 1]
        # TQQQ drawdown from trailing 252-session high of daily closes
        lo = max(0, k - 251)
        tqdd = tq / closes[last[lo:k], 1].max() - 1 if k > lo else 0.0
        e = dser.get(d, np.nan)
        edd = dd_eq.get(d, np.nan)
        ww = w[f, 1]
        print(f"{d}  {dctx['dclose'][k]:7.2f} {dctx['dd_prev'][k]*100:7.2f} "
              f"{int(dctx['reg'][k])}  {tq:7.2f} {tqdd*100:7.2f}  "
              f"{e:10.0f} {edd*100:7.2f}  {ww:.2f}")


def main():
    ts, opens, closes = L.load_panel()
    dctx = L.daily_context(ts, closes)
    frac = np.ones(dctx["n"])
    w, _ = L.render(ts, opens, closes, dctx, frac)

    show(ts, opens, closes, dctx, w, "2026-06-01", "2026-08-14", "5y max-DD episode")
    show(ts, opens, closes, dctx, w, "2018-08-20", "2019-01-15", "2018 Q4 whipsaw")
    show(ts, opens, closes, dctx, w, "2019-04-15", "2019-06-20", "2019 Q2 whipsaw")


if __name__ == "__main__":
    main()
