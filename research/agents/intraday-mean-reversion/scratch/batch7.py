"""Batch 7: opening-gap overreaction (classic intraday MR) + sub-period robustness."""
import numpy as np
import pandas as pd

import engine3 as E

ts, o, c, feats = E.load_cached()
n = len(ts)
qqq, tqqq = feats["qqq"], feats["tqqq"]
date, bars, reg = feats["date"], feats["bars"], feats["regime"]
dopen = feats["dopen"]
qpc = feats["qpc"]
i0 = E.bt.start_index(ts, E.START10)

gap = dopen / qpc - 1.0
print("=== gap distribution (regime-on days) ===")
m_all = (np.arange(n) >= i0) & (reg > 0.5) & (bars == 0) & np.isfinite(gap)
print("days", int(m_all.sum()), "sd gap", np.std(gap[m_all]) * 100, "%")
for lo, hi in [(-0.05, -0.010), (-0.010, -0.007), (-0.007, -0.005), (-0.005, -0.003), (-0.003, 0.0),
               (0.0, 0.003), (0.003, 0.005), (0.005, 0.007), (0.007, 0.010), (0.010, 0.05)]:
    mm = m_all & (gap >= lo) & (gap < hi)
    if mm.sum() < 10:
        continue
    # index of 09:35 open (second bar) for each such day
    idxs = np.flatnonzero(mm)
    # TQQQ return from 09:35 open to 10:30 open and to close
    r1030, rclose = [], []
    for j in idxs:
        k = j + 6
        if k < n and date[k] == date[j]:
            r1030.append(o[k, 1] / o[j + 1, 1] - 1)
        kk = j + 77
        if kk < n and date[kk] == date[j]:
            rclose.append(c[kk, 1] / o[j + 1, 1] - 1)
    print(f"  gap [{lo*100:+5.2f},{hi*100:+5.2f})% n={mm.sum():4d}  09:35->10:30 {np.mean(r1030)*100:+.3f}% "
          f"(win {np.mean(np.array(r1030)>0)*100:4.1f}%)  09:35->close {np.mean(rclose)*100:+.3f}% "
          f"(win {np.mean(np.array(rclose)>0)*100:4.1f}%)")

print("\n=== sub-period stats: 2017-01..2021-10 and 2021-10..2026-10 ===")
for label, p in [
    ("base", dict(signal="none", base=1.0, entry=0, exit=0)),
    ("stop2.5", dict(signal="none", base=1.0, entry=0, exit=0, stop_prev=0.025)),
    ("stop3.0", dict(signal="none", base=1.0, entry=0, exit=0, stop_prev=0.030)),
    ("stop3.5", dict(signal="none", base=1.0, entry=0, exit=0, stop_prev=0.035)),
]:
    w = E.make_weights(feats, o, n, p)
    vals = []
    for start, end in (("2017-01-03", "2021-10-22"), ("2021-10-25", "2026-10-23")):
        res = E.bt.run(ts, o, c, w, start, band=0.0, slippage_bps=1.0)
        a = E.bt.start_index(ts, start)
        b = E.bt.start_index(ts, end)
        eq = res["equity"][: b - a + 1]
        tt = res["ts"][: b - a + 1]
        s = E.bt.stats({"equity": eq, "cash": res["cash"][: b - a + 1], "fills": 0, "turnover": 0, "ts": tt}, E.BARS_PER_YEAR)
        vals.append((start, s["cagr"], s["max_drawdown"], s["sharpe"]))
    print(f"  {label:8s} " + "  ".join(f"{a[:7]}: {c*100:5.1f}%/{d*100:4.1f}% sh{sh:.2f}" for a, c, d, sh in vals))
