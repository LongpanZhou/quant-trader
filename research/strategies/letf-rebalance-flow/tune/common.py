"""Shared helpers for the 2026-11-27 tuning diagnostics (dev only)."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
SDIR = HERE.parent
ROOT = SDIR.parents[2]
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(SDIR))
import bt  # noqa
import strategy as S  # noqa

DEV0, DEV1 = "2016-01-04", "2023-12-29"
BARS = 252 * 390


def load():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), DEV0, DEV1, "1min", warmup_days=0)
    assert ts[-1] < pd.Timestamp("2023-12-30", tz="America/New_York")
    return ts, o, c


def sessions(ts):
    d = pd.DatetimeIndex(ts).tz_convert("America/New_York").normalize().tz_localize(None)
    uniq = pd.DatetimeIndex(sorted(set(d)))
    sess = np.searchsorted(uniq.values, d.values)
    starts = np.searchsorted(sess, np.arange(len(uniq)), side="left")
    ends = np.searchsorted(sess, np.arange(len(uniq)), side="right")
    return uniq, sess, starts, ends


def daily_ret(ts, eq):
    uniq, sess, starts, ends = sessions(ts)
    e = eq[ends - 1]
    r = np.r_[e[0] / 1e5 - 1, e[1:] / e[:-1] - 1]
    return pd.Series(r, index=uniq)


def baseline_w(ts):
    qd = pd.read_parquet(S.QQQ_DAILY)
    qd["date"] = pd.to_datetime(qd["date"]).dt.normalize()
    qd = qd.set_index("date")["close"].sort_index()
    return S.to_minutes(ts, S.baseline_daily_weights(qd.to_numpy()), pd.DatetimeIndex(qd.index))


def st(r):
    s = bt.stats(r, BARS)
    return {k: s[k] for k in ("cagr", "max_drawdown", "sharpe", "fills")}


def sub_cagr(ts, eq, y0, y1):
    dr = daily_ret(ts, eq)
    dr = dr[(dr.index.year >= y0) & (dr.index.year <= y1)]
    yrs = len(dr) / 252
    return float((1 + dr).prod() ** (1 / yrs) - 1)
