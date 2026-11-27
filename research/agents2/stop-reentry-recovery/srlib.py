"""Shared helpers for the stop re-entry / recovery study.

Conventions match research/bt.py: weight[i] is a target set from the close of
bar i and filled at the open of bar i+1.  Every signal uses only bars <= i.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import prep  # noqa: E402

START10, START5, END = "2017-01-03", "2021-10-25", "2026-10-23"
SMA_N, MA_N = 165, 20
STOP, ARM_BUF = 0.04, 0.01
BPY = 252 * 390

_DAYS = None


def arrays():
    global _DAYS
    ts, o, h, l, c, v = prep.build()
    dates = np.array([d for d in ts.date])
    first, last = prep.day_bounds(dates)
    _DAYS = (ts, dates, first, last)
    return dict(ts=ts, dates=dates, first=first, last=last, o=o, h=h, l=l, c=c, v=v)


def regime(ts, qqq_c, first, last):
    """Daily SMA165 regime and MA20, both through the prior close, per minute."""
    dc = qqq_c[last]
    sma = pd.Series(dc).rolling(SMA_N).mean().to_numpy()
    ma20 = pd.Series(dc).rolling(MA_N).mean().to_numpy()
    reg_day = np.zeros(len(dc), bool)
    ma20_prev_day = np.full(len(dc), np.nan)
    reg_day[1:] = dc[:-1] > sma[:-1]
    ma20_prev_day[1:] = ma20[:-1]
    day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, len(ts)]))
    return reg_day[day_id], ma20_prev_day[day_id]


def session_vwap(h, l, c, v, first, last):
    tp = (h + l + c) / 3.0
    out = np.empty(len(c))
    for f, z in zip(first, last):
        cs = np.cumsum(tp[f:z + 1, 1] * v[f:z + 1, 1])
        cv = np.cumsum(v[f:z + 1, 1])
        with np.errstate(invalid="ignore", divide="ignore"):
            x = np.where(cv > 0, cs / cv, np.nan)
        out[f:z + 1] = np.where(np.isfinite(x), x, tp[f:z + 1, 1])
    return out


def session_ema(c, first, last, bucket, span, col=1):
    """EMA of `bucket`-minute closes, exposed only on later minutes (no look-ahead).

    Minute m sees the EMA of all buckets that closed strictly before m's bucket.
    """
    out = np.full(len(c), np.nan)
    for f, z in zip(first, last):
        m = z - f + 1
        nb = m // bucket
        if nb < 2:
            continue
        bc = c[f + bucket - 1: f + nb * bucket: bucket, col]
        e = pd.Series(bc).ewm(span=span, adjust=False).mean().to_numpy()
        for b in range(1, nb):
            out[f + b * bucket: f + (b + 1) * bucket] = e[b - 1]
    return out


def base_weights(A, reg, ma20_prev, always_armed=False):
    """Round-1 winner, verbatim: 4% stop, armed, out rest of day + night."""
    ts, first, last = A["ts"], A["first"], A["last"]
    o, c = A["o"], A["c"]
    n = len(ts)
    hold = np.zeros(n, bool)
    stops = []
    for k, (f, z) in enumerate(zip(first, last)):
        if not reg[f]:
            continue
        armed = True if always_armed else bool(
            ma20_prev[f] == ma20_prev[f] and c[f, 0] < ma20_prev[f] * (1 + ARM_BUF))
        base = o[f, 1]
        state = True
        for i in range(f, z + 1):
            if armed and state and c[i, 1] < base * (1 - STOP):
                state = False
                stops.append(i)
            hold[i] = state
    w = np.zeros((n, 3))
    w[:, 1] = hold.astype(float)
    w[:, 2] = 1.0 - w[:, 1]
    return w, dict(stop_bars=np.array(stops), stop_days=len(np.unique([ts[i].date() for i in stops])))


def make_weights(A, reg, ma20_prev, vwap, ema5, ema5b, ema15,
                 mode="base", confirm=1, buffer=0.0, tight=0.0, vwap_fail=0.0,
                 t_start=0, t_end=390, ema_line=None, overnight_cond="stoplevel",
                 block_next_on_weak_close=False, size=1.0, always_armed=False,
                 block_frac=1.0, block_mask=None, next_day_tight=0.0,
                 next_day_tight_weak_only=False, next_day_tight_armed_only=False,
                 tight_chain=True, tight_anchor="open", block_stop=0.0,
                 block_stop_anchor="entry", block_overnight=True):
    """Per-day state machine with optional same-day re-entry.

    mode:
      base      winner, no re-entry
      vwap      re-enter when TQQQ closes above session VWAP (confirm bars)
      ema5      re-enter on TQQQ reclaim of the 5-minute EMA
      ema15     re-enter on TQQQ reclaim of the 15-minute EMA
      qqqma     re-enter when QQQ closes above its prior-day 20-day SMA
      overnight re-enter at 15:59 only if the close recovered
      nextday   winner, but block the next session's entry if the stop-day
                close is weak (close < open*0.96)
    """
    ts, first, last = A["ts"], A["first"], A["last"]
    o, c = A["o"], A["c"]
    n = len(ts)
    hold = np.zeros(n)
    diag = dict(reentries=[], second_stops=[], overnight=0, blocked_days=0, stops=[],
                tight_days=0, tight_stops=0, block_stops=0, blocked_dates=[],
                tight_dates=[], tight_stop_dates=[])
    prev_stop_weak = False
    line = {"vwap": vwap, "ema5": ema5, "ema15": ema15, "ema5b": ema5b}.get(ema_line or mode)

    prev_stopped = False
    for k, (f, z) in enumerate(zip(first, last)):
        if not reg[f]:
            prev_stop_weak = False
            prev_stopped = False
            continue
        do_block = (block_next_on_weak_close and prev_stop_weak
                    and (block_mask is None or bool(block_mask[f])))
        if do_block:
            diag["blocked_days"] += 1
            diag["blocked_dates"].append(A["dates"][f])
            if block_stop > 0:
                pos = 1.0 - block_frac
                anchor = o[f + 1, 1] if block_stop_anchor == "entry" else o[f, 1]
                for i in range(f, z + 1):
                    if i > f and pos > 0 and c[i, 1] < anchor * (1 - block_stop):
                        pos = 0.0
                        diag["tight_stops"] += 1
                        diag["block_stops"] += 1
                    hold[i] = pos
            elif block_overnight:
                hold[f:z + 1] = 1.0 - block_frac
            else:
                hold[f:z + 1] = 1.0 - block_frac
                hold[max(f, z - 1):z + 1] = 0.0   # exit at the 15:59 open
            prev_stop_weak = False
            prev_stopped = False
            continue
        prior_weak = prev_stop_weak
        was_stopped = prev_stopped
        prev_stop_weak = False
        prev_stopped = False
        armed = True if always_armed else bool(
            ma20_prev[f] == ma20_prev[f] and c[f, 0] < ma20_prev[f] * (1 + ARM_BUF))
        day_stop = STOP
        anchor_entry = False
        if was_stopped and next_day_tight > 0:
            if next_day_tight_weak_only and not prior_weak:
                pass
            elif next_day_tight_armed_only and not armed:
                pass
            else:
                day_stop = next_day_tight
                armed = True
                anchor_entry = tight_anchor == "entry"
                diag["tight_days"] += 1
                diag["tight_dates"].append(A["dates"][f])
        base = o[f + 1, 1] if anchor_entry else o[f, 1]
        pos = 1.0
        entry_px = np.nan
        pending_entry = False
        stopped_once = False
        reentered = False
        nconf = 0
        for i in range(f, z + 1):
            if pending_entry:
                entry_px = o[i, 1]
                pending_entry = False
            if pos > 0:
                if anchor_entry and i == f:
                    pass
                elif not np.isnan(entry_px):
                    if tight > 0 and c[i, 1] < entry_px * (1 - tight):
                        pos = 0.0
                        diag["second_stops"].append(i)
                    elif vwap_fail > 0 and c[i, 1] < vwap[i] * (1 - vwap_fail):
                        pos = 0.0
                        diag["second_stops"].append(i)
                elif armed and c[i, 1] < base * (1 - day_stop):
                    pos = 0.0
                    stopped_once = True
                    diag["stops"].append(i)
                    if day_stop < STOP:
                        diag["tight_stops"] += 1
                        diag["tight_stop_dates"].append(A["dates"][f])
            else:
                # count confirmation only while flat
                ok_line = False
                if mode in ("vwap", "ema5", "ema15"):
                    x = line[i]
                    ok_line = bool(np.isfinite(x) and c[i, 1] > x * (1 + buffer))
                elif mode == "qqqma":
                    x = ma20_prev[f]
                    ok_line = bool(np.isfinite(x) and c[i, 0] > x * (1 + buffer))
                if ok_line:
                    nconf += 1
                else:
                    nconf = 0
                if (mode in ("vwap", "ema5", "ema15", "qqqma") and not reentered
                        and stopped_once and t_start <= (i - f) < t_end
                        and nconf >= confirm):
                    pos = size
                    pending_entry = True
                    reentered = True
                    diag["reentries"].append(i)
                    nconf = 0
                elif mode == "overnight" and stopped_once and not reentered and i == z - 1:
                    if overnight_cond == "stoplevel":
                        rec = c[i, 1] > base * (1 - STOP)
                    elif overnight_cond == "vwap":
                        rec = c[i, 1] > vwap[i]
                    elif overnight_cond == "open":
                        rec = c[i, 1] > base
                    else:
                        rec = True
                    if rec:
                        pos = size
                        pending_entry = True
                        reentered = True
                        diag["overnight"] += 1
            hold[i] = pos
        if stopped_once:
            prev_stop_weak = bool(c[z, 1] < base * (1 - day_stop))
            prev_stopped = bool(tight_chain or day_stop >= STOP)
    w = np.zeros((n, 3))
    w[:, 1] = hold
    w[:, 2] = 1.0 - hold
    return w, diag


def metrics(ts, o, c, w, start, slip=1.0):
    r = bt.run(ts, o, c, w, start, band=0.02, slippage_bps=slip)
    s = bt.stats(r, BPY)
    i = bt.start_index(ts, start)
    eq = pd.Series(r["equity"], index=ts[i:])
    deq = eq.groupby(eq.index.date).last().to_numpy()
    s["max_drawdown_daily_marks"] = float(-(deq / np.maximum.accumulate(deq) - 1.0).min())
    v = eq.to_numpy()
    peak = np.maximum.accumulate(v)
    dd = v / peak - 1.0
    j = int(np.argmin(dd))
    p = int(np.argmax(v[:j + 1]))
    s["dd_peak_ts"], s["dd_trough_ts"] = str(eq.index[p]), str(eq.index[j])
    s["eq"] = eq
    s["bench"] = bt.benchmark(c[i:, 1], ts[i:], BPY)
    s["yearly"] = bt.yearly(ts[i:], r["equity"], c[i:, 1])
    return s


def line(label, s):
    print(f"{label:44s} CAGR {s['cagr']*100:6.2f}%  DD {s['max_drawdown']*100:5.2f}%  "
          f"Sharpe {s['sharpe']:4.2f}  fills {s['fills']:5,d}  exp {s['exposure']*100:5.1f}%")


def rolling3(eq_daily: pd.Series, bench_daily: pd.Series, winner_daily: pd.Series | None = None):
    """Full 3-year windows starting each quarter (daily marks)."""
    rows = []
    idx = eq_daily.index
    starts = pd.date_range(idx[0], idx[-1], freq="QS")
    for s in starts:
        e = s + pd.DateOffset(years=3)
        if e > idx[-1]:
            break
        a = eq_daily.loc[s:e]
        b = bench_daily.loc[s:e]
        if len(a) < 700:
            continue
        yrs = (a.index[-1] - a.index[0]).total_seconds() / (365.25 * 86400)
        ca = (a.iloc[-1] / a.iloc[0]) ** (1 / yrs) - 1
        cb = (b.iloc[-1] / b.iloc[0]) ** (1 / yrs) - 1
        dd = float(-(a / a.cummax() - 1).min())
        ddb = float(-(b / b.cummax() - 1).min())
        row = dict(start=str(s.date()), cagr=float(ca), dd=dd, bench_cagr=float(cb),
                   bench_dd=ddb, beats_bench=bool(ca > cb and dd < ddb))
        if winner_daily is not None:
            w = winner_daily.loc[s:e]
            cw = (w.iloc[-1] / w.iloc[0]) ** (1 / yrs) - 1
            ddw = float(-(w / w.cummax() - 1).min())
            row.update(winner_cagr=float(cw), winner_dd=ddw,
                       beats_winner=bool(ca > cw and dd < ddw))
        rows.append(row)
    return rows
