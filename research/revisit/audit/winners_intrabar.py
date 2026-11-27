import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import winners_lib as W  # noqa: E402
import bt  # noqa: E402

ts, o, h, l, c = W.load_panel()
dates = bt.session_dates(ts)
first, last = bt.day_bounds_from_dates(dates)
sd = dates[last]

out = {}
for j, sym in enumerate(("QQQ", "TQQQ", "BIL")):
    # intra-session only: return from bar i-1 close to bar i close, same session
    r = np.diff(c[:, j]) / c[:-1, j]
    same = dates[1:] == dates[:-1]
    r = np.where(same, r, np.nan)
    rr = r[np.isfinite(r)]
    order = np.argsort(r)
    top = []
    for i in list(order[:15]):
        # global index: r index i corresponds to bar i+1
        g = i + 1
        nxt = r[i + 1] if i + 1 < len(r) else np.nan
        top.append({"ts": str(ts[g]), "ret": float(r[i]),
                    "prev_close": float(c[g - 1, j]), "close": float(c[g, j]),
                    "next_same_session_ret": None if not np.isfinite(nxt) else float(nxt),
                    "reversal": None if not np.isfinite(nxt) else float(-np.sign(r[i]) * nxt)})
    out[sym] = {
        "n_gt_5pct": int((np.abs(rr) > 0.05).sum()),
        "n_gt_10pct": int((np.abs(rr) > 0.10).sum()),
        "n_gt_15pct": int((np.abs(rr) > 0.15).sum()),
        "n_gt_20pct": int((np.abs(rr) > 0.20).sum()),
        "top15": top,
    }
print(json.dumps(out, indent=1))

# daily close worst differences vs yahoo
for j, sym in enumerate(("QQQ", "TQQQ", "BIL")):
    df = pd.read_parquet(W.ROOT / "data" / "intraday-hf" / f"{sym}-1d-yahoo.parquet")
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df = df.set_index("date")
    p = pd.Series(c[last, j], index=[pd.Timestamp(d).date() for d in sd])
    common = p.index.intersection(df.index)
    rel = p.loc[common] / df.loc[common, "adjclose"].astype(float) - 1.0
    print(sym, "worst daily close rel")
    print(rel.abs().sort_values(ascending=False).head(8).to_string())
