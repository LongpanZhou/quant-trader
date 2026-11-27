r"""Rolling 3-year consistency for the ratio-froth blends.

Run from the repo root:
    $env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
    python research/verification/rolling_ratio_blend.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

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


agent17 = load("a17", ROOT / "research" / "agents2" / "overnight-crash-filter" / "strategy.py")
agent21 = load("a21", ROOT / "research" / "agents2" / "ratio-pairs" / "strategy.py")

START10, END = "2017-01-03", "2026-10-23"
BARS = 252 * 390


def daily(ts, eq):
    s = pd.Series(eq, index=ts)
    d = s.groupby(s.index.date).last()
    return pd.DatetimeIndex(pd.to_datetime(d.index)), d.to_numpy(float)


def cagr_dd(v, i, j):
    x = v[i:j]
    years = (j - i) / 252.0
    cagr = (x[-1] / x[0]) ** (1.0 / years) - 1.0
    peak = np.maximum.accumulate(x)
    return float(cagr), float(-(x / peak - 1.0).min())


def main():
    ts, op, cl = bt.panel(("QQQ", "TQQQ", "BIL"), START10, END, "1min")
    D = engine.Data()
    w17 = agent17.build_weights(ts, op, cl)
    w21, _ = agent21.build_weights(ts, op, cl)
    w23, _ = agent23.build_weights(D)
    names = {
        "ratio": w21,
        "ratio+first": 0.5 * w21 + 0.5 * w17,
        "ratio+volume": 0.5 * w21 + 0.5 * w23,
        "1/3 each": (w21 + w17 + w23) / 3.0,
    }
    curves = {}
    for name, w in names.items():
        r = fastbt.run(ts, op, cl, w, START10, band=0.02, slippage_bps=1.0)
        curves[name] = daily(r["ts"], r["equity"])
    dts, tq = daily(ts[bt.start_index(ts, START10):], cl[bt.start_index(ts, START10):, 1])
    rows = []
    for start in pd.date_range("2017-01-03", "2023-10-01", freq="QS"):
        a = int(dts.searchsorted(start))
        b = int(dts.searchsorted(start + pd.DateOffset(years=3)))
        if a >= b or b > len(dts) or b - a < 500:
            continue
        vals = {name: cagr_dd(eq, a, b) for name, (_, eq) in curves.items()}
        ct, dt = cagr_dd(tq, a, b)
        rows.append((vals, ct, dt))
    print(f"rolling 3y: {len(rows)} windows")
    for name in names:
        cw = sum(v[name][0] > ct for v, ct, _ in rows)
        dw = sum(v[name][1] < dt for v, _, dt in rows)
        both = sum(v[name][0] > ct and v[name][1] < dt for v, ct, dt in rows)
        print(f"  {name:14s} vs TQQQ: return {cw}/{len(rows)}, DD {dw}/{len(rows)}, both {both}/{len(rows)}")
    base = "ratio"
    for name in names:
        if name == base:
            continue
        cw = sum(v[name][0] > v[base][0] for v, _, _ in rows)
        dw = sum(v[name][1] < v[base][1] for v, _, _ in rows)
        print(f"  {name:14s} vs ratio: return {cw}/{len(rows)}, DD {dw}/{len(rows)}")


if __name__ == "__main__":
    main()
