"""Cost slope of the core strategy (0-10 bp)."""
import sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "research"))
sys.path.insert(0, str(HERE))
import bt
import strategy as S

ts, o, c, bars = S.load_dev()
w = S.build_weights(ts, o, c)
for slip in (0.0, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0):
    r = bt.run(ts, o, c, w, S.DEV_START, band=0.02, slippage_bps=slip)
    s = bt.stats(r, S.BARS_1M)
    print(f"{slip:4.1f}bp: CAGR {s['cagr']*100:6.2f}%  DD {s['max_drawdown']*100:6.2f}%  "
          f"Sharpe {s['sharpe']:.2f}")
