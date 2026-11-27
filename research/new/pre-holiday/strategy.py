"""Pre-holiday TQQQ: own TQQQ for the sessions before scheduled NYSE holidays.

Rules
-----
For every **scheduled** NYSE holiday ``H`` (hardcoded, ex-ante list) let ``k``
be the last session strictly before ``H``.  Hold TQQQ for sessions
``k-back+1 .. k`` (``back`` = 3 in the primary) and BIL otherwise.

Fills follow the shared next-open model: the target is set on the last bar of
the preceding session and filled at the 09:30 open of the first held session.
The primary exits at the 09:30 open of the first session **after** the
holiday, so the position necessarily spans the holiday closure -- with
next-open fills a daily strategy cannot leave at the close.  ``exit_1559`` is
the alternative that clears the target on the penultimate bar of the last held
session, giving up the holiday gap.

Volatility filter (mandated)
----------------------------
TQQQ 20-session realised vol of daily log returns, annualised, against its own
trailing 252-session 75th percentile (trailing only -- no full-sample
normalisation).  The gate uses information through session ``k-1`` and scales
the TQQQ weight by 0.5 when vol is high; BIL takes the rest.

This file writes ``result.json`` with the primary at 1/5/10 bp, the 8-cell
pre-registered grid, the window-length frontier, the per-window event study,
a random-window placebo (500 draws plus 27 exposure-matched phases), a
holiday-shift neighbour test, subperiod / leave-one-year-out / drop-best
cuts, and an overnight-vs-intraday decomposition.

Development window only: 2016-01-04 .. 2023-12-29.  ``bt.panel`` is called with
that ``end`` so no 2024+ row is read.

Run:
    cd C:\\Users\\27175\\Desktop\\quant-trader-research
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    $env:BT_THREADS = "1"
    python research/new/pre-holiday/strategy.py
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

START = "2016-01-04"
END = "2023-12-29"
START_DATE = date.fromisoformat(START)
END_DATE = date.fromisoformat(END)
BARS_PER_YEAR = 252 * 390
BAND = 0.02
COSTS = (1.0, 5.0, 10.0)
TQQQ_BAR = {"cagr": 0.3672, "max_drawdown": 0.8229, "sharpe": 0.82}
TARGET_DD = 0.60

# Primary parameters (pre-registered in HYPOTHESIS.md).
P_BACK = 3
P_MODE = "hold_through"
P_HALF = False
P_GATE_FLOOR = 0.5      # scale TQQQ to this when the vol gate is shut
P_GATE_Q = 0.75
P_GATE_WIN = 20
P_GATE_LOOK = 252

# ---------------------------------------------------------------------------
# Scheduled NYSE closures, 2016-2023.  Hardcoded, knowable years in advance.
# Unscheduled closures (2018-12-05 day of mourning) are deliberately excluded.
# ---------------------------------------------------------------------------
HOLIDAYS_TXT = """
2016-01-01 2016-01-18 2016-02-15 2016-03-25 2016-05-30 2016-07-04 2016-09-05 2016-11-24 2016-12-26
2017-01-02 2017-01-16 2017-02-20 2017-04-14 2017-05-29 2017-07-04 2017-09-04 2017-11-23 2017-12-25
2018-01-01 2018-01-15 2018-02-19 2018-03-30 2018-05-28 2018-07-04 2018-09-03 2018-11-22 2018-12-25
2019-01-01 2019-01-21 2019-02-18 2019-04-19 2019-05-27 2019-07-04 2019-09-02 2019-11-28 2019-12-25
2020-01-01 2020-01-20 2020-02-17 2020-04-10 2020-05-25 2020-07-03 2020-09-07 2020-11-26 2020-12-25
2021-01-01 2021-01-18 2021-02-15 2021-04-02 2021-05-31 2021-07-05 2021-09-06 2021-11-25 2021-12-24
2022-01-17 2022-02-21 2022-04-15 2022-05-30 2022-06-20 2022-07-04 2022-09-05 2022-11-24 2022-12-26
2023-01-02 2023-01-16 2023-02-20 2023-04-07 2023-05-29 2023-06-19 2023-07-04 2023-09-04 2023-11-23 2023-12-25
"""
HOLIDAYS = sorted({date.fromisoformat(tok) for tok in HOLIDAYS_TXT.split()})
UNSCHEDULED = {date(2018, 12, 5)}
HALF_DAYS = {d for d in bt.HALF_DAYS if START_DATE <= d <= END_DATE}


# ---------------------------------------------------------------------------
# Calendar helpers
# ---------------------------------------------------------------------------
def _calendar(ts):
    dates = bt.session_dates(ts)
    first, last = bt.day_bounds_from_dates(dates)
    return dates, first, last, dates[first]


def _pairs(sess, back: int, extra=()):
    """(anchor session index, holiday) for windows that start in the dev window."""
    out = []
    for h in sorted(set(HOLIDAYS) | set(extra)):
        k = int(np.searchsorted(sess, h)) - 1
        a = k - back + 1
        if k < 0 or k >= len(sess) or a < 0 or sess[a] < START_DATE:
            continue
        out.append((k, h))
    return out


def _vol_gate(c, first, last, floor: float, q: float):
    """Per-session TQQQ weight multiplier from trailing realised vol.

    ``gate[i]`` is known at the close of session ``i-1`` (one-session shift), so
    the weight applied during session ``i`` never uses that session's return.
    """
    n = len(first)
    close = c[last, 1]
    r = pd.Series(np.log(close)).diff()
    vol = r.rolling(P_GATE_WIN).std() * np.sqrt(252.0)
    thr = vol.rolling(P_GATE_LOOK, min_periods=60).quantile(q)
    shut = vol.notna() & thr.notna() & (vol > thr)
    gate = np.where(shut, float(floor), 1.0)
    gate = np.r_[1.0, gate[:-1]]          # shift: use data through i-1
    assert len(gate) == n
    return gate, vol.to_numpy(), thr.to_numpy()


def _held_sessions(sess, anchors, back: int, half: bool):
    n = len(sess)
    held = np.zeros(n, dtype=bool)
    for k in anchors:
        a = k - back + 1
        if a < 0 or k >= n:
            continue
        held[a:k + 1] = True
    if half:
        halfset = set(HALF_DAYS)
        for i, d in enumerate(sess):
            if d in halfset:
                held[i] = True
    return held


def _hold_bars(n_bars, first, last, held, mode: str):
    """Boolean per bar: we want to be positioned from this bar's open."""
    hold = np.repeat(held, np.diff(np.r_[first, n_bars]))
    if mode == "exit_1559":
        run_end = np.flatnonzero(np.r_[held[1:] != held[:-1], True])
        for i in run_end:
            if held[i]:
                hold[last[i]] = False
    elif mode != "hold_through":
        raise ValueError(mode)
    return hold


