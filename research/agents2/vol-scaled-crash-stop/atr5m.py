"""5m-ATR variant on both windows at 1 bp (the sweep4 job died before it).

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/agents2/vol-scaled-crash-stop/atr5m.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

from sweep1 import (  # noqa: E402
    build_measures, build_weights, load_cache, regime_arrays, run_one,
)


def main():
    ts, opens, highs, lows, closes, _ = load_cache()
    m = build_measures(ts, opens, highs, lows, closes)
    first, last = m["first"], m["last"]
    risk_on, armed, _ = regime_arrays(ts, closes, first, last)
    out = {}
    for k in (6.0, 7.0, 8.0):
        d = np.clip(k * m["atr5"], 0.025, 0.040)
        w, ns = build_weights(ts, opens, closes, first, last, risk_on, armed, d)
        s10 = run_one("", ts, opens, closes, w, "10y", 1.0)
        s5 = run_one("", ts, opens, closes, w, "5y", 1.0)
        out[f"{k:.0f}x"] = dict(stops=ns, cagr10=s10["cagr"], dd10=s10["max_drawdown"],
                                cagr5=s5["cagr"], dd5=s5["max_drawdown"],
                                fills=s10["fills"])
        print(f"ATR5m x{k:.0f} cap4  stops {ns:4d}  10y "
              f"{s10['cagr']*100:5.2f}/{s10['max_drawdown']*100:5.2f}  5y "
              f"{s5['cagr']*100:5.2f}/{s5['max_drawdown']*100:5.2f}  fills {s10['fills']}")
        (HERE / "atr5m.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
