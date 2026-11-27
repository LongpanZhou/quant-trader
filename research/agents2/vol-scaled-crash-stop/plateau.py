"""Check the k-neighbourhood around the ATR plateau on the 5y window (1 bp).

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/agents2/vol-scaled-crash-stop/plateau.py
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
    for k in (0.45, 0.50, 0.55, 0.60, 0.65):
        d = np.clip(k * m["atr14"], 0.025, 0.06)
        w, ns = build_weights(ts, opens, closes, first, last, risk_on, armed, d)
        s5 = run_one("", ts, opens, closes, w, "5y", 1.0)
        s10 = run_one("", ts, opens, closes, w, "10y", 1.0)
        out[f"{k:.2f}"] = dict(stops=ns, cagr5=s5["cagr"], dd5=s5["max_drawdown"],
                               cagr10=s10["cagr"], dd10=s10["max_drawdown"])
        print(f"k={k:.2f} stops {ns:4d}  10y {s10['cagr']*100:5.2f}/{s10['max_drawdown']*100:5.2f}"
              f"   5y {s5['cagr']*100:5.2f}/{s5['max_drawdown']*100:5.2f}")
        (HERE / "plateau.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
