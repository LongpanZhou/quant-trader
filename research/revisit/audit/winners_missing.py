import sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import winners_lib as W
import bt

ts, o, h, l, c = W.load_panel()
dates = bt.session_dates(ts)
first, last = bt.day_bounds_from_dates(dates)
sd = dates[last]
out = {}
for d in ("2016-02-02", "2016-02-22", "2020-03-09", "2020-03-12", "2020-03-16", "2020-03-18"):
    k = int(np.flatnonzero(sd == np.datetime64(d))[0])
    f, ll = first[k], last[k]
    times = pd.DatetimeIndex(ts[f:ll + 1])
    all_min = pd.date_range(times[0], times[-1], freq="1min")
    missing = all_min.difference(times)
    out[d] = {
        "bars": int(ll - f + 1),
        "missing": [str(x.time()) for x in missing],
        "n_missing": int(len(missing)),
        "tqqq_ret_day": float(c[ll, 1] / c[f, 1] - 1),
    }
print(out)
