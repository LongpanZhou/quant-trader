"""Intraday crash-stop overlay on a daily QQQ 165-day SMA regime.

Despite the agent's folder name, there is no mean-reversion entry here: this
is the 165d regime plus a fixed 3% stop measured from QQQ's prior close.  The
leaderboard labels it "3% prior-close stop".

Rules (long-only, no look-ahead, next-bar-open fills):

1. Regime, evaluated on the close of each regular-session day:
   QQQ close > 165-day SMA of QQQ closes  ->  target 100% TQQQ
   otherwise                              ->  target 100% BIL
   The regime decided at the 15:55-15:59 close is executed at the next
   session's 09:30 open.

2. Intraday crash stop while long TQQQ (5-minute closes by default):
   if QQQ trades at or below (1 - stop) x previous daily close at any
   intraday bar close, sell to BIL at the next bar's open and stay in BIL
   for the rest of that session, then re-enters at the next session's open
   if the regime is still on.

3. No other exits.  Overnight exposure is held while the regime is on.

Run:
    python research/agents/intraday-mean-reversion/strategy.py
    python .../strategy.py --rule 1min --stop 0.03
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

START10, START5, END = "2017-01-03", "2021-10-25", "2026-10-23"
BARS_PER_YEAR = {"1min": 252 * 390, "5min": 252 * 78}


def prepare(rule: str = "5min", sma_days: int = 165):
    """Load the panel and build the daily regime / prior-close features."""
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), START10, END, rule)
    dates = pd.Series(ts.date)
    dlist = dates.to_numpy()
    bars = dates.groupby(dates).cumcount().to_numpy()
    # Last bar of each session (13:00 on half days), not a global bar count.
    is_last = np.r_[dlist[1:] != dlist[:-1], True]

    # ---- daily regime from daily bars (same data the README baseline uses)
    tsd, _, cd = bt.panel(("QQQ", "TQQQ", "BIL"), START10, END, "1D")
    qd = cd[:, 0]
    daily = pd.DataFrame({"c": qd}, index=pd.Index([t.date() for t in tsd]))
    sma = daily["c"].rolling(sma_days).mean()
    reg = (daily["c"] > sma).astype(float)          # known at that day's close
    reg_today = reg.to_dict()
    reg_prev = reg.shift(1).to_dict()
    reg_next = np.where(is_last,
                        [reg_today.get(d, 0.0) for d in dlist],
                        [reg_prev.get(d, 0.0) for d in dlist])

    last_close = pd.Series(c[:, 0]).groupby(dlist).last()
    prev_close_map = last_close.shift(1).to_dict()
    qpc = np.array([prev_close_map.get(d, np.nan) for d in dlist])

    feats = dict(bars=bars, dlist=dlist, is_last=is_last, reg_next=reg_next,
                 qpc=qpc, qqq=c[:, 0], regime_on=float(np.nanmean(reg_next)))
    return ts, o, c, feats


def make_weights(feats, n, stop: float = 0.03, reenter_next_open: bool = True):
    """Long-only target weights; w[i] is set from data through bar i, filled at open i+1."""
    dlist, is_last = feats["dlist"], feats["is_last"]
    reg_next, qpc, qqq = feats["reg_next"], feats["qpc"], feats["qqq"]

    w = np.zeros((n, 3))
    w[:, 2] = 1.0
    pos = 0
    blocked = None
    stops = 0
    for i in range(n - 1):
        d = dlist[i]
        same_session = not is_last[i]
        if pos:
            mv = qqq[i] / qpc[i] - 1.0 if np.isfinite(qpc[i]) else 0.0
            if mv <= -stop:
                w[i, 1], w[i, 2] = 0.0, 1.0
                pos = 0
                blocked = d
                stops += 1
                continue
            if reg_next[i] < 0.5:
                w[i, 1], w[i, 2] = 0.0, 1.0
                pos = 0
                continue
            w[i, 1], w[i, 2] = 1.0, 0.0
            continue
        can_enter = reg_next[i] > 0.5 and not (blocked == d and (same_session or not reenter_next_open))
        if can_enter:
            w[i, 1], w[i, 2] = 1.0, 0.0
            pos = 1
    w[-1] = (0.0, 0.0, 1.0)
    return w, stops


def build(rule: str = "5min", stop: float = 0.03, sma_days: int = 165,
          reenter_next_open: bool = True):
    """Return (ts, opens, closes, weights, feats) for the full warmed-up panel."""
    ts, o, c, feats = prepare(rule, sma_days)
    w, stops = make_weights(feats, len(ts), stop, reenter_next_open)
    feats["stops"] = stops
    return ts, o, c, w, feats


def daily_marked(res):
    """Recompute stats on 15:59 marks only, so DD/Sharpe are comparable to daily bars."""
    eq = pd.Series(res["equity"], index=pd.DatetimeIndex(res["ts"]))
    cash = pd.Series(res["cash"], index=pd.DatetimeIndex(res["ts"]))
    last = eq.groupby(eq.index.date).last()
    lastc = cash.groupby(cash.index.date).last()
    tt = pd.DatetimeIndex([pd.Timestamp(d, tz="America/New_York") for d in last.index])
    return bt.stats({"equity": last.to_numpy(), "cash": lastc.to_numpy(), "fills": 0,
                     "turnover": 0.0, "ts": tt}, 252)


def metrics(ts, o, c, w, start, slippage_bps):
    """Same convention as every other agent: start at `start`'s first bar, 2% band."""
    i0 = bt.start_index(ts, start)
    res = bt.run(ts, o, c, w, start, band=0.02, slippage_bps=slippage_bps)
    s = bt.stats(res, BARS_PER_YEAR[RULE])
    b = bt.benchmark(c[i0:, 1], ts[i0:], BARS_PER_YEAR[RULE])
    return s, b, res, i0


