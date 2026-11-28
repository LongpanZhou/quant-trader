"""Deep Drawdown Recovery (DDR) -- standalone rebuild of the drawdown idea.

STATUS: DESIGN ONLY. Backtests are paused by the lead (BRIEF.md clarification,
2026-11-26). This file has NOT been run. `python strategy.py` prints the frozen
spec and exits; `--run` is required to backtest and must not be used until the
lead authorises it.

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
Weights are set on the prior session's last bar and fill at session k's open.

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
    """Per-day values known at the open of that day.

    dd[t]   = close[t-1] / max(close[t-window .. t-1]) - 1
    hi_b[t] = max(close[t-1-b .. t-2])   the b sessions BEFORE close[t-1]
    lo_b[t] = min(close[t-1-b .. t-2])
    They are compared with close[t-1], so they must exclude it: including it
    (the earlier shift(1)) made "close above the prior 20-session high"
    impossible, and it only fired on rounding noise between the minute and
    daily closes.
    """
    s = pd.Series(close, index=pd.to_datetime(ddates))
    win = int(p["window"])
    hi = s.rolling(win, min_periods=200).max()
    dd_now = (s / hi - 1.0).to_numpy()
    dd = np.r_[np.nan, dd_now[:-1]]

    eb, xb = int(p["entry_break"]), int(p["exit_low"])
    hi_b = s.shift(2).rolling(eb, min_periods=eb).max().to_numpy()
    lo_b = s.shift(2).rolling(xb, min_periods=xb).min().to_numpy()
    return dd, hi_b, lo_b


def _sessions(ts):
    dates = bt.session_dates(ts)
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(dates) - 1]
    return dates[last], first, last


# ---------------------------------------------------------------- strategy
def build_weights(ts, opens, closes, params=None, mode="ddr"):
    """Return (weights, info) for Deep Drawdown Recovery.

    mode:
      "ddr"           frozen strategy
      "breakout_only" control: no drawdown arm, any 20-session high
      "deep_only"     control: enter on the first day of the drawdown, no breakout
      "qqq"           robustness: hold QQQ instead of TQQQ in the window
    """
    p = dict(PARAMS)
    if params:
        p.update(params)
    dates, first, last = _sessions(ts)
    n_days, n_bars = len(first), len(ts)
    dclose = closes[last, 0]
    dprev = np.r_[np.nan, dclose[:-1]]

    ddates, dcl = _qqq_daily()
    dd_d, hi_d, lo_d = _daily_state(ddates, dcl, p)
    pos = {d: i for i, d in enumerate(ddates)}
    miss = [d for d in dates if d not in pos]
    if miss:
        raise ValueError(f"QQQ daily history missing {len(miss)} sessions, e.g. {miss[:3]}")
    ix = np.array([pos[d] for d in dates])
    dd, hi_b, lo_b = dd_d[ix], hi_d[ix], lo_d[ix]

    hold = int(p["hold"])
    col = 0 if mode == "qqq" else 1
    w = np.zeros((n_bars, 3))
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
            elif np.isfinite(dprev[k]) and dprev[k] < lo_b[k]:
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
            if np.isfinite(dprev[k]) and armed:
                if mode == "breakout_only":
                    trig = dprev[k] > hi_b[k]
                elif mode == "deep_only":
                    trig = dd[k] <= -p["deep_dd"]
                else:
                    trig = (dd[k] <= -p["deep_dd"]) and (dprev[k] > hi_b[k])
                if trig:
                    target, reason = 1.0, "entry"
                    state, entry_k = 1, k
                    episodes.append(dict(entry_i=int(k), entry_date=str(dates[k]),
                                         dd=float(dd[k]), entry_px=float(opens[first[k], col])))

        if state == 1 and target == 0.0 and reason:
            state = 0
            # the breakout-only control has no drawdown state, so it stays armed
            if mode != "breakout_only":
                armed = False
                ref = min(dd[k], -p["rearm"])
            episodes[-1]["exit_i"] = int(k)
            episodes[-1]["exit_date"] = str(dates[k])
            episodes[-1]["exit_reason"] = reason

        w[first[k]:last[k] + 1, col] = target
        w[first[k]:last[k] + 1, 2] = 1.0 - target

    for e in episodes:
        i, j = e["entry_i"], e.get("exit_i", n_days)
        e["days"] = int(j - i)
        e["ret"] = float(opens[first[min(j, n_days - 1)], col] / e["entry_px"] - 1.0)
        e.pop("entry_px", None)

    info = dict(mode=mode, params=p, n_episodes=len(episodes),
                exposure=float(np.mean(w[:, col])),
                mean_dd_at_entry=float(np.mean([e["dd"] for e in episodes])) if episodes else None,
                episodes=episodes)
    return w, info


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

    out = {
        "agent": "drawdown-regime",
        "original": "research/agents2/drawdown-regime",
        "status": "pending_test",
        "idea": "After a >=20% QQQ drawdown, own TQQQ only inside a confirmed "
                "60-session recovery window, then stand aside until the drawdown heals.",
        "hypothesis": "The post-capitulation recovery is a distinct, time-limited return "
                      "state; a confirmed turn after a deep drawdown captures it with low "
                      "exposure and low correlation to slow trend-following.",
        "universe": ["QQQ (signal)", "TQQQ (risk)", "BIL (cash)"],
        "frozen_commit": None,
        "variants_tried": 0,
        "corr_vs_165d_baseline": None,
        "max_corr_vs_other_rebuilds": None,
        "windows": {"dev": {}, "holdout": None, "10y": None, "5y": None},
        "marks": "1m",
        "benchmarks": {},
        "episodes": info["episodes"],
        "params": info["params"],
        "note": "not run: backtests paused 2026-11-26",
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
    print("Deep Drawdown Recovery (DDR) -- frozen spec, not tested")
    for k, v in PARAMS.items():
        print(f"  {k:12s} {v}")
    print("  universe     QQQ signal / TQQQ risk / BIL cash")
    print("  arm          QQQ close <= -20% from its trailing 252-session high")
    print("  entry        close > prior 20-session high, after a re-arm")
    print("  hold         60 sessions, or exit on a close below the prior 20-session low")
    print("  re-arm       after an exit, wait for the drawdown to heal 5pp")
    print("  sizing       100% TQQQ in the window, 100% BIL otherwise")
    print("  timing       decisions on closes through t-1; fills at t's open")


if __name__ == "__main__":
    if "--run" not in sys.argv:
        print_spec()
        raise SystemExit("DESIGN ONLY: backtests paused; pass --run only after authorisation")
    main()
