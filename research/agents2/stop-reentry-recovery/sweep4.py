"""Re-entry day with a tighter stop (after the prior session's stop)."""
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

V = {
    "base": dict(mode="base"),
    "ndt1.5": dict(mode="base", next_day_tight=0.015),
    "ndt2": dict(mode="base", next_day_tight=0.02),
    "ndt3": dict(mode="base", next_day_tight=0.03),
    "ndt2_weak": dict(mode="base", next_day_tight=0.02, next_day_tight_weak_only=True),
    "ndt2_armed": dict(mode="base", next_day_tight=0.02, next_day_tight_armed_only=True),
    "blk25_ndt2": dict(mode="nextday", block_next_on_weak_close=True, block_frac=0.25, next_day_tight=0.02),
    "blk50_ndt2": dict(mode="nextday", block_next_on_weak_close=True, block_frac=0.50, next_day_tight=0.02),
}

res = {}
t0 = time.time()
for name, kw in V.items():
    w, d = S.make_weights(A, reg, ma20, vwap, ema5, ema5b, ema15, **kw)
    row = dict(stops=len(d["stops"]), blocked=d["blocked_days"])
    for lab, start in (("10y", S.START10), ("5y", S.START5)):
        s = S.metrics(ts, o, c, w, start, 1.0)
        row[lab] = dict(cagr=s["cagr"], dd=s["max_drawdown"], sharpe=s["sharpe"], fills=s["fills"])
    res[name] = row
    print(f"{name:12s} stops={row['stops']:3d} blk={row['blocked']:2d} | "
          f"10y {row['10y']['cagr']*100:6.2f}/{row['10y']['dd']*100:5.2f} | "
          f"5y {row['5y']['cagr']*100:6.2f}/{row['5y']['dd']*100:5.2f} | fills {row['10y']['fills']:5d}")

(HERE / "sweep4.json").write_text(json.dumps(res, indent=2))
print(f"\n{time.time()-t0:.1f}s")
