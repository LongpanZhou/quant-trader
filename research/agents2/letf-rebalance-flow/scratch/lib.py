"""Shared helpers for the LETF end-of-day rebalancing study."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "research")
import bt

HERE = Path(__file__).resolve().parents[1]
CACHE = HERE / "panel_cache.npz"


def load_panel():
    z = np.load(CACHE)
    ts = pd.DatetimeIndex(z["ts"]).tz_localize("UTC").tz_convert("America/New_York")
    return ts, z["opens"], z["closes"]


def session_info(ts):
    dates = ts.normalize()
    uniq = pd.DatetimeIndex(sorted(set(dates)))
    sess = np.searchsorted(uniq.values, dates.values)
    mins = (ts.hour * 60 + ts.minute) - (9 * 60 + 30)
    return uniq, sess, mins


def session_bounds(sess, n_sess):
    """Start/end bar index for each session (sess is sorted)."""
    starts = np.searchsorted(sess, np.arange(n_sess), side="left")
    ends = np.searchsorted(sess, np.arange(n_sess), side="right")
    return starts, ends


def daily_close(ts, closes, sess, mins, n_sess, col=0):
    """Last trade of each session (handles 13:00 half-days)."""
    starts, ends = session_bounds(sess, n_sess)
    out = np.full(n_sess, np.nan)
    ok = ends > starts
    out[ok] = closes[ends[ok] - 1, col]
    return out


def session_series(values, sess, mins, n_sess, minute):
    out = np.full(n_sess, np.nan)
    sel = mins == minute
    out[sess[sel]] = values[sel]
    return out


def winner_daily(ts, opens, closes):
    """Per-session arrays for the round-1 winner."""
    uniq, sess, mins = session_info(ts)
    n_sess = len(uniq)
    starts, ends = session_bounds(sess, n_sess)
    qclose = daily_close(ts, closes, sess, mins, n_sess, 0)
    s = pd.Series(qclose)
    sma165 = s.rolling(165).mean().shift(1).to_numpy()
    ma20 = s.rolling(20).mean().shift(1).to_numpy()
    prev = s.shift(1).to_numpy()
    risk_on = prev > sma165

    first_close = np.full(n_sess, np.nan)
    sel = mins == 0
    first_close[sess[sel]] = closes[sel, 0]
    armed = first_close < ma20 * 1.01

    topen = np.full(n_sess, np.nan)
    topen[sess[sel]] = opens[sel, 1]

    stop_min = np.full(n_sess, 999, dtype=int)
    for k in range(n_sess):
        if not risk_on[k] or not armed[k] or not np.isfinite(topen[k]):
            continue
        idx = np.arange(starts[k], ends[k])
        bad = idx[closes[idx, 1] < topen[k] * 0.96]
        if len(bad):
            stop_min[k] = mins[bad[0]]
    return dict(dates=uniq, risk_on=risk_on, armed=armed, stop_min=stop_min,
                sma165=sma165, ma20=ma20, qclose=qclose, topen=topen,
                starts=starts, ends=ends, sess=sess, mins=mins)


def base_winner_weights(ts, wd):
    n = len(ts)
    sess = wd["sess"]
    mins = wd["mins"]
    starts, ends = wd["starts"], wd["ends"]
    n_sess = len(wd["dates"])
    w = np.zeros((n, 3))
    for k in range(n_sess):
        a, b = starts[k], ends[k]
        if b <= a:
            continue
        if wd["risk_on"][k]:
            stop = wd["stop_min"][k]
            hold = mins[a:b] < stop
            w[a:b][hold, 1] = 1.0
            w[a:b][~hold, 2] = 1.0
        else:
            w[a:b, 2] = 1.0
    return w


def weights_from_rules(ts, opens, closes, wd, late_rules=None, base_weights=None):
    """Build per-bar weights. late_rules are pre-resolved session masks."""
    if base_weights is not None:
        w = base_weights.copy()
    else:
        w = base_winner_weights(ts, wd)
    if not late_rules:
        return w
    mins, starts, ends = wd["mins"], wd["starts"], wd["ends"]
    for rule in late_rules:
        mask = rule["mask"]
        long_side = rule["long"]
        overnight = rule.get("overnight")
        protect = rule.get("protect_stop", True)
        for k in np.where(mask)[0]:
            a, b = starts[k], ends[k]
            if b <= a:
                continue
            m = mins[a:b]
            sel = (m >= rule["entry_min"]) & (m <= rule["exit_min"])
            if not sel.any():
                continue
            if long_side:
                w[a:b][sel, 1] = 1.0
                w[a:b][sel, 2] = 0.0
            else:
                w[a:b][sel, 1] = 0.0
                w[a:b][sel, 2] = 1.0
            stopped = base_weights is not None and base_weights[b - 1, 1] < 0.5
            if overnight is True and not (protect and stopped):
                w[b - 1, 1] = 1.0
                w[b - 1, 2] = 0.0
            elif overnight is False:
                w[b - 1, 1] = 0.0
                w[b - 1, 2] = 1.0
    return w


def fmt(s, b=None):
    out = (f"CAGR {s['cagr']*100:6.2f}%  DD {s['max_drawdown']*100:5.2f}%  "
           f"Sharpe {s['sharpe']:4.2f}  fills {s['fills']:,}  turn {s['turnover']:.0f}x")
    if b:
        out += f"  | bench CAGR {b['cagr']*100:6.2f}% DD {b['max_drawdown']*100:5.2f}%"
    return out


def daily_equity(ts, equity):
    dates = ts.normalize()
    uniq = pd.DatetimeIndex(sorted(set(dates)))
    sess = np.searchsorted(uniq.values, dates.values)
    starts, ends = session_bounds(sess, len(uniq))
    out = np.full(len(uniq), np.nan)
    ok = ends > starts
    out[ok] = equity[ends[ok] - 1]
    return uniq, out


def window_stats(ts, equity, start, end=None):
    mask = ts >= pd.Timestamp(start, tz="America/New_York")
    if end:
        mask &= ts < pd.Timestamp(end, tz="America/New_York")
    e = equity[mask]
    t = ts[mask]
    yrs = (t[-1] - t[0]).total_seconds() / (365.25 * 86400)
    peak = np.maximum.accumulate(e)
    return dict(cagr=(e[-1] / e[0]) ** (1 / yrs) - 1, dd=float(-(e / peak - 1).min()),
                years=yrs, start=str(t[0].date()), end=str(t[-1].date()))
