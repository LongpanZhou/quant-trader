"""Evaluate daily walk-forward classifier probabilities as trading signals."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(ROOT / "research" / "agents" / "ml-classifier"))
import bt  # noqa: E402


def stats(ts, o, c, w, start, slip=1.0):
    r = bt.run(ts, o, c, w, start, band=0.02, slippage_bps=slip)
    return r, bt.stats(r, 252)


def show(label, ts, o, c, w, b10, b5, slips=(1.0,)):
    out = []
    for slip in slips:
        _, s10 = stats(ts, o, c, w, "2017-01-03", slip)
        _, s5 = stats(ts, o, c, w, "2021-10-25", slip)
        print(f"{label:38s} {slip:3.1f}bp 10y {s10['cagr']*100:6.2f}/{s10['max_drawdown']*100:5.1f}/sh{s10['sharpe']:4.2f} "
              f"fills{s10['fills']:4d} turn{s10['turnover']:5.0f} | 5y {s5['cagr']*100:6.2f}/{s5['max_drawdown']*100:5.1f}/sh{s5['sharpe']:4.2f} "
              f"fills{s5['fills']:4d} turn{s5['turnover']:5.0f}", flush=True)
        out.append((s10, s5))
    return out


def main():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), "2017-01-03", "2026-10-23", "1D")
    n = len(ts)
    i10, i5 = bt.start_index(ts, "2017-01-03"), bt.start_index(ts, "2021-10-25")
    b10 = bt.benchmark(c[i10:, 1], ts[i10:], 252)
    b5 = bt.benchmark(c[i5:, 1], ts[i5:], 252)
    print(f"bench 10y {b10['cagr']*100:.2f}/{b10['max_drawdown']*100:.2f} 5y {b5['cagr']*100:.2f}/{b5['max_drawdown']*100:.2f}", flush=True)

    q = c[:, 0]
    sma = pd.Series(q).rolling(165, min_periods=100).mean().to_numpy()
    base = (q > sma).astype(float)
    wbase = np.zeros((n, 3)); wbase[:, 1] = base; wbase[:, 2] = 1 - base
    print("--- baseline ---", flush=True)
    show("SMA165", ts, o, c, wbase, b10, b5)

    for h in (5, 10, 20):
        for win in (None, 750):
            fn = ROOT / "research" / "agents" / "ml-classifier" / f"pd_h{h}_w{win}.npy"
            if not fn.exists():
                continue
            p = np.load(fn)
            ps = pd.Series(p)
            print(f"\n=== h={h} window={win}  finite={np.isfinite(p).sum()} ===", flush=True)
            # AUC by year with finite y not available here; just strategy results
            for qq in (0.4, 0.5, 0.6, 0.7):
                thr = ps.rolling(252, min_periods=60).quantile(qq).shift(1)
                pos = (ps > thr).to_numpy().astype(float)
                pos[~np.isfinite(pos)] = 0
                w = np.zeros((n, 3)); w[:, 1] = pos; w[:, 2] = 1 - pos
                show(f"ML q{qq}", ts, o, c, w, b10, b5)
            # blend: base AND (not ml_bear), i.e. exit base when p in bottom 20%
            for qlo in (0.1, 0.2, 0.3):
                thr = ps.rolling(252, min_periods=60).quantile(qlo).shift(1).to_numpy()
                bear = (p < thr)
                pos = (base > 0) & ~bear
                w = np.zeros((n, 3)); w[:, 1] = pos.astype(float); w[:, 2] = 1 - pos
                show(f"SMA & !MLbear q{qlo}", ts, o, c, w, b10, b5)
            # blend: base OR ml_bull
            for qhi in (0.8, 0.9):
                thr = ps.rolling(252, min_periods=60).quantile(qhi).shift(1).to_numpy()
                bull = (p > thr)
                pos = (base > 0) | bull
                w = np.zeros((n, 3)); w[:, 1] = pos.astype(float); w[:, 2] = 1 - pos
                show(f"SMA | MLbull q{qhi}", ts, o, c, w, b10, b5)


if __name__ == "__main__":
    main()
