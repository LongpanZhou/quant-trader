"""Second screen: ungated stop + re-entry, and partial conditional next-open."""
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
    "ungated_base": dict(mode="base", always_armed=True),
    "ungated_vwap_c1_t2": dict(mode="vwap", confirm=1, tight=0.02, always_armed=True),
    "ungated_vwap_c3_t2": dict(mode="vwap", confirm=3, tight=0.02, always_armed=True),
    "ungated_vwap_c1": dict(mode="vwap", confirm=1, always_armed=True),
    "ungated_ema5_t2": dict(mode="ema5", confirm=1, tight=0.02, always_armed=True),
    "ungated_ema15_t2": dict(mode="ema15", confirm=1, tight=0.02, always_armed=True),
    "blk25": dict(mode="nextday", block_next_on_weak_close=True, block_frac=0.25),
    "blk50": dict(mode="nextday", block_next_on_weak_close=True, block_frac=0.50),
    "blk75": dict(mode="nextday", block_next_on_weak_close=True, block_frac=0.75),
    "blk50_vwapnext": dict(mode="nextday", block_next_on_weak_close=True, block_frac=0.50),
}

res = {}
t0 = time.time()
for name, kw in V.items():
    w, d = S.make_weights(A, reg, ma20, vwap, ema5, ema5b, ema15, **kw)
    row = dict(reentries=len(d["reentries"]), second_stops=len(d["second_stops"]),
               blocked=d["blocked_days"])
    for lab, start in (("10y", S.START10), ("5y", S.START5)):
        s = S.metrics(ts, o, c, w, start, 1.0)
        row[lab] = dict(cagr=s["cagr"], dd=s["max_drawdown"], sharpe=s["sharpe"], fills=s["fills"])
    res[name] = row
    print(f"{name:20s} re={row['reentries']:3d} ss={row['second_stops']:3d} blk={row['blocked']:3d} | "
          f"10y {row['10y']['cagr']*100:6.2f}/{row['10y']['dd']*100:5.2f} | "
          f"5y {row['5y']['cagr']*100:6.2f}/{row['5y']['dd']*100:5.2f} | fills {row['10y']['fills']:5d}")

(HERE / "sweep2.json").write_text(json.dumps(res, indent=2))
print(f"\n{time.time()-t0:.1f}s")
