"""TQQQ/QQQ leverage-ratio froth overlay on the 165-day QQQ regime.

Idea
----
The TQQQ/QQQ price ratio is a cumulative record of *realised* leverage
outperformance.  Writing L for TQQQ and S for QQQ, the Avellaneda-Zhang
identity gives, to first order,

    log(L_t / L_0) = 3 log(S_t / S_0) - 3 V_t          (V = realised variance)

so the ratio's log is  2 log(S_t/S_0) - 3 V_t.  Its level relative to its own
200-day mean ("extension") therefore measures a *combination* of how far QQQ
has run and how little volatility it took to get there.  A very high extension
is a low-volatility melt-up in which leveraged exposure has compounded without
paying drag.  The macro-finance literature calls the associated build-up of
risk the "volatility paradox" (Brunnermeier & Sannikov 2014): calm, strongly
trending markets are exactly when leverage and crowding accumulate, and the
subsequent shock is amplified.

Rules
-----
Base (round-1 winner, unchanged):
  1. Risk-on when QQQ's prior close is above its 165-day SMA, else BIL.
  2. On risk-on days arm a 4% stop from the session open only when QQQ's
     first-minute price is below its prior 20-day SMA times 1.01.  If armed
     and TQQQ closes 4% below the open, move to BIL at the next minute's open
     for the rest of the session and the night.

Ratio overlay (new):
  3. At each close compute ext = log(ratio / 200-day MA of ratio).  If the
     prior close's ext > 0.18, hold QQQ instead of TQQQ for the next session
     (including overnight).  The 4% stop still applies while in QQQ, so a
     3x-sized intraday collapse takes the book to BIL.

Everything is long-only, uses only data through bar i, and fills at bar i+1's
open.  Costs are charged on traded notional by research/bt.py.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/agents2/ratio-pairs/strategy.py
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
SMA_N = 165          # QQQ regime
MA_FAST = 20         # stop arming
STOP = 0.04          # TQQQ intraday stop
ARM_BUF = 0.01
RATIO_MA = 200       # ratio extension window
THETA = 0.18         # log-extension threshold
DEFENSIVE = "QQQ"    # asset held on froth days ("QQQ" or "BIL")
BARS_PER_YEAR = 252 * 390
OUT = Path(__file__).resolve().parent


def day_bounds(ts):
    dates = np.array([t.date() for t in ts])
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(ts) - 1]
    return dates, first, last


def winner_state(ts, opens, closes):
    """Per-minute TQQQ hold mask and per-day risk-on flag (round-1 winner)."""
    dates, first, last = day_bounds(ts)
    n = len(ts)
    qqq_close, tqqq_close = closes[:, 0], closes[:, 1]
    dc = qqq_close[last]
    sma = pd.Series(dc).rolling(SMA_N).mean().to_numpy()
    ma20 = pd.Series(dc).rolling(MA_FAST).mean().to_numpy()
    sma_prev = np.r_[np.nan, sma[:-1]]
    ma20_prev = np.r_[np.nan, ma20[:-1]]
    hold = np.zeros(n, bool)
    risk_on = np.zeros(len(first), bool)
    for k, (f, l) in enumerate(zip(first, last)):
        if k == 0 or not (sma_prev[k] == sma_prev[k] and dc[k - 1] > sma_prev[k]):
            continue
        risk_on[k] = True
        armed = bool(ma20_prev[k] == ma20_prev[k] and qqq_close[f] < ma20_prev[k] * (1 + ARM_BUF))
        base = opens[f, 1]
        state = True
        for i in range(f, l + 1):
            if armed and state and tqqq_close[i] < base * (1 - STOP):
                state = False
            hold[i] = state
    return hold, risk_on, first, last


def froth_flag(closes, last, ratio_ma=RATIO_MA, theta=THETA):
    """Per-day flag: prior close's ratio extension above its MA exceeds theta."""
    ratio = closes[last, 1] / closes[last, 0]
    ext = np.log(ratio / pd.Series(ratio).rolling(ratio_ma).mean().to_numpy())
    prior = np.r_[np.nan, ext[:-1]]
    return np.nan_to_num(prior, nan=-9.0) > theta, ext


def build_weights(ts, opens, closes, defensive=DEFENSIVE, ratio_ma=RATIO_MA,
                  theta=THETA, use_overlay=True, use_stop=True):
    hold, risk_on, first, last = winner_state(ts, opens, closes)
    froth, ext = froth_flag(closes, last, ratio_ma, theta)
    if not use_overlay:
        froth = np.zeros_like(froth)
    nd = len(first)
    day = np.zeros((nd, 3))
    day[risk_on & ~froth, 1] = 1.0
    if defensive == "QQQ":
        day[risk_on & froth, 0] = 1.0
    day[~risk_on, 2] = 1.0
    if defensive == "BIL":
        day[froth, :] = (0.0, 0.0, 1.0)
    n = len(ts)
    w = np.zeros((n, 3))
    for k, (f, l) in enumerate(zip(first, last)):
        w[f:l + 1] = day[k]
    if use_stop:
        w[~hold] = (0.0, 0.0, 1.0)
    return w, {"froth_days": int(froth.sum()), "risk_on_days": int(risk_on.sum()),
               "days": nd}


