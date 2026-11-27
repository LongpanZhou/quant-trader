"""Short opening-range neighbour test (5/10 min etc.), same rules."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "research"))
sys.path.insert(0, str(HERE))
import bt  # noqa: E402
import strategy as S  # noqa: E402

ts, o, c, bars = S.load_dev()
i = bt.start_index(ts, S.DEV_START)
for om in (1, 2, 3, 5, 10, 15, 20, 30, 45, 60):
    w, inf = S._build(ts, o, c, dict(S.CFG, or_min=om), bars)
    res = bt.run(ts, o, c, w, S.DEV_START, band=0.02, slippage_bps=1.0)
    s = bt.stats(res, S.BARS_1M)
    exp = np.mean(w[i:, 1] > 0)
    print(f"OR{om:2d}: CAGR {s['cagr']*100:6.2f}%  DD {s['max_drawdown']*100:6.2f}%  "
          f"Sharpe {s['sharpe']:5.2f}  entries {inf['entries']:4d}  exp {exp*100:5.1f}%  "
          f"fills {s['fills']}")
