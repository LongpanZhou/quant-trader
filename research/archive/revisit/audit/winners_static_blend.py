import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import winners_lib as W  # noqa: E402
import bt  # noqa: E402

ts, o, h, l, c = W.load_panel()
mod, w_r, _ = W.load_ratio_froth(ts, o, c)
modv, w_v, _, _, _, _ = W.load_vol(ts, o, h, l, c)
out = {}
for name, w in (("ratio_froth", w_r), ("vol_scaled", w_v)):
    m = w.mean(axis=0)
    const = np.tile(m, (len(ts), 1))
    r = bt.run(ts, o, c, const, W.START, band=0.02, slippage_bps=1.0)
    d = W.daily_equity(r)
    s = W.metrics(d)
    sr = W.daily_returns(d)
    dates = bt.session_dates(ts)
    _, last = bt.day_bounds_from_dates(dates)
    tq = __import__("pandas").Series(c[last, 1], index=__import__("pandas").to_datetime(dates[last])).pct_change()
    out[name] = {"weights": [float(x) for x in m], "daily": s,
                 "beta": W.beta_corr(sr, tq)}
    print(name, out[name]["weights"], s["cagr"], s["max_drawdown"], s["sharpe"],
          out[name]["beta"])
W.save_json("winners_static_blend.json", out)
