"""Features of the weak-close stop days that the partial block skips."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import srlib as S  # noqa: E402

A = S.arrays()
ts, dates, first, last = A["ts"], A["dates"], A["first"], A["last"]
o, c = A["o"], A["c"]
reg, ma20 = S.regime(ts, c[:, 0], first, last)
dclose = c[last, 0]
n_days = len(first)
ma50 = pd.Series(dclose).rolling(50).mean().to_numpy()
ma20d = pd.Series(dclose).rolling(20).mean().to_numpy()
hi20 = pd.Series(dclose).rolling(20).max().to_numpy()

rows = []
for k, (f, z) in enumerate(zip(first, last)):
    if not reg[f] or k + 1 >= n_days:
        continue
    if not (np.isfinite(ma20[f]) and c[f, 0] < ma20[f] * (1 + S.ARM_BUF)):
        continue
    base = o[f, 1]
    for i in range(f, z + 1):
        if c[i, 1] < base * (1 - S.STOP):
            weak = c[z, 1] < base * (1 - S.STOP)
            nf, nz = first[k + 1], last[k + 1]
            nxt_oc = c[nz, 1] / o[nf, 1] - 1          # what the winner earns next day (from open)
            nxt_oc_0931 = c[nz, 1] / o[nf + 1, 1] - 1
            qret = c[z, 0] / dclose[k - 1] - 1
            q5 = dclose[k] / dclose[k - 5] - 1 if k >= 5 else np.nan
            rows.append(dict(date=dates[f], year=dates[f].year, weak=weak,
                             minute=i - f, qret=qret, q5=q5,
                             q_below_ma50=bool(np.isfinite(ma50[k]) and dclose[k] < ma50[k]),
                             q_dd20=float(dclose[k] / hi20[k] - 1) if np.isfinite(hi20[k]) else np.nan,
                             tqqq_close_ret=float(c[z, 1] / base - 1),
                             nxt_oc=nxt_oc, nxt_oc_0931=nxt_oc_0931))
            break

ev = pd.DataFrame(rows)
w = ev[ev["weak"]].copy()
print(f"weak-close stop days: {len(w)} of {len(ev)}")
print("\nby year: count, mean next-day open->close, worst:")
print(w.groupby("year")["nxt_oc"].agg(["size", "mean", "min"]).round(4).to_string())
print(f"\noverall weak mean {w['nxt_oc'].mean()*100:+.3f}%  median {w['nxt_oc'].median()*100:+.3f}%  "
      f"share<0 {(w['nxt_oc']<0).mean()*100:.0f}%")
r = ev[~ev["weak"]]
print(f"recovered mean {r['nxt_oc'].mean()*100:+.3f}%  median {r['nxt_oc'].median()*100:+.3f}%")

print("\nweak days split by ex-ante features (next-day open->close):")
for name, m in (
    ("QQQ day < -1.5%", w["qret"] < -0.015),
    ("QQQ day >= -1.5%", w["qret"] >= -0.015),
    ("QQQ 5d < -3%", w["q5"] < -0.03),
    ("QQQ 5d >= -3%", w["q5"] >= -0.03),
    ("QQQ < MA50", w["q_below_ma50"]),
    ("QQQ >= MA50", ~w["q_below_ma50"]),
    ("QQQ >5% off 20d high", w["q_dd20"] < -0.05),
    ("QQQ <=5% off 20d high", w["q_dd20"] >= -0.05),
    ("stop before noon", w["minute"] < 150),
    ("stop after noon", w["minute"] >= 150),
):
    x = w.loc[m, "nxt_oc"]
    if len(x):
        print(f"  {name:24s} n={len(x):3d} mean {x.mean()*100:+7.3f}%  median {x.median()*100:+6.3f}%  "
              f"worst {x.min()*100:+6.2f}%  share<0 {(x<0).mean()*100:4.0f}%")

# 2025 events in detail
print("\n2025 weak-close days:")
print(w[w["year"] == 2025][["date", "qret", "q5", "q_dd20", "q_below_ma50", "nxt_oc"]].round(4).to_string(index=False))
print("\n2018 weak-close days:")
print(w[w["year"] == 2018][["date", "qret", "q5", "q_dd20", "q_below_ma50", "nxt_oc"]].round(4).to_string(index=False))
w.to_csv(HERE / "weak_days.csv", index=False)
