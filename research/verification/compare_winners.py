r"""Head-to-head: Agent 1 minute-stop leader vs Agent 8 ensemble.

Both are re-built from their published rules and run through the same harness.
The comparison reports the two headline windows plus rolling 3-year windows.

Run from the repo root:

    $env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
    python research/verification/compare_winners.py
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
import bt  # noqa: E402
from verify_agent1 import build_weights as weights_agent1  # noqa: E402

START10, START5, END = "2017-01-03", "2021-10-25", "2026-10-23"
BARS_PER_YEAR = 252 * 390

spec = importlib.util.spec_from_file_location(
    "ensemble_strategy",
    ROOT / "research" / "agents" / "ensemble-signals" / "strategy.py",
)
ensemble = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(ensemble)


def evaluate(ts, opens, closes, weights, start, slip):
    r = bt.run(ts, opens, closes, weights, start, band=0.02, slippage_bps=slip)
    return r, bt.stats(r, BARS_PER_YEAR)


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


def rolling(ts, equity, tqqq):
    dts, deq = daily(ts, equity)
    _, dtq = daily(ts, tqqq)
    rows = []
    for start in pd.date_range("2017-01-03", "2023-10-01", freq="QS"):
        i = int(dts.searchsorted(start))
        j = int(dts.searchsorted(start + pd.DateOffset(years=3)))
        if i >= j or j > len(dts) or j - i < 500:
            continue
        cs, ds = cagr_dd(deq, i, j)
        cb, db = cagr_dd(dtq, i, j)
        rows.append((cs, ds, cb, db))
    return rows


def main():
    ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), START10, END, "1min")
    w1, _ = weights_agent1(ts, opens, closes)
    w8 = ensemble.build_weights(ts, opens, closes)
    print(f"panel {len(ts):,} bars")

    names = {"Agent 1 minute-stop": w1, "Agent 8 ensemble": w8}
    for name, w in names.items():
        print(f"\n{name}")
        for label, start in (("10y", START10), ("5y", START5)):
            for slip in (1.0, 5.0):
                r, s = evaluate(ts, opens, closes, w, start, slip)
                print(f"  {label} {slip:3.0f}bp  CAGR {s['cagr']*100:6.2f}%  "
                      f"DD {s['max_drawdown']*100:5.2f}%  Sharpe {s['sharpe']:4.2f}  "
                      f"fills {s['fills']:4.0f}")

    for name, w in names.items():
        r, _ = evaluate(ts, opens, closes, w, START10, 1.0)
        i = bt.start_index(ts, START10)
        rows = rolling(ts[i:], r["equity"], closes[i:, 1])
        ret = sum(cs > cb for cs, _, cb, _ in rows)
        dd = sum(ds < db for _, ds, _, db in rows)
        both = sum(cs > cb and ds < db for cs, ds, cb, db in rows)
        print(f"{name:22s} rolling 3y: return {ret}/{len(rows)}  DD {dd}/{len(rows)}  both {both}/{len(rows)}")


if __name__ == "__main__":
    main()
