"""Round 2, agent 23: volume / order-flow proxies.

Final strategy -- "participation-armed crash stop":

  1. Daily regime (round-1 gate): hold 100% TQQQ while QQQ's prior close is
     above its 165-day SMA, else 100% BIL.
  2. Intraday stop: on a risk-on session, if TQQQ trades 4% below the session
     open the position is liquidated at the next minute's open and stays in
     BIL for the rest of the session and the following night.
  3. Volume arming (the new part).  Let

         rvol(i) = (QQQ volume from 09:30 through minute i)
                   / (mean of the same quantity over the prior 20 sessions
                      at the same minute of day)

     The stop is honoured at minute i only if rvol(i) > 1.0, i.e. only when
     participation is at least normal.  It is additionally armed when
     rvol(i) > 1.5 even if QQQ is above its 20-day MA.

     armed(i) = ( qqq_0930 < MA20(prev) * 1.01  OR  rvol(i) > 1.5 )
                AND rvol(i) > 1.0

  Everything is causal: rvol(i) uses bars <= i, the MA20 uses closes through
  the prior session, and weights set at bar i fill at bar i+1's open.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/agents2/volume-orderflow/strategy.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402
import engine  # noqa: E402
import fastsim  # noqa: E402

OUT = HERE
START10, START5, END = "2017-01-03", "2021-10-25", "2026-10-23"
BARS = 252 * 390
STOP = 0.04
MA_N = 20
ARM_BUF = 0.01
RV_HI = 1.5
RV_FLOOR = 1.0


def build_weights(D, stop=STOP, ma_n=MA_N, buf=ARM_BUF, hi=RV_HI, floor=RV_FLOOR):
    """Return (weights, stop-event list)."""
    ma = pd.Series(D.qc).rolling(ma_n).mean().to_numpy()
    mprev = np.r_[np.nan, ma[:-1]]
    w = np.zeros((D.n, 3))
    hold = np.ones(D.n, bool)
    hold[~D.reg_bar] = False
    events = []
    for d in range(D.nd):
        if not D.reg[d]:
            continue
        f, l = int(D.first[d]), int(D.last[d])
        # Index the per-day (time-of-day) matrices by each bar's own minute, so
        # rv lines up with D.cl[f:l+1] even on sessions with missing minutes.
        a_ma = bool(np.isfinite(mprev[d]) and D.cl[f, 0] < mprev[d] * (1 + buf))
        rv = D.rvol_cum_q[d, D.tod[f:l + 1]]
        ok = np.isfinite(rv)
        armed = ((a_ma | (ok & (rv > hi))) & ok & (rv > floor))
        hit = armed & (D.cl[f:l + 1, 1] < D.to[d] * (1 - stop))
        if hit.any():
            j = int(np.argmax(hit))
            hold[f + j:l + 1] = False
            events.append({"date": str(D.dates[f]), "minute_of_day": int(D.tod[f + j]),
                           "rvol": float(rv[j]), "rearmed_by_volume": bool(rv[j] > hi),
                           "qqq_below_ma20_at_open": a_ma})
    w[:, 1] = hold.astype(float)
    w[:, 2] = 1 - w[:, 1]
    return w, events


def detail(D, w, start, slip, bench_k=1):
    i = bt.start_index(D.ts, start)
    res = fastsim.fast_sim(D.op[i:], D.cl[i:], w[i:], band=0.02, slippage_bps=slip)
    res["ts"] = D.ts[i:]
    s = bt.stats(res, BARS)
    s["bench"] = bt.benchmark(D.cl[i:, bench_k], D.ts[i:], BARS)
    s["yearly"] = {str(k): v for k, v in bt.yearly(D.ts[i:], res["equity"],
                                                   D.cl[i:, bench_k]).items()}
    eq = pd.Series(res["equity"], index=res["ts"])
    deq = eq.groupby(eq.index.date).last().to_numpy()
    peak = np.maximum.accumulate(deq)
    s["max_drawdown_daily_marks"] = float(-(deq / peak - 1.0).min())
    return s


def main():
    D = engine.Data()
    w, events = build_weights(D)
    w_win, _ = engine.winner_weights(D)

    out = {
        "agent": "volume-orderflow",
        "strategy": "165d QQQ regime + 4% minute stop armed by relative volume",
        "rules": {
            "regime": "QQQ prior close > 165-day SMA -> TQQQ, else BIL",
            "stop": f"{STOP*100:.0f}% below session open, next-minute fill, "
                    "out for the rest of the session and the overnight",
            "arming": f"(QQQ@09:30 < MA{MA_N}(prev)*{1+ARM_BUF:.2f} or rvol>{RV_HI}) "
                      f"and rvol>{RV_FLOOR}",
            "rvol": "cumulative QQQ volume / 20-day same-time-of-day mean",
            "fills": "next bar open", "band": 0.02,
        },
        "diagnostics": {"stop_events": len(events),
                        "rearmed_by_volume": int(sum(e["rearmed_by_volume"] for e in events)),
                        "events_by_year": {}},
        "windows": {}, "winner_reference": {}, "cost_sensitivity": {},
        "ablation": {}, "rolling_3y": {}, "negative_tests": {},
    }
    yrs = {}
    for e in events:
        y = e["date"][:4]
        yrs[y] = yrs.get(y, 0) + 1
    out["diagnostics"]["events_by_year"] = dict(sorted(yrs.items()))
    out["diagnostics"]["events"] = events

    for label, start in (("10y", START10), ("5y", START5)):
        s = detail(D, w, start, 1.0)
        sw = detail(D, w_win, start, 1.0)
        out["windows"][label] = {k: s[k] for k in
                                 ("cagr", "total_return", "max_drawdown",
                                  "max_drawdown_daily_marks", "sharpe", "sortino",
                                  "volatility", "exposure", "fills", "turnover",
                                  "ending_equity", "years", "yearly")}
        out["windows"][label]["benchmark"] = s["bench"]
        out["winner_reference"][label] = {
            "cagr": sw["cagr"], "max_drawdown": sw["max_drawdown"],
            "max_drawdown_daily_marks": sw["max_drawdown_daily_marks"],
            "sharpe": sw["sharpe"], "fills": sw["fills"], "turnover": sw["turnover"]}

    for slip in (1.0, 5.0, 10.0):
        out["cost_sensitivity"][f"{slip:.0f}bp"] = {}
        for label, start in (("10y", START10), ("5y", START5)):
            s = detail(D, w, start, slip)
            out["cost_sensitivity"][f"{slip:.0f}bp"][label] = {
                k: s[k] for k in ("cagr", "max_drawdown", "sharpe", "fills", "turnover")}

    # ablations: which half of the arming rule matters?
    for name, kw in (("volume_floor_only", dict(hi=99.0)),
                     ("high_volume_rearm_only", dict(floor=0.0)),
                     ("neither_round1_winner", dict(hi=99.0, floor=0.0))):
        wv, _ = build_weights(D, **kw)
        out["ablation"][name] = {}
        for label, start in (("10y", START10), ("5y", START5)):
            s = detail(D, wv, start, 1.0)
            out["ablation"][name][label] = {
                "cagr": s["cagr"], "max_drawdown": s["max_drawdown"], "fills": s["fills"]}

    # rolling 3y, candidate vs winner, beat-the-winner counts
    r3 = engine.rolling3y(D, w, START10, 1.0)
    r3w = engine.rolling3y(D, w_win, START10, 1.0)
    out["rolling_3y"]["candidate"] = r3
    out["rolling_3y"]["winner"] = r3w
    out["rolling_3y"]["summary"] = {
        "n": len(r3),
        "beat_tqqq_cagr": int(sum(r["cagr"] > r["bench_cagr"] for r in r3)),
        "lower_dd_than_tqqq": int(sum(r["dd"] < r["bench_dd"] for r in r3)),
        "beat_winner_cagr": int(sum(a["cagr"] > b["cagr"] for a, b in zip(r3, r3w))),
        "lower_dd_than_winner": int(sum(a["dd"] < b["dd"] for a, b in zip(r3, r3w))),
    }

    # pass / fail
    tq = {"10y": (0.3928, 0.8168), "5y": (0.1347, 0.8168)}
    out["pass_vs_tqqq"] = {
        k: bool(out["windows"][k]["cagr"] > tq[k][0]
                and out["windows"][k]["max_drawdown"] < tq[k][1]) for k in ("10y", "5y")}
    out["pass_vs_winner_strict_dominance"] = {
        k: bool(out["windows"][k]["cagr"] > out["winner_reference"][k]["cagr"]
                and out["windows"][k]["max_drawdown"]
                < out["winner_reference"][k]["max_drawdown"]) for k in ("10y", "5y")}

    # single-event sensitivity: restore the 2026-06-24 stop the volume floor removed
    w2 = w.copy()
    dd = {str(D.dates[D.first[d]]): d for d in range(D.nd)}
    if "2026-06-24" in dd:
        d = dd["2026-06-24"]
        hit = np.flatnonzero(w[D.first[d]:D.last[d] + 1, 1] == 0)
        if len(hit) == 0:
            i0 = D.first[d]
            for i in range(i0, D.last[d] + 1):
                if D.cl[i, 1] < D.to[d] * (1 - STOP):
                    w2[i:D.last[d] + 1, 1] = 0.0
                    w2[i:D.last[d] + 1, 2] = 1.0
                    break
    out["single_event_sensitivity"] = {
        "note": "re-enabling the 2026-06-24 stop (rvol 0.87, suppressed by the floor)",
    }
    for label, start in (("10y", START10), ("5y", START5)):
        s = detail(D, w2, start, 1.0)
        out["single_event_sensitivity"][label] = {
            "cagr": s["cagr"], "max_drawdown": s["max_drawdown"]}

    # compact negative-test summary (measured in explore1/3/robustness.py)
    out["negative_tests"] = {
        "1m_clv_flow_vs_next30m_corr": -0.0101,
        "1m_vwap_dev_vs_next30m_corr": -0.0088,
        "1m_cum_rvol_vs_next30m_corr": -0.0468,
        "5m_cum_flow_vs_next30m_corr": 0.0011,
        "5m_vwap_dev_vs_next30m_corr": 0.0070,
        "5m_cum_rvol_vs_next30m_corr": 0.0061,
        "first30_return_vs_last30_corr": 0.022,
        "overnight_gate_rvol1.5_10y": [0.5735, 0.4452],
        "overnight_gate_rvol1.5_5y": [0.4108, 0.3614],
        "volume_confirmed_regime_exit_10y": [0.5118, 0.5230],
        "distribution_day_overlay_10y": [0.0914, 0.3823],
        "vwap165_regime_10y": [0.4708, 0.5803],
        "note": "all rejected; see report.md section 7",
    }

    (OUT / "result.json").write_text(json.dumps(out, indent=2, default=float))
    for label in ("10y", "5y"):
        s, sw = out["windows"][label], out["winner_reference"][label]
        print(f"{label}: {s['cagr']*100:6.2f}%/{s['max_drawdown']*100:5.2f}%  "
              f"(winner {sw['cagr']*100:6.2f}%/{sw['max_drawdown']*100:5.2f}%)  "
              f"fills {s['fills']}")
    print("wrote", OUT / "result.json")


if __name__ == "__main__":
    main()
