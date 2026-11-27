r"""Exact 1-minute validation of the GPU block-engine top candidates.

Run from the repo root:
    $env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
    python research/verification/gpu_top_validate.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(ROOT / "research" / "agents2" / "overnight-crash-filter"))
import bt  # noqa: E402
import lab  # noqa: E402

START10, START5, END = "2017-01-03", "2021-10-25", "2026-10-23"
BARS = 252 * 390

variants = {
    "GPU top: SMA165 b2 cap55 thr-.5 stop3": dict(sma=165, band=0.02, cap=0.55, thr=-0.005, stop=0.03),
    "GPU 2: SMA165 b2 cap35 thr-.5 stop3": dict(sma=165, band=0.02, cap=0.35, thr=-0.005, stop=0.03),
    "GPU 3: SMA165 b2 cap55 thr-.5 stop4": dict(sma=165, band=0.02, cap=0.55, thr=-0.005, stop=0.04),
    "GPU Calmar: SMA135 b1 cap35 thr0 stop4": dict(sma=135, band=0.01, cap=0.35, thr=0.0, stop=0.04),
    "Agent 17 ref: SMA165 b2 cap35 thr-.5 stop4": dict(sma=165, band=0.02, cap=0.35, thr=-0.005, stop=0.04),
}


def main():
    ts, op, cl = bt.panel(("QQQ", "TQQQ", "BIL"), START10, END, "1min")
    d = lab.Days(ts, op, cl)
    for name, p in variants.items():
        gate = d.gate(n=p["sma"], band=p["band"])
        w = lab.build_weights(d, base="signal", m=60, gate=gate,
                              vol_max=p["cap"], stop=p["stop"],
                              signal_thr=p["thr"])
        print(f"\n{name}")
        for label, start in (("10y", START10), ("5y", START5)):
            out = []
            for slip in (1.0, 5.0):
                s = bt.stats(bt.run(ts, op, cl, w, start, band=0.02,
                                    slippage_bps=slip), BARS)
                out.append(f"{slip:.0f}bp {s['cagr']*100:.2f}/{s['max_drawdown']*100:.2f}")
            print(f"  {label}: " + "  ".join(out))


if __name__ == "__main__":
    main()
