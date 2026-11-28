"""Development-only diagnostics: AUC/IC of the no-long-MA ML direction models.

PRE-PAUSE EXPLORATORY PROTOTYPE: diagnostics for the rejected stripped-base
approach, not the final strategy.  See `strategy.py` for the regime-cluster
rebuild.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(ROOT / "research" / "revisit" / "ml-classifier"))
import bt  # noqa: E402
from dev_explore import build_features, make_labels, walk_forward  # noqa: E402


def auc(y, p):
    y = np.asarray(y); p = np.asarray(p)
    ok = np.isfinite(y) & np.isfinite(p)
    y, p = y[ok], p[ok]
    n1 = y.sum(); n0 = len(y) - n1
    if n0 == 0 or n1 == 0:
        return np.nan
    r = pd.Series(p).rank().to_numpy()
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


def main():
    ts5, o5, c5 = bt.panel(("QQQ", "TQQQ", "BIL"), "2016-01-04", "2023-12-29", "5min")
    tsd, od, cd = bt.panel(("QQQ", "TQQQ", "BIL"), "2016-01-04", "2023-12-29", "1D")
    f = build_features(ts5, o5, c5, tsd, od, cd)
    x = f.to_numpy()
    yrs = np.asarray([t.year for t in tsd])
    for h in (5, 10, 20):
        y = make_labels(od, h)
        p = walk_forward(tsd, x, y, h)
        ft = np.full(len(od), np.nan); fb = np.full(len(od), np.nan)
        ft[:-(h + 1)] = np.log(od[h + 1:, 1] / od[1:-h, 1])
        fb[:-(h + 1)] = np.log(od[h + 1:, 2] / od[1:-h, 2])
        ex = ft - fb
        print(f"\n=== h={h} ===")
        for yr in range(2017, 2024):
            m = (yrs == yr) & np.isfinite(p) & np.isfinite(y)
            if m.sum() == 0:
                continue
            ic = np.corrcoef(p[m], ex[m])[0, 1]
            print(f"  {yr}: n={m.sum():3d} auc={auc(y[m], p[m]):.3f} "
                  f"acc={np.mean((p[m] > .5) == (y[m] > .5)):.3f} base={y[m].mean():.3f} "
                  f"ic={ic:+.4f}", flush=True)
        m = np.isfinite(p) & np.isfinite(ex)
        dec = pd.qcut(pd.Series(p[m]), 10, labels=False, duplicates="drop")
        tab = pd.DataFrame({"d": dec, "ex": ex[m]}).groupby("d")["ex"].agg(["mean", "count"])
        print("  decile excess bp:", (tab["mean"] * 1e4).round(2).tolist(), flush=True)


if __name__ == "__main__":
    main()
