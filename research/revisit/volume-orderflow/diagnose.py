import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"C:\Users\27175\Desktop\quant-trader-research")
sys.path.insert(0, str(ROOT / "research"))
path = ROOT / "research" / "revisit" / "volume-orderflow" / "strategy.py"
spec = importlib.util.spec_from_file_location("vo", path)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

ts, o, c, h, l, v = mod.load_panel()
dates, first, last, f = mod.session_features(ts, o, c, h, l, v)
rv, intr, clv = f["rvol"], f["intraday"], f["clv"]
print("sessions", len(first))
for label, mask in [
    ("rvol>=1.5", rv >= 1.5),
    ("intraday<=-0.8%", intr <= -0.008),
    ("clv>=0", clv >= 0),
    ("rvol & intraday", (rv >= 1.5) & (intr <= -0.008)),
    ("rvol & clv", (rv >= 1.5) & (clv >= 0)),
    ("intraday & clv", (intr <= -0.008) & (clv >= 0)),
    ("all", (rv >= 1.5) & (intr <= -0.008) & (clv >= 0)),
]:
    print(f"{label:22s} {int(np.nansum(mask))}")
print("rvol quantiles", np.nanpercentile(rv, [50, 75, 90, 95, 99]))
print("intraday quantiles", np.nanpercentile(intr, [1, 5, 10, 25, 50]))
print("clv quantiles", np.nanpercentile(clv, [10, 25, 50, 75, 90]))
