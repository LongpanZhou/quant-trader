"""Neighborhood grid around half-size weak-close blocking + 2% re-entry-day stop."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import srlib as S  # noqa: E402

A = S.arrays()
ts, first, last = A["ts"], A["first"], A["last"]
o, c = A["o"], A["c"]
reg, ma20 = S.regime(ts, c[:, 0], first, last)
vwap = S.session_vwap(A["h"], A["l"], A["c"], A["v"], first, last)
ema5 = S.session_ema(c, first, last, 5, 9)
ema5b = S.session_ema(c, first, last, 5, 20)
ema15 = S.session_ema(c, first, last, 15, 9)

res = {}
t0 = time.time()
for frac in (0.25, 0.375, 0.50, 0.625, 0.75):
    for tight in (0.015, 0.02, 0.025, 0.03):
        name = f"f{frac:.3f}_t{tight:.3f}"
        w, d = S.make_weights(A, reg, ma20, vwap, ema5, ema5b, ema15, mode="nextday",
                              block_next_on_weak_close=True, block_frac=frac,
                              next_day_tight=tight)
        row = dict(frac=frac, tight=tight, stops=len(d["stops"]), blocked=d["blocked_days"],
                   tight_stops=d["tight_stops"])
        for lab, start in (("10y", S.START10), ("5y", S.START5)):
            s = S.metrics(ts, o, c, w, start, 1.0)
            row[lab] = dict(cagr=s["cagr"], dd=s["max_drawdown"], sharpe=s["sharpe"], fills=s["fills"])
        res[name] = row
        print(f"frac {frac:.3f} tight {tight*100:4.1f}%  blk {row['blocked']:2d} ts {row['tight_stops']:2d} | "
              f"10y {row['10y']['cagr']*100:6.2f}/{row['10y']['dd']*100:5.2f} | "
              f"5y {row['5y']['cagr']*100:6.2f}/{row['5y']['dd']*100:5.2f}")
    print()

(HERE / "sweep5.json").write_text(json.dumps(res, indent=2))
print(f"{time.time()-t0:.1f}s")
