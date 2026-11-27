import json
import sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import winners_lib as W
import bt

ts, o, h, l, c = W.load_panel()
mod, w_full, _ = W.load_ratio_froth(ts, o, c)
w_base = mod.build_weights(ts, o, c, use_overlay=False)[0]
w_bil = mod.build_weights(ts, o, c, defensive="BIL")[0]
out = {}
for name, w in (("old_base", w_base), ("full_qqq", w_full), ("full_bil", w_bil)):
    r = bt.run(ts, o, c, w, W.START, band=0.02, slippage_bps=1.0)
    d = W.daily_equity(r)
    out[name] = {
        "dev": W.subperiod(d, "2016-01-04", "2023-12-29"),
        "holdout": W.subperiod(d, "2024-01-02", "2026-10-23"),
        "2024": W.subperiod(d, "2024-01-01", "2024-12-31"),
        "2025": W.subperiod(d, "2025-01-01", "2025-12-31"),
        "2026": W.subperiod(d, "2026-01-01", "2026-10-23"),
    }
    print(name)
    for k, v in out[name].items():
        print(" ", k, round(v["cagr"] * 100, 2), round(v["max_drawdown"] * 100, 2), round(v["sharpe"], 2))
W.save_json("winners_ratio_subperiod.json", out)
