r"""Blend the ratio-froth overlay with the first-hour / volume-stop sleeves.

Run from the repo root:
    $env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
    python research/verification/blend_ratio.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(ROOT / "research" / "agents2" / "volume-orderflow"))
import bt  # noqa: E402
import fastbt  # noqa: E402
import engine  # noqa: E402
import strategy as agent23  # noqa: E402


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


agent17 = load("agent17b", ROOT / "research" / "agents2" / "overnight-crash-filter" / "strategy.py")
agent21 = load("agent21", ROOT / "research" / "agents2" / "ratio-pairs" / "strategy.py")

START10, START5, END = "2017-01-03", "2021-10-25", "2026-10-23"
BARS = 252 * 390


def main():
    ts, op, cl = bt.panel(("QQQ", "TQQQ", "BIL"), START10, END, "1min")
    D = engine.Data()
    w17 = agent17.build_weights(ts, op, cl)
    w21, _ = agent21.build_weights(ts, op, cl)
    w23, _ = agent23.build_weights(D)

    names = {
        "Agent 21 ratio-froth": w21,
        "Agent 17 first-hour": w17,
        "Agent 23 volume-stop": w23,
        "50/50 ratio + volume": 0.5 * w21 + 0.5 * w23,
        "50/50 ratio + first-hour": 0.5 * w21 + 0.5 * w17,
        "1/3 each": (w21 + w17 + w23) / 3.0,
    }
    for name, w in names.items():
        print(f"\n{name}")
        for label, start in (("10y", START10), ("5y", START5)):
            vals = []
            for slip in (1.0, 5.0, 10.0):
                s = bt.stats(fastbt.run(ts, op, cl, w, start, band=0.02,
                                        slippage_bps=slip), BARS)
                vals.append(f"{slip:.0f}bp {s['cagr']*100:.2f}/{s['max_drawdown']*100:.2f}")
            print(f"  {label}: " + "  ".join(vals))


if __name__ == "__main__":
    main()