def yearly_table(res, bench_close):
    y = bt.yearly(res["ts"], res["equity"], bench_close)
    return {int(k): {"strategy": round(v["strategy"], 6), "benchmark": round(v["benchmark"], 6)}
            for k, v in y.items()}


RULE = "5min"


def main():
    global RULE
    ap = argparse.ArgumentParser()
    ap.add_argument("--rule", default="5min", choices=["1min", "5min"])
    ap.add_argument("--stop", type=float, default=0.03)
    ap.add_argument("--sma", type=int, default=165)
    ap.add_argument("--slip", type=float, default=1.0)
    ap.add_argument("--json", action="store_true",
                    help="write strategy_run.json and refresh result.json headline windows")
    args = ap.parse_args()
    RULE = args.rule

    ts, o, c, w, feats = build(args.rule, args.stop, args.sma)
    out = {"rule": args.rule, "stop": args.stop, "sma_days": args.sma,
           "cost_bps": args.slip, "windows": {}, "yearly": {}, "stops_triggered": int(feats["stops"])}

    for start, key in ((START10, "10y"), (START5, "5y")):
        s, b, res, i0 = metrics(ts, o, c, w, start, args.slip)
        out["windows"][key] = {
            "start": start, "end": END,
            "cagr": round(s["cagr"], 6), "max_drawdown": round(s["max_drawdown"], 6),
            "sharpe": round(s["sharpe"], 4), "sortino": round(s["sortino"], 4),
            "volatility": round(s["volatility"], 6), "exposure": round(s["exposure"], 4),
            "fills": int(s["fills"]), "turnover": round(s["turnover"], 1),
            "ending_equity": round(s["ending_equity"], 2), "years": round(s["years"], 3),
            "bench_cagr": round(b["cagr"], 6), "bench_max_drawdown": round(b["max_drawdown"], 6),
            "bench_sharpe": round(b["sharpe"], 4),
        }
        if key == "10y":
            out["yearly"] = yearly_table(res, c[i0:, 1])
        bt.print_summary(f"{key} @ {args.slip:.0f}bp", s, b)
        dm = daily_marked(res)
        out["windows"][key].update({
            "daily_marked_cagr": round(dm["cagr"], 6),
            "daily_marked_max_drawdown": round(dm["max_drawdown"], 6),
            "daily_marked_sharpe": round(dm["sharpe"], 4),
        })
        print(f"  daily-marked: CAGR {dm['cagr']*100:6.2f}%  DD {dm['max_drawdown']*100:5.2f}%  "
              f"Sharpe {dm['sharpe']:4.2f}")

    # cost sensitivity
    out["cost_sensitivity"] = {}
    for slip in (0.0, 1.0, 5.0, 10.0, 20.0):
        row = {}
        for start, key in ((START10, "10y"), (START5, "5y")):
            s, b, _, _ = metrics(ts, o, c, w, start, slip)
            row[key] = {"cagr": round(s["cagr"], 6), "max_drawdown": round(s["max_drawdown"], 6)}
        out["cost_sensitivity"][f"{slip:.0f}bp"] = row
        print(f"  {slip:4.0f}bp  10y {row['10y']['cagr']*100:6.2f}%/{row['10y']['max_drawdown']*100:5.2f}%"
              f"   5y {row['5y']['cagr']*100:6.2f}%/{row['5y']['max_drawdown']*100:5.2f}%")

    if args.json:
        path = HERE / "strategy_run.json"
        path.write_text(json.dumps(out, indent=2))
        print("wrote", path)
        if args.rule == "5min" and args.stop == 0.03 and args.sma == 165 and args.slip == 1.0:
            res_path = HERE / "result.json"
            res = json.loads(res_path.read_text(encoding="utf-8"))
            res["windows"] = out["windows"]
            res["windows_note"] = ("headline windows regenerated by strategy.py --json "
                                   "(per-session close detection, 2% band, bt.run start)")
            res_path.write_text(json.dumps(res, indent=2), encoding="utf-8")
            print("updated", res_path)


if __name__ == "__main__":
    main()