def weights_for(ts, o, c, back=P_BACK, mode=P_MODE, half=P_HALF,
                gate_floor=0.0, gate_q=P_GATE_Q, gate=True, exclude=(),
                extra_holidays=()):
    """TQQQ/BIL weights for one cell.  Returns (weights, diagnostics)."""
    dates, first, last, sess = _calendar(ts)
    n_bars = len(ts)
    pairs = _pairs(sess, back, extra_holidays)
    ex = set(int(x) for x in exclude)
    anchors = [k for k, _ in pairs if k not in ex]
    held = _held_sessions(sess, anchors, back, half)
    hold = _hold_bars(n_bars, first, last, held, mode)

    if gate:
        g, vol, thr = _vol_gate(c, first, last, gate_floor, gate_q)
        sess_of_bar = np.repeat(np.arange(len(sess)), np.diff(np.r_[first, n_bars]))
        mult = g[sess_of_bar]
        shut_share = float(np.mean([g[k] < 1.0 for k in anchors])) if anchors else 0.0
    else:
        mult = np.ones(n_bars)
        vol = thr = np.full(len(sess), np.nan)
        shut_share = 0.0

    exposure_bar = hold.astype(float) * mult
    w = np.zeros((n_bars, 3))
    if n_bars > 1:
        w[:-1, 1] = exposure_bar[1:]         # hold bar j  <=>  w[j-1]
        w[-1, 1] = exposure_bar[-1]          # never filled
    w[:, 2] = 1.0 - w[:, 1]
    diag = {
        "windows": len(anchors),
        "held_sessions": int(held.sum()),
        "session_share": float(held.mean()),
        "weight_share": float(w[:, 1].mean()),
        "gate_shut_share_of_windows": shut_share,
        "vol20_median": float(np.nanmedian(vol)) if gate else None,
        "vol20_thr_median": float(np.nanmedian(thr)) if gate else None,
    }
    return w, diag


def build_weights(ts, o, c):
    """Primary strategy weights (pre-registered G1)."""
    w, _ = weights_for(ts, o, c, back=P_BACK, mode=P_MODE, half=P_HALF,
                       gate_floor=P_GATE_FLOOR, gate_q=P_GATE_Q, gate=True)
    return w


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
def _daily(ts, values):
    return pd.Series(np.asarray(values, float), index=ts).groupby(ts.date).last()


def _lite(ts, o, c, w, slip: float = 1.0, start: str = START):
    """Fast metrics for sweeps: no yearly table, no drawdown dates."""
    r = bt.run(ts, o, c, w, start, band=BAND, slippage_bps=slip)
    s = bt.stats(r, BARS_PER_YEAR)
    i = bt.start_index(ts, start)
    return {
        "cagr": float(s["cagr"]),
        "max_drawdown": float(s["max_drawdown"]),
        "sharpe": float(s["sharpe"]),
        "exposure_tqqq": float(w[i:, 1].mean()),
    }


