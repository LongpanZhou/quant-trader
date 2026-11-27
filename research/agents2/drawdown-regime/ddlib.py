"""Shared helpers for the drawdown-regime agent.

Loads the read-only 1m panel cached by the round-1 winner agent and implements
the winner's 165-day SMA regime + armed 4% minute stop, plus drawdown-based
overlays on top.

No look-ahead: every per-session signal for session k uses QQQ closes through
session k-1 only; the intraday stop checks bar i's close and fills at i+1 open.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

CACHE = ROOT / "research" / "agents" / "daily-regime-minute-entry" / "panel_cache.npz"
START10, START5, END = "2017-01-03", "2021-10-25", "2026-10-23"
BARS_PER_YEAR = 252 * 390


def load_panel(force: bool = False):
    """QQQ/TQQQ/BIL 1-minute opens and closes.

    Uses the read-only round-1 panel cache when present (identical to
    bt.panel); otherwise rebuilds it with bt.panel.
    """
    if CACHE.exists() and not force:
        z = np.load(CACHE)
        ts = pd.DatetimeIndex(
            pd.to_datetime(z["ts"], unit="ns", utc=True).tz_convert("America/New_York")
        )
        return ts, z["opens"], z["closes"]
    return bt.panel(("QQQ", "TQQQ", "BIL"), START10, END, "1min")


def day_bounds(dates):
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(dates) - 1]
    return first, last


def daily_context(ts, closes, sma_n=165, ma_fast=20):
    """Per-session arrays for the winner's regime and the DD state."""
    dates_bar = np.array([d for d in ts.date])
    first, last = day_bounds(dates_bar)
    dates = dates_bar[last]
    dc = closes[last, 0]
    n = len(dc)

    sma = pd.Series(dc).rolling(sma_n).mean().to_numpy()
    ma20 = pd.Series(dc).rolling(ma_fast).mean().to_numpy()
    high252 = pd.Series(dc).rolling(252, min_periods=200).max().to_numpy()

    reg = np.zeros(n, bool)          # risk-on for session k
    reg[1:] = dc[:-1] > sma[:-1]
    arm_ma20 = np.r_[np.nan, ma20[:-1]]       # MA20 through prior close
    hi_prev = np.r_[np.nan, high252[:-1]]     # trailing 52w high through k-1
    dd_prev = np.r_[np.nan, dc[:-1]] / hi_prev - 1.0
    dd_prev = np.where(np.isfinite(dd_prev), dd_prev, 0.0)
    hi_prev = np.where(np.isfinite(hi_prev), hi_prev, np.nan)

    # sessions since the trailing high was last set, through prior close
    uw = np.zeros(n, dtype=int)
    run = 0
    for k in range(1, n):
        if np.isfinite(hi_prev[k]) and dc[k - 1] >= hi_prev[k] * (1 - 1e-12):
            run = 0
        else:
            run += 1
        uw[k] = run

    # trailing 20-day high of daily closes through k-1 (recovery condition)
    hi20 = pd.Series(dc).rolling(20, min_periods=10).max().to_numpy()
    hi20_prev = np.r_[np.nan, hi20[:-1]]

    return dict(dates=dates, first=first, last=last, dclose=dc, sma=sma,
                ma20=ma20, reg=reg, arm_ma20=arm_ma20, dd_prev=dd_prev,
                hi_prev=hi_prev, uw=uw, hi20_prev=hi20_prev, n=n)


def dd_state(dctx, exit_thr, reenter_thr, scale=0.0, kind="dd"):
    """Per-session allowed TQQQ fraction from a daily drawdown state machine.

    kind='dd':  exit when dd_prev <= -exit_thr, re-enter when
                dd_prev >= -reenter_thr.
    kind='uw':  exit when underwater sessions >= exit_thr (int), re-enter when
                underwater sessions <= reenter_thr.
    scale:      fraction held while the de-risk state is on (0 = all BIL).
    """
    n = dctx["n"]
    frac = np.ones(n)
    if kind == "dd":
        x = dctx["dd_prev"]
        is_out = x <= -exit_thr
        is_in = x >= -reenter_thr
    else:
        x = dctx["uw"]
        is_out = x >= exit_thr
        is_in = x <= reenter_thr
    blocked = False
    for k in range(n):
        if not dctx["reg"][k]:
            frac[k] = 0.0
            continue
        if blocked:
            if is_in[k]:
                blocked = False
        else:
            if is_out[k]:
                blocked = True
        frac[k] = float(scale) if blocked else 1.0
    return frac


