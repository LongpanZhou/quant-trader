"""Replicate the round-1 winner on this panel."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, "research")
sys.path.insert(0, str(HERE / "scratch"))
import bt
import lib

ts, opens, closes = lib.load_panel()
wd = lib.winner_daily(ts, opens, closes)
w = lib.weights_from_rules(ts, opens, closes, wd)

for start, tag in [("2017-01-03", "10y"), ("2021-10-25", "5y")]:
    for bp in (1.0, 5.0, 10.0):
        r = bt.run(ts, opens, closes, w, start, band=0.02, slippage_bps=bp)
        s = bt.stats(r, 252 * 390)
        print(tag, f"{bp:g}bp", lib.fmt(s))