def window_metrics(result, ts, close_tqqq, start):
    s = bt.stats(result, BARS_PER_YEAR)
    i = bt.start_index(ts, start)
    bench = bt.benchmark(close_tqqq[i:], ts[i:], BARS_PER_YEAR)
    eq = pd.Series(result["equity"], index=result["ts"])
    deq = eq.groupby(eq.index.date).last().to_numpy()
    peak = np.maximum.accumulate(deq)
    s["max_drawdown_daily_marks"] = float(-(deq / peak - 1.0).min())
    peak_m = np.maximum.accumulate(result["equity"])
    dd = result["equity"] / peak_m - 1.0
    j = int(np.argmin(dd))
    p = int(np.argmax(result["equity"][: j + 1]))
    s["dd_peak_ts"] = str(result["ts"][p])
    s["dd_trough_ts"] = str(result["ts"][j])
    s["bench"] = bench
    s["yearly"] = bt.yearly(result["ts"], result["equity"], close_tqqq[i:])
    return s


def rolling_3y(result, bench, starts):
    """Quarterly-start 3-year windows; `bench` is a Series on result['ts']."""
    eq = pd.Series(result["equity"], index=result["ts"])
    out = []
    for st in starts:
        en = st + pd.DateOffset(years=3)
        m = (eq.index >= st) & (eq.index < en)
        if m.sum() < 500:
            continue
        e = eq[m].to_numpy()
        t = eq.index[m]
        years = (t[-1] - t[0]).total_seconds() / (365.25 * 86400)
        peak = np.maximum.accumulate(e)
        b = bench[m].to_numpy()
        bp = np.maximum.accumulate(b)
        out.append({
            "start": str(st.date()),
            "cagr": float((e[-1] / e[0]) ** (1 / years) - 1),
            "max_drawdown": float(-(e / peak - 1).min()),
            "tqqq_cagr": float((b[-1] / b[0]) ** (1 / years) - 1),
            "tqqq_max_drawdown": float(-(b / bp - 1).min()),
        })
    return out


