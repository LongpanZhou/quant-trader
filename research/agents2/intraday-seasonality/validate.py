"""Validate the fast simulator against bt.simulate and reproduce the winner."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402
import lib  # noqa: E402

ts, opens, closes = lib.load_panel()
print("panel", len(ts), ts[0], ts[-1])
t0 = time.time()
w, diag = lib.build_base(ts, opens, closes)
print(f"base built in {time.time()-t0:.1f}s, stop events {diag['stop_events']}, days {diag['days']}")

for slip in (1.0, 5.0, 10.0):
    t0 = time.time()
    r = lib.simulate(ts, opens, closes, w, slippage_bps=slip)
    tf = time.time() - t0
    for label, start in (("10y", lib.START10), ("5y", lib.START5)):
        s = lib.window(r, ts, start)
        print(f"fast {slip:.0f}bp {label}: CAGR {s['cagr']*100:6.2f}%  DD {s['max_drawdown']*100:5.2f}% "
              f"Sharpe {s['sharpe']:4.2f}  fills {r['fills']}  [{tf:.2f}s]")

# reference: bt.simulate at 1bp
t0 = time.time()
ref = bt.run(ts, opens, closes, w, lib.START10, band=0.02, slippage_bps=1.0)
s = bt.stats(ref, lib.BARS_PER_YEAR)
mine = lib.window(lib.simulate(ts, opens, closes, w, 1.0), ts, lib.START10)
print(f"\nbt.simulate 10y: CAGR {s['cagr']*100:.4f}%  DD {s['max_drawdown']*100:.4f}%  "
      f"end {s['ending_equity']:.2f}  fills {s['fills']}  [{time.time()-t0:.1f}s]")
print(f"fast        10y: CAGR {mine['cagr']*100:.4f}%  DD {mine['max_drawdown']*100:.4f}%  "
      f"end {mine['ending_equity']:.2f}")
