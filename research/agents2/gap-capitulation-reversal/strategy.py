"""Gap-down and capitulation reversal in a QQQ 165-day bull regime.

What this file does
-------------------
1. Reproduces the round-1 winner (QQQ > 165-day SMA -> TQQQ, armed 4% minute
   stop, else BIL) exactly, and reports 1/5/10 bp on the 10y and 5y windows.
2. Runs the mandated event study: buy TQQQ at the next session's open after
   (a) a QQQ gap down, (b) a QQQ intraday drawdown, (c) a TQQQ gap down,
   holding 1/3/5 sessions.  Reports mean/median/win/t and the regime split.
3. Runs the standalone event strategy (QQQ gap <= -1.5%, 1-day hold, 4% stop,
   exit on regime off) and the winner-overlay candidates:
      - gap-down arms the 4% stop (gap-arm),
      - do not stop into capitulation (suppress),
      - arm the stop after a prior -2% QQQ day (prior-down arm).
4. Writes result.json with all metrics, yearly returns and rolling 3y windows.

No look-ahead: every signal uses bars <= i and every order fills at bar i+1's
open.  The gap event is observable at the 09:30 open of the event day and the
entry is the *next* session's open, so it is strictly causal.  The intraday
drawdown event is observable by the event day's close; entry is the next open.
Stops use the current bar's close and fill at the next bar's open.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/agents2/gap-capitulation-reversal/strategy.py
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


# ----------------------------------------------------------------------------
# data
# ----------------------------------------------------------------------------
class Panel:
    def __init__(self):
        ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), START10, END, "1min")
        self.ts, self.opens, self.closes = ts, opens, closes
        dates = np.array([t.date() for t in ts])
        self.dates = dates
        self.first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
        self.last = np.r_[self.first[1:] - 1, len(ts) - 1]
        self.n = len(ts)
        self.nd = len(self.first)

        # QQQ daily low from the raw 1-minute file (the panel has no low column)
        q = bt.load_1m("QQQ")
        q["date"] = q["date"].astype("datetime64[ns]")
        low = q.groupby("date")["low"].min()
        low.index = pd.to_datetime(low.index)
        idx = pd.to_datetime(pd.Series(dates[self.first]))
        qlow = low.reindex(idx).to_numpy()
        proxy = np.minimum.reduceat(closes[:, 0], self.first)
        self.q_low = np.where(np.isfinite(qlow), qlow, proxy)

        self.q_open = opens[self.first, 0]
        self.t_open = opens[self.first, 1]
        self.q_close = closes[self.last, 0]
        self.t_close = closes[self.last, 1]
        self.prior_q = np.r_[np.nan, self.q_close[:-1]]
        self.prior_t = np.r_[np.nan, self.t_close[:-1]]
        self.qgap = self.q_open / self.prior_q - 1.0
        self.tgap = self.t_open / self.prior_t - 1.0
        self.qdd = self.q_low / self.prior_q - 1.0
        self.qret = self.q_close / self.prior_q - 1.0

        self.sma = pd.Series(self.q_close).rolling(SMA_N).mean().to_numpy()
        self.ma20 = pd.Series(self.q_close).rolling(MA_FAST).mean().to_numpy()
        self.reg_start = np.zeros(self.nd, bool)
        self.reg_start[1:] = self.q_close[:-1] > self.sma[:-1]
        self.reg_next = self.q_close > self.sma

    def session_bounds(self, k):
        return int(self.first[k]), int(self.last[k])


# ----------------------------------------------------------------------------
# weight builders
# ----------------------------------------------------------------------------
def winner_hold(p: Panel, stop=STOP, arm_buf=ARM_BUF, gap_arm=None,
                suppress=None, prior_down_arm=None):
    """Round-1 winner with optional event overlays.

    gap_arm:        also arm the 4% stop on a session that gaps down at least
                    this much (even if QQQ is above its 20-day MA).
    suppress:       once QQQ is this far below the prior close, disable the stop
                    for the rest of the session (do not stop into capitulation).
    prior_down_arm: also arm the stop after a prior session whose QQQ return was
                    at most -this amount.
    """
    hold = np.zeros(p.n, bool)
    for k in range(1, p.nd):
        f, l = p.session_bounds(k)
        if not p.reg_start[k]:
            continue
        armed = bool(p.ma20[k - 1] == p.ma20[k - 1]
                     and p.closes[f, 0] < p.ma20[k - 1] * (1 + arm_buf))
        if gap_arm is not None and p.qgap[k] <= -gap_arm:
            armed = True
        if prior_down_arm is not None and p.qret[k - 1] <= -prior_down_arm:
            armed = True
        base = p.opens[f, 1]
        state = True
        for i in range(f, l + 1):
            if armed and suppress is not None:
                if p.closes[i, 0] / p.prior_q[k] - 1.0 <= -suppress:
                    armed = False
            if state and armed and p.closes[i, 1] < base * (1 - stop):
                state = False
            hold[i] = state
    return hold


def event_hold(p: Panel, kind, thresh, hold_days, stop=STOP):
    """Standalone event strategy.

    Event on session k-1, in a bull regime at the start of k-1.  Entry at the
    open of session k, but only if the regime is still on at the close of k-1
    (the exit-on-regime-off rule).  Hold `hold_days` sessions; exit at the open
    after the last held session.  A stop ends the trade.
    """
    if kind == "qgap":
        ev = p.qgap <= -thresh
    elif kind == "tgap":
        ev = p.tgap <= -thresh
    elif kind == "qdd":
        ev = p.qdd <= -thresh
    elif kind == "qret":
        ev = p.qret <= -thresh
    elif kind == "dd20":
        high20 = pd.Series(p.q_close).rolling(20).max().to_numpy()
        ev = p.q_close / high20 - 1.0 <= -thresh
    else:
        raise ValueError(kind)

    hold = np.zeros(p.n, bool)
    active_until = -1
    for k in range(1, p.nd):
        # decision at the close of k-1: event occurred and the entry-day regime is on
        if ev[k - 1] and p.reg_start[k - 1] and p.reg_next[k - 1]:
            active_until = max(active_until, (k - 1) + hold_days)
        if k > active_until:
            continue
        if not p.reg_start[k]:          # exit on regime off (fill at this open)
            active_until = -1
            continue
        f, l = p.session_bounds(k)
        base = p.opens[f, 1]
        state = True
        for i in range(f, l + 1):
            if state:
                if p.closes[i, 1] < base * (1 - stop):
                    state = False
                    active_until = -1
            hold[i] = state
    return hold


def to_weights(hold):
    w = np.zeros((len(hold), 3))
    w[:, 1] = hold.astype(float)
    w[:, 2] = 1.0 - w[:, 1]
    return w


# ----------------------------------------------------------------------------
# metrics
# ----------------------------------------------------------------------------
def window_metrics(result, ts, bench_close, start):
    s = bt.stats(result, BARS_PER_YEAR)
    i = bt.start_index(ts, start)
    bench = bt.benchmark(bench_close[i:], ts[i:], BARS_PER_YEAR)
    eq = pd.Series(result["equity"], index=ts[i:])
    daily = eq.groupby(eq.index.date).last().to_numpy()
    peak = np.maximum.accumulate(daily)
    s["max_drawdown_daily_marks"] = float(-(daily / peak - 1.0).min())
    peak_m = np.maximum.accumulate(result["equity"])
    dd = result["equity"] / peak_m - 1.0
    j = int(np.argmin(dd))
    p = int(np.argmax(result["equity"][: j + 1]))
    s["dd_peak_ts"] = str(ts[i:][p])
    s["dd_trough_ts"] = str(ts[i:][j])
    s["bench"] = bench
    s["yearly"] = bt.yearly(ts[i:], result["equity"], bench_close[i:])
    s["equity"] = result["equity"]
    s["ts"] = ts[i:]
    return s


def rolling_3y(ts, eq, bench, winner_eq=None):
    """Quarterly-start, full 3-year windows.  CAGR and max DD for strategy,
    TQQQ and (optionally) the round-1 winner."""
    rows = []
    start = pd.Timestamp(START10, tz="America/New_York")
    end = ts[-1]
    while start + pd.Timedelta(days=3 * 365) <= end:
        i = int(ts.searchsorted(start))
        j = int(ts.searchsorted(start + pd.Timedelta(days=3 * 365)))
        if j <= i + 100:
            start += pd.DateOffset(months=3)
            continue
        t = ts[i:j]
        e = eq[i:j]
        b = bench[i:j]
        yrs = (t[-1] - t[0]).total_seconds() / (365.25 * 86400)

        def cagr(x):
            return (x[-1] / x[0]) ** (1 / yrs) - 1

        def mdd(x):
            return float(-(x / np.maximum.accumulate(x) - 1).min())

        row = {"start": str(t[0].date()), "strategy_cagr": cagr(e),
               "strategy_dd": mdd(e), "tqqq_cagr": cagr(b), "tqqq_dd": mdd(b)}
        if winner_eq is not None:
            w = winner_eq[i:j]
            row["winner_cagr"] = cagr(w)
            row["winner_dd"] = mdd(w)
        rows.append(row)
        start += pd.DateOffset(months=3)
    out = {
        "n": len(rows),
        "windows": rows,
        "beat_tqqq_cagr": sum(r["strategy_cagr"] > r["tqqq_cagr"] for r in rows),
        "lower_dd_than_tqqq": sum(r["strategy_dd"] < r["tqqq_dd"] for r in rows),
    }
    if winner_eq is not None:
        out["beat_winner_cagr"] = sum(r["strategy_cagr"] > r["winner_cagr"] for r in rows)
        out["lower_dd_than_winner"] = sum(r["strategy_dd"] < r["winner_dd"] for r in rows)
        out["beat_both"] = sum(
            r["strategy_cagr"] > r["winner_cagr"] and r["strategy_dd"] < r["winner_dd"]
            for r in rows)
    out["min_cagr"] = min(r["strategy_cagr"] for r in rows)
    out["max_dd"] = max(r["strategy_dd"] for r in rows)
    return out


def run(p: Panel, hold, start, slip):
    return bt.run(p.ts, p.opens, p.closes, to_weights(hold), start,
                  band=0.02, slippage_bps=slip)


def summarize(p: Panel, hold, start, slip):
    r = run(p, hold, start, slip)
    return window_metrics(r, p.ts, p.closes[:, 1], start)


# ----------------------------------------------------------------------------
# event study
# ----------------------------------------------------------------------------
def event_study(p: Panel):
    """Forward TQQQ returns after each event, regime-on sessions, 2017+."""
    start = np.datetime64(START10)
    in_win = p.dates[p.first] >= start
    n1 = np.full(p.nd, np.nan)
    n3 = np.full(p.nd, np.nan)
    n5 = np.full(p.nd, np.nan)
    for k in range(p.nd - 1):
        n1[k] = p.t_close[k + 1] / p.t_open[k + 1] - 1
    for k in range(p.nd - 3):
        n3[k] = p.t_close[k + 3] / p.t_open[k + 1] - 1
    for k in range(p.nd - 5):
        n5[k] = p.t_close[k + 5] / p.t_open[k + 1] - 1

    high20 = pd.Series(p.q_close).rolling(20).max().to_numpy()
    dd20 = p.q_close / high20 - 1.0
    q3 = pd.Series(p.q_close).pct_change(3).to_numpy()

    def stats(x, mask):
        v = x[mask & np.isfinite(x)]
        if len(v) < 3:
            return None
        return {
            "n": int(len(v)),
            "mean": float(v.mean()),
            "median": float(np.median(v)),
            "win": float((v > 0).mean()),
            "t": float(v.mean() / v.std(ddof=1) * np.sqrt(len(v))),
        }

    defs = []
    for g in (0.015, 0.02, 0.03):
        defs.append((f"QQQ gap <= -{g:.1%}", p.qgap <= -g))
    for g in (0.05, 0.06, 0.08):
        defs.append((f"TQQQ gap <= -{g:.1%}", p.tgap <= -g))
    for g in (0.02, 0.03, 0.04):
        defs.append((f"QQQ intraday low <= -{g:.1%}", p.qdd <= -g))
    for g in (0.02, 0.025):
        defs.append((f"QQQ close <= -{g:.1%}", p.qret <= -g))
    for g in (0.08, 0.10):
        defs.append((f"QQQ 20-day DD <= -{g:.1%}", dd20 <= -g))
    defs.append(("QQQ 3-day <= -4%", q3 <= -0.04))

    out = {}
    for label, ev in defs:
        m = ev & p.reg_start & in_win
        row = {"n": int(m.sum()), "next1": stats(n1, m), "next3": stats(n3, m),
               "next5": stats(n5, m)}
        if row["next1"] is not None:
            out[label] = row

    # regime split for the two most important signals
    split = {}
    for label, ev in (("QQQ close <= -2%", p.qret <= -0.02),
                      ("QQQ intraday low <= -3%", p.qdd <= -0.03),
                      ("QQQ 20-day DD <= -10%", dd20 <= -0.10)):
        for rn, rl in ((0, "regime_off_next"), (1, "regime_on_next")):
            m = ev & p.reg_start & in_win & (p.reg_next.astype(int) == rn)
            split[f"{label} | {rl}"] = stats(n1, m)
    out["_regime_split"] = split
    return out


def stop_event_study(p: Panel):
    """P&L of the winner's stop vs holding, split by QQQ drawdown at the stop."""
    rows = []
    for k in range(1, p.nd):
        f, l = p.session_bounds(k)
        if not p.reg_start[k]:
            continue
        armed = bool(p.ma20[k - 1] == p.ma20[k - 1]
                     and p.closes[f, 0] < p.ma20[k - 1] * 1.01)
        if not armed:
            continue
        base = p.opens[f, 1]
        for i in range(f, l + 1):
            if p.closes[i, 1] < base * 0.96:
                if i + 1 <= l:
                    fill = p.opens[i + 1, 1]
                else:
                    fill = p.t_close[k]
                if k + 1 < p.nd:
                    # stop: flat from fill to next open, then long to next close
                    stop_ret = (p.t_open[k + 1] / p.t_close[k]) * (p.t_close[k + 1] / p.t_open[k + 1]) - 1
                    hold_ret = p.t_close[k + 1] / fill - 1
                    diff = stop_ret - hold_ret
                else:
                    stop_ret = hold_ret = diff = np.nan
                rows.append({
                    "date": str(p.dates[f]),
                    "qdd_at_stop": float(p.closes[i, 0] / p.prior_q[k] - 1),
                    "to_close": float(p.t_close[k] / fill - 1),
                    "to_next_open": float(p.t_open[k + 1] / p.t_close[k] - 1) if k + 1 < p.nd else np.nan,
                    "next_oc": float(p.t_close[k + 1] / p.t_open[k + 1] - 1) if k + 1 < p.nd else np.nan,
                    "stop_vs_hold": float(diff),
                })
                break
    out = {"n": len(rows), "events": rows}
    for label, mask in (
        ("all", np.ones(len(rows), bool)),
        ("qdd_at_stop <= -3%", np.array([r["qdd_at_stop"] <= -0.03 for r in rows])),
        ("qdd_at_stop > -3%", np.array([r["qdd_at_stop"] > -0.03 for r in rows])),
        ("day low <= -3%", None),
    ):
        if mask is None:
            continue
        sub = [r for r, m in zip(rows, mask) if m]
        if not sub:
            continue
        v = np.array([r["stop_vs_hold"] for r in sub])
        out[label] = {
            "n": len(sub),
            "mean": float(v.mean()),
            "t": float(v.mean() / v.std(ddof=1) * np.sqrt(len(v))) if len(v) > 1 else None,
            "to_close": float(np.mean([r["to_close"] for r in sub])),
            "to_next_open": float(np.nanmean([r["to_next_open"] for r in sub])),
            "next_oc": float(np.nanmean([r["next_oc"] for r in sub])),
        }
    return out


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------
def main():
    p = Panel()
    print(f"panel: {p.n:,} bars, {p.nd:,} sessions, {p.dates[0]}..{p.dates[-1]}")

    # headline holds
    winner = winner_hold(p)
    gaparm = winner_hold(p, gap_arm=0.015)
    suppress = winner_hold(p, suppress=0.03)
    prior_down = winner_hold(p, prior_down_arm=0.02)
    standalone = event_hold(p, "qgap", 0.015, 1, stop=0.04)

    variants = {
        "winner": winner,
        "winner_gaparm_1.5": gaparm,
        "winner_suppress_capitulation_3": suppress,
        "winner_prior_down_arm_2": prior_down,
        "standalone_event_qgap_1.5_1d_stop4": standalone,
    }

    out = {
        "agent": "gap-capitulation-reversal",
        "as_of": "2026-10-23",
        "data": "local adjusted 1-minute QQQ/TQQQ/BIL, regular session",
        "windows": {"10y": [START10, END], "5y": [START5, END]},
        "rules": {
            "winner": "QQQ prior close > 165d SMA -> TQQQ; 4% stop below session open, "
                      "armed when QQQ first minute < 20d SMA * 1.01; stop fills next minute "
                      "and stays out to the next session open; else BIL.",
            "gaparm": "winner + arm the stop on any session with QQQ gap <= -1.5%.",
            "suppress": "winner but once QQQ <= -3% from prior close, disable the stop for the day.",
            "prior_down_arm": "winner + arm the stop after a prior QQQ session <= -2%.",
            "standalone_event": "QQQ gap <= -1.5% on a bull-regime session; buy TQQQ at the "
                                "next session open if the regime is still on; hold 1 session; "
                                "4% stop below the session open; exit on regime off.",
        },
        "headline": {},
        "cost_sensitivity": {},
        "event_study": {},
        "stop_event_study": {},
        "rolling3y": {},
        "pass_fail": {},
    }

    # headline at 1 bp + yearly/rolling
    winner_metrics = {}
    for label, start in (("10y", START10), ("5y", START5)):
        s = summarize(p, winner, start, 1.0)
        out["headline"][f"winner_{label}"] = {
            "cagr": s["cagr"], "max_drawdown": s["max_drawdown"],
            "max_drawdown_daily_marks": s["max_drawdown_daily_marks"],
            "sharpe": s["sharpe"], "sortino": s["sortino"],
            "volatility": s["volatility"], "fills": s["fills"],
            "turnover": s["turnover"], "ending_equity": s["ending_equity"],
            "dd_peak": s["dd_peak_ts"], "dd_trough": s["dd_trough_ts"],
            "benchmark": s["bench"],
            "yearly": {str(k): v for k, v in s["yearly"].items()},
        }
        winner_metrics[label] = s

    # all variants at 1/5/10 bp
    for name, hold in variants.items():
        out["cost_sensitivity"][name] = {}
        for slip in (1.0, 5.0, 10.0):
            out["cost_sensitivity"][name][f"{slip:.0f}bp"] = {}
            for label, start in (("10y", START10), ("5y", START5)):
                s = summarize(p, hold, start, slip)
                out["cost_sensitivity"][name][f"{slip:.0f}bp"][label] = {
                    "cagr": s["cagr"], "max_drawdown": s["max_drawdown"],
                    "max_drawdown_daily_marks": s["max_drawdown_daily_marks"],
                    "sharpe": s["sharpe"], "fills": s["fills"],
                    "turnover": s["turnover"], "ending_equity": s["ending_equity"],
                }
        print(f"done {name}")

    # yearly for the standalone (1 bp)
    for label, start in (("10y", START10), ("5y", START5)):
        s = summarize(p, standalone, start, 1.0)
        out["cost_sensitivity"]["standalone_event_qgap_1.5_1d_stop4"][
            f"{label}_yearly_1bp"] = {str(k): v for k, v in s["yearly"].items()}

    # rolling 3y: standalone and winner, vs TQQQ and the winner
    for label, start in (("10y", START10), ("5y", START5)):
        i = bt.start_index(p.ts, start)
        r = run(p, standalone, start, 1.0)
        eq = r["equity"]
        w = winner_metrics[label]["equity"]
        out["rolling3y"][f"standalone_{label}"] = rolling_3y(
            p.ts[i:], eq, p.closes[i:, 1], winner_eq=w)
        out["rolling3y"][f"winner_{label}"] = rolling_3y(
            p.ts[i:], w, p.closes[i:, 1])

    # event study and stop-event study
    out["event_study"] = event_study(p)
    out["stop_event_study"] = stop_event_study(p)

    # pass/fail
    tqqq = {"10y": {"cagr": 0.3928, "max_drawdown": 0.8168},
            "5y": {"cagr": 0.1347, "max_drawdown": 0.8168}}
    winner_ref = {"10y": {"cagr": 0.5880, "max_drawdown": 0.4456},
                  "5y": {"cagr": 0.4988, "max_drawdown": 0.3349}}
    for name in variants:
        cs = out["cost_sensitivity"][name]["1bp"]
        out["pass_fail"][name] = {
            label: {
                "beats_tqqq": bool(cs[label]["cagr"] > tqqq[label]["cagr"]
                                   and cs[label]["max_drawdown"] < tqqq[label]["max_drawdown"]),
                "beats_winner": bool(cs[label]["cagr"] > winner_ref[label]["cagr"]
                                     and cs[label]["max_drawdown"] < winner_ref[label]["max_drawdown"]),
                "cagr_vs_winner_pp": float((cs[label]["cagr"] - winner_ref[label]["cagr"]) * 100),
                "dd_vs_winner_pp": float((winner_ref[label]["max_drawdown"] - cs[label]["max_drawdown"]) * 100),
            }
            for label in ("10y", "5y")
        }

    (OUT / "result.json").write_text(json.dumps(out, indent=2, default=float))
    print("wrote", OUT / "result.json")

    for name in variants:
        row = out["cost_sensitivity"][name]
        print(f"\n{name}")
        for slip in ("1bp", "5bp", "10bp"):
            c = row[slip]
            print(f"  {slip:4s} 10y {c['10y']['cagr']*100:6.2f}/{c['10y']['max_drawdown']*100:5.2f}"
                  f"  5y {c['5y']['cagr']*100:6.2f}/{c['5y']['max_drawdown']*100:5.2f}")


if __name__ == "__main__":
    main()
