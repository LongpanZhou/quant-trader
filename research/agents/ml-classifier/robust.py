"""Robustness: yearly baseline, 5bp, parameter neighborhood, placebo exits."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(ROOT / "research" / "agents" / "ml-classifier"))
import bt  # noqa: E402


def weights_from_pos(pos):
    w = np.zeros((len(pos), 3))
    w[:, 1] = pos.astype(float)
    w[:, 2] = 1.0 - pos
    return w


def run(ts, o, c, pos, start, slip=1.0):
    r = bt.run(ts, o, c, weights_from_pos(pos), start, band=0.02, slippage_bps=slip)
    return r, bt.stats(r, 252)


def base_pos(ts, c):
    q = c[:, 0]
    sma = pd.Series(q).rolling(165, min_periods=100).mean().to_numpy()
    return (q > sma)


def overlay(p, qlo, base):
    thr = pd.Series(p).rolling(252, min_periods=60).quantile(qlo).shift(1).to_numpy()
    return base & ~(p < thr)


def main():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), "2017-01-03", "2026-10-23", "1D")
    n = len(ts)
    base = base_pos(ts, c)
    i10 = bt.start_index(ts, "2017-01-03")
    b10 = bt.benchmark(c[i10:, 1], ts[i10:], 252)
    b5 = bt.benchmark(c[bt.start_index(ts, "2021-10-25"):, 1], ts[bt.start_index(ts, "2021-10-25"):], 252)

    # baseline yearly
    rb, sb = run(ts, o, c, base, "2017-01-03")
    yb = bt.yearly(rb["ts"], rb["equity"], c[i10:i10 + len(rb["ts"]), 1])
    print("baseline yearly:", {y: round(v["strategy"] * 100, 1) for y, v in yb.items()})
    print(f"baseline 10y {sb['cagr']*100:.2f}/{sb['max_drawdown']*100:.2f}", flush=True)

    configs = [(5, 750, 0.1), (5, 750, 0.2), (5, 750, 0.3),
               (10, 750, 0.1), (10, 750, 0.2), (10, 750, 0.3),
               (20, 750, 0.1), (20, 750, 0.2), (20, 750, 0.3),
               (5, None, 0.2), (10, None, 0.2), (20, None, 0.2)]
    store = {}
    print("\nparam neighborhood (1bp / 5bp):")
    for h, win, qlo in configs:
        p = np.load(ROOT / "research" / "agents" / "ml-classifier" / f"pd_h{h}_w{win}.npy")
        pos = overlay(p, qlo, base)
        _, s10 = run(ts, o, c, pos, "2017-01-03", 1.0)
        _, s5 = run(ts, o, c, pos, "2021-10-25", 1.0)
        _, s10b = run(ts, o, c, pos, "2017-01-03", 5.0)
        _, s5b = run(ts, o, c, pos, "2021-10-25", 5.0)
        print(f" h{h:2d} w{str(win):4s} q{qlo:.1f}: 10y {s10['cagr']*100:6.2f}/{s10['max_drawdown']*100:5.1f} "
              f"sh{s10['sharpe']:4.2f} 5y {s5['cagr']*100:6.2f}/{s5['max_drawdown']*100:5.1f} sh{s5['sharpe']:4.2f} | "
              f"5bp {s10b['cagr']*100:6.2f} / {s5b['cagr']*100:6.2f}", flush=True)
        store[(h, win, qlo)] = pos

    # placebo + inverted for chosen configs
    rng = np.random.default_rng(7)
    print("\nplacebo (random exits at same rate) / inverted:")
    for h, win, qlo in [(5, 750, 0.2), (10, 750, 0.2), (20, 750, 0.2)]:
        p = np.load(ROOT / "research" / "agents" / "ml-classifier" / f"pd_h{h}_w{win}.npy")
        pos = store[(h, win, qlo)]
        # inverted: exit when p is HIGH (top q)
        thr_hi = pd.Series(p).rolling(252, min_periods=60).quantile(1 - qlo).shift(1).to_numpy()
        inv = base & ~(p > thr_hi)
        _, si = run(ts, o, c, inv, "2017-01-03")
        print(f" h{h} q{qlo} inverted: {si['cagr']*100:6.2f}/{si['max_drawdown']*100:5.1f}", flush=True)
        cagrs = []
        for _ in range(200):
            pr = rng.random(n)
            posr = overlay(pr, qlo, base)
            _, sr = run(ts, o, c, posr, "2017-01-03")
            cagrs.append(sr["cagr"])
        cagrs = np.array(cagrs)
        _, sm = run(ts, o, c, pos, "2017-01-03")
        pct = (cagrs < sm["cagr"]).mean()
        print(f"   ML CAGR {sm['cagr']*100:.1f}%  placebo mean {cagrs.mean()*100:.1f}% "
              f"p5 {np.percentile(cagrs,5)*100:.1f}% p95 {np.percentile(cagrs,95)*100:.1f}% "
              f"percentile {pct*100:.1f}%", flush=True)


if __name__ == "__main__":
    main()
