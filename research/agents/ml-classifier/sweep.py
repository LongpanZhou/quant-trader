"""Hyperparameter stability sweep for the ensemble overlay."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(ROOT / "research" / "agents" / "ml-classifier"))
import bt  # noqa: E402
from daily_ml import build_daily_features, walk_forward_daily  # noqa: E402


def main():
    ts5, o5, c5 = bt.panel(("QQQ", "TQQQ", "BIL"), "2017-01-03", "2026-10-23", "5min")
    tsd, od, cd = bt.panel(("QQQ", "TQQQ", "BIL"), "2017-01-03", "2026-10-23", "1D")
    f = build_daily_features(ts5, o5, c5, tsd, od, cd)
    x = f.to_numpy()
    n = len(tsd)
    q = cd[:, 0]
    sma = pd.Series(q).rolling(165, min_periods=100).mean().to_numpy()
    base = q > sma

    def evaluate(pos):
        w = np.zeros((n, 3)); w[:, 1] = pos.astype(float); w[:, 2] = 1 - pos
        out = []
        for start in ("2017-01-03", "2021-10-25"):
            r = bt.run(tsd, od, cd, w, start, band=0.02, slippage_bps=1.0)
            out.append(bt.stats(r, 252))
        return out

    for window in (500, 750, 1000, None):
        for lam in (3.0, 10.0, 30.0, 100.0):
            ps = {}
            for h in (5, 10, 20):
                ft = np.full(n, np.nan); fb = np.full(n, np.nan)
                ft[:-(h + 1)] = np.log(od[h + 1:, 1] / od[1:-h, 1])
                fb[:-(h + 1)] = np.log(od[h + 1:, 2] / od[1:-h, 2])
                y = (ft > fb).astype(float); y[~np.isfinite(ft) | ~np.isfinite(fb)] = np.nan
                ps[h] = walk_forward_daily(tsd, x, y, lam=lam, window=window, verbose=False, purge=h + 1)
            R = np.column_stack([pd.Series(ps[h]).rolling(252, min_periods=60).rank(pct=True).to_numpy() for h in (5, 10, 20)])
            rm = np.nanmean(R, axis=1)
            for qlo in (0.15, 0.2, 0.25):
                pos = base & ~(rm < qlo)
                s10, s5 = evaluate(pos)
                print(f"w{str(window):4s} lam{lam:5.0f} q{qlo:.2f}: 10y {s10['cagr']*100:6.2f}/{s10['max_drawdown']*100:5.1f} "
                      f"sh{s10['sharpe']:4.2f} | 5y {s5['cagr']*100:6.2f}/{s5['max_drawdown']*100:5.1f} sh{s5['sharpe']:4.2f}", flush=True)


if __name__ == "__main__":
    main()
