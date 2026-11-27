"""Report appendix numbers: rolling table, stop counts by year, yearly table."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import srlib as S  # noqa: E402

R = json.loads((HERE / "result.json").read_text())
print("YEARLY (1 bp)")
print("year  base     combo    tqqq     delta")
for y, b in R["variants"]["base"]["10y"]["yearly"].items():
    q = R["variants"]["combo"]["10y"]["yearly"][y]
    print(f"{y}  {b['strategy']*100:7.2f}% {q['strategy']*100:7.2f}% {b['benchmark']*100:7.2f}% "
          f"{(q['strategy']-b['strategy'])*100:+7.2f}pp")

print("\nROLLING 3Y")
print("start       combo CAGR/DD      winner CAGR/DD     tqqq CAGR/DD      beats")
rows = R["rolling"]["windows"]
for r in rows:
    print(f"{r['start']}  {r['cagr']*100:6.2f}/{r['dd']*100:5.2f}  "
          f"{r['winner_cagr']*100:6.2f}/{r['winner_dd']*100:5.2f}  "
          f"{r['bench_cagr']*100:6.2f}/{r['bench_dd']*100:5.2f}  "
          f"{'W' if r['beats_winner'] else '-'}{'T' if r['beats_bench'] else '-'}")
print(f"beats winner on both: {sum(r['beats_winner'] for r in rows)}/{len(rows)}")
print(f"beats tqqq on both:   {sum(r['beats_bench'] for r in rows)}/{len(rows)}")
print(f"lower DD than winner: {sum(r['dd'] < r['winner_dd'] for r in rows)}/{len(rows)}")
print(f"higher CAGR than winner: {sum(r['cagr'] > r['winner_cagr'] for r in rows)}/{len(rows)}")

# stop counts in the test window
A = S.arrays()
ts, first, last = A["ts"], A["first"], A["last"]
o, c = A["o"], A["c"]
reg, ma20 = S.regime(ts, c[:, 0], first, last)
vwap = S.session_vwap(A["h"], A["l"], A["c"], A["v"], first, last)
ema5 = S.session_ema(c, first, last, 5, 9)
ema5b = S.session_ema(c, first, last, 5, 20)
ema15 = S.session_ema(c, first, last, 15, 9)
for name, kw in (("base", dict(mode="base")),
                 ("combo", dict(mode="nextday", block_next_on_weak_close=True, block_frac=0.5,
                                next_day_tight=0.02))):
    w, d = S.make_weights(A, reg, ma20, vwap, ema5, ema5b, ema15, **kw)
    sd = [A["dates"][i] for i in d["stops"] if A["dates"][i].year >= 2017]
    print(f"\n{name} stop events in test window: {len(sd)}")
    print(pd.Series([str(x)[:4] for x in sd]).value_counts().sort_index().to_dict())
    print(f"  tight days {d['tight_days']} tight stops {d['tight_stops']} blocked {d['blocked_days']}")
