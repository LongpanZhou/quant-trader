"""Anchor comparison + base re-validation after edits."""
from __future__ import annotations

import sys
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
    "combo_open": dict(mode="nextday", block_next_on_weak_close=True, block_frac=0.5,
                       next_day_tight=0.02),
    "combo_entry": dict(mode="nextday", block_next_on_weak_close=True, block_frac=0.5,
                        next_day_tight=0.02, tight_anchor="entry"),
    "combo_nochain": dict(mode="nextday", block_next_on_weak_close=True, block_frac=0.5,
                          next_day_tight=0.02, tight_chain=False),
}
for name, kw in V.items():
    w, d = S.make_weights(A, reg, ma20, vwap, ema5, ema5b, ema15, **kw)
    print(f"\n{name}: stops {len(d['stops'])} tight_days {d['tight_days']} tight_stops {d['tight_stops']} "
          f"blocked {d['blocked_days']}")
    for lab, start in (("10y", S.START10), ("5y", S.START5)):
        s = S.metrics(ts, o, c, w, start, 1.0)
        print(f"  {lab} CAGR {s['cagr']*100:6.2f}%  DD {s['max_drawdown']*100:5.2f}%  "
              f"Sharpe {s['sharpe']:4.2f}  fills {s['fills']:4d}  "
              f"DD {s['dd_peak_ts'][:10]} -> {s['dd_trough_ts'][:10]}")
