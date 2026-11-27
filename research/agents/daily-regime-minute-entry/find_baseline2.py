"""Scan SMA lengths / details to locate README baseline 45.31%/58.71%."""
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, "research")
import bt

START10, START5, END = "2017-01-03", "2021-10-25", "2026-10-23"
ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), START10, END, "1D")
q = closes[:, 0]


def evaluate(reg, label):
    w = np.zeros((len(ts), 3))
    w[:, 1] = reg.astype(float)
    w[:, 2] = 1.0 - reg
    out = []
    for start in (START10, START5):
        r = bt.run(ts, opens, closes, w, start, band=0.02, slippage_bps=1.0)
        s = bt.stats(r, 252)
        out.append((s["cagr"] * 100, s["max_drawdown"] * 100, s["sharpe"], s["fills"]))
    print(f"{label:30s} 10y {out[0][0]:6.2f}%/{out[0][1]:5.2f}% sh{out[0][2]:.2f} f{out[0][3]:3d} | "
          f"5y {out[1][0]:6.2f}%/{out[1][1]:5.2f}% sh{out[1][2]:.2f}")


for n in (100, 120, 150, 165, 180, 200, 210, 250):
    sma = pd.Series(q).rolling(n).mean().to_numpy()
    reg = np.zeros(len(ts), bool)
    reg[1:] = q[:-1] > sma[:-1]
    evaluate(reg, f"SMA{n} prev close")
