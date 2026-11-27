"""Feature-subset stability for the ML risk-off overlay."""
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
    names = list(f.columns)
    n = len(tsd)
    q = cd[:, 0]
    sma = pd.Series(q).rolling(165, min_periods=100).mean().to_numpy()
    base = q > sma

    def pos_from_p(p, qlo=0.2):
        thr = pd.Series(p).rolling(252, min_periods=60).quantile(qlo).shift(1).to_numpy()
        return base & ~(p < thr)

    def evaluate(pos, start, slip=1.0):
        w = np.zeros((n, 3)); w[:, 1] = pos.astype(float); w[:, 2] = 1 - pos
        r = bt.run(tsd, od, cd, w, start, band=0.02, slippage_bps=slip)
        return bt.stats(r, 252)

    groups = {
        "all38": names,
        "no_minute": [x for x in names if x not in
                      ("rv5_20", "overnight20", "intraday20", "gap", "intraday", "first30", "last30", "vwap_dist", "close_loc")],
        "compact12": ["q_r20", "q_r60", "sma50", "sma165", "rsi14", "dd252", "rv20", "rv_ratio",
                      "rv_pct", "t_r20", "overnight20", "intraday20"],
        "trend8": ["q_r20", "q_r60", "q_r120", "sma50", "sma165", "dd252", "rv20", "rsi14"],
        "minute9": ["rv5_20", "overnight20", "intraday20", "gap", "intraday", "first30", "last30",
                    "vwap_dist", "close_loc"],
        "vol6": ["rv10", "rv20", "rv60", "rv_ratio", "rv_pct", "rv5_20"],
    }
    for h in (10, 20):
        ft = np.full(n, np.nan); fb = np.full(n, np.nan)
        ft[:-(h + 1)] = np.log(od[h + 1:, 1] / od[1:-h, 1])
        fb[:-(h + 1)] = np.log(od[h + 1:, 2] / od[1:-h, 2])
        y = (ft > fb).astype(float); y[~np.isfinite(ft) | ~np.isfinite(fb)] = np.nan
        print(f"\n########## h={h} ##########")
        for label, cols in groups.items():
            idx = [names.index(c) for c in cols]
            p = walk_forward_daily(tsd, f.to_numpy()[:, idx], y, window=750, verbose=False, purge=h + 1)
            pos = pos_from_p(p, 0.2)
            s10 = evaluate(pos, "2017-01-03")
            s5 = evaluate(pos, "2021-10-25")
            print(f"  {label:10s} nfeat {len(idx):2d}: 10y {s10['cagr']*100:6.2f}/{s10['max_drawdown']*100:5.1f} "
                  f"sh{s10['sharpe']:4.2f} | 5y {s5['cagr']*100:6.2f}/{s5['max_drawdown']*100:5.1f} sh{s5['sharpe']:4.2f}", flush=True)


if __name__ == "__main__":
    main()
