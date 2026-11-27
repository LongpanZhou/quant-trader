import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402
import fastbt  # noqa: E402

rng = np.random.default_rng(7)
for label, weights in (
    ("random dense", None),
    ("piecewise", None),
):
    n = 20_000
    opens = 100 + np.cumsum(rng.normal(0, 0.05, (n, 3)), axis=0)
    closes = opens + rng.normal(0, 0.03, (n, 3))
    if label == "random dense":
        w = rng.random((n, 3))
        w /= w.sum(axis=1, keepdims=True)
    else:
        w = np.zeros((n, 3))
        for a in range(0, n, 500):
            b = min(a + 500, n)
            j = 1 if (a // 500) % 2 == 0 else 2
            w[a:b, j] = 1.0
    a = bt.simulate(np.arange(n), opens, closes, w, band=0.02, slippage_bps=1.0)
    b = fastbt.fast_sim(opens, closes, w, band=0.02, slippage_bps=1.0)
    print(label, "equity diff", np.nanmax(np.abs(a["equity"] - b["equity"])),
          "fills", a["fills"], b["fills"], "turnover", a["turnover"], b["turnover"])
