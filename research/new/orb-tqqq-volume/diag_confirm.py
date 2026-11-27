"""Diagnostic: is the QQQ-confirmation ORB subset real or an artifact?"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

df = pd.read_pickle(Path(__file__).resolve().parent / "_sessions3.pkl")
df = df[df["date"] >= pd.Timestamp("2016-01-04").date()].reset_index(drop=True)
b = df[df["brk_px"].notna()].copy()

m = (b["gap"] > 0) & (b["or_ret"] > 0.003) & b["qqq_confirm"]
s = b[m]
print(f"n={len(s)} mean={s['brk_ret'].mean()*100:.3f}% med={s['brk_ret'].median()*100:.3f}% "
      f"std={s['brk_ret'].std()*100:.2f}%")

print("\nentry minute distribution:")
print(s["brk_min"].describe())
print(pd.cut(s["brk_min"], [600, 605, 610, 620, 640, 700, 800, 900, 960]).value_counts().sort_index())

print("\nQQQ breakout minute vs TQQQ breakout minute:")
d = (s["brk_min"] - s["qbrk_min"])
print(d.describe())
print("QQQ first:", (d > 0).sum(), " same:", (d == 0).sum(), " TQQQ first:", (d < 0).sum())

print("\nyearly:")
for y, g in s.groupby(s["date"].apply(lambda x: x.year)):
    print(f"  {y}: n={len(g):3d} mean={g['brk_ret'].mean()*100:7.3f}% "
          f"med={g['brk_ret'].median()*100:7.3f}% win={np.mean(g['brk_ret']>0)*100:5.1f}%")

print("\ntop 15 trades:")
print(s.nlargest(15, "brk_ret")[["date", "gap", "or_ret", "brk_min", "qbrk_min", "brk_ret"]]
      .to_string(index=False))

print("\ncompare: TQQQ breakout first (d<0) vs QQQ first (d>0)")
for label, mask in (("QQQ first", d > 0), ("same minute", d == 0), ("TQQQ first", d < 0)):
    x = s[mask]["brk_ret"]
    print(f"  {label:12s} n={len(x):3d} mean={x.mean()*100:7.3f}% med={x.median()*100:7.3f}%")

print("\nstrict same-bar confirm (within 1 minute):")
m2 = m & ((b["brk_min"] - b["qbrk_min"]).abs() <= 1)
x = b[m2]["brk_ret"]
print(f"  n={len(x)} mean={x.mean()*100:.3f}% med={x.median()*100:.3f}%")

print("\nwithout qqq confirm, by entry timing:")
for lo, hi in ((600, 620), (620, 660), (660, 720), (720, 960)):
    x = b[(b["gap"] > 0) & (b["or_ret"] > 0.003) & b["brk_min"].between(lo, hi)]["brk_ret"]
    print(f"  {lo}-{hi}: n={len(x):3d} mean={x.mean()*100:7.3f}%")

print("\nQQQ confirm rate and mean by TQQQ entry bucket:")
for lo, hi in ((600, 605), (605, 620), (620, 660), (660, 720), (720, 960)):
    g = b[(b["gap"] > 0) & (b["or_ret"] > 0.003) & b["brk_min"].between(lo, hi)]
    for lab, mm in (("confirm", g["qqq_confirm"]), ("no", ~g["qqq_confirm"])):
        x = g[mm]["brk_ret"]
        if len(x):
            print(f"  {lo}-{hi} {lab:8s} n={len(x):3d} mean={x.mean()*100:7.3f}%")

# Is qqq_confirm just a proxy for QQQ already being up a lot?
print("\ncorr(qqq_confirm, gap) among ORB days:", b["qqq_confirm"].astype(float).corr(b["gap"]))
print("QQQ OR return vs TQQQ OR return corr:",
      ((b["q_or_hi"] / b["q_open"] - 1).corr(b["or_ret"])))

# Causal variant: at TQQQ breakout bar, require QQQ close > QQQ OR high on that
# same bar (contemporaneous), computed directly.
ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), "2016-01-04", "2023-12-29", "1min",
                             warmup_days=100)
lo, hi = pd.Timestamp(ts[0]), pd.Timestamp(ts[-1])

def prep(sym):
    d = bt.load_1m(sym)
    d = d[(d["ts"] >= lo) & (d["ts"] <= hi)]
    return d.set_index("ts").reindex(ts).ffill()

q, t = prep("QQQ"), prep("TQQQ")
to, tc = t["open"].to_numpy(), t["close"].to_numpy()
qc = q["close"].to_numpy()
dates = ts.date
starts = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
ends = np.r_[starts[1:], len(ts)]
tod = np.asarray(ts.hour * 60 + ts.minute)

rows = []
for k, (s0, e) in enumerate(zip(starts, ends)):
    j = int(np.searchsorted(tod[s0:e], 600))
    if j < 10:
        continue
    orh = t["high"].to_numpy()[s0:s0 + j].max()
    qorh = q["high"].to_numpy()[s0:s0 + j].max()
    brk = -1
    for i in range(s0 + j, e - 1):
        if tc[i] > orh:
            brk = i
            break
    if brk < 0:
        continue
    rows.append(dict(date=dates[s0], brk_min=tod[brk],
                     tqqq_q_above=tc[brk] / orh - 1,
                     qqq_q_above=qc[brk] / qorh - 1,
                     ret=tc[e - 1] / to[brk + 1] - 1))
z = pd.DataFrame(rows)
print("\ncontemporaneous QQQ close above QQQ ORH at TQQQ breakout bar:")
for th in (-0.001, 0.0, 0.001, 0.002):
    x = z[z["qqq_q_above"] > th]["ret"]
    print(f"  qqq above ORH by >{th*100:+.1f}%: n={len(x):4d} mean={x.mean()*100:7.3f}% "
          f"med={x.median()*100:7.3f}%")
x = z[z["qqq_q_above"] <= 0]["ret"]
print(f"  qqq below ORH: n={len(x):4d} mean={x.mean()*100:7.3f}% med={x.median()*100:7.3f}%")
print("\ncorr(qqq_q_above, ret):", z["qqq_q_above"].corr(z["ret"]))
for qq in (-0.01, -0.005, 0, 0.005, 0.01):
    sel = z[np.abs(z["qqq_q_above"] - qq) < 0.0025]
    print(f"  qqq_q_above ~ {qq*100:+.1f}%: n={len(sel):3d} mean={sel['ret'].mean()*100:7.3f}%")
