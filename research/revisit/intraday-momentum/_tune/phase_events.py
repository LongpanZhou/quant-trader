"""Event-level fwd-5 spreads (above-median minus below, bp) for each of the 5 rebalance phases, with permutation p."""
import numpy as np, pandas as pd
from common import *  # noqa
from vlib import feats
ts, o, c = panel()
a, b, on, idr, fh, q1 = feats(ts, o, c)
nd = len(a); rng = np.random.default_rng(1)
for col in ("sp", "fh", "ret5"):
    line = []
    for off in range(5):
        xs, ys = [], []
        for r in range(9 + off, nd - 1, 5):
            win = slice(r - 4, r + 1)
            x = {"sp": (on[win] - idr[win]).sum(), "fh": fh[win].sum(), "ret5": q1[r] / q1[r - 5] - 1}[col]
            e = min(r + 5, nd - 1)
            xs.append(x); ys.append(c[b[e] - 1, 0] / o[a[r + 1], 0] - 1)
        xs = np.array(xs); ys = np.array(ys)
        m = np.array([xs[i] > np.median(xs[max(0, i - 25): i + 1]) for i in range(len(xs))])[12:]
        y = ys[12:]
        obs = y[m].mean() - y[~m].mean()
        p = np.mean([(lambda mm: y[mm].mean() - y[~mm].mean())(rng.permutation(m)) <= obs for _ in range(3000)])
        line.append(f"ph{off}: {obs*1e4:7.1f} (p_low={p:.3f})")
    print(f"{col:5s} " + "  ".join(line))
