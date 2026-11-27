"""Shared library for the intraday-seasonality round-2 agent.

Fast next-open simulator (validated against research/bt.py), the round-1 winner
baseline, calendar masks, overlay helpers and metric helpers.

Signals use bars <= i; every fill is at bar i+1's open.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

OUT = Path(__file__).resolve().parent
CACHE = OUT / "panel.npz"
START10, START5, END = "2017-01-03", "2021-10-25", "2026-10-23"
SMA_N = 165
MA_FAST = 20
STOP = 0.04
ARM_BUF = 0.01
BARS_PER_YEAR = 252 * 390


# ---------------------------------------------------------------- data
def load_panel(force: bool = False):
    if CACHE.exists() and not force:
        z = np.load(CACHE, allow_pickle=True)
        ts = pd.DatetimeIndex(pd.to_datetime(z["ts"], unit="ns", utc=True).tz_convert("America/New_York"))
        return ts, z["opens"], z["closes"]
    ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), START10, END, "1min", warmup_days=500)
    np.savez_compressed(
        CACHE,
        ts=ts.tz_convert("UTC").tz_localize(None).to_numpy(dtype="datetime64[ns]").astype("int64"),
        opens=opens, closes=closes,
    )
    return ts, opens, closes


def day_bounds(dates: np.ndarray):
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(dates) - 1]
    return first, last


def time_index(ts: pd.DatetimeIndex, first: np.ndarray, last: np.ndarray, hh: int, mm: int) -> np.ndarray:
    """Index of the first bar at or after hh:mm in each session."""
    target = hh * 60 + mm
    mins = ts.hour.to_numpy() * 60 + ts.minute.to_numpy()
    out = np.empty(len(first), dtype=np.int64)
    for k, (f, l) in enumerate(zip(first, last)):
        j = np.searchsorted(mins[f:l + 1], target)
        out[k] = min(f + j, l)
    return out


# ---------------------------------------------------------------- simulator
def simulate(ts, opens, closes, weights, slippage_bps: float = 1.0,
             start_equity: float = 100_000.0) -> dict:
    """Delegates to bt.simulate (compiled Rust core) with the usual 2% band.

    This used to be a vectorised approximation of bt.simulate (returns
    compounded from fractional holdings, band applied only to fully-invested
    rows, turnover in units of book). It now uses the exact harness, so
    turnover is traded notional / start equity like every other agent.
    """
    return bt.simulate(ts, opens, closes, weights, band=0.02,
                       slippage_bps=slippage_bps, start_equity=start_equity)


def window(result: dict, ts: pd.DatetimeIndex, start: str, end: str | None = None) -> dict:
    i = bt.start_index(ts, start)
    j = bt.start_index(ts, end) if end else len(ts)
    eq = result["equity"][i:j]
    eq = eq / eq[0] * 100_000.0
    t = ts[i:j]
    rets = np.diff(eq) / eq[:-1]
    years = (t[-1] - t[0]).total_seconds() / (365.25 * 86400)
    peak = np.maximum.accumulate(eq)
    downside = np.minimum(rets, 0.0)
    return {
        "ts": t, "equity": eq, "cagr": float((eq[-1] / eq[0]) ** (1 / years) - 1),
        "max_drawdown": float(-(eq / peak - 1).min()),
        "volatility": float(np.std(rets, ddof=0) * np.sqrt(BARS_PER_YEAR)),
        "sharpe": float(np.mean(rets) / np.std(rets, ddof=0) * np.sqrt(BARS_PER_YEAR)),
        "sortino": float(np.mean(rets) / np.sqrt(np.mean(downside ** 2)) * np.sqrt(BARS_PER_YEAR)),
        "total_return": float(eq[-1] / eq[0] - 1.0),
        "ending_equity": float(eq[-1]), "years": years,
    }


def daily_marks(w: dict) -> np.ndarray:
    ts, eq = w["ts"], w["equity"]
    d = np.array([t.date() for t in ts])
    _, last = day_bounds(d)
    return eq[last]


def bench_window(ts, close, start):
    return window({"equity": close, "ts": ts}, ts, start)


# ---------------------------------------------------------------- regime / winner
def build_base(ts, opens, closes, armed_mask: np.ndarray | None = None,
               stop: float = STOP, sma_n: int = SMA_N, arm_buf: float = ARM_BUF):
    """Round-1 winner: 165d SMA regime, 4% intraday stop armed below MA20(+1%).

    armed_mask: optional bool per session to enable/disable the arming rule.
    """
    dates = np.array([t.date() for t in ts])
    first, last = day_bounds(dates)
    n = len(ts)
    qqq_close = closes[:, 0]
    tqqq_close = closes[:, 1]
    dclose = qqq_close[last]
    sma = pd.Series(dclose).rolling(sma_n).mean().to_numpy()
    ma20 = pd.Series(dclose).rolling(MA_FAST).mean().to_numpy()
    sma_prev = np.r_[np.nan, sma[:-1]]
    ma20_prev = np.r_[np.nan, ma20[:-1]]
    day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, n]))

    hold = np.zeros(n, dtype=bool)
    stops = []
    for k, (f, l) in enumerate(zip(first, last)):
        risk_on = bool(k > 0 and sma_prev[k] == sma_prev[k] and dclose[k - 1] > sma_prev[k])
        if not risk_on:
            continue
        armed = bool(ma20_prev[k] == ma20_prev[k] and qqq_close[f] < ma20_prev[k] * (1.0 + arm_buf))
        if armed_mask is not None:
            armed = armed and bool(armed_mask[k])
        base = opens[f, 1]
        state = True
        for i in range(f, l + 1):
            if armed and state and tqqq_close[i] < base * (1.0 - stop):
                state = False
                stops.append((str(dates[f]), str(ts[i].time())))
            hold[i] = state

    w = np.zeros((n, 3))
    w[:, 1] = hold.astype(float)
    w[:, 2] = 1.0 - w[:, 1]
    diag = {"days": int(len(first)), "stop_events": len(stops), "stops": stops}
    return w, diag


def regime_on(ts, closes) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per-session bool: QQQ prior close > 165d SMA (signal at prior close)."""
    dates = np.array([t.date() for t in ts])
    first, last = day_bounds(dates)
    dclose = closes[last, 0]
    sma = pd.Series(dclose).rolling(SMA_N).mean().to_numpy()
    on = np.zeros(len(dclose), bool)
    on[1:] = dclose[:-1] > sma[:-1]
    return on, first, last


