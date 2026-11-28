"""Overfitting controls for V3 (first-hour reversal, TQQQ/BIL) and V2. Dev only."""
import numpy as np, json, itertools
from common import *  # noqa
from vlib import build
ts, o, c = panel()
base = dict(legs=(("fh", -1),), ladder=("BIL", "TQQQ"))
grid = {}
for step, med, fhb in itertools.product((3, 5, 10), (13, 26, 52), (30, 60, 90)):
    kw = dict(base, step=step, med_n=med, min_hist=min(13, med), fh_bars=fhb)
    grid[f"step{step} med{med} fh{fhb}"] = kw
for off in range(1, 5):
    grid[f"phase+{off}"] = dict(base, offset=off)
for vc in ((0.5, 0.7), (0.7, 0.9), None):
    grid[f"volcap {vc}"] = dict(base, vol_caps=vc)
grid["V2 phase0"] = dict(legs=(("sp", 1), ("fh", -1)))
for off in range(1, 5):
    grid[f"V2 phase+{off}"] = dict(legs=(("sp", 1), ("fh", -1)), offset=off)
for off in range(1, 5):
    grid[f"P ret5 phase+{off}"] = dict(legs=(("ret5", -1),), ladder=("BIL", "TQQQ"), offset=off)
out = {}
keys = list(grid)
for i in range(0, len(keys), 8):
    ks = keys[i:i + 8]
    ws = [build(ts, o, c, **grid[k])[0] for k in ks]
    for slip in (1.0, 5.0):
        rs = run_many(ws, slip)
        for k, r in zip(ks, rs):
            s = stats(r); d = out.setdefault(k, {})
            d[f"{int(slip)}bp"] = [round(s["cagr"]*100, 2), round(s["max_drawdown"]*100, 2), round(s["sharpe"], 2)]
            if slip == 1.0:
                d["corr"] = round(corr_base(r), 3)
                d["sub"] = [round(v*100, 1) for v in sub_cagr(r).values()]
    del ws
for k, d in out.items():
    print(f"{k:24s} 1bp {d['1bp']}  5bp {d['5bp']}  corr {d['corr']}  sub {d['sub']}")
with open(HERE / "sweep2.json", "w", newline="\n", encoding="utf-8") as f:
    json.dump(out, f, indent=1)
