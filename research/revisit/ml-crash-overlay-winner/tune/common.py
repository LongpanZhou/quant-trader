"""Shared helpers for the 2026-11-27 tuning study (dev window only)."""
import sys, warnings; warnings.filterwarnings("ignore")
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(ROOT / "research"))
import numpy as np, pandas as pd
import bt
from minute_marks import to_minutes
import strategy as S
assert S.DEV_END == "2023-12-29"
BARS = 252 * 390

ts1, o1, c1 = bt.panel(S.SYMS, S.DEV_START, S.DEV_END, "1min")
tsd, od, cd = bt.panel(S.SYMS, S.DEV_START, S.DEV_END, "1D")
assert ts1[-1] < pd.Timestamp("2023-12-30", tz="America/New_York")
dts = pd.DatetimeIndex(tsd).tz_localize(None)
_vol = bt.load_1m("QQQ").set_index("ts")["volume"].reindex(ts1).fillna(0.0).to_numpy()
F = S.build_features(ts1, o1, c1, np.column_stack([_vol, _vol, _vol]))
F.index = pd.DatetimeIndex(F.index); F = F.reindex(dts).ffill()
X = F[S.FEATURES].to_numpy()
DECAY = S.forward_decay(od, cd, S.HORIZON)
_pc = {}


def probs(label_q=S.LABEL_Q, window=S.WINDOW, lam=S.LAM, feats=None):
    key = (label_q, window, lam, tuple(feats) if feats else None)
    if key not in _pc:
        x = X if feats is None else F[list(feats)].to_numpy()
        _pc[key] = S.walk_forward_decay(dts, x, DECAY, label_q=label_q, window=window, lam=lam)[0]
    return _pc[key]


def rank_of(p, rw=S.RANK_WINDOW):
    return pd.Series(p).rolling(rw, min_periods=(60 if rw >= 252 else 40)).rank(pct=True).to_numpy()


def minutes(wd):
    return to_minutes(tsd, wd, ts1, "1D")


def run(wd, slip=1.0, start=S.DEV_START):
    return bt.run(ts1, o1, c1, minutes(wd), start, band=0.02, slippage_bps=slip)


def run_many(wds, slip=1.0, start=S.DEV_START):
    return bt.run_many(ts1, o1, c1, [minutes(w) for w in wds], start=start, band=0.02,
                       slippage_bps=slip)


def st(r):
    return bt.stats(r, BARS)


def daily_ret(r):
    eq = pd.Series(r["equity"], index=r["ts"])
    d = eq.groupby(eq.index.date).last(); d.index = pd.DatetimeIndex(d.index)
    first = r["equity"][0]
    return pd.concat([pd.Series([first], index=[d.index[0] - pd.Timedelta(days=1)]), d]).pct_change().dropna()


_base = []


def base_daily():
    if not _base:
        _base.append(daily_ret(run(S.baseline_weights(tsd, cd))))
    return _base[0]


def corr_base(r):
    a, b = daily_ret(r), base_daily()
    i = a.index.intersection(b.index)
    return float(np.corrcoef(a.loc[i], b.loc[i])[0, 1])


def sub_stats(r, a, b):
    ts = r["ts"]; m = (ts >= pd.Timestamp(a, tz=ts.tz)) & (ts < pd.Timestamp(b, tz=ts.tz))
    e = r["equity"][m]; yrs = (ts[m][-1] - ts[m][0]).total_seconds() / (365.25 * 86400)
    rets = np.diff(e) / e[:-1]
    dd = float(-(e / np.maximum.accumulate(e) - 1).min())
    sh = float(rets.mean() / rets.std() * np.sqrt(BARS))
    return {"cagr": float((e[-1] / e[0]) ** (1 / yrs) - 1), "dd": dd, "sharpe": sh}


SUBS = [("2016-01-01", "2020-01-01"), ("2020-01-01", "2022-01-01"), ("2022-01-01", "2024-01-01")]


def subs(r):
    return {f"{a[:4]}-{int(b[:4]) - 1}": sub_stats(r, a, b) for a, b in SUBS}


def onehot(state):
    w = np.zeros((len(state), 3))
    for k in (0, 1, 2):
        w[state == k, k] = 1.0
    return w
