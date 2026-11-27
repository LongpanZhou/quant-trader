"""Tune-brief Step 3 sweep. DEV ONLY (panel ends 2023-12-29).

Families (each counted as variants):
  A  fixed threshold 2.0..4.0 (re-measure of the pre-registered V1)
  B  vol-normalised threshold dd <= -k * sigma20 (sigma20 = prior 20-session std of QQQ daily ret)
  C  exit timing inside the held session: exit after m minutes (60/120/210/full)
  D  enter at the trigger session's 15:59 open and hold overnight + next session
  E  preliminary-harness reproduction: consecutive events held overnight
"""
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("imr", HERE.parent / "strategy.py")
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)
bt = S.bt

ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), S.DEV_START, S.DEV_END, "1min")
assert ts[-1].date() <= pd.Timestamp(S.DEV_END).date()
F = S.session_features(ts, c)
first, last, nd = F["first"], F["last"], F["nd"]
sdate = F["d"][first]
i0, i1 = S.window_bounds(ts, S.DEV_START, S.DEV_END)
tsw = ts[i0:i1 + 1]
base_w = S.correlation_baseline_weights(ts, c)


def sim(w, slip=1.0):
    return bt.simulate(tsw, o[i0:i1 + 1], c[i0:i1 + 1], w[i0:i1 + 1], band=0.02, slippage_bps=slip)


rb = sim(base_w)
base_r = S.daily_returns(rb)


def weights(event, exit_min=None, overnight_entry=False, consec_overnight=False):
    """event: bool per session (trigger). Held session = k+1."""
    n = len(ts)
    w = np.zeros((n, 3))
    held = np.zeros(nd, bool)
    held[1:] = event[:-1]
    for k in range(nd):
        a, b = first[k], last[k]
        if held[k]:
            e = b - 1 if exit_min is None else min(b - 1, a + exit_min - 1)
            w[a:e, 1] = 1.0           # target set at bar e -> 0, filled at bar e+1 open
            w[e:b, 1] = 0.0
            if consec_overnight and k + 1 < nd and held[k + 1]:
                w[a:b, 1] = 1.0
        if k + 1 < nd and held[k + 1]:
            w[b, 1] = 1.0
            if overnight_entry and event[k]:
                w[b - 1, 1] = 1.0     # fill at the trigger session's 15:59 open
    w[-1, 1] = 0.0
    w[:, 2] = 1.0 - w[:, 1]
    return w, int(held[i0 <= first].sum())


def evaluate(w, nev):
    out = {"n": nev}
    for slip in (1.0, 5.0, 10.0):
        r = sim(w, slip)
        s = bt.stats(r, S.BARS_1M)
        out[f"{slip:.0f}bp"] = [round(s["cagr"], 4), round(s["max_drawdown"], 4), round(s["sharpe"], 3)]
        if slip == 1.0:
            eq = pd.Series(r["equity"], index=tsw)
            sub = {}
            for lab, y0, y1 in (("16-19", 2016, 2019), ("20-21", 2020, 2021), ("22-23", 2022, 2023)):
                seg = eq[(eq.index.year >= y0) & (eq.index.year <= y1)]
                yrs = (seg.index[-1] - seg.index[0]).total_seconds() / (365.25 * 86400)
                sub[lab] = round((seg.iloc[-1] / seg.iloc[0]) ** (1 / yrs) - 1, 4)
            out["sub_cagr"] = sub
            dr = S.daily_returns(r)
            j = dr.index.intersection(base_r.index)
            out["corr"] = round(float(np.corrcoef(dr.loc[j], base_r.loc[j])[0, 1]), 3)
    return out


R = {}
dmin = F["dmin"]
sig = F["sigma20"]  # known at prior session's close (shifted): sigma for session k uses sessions < k
ok = np.isfinite(dmin)

# sanity: family A at 3% equals the frozen build_weights
w_ref, _ = S.build_weights(ts, o, c)
evt = np.zeros(nd, bool); evt[1:] = ok[1:] & (dmin[1:] <= -0.03)
w3, n3 = weights(evt)
R["sanity_max_abs_diff_vs_frozen"] = float(np.abs(w3 - w_ref).max())

for th in (0.02, 0.025, 0.03, 0.035, 0.04):
    ev = np.zeros(nd, bool); ev[1:] = ok[1:] & (dmin[1:] <= -th)
    R[f"A_th{th}"] = evaluate(*weights(ev))

for kk in (1.5, 2.0, 2.5, 3.0, 3.5):
    ev = np.zeros(nd, bool)
    ev[1:] = ok[1:] & np.isfinite(sig[1:]) & (dmin[1:] <= -kk * sig[1:])
    R[f"B_k{kk}"] = evaluate(*weights(ev))

for m in (60, 120, 210, 300):
    R[f"C_exit{m}m"] = evaluate(*weights(evt, exit_min=m))

R["D_overnight_entry"] = evaluate(*weights(evt, overnight_entry=True))
R["E_prelim_consec_overnight"] = evaluate(*weights(evt, consec_overnight=True))

json.dump(R, open(HERE / "tune_sweep.json", "w", newline="\n", encoding="utf-8"), indent=1)
for k, v in R.items():
    print(k, v)