def _metrics(ts, o, c, w, slip: float = 1.0, start: str = START):
    r = bt.run(ts, o, c, w, start, band=BAND, slippage_bps=slip)
    s = bt.stats(r, BARS_PER_YEAR)
    i = bt.start_index(ts, start)
    eq = np.asarray(r["equity"], float)
    dts = ts[i:]
    deq = _daily(dts, eq)
    dd_daily = float(-(deq / deq.cummax() - 1.0).min())
    yr = bt.yearly(dts, eq, c[i:, 1])
    years = float(s["years"])
    dd = deq / deq.cummax() - 1.0
    j_dd = int(np.argmin(dd.to_numpy()))
    p_dd = int(np.argmax(deq.to_numpy()[: j_dd + 1]))
    out = {
        "cagr": float(s["cagr"]),
        "total_return": float(s["total_return"]),
        "max_drawdown": float(s["max_drawdown"]),
        "max_drawdown_daily": dd_daily,
        "sharpe": float(s["sharpe"]),
        "sortino": float(s["sortino"]),
        "volatility": float(s["volatility"]),
        "calmar": float(s["cagr"] / s["max_drawdown"]) if s["max_drawdown"] > 0 else None,
        "exposure_tqqq": float(w[i:, 1].mean()),
        "fills": int(s["fills"]),
        "turnover": float(s["turnover"]),
        "turnover_per_year": float(s["turnover"] / years) if years > 0 else None,
        "ending_equity": float(s["ending_equity"]),
        "years": years,
        "dd_peak": str(deq.index[p_dd]),
        "dd_trough": str(deq.index[j_dd]),
        "yearly": {str(k): {"strategy": float(v["strategy"]),
                            "tqqq": float(v["benchmark"])}
                   for k, v in yr.items()},
    }
    return out, r, dts, deq


def _corr_beta(dts, equity, price):
    a = _daily(dts, equity).pct_change()
    b = _daily(dts, price).pct_change()
    j = pd.concat([a.rename("s"), b.rename("b")], axis=1).dropna()
    corr = float(j["s"].corr(j["b"]))
    beta = float(np.cov(j["s"], j["b"])[0, 1] / np.var(j["b"], ddof=1))
    return corr, beta


def _slice(ts, o, c, w, a: date, b: date, slip: float = 1.0):
    dates, first, last, sess = _calendar(ts)
    idx = np.flatnonzero((sess >= a) & (sess <= b))
    if len(idx) == 0:
        return None
    i0, i1 = int(first[idx[0]]), int(last[idx[-1]]) + 1
    r = bt.simulate(ts[i0:i1], o[i0:i1], c[i0:i1], w[i0:i1],
                    band=BAND, slippage_bps=slip)
    s = bt.stats(r, BARS_PER_YEAR)
    return {
        "cagr": float(s["cagr"]),
        "max_drawdown": float(s["max_drawdown"]),
        "sharpe": float(s["sharpe"]),
        "exposure_tqqq": float(w[i0:i1, 1].mean()),
        "ending_equity": float(s["ending_equity"]),
    }


def _year_logs(deq):
    ye = deq.groupby(deq.index.map(lambda d: d.year)).last()
    logs, prev = {}, deq.iloc[0]
    for y, v in ye.items():
        logs[int(y)] = float(np.log(v / prev))
        prev = v
    return logs


