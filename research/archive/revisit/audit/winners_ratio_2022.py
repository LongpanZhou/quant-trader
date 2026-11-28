import json, sys
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
        "2021": W.subperiod(d, "2021-01-01", "2021-12-31"),
        "2022": W.subperiod(d, "2022-01-01", "2022-12-31"),
        "2023": W.subperiod(d, "2023-01-01", "2023-12-29"),
        "2021_2023": W.subperiod(d, "2021-01-01", "2023-12-29"),
    }
    print(name, {k: (round(v["cagr"]*100,2), round(v["max_drawdown"]*100,2)) for k,v in out[name].items()})
W.save_json("winners_ratio_2022.json", out)
