"""Mandated 30/60-minute classifier: walk-forward accuracy and trading results."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(ROOT / "research" / "agents" / "ml-classifier"))
import bt  # noqa: E402
from explore import build_features  # noqa: E402
from experiments import walk_forward, direct_weights  # noqa: E402


def main():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), "2017-01-03", "2026-10-23", "5min")
    x, names = build_features(ts, o, c)
    n = len(ts)
    years = np.asarray([t.year for t in ts])
    i10, i5 = bt.start_index(ts, "2017-01-03"), bt.start_index(ts, "2021-10-25")
    b10 = bt.benchmark(c[i10:, 1], ts[i10:], 252 * 78)
    b5 = bt.benchmark(c[i5:, 1], ts[i5:], 252 * 78)
    print(f"bench 10y {b10['cagr']*100:.2f}/{b10['max_drawdown']*100:.2f} 5y {b5['cagr']*100:.2f}/{b5['max_drawdown']*100:.2f}", flush=True)
    for h in (6, 12):
        ft = np.zeros(n); fb = np.zeros(n)
        ft[:-h] = np.log(c[h:, 1] / c[:-h, 1])
        fb[:-h] = np.log(c[h:, 2] / c[:-h, 2])
        y = np.full(n, np.nan)
        y[:-h] = (ft[:-h] > fb[:-h]).astype(float)
        print(f"\n===== h={h} ({h*5} min) =====", flush=True)
        p, _ = walk_forward(ts, x, y, h, verbose=True)
        np.save(ROOT / "research" / "agents" / "ml-classifier" / f"p5_h{h}.npy", p)
        # accuracy / IC
        for yr in range(2017, 2027):
            m = (years == yr) & np.isfinite(p) & np.isfinite(y)
            if m.sum() == 0:
                continue
            ic = np.corrcoef(p[m], (ft - fb)[m])[0, 1]
            print(f"  {yr}: acc={((p[m]>.5)==(y[m]>.5)).mean():.4f} base={y[m].mean():.4f} ic={ic:+.4f}", flush=True)
        # decile
        ex = ft - fb
        m = np.isfinite(p) & np.isfinite(ex)
        dec = pd.qcut(pd.Series(p[m]), 10, labels=False, duplicates="drop")
        tab = pd.DataFrame({"d": dec, "ex": ex[m]}).groupby("d")["ex"].agg(["mean", "count"])
        print("  decile excess bp:", (tab["mean"] * 1e4).round(2).tolist(), flush=True)
        for enter, exit_, hold in [(0.55, 0.45, 12), (0.6, 0.4, 12), (0.55, 0.45, 78)]:
            w = direct_weights(ts, p, enter, exit_, hold)
            for start, b in (("2017-01-03", b10), ("2021-10-25", b5)):
                r = bt.run(ts, o, c, w, start, band=0.02, slippage_bps=1.0)
                s = bt.stats(r, 252 * 78)
                print(f"  rule e{enter}/x{exit_}/h{hold} {start}: CAGR {s['cagr']*100:6.2f} DD {s['max_drawdown']*100:5.1f} "
                      f"Sharpe {s['sharpe']:4.2f} fills {s['fills']:5d} turn {s['turnover']:6.0f} "
                      f"bench {b['cagr']*100:5.2f}/{b['max_drawdown']*100:5.2f}", flush=True)


if __name__ == "__main__":
    main()
