"""Robustness of the stop-distance definition: intraday range instead of true
range, Wilder smoothing, longer/shorter lookback. 1 bp, both windows.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/agents2/vol-scaled-crash-stop/robust.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

from sweep1 import (  # noqa: E402
    build_measures, build_weights, fmt, load_cache, regime_arrays, run_one,
)


def alt_measures(highs, lows, closes, first, last):
    high = np.maximum.reduceat(highs[:, 1], first)
    low = np.minimum.reduceat(lows[:, 1], first)
    close = closes[last, 1]
    prev = np.r_[np.nan, close[:-1]]
    tr = np.maximum.reduce([high - low, np.abs(high - prev), np.abs(low - prev)])
    sh = lambda x: np.r_[np.nan, x[:-1]]
    out = {}
    out["range14"] = sh(pd.Series(high - low).rolling(14).mean().to_numpy() / close)
    # Wilder ATR(14)
    a = pd.Series(tr).ewm(alpha=1 / 14, adjust=False).mean().to_numpy() / close
    out["wilder14"] = sh(a)
    out["atr20"] = sh(pd.Series(tr).rolling(20).mean().to_numpy() / close)
    out["atr10"] = sh(pd.Series(tr).rolling(10).mean().to_numpy() / close)
    return out


def main():
    t0 = time.time()
    ts, opens, highs, lows, closes, vols = load_cache()
    m = build_measures(ts, opens, highs, lows, closes)
    dates, first, last = m["dates"], m["first"], m["last"]
    risk_on, armed, dc = regime_arrays(ts, closes, first, last)
    alt = alt_measures(highs, lows, closes, first, last)
    cl = np.clip

    cands = {
        "ATR14 simple x0.70": cl(0.70 * m["atr14"], 0.025, 0.040),
        "intraday range14 x0.70": cl(0.70 * alt["range14"], 0.025, 0.040),
        "ATR14 Wilder x0.70": cl(0.70 * alt["wilder14"], 0.025, 0.040),
        "ATR20 simple x0.70": cl(0.70 * alt["atr20"], 0.025, 0.040),
        "ATR10 simple x0.70": cl(0.70 * alt["atr10"], 0.025, 0.040),
    }
    out = {}
    print(f"\n{'stop definition':30s} {'stops':>5s}   10y @1bp              5y @1bp")
    for label, d in cands.items():
        w, ns = build_weights(ts, opens, closes, first, last, risk_on, armed, d)
        s10 = run_one(label, ts, opens, closes, w, "10y", 1.0)
        s5 = run_one(label, ts, opens, closes, w, "5y", 1.0)
        out[label] = dict(stops=ns,
                          cagr10=s10["cagr"], dd10=s10["max_drawdown"],
                          cagr5=s5["cagr"], dd5=s5["max_drawdown"],
                          fills=s10["fills"])
        print(f"{label:30s} {ns:5d}   {s10['cagr']*100:5.2f}/{s10['max_drawdown']*100:5.2f}"
              f"          {s5['cagr']*100:5.2f}/{s5['max_drawdown']*100:5.2f}")
    (HERE / "robust.json").write_text(json.dumps(out, indent=2))
    print(f"done {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
