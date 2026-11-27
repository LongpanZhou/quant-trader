"""Causal gate / threshold grid for the last-hour continuation overlay.

Gate uses only information visible at 15:00: QQQ's 15:00 price vs the 20/50-day
MA computed from prior daily closes.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/agents2/intraday-seasonality/grid2.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import lib  # noqa: E402

OUT = Path(__file__).resolve().parent
IS_END = "2022-01-01"


def main():
    ts, opens, closes = lib.load_panel()
    cal = lib.calendar(ts)
    first, last = cal["first"], cal["last"]
    w_base, _ = lib.build_base(ts, opens, closes)

    i1500 = lib.time_index(ts, first, last, 15, 0)
    q_open = opens[first, 0]
    q_1500 = closes[i1500, 0]
    sig = q_1500 / q_open - 1.0
    dc = closes[last, 0]

    mas = {}
    for n in (10, 20, 50, 100):
        m = pd.Series(dc).rolling(n).mean().to_numpy()
        mas[n] = np.r_[np.nan, m[:-1]]          # through the previous close
    on, _, _ = lib.regime_on(ts, closes)

    rows = []

    def ev(name, w, note, slip=1.0):
        r = lib.simulate(ts, opens, closes, w, slip)
        row = {"name": name, "note": note, "fills": r["fills"]}
        for label, start, end in (("10y", lib.START10, None), ("5y", lib.START5, None),
                                  ("IS", lib.START10, IS_END), ("OOS", IS_END, None)):
            s = lib.window(r, ts, start, end)
            row[f"{label}_cagr"] = s["cagr"]
            row[f"{label}_dd"] = s["max_drawdown"]
        return row

    rows.append(ev("BASE", w_base, "winner"))

    gates = {
        "none": np.ones(len(sig), bool),
        "px<MA10": q_1500 < mas[10],
        "px<MA20": q_1500 < mas[20],
        "px<MA50": q_1500 < mas[50],
        "px<MA100": q_1500 < mas[100],
        "px>MA20": q_1500 > mas[20],
    }
    for gname, gate in gates.items():
        for thr in (0.0, -0.0025, -0.005, -0.0075, -0.010):
            mask = (sig < thr) & gate
            w = lib.carve(w_base, cal, (15, 0), (15, 59), ts, mask)
            rows.append(ev(f"15:00 {gname} thr{thr*100:.2f}", w, f"n={int(mask.sum())}"))

    # 15:00-15:30 only
    for gname in ("none", "px<MA20"):
        for thr in (0.0, -0.005, -0.010):
            mask = (sig < thr) & gates[gname]
            w = lib.carve(w_base, cal, (15, 0), (15, 30), ts, mask)
            rows.append(ev(f"last30 {gname} thr{thr*100:.2f}", w, f"n={int(mask.sum())}"))

    tab = pd.DataFrame(rows)
    tab.to_csv(OUT / "grid2.csv", index=False)
    cols = ["name", "note", "10y_cagr", "10y_dd", "5y_cagr", "5y_dd",
            "IS_cagr", "IS_dd", "OOS_cagr", "OOS_dd", "fills"]
    out = tab[cols].copy()
    for c in cols[2:-1]:
        out[c] = (out[c] * 100).round(2)
    pd.set_option("display.width", 240)
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
