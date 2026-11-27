"""Evaluate trading rules on saved walk-forward probabilities."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(ROOT / "research" / "agents" / "ml-classifier"))
import bt  # noqa: E402
from experiments import direct_weights, daily_weights  # noqa: E402


def evaluate(ts, o, c, w, start, slip=1.0):
    r = bt.run(ts, o, c, w, start, band=0.02, slippage_bps=slip)
    s = bt.stats(r, 252 * 78)
    return r, s


def bench(ts, c, start):
    i = bt.start_index(ts, start)
    return bt.benchmark(c[i:, 1], ts[i:], 252 * 78)


def main():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), "2017-01-03", "2026-10-23", "5min")
    p = np.load(ROOT / "research" / "agents" / "ml-classifier" / "p_h6.npy")
    b10, b5 = bench(ts, c, "2017-01-03"), bench(ts, c, "2021-10-25")
    print(f"bench10 {b10['cagr']*100:.2f}/{b10['max_drawdown']*100:.2f}  bench5 {b5['cagr']*100:.2f}/{b5['max_drawdown']*100:.2f}", flush=True)

    rules = []
    for enter, exit_, hold in [(0.5, 0.5, 0), (0.52, 0.48, 6), (0.55, 0.45, 0),
                               (0.55, 0.45, 6), (0.55, 0.45, 12), (0.55, 0.45, 78),
                               (0.58, 0.42, 12), (0.60, 0.40, 12), (0.60, 0.40, 78)]:
        rules.append((f"direct e{enter} x{exit_} h{hold}", direct_weights(ts, p, enter, exit_, hold)))
    for kind, th in [("mean", 0.50), ("mean", 0.52), ("mean", 0.53), ("mean", 0.535),
                     ("last", 0.52), ("last", 0.535), ("last6", 0.52), ("last6", 0.535),
                     ("frac", 0.52), ("frac", 0.55)]:
        rules.append((f"daily {kind} {th}", daily_weights(ts, o, c, p, kind=kind, enter=th, exit=th - 0.01)))

    rows = []
    for name, w in rules:
        _, s10 = evaluate(ts, o, c, w, "2017-01-03")
        _, s5 = evaluate(ts, o, c, w, "2021-10-25")
        print(f"{name:26s} 10y {s10['cagr']*100:6.2f}/{s10['max_drawdown']*100:5.1f}/sh{s10['sharpe']:4.2f} "
              f"fills{s10['fills']:5d} turn{s10['turnover']:6.0f} exp{s10['exposure']*100:4.0f} | "
              f"5y {s5['cagr']*100:6.2f}/{s5['max_drawdown']*100:5.1f}/sh{s5['sharpe']:4.2f} "
              f"fills{s5['fills']:5d} turn{s5['turnover']:6.0f}", flush=True)
        rows.append((name, s10, s5, w))
    np.save(ROOT / "research" / "agents" / "ml-classifier" / "best_w.npy", rows[0][3])


if __name__ == "__main__":
    main()
