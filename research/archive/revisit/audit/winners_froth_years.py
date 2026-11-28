import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import winners_lib as W
import bt

ts, o, h, l, c = W.load_panel()
mod, w, _ = W.load_ratio_froth(ts, o, c)
dates = bt.session_dates(ts)
first, last = bt.day_bounds_from_dates(dates)
sd = dates[last]
froth, ext = mod.froth_flag(c, last)
years = pd.to_datetime(sd).year
out = {}
for y in sorted(set(years)):
    m = years == y
    out[int(y)] = {"sessions": int(m.sum()), "froth_days": int((froth & m).sum()),
                   "froth_share": float((froth & m).sum() / m.sum())}
print(json.dumps(out, indent=1))
# yearly full vs old base delta
a = json.load(open(HERE / "winners_attrib.json"))
full = a["ratio"]["full"]["yearly"]
base = a["ratio"]["no_overlay_gate_stop"]["yearly"]
print("overlay delta pp")
for y in sorted(full, key=int):
    print(y, round((full[y] - base[y]) * 100, 2))