def main():
    ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), START10, END, "1min")
    weights, diag = build_weights(ts, opens, closes)

    # ablations
    w_nostop, _ = build_weights(ts, opens, closes, use_stop=False)
    w_nooverlay, _ = build_weights(ts, opens, closes, use_overlay=False)
    w_bil, _ = build_weights(ts, opens, closes, defensive="BIL")

    out = {
        "agent": "ratio-pairs",
        "strategy": {
            "base": f"QQQ close > {SMA_N}-day SMA -> TQQQ, else BIL; "
                    f"{STOP*100:.0f}% intraday stop armed when QQQ first minute < "
                    f"{MA_FAST}-day SMA * (1+{ARM_BUF})",
            "overlay": f"hold {DEFENSIVE} instead of TQQQ while prior close's "
                       f"log(TQQQ/QQQ ratio / {RATIO_MA}-day MA) > {THETA}",
            "fills": "next bar open, long only, cost on traded notional",
            "cost": "1 bp one-way headline; 0/5/10 bp reported",
        },
        "diagnostics": diag,
        "windows": {},
        "ablation": {},
        "cost_sensitivity": {},
        "yearly": {},
        "rolling_3y": [],
        "pass_vs_tqqq": {},
        "pass_vs_winner": {},
    }

    runs = {}
    for label, start in (("10y", START10), ("5y", START5)):
        r = bt.run(ts, opens, closes, weights, start, band=0.02, slippage_bps=1.0)
        s = window_metrics(r, ts, closes[:, 1], start)
        runs[label] = r
        out["windows"][label] = {
            "start": start, "end": END,
            "cagr": s["cagr"], "max_drawdown": s["max_drawdown"],
            "max_drawdown_daily_marks": s["max_drawdown_daily_marks"],
            "sharpe": s["sharpe"], "sortino": s["sortino"], "volatility": s["volatility"],
            "fills": s["fills"], "turnover": s["turnover"],
            "ending_equity": s["ending_equity"],
            "dd_peak": s["dd_peak_ts"], "dd_trough": s["dd_trough_ts"],
            "benchmark": s["bench"],
        }
        out["yearly"][label] = {str(k): v for k, v in s["yearly"].items()}

    for name, w in (("no_stop", w_nostop), ("no_overlay_winner", w_nooverlay),
                    ("defensive_BIL", w_bil)):
        out["ablation"][name] = {}
        for label, start in (("10y", START10), ("5y", START5)):
            r = bt.run(ts, opens, closes, w, start, band=0.02, slippage_bps=1.0)
            s = bt.stats(r, BARS_PER_YEAR)
            out["ablation"][name][label] = {
                "cagr": s["cagr"], "max_drawdown": s["max_drawdown"],
                "sharpe": s["sharpe"], "fills": s["fills"],
            }

    for slip in (0.0, 5.0, 10.0):
        key = f"{slip:.0f}bp"
        out["cost_sensitivity"][key] = {}
        for label, start in (("10y", START10), ("5y", START5)):
            r = bt.run(ts, opens, closes, weights, start, band=0.02, slippage_bps=slip)
            s = bt.stats(r, BARS_PER_YEAR)
            out["cost_sensitivity"][key][label] = {
                "cagr": s["cagr"], "max_drawdown": s["max_drawdown"],
                "sharpe": s["sharpe"], "fills": s["fills"], "turnover": s["turnover"],
            }

    starts = pd.date_range("2017-01-01", "2023-10-23", freq="QS",
                           tz="America/New_York")
    bench = pd.Series(closes[bt.start_index(ts, START10):, 1], index=runs["10y"]["ts"])
    roll = rolling_3y(runs["10y"], bench, starts)
    r_win = bt.run(ts, opens, closes, w_nooverlay, START10, band=0.02, slippage_bps=1.0)
    roll_win = {w["start"]: w for w in rolling_3y(r_win, bench, starts)}
    for w in roll:
        ww = roll_win.get(w["start"], {})
        w["winner_cagr"] = ww.get("cagr")
        w["winner_max_drawdown"] = ww.get("max_drawdown")
    out["rolling_3y"] = roll
    n3 = len(roll)
    out["rolling_3y_summary"] = {
        "n": n3,
        "beats_tqqq_cagr": int(sum(w["cagr"] > w["tqqq_cagr"] for w in roll)),
        "beats_tqqq_dd": int(sum(w["max_drawdown"] < w["tqqq_max_drawdown"] for w in roll)),
        "beats_winner_cagr": int(sum(w["cagr"] > w["winner_cagr"] for w in roll)),
        "beats_winner_dd": int(sum(w["max_drawdown"] < w["winner_max_drawdown"] for w in roll)),
        "median_cagr": float(np.median([w["cagr"] for w in roll])),
        "median_tqqq_cagr": float(np.median([w["tqqq_cagr"] for w in roll])),
        "median_winner_cagr": float(np.median([w["winner_cagr"] for w in roll])),
    }

    tq = {"10y": {"cagr": 0.3928, "max_drawdown": 0.8168},
          "5y": {"cagr": 0.1347, "max_drawdown": 0.8168}}
    win = {"10y": {"cagr": 0.5880, "max_drawdown": 0.4456},
           "5y": {"cagr": 0.4988, "max_drawdown": 0.3349}}
    out["pass_vs_tqqq"] = {
        k: bool(out["windows"][k]["cagr"] > tq[k]["cagr"]
                and out["windows"][k]["max_drawdown"] < tq[k]["max_drawdown"])
        for k in ("10y", "5y")
    }
    out["pass_vs_winner"] = {
        "strict_dominance": {
            k: bool(out["windows"][k]["cagr"] > win[k]["cagr"]
                    and out["windows"][k]["max_drawdown"] < win[k]["max_drawdown"])
            for k in ("10y", "5y")
        },
        "lower_dd_cagr_within_2pp": {
            k: bool(out["windows"][k]["max_drawdown"] < win[k]["max_drawdown"]
                    and out["windows"][k]["cagr"] > win[k]["cagr"] - 0.02)
            for k in ("10y", "5y")
        },
    }

    OUT.joinpath("result.json").write_text(json.dumps(out, indent=2, default=float))
    print("windows")
    for label in ("10y", "5y"):
        w = out["windows"][label]
        print(f"  {label}: CAGR {w['cagr']*100:6.2f}%  DD {w['max_drawdown']*100:5.2f}%  "
              f"Sharpe {w['sharpe']:.2f}  fills {w['fills']}  end ${w['ending_equity']:,.0f}")
    print("ablation")
    for k, v in out["ablation"].items():
        print(f"  {k:16s} 10y {v['10y']['cagr']*100:6.2f}/{v['10y']['max_drawdown']*100:5.2f}   "
              f"5y {v['5y']['cagr']*100:6.2f}/{v['5y']['max_drawdown']*100:5.2f}")
    print("cost")
    for k, v in out["cost_sensitivity"].items():
        print(f"  {k:5s} 10y {v['10y']['cagr']*100:6.2f}/{v['10y']['max_drawdown']*100:5.2f}   "
              f"5y {v['5y']['cagr']*100:6.2f}/{v['5y']['max_drawdown']*100:5.2f}")
    print("rolling3y", out["rolling_3y_summary"])
    print("wrote", OUT / "result.json")


if __name__ == "__main__":
    main()
