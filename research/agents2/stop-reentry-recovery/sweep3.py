"""Partial next-open blocking + trend/whipsaw filters."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

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

dclose = c[last, 0]
day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, len(ts)]))


def prior(ma_n):
    m = pd.Series(dclose).rolling(ma_n).mean().to_numpy()
    p = np.r_[np.nan, m[:-1]]
    return p[day_id]


q_ma10, q_ma20, q_ma50, q_ma165 = (prior(n) for n in (10, 20, 50, 165))


def below(ma):
    x = dclose[day_id] if False else np.r_[np.nan, dclose[:-1]][day_id]
    return np.isfinite(ma) & (x < ma)


masks = {"none": None, "ma10": below(q_ma10), "ma20": below(q_ma20),
         "ma50": below(q_ma50), "ma165": below(q_ma165)}

V = {
    "base": dict(mode="base"),
    "blk50": dict(mode="nextday", block_next_on_weak_close=True, block_frac=0.50),
    "blk50_ma50": dict(mode="nextday", block_next_on_weak_close=True, block_frac=0.50, block_mask=masks["ma50"]),
    "blk75_ma50": dict(mode="nextday", block_next_on_weak_close=True, block_frac=0.75, block_mask=masks["ma50"]),
    "blk100_ma50": dict(mode="nextday", block_next_on_weak_close=True, block_frac=1.00, block_mask=masks["ma50"]),
    "blk50_ma20": dict(mode="nextday", block_next_on_weak_close=True, block_frac=0.50, block_mask=masks["ma20"]),
    "blk75_ma20": dict(mode="nextday", block_next_on_weak_close=True, block_frac=0.75, block_mask=masks["ma20"]),
    "blk50_ma10": dict(mode="nextday", block_next_on_weak_close=True, block_frac=0.50, block_mask=masks["ma10"]),
    "blk50_ma165": dict(mode="nextday", block_next_on_weak_close=True, block_frac=0.50, block_mask=masks["ma165"]),
}

res = {}
t0 = time.time()
for name, kw in V.items():
    w, d = S.make_weights(A, reg, ma20, vwap, ema5, ema5b, ema15, **kw)
    row = dict(blocked=d["blocked_days"])
    for lab, start in (("10y", S.START10), ("5y", S.START5)):
        s = S.metrics(ts, o, c, w, start, 1.0)
        row[lab] = dict(cagr=s["cagr"], dd=s["max_drawdown"], sharpe=s["sharpe"], fills=s["fills"])
        if name in ("base", "blk50", "blk50_ma50"):
            row[lab]["yearly"] = {str(k): v for k, v in s["yearly"].items()}
    res[name] = row
    print(f"{name:14s} blk={row['blocked']:3d} | 10y {row['10y']['cagr']*100:6.2f}/{row['10y']['dd']*100:5.2f} | "
          f"5y {row['5y']['cagr']*100:6.2f}/{row['5y']['dd']*100:5.2f} | fills {row['10y']['fills']:5d}")

(HERE / "sweep3.json").write_text(json.dumps(res, indent=2))
if "base" in res:
    print("\nyearly:")
    for y in res["base"]["10y"]["yearly"]:
        print(f"  {y}: base {res['base']['10y']['yearly'][y]['strategy']*100:7.2f}%  "
              f"blk50 {res['blk50']['10y']['yearly'][y]['strategy']*100:7.2f}%  "
              f"blk50_ma50 {res['blk50_ma50']['10y']['yearly'][y]['strategy']*100:7.2f}%")
print(f"\n{time.time()-t0:.1f}s")
