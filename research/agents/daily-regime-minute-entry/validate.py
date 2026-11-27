"""Build cache, validate 1m control equals daily baseline, time one run."""
import time
import numpy as np

import strat_lib as sl

t0 = time.time()
A = sl.load_arrays(force=True)
print(f"load {time.time()-t0:.1f}s  bars {len(A['ts']):,}  days {len(A['first']):,}")

reg, dc, sma, dates, first, last = sl.daily_regime(A["ts"], A["closes"][:, 0], 165)
print("regime days on:", reg[first].mean())

n = len(A["ts"])
w = np.zeros((n, 3))
w[:, 1] = reg.astype(float)
w[:, 2] = 1.0 - w[:, 1]

t0 = time.time()
out = sl.summarize("control regime-on=TQQQ (1m)", A["ts"], A["opens"], A["closes"], w)
print(f"sim {time.time()-t0:.1f}s")
