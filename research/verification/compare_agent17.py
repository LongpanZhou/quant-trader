r"""Agent 17 (first-hour + crash filter) vs Agent 1 (round-1 winner).

Re-builds both weight paths from their published rules and compares:
  * 10y/5y CAGR, DD, Sharpe at 1/5/10 bp;
  * rolling 3-year windows vs TQQQ;
  * rolling 3-year head-to-head, Agent 17 vs Agent 1.

Run from the repo root:

    $env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
    python research/verification/compare_agent17.py
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


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


agent17 = load_module(
    "agent17_strategy",
    ROOT / "research" / "agents2" / "overnight-crash-filter" / "strategy.py",
)


def run(ts, opens, closes, weights, start, slip):
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


def main():
    ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), START10, END, "1min")
    w1, _ = weights_agent1(ts, opens, closes)
    w17 = agent17.build_weights(ts, opens, closes)
    print(f"panel {len(ts):,} bars")

    names = {"Agent 1 minute-stop": w1, "Agent 17 first-hour": w17}
    for name, w in names.items():
        print(f"\n{name}")
        for label, start in (("10y", START10), ("5y", START5)):
            for slip in (1.0, 5.0, 10.0):
                _, s = run(ts, opens, closes, w, start, slip)
                print(f"  {label} {slip:4.0f}bp  CAGR {s['cagr']*100:6.2f}%  "
                      f"DD {s['max_drawdown']*100:5.2f}%  Sharpe {s['sharpe']:4.2f}  "
                      f"fills {s['fills']:4.0f}")

    r1, _ = run(ts, opens, closes, w1, START10, 1.0)
    r17, _ = run(ts, opens, closes, w17, START10, 1.0)
    i = bt.start_index(ts, START10)
    dts, e1 = daily(ts[i:], r1["equity"])
    _, e17 = daily(ts[i:], r17["equity"])
    _, tq = daily(ts[i:], closes[i:, 1])

    rows = []
    for start in pd.date_range("2017-01-03", "2023-10-01", freq="QS"):
        a = int(dts.searchsorted(start))
        b = int(dts.searchsorted(start + pd.DateOffset(years=3)))
        if a >= b or b > len(dts) or b - a < 500:
            continue
        c1, d1 = cagr_dd(e1, a, b)
        c17, d17 = cagr_dd(e17, a, b)
        ct, dt = cagr_dd(tq, a, b)
        rows.append((c1, d1, c17, d17, ct, dt))

    def wins(idx, other_idx, tq_idx=None):
        return sum(r[idx] > r[other_idx] for r in rows)

    print(f"\nrolling 3y: {len(rows)} windows")
    print(f"  Agent 1 vs TQQQ: return {sum(c1 > ct for c1, _, _, _, ct, _ in rows)}/{len(rows)}, "
          f"DD {sum(d1 < dt for _, d1, _, _, _, dt in rows)}/{len(rows)}")
    print(f"  Agent 17 vs TQQQ: return {sum(c17 > ct for _, _, c17, _, ct, _ in rows)}/{len(rows)}, "
          f"DD {sum(d17 < dt for _, _, _, d17, _, dt in rows)}/{len(rows)}")
    print(f"  Agent 17 vs Agent 1: return {sum(r[2] > r[0] for r in rows)}/{len(rows)}, "
          f"DD {sum(r[3] < r[1] for r in rows)}/{len(rows)}, "
          f"both {sum(r[2] > r[0] and r[3] < r[1] for r in rows)}/{len(rows)}")
    print(f"  min 3y CAGR: Agent 1 {min(r[0] for r in rows)*100:.1f}%, "
          f"Agent 17 {min(r[2] for r in rows)*100:.1f}%")
    print(f"  max 3y DD:   Agent 1 {max(r[1] for r in rows)*100:.1f}%, "
          f"Agent 17 {max(r[3] for r in rows)*100:.1f}%")


if __name__ == "__main__":
    main()
