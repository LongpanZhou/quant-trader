"""Second screen: is ATR scaling better than a fixed tighter stop, and does
partial de-risking combine with it? 10y, 1 bp.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/agents2/vol-scaled-crash-stop/sweep2.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

from sweep1 import (  # noqa: E402
    BARS, START10, START5, build_measures, build_weights, day_bounds, fmt,
    load_cache, regime_arrays, run_one,
)


def main():
    t0 = time.time()
    ts, opens, highs, lows, closes, vols = load_cache()
    m = build_measures(ts, opens, highs, lows, closes)
    dates, first, last = m["dates"], m["first"], m["last"]
    risk_on, armed, dc = regime_arrays(ts, closes, first, last)
    nd = len(first)
    print(f"setup {time.time()-t0:.1f}s")

    fixed = lambda x: np.full(nd, x)
    cl = lambda x, lo, hi: np.clip(x, lo, hi)
    a = m["atr14"]

    variants = [
        ("fixed 2.5% -> BIL", fixed(0.025), (0, 0, 1), None, 1.5, False),
        ("fixed 3.0% -> BIL", fixed(0.030), (0, 0, 1), None, 1.5, False),
        ("fixed 3.5% -> BIL", fixed(0.035), (0, 0, 1), None, 1.5, False),
        ("ATR .60 [2.5,6] -> BIL", cl(0.60 * a, 0.025, 0.06), (0, 0, 1), None, 1.5, False),
        ("ATR .65 [2.5,6] -> BIL", cl(0.65 * a, 0.025, 0.06), (0, 0, 1), None, 1.5, False),
        ("ATR .70 [2.5,6] -> BIL", cl(0.70 * a, 0.025, 0.06), (0, 0, 1), None, 1.5, False),
        ("ATR .75 [2.5,6] -> BIL", cl(0.75 * a, 0.025, 0.06), (0, 0, 1), None, 1.5, False),
        ("ATR .80 [2.5,6] -> BIL", cl(0.80 * a, 0.025, 0.06), (0, 0, 1), None, 1.5, False),
        ("ATR .70 [2.0,5.0] -> BIL", cl(0.70 * a, 0.020, 0.05), (0, 0, 1), None, 1.5, False),
        ("ATR .70 [3.0,7.0] -> BIL", cl(0.70 * a, 0.030, 0.07), (0, 0, 1), None, 1.5, False),
        ("ATR .70 [2.5,6] -> QQQ", cl(0.70 * a, 0.025, 0.06), (1, 0, 0), None, 1.5, False),
        ("ATR .70 [2.5,6] -> 50QQQ", cl(0.70 * a, 0.025, 0.06), (0.5, 0, 0.5), None, 1.5, False),
        ("ATR .85 [2.5,6] -> 50QQQ", cl(0.85 * a, 0.025, 0.06), (0.5, 0, 0.5), None, 1.5, False),
        ("fixed 4% -> 100% QQQ", fixed(0.04), (1, 0, 0), None, 1.5, False),
        ("ATR .70 2-stage 50QQQ/BIL x1.8", cl(0.70 * a, 0.025, 0.06), (0.5, 0, 0.5), (0, 0, 1), 1.8, False),
        ("ATR .70 2-stage 50QQQ/BIL x2.0", cl(0.70 * a, 0.025, 0.06), (0.5, 0, 0.5), (0, 0, 1), 2.0, False),
        ("vol20 x1.2 [3,6] -> 50QQQ", cl(1.2 * m["vol20"], 0.03, 0.06), (0.5, 0, 0.5), None, 1.5, False),
        ("ATR5m x7 [2.5,6] -> 50QQQ", cl(7.0 * m["atr5"], 0.025, 0.06), (0.5, 0, 0.5), None, 1.5, False),
    ]

    out = {}
    print(f"\n{'variant':36s} {'stops':>5s}  10y @1bp")
    for label, d, a1, a2, s2, io in variants:
        t1 = time.time()
        w, ns = build_weights(ts, opens, closes, first, last, risk_on, armed, d,
                              alloc1=a1, alloc2=a2, stage2_mult=s2, intraday_only=io)
        s = run_one(label, ts, opens, closes, w, "10y", 1.0)
        out[label] = dict(stops=ns, cagr=s["cagr"], dd=s["max_drawdown"],
                          sharpe=s["sharpe"], fills=s["fills"], turnover=s["turnover"])
        print(f"{label:36s} {ns:5d}  {fmt(s)}   [{time.time()-t1:.0f}s]")

    (HERE / "sweep2.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