# ---------------------------------------------------------------- calendar
def holiday_flags(dates: np.ndarray):
    d = pd.DatetimeIndex(pd.to_datetime(list(dates)))
    weekdays = pd.bdate_range(d[0], d[-1])
    missing = weekdays.difference(d)
    pre = np.zeros(len(d), bool)
    post = np.zeros(len(d), bool)
    pos = {x: i for i, x in enumerate(d)}
    for m in missing:
        before = m - pd.Timedelta(days=1)
        while before not in pos and before > d[0]:
            before -= pd.Timedelta(days=1)
        after = m + pd.Timedelta(days=1)
        while after not in pos and after < d[-1]:
            after += pd.Timedelta(days=1)
        if before in pos:
            pre[pos[before]] = True
        if after in pos:
            post[pos[after]] = True
    return pre, post


def opex_flags(dates: np.ndarray):
    d = pd.DatetimeIndex(pd.to_datetime(list(dates)))
    third = []
    for p in pd.period_range(d[0], d[-1], freq="M"):
        first = p.to_timestamp()
        fridays = [first + pd.Timedelta(days=k) for k in range(31)
                   if (first + pd.Timedelta(days=k)).month == first.month
                   and (first + pd.Timedelta(days=k)).day_of_week == 4]
        third.append(fridays[2])
    third = pd.DatetimeIndex(third)
    week_start = third - pd.to_timedelta(third.day_of_week, unit="D")
    opex = np.zeros(len(d), bool)
    prew = np.zeros(len(d), bool)
    postw = np.zeros(len(d), bool)
    for ws in week_start:
        we = ws + pd.Timedelta(days=4)
        opex |= (d >= ws) & (d <= we)
        prew |= (d >= ws - pd.Timedelta(days=7)) & (d <= we - pd.Timedelta(days=7))
        postw |= (d >= ws + pd.Timedelta(days=7)) & (d <= we + pd.Timedelta(days=7))
    return opex, prew, postw


def calendar(ts) -> dict:
    dates = np.array([t.date() for t in ts])
    first, last = day_bounds(dates)
    d = pd.DatetimeIndex(pd.to_datetime([x for x in dates[first]]))
    pre, post = holiday_flags(dates[first])
    op, prew, postw = opex_flags(dates[first])
    return {
        "dates": d, "dow": d.day_of_week.to_numpy(), "year": d.year.to_numpy(),
        "month": d.month.to_numpy(),
        "pre_hol": pre, "post_hol": post,
        "opex": op, "pre_opex": prew, "post_opex": postw,
        "first": first, "last": last,
    }


# ---------------------------------------------------------------- overlays
def carve(w: np.ndarray, cal: dict, start_hhmm: tuple[int, int], end_hhmm: tuple[int, int],
          ts: pd.DatetimeIndex, day_mask: np.ndarray, asset: int = 2) -> np.ndarray:
    """On masked sessions, replace TQQQ with `asset` inside [start,end).

    Weights are filled at the next bar's open, so the carve sets the weight at
    the `start` bar (out at start+1min) and restores it at the bar *before*
    `end` (back in at end).  Hence the position is out from start+1 to end.
    """
    out = w.copy()
    si = time_index(ts, cal["first"], cal["last"], *start_hhmm)
    ei = time_index(ts, cal["first"], cal["last"], *end_hhmm)
    for k in np.flatnonzero(day_mask):
        f, l = cal["first"][k], cal["last"][k]
        a, b = si[k], ei[k] - 2
        a, b = max(a, f), min(b, l)
        if b < a:
            continue
        out[a:b + 1, :] = 0.0
        out[a:b + 1, asset] = 1.0
    return out


def apply_stop_gate(ts, opens, closes, gate: np.ndarray, **kw):
    return build_base(ts, opens, closes, armed_mask=gate, **kw)


# ---------------------------------------------------------------- metrics
def rolling3(ts, equity, starts, months=36):
    """CAGR/DD over rolling 3-year windows beginning at each requested timestamp."""
    out = []
    idx = np.searchsorted(ts, pd.DatetimeIndex(starts))
    for i0, s in zip(idx, starts):
        j0 = int(i0)
        j1 = int(np.searchsorted(ts, pd.Timestamp(s) + pd.DateOffset(months=months)))
        if j1 <= j0 + 100 or j1 > len(ts):
            continue
        e = equity[j0:j1]
        yrs = (ts[j1 - 1] - ts[j0]).total_seconds() / (365.25 * 86400)
        peak = np.maximum.accumulate(e)
        out.append({"start": str(pd.Timestamp(s).date()),
                    "cagr": float((e[-1] / e[0]) ** (1 / yrs) - 1),
                    "dd": float(-(e / peak - 1).min())})
    return out


def yearly_table(ts, equity, start):
    i = bt.start_index(ts, start)
    e = equity[i:]
    t = ts[i:]
    out = {}
    for y in sorted(set(t.year)):
        m = t.year == y
        if m.sum() < 2:
            continue
        out[int(y)] = float(e[m][-1] / e[m][0] - 1)
    return out
