"""Core ORB weight generator used by the exploration and final strategy.

All decisions use data through the close of bar i; the harness fills at the
open of bar i+1.  Signals are long-only.  Symbols: 0=QQQ, 1=TQQQ, 2=BIL.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def day_arrays(ts):
    dates = ts.date
    starts = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    ends = np.r_[starts[1:], len(ts)]
    return dates, starts, ends


def daily_tables(ts, q, t):
    g = pd.DataFrame({
        "date": ts.date,
        "qo": q["open"].to_numpy(), "qh": q["high"].to_numpy(),
        "ql": q["low"].to_numpy(), "qc": q["close"].to_numpy(),
        "to": t["open"].to_numpy(), "th": t["high"].to_numpy(),
        "tl": t["low"].to_numpy(), "tc": t["close"].to_numpy(),
    })
    d = g.groupby("date").agg(
        qo=("qo", "first"), qh=("qh", "max"), ql=("ql", "min"), qc=("qc", "last"),
        to=("to", "first"), th=("th", "max"), tl=("tl", "min"), tc=("tc", "last"))
    for pre in ("q", "t"):
        pc = d[f"{pre}c"].shift(1)
        tr = pd.concat([d[f"{pre}h"] - d[f"{pre}l"],
                        (d[f"{pre}h"] - pc).abs(),
                        (d[f"{pre}l"] - pc).abs()], axis=1).max(axis=1)
        d[f"{pre}_atr14"] = tr.rolling(14).mean()
        d[f"{pre}_atrpct"] = d[f"{pre}_atr14"] / d[f"{pre}c"]
        d[f"{pre}_atrpct_prev"] = d[f"{pre}_atrpct"].shift(1)
    d["sma165"] = d["qc"].rolling(165).mean()
    d["regime"] = (d["qc"] > d["sma165"]).astype(float)
    d["regime_prev"] = d["regime"].shift(1).fillna(0.0)
    return d


def orb_hl(sig, starts, ends, or_min):
    hi = sig["high"].to_numpy()
    lo = sig["low"].to_numpy()
    op = sig["open"].to_numpy()
    cl = sig["close"].to_numpy()
    n = len(starts)
    or_hi = np.full(n, np.nan)
    or_lo = np.full(n, np.nan)
    or_open = np.full(n, np.nan)
    or_close = np.full(n, np.nan)
    for k, (s, e) in enumerate(zip(starts, ends)):
        j = min(s + or_min, e)
        if j > s:
            or_hi[k] = hi[s:j].max()
            or_lo[k] = lo[s:j].min()
            or_open[k] = op[s]
            or_close[k] = cl[j - 1]
    return or_hi, or_lo, or_open, or_close


def build_weights(ts, q, t, d, cfg):
    """Return (weights, info) for a long-only ORB configuration.

    cfg keys (defaults in DEFAULTS below):
      mode:       'orb'          intraday/swing ORB
                  'regime_hold'  hold TQQQ whenever regime is on, ORB used
                                 only as an intraday stop / re-entry
      or_min:     5 | 15 | 30
      trade:      'TQQQ' | 'QQQ'
      entry:      'breakout' (close > OR high) | 'first' (paper: OR candle up)
      ...
    """
    c = dict(DEFAULTS)
    c.update(cfg)

    n = len(ts)
    w = np.zeros((n, 3))
    w[:, 2] = 1.0

    dates, starts, ends = day_arrays(ts)
    uniq = dates[starts]
    trade_sym = t if c["trade"] == "TQQQ" else q
    sig = q if c["signal"] == "QQQ" else t
    col = 1 if c["trade"] == "TQQQ" else 0
    or_hi, or_lo, or_open, or_close = orb_hl(sig, starts, ends, c["or_min"])
    t_or_hi, t_or_lo, t_or_open, t_or_close = orb_hl(trade_sym, starts, ends, c["or_min"])
    reg = d["regime_prev"].reindex(uniq).to_numpy()
    atrp = (d["t_atrpct_prev"] if c["trade"] == "TQQQ" else d["q_atrpct_prev"]).reindex(uniq).to_numpy()

    shi = sig["high"].to_numpy()
    slo = sig["low"].to_numpy()
    scl = sig["close"].to_numpy()
    hi = trade_sym["high"].to_numpy()
    lo = trade_sym["low"].to_numpy()
    cl = trade_sym["close"].to_numpy()

    day_of = np.repeat(np.arange(len(uniq)), ends - starts)
    minute = ts.hour.to_numpy() * 60 + ts.minute.to_numpy()
    eod_mask = minute == c["eod_min"]
    cutoff = minute >= c["cutoff_min"]
    buf = c["buffer_bps"] / 1e4

    pos = 0
    entry_px = np.nan
    stop = np.nan
    target = np.inf
    hwm = np.nan
    days_held = 0
    trades = 0
    prev_day = -1

    for i in range(n):
        k = day_of[i]
        if k != prev_day:
            prev_day = k
            if pos == 1:
                days_held += 1

        if pos == 1:
            # ---------------- manage an open long ----------------
            hit_stop = np.isfinite(stop) and lo[i] <= stop
            hit_tgt = np.isfinite(target) and hi[i] >= target
            exit_now = hit_stop or hit_tgt

            if c["exit_on_or_break"] and i >= starts[k] + c["or_min"] and scl[i] < or_lo[k] * (1.0 - buf):
                exit_now = True

            if c["use_regime"] and c["mode"] == "orb" and reg[k] < 0.5:
                exit_now = True

            if c["mode"] == "regime_hold":
                # intraday breakdown: close below today's opening-range low
                if i >= starts[k] + c["or_min"] and scl[i] < or_lo[k] * (1.0 - buf):
                    exit_now = True

            if eod_mask[i]:
                if c["mode"] == "regime_hold":
                    if reg[k] < 0.5:
                        exit_now = True
                elif c["intraday_only"]:
                    exit_now = True
                elif c["overnight_rule"] == "if_above_or":
                    exit_now = exit_now or not (scl[i] > or_hi[k])
                elif c["overnight_rule"] == "if_profit":
                    exit_now = exit_now or not (cl[i] > entry_px)
                if days_held >= c["max_hold_days"]:
                    exit_now = True
                if c["use_regime"] and c["mode"] == "orb" and reg[k] < 0.5:
                    exit_now = True

            if exit_now:
                w[i, 0] = 0.0
                w[i, 1] = 0.0
                w[i, 2] = 1.0
                pos = 0
                entry_px = np.nan
                stop = np.nan
                days_held = 0
                continue

            w[i, 0] = 0.0
            w[i, 1] = 0.0
            w[i, 2] = 0.0
            w[i, col] = 1.0
            px = cl[i]
            hwm = max(hwm, px)
            if c["trail"] == "atr" and np.isfinite(atrp[k]):
                tr = hwm * (1.0 - c["trail_k"] * atrp[k])
                stop = max(stop, tr) if np.isfinite(stop) else tr
            continue

        # ---------------- flat: look for an entry ----------------
        trig = False
        if c["mode"] == "regime_hold":
            if reg[k] < 0.5:
                trig = False
            elif eod_mask[i]:
                # go long into the night only if the day is not broken down
                trig = scl[i] >= or_lo[k] * (1.0 - buf)
            elif i >= starts[k] + c["or_min"] and scl[i] > or_hi[k] * (1.0 + buf):
                trig = True
        else:
            if c["use_regime"] and reg[k] < 0.5:
                trig = False
            elif c["entry"] == "first":
                trig = (i == starts[k] + c["or_min"] - 1) and (or_close[k] > or_open[k] * (1.0 + buf))
            else:
                trig = (i >= starts[k] + c["or_min"]) and (not cutoff[i]) and (scl[i] > or_hi[k] * (1.0 + buf))

        if trig:
                px = cl[i]
                w[i, 0] = 0.0
                w[i, 1] = 0.0
                w[i, 2] = 0.0
                w[i, col] = 1.0
                pos = 1
                entry_px = px
                days_held = 1
                trades += 1
                if c["stop"] == "orlow":
                    if c["stop_ref"] == "signal":
                        stop = px * (1.0 + (or_lo[k] / scl[i] - 1.0))
                    elif c["stop_ref"] == "beta":
                        stop = px * (1.0 + c["stop_beta"] * (or_lo[k] / scl[i] - 1.0))
                    else:
                        stop = t_or_lo[k]
                elif c["stop"] == "atr":
                    stop = px - c["stop_k"] * atrp[k] * px
                elif c["stop"] == "fixed":
                    stop = px * (1.0 - c["fixed_pct"])
                else:
                    stop = np.nan
                risk = px - stop if np.isfinite(stop) else np.nan
                if c["target"] == "r" and np.isfinite(risk) and risk > 0:
                    target = px + c["target_r"] * risk
                elif c["target"] == "pct":
                    target = px * (1.0 + c["target_pct"])
                else:
                    target = np.inf
                hwm = px

    return w, {"entry_signals": trades}


DEFAULTS = dict(
    mode="orb",
    or_min=30,
    trade="TQQQ",
    signal="TQQQ",
    stop_ref="signal",
    stop_beta=3.0,
    exit_on_or_break=False,
    entry="breakout",
    buffer_bps=0.0,
    stop="orlow",
    stop_k=1.0,
    fixed_pct=0.01,
    target="none",
    target_r=None,
    target_pct=None,
    intraday_only=True,
    overnight_rule="always",
    trail="none",
    trail_k=3.0,
    cutoff_min=15 * 60,
    eod_min=15 * 60 + 54,
    use_regime=True,
    max_hold_days=10 ** 6,
)
