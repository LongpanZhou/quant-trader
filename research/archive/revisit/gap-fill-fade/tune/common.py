"""Shared loader for the 2026-11-27 tuning diagnostics (dev only)."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[2]))
import bt  # noqa
import strategy as S  # noqa

DEV0, DEV1 = "2016-01-04", "2023-12-29"
BPY = 252 * 390


def load():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), DEV0, DEV1, "1min")
    dates, first, last = S._sessions(ts)
    io, ic = S.inverse_qqq(o, c, first, last)
    O = np.column_stack([o, io]); C = np.column_stack([c, ic])
    q = bt.load_1m("QQQ").set_index("ts").reindex(ts).ffill()
    return ts, O, C, q["high"].to_numpy(), q["low"].to_numpy(), dates, first, last


def dev_slice(ts):
    i0 = bt.start_index(ts, DEV0)
    i1 = int(ts.searchsorted(pd.Timestamp(DEV1, tz="America/New_York").normalize() + pd.Timedelta(days=1)))
    return i0, i1


def sim(ts, O, C, w, slip=1.0, a=DEV0, b=DEV1):
    i0 = bt.start_index(ts, a)
    i1 = int(ts.searchsorted(pd.Timestamp(b, tz="America/New_York").normalize() + pd.Timedelta(days=1)))
    r = bt.simulate(ts[i0:i1], O[i0:i1], C[i0:i1], w[i0:i1], band=0.02, slippage_bps=slip)
    return r, bt.stats(r, BPY)


def daily(r):
    eq = pd.Series(r["equity"], index=r["ts"])
    return eq.groupby(eq.index.date).last().pct_change().dropna()


def baseline_165(ts, C, first, last):
    """Benchmark only: TQQQ if QQQ prior close > 165d SMA else BIL (daily, set at close)."""
    dc = C[last, 0]
    sma = pd.Series(dc).rolling(165).mean().to_numpy()
    on = dc > sma  # decided at session close, held next session
    w = np.zeros((len(ts), C.shape[1])); w[:, 2] = 1.0
    for k, (f, l) in enumerate(zip(first, last)):
        if k + 1 < len(first) and on[k]:
            w[l:last[k + 1], :] = 0; w[l:last[k + 1], 1] = 1.0
        elif k + 1 < len(first):
            w[l:last[k + 1], :] = 0; w[l:last[k + 1], 2] = 1.0
    return w
