"""Fixed-stop controls on the 5y window (for the surface table)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

from sweep1 import build_weights, load_cache, regime_arrays, run_one  # noqa: E402

ts, opens, highs, lows, closes, _ = load_cache()
from sweep1 import build_measures  # noqa: E402
m = build_measures(ts, opens, highs, lows, closes)
first, last = m["first"], m["last"]
risk_on, armed, _ = regime_arrays(ts, closes, first, last)
out = {}
for x in (0.025, 0.030, 0.035):
    w, ns = build_weights(ts, opens, closes, first, last, risk_on, armed,
                          np.full(len(first), x))
    s = run_one("", ts, opens, closes, w, "5y", 1.0)
    out[f"{x:.3f}"] = dict(stops=ns, cagr5=s["cagr"], dd5=s["max_drawdown"],
                           fills=s["fills"])
    print(f"fixed {x*100:.2f}%  5y {s['cagr']*100:5.2f}/{s['max_drawdown']*100:5.2f} "
          f"fills {s['fills']} stops {ns}", flush=True)
(HERE / "fixed5y.json").write_text(json.dumps(out, indent=2))
