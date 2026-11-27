"""Variant builder for the tuning sweep (dev only). Reuses strategy.py's helpers."""
import sys
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent)); sys.path.insert(0, str(HERE.parents[2]))
import bt, strategy as S
ROOT = HERE.parents[3]

EXTRA = dict(recovery_asset="tqqq", tqqq_units="qqq", normal_asset="qqq", warmup=False,
             pct_excl_self=False, placebo_seed=None)


def warm_daily(daily):
    y = pd.read_parquet(ROOT / "data" / "intraday-hf" / "QQQ-1d-yahoo.parquet")
    y.index = pd.to_datetime(y["date"]); y = y["adjclose"]
    first = daily.index[0].tz_localize(None).normalize()
    pre = y[y.index < first]
    if len(pre) == 0:
        return daily, 0
    pre.index = pre.index.tz_localize(daily.index.tz)
    return pd.concat([pre, daily]), len(pre)


def states_for(daily, p):
    rv_fast = S._realized_vol(daily, int(p["vol_fast"])); rv_mid = S._realized_vol(daily, int(p["vol_mid"]))
    if p["pct_excl_self"]:
        win = int(p["pct_window"])
        vals = rv_mid.to_numpy(float); pct = np.full(len(vals), np.nan)
        mp = max(60, win // 2)
        for i in range(len(vals)):
            h = vals[max(0, i - win):i]; h = h[np.isfinite(h)]
            if np.isfinite(vals[i]) and len(h) >= mp:
                pct[i] = (h <= vals[i]).mean()
        pct = pd.Series(pct, index=rv_mid.index)
    else:
        pct = S._percentile_rank(rv_mid, int(p["pct_window"]))
    slope = rv_fast / rv_mid.replace(0.0, np.nan) - 1.0
    raw = np.array([S._raw_state(pct.iloc[i], slope.iloc[i], stress_pct=float(p["stress_pct"]), calm_pct=float(p["calm_pct"]),
                    stress_slope=float(p["stress_slope"]), complacency_slope=float(p["complacency_slope"])) for i in range(len(daily))], dtype=object)
    st = S._state_path(raw, slope.to_numpy(float), min_hold=int(p["min_hold"]), max_recovery=int(p["max_recovery"]), reaccel_slope=float(p["reaccel_slope"]))
    return st, rv_mid.to_numpy(float)


def placebo(st, seed):
    """Shuffle the order of state runs (same run lengths and label mix)."""
    runs = []; cur = st[0]; n = 0
    for s in st:
        if s == cur:
            n += 1
        else:
            runs.append((cur, n)); cur, n = s, 1
    runs.append((cur, n))
    rng = np.random.default_rng(seed); rng.shuffle(runs)
    return np.array([s for s, k in runs for _ in range(k)], dtype=object)


def target(state, rv, p):
    if state in ("panic", "complacency") or not np.isfinite(rv) or rv <= 0:
        return (0.0, 0.0, 1.0)
    mw = float(p["max_weight"])
    if state == "recovery":
        a = p["recovery_asset"]
        if a == "bil":
            return (0.0, 0.0, 1.0)
        if a == "tqqq":
            div = 3.0 if p["tqqq_units"] == "tqqq" else 1.0
            wt = min(mw, float(p["tqqq_vol_target"]) / (div * rv)); return (0.0, wt, 1.0 - wt)
        state = "normal"
    if p["normal_asset"] == "tqqq":
        wt = min(mw, float(p["qqq_vol_target"]) / (3.0 * rv)); return (0.0, wt, 1.0 - wt)
    wq = min(mw, float(p["qqq_vol_target"]) / rv); return (wq, 0.0, 1.0 - wq)


def build(ts, opens, closes, **ov):
    p = dict(S.DEFAULTS); p.update(EXTRA); p.update(ov)
    daily = S.daily_closes(ts, closes); npre = 0
    if p["warmup"]:
        daily, npre = warm_daily(daily)
    st, rv = states_for(daily, p)
    if p["placebo_seed"] is not None:
        st = np.r_[st[:npre], placebo(st[npre:], p["placebo_seed"])]
    day_map = {d: i for i, d in enumerate(pd.Index(daily.index.date))}
    dv = np.asarray(ts.date)
    bod = np.r_[0, np.flatnonzero(dv[1:] != dv[:-1]) + 1]; eod = np.r_[bod[1:], len(ts)]
    w = np.zeros((len(ts), 3)); w[:, 2] = 1.0
    for b, e in zip(bod, eod):
        di = day_map.get(dv[b])
        if di is None:
            continue
        w[b:e] = target(st[di], rv[di], p)
        nd = di + 1 if di + 1 < len(daily) else di
        w[e - 1] = target(st[nd], rv[nd], p)
    return w, st[npre:], pd.Index(daily.index.date)[npre:]
