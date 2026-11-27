"""Does capping the ATR stop at/below the round-1 4% make the 5y result robust?

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/agents2/vol-scaled-crash-stop/cap.py
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
    for label, d in (
        ("k0.70 cap4.0", np.clip(0.70 * a, 0.025, 0.040)),
        ("k0.55 cap4.0", np.clip(0.55 * a, 0.025, 0.040)),
        ("k0.70 cap3.5", np.clip(0.70 * a, 0.025, 0.035)),
        ("k0.55 cap3.5", np.clip(0.55 * a, 0.025, 0.035)),
        ("k0.90 cap4.0", np.clip(0.90 * a, 0.025, 0.040)),
        ("fixed 2.75%", np.full(len(first), 0.0275)),
    ):
        w, ns = build_weights(ts, opens, closes, first, last, risk_on, armed, d)
        s10, p10, t10 = run(ts, opens, closes, w, START10)
        s5, p5, t5 = run(ts, opens, closes, w, START5)
        out[label] = dict(stops=ns, cagr10=s10["cagr"], dd10=s10["max_drawdown"],
                          cagr5=s5["cagr"], dd5=s5["max_drawdown"],
                          dd10_dates=(p10, t10), dd5_dates=(p5, t5))
        print(f"{label:14s} stops {ns:4d}  10y {s10['cagr']*100:5.2f}/{s10['max_drawdown']*100:5.2f}"
              f"   5y {s5['cagr']*100:5.2f}/{s5['max_drawdown']*100:5.2f}"
              f"   dd5 {p5}->{t5}")
    (HERE / "cap.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
