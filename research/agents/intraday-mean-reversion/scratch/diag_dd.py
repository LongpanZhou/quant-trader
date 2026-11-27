"""Drawdown anatomy of the passing daily baseline (shift=0, exact README numbers)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

START, END = "2017-01-03", "2026-10-23"
tsd, od, cd = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1D")
i0 = bt.start_index(tsd, START)
qqq = cd[:, 0]
day = pd.DataFrame({"c": qqq}, index=pd.Index(tsd))
sma = day["c"].rolling(165).mean()
reg = (day["c"] > sma).astype(float).fillna(0.0)
w = np.zeros((len(tsd), 3))
w[:, 1] = reg.to_numpy()
w[:, 2] = 1 - reg.to_numpy()
res = bt.run(tsd, od, cd, w, START, band=0.02)
eq = res["equity"]
ts = tsd[i0:]
peak = np.maximum.accumulate(eq)
ddown = eq / peak - 1
print("max dd", ddown.min())
# deepest episodes: find running max drawdown recovery
in_dd = False
start_i = 0
episodes = []
for i in range(len(eq)):
    if not in_dd and ddown[i] < -0.02:
        in_dd = True
        start_i = i
    elif in_dd and ddown[i] >= -1e-9:
        in_dd = False
        seg = ddown[start_i:i]
        j = int(np.argmin(seg)) + start_i
        episodes.append((seg.min(), ts[start_i], ts[j], ts[i]))
for v, a, b, c_ in sorted(episodes)[:8]:
    print(f"  dd {v*100:6.1f}%  {a.date()} -> trough {b.date()} -> recover {c_.date()}")
print("\nregime switches in test:")
sw = np.flatnonzero(np.diff(reg.to_numpy()[i0:]) != 0)
for k in sw[:40]:
    print("  ", ts[k].date(), "->", reg.to_numpy()[i0:][k + 1])
