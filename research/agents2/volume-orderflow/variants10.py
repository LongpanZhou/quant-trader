"""Step 19: component ablation, yearly returns and rolling 3y for the candidate."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine  # noqa: E402
from arming_grid import winner_vol  # noqa: E402

pd.set_option("display.width", 240)


def main():
    D = engine.Data()
    base, _ = engine.winner_weights(D)
    b = engine.evaluate(D, base, "winner")
    W = {k: (v["cagr"], v["max_drawdown"]) for k, v in b.items()}

    print("\n-- ablation")
    for lab, hi, q in (("quiet only (no OR)", 99, 0.9),
                       ("OR only (no quiet)", 1.5, 0.0),
                       ("both", 1.5, 0.9),
                       ("both, hi=1.3", 1.3, 0.9),
                       ("both, hi=1.8", 1.8, 0.9)):
        w, n = winner_vol(D, hi=hi, quiet=q)
        r = engine.evaluate(D, w, f"{lab} (n={n})")

    # full detail for the candidate
    w, n = winner_vol(D, hi=1.5, quiet=0.9)
    print("\n-- candidate: yearly returns")
    for slip in (1.0, 5.0, 10.0):
        out = engine.evaluate(D, w)
        print(f"\n  cost {slip}bp")
    for label in ("10y", "5y"):
        r = engine.evaluate(D, w, "", slip=1.0)[label]
        yr = r["yearly"] if "yearly" in r else None
    r10 = engine.evaluate(D, w, "")["10y"]
    print("\n  year   strategy    TQQQ")
    for y, v in r10["yearly"].items():
        print(f"  {y}  {v['strategy']*100:8.2f}%  {v['benchmark']*100:8.2f}%")

    print("\n-- rolling 3y (candidate)")
    for row in engine.rolling3y(D, w):
        print(f"  {row['start']}..{row['end']}  strat {row['cagr']*100:6.2f}%/"
              f"{row['dd']*100:5.2f}%   tqqq {row['bench_cagr']*100:6.2f}%/"
              f"{row['bench_dd']*100:5.2f}%")


if __name__ == "__main__":
    main()
