"""Scratch: combine the day-move signal with calendar conditioning, and get the
full cost curve for each candidate."""
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
sig = closes[i1500, 0] / opens[first, 0] - 1.0
dow = cal["dow"]

cands = {
    "q<-1.0": sig < -0.01,
    "q<-1.0 & opex": (sig < -0.01) & cal["opex"],
    "q<-0.5 & opex": (sig < -0.005) & cal["opex"],
    "q<0 & opex": (sig < 0) & cal["opex"],
    "opex only": cal["opex"],
    "q<-1.0 & (opex|wed)": (sig < -0.01) & (cal["opex"] | (dow == 2)),
    "q<-1.0 & post_opex": (sig < -0.01) & cal["post_opex"],
    "q<-1.0 & pre_opex": (sig < -0.01) & cal["pre_opex"],
    "q<-1.5": sig < -0.015,
    "q<-1.0 & q<ma20": None,
}

# causal MA20 gate
dc = closes[last, 0]
ma20 = pd.Series(dc).rolling(20).mean().to_numpy()
ma_prev = np.r_[np.nan, ma20[:-1]]
cands["q<-1.0 & q<ma20"] = (sig < -0.01) & (closes[i1500, 0] < ma_prev)

rows = []
for name, mask in cands.items():
    w = lib.carve(w_base, cal, (15, 0), (15, 30), ts, mask)
    for slip in (1.0, 5.0):
        r = lib.simulate(ts, opens, closes, w, slip)
        row = {"name": name, "slip": slip, "events": int(mask.sum()), "fills": r["fills"]}
        for label, start, end in (("10y", lib.START10, None), ("5y", lib.START5, None),
                                  ("IS", lib.START10, IS_END), ("OOS", IS_END, None)):
            s = lib.window(r, ts, start, end)
            row[f"{label}_cagr"] = s["cagr"]
            row[f"{label}_dd"] = s["max_drawdown"]
        rows.append(row)

for slip in (1.0, 5.0):
    r = lib.simulate(ts, opens, closes, w_base, slip)
    row = {"name": "BASE", "slip": slip, "events": 0, "fills": r["fills"]}
    for label, start, end in (("10y", lib.START10, None), ("5y", lib.START5, None),
                              ("IS", lib.START10, IS_END), ("OOS", IS_END, None)):
        s = lib.window(r, ts, start, end)
        row[f"{label}_cagr"] = s["cagr"]
        row[f"{label}_dd"] = s["max_drawdown"]
    rows.append(row)

tab = pd.DataFrame(rows)
tab.to_csv(OUT / "combo.csv", index=False)
cc = tab.copy()
for c in cc.columns:
    if c.endswith(("cagr", "dd")):
        cc[c] = (cc[c] * 100).round(2)
pd.set_option("display.width", 240)
print(cc.to_string(index=False))
