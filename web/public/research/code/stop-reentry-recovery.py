"""Stop re-entry / recovery overlay on the round-1 winner (long-only TQQQ/BIL).

Round-1 winner
--------------
QQQ daily close > 165-day SMA -> risk-on, hold TQQQ (including overnight),
otherwise BIL.  On risk-on days the 4% stop is armed only when QQQ's first
minute is below its prior 20-day SMA x 1.01.  If armed and TQQQ closes 4%
below the session open, sell at the next minute's open and stay in BIL for
the rest of the session and the night.

This strategy adds the round-2 "stop re-entry" rules that survived testing:

1. Weak-close re-entry (half size).  If the stopped session closes *below*
   its own stop level (close < open x 0.96), the next session re-enters at
   50% TQQQ (filled 09:31) and holds that 50% through the session and the
   following night.  If the close recovered above the stop level, the next
   session re-enters at 100% as in the winner.
2. Tighter stop on the re-entry day.  The session after *any* stop uses a
   2% stop from its open instead of 4%, and is always armed.  It is checked
   from the first minute, so a gap-down first minute cancels the re-entry.
   If the 2% stop fires, the position goes to BIL for the rest of the
   session; the tighter regime chains to the next session while stops keep
   firing.  A session that completes without a stop restores 100% / 4%.

Why these two: the same-day VWAP / 5m / 15m EMA / QQQ-MA20 reclaim variants
all had negative post-reclaim drift and higher drawdown (see report.md).
The next-open re-entry is the only one with positive forward returns, and
it is made safer by (a) half size when the stop-day close is still weak and
(b) a tighter stop on the vulnerable re-entry day.

No look-ahead: every signal uses bars <= i; weights set at bar i fill at the
open of bar i+1 (research/bt.py convention).  Long-only, 100% TQQQ or BIL
(50/50 on the weak-close re-entry session), no leverage, no shorts.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/agents2/stop-reentry-recovery/strategy.py
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

START10, START5, END = "2017-01-03", "2021-10-25", "2026-10-23"
SMA_N, MA_N = 165, 20
STOP, ARM_BUF = 0.04, 0.01
REENTRY_TIGHT = 0.02
BLOCK = 0.50
BPY = 252 * 390
OUT = Path(__file__).resolve().parent


def build_weights(ts, opens, closes):
    """Return (weights, diagnostics) for the winner + stop re-entry overlay."""
    dates = np.array([t.date() for t in ts])
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(ts) - 1]
    n = len(ts)
    qqq_close, tqqq_close = closes[:, 0], closes[:, 1]

    dclose = qqq_close[last]
    sma = pd.Series(dclose).rolling(SMA_N).mean().to_numpy()
    ma20 = pd.Series(dclose).rolling(MA_N).mean().to_numpy()
    sma_prev = np.r_[np.nan, sma[:-1]]
    ma20_prev = np.r_[np.nan, ma20[:-1]]

    hold = np.zeros(n)
    stops, blocked, tight = [], [], []
    prev_stopped = prev_weak = False

    for k, (f, z) in enumerate(zip(first, last)):
        risk_on = bool(k > 0 and sma_prev[k] == sma_prev[k] and dclose[k - 1] > sma_prev[k])
        if not risk_on:
            prev_stopped = prev_weak = False
            continue

        # --- half-size re-entry when the stop day closed still weak ----------
        if prev_weak:
            hold[f:z + 1] = 1.0 - BLOCK
            blocked.append(str(dates[f]))
            prev_stopped = prev_weak = False
            continue

        was_stopped = prev_stopped
        prev_stopped = prev_weak = False

        armed = bool(ma20_prev[k] == ma20_prev[k]
                     and qqq_close[f] < ma20_prev[k] * (1 + ARM_BUF))
        day_stop = STOP
        if was_stopped:
            # tighter, always-armed stop on the re-entry day
            day_stop = REENTRY_TIGHT
            armed = True
            tight.append(str(dates[f]))

        base = opens[f, 1]
        pos = 1.0
        stopped = False
        for i in range(f, z + 1):
            if pos > 0 and armed and tqqq_close[i] < base * (1 - day_stop):
                pos = 0.0
                stopped = True
                stops.append((str(dates[f]), str(ts[i].time())))
            hold[i] = pos

        if stopped:
            prev_stopped = True
            prev_weak = bool(tqqq_close[z] < base * (1 - day_stop))

    weights = np.zeros((n, 3))
    weights[:, 1] = hold
    weights[:, 2] = 1.0 - hold
    diag = dict(stops=len(stops), blocked=len(blocked), tight_days=len(tight),
                stop_dates=[d for d, _ in stops], blocked_dates=blocked, tight_dates=tight)
    return weights, diag


def window_metrics(result, ts, close_tqqq, start):
    s = bt.stats(result, BPY)
    i = bt.start_index(ts, start)
    s["bench"] = bt.benchmark(close_tqqq[i:], ts[i:], BPY)
    s["yearly"] = bt.yearly(ts[i:], result["equity"], close_tqqq[i:])
    eq = pd.Series(result["equity"], index=ts[i:])
    deq = eq.groupby(eq.index.date).last().to_numpy()
    s["dd_daily"] = float(-(deq / np.maximum.accumulate(deq) - 1.0).min())
    v = result["equity"]
    peak = np.maximum.accumulate(v)
    j = int(np.argmin(v / peak - 1.0))
    p = int(np.argmax(v[:j + 1]))
    s["dd_peak"], s["dd_trough"] = str(ts[i:][p]), str(ts[i:][j])
    return s


def main():
    ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), START10, END, "1min")
    weights, diag = build_weights(ts, opens, closes)

    # winner for comparison (same rules, no re-entry overlay)
    dates = np.array([t.date() for t in ts])
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(ts) - 1]
    dclose = closes[last, 0]
    sma = pd.Series(dclose).rolling(SMA_N).mean().to_numpy()
    ma20 = pd.Series(dclose).rolling(MA_N).mean().to_numpy()
    sma_prev, ma20_prev = np.r_[np.nan, sma[:-1]], np.r_[np.nan, ma20[:-1]]
    hold = np.zeros(len(ts))
    for k, (f, z) in enumerate(zip(first, last)):
        risk_on = bool(k > 0 and sma_prev[k] == sma_prev[k] and dclose[k - 1] > sma_prev[k])
        if not risk_on:
            continue
        armed = bool(ma20_prev[k] == ma20_prev[k]
                     and closes[f, 0] < ma20_prev[k] * (1 + ARM_BUF))
        base, state = opens[f, 1], True
        for i in range(f, z + 1):
            if armed and state and closes[i, 1] < base * (1 - STOP):
                state = False
            hold[i] = state
    base_w = np.zeros((len(ts), 3))
    base_w[:, 1] = hold
    base_w[:, 2] = 1.0 - hold

    out = {"strategy": "winner + half-size weak-close re-entry + 2% re-entry-day stop",
           "diagnostics": diag, "windows": {}, "costs": {}}
    print(f"stops {diag['stops']}  blocked days {diag['blocked']}  tight days {diag['tight_days']}")
    for lab, start in (("10y", START10), ("5y", START5)):
        r = bt.run(ts, opens, closes, weights, start, band=0.02, slippage_bps=1.0)
        s = window_metrics(r, ts, closes[:, 1], start)
        rb = bt.run(ts, opens, closes, base_w, start, band=0.02, slippage_bps=1.0)
        sb = bt.stats(rb, BPY)
        out["windows"][lab] = {
            "start": start, "end": END,
            "cagr": float(s["cagr"]), "max_drawdown": float(s["max_drawdown"]),
            "max_drawdown_daily": float(s["dd_daily"]),
            "sharpe": float(s["sharpe"]), "sortino": float(s["sortino"]),
            "volatility": float(s["volatility"]), "fills": int(s["fills"]),
            "turnover": float(s["turnover"]), "ending_equity": float(s["ending_equity"]),
            "dd_peak": s["dd_peak"], "dd_trough": s["dd_trough"],
            "winner": dict(cagr=float(sb["cagr"]), max_drawdown=float(sb["max_drawdown"])),
            "benchmark": s["bench"],
            "yearly": {str(k): v for k, v in s["yearly"].items()},
        }
        print(f"{lab}: CAGR {s['cagr']*100:.2f}%  DD {s['max_drawdown']*100:.2f}%  "
              f"dailyDD {s['dd_daily']*100:.2f}%  Sharpe {s['sharpe']:.2f}  "
              f"fills {s['fills']}  end ${s['ending_equity']:,.0f}")
        print(f"     winner {sb['cagr']*100:.2f}% / {sb['max_drawdown']*100:.2f}%")

    for slip in (5.0, 10.0):
        out["costs"][f"{slip:.0f}bp"] = {}
        for lab, start in (("10y", START10), ("5y", START5)):
            r = bt.run(ts, opens, closes, weights, start, band=0.02, slippage_bps=slip)
            s = bt.stats(r, BPY)
            out["costs"][f"{slip:.0f}bp"][lab] = dict(
                cagr=float(s["cagr"]), max_drawdown=float(s["max_drawdown"]),
                sharpe=float(s["sharpe"]), fills=int(s["fills"]))
            print(f"{slip:.0f}bp {lab}: {s['cagr']*100:.2f}% / {s['max_drawdown']*100:.2f}%")

    out["pass_vs_tqqq"] = {
        lab: bool(out["windows"][lab]["cagr"] > (0.3928 if lab == "10y" else 0.1347)
                  and out["windows"][lab]["max_drawdown"] < 0.8168)
        for lab in ("10y", "5y")}
    out["pass_vs_winner_strict"] = {
        lab: bool(out["windows"][lab]["cagr"] > out["windows"][lab]["winner"]["cagr"]
                  and out["windows"][lab]["max_drawdown"] < out["windows"][lab]["winner"]["max_drawdown"])
        for lab in ("10y", "5y")}
    (OUT / "strategy_result.json").write_text(json.dumps(out, indent=2, default=float))
    print("\npass vs TQQQ:", out["pass_vs_tqqq"])
    print("pass vs winner (strict):", out["pass_vs_winner_strict"])
    print("wrote", OUT / "strategy_result.json")


if __name__ == "__main__":
    main()
