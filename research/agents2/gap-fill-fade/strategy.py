"""Opening-gap fade overlay on the 165-day QQQ regime + armed 4% minute stop.

Base strategy (the round-1 winner)
----------------------------------
1. Regime: QQQ's prior daily close above its 165-day SMA -> risk-on for the next
   session, otherwise 100% BIL.
2. Risk-on sessions hold 100% TQQQ, including overnight.
3. Arm a 4% stop from the session open only when QQQ's first-minute close is
   below its prior 20-day SMA times 1.01. If TQQQ closes 4% below the open,
   sell at the next minute's open and stay in BIL for the rest of the session
   and the following night.

Gap overlay (this agent)
------------------------
On a risk-on day that is *armed* and whose QQQ opening gap is between +0.15%
and +0.50% versus the prior close, sell TQQQ at the 09:31 open and hold BIL
until the close. Re-enter TQQQ at the 15:59 open (the last executable minute)
unless TQQQ traded 4% below the session open at any point, in which case stay
in BIL overnight (the crash filter that the base stop would have provided).

Why these bounds: the local sample and the cited gap literature both show a
size split. Gaps below ~0.15% are noise and drift up intraday; gaps above
~1% are news and continue. The fade is concentrated in the small-gap band,
which is roughly 0.10-0.34x QQQ's median 14-day ATR of 1.49%.

Everything is causal: the gap and the 09:30 first-minute close are known at the
09:30 bar close, the sell fills at the 09:31 open, the re-entry decision is made
from data through the 15:58 close and fills at the 15:59 open. No look-ahead.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/agents2/gap-fill-fade/strategy.py
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
GAP_LO = 0.0015
GAP_HI = 0.0050
BARS_PER_YEAR = 252 * 390
OUT = Path(__file__).resolve().parent


# --------------------------------------------------------------------------
# weights
# --------------------------------------------------------------------------
def _sessions(ts: pd.DatetimeIndex):
    dates = np.array([t.date() for t in ts])
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(ts) - 1]
    return dates, first, last


def build_weights(ts, opens, closes, gap_lo=GAP_LO, gap_hi=GAP_HI,
                  use_overlay=True, prior_up_only=False, lookback_gap=None,
                  stop=STOP, sma_n=SMA_N, ma_fast=MA_FAST, arm_buf=ARM_BUF,
                  overlay_delay=0):
    """Return (weights, diagnostics).

    `lookback_gap` is an optional (lo, hi) pair used by the parameter sweep;
    when given it overrides gap_lo/gap_hi.
    """
    if lookback_gap is not None:
        gap_lo, gap_hi = lookback_gap
    dates, first, last = _sessions(ts)
    n = len(ts)
    qqq_close = closes[:, 0]
    tqqq_close = closes[:, 1]
    dclose = qqq_close[last]
    sma = pd.Series(dclose).rolling(sma_n).mean().to_numpy()
    ma20 = pd.Series(dclose).rolling(ma_fast).mean().to_numpy()
    sma_prev = np.r_[np.nan, sma[:-1]]
    ma20_prev = np.r_[np.nan, ma20[:-1]]
    prior_close = np.r_[np.nan, dclose[:-1]]
    gap = opens[first, 0] / prior_close - 1.0
    prior_up = np.r_[False, False, dclose[1:-1] > dclose[:-2]] if len(dclose) > 2 else np.zeros(len(dclose), bool)

    hold = np.zeros(n, dtype=bool)
    stops = []
    overlay_days = []
    for k, (f, l) in enumerate(zip(first, last)):
        if k == 0 or not np.isfinite(sma_prev[k]):
            continue
        risk_on = bool(dclose[k - 1] > sma_prev[k])
        if not risk_on:
            continue
        armed = bool(np.isfinite(ma20_prev[k]) and qqq_close[f] < ma20_prev[k] * (1.0 + arm_buf))
        base = opens[f, 1]
        state = True
        stopped_reentry = False
        for i in range(f, l + 1):
            if armed and state and tqqq_close[i] < base * (1.0 - stop):
                state = False
                stops.append({"date": str(dates[f]), "time": str(ts[i].time())})
            if armed and i < l and tqqq_close[i] < base * (1.0 - stop):
                stopped_reentry = True
            hold[i] = state

        # gap fade overlay
        if (use_overlay and armed and gap_lo <= gap[k] <= gap_hi
                and (not prior_up_only or prior_up[k])):
            overlay_days.append({"date": str(dates[f]), "gap": float(gap[k]),
                                 "stopped": bool(stopped_reentry)})
            sig = min(f + overlay_delay, l - 2)
            hold[sig:l - 1] = False
            hold[l - 1] = not stopped_reentry

    weights = np.zeros((n, 3))
    weights[:, 1] = hold.astype(float)
    weights[:, 2] = 1.0 - weights[:, 1]
    return weights, {"stops": stops, "overlay_days": overlay_days,
                     "n_stops": len(stops), "n_overlay": len(overlay_days)}


# --------------------------------------------------------------------------
# exact 0/1 specialization of bt.simulate (used only for sweeps)
# --------------------------------------------------------------------------
def fast_run(ts, opens, closes, weights, start, slippage_bps=1.0,
             start_equity=100_000.0):
    i0 = bt.start_index(ts, start)
    o, c, w = opens[i0:], closes[i0:], np.asarray(weights[i0:], float)
    n = len(o)
    slip = slippage_bps / 10_000.0
    tgt = np.where(w.sum(axis=1) > 0.5, np.argmax(w, axis=1), -1)
    exec_tgt = np.r_[tgt[0], tgt[:-1]]
    chg = np.flatnonzero(exec_tgt[1:] != exec_tgt[:-1]) + 1
    change_idx = np.unique(np.r_[1, chg])
    equity = np.empty(n)
    equity[0] = start_equity
    asset, units, cash = -1, 0.0, start_equity
    fills, traded, pos = 0, 0.0, 1
    for ci in change_idx:
        if ci == 0:
            continue
        if ci > pos:
            equity[pos:ci] = units * c[pos:ci, asset] if asset >= 0 else cash
        b = exec_tgt[ci]
        if b != asset:
            if asset >= 0:
                cash = units * o[ci, asset] * (1.0 - slip)
                traded += units * o[ci, asset]
                fills += 1
                units = 0.0
            asset = -1
            if b >= 0 and cash > 0:
                units = cash / (o[ci, b] * (1.0 + slip))
                traded += cash
                fills += 1
                cash = 0.0
                asset = b
        pos = ci
    if pos < n:
        equity[pos:] = units * c[pos:, asset] if asset >= 0 else cash
    return {"ts": ts[i0:], "equity": equity, "cash": np.zeros(n),
            "fills": fills, "turnover": traded / start_equity}


def stats_fast(ts, opens, closes, weights, start, slip):
    return bt.stats(fast_run(ts, opens, closes, weights, start, slip), BARS_PER_YEAR)


# --------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------
def window_metrics(result, ts, close_tqqq, start):
    s = bt.stats(result, BARS_PER_YEAR)
    i = bt.start_index(ts, start)
    eq = pd.Series(result["equity"], index=ts[i:])
    deq = eq.groupby(eq.index.date).last().to_numpy()
    peak = np.maximum.accumulate(deq)
    s["max_drawdown_daily_marks"] = float(-(deq / peak - 1.0).min())
    s["bench"] = bt.benchmark(close_tqqq[i:], ts[i:], BARS_PER_YEAR)
    s["yearly"] = bt.yearly(ts[i:], result["equity"], close_tqqq[i:])
    return s


def rolling_3y(ts, opens, closes, weights, tq_close):
    rows = []
    for st in pd.date_range("2017-04-03", "2023-10-02", freq="QS"):
        st = st.strftime("%Y-%m-%d")
        en = (pd.Timestamp(st) + pd.DateOffset(years=3)).strftime("%Y-%m-%d")
        i0 = bt.start_index(ts, st)
        i1 = int(ts.searchsorted(pd.Timestamp(en, tz="America/New_York")))
        a = stats_fast(ts[i0:i1], opens[i0:i1], closes[i0:i1], weights[i0:i1], st, 1.0)
        b = bt.benchmark(tq_close[i0:i1], ts[i0:i1], BARS_PER_YEAR)
        rows.append({"start": st, "cagr": a["cagr"], "max_drawdown": a["max_drawdown"],
                     "tqqq_cagr": b["cagr"], "tqqq_max_drawdown": b["max_drawdown"]})
    return rows


def gap_bucket_table(ts, opens, closes, start="2017-01-03"):
    dates, first, last = _sessions(ts)
    dclose = closes[last, 0]
    sma = pd.Series(dclose).rolling(SMA_N).mean().to_numpy()
    reg = np.zeros(len(dclose), bool)
    reg[1:] = dclose[:-1] > sma[:-1]
    gap = opens[first, 0] / np.r_[np.nan, dclose[:-1]] - 1.0
    fwd = opens[first + 1, 1]  # 09:31 open
    ret = closes[last, 1] / fwd - 1.0
    bins = [-1, -0.02, -0.01, -0.005, -0.002, -0.0005, 0.0005, 0.0015,
            0.002, 0.005, 0.0075, 0.01, 0.02, 1]
    labels = ["<-2", "-2..-1", "-1..-.5", "-.5..-.2", "-.2..-.05",
              "-.05..+.05", "+.05..+.15", "+.15..+.2", "+.2..+.5",
              "+.5..+.75", "+.75..+1", "+1..+2", ">+2"]
    st = pd.Timestamp(start).date()
    rows = []
    for lab, lo, hi in zip(labels, bins[:-1], bins[1:]):
        mask = reg & (np.array(dates[first]) >= st) & (gap >= lo) & (gap < hi)
        x = ret[mask]
        if len(x) == 0:
            continue
        rows.append({"bucket": lab, "n": int(len(x)), "mean_pct": float(x.mean() * 100),
                     "median_pct": float(np.median(x) * 100),
                     "win_rate": float((x > 0).mean()),
                     "t_stat": float(x.mean() / x.std() * np.sqrt(len(x))) if len(x) > 1 else 0.0})
    return rows


def standalone_fade(ts, opens, closes, tqqq_volume, gap_th=0.01, target="vwap", stop=0.02):
    """Long-only gap-down fade at 09:31, exit at VWAP or the close, 2% stop."""
    dates, first, last = _sessions(ts)
    dclose = closes[last, 0]
    sma = pd.Series(dclose).rolling(SMA_N).mean().to_numpy()
    reg = np.zeros(len(dclose), bool)
    reg[1:] = dclose[:-1] > sma[:-1]
    gap = opens[first, 0] / np.r_[np.nan, dclose[:-1]] - 1.0
    n = len(ts)
    w = np.zeros((n, 3))
    w[:, 2] = 1.0
    tclose = closes[:, 1]
    trades = []
    for k, (f, l) in enumerate(zip(first, last)):
        if k == 0 or not reg[k] or gap[k] > -gap_th:
            continue
        e = f + 1
        entry = opens[e, 1]
        pv = np.cumsum(tclose[f:l + 1] * tqqq_volume[f:l + 1])
        vv = np.cumsum(tqqq_volume[f:l + 1])
        vwap = pv / np.maximum(vv, 1)
        exit_i = l - 1
        for i in range(e, l):
            if tclose[i] < entry * (1.0 - stop):
                exit_i = i
                break
            if target == "vwap" and tclose[i] >= vwap[i - f]:
                exit_i = i
                break
        w[f, 1], w[f, 2] = 1.0, 0.0
        w[f:exit_i, 1], w[f:exit_i, 2] = 1.0, 0.0
        w[exit_i, 1], w[exit_i, 2] = 0.0, 1.0
        px = opens[min(exit_i + 1, l), 1]
        trades.append(px / entry - 1.0)
    tr = np.array(trades)
    return w, {"n": len(tr), "mean_pct": float(tr.mean() * 100) if len(tr) else 0.0,
               "win_rate": float((tr > 0).mean()) if len(tr) else 0.0}


# --------------------------------------------------------------------------
def main():
    ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), START10, END, "1min")
    dates, first, last = _sessions(ts)
    weights, diag = build_weights(ts, opens, closes)
    winner_w, winner_diag = build_weights(ts, opens, closes, use_overlay=False)

    out = {
        "agent": "gap-fill-fade",
        "strategy": {
            "base": "QQQ prior close > 165-day SMA -> 100% TQQQ, else BIL; "
                    "armed 4% minute stop from the session open",
            "overlay": f"on risk-on armed days with QQQ gap in [+{GAP_LO*100:.2f}%, "
                       f"+{GAP_HI*100:.2f}%]: sell TQQQ at the 09:31 open, hold BIL "
                       "to the close, re-enter at the 15:59 open unless TQQQ traded "
                       "4% below the open (then stay BIL overnight)",
            "fills": "next bar open",
            "costs": "1 bp one-way; 5 and 10 bp reported",
        },
        "parameters": {"sma": SMA_N, "ma_fast": MA_FAST, "stop": STOP,
                       "arm_buf": ARM_BUF, "gap_lo": GAP_LO, "gap_hi": GAP_HI},
        "diagnostics": {"overlay_days": diag["n_overlay"],
                        "stop_events": diag["n_stops"],
                        "overlay_days_stopped": int(sum(d["stopped"] for d in diag["overlay_days"]))},
        "windows": {},
        "winner_reference": {},
        "tqqq_reference": {"10y": {"cagr": 0.3928, "max_drawdown": 0.8168},
                           "5y": {"cagr": 0.1347, "max_drawdown": 0.8168}},
    }

    for slip in (1.0, 5.0, 10.0):
        for label, start in (("10y", START10), ("5y", START5)):
            r = bt.run(ts, opens, closes, weights, start, band=0.02, slippage_bps=slip)
            s = window_metrics(r, ts, closes[:, 1], start)
            out["windows"].setdefault(label, {})[f"{slip:.0f}bp"] = {
                "cagr": s["cagr"], "max_drawdown": s["max_drawdown"],
                "max_drawdown_daily_marks": s["max_drawdown_daily_marks"],
                "sharpe": s["sharpe"], "sortino": s["sortino"],
                "volatility": s["volatility"], "fills": s["fills"],
                "turnover": s["turnover"], "ending_equity": s["ending_equity"],
                "yearly": {str(k): v for k, v in s["yearly"].items()},
            }

    # winner reference at the same costs (for the pass/fail table)
    for slip in (1.0, 5.0, 10.0):
        for label, start in (("10y", START10), ("5y", START5)):
            s = stats_fast(ts, opens, closes, winner_w, start, slip)
            out["winner_reference"].setdefault(label, {})[f"{slip:.0f}bp"] = {
                "cagr": s["cagr"], "max_drawdown": s["max_drawdown"],
                "sharpe": s["sharpe"], "fills": s["fills"]}

    # pass / fail
    w = out["windows"]
    wr = out["winner_reference"]
    out["pass"] = {
        "vs_tqqq_1bp": {
            "10y": w["10y"]["1bp"]["cagr"] > 0.3928 and w["10y"]["1bp"]["max_drawdown"] < 0.8168,
            "5y": w["5y"]["1bp"]["cagr"] > 0.1347 and w["5y"]["1bp"]["max_drawdown"] < 0.8168,
        },
        "strict_dominance_vs_winner_1bp": {
            "10y": w["10y"]["1bp"]["cagr"] > wr["10y"]["1bp"]["cagr"]
                   and w["10y"]["1bp"]["max_drawdown"] < wr["10y"]["1bp"]["max_drawdown"],
            "5y": w["5y"]["1bp"]["cagr"] > wr["5y"]["1bp"]["cagr"]
                  and w["5y"]["1bp"]["max_drawdown"] < wr["5y"]["1bp"]["max_drawdown"],
        },
        "strict_dominance_vs_winner_5bp": {
            "10y": w["10y"]["5bp"]["cagr"] > wr["10y"]["5bp"]["cagr"]
                   and w["10y"]["5bp"]["max_drawdown"] < wr["10y"]["5bp"]["max_drawdown"],
            "5y": w["5y"]["5bp"]["cagr"] > wr["5y"]["5bp"]["cagr"]
                  and w["5y"]["5bp"]["max_drawdown"] < wr["5y"]["5bp"]["max_drawdown"],
        },
        "dd_within_2pp_cagr_vs_winner_10bp": {
            "10y": w["10y"]["10bp"]["max_drawdown"] < wr["10y"]["10bp"]["max_drawdown"]
                   and w["10y"]["10bp"]["cagr"] > wr["10y"]["10bp"]["cagr"] - 0.02,
            "5y": w["5y"]["10bp"]["max_drawdown"] < wr["5y"]["10bp"]["max_drawdown"]
                  and w["5y"]["10bp"]["cagr"] > wr["5y"]["10bp"]["cagr"] - 0.02,
        },
    }

    # rolling 3y
    tq = closes[:, 1]
    rs = rolling_3y(ts, opens, closes, weights, tq)
    rw = rolling_3y(ts, opens, closes, winner_w, tq)
    df = pd.DataFrame(rs)
    dfw = pd.DataFrame(rw)
    out["rolling_3y"] = {
        "windows_vs_tqqq": len(df),
        "return_wins_vs_tqqq": int((df.cagr > df.tqqq_cagr).sum()),
        "dd_wins_vs_tqqq": int((df.max_drawdown < df.tqqq_max_drawdown).sum()),
        "both_wins_vs_tqqq": int(((df.cagr > df.tqqq_cagr)
                                 & (df.max_drawdown < df.tqqq_max_drawdown)).sum()),
        "return_wins_vs_winner": int((df.cagr.values > dfw.cagr.values).sum()),
        "dd_wins_vs_winner": int((df.max_drawdown.values < dfw.max_drawdown.values).sum()),
        "both_wins_vs_winner": int(((df.cagr.values > dfw.cagr.values)
                                   & (df.max_drawdown.values < dfw.max_drawdown.values)).sum()),
        "windows": df.round(6).to_dict("records"),
    }

    # parameter plateau (1 and 5 bp)
    plateau = []
    for lo in (0.0010, 0.0015, 0.0020, 0.0025):
        for hi in (0.0040, 0.0050, 0.0075):
            ww, dd = build_weights(ts, opens, closes, gap_lo=lo, gap_hi=hi)
            row = {"gap_lo": lo, "gap_hi": hi, "n": dd["n_overlay"]}
            for slip in (1.0, 5.0):
                for label, start in (("10y", START10), ("5y", START5)):
                    s = stats_fast(ts, opens, closes, ww, start, slip)
                    row[f"{label}_{int(slip)}bp_cagr"] = s["cagr"]
                    row[f"{label}_{int(slip)}bp_dd"] = s["max_drawdown"]
            plateau.append(row)
    out["plateau"] = plateau

    # prior-day-up variant (the "with prior trend" branch)
    prior = []
    for lo, hi in ((0.0015, 0.005), (0.0015, 0.0075), (0.0020, 0.005)):
        ww, dd = build_weights(ts, opens, closes, gap_lo=lo, gap_hi=hi, prior_up_only=True)
        row = {"gap_lo": lo, "gap_hi": hi, "n": dd["n_overlay"]}
        for slip in (1.0, 5.0):
            for label, start in (("10y", START10), ("5y", START5)):
                s = stats_fast(ts, opens, closes, ww, start, slip)
                row[f"{label}_{int(slip)}bp_cagr"] = s["cagr"]
                row[f"{label}_{int(slip)}bp_dd"] = s["max_drawdown"]
        prior.append(row)
    out["prior_up_variant"] = prior

    # sub-periods
    sub = {}
    for stt, en in (("2017-01-03", "2019-12-31"), ("2020-01-01", "2022-12-31"),
                    ("2023-01-01", "2026-10-23"), (START5, END)):
        i0 = bt.start_index(ts, stt)
        i1 = int(ts.searchsorted(pd.Timestamp(en, tz="America/New_York")))
        for nm, ww in (("strategy", weights), ("winner", winner_w)):
            s = bt.stats(fast_run(ts[i0:i1], opens[i0:i1], closes[i0:i1],
                                  ww[i0:i1], stt, 1.0), BARS_PER_YEAR)
            sub.setdefault(f"{stt}..{en}", {})[nm] = {
                "cagr": s["cagr"], "max_drawdown": s["max_drawdown"],
                "sharpe": s["sharpe"]}
    out["sub_periods"] = sub

    # drawdown episodes, 1 bp
    def episodes(ww):
        r = fast_run(ts, opens, closes, ww, START10, 1.0)
        eq, t = r["equity"], r["ts"]
        peak = np.maximum.accumulate(eq)
        dd = eq / peak - 1.0
        rows = []
        for _ in range(3):
            j = int(np.argmin(dd))
            p = int(np.argmax(eq[:j + 1]))
            rows.append({"peak": str(t[p]), "trough": str(t[j]),
                         "drawdown": float(dd[j])})
            dd[:j + 1] = 0.0
        return rows
    out["dd_episodes_10y"] = {"strategy": episodes(weights),
                              "winner": episodes(winner_w)}

    # overlay event study
    day_index = {str(d): k for k, d in enumerate(dates[first])}
    t1559 = opens[last, 1]
    ev = []
    for d in diag["overlay_days"]:
        k = day_index[d["date"]]
        entry = opens[first[k] + 1, 1]
        pnl = -(t1559[k] / entry - 1.0)
        ev.append({"date": d["date"], "gap": d["gap"], "stopped": d["stopped"],
                   "pnl": float(pnl),
                   "year": int(pd.Timestamp(d["date"]).year)})
    evdf = pd.DataFrame(ev)
    evdf = evdf[evdf.date >= START10]
    out["event_study"] = {
        "n": int(len(evdf)),
        "mean_pct": float(evdf.pnl.mean() * 100),
        "median_pct": float(evdf.pnl.median() * 100),
        "win_rate": float((evdf.pnl > 0).mean()),
        "t_stat": float(evdf.pnl.mean() / evdf.pnl.std() * np.sqrt(len(evdf))),
        "stopped_days": int(evdf.stopped.sum()),
        "by_year": {str(y): {"n": int(g.pnl.size),
                             "mean_pct": float(g.pnl.mean() * 100),
                             "total_pct": float(((1 + g.pnl).prod() - 1) * 100),
                             "stopped": int(g.stopped.sum())}
                    for y, g in evdf.groupby("year")},
        "largest_gains": evdf.sort_values("pnl").tail(8).round(6).to_dict("records"),
    }

    # robustness: regime SMA x stop
    rob = []
    for sma in (150, 165, 180):
        for stp in (0.03, 0.04, 0.05):
            base_w, _ = build_weights(ts, opens, closes, use_overlay=False,
                                      sma_n=sma, stop=stp)
            ov_w, ovd = build_weights(ts, opens, closes, sma_n=sma, stop=stp)
            row = {"sma": sma, "stop": stp, "n": ovd["n_overlay"]}
            for slip in (1.0, 5.0):
                for label, start in (("10y", START10), ("5y", START5)):
                    a = stats_fast(ts, opens, closes, base_w, start, slip)
                    b = stats_fast(ts, opens, closes, ov_w, start, slip)
                    row[f"base_{label}_{int(slip)}bp"] = {
                        "cagr": a["cagr"], "max_drawdown": a["max_drawdown"]}
                    row[f"overlay_{label}_{int(slip)}bp"] = {
                        "cagr": b["cagr"], "max_drawdown": b["max_drawdown"]}
            rob.append(row)
    out["robustness_sma_stop"] = rob

    # robustness: arm buffer
    armbuf = []
    for buf in (0.0, 0.005, 0.01, 0.015, 0.02, 0.03):
        ww, dd = build_weights(ts, opens, closes, arm_buf=buf)
        row = {"arm_buffer": buf, "n": dd["n_overlay"]}
        for slip in (1.0, 5.0):
            for label, start in (("10y", START10), ("5y", START5)):
                s = stats_fast(ts, opens, closes, ww, start, slip)
                row[f"{label}_{int(slip)}bp"] = {
                    "cagr": s["cagr"], "max_drawdown": s["max_drawdown"]}
        armbuf.append(row)
    out["robustness_arm_buffer"] = armbuf

    # robustness: overlay entry delay
    delays = []
    for delay in (0, 1, 2, 3):
        ww, dd = build_weights(ts, opens, closes, overlay_delay=delay)
        row = {"delay_bars": delay}
        for label, start in (("10y", START10), ("5y", START5)):
            s = stats_fast(ts, opens, closes, ww, start, 1.0)
            row[f"{label}_1bp"] = {"cagr": s["cagr"],
                                   "max_drawdown": s["max_drawdown"]}
        delays.append(row)
    out["robustness_overlay_delay"] = delays

    # gap event study and standalone negative controls
    out["gap_buckets_10y"] = gap_bucket_table(ts, opens, closes, START10)
    tq1 = bt.load_1m("TQQQ")
    vol = tq1.set_index("ts").reindex(ts).ffill()["volume"].to_numpy()
    out["standalone_gap_down_fade"] = {}
    for th in (0.005, 0.01, 0.02):
        ww, info = standalone_fade(ts, opens, closes, vol, gap_th=th)
        rec = dict(info)
        for label, start in (("10y", START10), ("5y", START5)):
            s = stats_fast(ts, opens, closes, ww, start, 1.0)
            s5 = stats_fast(ts, opens, closes, ww, start, 5.0)
            rec[f"{label}_cagr"] = s["cagr"]
            rec[f"{label}_dd"] = s["max_drawdown"]
            rec[f"{label}_sharpe"] = s["sharpe"]
            rec[f"{label}_5bp_cagr"] = s5["cagr"]
            rec[f"{label}_5bp_dd"] = s5["max_drawdown"]
        out["standalone_gap_down_fade"][f"{th*100:.1f}%"] = rec

    (OUT / "result.json").write_text(json.dumps(out, indent=2, default=float))

    print("Gap-fill-fade overlay vs winner")
    for slip in (1, 5, 10):
        a = out["windows"]["10y"][f"{slip}bp"]
        b = out["windows"]["5y"][f"{slip}bp"]
        wa = out["winner_reference"]["10y"][f"{slip}bp"]
        wb = out["winner_reference"]["5y"][f"{slip}bp"]
        print(f"{slip:2d}bp  10y {a['cagr']*100:6.2f}/{a['max_drawdown']*100:5.2f} "
              f"(winner {wa['cagr']*100:6.2f}/{wa['max_drawdown']*100:5.2f})   "
              f"5y {b['cagr']*100:6.2f}/{b['max_drawdown']*100:5.2f} "
              f"(winner {wb['cagr']*100:6.2f}/{wb['max_drawdown']*100:5.2f})")
    print(f"overlay days {diag['n_overlay']}, stop events {diag['n_stops']}, "
          f"stopped overlay days {out['diagnostics']['overlay_days_stopped']}")
    print("wrote", OUT / "result.json")


if __name__ == "__main__":
    main()
