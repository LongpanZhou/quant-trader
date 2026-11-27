"""Scratch: cost sweep for the last-30-minute carve finalists."""
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

ts, opens, closes = lib.load_panel()
cal = lib.calendar(ts)
first, last = cal["first"], cal["last"]
w_base, _ = lib.build_base(ts, opens, closes)
i1500 = lib.time_index(ts, first, last, 15, 0)
q_open = opens[first, 0]
q_1500 = closes[i1500, 0]
sig = q_1500 / q_open - 1.0

rows = []
for thr in (0.0, -0.0025, -0.005, -0.0075, -0.010, -0.0125, -0.015, -0.020):
    mask = sig < thr
    w = lib.carve(w_base, cal, (15, 0), (15, 30), ts, mask)
    for slip in (1.0, 5.0, 10.0):
        r = lib.simulate(ts, opens, closes, w, slip)
        row = {"thr": thr, "slip": slip, "events": int(mask.sum()), "fills": r["fills"]}
        for label, start, end in (("10y", lib.START10, None), ("5y", lib.START5, None),
                                  ("IS", lib.START10, IS_END), ("OOS", IS_END, None)):
            s = lib.window(r, ts, start, end)
            row[f"{label}_cagr"] = s["cagr"]
            row[f"{label}_dd"] = s["max_drawdown"]
        rows.append(row)

r = lib.simulate(ts, opens, closes, w_base, 1.0)
for slip in (1.0, 5.0, 10.0):
    rr = lib.simulate(ts, opens, closes, w_base, slip)
    row = {"thr": np.nan, "slip": slip, "events": 0, "fills": rr["fills"]}
    for label, start, end in (("10y", lib.START10, None), ("5y", lib.START5, None),
                              ("IS", lib.START10, IS_END), ("OOS", IS_END, None)):
        s = lib.window(rr, ts, start, end)
        row[f"{label}_cagr"] = s["cagr"]
        row[f"{label}_dd"] = s["max_drawdown"]
    rows.append(row)

tab = pd.DataFrame(rows)
tab.to_csv(OUT / "cost_last30.csv", index=False)
cc = tab.copy()
for c in cc.columns:
    if c.endswith(("cagr", "dd")):
        cc[c] = (cc[c] * 100).round(2)
pd.set_option("display.width", 240)
print(cc.to_string(index=False))
