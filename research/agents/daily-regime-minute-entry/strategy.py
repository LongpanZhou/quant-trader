"""Daily 165-day SMA regime + intraday 4% stop overlay on TQQQ (long-only).

Rules
-----
1. Regime (daily): QQQ close > 165-day SMA of QQQ closes -> risk-on for the
   next session; otherwise hold BIL. The signal uses the previous close only
   (no look-ahead); weights set at bar i fill at bar i+1's open.
2. Risk-on sessions hold TQQQ by default (including overnight).
3. Intraday stop: on a risk-on day that is *armed*, if TQQQ trades 4% below
   the session open, liquidate at the next minute's open and stay in BIL for
   the rest of the session and the following night. Re-enter at the next
   session's open if the daily regime is still risk-on.
   "Armed" = QQQ's first-minute price is below its 20-day SMA (through the
   previous close) times 1.01. In strong short-term uptrends intraday dips
   are not stopped.
4. Nothing else: no shorts, no leverage beyond 100% TQQQ, one position at a
   time. BIL earns its (small) daily return while out.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/agents/daily-regime-minute-entry/strategy.py
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
SMA_N = 165
MA_FAST = 20
STOP = 0.04
ARM_BUF = 0.01
BARS_PER_YEAR = 252 * 390
OUT = Path(__file__).resolve().parent


def build_weights(ts, opens, closes):
    """Return (weights, diagnostics) for the daily regime + intraday stop."""
    dates = np.array([t.date() for t in ts])
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(dates) - 1]
    n = len(ts)
    qqq_close = closes[:, 0]
    tqqq_close = closes[:, 1]

    # daily closes (last bar of each session) and indicators through prior close
    dclose = qqq_close[last]
    sma = pd.Series(dclose).rolling(SMA_N).mean().to_numpy()
    ma20 = pd.Series(dclose).rolling(MA_FAST).mean().to_numpy()
    sma_prev = np.r_[np.nan, sma[:-1]]
    ma20_prev = np.r_[np.nan, ma20[:-1]]

    day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, n]))

    hold = np.zeros(n, dtype=bool)
    stops = []
    for f, l in zip(first, last):
        k = int(day_id[f])
        risk_on = bool(sma_prev[k] == sma_prev[k] and dclose[k - 1] > sma_prev[k]) if k > 0 else False
        if not risk_on:
            continue
        armed = bool(ma20_prev[k] == ma20_prev[k] and qqq_close[f] < ma20_prev[k] * (1.0 + ARM_BUF))
        base = opens[f, 1]
        state = True
        for i in range(f, l + 1):
            if armed and state and tqqq_close[i] < base * (1.0 - STOP):
                state = False
                stops.append((str(dates[f]), str(ts[i].time())))
            hold[i] = state

    weights = np.zeros((n, 3))
    weights[:, 1] = hold.astype(float)
    weights[:, 2] = 1.0 - weights[:, 1]
    diag = {"days": int(len(first)), "stop_events": len(stops), "stops": stops[:20]}
    return weights, diag


def window_metrics(result, ts, close_tqqq, start):
    s = bt.stats(result, BARS_PER_YEAR)
    i = bt.start_index(ts, start)
    bench = bt.benchmark(close_tqqq[i:], ts[i:], BARS_PER_YEAR)
    eq = pd.Series(result["equity"], index=ts[i:])
    deq = eq.groupby(eq.index.date).last().to_numpy()
    peak = np.maximum.accumulate(deq)
    s["max_drawdown_daily_marks"] = float(-(deq / peak - 1.0).min())
    peak_m = np.maximum.accumulate(result["equity"])
    dd = result["equity"] / peak_m - 1.0
    j = int(np.argmin(dd))
    p = int(np.argmax(result["equity"][: j + 1]))
    s["dd_peak_ts"] = str(ts[i:][p])
    s["dd_trough_ts"] = str(ts[i:][j])
    s["bench"] = bench
    s["yearly"] = bt.yearly(ts[i:], result["equity"], close_tqqq[i:])
    return s


def main():
    ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), START10, END, "1min")
    weights, diag = build_weights(ts, opens, closes)

    # control: same regime with no intraday overlay (the 1m-marked baseline)
    dates = np.array([t.date() for t in ts])
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(dates) - 1]
    dclose = closes[last, 0]
    sma = pd.Series(dclose).rolling(SMA_N).mean().to_numpy()
    reg_day = np.zeros(len(dclose), bool)
    reg_day[1:] = dclose[:-1] > sma[:-1]
    day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, len(ts)]))
    ctrl_hold = reg_day[day_id]
    ctrl_w = np.zeros((len(ts), 3))
    ctrl_w[:, 1] = ctrl_hold.astype(float)
    ctrl_w[:, 2] = 1.0 - ctrl_w[:, 1]

    out = {
        "agent": "daily-regime-minute-entry",
        "strategy": {
            "regime": f"QQQ daily close > {SMA_N}-day SMA (signal at prior close)",
            "instrument_risk_on": "TQQQ 100%, held overnight",
            "instrument_risk_off": "BIL 100%",
            "stop": f"{STOP*100:.0f}% below session open, next-minute fill, stays out rest of day + night",
            "stop_armed": f"QQQ first-minute price < {MA_FAST}-day SMA * (1 + {ARM_BUF})",
            "fills": "next bar open", "cost": "1 bp one-way (5/10 bp reported)",
        },
        "diagnostics": diag,
        "windows": {},
        "control_1m_no_overlay": {},
        "cost_sensitivity": {},
    }

    for label, start in (("10y", START10), ("5y", START5)):
        r = bt.run(ts, opens, closes, weights, start, band=0.02, slippage_bps=1.0)
        s = window_metrics(r, ts, closes[:, 1], start)
        out["windows"][label] = {
            "start": start, "end": END,
            "cagr": s["cagr"], "max_drawdown": s["max_drawdown"],
            "max_drawdown_daily_marks": s["max_drawdown_daily_marks"],
            "sharpe": s["sharpe"], "sortino": s["sortino"], "volatility": s["volatility"],
            "fills": s["fills"], "turnover": s["turnover"],
            "ending_equity": s["ending_equity"],
            "dd_peak": s["dd_peak_ts"], "dd_trough": s["dd_trough_ts"],
            "benchmark": s["bench"],
            "yearly": {str(k): v for k, v in s["yearly"].items()},
        }
        rc = bt.run(ts, opens, closes, ctrl_w, start, band=0.02, slippage_bps=1.0)
        cs = window_metrics(rc, ts, closes[:, 1], start)
        out["control_1m_no_overlay"][label] = {
            "cagr": cs["cagr"], "max_drawdown": cs["max_drawdown"],
            "max_drawdown_daily_marks": cs["max_drawdown_daily_marks"],
            "sharpe": cs["sharpe"], "fills": cs["fills"], "turnover": cs["turnover"],
        }

    for slip in (5.0, 10.0):
        out["cost_sensitivity"][f"{slip:.0f}bp"] = {}
        for label, start in (("10y", START10), ("5y", START5)):
            r = bt.run(ts, opens, closes, weights, start, band=0.02, slippage_bps=slip)
            s = bt.stats(r, BARS_PER_YEAR)
            out["cost_sensitivity"][f"{slip:.0f}bp"][label] = {
                "cagr": s["cagr"], "max_drawdown": s["max_drawdown"], "sharpe": s["sharpe"],
                "fills": s["fills"], "turnover": s["turnover"],
            }

    # pass/fail vs TQQQ buy-and-hold
    tq = {"10y": {"cagr": 0.3928, "max_drawdown": 0.8168},
          "5y": {"cagr": 0.1347, "max_drawdown": 0.8168}}
    out["pass_vs_tqqq"] = {
        k: bool(out["windows"][k]["cagr"] > tq[k]["cagr"]
                and out["windows"][k]["max_drawdown"] < tq[k]["max_drawdown"])
        for k in ("10y", "5y")
    }
    out["pass_vs_daily_baseline_readme"] = {
        "10y": bool(out["windows"]["10y"]["cagr"] > 0.4531
                    and out["windows"]["10y"]["max_drawdown"] < 0.5871),
        "5y": bool(out["windows"]["5y"]["cagr"] > 0.3461
                   and out["windows"]["5y"]["max_drawdown"] < 0.3686),
    }

    (OUT / "result.json").write_text(json.dumps(out, indent=2, default=float))
    for label in ("10y", "5y"):
        w = out["windows"][label]
        print(f"{label}: CAGR {w['cagr']*100:.2f}%  DD {w['max_drawdown']*100:.2f}%  "
              f"Sharpe {w['sharpe']:.2f}  fills {w['fills']}  end ${w['ending_equity']:,.0f}")
    print("wrote", OUT / "result.json")


if __name__ == "__main__":
    main()
