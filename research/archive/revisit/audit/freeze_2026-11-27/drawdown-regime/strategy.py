"""Deep Drawdown Recovery (DDR) -- standalone rebuild of the drawdown idea.

STATUS: tested on dev; tuned 2026-11-27 (bug fixes only, see DIAGNOSIS.md).
`python strategy.py` prints the spec; `--run` backtests the dev window and
writes result.json.

What the original idea was
--------------------------
`research/agents2/drawdown-regime` used QQQ's drawdown from its 52-week high to
*tighten an intraday stop* on top of the 165-day SMA trend base. Its only
surviving rule was "2% stop instead of 4% while QQQ is >=8% below its high".
The position-level version (exit to BIL when drawdown exceeds X) was tested and
failed even with the trend base underneath.

Why this is a different strategy, not the base with a new trigger
-----------------------------------------------------------------
DDR is flat by default. It owns TQQQ only inside a *recovery window* that opens
after a >=20% drawdown and a confirmed turn, holds for a fixed 60 sessions, and
then stands aside until the drawdown has healed by 5pp. It has:

  * its own signal: QQQ drawdown depth + a 20-session breakout + a re-arm rule;
  * its own holding period: 60 sessions, not "until the regime flips";
  * its own sizing: event-driven 100% / 0%, no continuous regime;
  * its own risk: a 20-session-low exit, no intraday stop, no MA gate.

It never uses QQQ/TQQQ/SPY/NDX against any 100-250-day moving average.

Timing: every decision for session k uses QQQ daily closes through k-1 only.
Weights are set on the prior session's last bar and fill at session k's open
(the 09:30 bar). Arming: once the current drawdown (since the last 52-week
high) has reached -20%, the strategy is armed until a new 52-week high; the
entry is the first 20-session-high close while armed (spec rule 1-2).

Run (only after authorisation):
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/revisit/drawdown-regime/strategy.py --run
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

DEV_START, DEV_END = "2016-01-04", "2023-12-29"
HOLDOUT_START = "2024-01-02"
BPY = 252 * 390
SYMS = ("QQQ", "TQQQ", "BIL")

# Frozen specification: round, a-priori numbers, no fitting.
PARAMS = dict(
    window=252,       # 52-week high for the drawdown
    deep_dd=0.20,     # arm after a 20% drawdown from the high
    entry_break=20,   # confirmed turn: close above the prior 20-session high
    hold=60,          # fixed holding period, sessions (~3 months)
    exit_low=20,      # failure exit: close below the prior 20-session low
    rearm=0.05,       # after an exit, wait for a 5pp drawdown recovery
)

VARIANTS_TRIED = 23  # tune 2026-11-27: steps 4, controls 5, neighbourhood 10, sizing 4

# Pre-registered neighbourhood (to run after the pause; not fitted now).
NEIGHBOURS = dict(
    deep_dd=(0.15, 0.20, 0.25),
    entry_break=(10, 20, 30),
    hold=(40, 60, 90),
    exit_low=(10, 20, 30),
    rearm=(0.03, 0.05, 0.08),
)


# --------------------------------------------------------------------- data
def _qqq_daily(end: str = "2026-10-23"):
    """Adjusted QQQ daily closes from 2015 (warmup) through `end`."""
    path = ROOT / "data" / "intraday-hf" / "QQQ-1d-yahoo.parquet"
    d = pd.read_parquet(path)
    d["date"] = pd.to_datetime(d["date"]).dt.date
    d = d[d["date"] <= pd.Timestamp(end).date()].sort_values("date")
    return d["date"].to_numpy(), d["adjclose"].to_numpy(float)


def _daily_state(ddates, close, p):
    """Per-day values known at the CLOSE of daily row t (used at t+1's open).

    dd[t]     = close[t] / max(close[t-window+1 .. t]) - 1
    trough[t] = lowest dd since the last 52-week high (dd == 0), through t
    hi_b[t]   = max(close[t-b .. t-1])   the b sessions BEFORE close[t]
    lo_b[t]   = min(close[t-b .. t-1])
    hi_b / lo_b are compared with close[t], so they exclude it (the original
    shift(1)-at-t+1 window included it, so "close above the prior 20-session
    high" was impossible on daily closes; tune 2026-11-27).
    """
    s = pd.Series(close)
    hi = s.rolling(int(p["window"]), min_periods=200).max()
    dd = s / hi - 1.0
    epi = (dd >= 0).cumsum()
    trough = dd.groupby(epi).cummin()
    eb, xb = int(p["entry_break"]), int(p["exit_low"])
    hi_b = s.shift(1).rolling(eb, min_periods=eb).max()
    lo_b = s.shift(1).rolling(xb, min_periods=xb).min()
    return (dd.to_numpy(), trough.to_numpy(), hi_b.to_numpy(), lo_b.to_numpy())


def _sessions(ts):
    dates = bt.session_dates(ts)
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(dates) - 1]
    return dates[last], first, last


# ---------------------------------------------------------------- strategy
def build_weights(ts, opens, closes, params=None, mode="ddr"):
    """Return (weights, info) for Deep Drawdown Recovery.

    mode:
      "ddr"           frozen strategy (armed once the current drawdown has
                      reached -deep_dd; enter on the first 20-session high)
      "same_day"      pre-tune logic: dd must still be <= -deep_dd on the
                      breakout day itself
      "breakout_only" control: no drawdown arm, any 20-session high
      "deep_only"     control: enter on the first day of the drawdown, no breakout
      "fixed_hold"    control: no 20-session-low exit
      "qqq"           robustness: hold QQQ instead of TQQQ in the window
    """
    p = dict(PARAMS)
    if params:
        p.update(params)
    dates, first, last = _sessions(ts)
    n_days, n_bars = len(first), len(ts)

    ddates, dcl = _qqq_daily()
    dd_d, tr_d, hi_d, lo_d = _daily_state(ddates, dcl, p)
    # Row j(k) = last daily close strictly before session k. Decisions for
    # session k read only rows <= j(k); the session's own daily bar is never used.
    j = np.searchsorted(ddates, dates, side="left") - 1
    if (j < 0).any():
        raise ValueError("QQQ daily history starts after the minute panel")
    gap = np.flatnonzero(ddates[j[1:]] != dates[:-1])
    if len(gap):
        raise ValueError(f"QQQ daily history missing sessions, e.g. {dates[gap[:3]]}")
    dprev, dd, trough, hi_b, lo_b = dcl[j], dd_d[j], tr_d[j], hi_d[j], lo_d[j]

    hold = int(p["hold"])
    col = 0 if mode == "qqq" else 1
    T = np.zeros(n_days)
    episodes = []
    state = 0
    entry_k = -1
    armed = True
    ref = 0.0

    for k in range(n_days):
        target = 0.0
        reason = ""
        if state == 1:
            if k - entry_k >= hold:
                target, reason = 0.0, "time"
            elif mode != "fixed_hold" and np.isfinite(lo_b[k]) and dprev[k] < lo_b[k]:
                target, reason = 0.0, "low"
            else:
                target = 1.0
        else:
            if mode != "breakout_only" and not armed:
                # wait for the drawdown to heal `rearm` from its lowest point
                # since the exit; capping at -rearm lets a new high re-arm us.
                ref = min(ref, dd[k])
                if dd[k] >= ref + p["rearm"]:
                    armed = True
            if armed and np.isfinite(dd[k]) and np.isfinite(hi_b[k]):
                brk = dprev[k] > hi_b[k]
                if mode == "breakout_only":
                    trig = brk
                elif mode == "deep_only":
                    trig = dd[k] <= -p["deep_dd"]
                elif mode == "same_day":
                    trig = (dd[k] <= -p["deep_dd"]) and brk
                else:
                    trig = (trough[k] <= -p["deep_dd"]) and brk
                if trig:
                    target, reason = 1.0, "entry"
                    state, entry_k = 1, k
                    episodes.append(dict(entry_i=int(k), entry_date=str(dates[k]),
                                         dd=float(dd[k]), trough=float(trough[k]),
                                         entry_px=float(opens[first[k], col])))

        if state == 1 and target == 0.0 and reason:
            state = 0
            # the breakout-only control has no drawdown state, so it stays armed
            if mode != "breakout_only":
                armed = False
                ref = min(dd[k], -p["rearm"])
            episodes[-1]["exit_i"] = int(k)
            episodes[-1]["exit_date"] = str(dates[k])
            episodes[-1]["exit_reason"] = reason
        T[k] = target

    w = weights_from_targets(T, first, last, col)

    for e in episodes:
        i, jx = e["entry_i"], e.get("exit_i", n_days)
        e["days"] = int(jx - i)
        e["ret"] = float(opens[first[min(jx, n_days - 1)], col] / e["entry_px"] - 1.0)
        e.pop("entry_px", None)

    info = dict(mode=mode, params=p, n_episodes=len(episodes),
                exposure=float(np.mean(w[:, col])),
                mean_dd_at_entry=float(np.mean([e["dd"] for e in episodes])) if episodes else None,
                episodes=episodes, targets=T, col=col)
    return w, info


def weights_from_targets(T, first, last, col):
    """Session-k target -> bar weights that fill at session k's first open.

    The target is decided from closes through session k-1, so it is written
    on session k-1's last bar (fill at the next bar = session k's open) and on
    every bar of session k except its last (which carries session k+1's
    target). Pre-tune code wrote it from session k's first bar, so every
    change filled one minute late.
    """
    n_bars = int(last[-1]) + 1
    day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, n_bars]))
    tb = T[day_id]
    tb[:-1] = tb[1:].copy()
    w = np.zeros((n_bars, 3))
    w[:, col] = tb
    w[:, 2] = 1.0 - tb
    return w


# ----------------------------------------------------- measurement helpers
def baseline_weights(ts, closes):
    """165-day QQQ SMA baseline: benchmark measurement only, never in the strategy."""
    dates, first, last = _sessions(ts)
    ddates, dcl = _qqq_daily()
    s = pd.Series(dcl, index=pd.to_datetime(ddates))
    sma = s.rolling(165, min_periods=165).mean().to_numpy()
    reg = np.r_[False, dcl[:-1] > sma[:-1]]
    mp = {d: bool(r) for d, r in zip(ddates, reg)}
    n = len(ts)
    day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, n]))
    w = np.zeros((n, 3))
    w[:, 1] = np.array([mp[d] for d in dates])[day_id].astype(float)
    w[:, 2] = 1.0 - w[:, 1]
    return w


def _stats(r):
    return bt.stats(r, BPY)


def _daily_returns(r):
    return pd.Series(r["equity"], index=r["ts"]).resample("1D").last().pct_change().dropna()


def main():
    ts, opens, closes = bt.panel(SYMS, DEV_START, DEV_END, "1min", warmup_days=500)
    w, info = build_weights(ts, opens, closes)
    assert np.isfinite(w).all() and (w >= 0).all() and (w.sum(1) <= 1 + 1e-12).all()

    out = {
        "agent": "drawdown-regime",
        "original": "research/agents2/drawdown-regime",
        "status": "rejected",
        "idea": "After a >=20% QQQ drawdown, own TQQQ only inside a confirmed "
                "60-session recovery window, then stand aside until the drawdown heals.",
        "hypothesis": "The post-capitulation recovery is a distinct, time-limited return "
                      "state; a confirmed turn after a deep drawdown captures it with low "
                      "exposure and low correlation to slow trend-following.",
        "universe": ["QQQ (signal)", "TQQQ (risk)", "BIL (cash)"],
        "frozen_commit": None,
        "variants_tried": VARIANTS_TRIED,
        "corr_vs_165d_baseline": None,
        "max_corr_vs_other_rebuilds": None,
        "windows": {"dev": {}, "holdout": None, "10y": None, "5y": None},
        "marks": "1m",
        "benchmarks": {},
        "episodes": info["episodes"],
        "params": info["params"],
        "note": "tuned 2026-11-27: spec-vs-code arm fix, session-open fill, daily-close "
                "breakout source. Fails pre-registered F1 (dev DD > 35%) and F6 "
                "(2022-23 DD > 25%); see DIAGNOSIS.md.",
        "exposure": info["exposure"],
    }
    for bp in (1.0, 5.0, 10.0):
        r = bt.run(ts, opens, closes, w, DEV_START, band=0.02, slippage_bps=bp)
        s = _stats(r)
        out["windows"]["dev"][f"{bp:.0f}bp"] = {
            k: s[k] for k in ("cagr", "max_drawdown", "sharpe", "sortino",
                              "volatility", "fills", "turnover", "ending_equity")
        }
        if bp == 1.0:
            rb = bt.run(ts, opens, closes, baseline_weights(ts, closes), DEV_START,
                        band=0.02, slippage_bps=1.0)
            out["corr_vs_165d_baseline"] = float(
                pd.concat([_daily_returns(r), _daily_returns(rb)], axis=1,
                          join="inner").dropna().corr().iloc[0, 1])
            out["benchmarks"]["original"] = {k: _stats(rb)[k] for k in
                                             ("cagr", "max_drawdown", "sharpe", "fills")}

    path = Path(__file__).resolve().parent / "result.json"
    path.write_text(json.dumps(out, indent=2, default=float))
    print("wrote", path)


def print_spec():
    print("Deep Drawdown Recovery (DDR) -- spec (tuned 2026-11-27)")
    for k, v in PARAMS.items():
        print(f"  {k:12s} {v}")
    print("  universe     QQQ signal / TQQQ risk / BIL cash")
    print("  arm          current drawdown from the 252-session high has reached -20%")
    print("  entry        close > prior 20-session high, after a re-arm")
    print("  hold         60 sessions, or exit on a close below the prior 20-session low")
    print("  re-arm       after an exit, wait for the drawdown to heal 5pp")
    print("  sizing       100% TQQQ in the window, 100% BIL otherwise")
    print("  timing       decisions on closes through t-1; fills at t's open")


if __name__ == "__main__":
    if "--run" not in sys.argv:
        print_spec()
        raise SystemExit("pass --run to backtest the dev window")
    main()
