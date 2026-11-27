"""Dual-speed regime: 165-day QQQ slow gate + armed 60-minute EMA(40) fast filter.

Headline variant (C4-40)
------------------------
Slow gate (daily)
    Hold TQQQ only if QQQ's prior session close is above its 165-day SMA;
    otherwise hold BIL for the whole session (including overnight).

Fast filter (60-minute QQQ bars, span 40 bars ~= 6.2 sessions)
    At each completed 60-minute bar, if the session is *armed*:
      * a down-cross of the bar close through the EMA exits TQQQ to BIL at the
        next minute's open;
      * an up-cross re-enters TQQQ at the next minute's open.
    The session resets to long at the open when the slow gate is on, so the
    filter only acts on a fresh cross during the session (a session that opens
    already below the EMA is not sold immediately).

Arming
    A session is armed only when QQQ's 09:30 first-minute close is below the
    prior session's 20-day SMA times 1.01 -- the same arm rule as the round-1
    winner. In strong short-term uptrends the fast filter and the stop are off.

Stop
    If armed and long and TQQQ's minute close is 4% below the session open,
    exit at the next minute's open. Re-entry requires a 60-minute up-cross
    (same day) or the next session's open (if the slow gate is still on).

No look-ahead: daily signals use the prior close, 60-minute signals use a bar
that has completed, and every weight set at bar i fills at bar i+1's open.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/agents2/dual-speed-regime/strategy.py
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
SLOW_N = 165
EMA_SPAN = 40
STOP = 0.04
ARM_BUF = 0.01
BPY = 252 * 390
OUT = Path(__file__).resolve().parent


# --------------------------------------------------------------------------- #
# panel helpers
# --------------------------------------------------------------------------- #
def day_index(ts):
    dates = np.array([t.date() for t in ts])
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(dates) - 1]
    day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, len(dates)]))
    return dates, first, last, day_id


def daily_gate(qqq_daily, n_slow=SLOW_N, n_fast=None, buf_entry=0.0):
    """Per-session TQQQ state from prior daily closes (state machine)."""
    sma = pd.Series(qqq_daily).rolling(n_slow).mean().to_numpy()
    fast = (pd.Series(qqq_daily).rolling(n_fast).mean().to_numpy()
            if n_fast else np.full(len(qqq_daily), np.nan))
    state = np.zeros(len(qqq_daily), bool)
    on = False
    for k in range(1, len(qqq_daily)):
        c, s, f = qqq_daily[k - 1], sma[k - 1], fast[k - 1]
        if not np.isfinite(s):
            continue
        if on:
            if c < s or (np.isfinite(f) and c < f):
                on = False
        else:
            if c > s * (1.0 + buf_entry) and (
                not np.isfinite(f) or c > f * (1.0 + buf_entry)
            ):
                on = True
        state[k] = on
    return state


def sixty_min_state(price, first, last, span):
    """Per-minute '60m close > EMA(span)' state, session-aligned bars.

    Bars end at 10:29, 11:29, ..., 15:29 and 15:59. A bar's state is applied
    from the following minute (one minute of conservatism relative to the
    close), and the 15:30-15:59 bar only seeds the next session's first-hour
    transition, so the overnight position is the state after the 14:30-15:29
    bar. This is the implementation that produced the reported numbers.
    """
    alpha = 2.0 / (span + 1.0)
    closes, day_of = [], []
    for k, (f, l) in enumerate(zip(first, last)):
        for e in (f + 59, f + 119, f + 179, f + 239, f + 299, f + 359, l):
            if e <= l:
                closes.append(price[e])
                day_of.append(k)
    closes = np.asarray(closes)
    day_of = np.asarray(day_of)
    ema = np.empty(len(closes))
    e = np.nan
    for j, c in enumerate(closes):
        e = c if not np.isfinite(e) else alpha * c + (1.0 - alpha) * e
        ema[j] = e
    bar_up = closes > ema

    state60 = np.zeros(len(price), bool)
    prev = False
    j = 0
    counts = np.bincount(day_of, minlength=len(first))
    for k, (f, l) in enumerate(zip(first, last)):
        nb = counts[k]
        state60[f:min(f + 60, l + 1)] = prev
        for m in range(min(6, nb - 1)):
            s = f + 60 * (m + 1)
            state60[s:min(s + 60, l + 1)] = bar_up[j + m]
        prev = bar_up[j + nb - 1] if nb else prev
        j += nb
    return state60


# --------------------------------------------------------------------------- #
# weights
# --------------------------------------------------------------------------- #
def build_weights(ts, opens, closes, first, last, day_id, ma20,
                  span=EMA_SPAN, stop=STOP, arm_buf=ARM_BUF):
    """Dual-speed weights (n,3) and diagnostics."""
    dc = closes[last, 0]
    reg = daily_gate(dc, SLOW_N)
    fast = sixty_min_state(closes[:, 0], first, last, span)
    qqq_c, tq_c = closes[:, 0], closes[:, 1]
    n = len(ts)
    hold = np.zeros(n, bool)
    ev = dict(early=0, reclaim=0, stops=0, days_armed=0, days_exited=0)
    for k, (f, l) in enumerate(zip(first, last)):
        if not reg[k]:
            continue
        ref = ma20[k - 1] if k > 0 else np.nan
        armed = bool(np.isfinite(ref) and qqq_c[f] < ref * (1.0 + arm_buf))
        if armed:
            ev["days_armed"] += 1
        base = opens[f, 1]
        state = True
        exited = False
        for i in range(f, l + 1):
            if armed and i > f:
                prev_up, cur_up = fast[i - 1], fast[i]
                if cur_up != prev_up:
                    if state and not cur_up:
                        state = False
                        ev["early"] += 1
                        exited = True
                    elif (not state) and cur_up:
                        state = True
                        ev["reclaim"] += 1
            if armed and state and tq_c[i] < base * (1.0 - stop):
                state = False
                ev["stops"] += 1
                exited = True
            hold[i] = state
        if exited:
            ev["days_exited"] += 1
    w = np.zeros((n, 3))
    w[:, 1] = hold.astype(float)
    w[:, 2] = 1.0 - w[:, 1]
    return w, ev, reg


def winner_weights(ts, opens, closes, first, last, ma20):
    """Round-1 winner: 165 gate + 4% stop armed by prior MA20*1.01."""
    dc = closes[last, 0]
    reg = daily_gate(dc, SLOW_N)
    qqq_c, tq_c = closes[:, 0], closes[:, 1]
    hold = np.zeros(len(ts), bool)
    for k, (f, l) in enumerate(zip(first, last)):
        if not reg[k]:
            continue
        ref = ma20[k - 1] if k > 0 else np.nan
        armed = bool(np.isfinite(ref) and qqq_c[f] < ref * (1.0 + ARM_BUF))
        base = opens[f, 1]
        state = True
        for i in range(f, l + 1):
            if armed and state and tq_c[i] < base * (1.0 - STOP):
                state = False
            hold[i] = state
    w = np.zeros((len(ts), 3))
    w[:, 1] = hold.astype(float)
    w[:, 2] = 1.0 - hold
    return w


def daily_fast_weights(ts, closes, first, last, day_id, n_fast):
    """Negative control: 165-day gate AND QQQ > n_fast-day MA (whole session)."""
    dc = closes[last, 0]
    reg = daily_gate(dc, SLOW_N, n_fast=n_fast)
    hold = reg[day_id]
    w = np.zeros((len(ts), 3))
    w[:, 1] = hold.astype(float)
    w[:, 2] = 1.0 - hold
    return w


# --------------------------------------------------------------------------- #
# reporting
# --------------------------------------------------------------------------- #
def dd_episodes(ts, eq, top=4):
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    out = []
    i, n = 0, len(eq)
    while i < n:
        if dd[i] >= -1e-9:
            i += 1
            continue
        j = i
        while j < n and dd[j] < -1e-9:
            j += 1
        p = int(np.argmax(eq[: i + 1]))
        seg = dd[p:j]
        t = p + int(np.argmin(seg))
        out.append([float(-seg.min()), str(ts[p])[:16], str(ts[t])[:16],
                    str(ts[min(j, n - 1)])[:16]])
        i = j + 1
    out.sort(reverse=True)
    return out[:top]


def window_metrics(r, ts, closes, start):
    s = bt.stats(r, BPY)
    i = bt.start_index(ts, start)
    s["benchmark"] = bt.benchmark(closes[i:, 1], ts[i:], BPY)
    s["yearly"] = bt.yearly(ts[i:], r["equity"], closes[i:, 1])
    s["dd_episodes"] = dd_episodes(ts[i:], r["equity"], 4)
    return s


def rolling3(eq, bench, ts):
    """Quarterly-start rolling 3-year windows from a 1-minute equity curve."""
    idx = pd.Series(eq, index=ts)
    b = pd.Series(bench, index=ts)
    rows = []
    for s in pd.date_range(ts[0].normalize(), ts[-1].normalize(), freq="QS"):
        e = s + pd.DateOffset(years=3)
        if e > ts[-1]:
            break
        a = idx.loc[s:e]
        c = b.loc[s:e]
        if len(a) < 100:
            continue
        yrs = (a.index[-1] - a.index[0]).total_seconds() / (365.25 * 86400)
        rows.append(dict(
            start=str(s.date()), end=str(a.index[-1].date()),
            cagr=float((a.iloc[-1] / a.iloc[0]) ** (1 / yrs) - 1),
            dd=float(-(a / a.cummax() - 1).min()),
            bench_cagr=float((c.iloc[-1] / c.iloc[0]) ** (1 / yrs) - 1),
            bench_dd=float(-(c / c.cummax() - 1).min()),
        ))
    return rows


def slim(s, cost):
    return {
        "cost_bps": cost,
        "cagr": float(s["cagr"]), "max_drawdown": float(s["max_drawdown"]),
        "sharpe": float(s["sharpe"]), "fills": int(s["fills"]),
        "turnover": float(s["turnover"]), "exposure": float(s["exposure"]),
        "benchmark_cagr": float(s["benchmark"]["cagr"]),
        "benchmark_max_drawdown": float(s["benchmark"]["max_drawdown"]),
    }


def main():
    ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), START10, END, "1min")
    dates, first, last, day_id = day_index(ts)
    dc = closes[last, 0]
    ma20 = pd.Series(dc).rolling(20).mean().to_numpy()

    w, ev, reg = build_weights(ts, opens, closes, first, last, day_id, ma20)
    w_win = winner_weights(ts, opens, closes, first, last, ma20)

    out = {
        "agent": "dual-speed-regime",
        "strategy": {
            "slow_gate": f"QQQ prior close > {SLOW_N}-day SMA; else BIL",
            "fast_filter": f"QQQ 60-minute close vs EMA({EMA_SPAN}) of 60-minute closes",
            "fast_action": "down-cross -> BIL, up-cross -> TQQQ, next-minute fill",
            "arming": f"QQQ first-minute close < prior 20-day SMA * (1+{ARM_BUF})",
            "stop": f"{STOP*100:.0f}% below session open when armed; next-minute fill",
            "reentry": "60-minute up-cross, or next session open if the slow gate is on",
            "session_reset": "long at the open when the slow gate is on",
            "fills": "next bar open", "cost": "1 bp one-way (5/10 bp reported)",
        },
        "parameters": {"slow_sma_days": SLOW_N, "ema_span_60m_bars": EMA_SPAN,
                       "stop": STOP, "arm_buffer": ARM_BUF},
        "diagnostics_full_panel": ev,
        "windows": {},
        "winner": {},
        "rolling_3y": {},
        "neighbours_1bp": {},
        "negative_controls_1bp": {},
    }

    curves = {}
    for cost in (1.0, 5.0, 10.0):
        key = f"{cost:.0f}bp"
        out["windows"][key] = {}
        out["winner"][key] = {}
        for label, start in (("10y", START10), ("5y", START5)):
            r = bt.run(ts, opens, closes, w, start, band=0.02, slippage_bps=cost)
            s = window_metrics(r, ts, closes, start)
            out["windows"][key][label] = slim(s, cost)
            if cost == 1.0:
                out["windows"][key][label]["yearly"] = {
                    str(k): {"strategy": float(v["strategy"]),
                             "tqqq": float(v["benchmark"])}
                    for k, v in s["yearly"].items()
                }
                out["windows"][key][label]["dd_episodes"] = s["dd_episodes"]
                curves[label] = (r["equity"], r["ts"])
            rw = bt.run(ts, opens, closes, w_win, start, band=0.02, slippage_bps=cost)
            sw = bt.stats(rw, BPY)
            out["winner"][key][label] = {
                "cagr": float(sw["cagr"]), "max_drawdown": float(sw["max_drawdown"]),
                "sharpe": float(sw["sharpe"]), "fills": int(sw["fills"]),
            }
            if cost == 1.0:
                curves[f"win_{label}"] = (rw["equity"], rw["ts"])

    # rolling 3y at 1 bp
    for label, start in (("10y", START10), ("5y", START5)):
        eq, ets = curves[label]
        i = bt.start_index(ts, start)
        rows = rolling3(eq, closes[i:, 1], ets)
        wq, wts = curves[f"win_{label}"]
        rows_w = rolling3(wq, closes[i:, 1], wts)
        out["rolling_3y"][label] = {
            "n": len(rows),
            "beat_tqqq_both": int(sum(1 for x in rows
                                      if x["cagr"] > x["bench_cagr"] and x["dd"] < x["bench_dd"])),
            "worst_dd": float(max(x["dd"] for x in rows)),
            "min_cagr": float(min(x["cagr"] for x in rows)),
            "winner_beat_tqqq_both": int(sum(1 for x in rows_w
                                             if x["cagr"] > x["bench_cagr"] and x["dd"] < x["bench_dd"])),
            "winner_worst_dd": float(max(x["dd"] for x in rows_w)),
            "winner_min_cagr": float(min(x["cagr"] for x in rows_w)),
            "windows": rows,
        }

    # neighbouring parameters (1 bp)
    neigh = {}
    for span in (35, 45):
        ww, _, _ = build_weights(ts, opens, closes, first, last, day_id, ma20, span=span)
        neigh[f"span_{span}"] = {}
        for label, start in (("10y", START10), ("5y", START5)):
            s = bt.stats(bt.run(ts, opens, closes, ww, start, band=0.02,
                                slippage_bps=1.0), BPY)
            neigh[f"span_{span}"][label] = {"cagr": float(s["cagr"]),
                                            "max_drawdown": float(s["max_drawdown"])}
    for stop in (0.035, 0.045):
        ww, _, _ = build_weights(ts, opens, closes, first, last, day_id, ma20, stop=stop)
        neigh[f"stop_{stop*100:.1f}"] = {}
        for label, start in (("10y", START10), ("5y", START5)):
            s = bt.stats(bt.run(ts, opens, closes, ww, start, band=0.02,
                                slippage_bps=1.0), BPY)
            neigh[f"stop_{stop*100:.1f}"][label] = {"cagr": float(s["cagr"]),
                                                     "max_drawdown": float(s["max_drawdown"])}
    out["neighbours_1bp"] = neigh

    # negative controls (1 bp)
    for n_fast in (20, 50):
        ww = daily_fast_weights(ts, closes, first, last, day_id, n_fast)
        out["negative_controls_1bp"][f"daily_ma{n_fast}_full_exit"] = {}
        for label, start in (("10y", START10), ("5y", START5)):
            s = bt.stats(bt.run(ts, opens, closes, ww, start, band=0.02,
                                slippage_bps=1.0), BPY)
            out["negative_controls_1bp"][f"daily_ma{n_fast}_full_exit"][label] = {
                "cagr": float(s["cagr"]), "max_drawdown": float(s["max_drawdown"]),
                "fills": int(s["fills"])}

    # pass/fail
    out["pass_vs_tqqq"] = {}
    out["pass_vs_winner"] = {}
    for key in ("1bp", "5bp", "10bp"):
        out["pass_vs_tqqq"][key] = {
            label: bool(out["windows"][key][label]["cagr"]
                        > out["windows"][key][label]["benchmark_cagr"]
                        and out["windows"][key][label]["max_drawdown"]
                        < out["windows"][key][label]["benchmark_max_drawdown"])
            for label in ("10y", "5y")
        }
        out["pass_vs_winner"][key] = {
            label: bool(out["windows"][key][label]["cagr"]
                        > out["winner"][key][label]["cagr"]
                        and out["windows"][key][label]["max_drawdown"]
                        < out["winner"][key][label]["max_drawdown"])
            for label in ("10y", "5y")
        }
    out["target_met"] = {
        "strict_dominance_1bp": all(out["pass_vs_winner"]["1bp"].values()),
        "strict_dominance_5bp": all(out["pass_vs_winner"]["5bp"].values()),
        "passes_at_10bp": all(out["pass_vs_winner"]["10bp"].values()),
    }

    (OUT / "result.json").write_text(json.dumps(out, indent=2))
    for key in ("1bp", "5bp", "10bp"):
        a, b = out["windows"][key]["10y"], out["windows"][key]["5y"]
        print(f"{key:>4}  10y {a['cagr']*100:6.2f}/{a['max_drawdown']*100:5.2f} "
              f"Sh {a['sharpe']:4.2f} fl {a['fills']:5d} | "
              f"5y {b['cagr']*100:6.2f}/{b['max_drawdown']*100:5.2f} "
              f"Sh {b['sharpe']:4.2f} fl {b['fills']:5d}")
    print("rolling 3y:", {k: (v["beat_tqqq_both"], v["n"], round(v["min_cagr"], 3))
                          for k, v in out["rolling_3y"].items()})
    print("wrote", OUT / "result.json")


if __name__ == "__main__":
    main()