def render(ts, opens, closes, dctx, frac, stop=0.04, arm_buf=0.01,
           dd_intraday=None, rec_thr=None):
    """Apply the winner's intraday stop on top of a per-session fraction.

    dd_intraday: (thr,) -> exit intraday when QQQ's close is below
                 hi_prev * (1-thr); stay out until dd_prev >= -rec_thr.
    """
    first, last = dctx["first"], dctx["last"]
    n = len(ts)
    qqq_close = closes[:, 0]
    tqqq_close = closes[:, 1]

    hold = np.zeros(n, dtype=float)
    stops, ddexit = [], []
    sticky = False
    for k, (f, l) in enumerate(zip(first, last)):
        if not dctx["reg"][k]:
            continue
        if sticky:
            if rec_thr is not None and dctx["dd_prev"][k] >= -rec_thr:
                sticky = False
            else:
                continue
        f_k = float(frac[k])
        if f_k <= 0:
            continue
        armed = bool(np.isfinite(dctx["arm_ma20"][k])
                     and qqq_close[f] < dctx["arm_ma20"][k] * (1.0 + arm_buf))
        base = opens[f, 1]
        on = True
        for i in range(f, l + 1):
            if on and armed and tqqq_close[i] < base * (1.0 - stop):
                on = False
                stops.append((str(dctx["dates"][k]), str(ts[i].time())))
            if on and dd_intraday is not None and np.isfinite(dctx["hi_prev"][k]):
                if qqq_close[i] < dctx["hi_prev"][k] * (1.0 - dd_intraday):
                    on = False
                    sticky = True
                    ddexit.append((str(dctx["dates"][k]), str(ts[i].time())))
            hold[i] = f_k if on else 0.0

    w = np.zeros((n, 3))
    w[:, 1] = hold
    w[:, 2] = 1.0 - hold
    diag = dict(stop_events=len(stops), stops=stops[:10],
                dd_intraday_exits=len(ddexit), dd_exits=ddexit[:10],
                mean_frac=float(frac.mean()))
    return w, diag


def summary(ts, opens, closes, w, slippage_bps=1.0, starts=(START10, START5),
            band=0.02):
    import fastsim
    out = {}
    for start in starts:
        i = bt.start_index(ts, start)
        r = fastsim.simulate(ts[i:], opens[i:], closes[i:], w[i:],
                             band=band, slippage_bps=slippage_bps)
        s = bt.stats(r, BARS_PER_YEAR)
        s["bench"] = bt.benchmark(closes[i:, 1], ts[i:], BARS_PER_YEAR)
        s["yearly"] = bt.yearly(ts[i:], r["equity"], closes[i:, 1])
        s["result"] = r
        out[start] = s
    return out


def fmt(label, out, starts=(START10, START5)):
    parts = []
    for st in starts:
        s = out[st]
        parts.append(f"{st[:4]} {s['cagr']*100:6.2f}/{s['max_drawdown']*100:5.2f}  "
                     f"Sh {s['sharpe']:4.2f}  f{s['fills']:5d}")
    print(f"{label:38s} " + " | ".join(parts))
    return out


def rolling3y(ts, opens, closes, w, start=START10, end=END, months=36,
              step_months=1, slippage_bps=1.0):
    """Rolling 3-year windows: strategy vs TQQQ."""
    edges = []
    t0 = pd.Timestamp(start, tz="America/New_York")
    t_end = pd.Timestamp(end, tz="America/New_York")
    cur = t0
    while True:
        nxt = cur + pd.DateOffset(months=months)
        if nxt > t_end:
            break
        edges.append((cur, nxt))
        cur = cur + pd.DateOffset(months=step_months)
    rows = []
    for a, b in edges:
        i = bt.start_index(ts, str(a.date()))
        j = int(np.searchsorted(ts, b))
        r = _run_slice(ts, opens, closes, w, i, j, slippage_bps)
        eq = r["equity"]
        if len(eq) < 100:
            continue
        s = _stats_from_equity(eq, ts[i:j])
        bm = bt.benchmark(closes[i:j, 1], ts[i:j], BARS_PER_YEAR)
        rows.append(dict(start=str(a.date()), end=str(b.date()),
                         cagr=s["cagr"], dd=s["max_drawdown"],
                         bcagr=bm["cagr"], bdd=bm["max_drawdown"]))
    return rows


def _run_slice(ts, opens, closes, w, i, j, slippage_bps):
    import fastsim
    return fastsim.simulate(ts[i:j], opens[i:j], closes[i:j], w[i:j],
                            band=0.02, slippage_bps=slippage_bps)


def _stats_from_equity(eq, ts):
    years = (ts[-1] - ts[0]).total_seconds() / (365.25 * 86400)
    peak = np.maximum.accumulate(eq)
    return dict(cagr=(eq[-1] / eq[0]) ** (1 / years) - 1,
                max_drawdown=float(-(eq / peak - 1).min()),
                years=years)
