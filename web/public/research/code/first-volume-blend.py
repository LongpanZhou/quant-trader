r"""Blend Agent 17 (first-hour) and Agent 23 (volume-armed stop).

Tests a simple 50/50 blend and an inverse-vol blend against both parents,
TQQQ, and the round-1 winner.

Run from the repo root:

    $env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
    python research/verification/blend_17_23.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(ROOT / "research" / "verification"))
sys.path.insert(0, str(ROOT / "research" / "agents2" / "volume-orderflow"))
import bt  # noqa: E402
from verify_agent1 import build_weights as weights_agent1  # noqa: E402


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


agent17 = load("agent17", ROOT / "research" / "agents2" / "overnight-crash-filter" / "strategy.py")
import engine  # noqa: E402
import strategy as agent23  # noqa: E402

START10, START5, END = "2017-01-03", "2021-10-25", "2026-10-23"
BARS = 252 * 390


def run(ts, op, cl, w, start, slip):
    r = bt.run(ts, op, cl, w, start, band=0.02, slippage_bps=slip)
    return bt.stats(r, BARS)


def daily(ts, values):
    s = pd.Series(values, index=ts)
    d = s.groupby(s.index.date).last()
    return pd.DatetimeIndex(pd.to_datetime(d.index)), d.to_numpy(dtype=float)


def cagr_dd(v, i, j):
    x = v[i:j]
    years = (j - i) / 252.0
    cagr = (x[-1] / x[0]) ** (1.0 / years) - 1.0
    peak = np.maximum.accumulate(x)
    return float(cagr), float(-(x / peak - 1.0).min())


def main():
    D = engine.Data()
    ts, op, cl = D.ts, D.op, D.cl
    w17 = agent17.build_weights(ts, op, cl)
    w23, _ = agent23.build_weights(D)
    w1, _ = weights_agent1(ts, op, cl)
    w50 = 0.5 * w17 + 0.5 * w23

    # Causal inverse-vol blend: trailing 20-day vol of each sleeve's daily
    # returns, shifted one day, then normalised.
    def sleeve_vol(w):
        r = bt.run(ts, op, cl, w, START10, band=0.02, slippage_bps=1.0)
        dts, eq = daily(ts[bt.start_index(ts, START10):], r["equity"])
        ret = pd.Series(np.diff(eq) / eq[:-1], index=dts[1:])
        return ret.rolling(20).std().shift(1)

    v17, v23 = sleeve_vol(w17), sleeve_vol(w23)
    inv = pd.DataFrame({"a": 1.0 / v17, "b": 1.0 / v23}).fillna(0.0)
    inv = inv.div(inv.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.5)
    alpha_by_day = pd.Series(inv["a"].to_numpy(), index=pd.to_datetime(inv.index).date)
    bar_dates = np.array([t.date() for t in ts])
    alpha = pd.Series(bar_dates).map(alpha_by_day).ffill().bfill().to_numpy()
    wv = alpha[:, None] * w17 + (1.0 - alpha[:, None]) * w23

    names = {
        "Agent 1 winner": w1,
        "Agent 17 first-hour": w17,
        "Agent 23 volume-stop": w23,
        "50/50 blend": w50,
        "inverse-vol blend": wv,
    }
    for name, w in names.items():
        print(f"\n{name}")
        for label, start in (("10y", START10), ("5y", START5)):
            vals = []
            for slip in (1.0, 5.0, 10.0):
                s = run(ts, op, cl, w, start, slip)
                vals.append(f"{slip:.0f}bp {s['cagr']*100:.2f}/{s['max_drawdown']*100:.2f}")
            print(f"  {label}: " + "  ".join(vals))

    # Rolling 3y for the 50/50 blend vs TQQQ, and vs each parent.
    i = bt.start_index(ts, START10)
    curves = {}
    for name, w in names.items():
        r = bt.run(ts, op, cl, w, START10, band=0.02, slippage_bps=1.0)
        dts, eq = daily(ts[i:], r["equity"])
        curves[name] = (dts, eq)
    dts, tq = daily(ts[i:], cl[i:, 1])
    rows = []
    for start in pd.date_range("2017-01-03", "2023-10-01", freq="QS"):
        a = int(dts.searchsorted(start))
        b = int(dts.searchsorted(start + pd.DateOffset(years=3)))
        if a >= b or b > len(dts) or b - a < 500:
            continue
        vals = {name: cagr_dd(eq, a, b) for name, (_, eq) in curves.items()}
        ct, dt = cagr_dd(tq, a, b)
        rows.append((vals, ct, dt))
    print(f"\nrolling 3y ({len(rows)} windows)")
    for name in ("Agent 17 first-hour", "Agent 23 volume-stop", "50/50 blend", "inverse-vol blend"):
        cw = sum(v[name][0] > ct for v, ct, _ in rows)
        dw = sum(v[name][1] < dt for v, _, dt in rows)
        print(f"  {name:22s} vs TQQQ: return {cw}/{len(rows)}, DD {dw}/{len(rows)}")
    for name in ("50/50 blend", "inverse-vol blend"):
        c17 = sum(v[name][0] > v["Agent 17 first-hour"][0] for v, _, _ in rows)
        d17 = sum(v[name][1] < v["Agent 17 first-hour"][1] for v, _, _ in rows)
        c23 = sum(v[name][0] > v["Agent 23 volume-stop"][0] for v, _, _ in rows)
        d23 = sum(v[name][1] < v["Agent 23 volume-stop"][1] for v, _, _ in rows)
        print(f"  {name:22s} vs 17: return {c17}/{len(rows)}, DD {d17}/{len(rows)}; "
              f"vs 23: return {c23}/{len(rows)}, DD {d23}/{len(rows)}")


if __name__ == "__main__":
    main()
