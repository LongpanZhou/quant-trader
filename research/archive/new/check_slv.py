import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"C:\Users\27175\Desktop\quant-trader-research")
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(ROOT / "research" / "new"))
import bt
import run_holdout as R

EXISTING = ["ratio-froth", "vol-scaled-crash-stop", "relative-value-tqqq",
            "fomc-opex-window", "family-session-timing", "family-short-reversal",
            "family-rebalance-flow", "family-intraday-microstructure-day"]
slug = "family-slv-gld"
ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), R.START, R.END, "1min", warmup_days=0)
_, _, last = bt.day_bounds(ts)
states = dict(np.load(ROOT / "research/new/_full_states.npz", allow_pickle=True))
m = R.load(slug)
out = R.build_full(m, ts, o, c)
w = out[0] if isinstance(out, tuple) else out
w = np.asarray(w, float)
if w.shape[1] == 2:
    w = R.tqqq_bil_to_three(w, len(ts))
sig = w[last, 1] > 0.5

allj = json.loads((ROOT / "web/public/data/compare/all.json").read_text())
curves = {s["id"]: pd.Series(s["values"], index=pd.to_datetime(allj["dates"]))
          for s in allj["series"]}
d = json.loads((ROOT / "research/new/curves" / f"{slug}.json").read_text())
curves[slug] = pd.Series(d["values"], index=pd.to_datetime(d["dates"]))

print("Jaccard")
for e in EXISTING:
    a, b = sig, states[e]
    j = np.logical_and(a, b).sum() / max(1, np.logical_or(a, b).sum())
    print(f"  {e:38s} {j:.3f}")

print("correlation")
for e in EXISTING:
    ra = curves[slug].pct_change()
    rb = curves[e].pct_change()
    df = pd.concat([ra, rb], axis=1, join="inner").dropna()
    corr = np.corrcoef(df.iloc[:, 0], df.iloc[:, 1])[0, 1]
    print(f"  {e:38s} {corr:.3f}")
