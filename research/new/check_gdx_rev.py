import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"C:\Users\27175\Desktop\quant-trader-research")
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(ROOT / "research" / "new"))
import bt
import ext_alt
import run_holdout as R

EXISTING = ["ratio-froth", "vol-scaled-crash-stop", "relative-value-tqqq",
            "fomc-opex-window", "family-session-timing", "family-short-reversal",
            "family-rebalance-flow", "family-intraday-microstructure-day"]
ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), R.START, R.END, "1min", warmup_days=0)
_, _, last = bt.day_bounds(ts)
states = dict(np.load(ROOT / "research/new/_full_states.npz", allow_pickle=True))
w, info = ext_alt.make_weights(ts, o, c, "gdx_gld", {"flip": False})
r = bt.run(ts, o, c, w, R.START, band=0.02, slippage_bps=1.0)
s = bt.stats(r, 252 * 390)
eq = pd.Series(r["equity"], index=pd.to_datetime(r["ts"]))
if eq.index.tz is not None:
    eq.index = eq.index.tz_localize(None)
eq = eq.groupby(eq.index.normalize()).last()
print("full", {k: round(float(s[k]), 4) for k in ("cagr", "max_drawdown", "sharpe", "fills")})
sig = w[last, 1] > 0.5
for e in EXISTING:
    a, b = sig, states[e]
    j = np.logical_and(a, b).sum() / max(1, np.logical_or(a, b).sum())
    print(f"J {e:38s} {j:.3f}")
allj = json.loads((ROOT / "web/public/data/compare/all.json").read_text())
curves = {x["id"]: pd.Series(x["values"], index=pd.to_datetime(allj["dates"]))
          for x in allj["series"]}
for e in EXISTING:
    ra = eq.pct_change()
    rb = curves[e].pct_change()
    df = pd.concat([ra, rb], axis=1, join="inner").dropna()
    print(f"corr {e:38s} {np.corrcoef(df.iloc[:,0], df.iloc[:,1])[0,1]:.3f}")
