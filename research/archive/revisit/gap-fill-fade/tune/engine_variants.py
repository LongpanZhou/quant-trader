"""Engine runs (dev only) of the fixed primary and the best broadened candidate."""
import numpy as np, pandas as pd
from common import *

ts, O, C, H, L, dates, first, last = load()
wbase = baseline_165(ts, C, first, last); db = daily(sim(ts, O, C, wbase, 1)[0])
cands = {
    "primary (fixed)": {},
    "cand: no stress, gap<=1.5%": dict(gap_hi=0.015, stress_mult=0.0),
    "cand gap<=1.2%": dict(gap_hi=0.012, stress_mult=0.0),
    "cand gap<=2.0%": dict(gap_hi=0.020, stress_mult=0.0),
    "cand weak5": dict(gap_hi=0.015, stress_mult=0.0, weak_ma=5),
    "cand weak20": dict(gap_hi=0.015, stress_mult=0.0, weak_ma=20),
    "cand size x2 (vt 20%, max 2)": dict(gap_hi=0.015, stress_mult=0.0, vol_target=0.20, size_max=1.0),
    "cand random entry (placebo)": dict(gap_hi=0.015, stress_mult=0.0, random_entry=True),
}
for nm, kw in cands.items():
    w, info = S.build_weights(ts, O, C, H, L, **kw)
    n = sum(DEV0 <= e["date"] <= DEV1 for e in info["events"])
    line = f"{nm:32s} ev={n:3d}"
    for slip in (1, 5, 10):
        r, s = sim(ts, O, C, w, slip)
        line += f" | {slip}bp {s['cagr']*100:5.2f}%/{s['max_drawdown']*100:4.2f}%/{s['sharpe']:.2f}"
        if slip == 1: d = daily(r)
    subs = []
    for a, b in (("2016-01-04", "2019-12-31"), ("2020-01-01", "2021-12-31"), ("2022-01-01", "2023-12-29")):
        subs.append(f"{sim(ts, O, C, w, 1, a, b)[1]['cagr']*100:.2f}")
    print(line, "| subs", "/".join(subs), f"| corr165 {d.corr(db.reindex(d.index)):+.3f}")
wb = np.zeros((len(ts), 4)); wb[:, 2] = 1
for a, b in ((DEV0, DEV1), ("2016-01-04", "2019-12-31"), ("2020-01-01", "2021-12-31"), ("2022-01-01", "2023-12-29")):
    print("BIL", a, b, f"{sim(ts, O, C, wb, 1, a, b)[1]['cagr']*100:.2f}%")