def _flat_weights(n_bars, hold, mult=None):
    """Turn a per-bar hold mask (+ optional multiplier) into [QQQ, TQQQ, BIL]."""
    e = hold.astype(float) if mult is None else hold.astype(float) * mult
    w = np.zeros((n_bars, 3))
    if n_bars > 1:
        w[:-1, 1] = e[1:]
        w[-1, 1] = e[-1]
    w[:, 2] = 1.0 - w[:, 1]
    return w


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1min", warmup_days=10)
    dates, first, last, sess = _calendar(ts)
    n_sess = len(sess)
    n_bars = len(ts)
    years_full = (sess[-1] - sess[0]).days / 365.25
    pairs = _pairs(sess, P_BACK)
    anchors = [k for k, _ in pairs]
    print(f"bars {n_bars:,}  sessions {n_sess}  windows {len(pairs)}")

    # Holiday list validation against the panel calendar.
    ss = set(sess)
    traded_holidays = [str(h) for h in HOLIDAYS if h in ss]
    weekday_gaps = []
    d = sess[0]
    while d <= sess[-1]:
        if d.weekday() < 5 and d not in ss:
            weekday_gaps.append(d)
        d = date.fromordinal(d.toordinal() + 1)
    unexplained = [str(x) for x in weekday_gaps
                   if x not in set(HOLIDAYS) and x not in UNSCHEDULED]

    out = {
        "agent": "pre-holiday",
        "idea": "Own TQQQ only for the 1-3 sessions before scheduled US market "
                "holidays, BIL otherwise, with a volatility gate.",
        "hypothesis": "A short-horizon risk premium is paid for holding equity "
                      "inventory into a multi-day exchange closure; a 3x fund "
                      "amplifies it.",
        "universe": ["QQQ", "TQQQ", "BIL"],
        "window": {"start": START, "end": END, "marks": "1m"},
        "bar": TQQQ_BAR,
        "target_dd": TARGET_DD,
        "primary_id": "G1",
        "params": {
            "back": P_BACK, "mode": P_MODE, "half_days": P_HALF,
            "vol_gate": {"measure": "TQQQ 20d realised vol, annualised",
                         "threshold": "trailing 252d q75",
                         "shut_weight": P_GATE_FLOOR,
                         "lookahead": "none: gate uses data through k-1"},
            "band": BAND, "costs_bp": list(COSTS), "out_asset": "BIL",
        },
        "calendar_check": {
            "holidays_listed": len(HOLIDAYS),
            "windows_used": len(pairs),
            "holiday_dates_that_traded": traded_holidays,
            "weekday_gaps_unexplained": unexplained,
            "weekday_gaps_from_unscheduled": [str(x) for x in sorted(UNSCHEDULED)],
            "half_days_in_window": len(HALF_DAYS),
        },
    }

    # --- benchmark on the same 1-minute marks ---------------------------
    i0 = bt.start_index(ts, START)
    bench = bt.benchmark(c[i0:, 1], ts[i0:], BARS_PER_YEAR)
    out["benchmark_1min"] = {k: float(bench[k]) for k in
                             ("cagr", "max_drawdown", "sharpe", "volatility",
                              "years", "ending_equity")}
    print(f"TQQQ 1m bench: CAGR {bench['cagr']*100:.2f}%  "
          f"DD {bench['max_drawdown']*100:.2f}%  Sh {bench['sharpe']:.2f}")

    # --- primary -------------------------------------------------------
    w_primary, diag = weights_for(ts, o, c, back=P_BACK, mode=P_MODE,
                                  half=P_HALF, gate_floor=P_GATE_FLOOR,
                                  gate_q=P_GATE_Q, gate=True)
    per_cost = {}
    for slip in COSTS:
        m, r, dts, deq = _metrics(ts, o, c, w_primary, slip)
        per_cost[f"{slip:.0f}bp"] = m
        if slip == 1.0:
            p_eq, p_dts, p_deq = np.asarray(r["equity"]), dts, deq
    corr_t, beta_t = _corr_beta(p_dts, p_eq, c[i0:, 1])
    corr_q, beta_q = _corr_beta(p_dts, p_eq, c[i0:, 0])
    p = per_cost["1bp"]

    out["primary"] = {
        "id": "G1",
        "params": {"back": P_BACK, "mode": P_MODE, "half_days": P_HALF,
                   "vol_gate_floor": P_GATE_FLOOR, "vol_gate_q": P_GATE_Q},
        "diagnostics": diag,
        "dev": per_cost,
        "corr_tqqq_daily": corr_t, "beta_tqqq_daily": beta_t,
        "corr_qqq_daily": corr_q, "beta_qqq_daily": beta_q,
    }
    out["windows"] = {"dev": per_cost}
    out["dev_1bp"] = p
    out["exposure"] = p["exposure_tqqq"]
    out["corr_vs_tqqq"] = corr_t
    out["yearly"] = p["yearly"]

    # --- pre-registered grid (8 cells) ----------------------------------
    grid_defs = [
        ("G1", 3, "hold_through", False, 0.5, 0.75,
         "primary: 3 sessions + 0.5 vol gate above trailing q75"),
        ("G2", 1, "hold_through", False, 0.0, 0.75, "shortest window"),
        ("G3", 2, "hold_through", False, 0.0, 0.75, "middle window"),
        ("G4", 3, "hold_through", False, 0.0, 0.75, "primary without the filter"),
        ("G5", 3, "exit_1559", False, 0.0, 0.75, "pure session exposure, no holiday gap"),
        ("G6", 3, "hold_through", True, 0.0, 0.75, "adds the shortened sessions"),
        ("G7", 3, "hold_through", False, 0.0, 0.50, "hard vol gate (0) above q50"),
        ("G8", 5, "hold_through", False, 0.0, 0.75, "window-length neighbour"),
    ]
    grid = {}
    for cid, back, mode, half, floor, q, note in grid_defs:
        use_gate = bool(floor > 0.0 or q != 0.75 or cid == "G7")
        w, dg = weights_for(ts, o, c, back=back, mode=mode, half=half,
                            gate_floor=floor, gate_q=q, gate=use_gate)
        m, _, _, _ = _metrics(ts, o, c, w, 1.0)
        rec = {"note": note, "back": back, "mode": mode, "half_days": half,
               "vol_gate": {"floor": floor, "q": q} if use_gate else None,
               "diagnostics": dg, "dev_1bp": m}
        for slip in (5.0, 10.0):
            rec[f"dev_{slip:.0f}bp"] = _lite(ts, o, c, w, slip)
        grid[cid] = rec
        print(f"  {cid}: CAGR {m['cagr']*100:6.2f}%  DD {m['max_drawdown']*100:5.2f}%  "
              f"Sh {m['sharpe']:4.2f}  wTQQQ {m['exposure_tqqq']*100:5.1f}%  "
              f"win {dg['windows']:3d}  sess {dg['session_share']*100:5.1f}%")
    out["grid"] = grid

    # --- window-length frontier (diagnostic, not a selection menu) ------
    frontier = {}
    for back in list(range(1, 8)) + [10, 12, 15, 20, 25]:
        w, dg = weights_for(ts, o, c, back=back, mode="hold_through",
                            half=False, gate=False)
        m = _lite(ts, o, c, w, 1.0)
        frontier[str(back)] = {
            "back": back, "cagr": m["cagr"], "max_drawdown": m["max_drawdown"],
            "sharpe": m["sharpe"], "exposure_tqqq": m["exposure_tqqq"],
            "session_share": dg["session_share"],
            "calmar": (m["cagr"] / m["max_drawdown"]) if m["max_drawdown"] > 0 else None,
        }
        print(f"  frontier back {back:2d}: CAGR {m['cagr']*100:6.2f}%  "
              f"DD {m['max_drawdown']*100:5.1f}%  Sh {m['sharpe']:4.2f}  "
              f"sess {dg['session_share']*100:5.1f}%")
    under60 = [v for v in frontier.values() if v["max_drawdown"] < TARGET_DD]
    out["frontier"] = {
        "note": "window-length scan; reported to show the family's risk-return "
                "line, not used to pick the primary",
        "by_back": frontier,
        "best_cagr_under_60dd": max((v["cagr"] for v in under60), default=None),
        "best_calmar": max(frontier.values(),
                           key=lambda v: v["calmar"] or -1.0)["back"],
        "cells_clearing_published_bar": [
            back for back, v in frontier.items()
            if v["cagr"] > TQQQ_BAR["cagr"]
            and v["max_drawdown"] < TQQQ_BAR["max_drawdown"]],
        "note_on_bar_clearing": "only the 20-session cell clears the published "
                                "bar, at 60.8% of sessions and 75.1% DD; it is "
                                "not a pre-holiday strategy and the adjacent "
                                "15/25 cells give 26.6%/30.3% CAGR",
    }

    # --- per-window event study ----------------------------------------
    tq_o, tq_c = o[:, 1], c[:, 1]
    rows = []
    for k, h in pairs:
        a = k - P_BACK + 1
        ia, ib = int(first[a]), int(last[k])
        x = min(k + 1, n_sess - 1)
        hold_ret = tq_o[int(first[x])] / tq_o[ia] - 1.0
        sess_ret = tq_c[ib] / tq_o[ia] - 1.0
        intraday = float(np.sum(np.log(tq_c[last[a:k + 1]] / tq_o[first[a:k + 1]])))
        night = float(np.sum(np.log(tq_o[first[a + 1:k + 2]] /
                                  tq_c[last[a:k + 1]]))) if k + 2 <= n_sess else np.nan
        rows.append({"holiday": str(h), "anchor": str(sess[k]),
                     "start": str(sess[a]), "end": str(sess[x]),
                     "hold_ret": float(hold_ret), "session_ret": float(sess_ret),
                     "intraday_log": intraday, "overnight_log": night})
    ev = pd.DataFrame(rows)
    v = ev["hold_ret"].to_numpy()
    vs = ev["session_ret"].to_numpy()
    rng = np.random.default_rng(20261127)
    draws = rng.integers(0, n_sess - P_BACK - 1, size=(4000, len(v)))
    null_means = np.array([np.mean(tq_o[first[s + P_BACK]] / tq_o[first[s]] - 1.0)
                           for s in draws])
    out["event_study"] = {
        "n_windows": int(len(v)),
        "hold_through": {
            "mean": float(v.mean()), "median": float(np.median(v)),
            "sd": float(v.std(ddof=1)),
            "t": float(v.mean() / (v.std(ddof=1) / np.sqrt(len(v)))),
            "positive_share": float((v > 0).mean()),
            "sum_log": float(np.log1p(v).sum()),
            "cagr_if_only_these_days": float(np.exp(np.log1p(v).sum() / 7.98) - 1.0),
        },
        "session_only": {
            "mean": float(vs.mean()), "median": float(np.median(vs)),
            "sd": float(vs.std(ddof=1)),
            "t": float(vs.mean() / (vs.std(ddof=1) / np.sqrt(len(vs)))),
            "positive_share": float((vs > 0).mean()),
            "sum_log": float(np.log1p(vs).sum()),
            "cagr_if_only_these_days": float(np.exp(np.log1p(vs).sum() / 7.98) - 1.0),
        },
        "decomposition_sum_log": {
            "intraday": float(ev["intraday_log"].sum()),
            "overnight": float(np.nansum(ev["overnight_log"])),
        },
        "random_null": {
            "draws": 4000, "seed": 20261127,
            "note": "per draw: mean open->open return of 73 random 3-session "
                    "windows, same count and length as the primary",
            "mean_of_means": float(null_means.mean()),
            "sd_of_means": float(null_means.std(ddof=1)),
            "p50": float(np.percentile(null_means, 50)),
            "p95": float(np.percentile(null_means, 95)),
            "pctile_of_primary": float((null_means < v.mean()).mean()),
        },
        "worst": sorted(rows, key=lambda r: r["hold_ret"])[:5],
        "best": sorted(rows, key=lambda r: r["hold_ret"])[-5:],
    }
    print(f"  event: mean {v.mean()*100:.2f}%  t {out['event_study']['hold_through']['t']:.2f}  "
          f"null pct {out['event_study']['random_null']['pctile_of_primary']*100:.1f}%  "
          f"intraday log {out['event_study']['decomposition_sum_log']['intraday']*100:.1f}%  "
          f"overnight log {out['event_study']['decomposition_sum_log']['overnight']*100:.1f}%")

    # --- placebo: same count and length, random start sessions ----------
    def placebo_draws(seed, n_draws, count, length):
        r = np.random.default_rng(seed)
        res = []
        for _ in range(n_draws):
            s = r.integers(0, n_sess - length, count)
            held = np.zeros(n_sess, bool)
            for x in s:
                held[x:x + length] = True
            w = _flat_weights(n_bars, np.repeat(held, np.diff(np.r_[first, n_bars])))
            m = _lite(ts, o, c, w, 1.0)
            res.append((m["cagr"], m["max_drawdown"], m["sharpe"],
                        m["exposure_tqqq"]))
        return np.asarray(res)

    pres = placebo_draws(11, 500, len(pairs), P_BACK)
    unf = grid["G4"]["dev_1bp"]
    out["placebo"] = {
        "draws": 500, "seed": 11, "n_windows": len(pairs),
        "hold_sessions": P_BACK, "overlaps_allowed": True,
        "note": "random start sessions, same window count and length; no filter",
        "cagr": {"median": float(np.median(pres[:, 0])),
                 "p90": float(np.percentile(pres[:, 0], 90)),
                 "p95": float(np.percentile(pres[:, 0], 95)),
                 "p99": float(np.percentile(pres[:, 0], 99)),
                 "max": float(pres[:, 0].max()),
                 "percentile_of_primary": float((pres[:, 0] < p["cagr"]).mean()),
                 "percentile_of_unfiltered": float((pres[:, 0] < unf["cagr"]).mean())},
        "max_drawdown": {"median": float(np.median(pres[:, 1])),
                         "p10": float(np.percentile(pres[:, 1], 10)),
                         "p05": float(np.percentile(pres[:, 1], 5)),
                         "min": float(pres[:, 1].min()),
                         "percentile_of_primary": float((pres[:, 1] > p["max_drawdown"]).mean())},
        "sharpe": {"median": float(np.median(pres[:, 2])),
                   "p95": float(np.percentile(pres[:, 2], 95)),
                   "max": float(pres[:, 2].max()),
                   "percentile_of_primary": float((pres[:, 2] < p["sharpe"]).mean())},
        "exposure_median": float(np.median(pres[:, 3])),
        "joint_frac_cagr_ge_primary_and_dd_le": float(np.mean(
            (pres[:, 0] >= p["cagr"]) & (pres[:, 1] <= p["max_drawdown"]))),
    }
    # exposure-matched: non-overlapping blocks on a fixed cycle, every phase
    step = max(1, n_sess // len(pairs))
    phase = []
    for ph in range(step):
        held = np.zeros(n_sess, bool)
        for x in range(ph, n_sess - P_BACK, step):
            held[x:x + P_BACK] = True
        w = _flat_weights(n_bars, np.repeat(held, np.diff(np.r_[first, n_bars])))
        m = _lite(ts, o, c, w, 1.0)
        phase.append((m["cagr"], m["max_drawdown"], m["sharpe"],
                      m["exposure_tqqq"]))
    phase = np.asarray(phase)
    out["placebo_phase"] = {
        "note": "generic every-Nth-session cycle, all phases; same number of "
                "non-overlapping 3-session blocks, exposure-matched",
        "phases": int(step), "step_sessions": int(step),
        "exposure_median": float(np.median(phase[:, 3])),
        "cagr": {"median": float(np.median(phase[:, 0])),
                 "p90": float(np.percentile(phase[:, 0], 90)),
                 "p95": float(np.percentile(phase[:, 0], 95)),
                 "max": float(phase[:, 0].max()),
                 "percentile_of_primary": float((phase[:, 0] < p["cagr"]).mean())},
        "max_drawdown": {"median": float(np.median(phase[:, 1])),
                         "p05": float(np.percentile(phase[:, 1], 5)),
                         "min": float(phase[:, 1].min()),
                         "percentile_of_primary": float((phase[:, 1] > p["max_drawdown"]).mean())},
        "sharpe": {"median": float(np.median(phase[:, 2])),
                   "p95": float(np.percentile(phase[:, 2], 95)),
                   "percentile_of_primary": float((phase[:, 2] < p["sharpe"]).mean())},
    }
    print(f"  placebo: CAGR p50 {out['placebo']['cagr']['median']*100:5.1f}%  "
          f"p95 {out['placebo']['cagr']['p95']*100:5.1f}%  "
          f"primary pct {out['placebo']['cagr']['percentile_of_primary']*100:4.1f}%  "
          f"unfiltered pct {out['placebo']['cagr']['percentile_of_unfiltered']*100:4.1f}%")

    # --- shift test: move every anchor by s sessions ---------------------
    shift_rows = {}
    for s in range(-10, 11):
        moved = [k + s for k in anchors if 0 <= k + s < n_sess]
        held = _held_sessions(sess, moved, P_BACK, P_HALF)
        hold = _hold_bars(n_bars, first, last, held, P_MODE)
        w = _flat_weights(n_bars, hold)
        m = _lite(ts, o, c, w, 1.0)
        shift_rows[str(s)] = {"cagr": m["cagr"], "max_drawdown": m["max_drawdown"],
                              "sharpe": m["sharpe"], "exposure_tqqq": m["exposure_tqqq"]}
    out["shift_test"] = {
        "note": "every holiday anchor shifted by N sessions; same 3-session "
                "window, no filter. A genuine pre-holiday premium should peak at 0",
        "by_shift": shift_rows,
        "peak_shift": max(shift_rows, key=lambda s: shift_rows[s]["cagr"]),
        "cagr_at_0": shift_rows["0"]["cagr"],
    }
    print(f"  shift: peak at {out['shift_test']['peak_shift']}  "
          f"CAGR@0 {shift_rows['0']['cagr']*100:.1f}%  "
          f"peak {shift_rows[out['shift_test']['peak_shift']]['cagr']*100:.1f}%")

    # --- cuts ------------------------------------------------------------
    cuts = {}
    for lab, a, b in (("2016-2019", date(2016, 1, 4), date(2019, 12, 31)),
                      ("2020-2021", date(2020, 1, 2), date(2021, 12, 31)),
                      ("2022-2023", date(2022, 1, 3), date(2023, 12, 29))):
        cuts[lab] = _slice(ts, o, c, w_primary, a, b)
    out["cuts"] = {"subperiods": cuts}

    ylogs = _year_logs(p_deq)
    tot = float(np.log(p_deq.iloc[-1] / p_deq.iloc[0]))
    loo = {}
    for y, lg in ylogs.items():
        loo[str(y)] = {"year_return": float(np.exp(lg) - 1.0),
                       "ex_cagr": float(np.exp((tot - lg) / 7.0) - 1.0)}
    out["cuts"]["leave_one_year_out"] = loo

    order = np.argsort(v)[::-1]
    drop = {}
    for n in (1, 3, 5):
        bad = {int(anchors[i]) for i in order[:n]}
        w, dg = weights_for(ts, o, c, back=P_BACK, mode=P_MODE, half=P_HALF,
                            gate_floor=P_GATE_FLOOR, gate_q=P_GATE_Q,
                            gate=True, exclude=bad)
        m = _lite(ts, o, c, w, 1.0)
        drop[f"drop_best_{n}"] = {**m, "windows": dg["windows"]}
    out["cuts"]["drop_best_windows"] = drop

    ev["md"] = ev["holiday"].map(lambda s: s[5:])
    slot = ev.groupby("md")["hold_ret"].agg(["count", "mean"])
    out["cuts"]["by_slot"] = {k: {"count": int(r["count"]), "mean": float(r["mean"])}
                              for k, r in slot.iterrows()}

    # --- overnight vs intraday decomposition of TQQQ ---------------------
    tq_c_d = c[last, 1]
    tq_o_d = o[first, 1]
    oc = np.log(tq_c_d / tq_o_d)
    cc = np.r_[np.nan, np.log(tq_o_d[1:] / tq_c_d[:-1])]
    out["decomposition_all_sessions"] = {
        "years": float(years_full),
        "intraday_sum_log": float(np.nansum(oc)),
        "overnight_sum_log": float(np.nansum(cc)),
        "intraday_share_of_log": float(np.nansum(oc) / np.nansum(oc + cc)),
        "intraday_cagr": float(np.exp(np.nansum(oc) / years_full) - 1.0),
        "overnight_cagr": float(np.exp(np.nansum(cc) / years_full) - 1.0),
        "note": "TQQQ on all 2016-2023 sessions: 36.5% of the log return is "
                "earned open-to-close and 63.5% close-to-open. Inside the "
                "pre-holiday windows the split flips (see event_study), so any "
                "pre-holiday premium is a session phenomenon, not an "
                "overnight one.",
    }

    # --- sensitivity: include the unscheduled 2018-12-05 closure ---------
    w_alt, _ = weights_for(ts, o, c, back=P_BACK, mode=P_MODE, half=P_HALF,
                           gate_floor=P_GATE_FLOOR, gate_q=P_GATE_Q, gate=True,
                           extra_holidays=UNSCHEDULED)
    m_alt = _lite(ts, o, c, w_alt, 1.0)
    out["sensitivity_unscheduled_2018_12_05"] = {
        "note": "adds the Bush day-of-mourning closure, not knowable in advance; "
                "not used by the primary",
        "dev_1bp": m_alt,
    }

    # --- exposure arithmetic: what the bar would require ------------------
    bar_log = float(np.log1p(TQQQ_BAR["cagr"]) * years_full)
    obs_log = float(np.sum(np.log1p(v)))
    req_win = bar_log / len(v)
    out["exposure_arithmetic"] = {
        "windows": int(len(v)),
        "tqqq_total_log_required": bar_log,
        "observed_total_log_of_windows": obs_log,
        "multiple_of_window_return_needed": float(bar_log / obs_log),
        "required_log_per_window": float(req_win),
        "observed_log_per_window": float(np.mean(np.log1p(v))),
        "required_arithmetic_per_window": float(req_win + 0.5 * np.var(v)),
        "observed_arithmetic_per_window": float(v.mean()),
        "note": "the strategy owns TQQQ in 10.7% of sessions, so matching a "
                "fully-invested TQQQ requires each 3-session window to compound "
                "far more than the whole sample delivered; this is why no "
                "1-3 session cell can clear the bar",
    }
    se_log = float(np.std(np.log1p(v), ddof=1) / np.sqrt(len(v)))
    cagr_ev = float(np.exp(np.log1p(v).sum() / years_full) - 1.0)
    out["sampling_error"] = {
        "window_log_sd": float(np.std(np.log1p(v), ddof=1)),
        "se_log_per_window": se_log,
        "se_total_log": float(se_log * len(v)),
        "se_cagr_points": float((1.0 + cagr_ev) * se_log * len(v) / years_full),
        "note": "one standard error on the CAGR from window selection alone; "
                "it is larger than the whole 1-3 session CAGR range",
    }

    # --- status ----------------------------------------------------------
    passed = (p["cagr"] > TQQQ_BAR["cagr"]
              and p["max_drawdown"] < TQQQ_BAR["max_drawdown"])
    best_cell = max(grid, key=lambda cid: grid[cid]["dev_1bp"]["cagr"])
    out["best_grid_cell"] = {
        "id": best_cell,
        "cagr": grid[best_cell]["dev_1bp"]["cagr"],
        "max_drawdown": grid[best_cell]["dev_1bp"]["max_drawdown"],
        "sharpe": grid[best_cell]["dev_1bp"]["sharpe"],
    }
    out["passed_dev_bar"] = bool(passed)
    out["status"] = "passed_dev_only" if passed else "below_dev_bar"
    out["verdict"] = (
        "FAIL. The pre-holiday window return is statistically indistinguishable "
        "from a random window (t=0.52; 43.5th percentile of a 4,000-draw null) "
        "and is one to two orders of magnitude too small to lift a 10.7%-of-"
        "sessions strategy to TQQQ's compounded 36.72%. The best pre-registered "
        "cell is G8 (5 sessions) at 21.21% CAGR, 15.5 points short; the best "
        "1-3 session cell is G3 at 5.29%. Do not send to holdout."
    )
    out["notes"] = [
        f"TQQQ benchmark recomputed on the same 1-minute panel is "
        f"{bench['cagr']*100:.2f}% / {bench['max_drawdown']*100:.2f}% / "
        f"{bench['sharpe']:.2f}; the programme bar is 36.72% / 82.29% / 0.82.",
        f"{len(HOLIDAYS)} scheduled holidays, {len(pairs)} windows in the dev "
        f"window, {diag['held_sessions']} held sessions.",
        "The holiday list reproduces every weekday gap in the panel exactly; "
        "the only excluded closure is the unscheduled 2018-12-05.",
        "exposure_tqqq is the mean TQQQ weight over 1-minute bars, not "
        "bt.stats' 'exposure' (which counts the BIL leg as invested).",
    ]

    (HERE / "result.json").write_text(json.dumps(out, indent=2, default=float),
                                      encoding="utf-8")
    print(f"\nwrote {HERE / 'result.json'}")
    print(f"primary 1bp: CAGR {p['cagr']*100:.2f}%  DD {p['max_drawdown']*100:.2f}%  "
          f"Sharpe {p['sharpe']:.2f}  wTQQQ {p['exposure_tqqq']*100:.1f}%  "
          f"corr {corr_t:.2f}  fills {p['fills']}  turnover {p['turnover']:.0f}x")


if __name__ == "__main__":
    main()
