"""Surface for the capped ATR stop: dist = clip(k * ATR14, floor, cap).

Two designs are compared on both windows at 1 bp:
  * cap 4.0%  (never wider than the round-1 stop, tighter in calm markets)
  * cap 6.0%  (the uncapped version, for reference)
plus partial de-risking variants.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/agents2/vol-scaled-crash-stop/cap2.py
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
    BARS, START10, START5, build_measures, build_weights, load_cache,
    regime_arrays,
)


def run(ts, opens, closes, w, start):
    r = bt.run(ts, opens, closes, w, start, band=0.02, slippage_bps=1.0)
    s = bt.stats(r, BARS)
    dd = r["equity"] / np.maximum.accumulate(r["equity"]) - 1.0
    j = int(np.argmin(dd))
    p = int(np.argmax(r["equity"][: j + 1]))
    return s, str(r["ts"][p])[:10], str(r["ts"][j])[:10]


def main():
    ts, opens, highs, lows, closes, _ = load_cache()
    m = build_measures(ts, opens, highs, lows, closes)
    first, last = m["first"], m["last"]
    risk_on, armed, _ = regime_arrays(ts, closes, first, last)
    a = m["atr14"]
    out = {}

    cases = []
    for k in (0.45, 0.55, 0.65, 0.70, 0.75, 0.85, 0.95):
        cases.append((f"cap4 k{k:.2f}", np.clip(k * a, 0.025, 0.040), (0, 0, 1)))
    cases += [
        ("cap6 k0.70", np.clip(0.70 * a, 0.025, 0.060), (0, 0, 1)),
        ("cap4 k0.70 floor1.5", np.clip(0.70 * a, 0.015, 0.040), (0, 0, 1)),
        ("cap4 k0.70 floor3.0", np.clip(0.70 * a, 0.030, 0.040), (0, 0, 1)),
        ("cap4 k0.70 -> 50QQQ", np.clip(0.70 * a, 0.025, 0.040), (0.5, 0, 0.5)),
        ("fixed4 -> 50QQQ", np.full(len(first), 0.04), (0.5, 0, 0.5)),
    ]

    for label, d, alloc in cases:
        w, ns = build_weights(ts, opens, closes, first, last, risk_on, armed, d,
                              alloc1=alloc)
        s10, p10, t10 = run(ts, opens, closes, w, START10)
        s5, p5, t5 = run(ts, opens, closes, w, START5)
        out[label] = dict(stops=ns, alloc=list(alloc),
                          cagr10=s10["cagr"], dd10=s10["max_drawdown"],
                          sharpe10=s10["sharpe"], fills=s10["fills"],
                          cagr5=s5["cagr"], dd5=s5["max_drawdown"], sharpe5=s5["sharpe"],
                          dd5_dates=(p5, t5))
        print(f"{label:22s} stops {ns:4d}  10y {s10['cagr']*100:5.2f}/{s10['max_drawdown']*100:5.2f}"
              f"  Sh {s10['sharpe']:.2f}   5y {s5['cagr']*100:5.2f}/{s5['max_drawdown']*100:5.2f}"
              f"  Sh {s5['sharpe']:.2f}  fills {s10['fills']}")
        (HERE / "cap2.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
