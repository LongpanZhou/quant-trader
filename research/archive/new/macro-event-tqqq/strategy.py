"""Macro-event TQQQ: hold the middle of the FOMC intermeeting period.

Rules
-----
For every scheduled FOMC decision day F (session k):
    long TQQQ from the open of session k+3 through the close of session k+20
    BIL otherwise.
No stop, no trend filter, no shorting.  Entry is a target set on the prior
session's last bar and filled at the next session's 09:30 open; exit is set at
15:58 and filled at the 15:59 open, so the position is not held overnight after
the window.

This file writes ``result.json`` with:
  * primary dev results at 1/5/10 bp,
  * the 8-cell pre-registered grid,
  * a random-date placebo with the same event count and window length,
  * a shifted-calendar test, subperiod cuts and leave-one-year-out,
  * per-cycle event study on TQQQ and QQQ,
  * daily correlation/beta to TQQQ.

Development window only: 2016-01-04 .. 2023-12-29.  The panel call below never
reads a 2024+ row.

Run:
    cd C:\\Users\\27175\\Desktop\\quant-trader-research
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    $env:BT_THREADS = "1"
    python research/new/macro-event-tqqq/strategy.py
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
BARS_PER_YEAR = 252 * 390
BAND = 0.02
COSTS = (1.0, 5.0, 10.0)
TQQQ_BAR = {"cagr": 0.3672, "max_drawdown": 0.8229, "sharpe": 0.82}

# ---------------------------------------------------------------------------
# Hardcoded, ex-ante calendars.  Source: Federal Reserve FOMC calendars;
# BLS CPI release schedules.  No network access at run time.
# The 2026-10-28 and 2026-12-09 FOMC decisions fall after the 2026-10-23
# verification panel end and are therefore not listed.
# ---------------------------------------------------------------------------
FOMC = """
2016-01-27 2016-03-16 2016-04-27 2016-06-15 2016-07-27 2016-09-21 2016-11-02 2016-12-14
2017-02-01 2017-03-15 2017-05-03 2017-06-14 2017-07-26 2017-09-20 2017-11-01 2017-12-13
2018-01-31 2018-03-21 2018-05-02 2018-06-13 2018-08-01 2018-09-26 2018-11-08 2018-12-19
2019-01-30 2019-03-20 2019-05-01 2019-06-19 2019-07-31 2019-09-18 2019-10-30 2019-12-11
2020-01-29 2020-04-29 2020-06-10 2020-07-29 2020-09-16 2020-11-05 2020-12-16
2021-01-27 2021-03-17 2021-04-28 2021-06-16 2021-07-28 2021-09-22 2021-11-03 2021-12-15
2022-01-26 2022-03-16 2022-05-04 2022-06-15 2022-07-27 2022-09-21 2022-11-02 2022-12-14
2023-02-01 2023-03-22 2023-05-03 2023-06-14 2023-07-26 2023-09-20 2023-11-01 2023-12-13
2024-01-31 2024-03-20 2024-05-01 2024-06-12 2024-07-31 2024-09-18 2024-11-07 2024-12-18
2025-01-29 2025-03-19 2025-05-07 2025-06-18 2025-07-30 2025-09-17 2025-10-29 2025-12-10
2026-01-28 2026-03-18 2026-04-29 2026-06-17 2026-07-29 2026-09-16
"""

# CPI release dates (08:30 ET).  2016 reconstructed from the published 2016
# schedule; 2017-2023 from archived BLS schedules.
CPI = """
2016-01-20 2016-02-19 2016-03-16 2016-04-14 2016-05-13 2016-06-16
2016-07-15 2016-08-16 2016-09-16 2016-10-18 2016-11-17 2016-12-15
2017-01-18 2017-02-15 2017-03-15 2017-04-14 2017-05-12 2017-06-14
2017-07-14 2017-08-11 2017-09-14 2017-10-13 2017-11-15 2017-12-13
2018-01-12 2018-02-14 2018-03-13 2018-04-11 2018-05-10 2018-06-12
2018-07-12 2018-08-10 2018-09-13 2018-10-11 2018-11-14 2018-12-12
2019-01-11 2019-02-13 2019-03-12 2019-04-10 2019-05-10 2019-06-12
2019-07-11 2019-08-13 2019-09-12 2019-10-10 2019-11-13 2019-12-11
2020-01-14 2020-02-13 2020-03-11 2020-04-10 2020-05-12 2020-06-10
2020-07-14 2020-08-12 2020-09-11 2020-10-13 2020-11-12 2020-12-10
2021-01-13 2021-02-10 2021-03-10 2021-04-13 2021-05-12 2021-06-10
2021-07-13 2021-08-11 2021-09-14 2021-10-13 2021-11-10 2021-12-10
2022-01-12 2022-02-10 2022-03-10 2022-04-12 2022-05-11 2022-06-10
2022-07-13 2022-08-10 2022-09-13 2022-10-13 2022-11-10 2022-12-13
2023-01-12 2023-02-14 2023-03-14 2023-04-12 2023-05-10 2023-06-13
2023-07-12 2023-08-10 2023-09-13 2023-10-12 2023-11-14 2023-12-12
"""

# Monthly option expiry: third Friday, rolled back over a holiday.  Frozen list.
OPEX = """
2016-01-15 2016-02-19 2016-03-18 2016-04-15 2016-05-20 2016-06-17 2016-07-15 2016-08-19 2016-09-16 2016-10-21 2016-11-18 2016-12-16
2017-01-20 2017-02-17 2017-03-17 2017-04-21 2017-05-19 2017-06-16 2017-07-21 2017-08-18 2017-09-15 2017-10-20 2017-11-17 2017-12-15
2018-01-19 2018-02-16 2018-03-16 2018-04-20 2018-05-18 2018-06-15 2018-07-20 2018-08-17 2018-09-21 2018-10-19 2018-11-16 2018-12-21
2019-01-18 2019-02-15 2019-03-15 2019-04-18 2019-05-17 2019-06-21 2019-07-19 2019-08-16 2019-09-20 2019-10-18 2019-11-15 2019-12-20
2020-01-17 2020-02-21 2020-03-20 2020-04-17 2020-05-15 2020-06-19 2020-07-17 2020-08-21 2020-09-18 2020-10-16 2020-11-20 2020-12-18
2021-01-15 2021-02-19 2021-03-19 2021-04-16 2021-05-21 2021-06-18 2021-07-16 2021-08-20 2021-09-17 2021-10-15 2021-11-19 2021-12-17
2022-01-21 2022-02-18 2022-03-18 2022-04-14 2022-05-20 2022-06-17 2022-07-15 2022-08-19 2022-09-16 2022-10-21 2022-11-18 2022-12-16
2023-01-20 2023-02-17 2023-03-17 2023-04-21 2023-05-19 2023-06-16 2023-07-21 2023-08-18 2023-09-15 2023-10-20 2023-11-17 2023-12-15
"""


def _dates(block: str) -> list[date]:
    return [date.fromisoformat(tok) for tok in block.split()]


FOMC_DATES = _dates(FOMC)
CPI_DATES = _dates(CPI)
OPEX_DATES = _dates(OPEX)


# ---------------------------------------------------------------------------
# Calendar and weight construction
# ---------------------------------------------------------------------------
def _sessions(ts):
    """(dates, first_bar, last_bar, session_dates, day_of) for a 1-min panel."""
    dates = bt.session_dates(ts)
    first, last = bt.day_bounds_from_dates(dates)
    sess = dates[first]
    day_of = {d: k for k, d in enumerate(sess)}
    return dates, first, last, sess, day_of


def event_windows(sess, day_of, events, a_off: int, b_off: int):
    """Inclusive session-index windows ``[k+a_off, k+b_off]`` around events.

    Windows that start before the panel or run past the last session are
    clipped; windows whose event is not a trading day are skipped.
    """
    out = []
    n = len(sess)
    for d in events:
        k = day_of.get(d)
        if k is None:
            continue
        ka, kb = k + a_off, k + b_off
        if ka < 0 or ka >= n:
            continue
        kb = min(kb, n - 1)
        if kb >= ka:
            out.append((ka, kb))
    return out


def weights_from_index_windows(ts, windows):
    """0/1 TQQQ targets from inclusive session windows.

    The target is true from the first bar of the entry session up to (but not
    including) the last bar of the exit session, so the exit fill is the 15:59
    open and the position is not carried overnight after the window.
    """
    dates = bt.session_dates(ts)
    first, last = bt.day_bounds_from_dates(dates)
    target = np.zeros(len(ts), dtype=bool)
    for ka, kb in windows:
        if ka < 0 or kb < ka or ka >= len(first):
            continue
        kb = min(kb, len(first) - 1)
        target[first[ka]:last[kb]] = True
    w = np.zeros((len(ts), 3))
    if len(ts) > 1:
        w[:-1, 1] = target[1:].astype(float)
    w[:, 2] = 1.0 - w[:, 1]
    return w


def build_weights(ts, o, c):
    """Primary strategy weights: FOMC +3 .. +20, TQQQ else BIL.

    Parameters ``o`` and ``c`` are accepted for the shared interface; the
    signal is purely calendar-based and does not use prices.
    """
    _, _, _, sess, day_of = _sessions(ts)
    windows = event_windows(sess, day_of, FOMC_DATES, 3, 20)
    return weights_from_index_windows(ts, windows)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
def _metrics(ts, o, c, w, slip: float = 1.0):
    r = bt.run(ts, o, c, w, START, band=BAND, slippage_bps=slip)
    s = bt.stats(r, BARS_PER_YEAR)
    i = bt.start_index(ts, START)
    eq = np.asarray(r["equity"], dtype=float)
    dts = ts[i:]
    deq = pd.Series(eq, index=dts).groupby(dts.date).last()
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
        "exposure": float(w[i:, 1].mean()),
        "exposure_invested": float(s["exposure"]),
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
    return out, eq, dts, deq


def _daily_series(ts, values):
    return pd.Series(values, index=ts).groupby(ts.date).last()


def _corr_beta(ts, equity, price):
    a = _daily_series(ts, equity).pct_change()
    b = _daily_series(ts, price).pct_change()
    j = pd.concat([a.rename("s"), b.rename("b")], axis=1).dropna()
    corr = float(j["s"].corr(j["b"]))
    beta = float(np.cov(j["s"], j["b"])[0, 1] / np.var(j["b"], ddof=1))
    return corr, beta


def _slice(ts, o, c, w, a, b, slip=1.0):
    """Simulate sessions a..b inclusive (both must be trading days)."""
    _, first, last, sess, day_of = _sessions(ts)
    ka, kb = day_of[a], day_of[b]
    i0, i1 = first[ka], last[kb] + 1
    r = bt.simulate(ts[i0:i1], o[i0:i1], c[i0:i1], w[i0:i1],
                    band=BAND, slippage_bps=slip)
    s = bt.stats(r, BARS_PER_YEAR)
    t = ts[i0:i1]
    eq = np.asarray(r["equity"], float)
    deq = pd.Series(eq, index=t).groupby(t.date).last()
    return {
        "cagr": float(s["cagr"]),
        "max_drawdown": float(s["max_drawdown"]),
        "sharpe": float(s["sharpe"]),
        "exposure": float(w[i0:i1, 1].mean()),
        "ending_equity": float(s["ending_equity"]),
    }


def _year_logs(deq):
    ye = deq.groupby(deq.index.map(lambda d: d.year)).last()
    y0 = deq.iloc[0]
    logs, prev = {}, y0
    for y, v in ye.items():
        logs[int(y)] = float(np.log(v / prev))
        prev = v
    return logs


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1min", warmup_days=10)
    _, _, _, sess, day_of = _sessions(ts)
    n_sess = len(sess)
    fomc_idx = [k for d in FOMC_DATES if (k := day_of.get(d)) is not None]
    print(f"bars {len(ts):,}  sessions {n_sess}  FOMC {len(fomc_idx)}")

    out = {
        "agent": "macro-event-tqqq",
        "idea": "Own TQQQ only in the middle of the FOMC intermeeting period; "
                "BIL during the post-decision unwind and the late pre-meeting de-risking.",
        "hypothesis": "The equity risk premium is earned in the ~3 weeks after the "
                      "two-day post-FOMC positioning unwind; the immediate post-decision "
                      "and late pre-meeting phases are flat or negative.",
        "universe": ["QQQ", "TQQQ", "BIL"],
        "window": {"start": START, "end": END, "marks": "1m"},
        "bar": TQQQ_BAR,
        "primary_id": "G1",
        "params": {"event": "scheduled FOMC decision day",
                   "entry_offset": 3, "exit_offset": 20, "hold_sessions": 18,
                   "out_asset": "BIL", "band": BAND,
                   "costs_bp": list(COSTS)},
        "event_count": {"scheduled_fomc": len(FOMC_DATES),
                        "in_panel": len(fomc_idx),
                        "windows_used": len(event_windows(sess, day_of, FOMC_DATES, 3, 20))},
        "excluded": ["unscheduled emergency FOMC 2020-03-03, 2020-03-15",
                     "scheduled 2020-03-18 meeting (cancelled)"],
    }

    # --- benchmark on the same 1-min marks -------------------------------
    i0 = bt.start_index(ts, START)
    bench = bt.benchmark(c[i0:, 1], ts[i0:], BARS_PER_YEAR)
    out["benchmark_1min"] = {k: float(bench[k]) for k in
                             ("cagr", "max_drawdown", "sharpe", "volatility",
                              "years", "ending_equity")}

    # --- primary at 1/5/10 bp -------------------------------------------
    w_primary = build_weights(ts, o, c)
    per_cost = {}
    primary_eq = primary_dts = primary_deq = None
    for slip in COSTS:
        m, eq, dts, deq = _metrics(ts, o, c, w_primary, slip)
        per_cost[f"{slip:.0f}bp"] = m
        if slip == 1.0:
            primary_eq, primary_dts, primary_deq = eq, dts, deq
    corr_t, beta_t = _corr_beta(primary_dts, primary_eq, c[i0:, 1])
    corr_q, beta_q = _corr_beta(primary_dts, primary_eq, c[i0:, 0])
    out["primary"] = {
        "id": "G1",
        "params": {"fomc_window": [3, 20], "hold_sessions": 18},
        "dev": per_cost,
        "corr_tqqq_daily": corr_t,
        "beta_tqqq_daily": beta_t,
        "corr_qqq_daily": corr_q,
        "beta_qqq_daily": beta_q,
    }
    # leaderboard compatibility
    out["windows"] = {"dev": per_cost}
    out["dev_1bp"] = per_cost["1bp"]
    out["exposure"] = per_cost["1bp"]["exposure"]
    out["corr_vs_tqqq"] = corr_t
    out["corr_vs_qqq"] = corr_q
    out["yearly"] = per_cost["1bp"]["yearly"]

    # --- pre-registered grid (8 cells) ----------------------------------
    def cell_windows(fomc_off=(3, 20), extras=()):
        wins = event_windows(sess, day_of, FOMC_DATES, fomc_off[0], fomc_off[1])
        for ev, a, b in extras:
            wins += event_windows(sess, day_of, ev, a, b)
        return wins

    grid_defs = [
        ("G1", (3, 20), (), "primary: middle of the intermeeting period"),
        ("G2", (1, 15), (), "early phase, shorter"),
        ("G3", (3, 15), (), "shorter middle"),
        ("G4", (3, 25), (), "longer middle, includes late pre-meeting"),
        ("G5", (5, 20), (), "later start, more unwind skipped"),
        ("G6", (3, 20), ((CPI_DATES, -1, 2),), "FOMC window + CPI [-1,+2]"),
        ("G7", (3, 20), ((OPEX_DATES, 1, 3),), "FOMC window + OpEx [+1,+3]"),
        ("G8", (3, 20), ((CPI_DATES, -1, 2), (OPEX_DATES, 1, 3)),
         "FOMC + CPI + OpEx"),
    ]
    grid = {}
    for cid, fomc_off, extras, note in grid_defs:
        wins = cell_windows(fomc_off, extras)
        w = weights_from_index_windows(ts, wins)
        m, _, _, _ = _metrics(ts, o, c, w, 1.0)
        rec = {"note": note, "fomc_off": list(fomc_off),
               "extras": [[e.__class__.__name__, a, b] for e, a, b in extras],
               "windows": len(wins), "dev_1bp": m}
        if cid in ("G1", "G7", "G8"):
            for slip in (5.0, 10.0):
                mm, _, _, _ = _metrics(ts, o, c, w, slip)
                rec[f"dev_{slip:.0f}bp"] = mm
        grid[cid] = rec
        print(f"  {cid}: CAGR {m['cagr']*100:6.2f}%  DD {m['max_drawdown']*100:5.2f}%  "
              f"Sh {m['sharpe']:4.2f}  exp {m['exposure']*100:4.1f}%  nwin {len(wins)}")
    out["grid"] = grid

    # --- random-date placebo --------------------------------------------
    rng = np.random.default_rng(11)
    n_ev, hold = len(FOMC_DATES), 18
    draws = 500
    pres = []
    for _ in range(draws):
        starts = rng.integers(0, max(1, n_sess - hold), n_ev)
        wins = [(int(s), int(min(s + hold - 1, n_sess - 1))) for s in starts]
        w = weights_from_index_windows(ts, wins)
        m, _, _, _ = _metrics(ts, o, c, w, 1.0)
        pres.append((m["cagr"], m["max_drawdown"], m["sharpe"], m["exposure"]))
    pres = np.asarray(pres)
    p = per_cost["1bp"]
    out["placebo"] = {
        "draws": draws,
        "n_events": n_ev,
        "hold_sessions": hold,
        "seed": 11,
        "note": "random start sessions, same event count and hold length; overlaps allowed",
        "cagr": {"median": float(np.median(pres[:, 0])),
                 "p90": float(np.percentile(pres[:, 0], 90)),
                 "p95": float(np.percentile(pres[:, 0], 95)),
                 "p99": float(np.percentile(pres[:, 0], 99)),
                 "max": float(pres[:, 0].max()),
                 "percentile_of_primary": float((pres[:, 0] < p["cagr"]).mean())},
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
        "joint_frac_cagr_ge_and_dd_le": float(np.mean(
            (pres[:, 0] >= p["cagr"]) & (pres[:, 1] <= p["max_drawdown"]))),
    }

    # Exposure-matched placebo: a generic 30-session cycle with a random phase.
    # 63 non-overlapping 18-session windows -> roughly the same time in market.
    phase_res = []
    for phase in range(30):
        wins, s = [], phase
        while len(wins) < n_ev and s + hold - 1 < n_sess:
            wins.append((s, s + hold - 1))
            s += 30
        w = weights_from_index_windows(ts, wins)
        m, _, _, _ = _metrics(ts, o, c, w, 1.0)
        phase_res.append((m["cagr"], m["max_drawdown"], m["sharpe"], m["exposure"]))
    phase_res = np.asarray(phase_res)
    out["placebo_phase"] = {
        "note": "generic 30-session cycle, random phase, 63 non-overlapping 18-session "
                "windows; same frequency and roughly the same exposure as the primary",
        "phases": 30,
        "exposure_median": float(np.median(phase_res[:, 3])),
        "cagr": {"median": float(np.median(phase_res[:, 0])),
                 "p90": float(np.percentile(phase_res[:, 0], 90)),
                 "p95": float(np.percentile(phase_res[:, 0], 95)),
                 "max": float(phase_res[:, 0].max()),
                 "percentile_of_primary": float((phase_res[:, 0] < p["cagr"]).mean())},
        "max_drawdown": {"median": float(np.median(phase_res[:, 1])),
                         "p05": float(np.percentile(phase_res[:, 1], 5)),
                         "min": float(phase_res[:, 1].min()),
                         "percentile_of_primary": float((phase_res[:, 1] > p["max_drawdown"]).mean())},
        "sharpe": {"median": float(np.median(phase_res[:, 2])),
                   "p95": float(np.percentile(phase_res[:, 2], 95)),
                   "max": float(phase_res[:, 2].max()),
                   "percentile_of_primary": float((phase_res[:, 2] < p["sharpe"]).mean())},
        "joint_frac_cagr_ge_and_dd_le": float(np.mean(
            (phase_res[:, 0] >= p["cagr"]) & (phase_res[:, 1] <= p["max_drawdown"]))),
    }
    print(f"  phase placebo: CAGR p50 {out['placebo_phase']['cagr']['median']*100:5.1f}%  "
          f"p95 {out['placebo_phase']['cagr']['p95']*100:5.1f}%  primary pct "
          f"{out['placebo_phase']['cagr']['percentile_of_primary']*100:4.1f}%")
    print(f"  placebo: CAGR p50 {out['placebo']['cagr']['median']*100:5.1f}%  "
          f"p95 {out['placebo']['cagr']['p95']*100:5.1f}%  primary pct "
          f"{out['placebo']['cagr']['percentile_of_primary']*100:4.1f}%")

    # --- shifted calendar ------------------------------------------------
    shift_rows = {}
    for shift in range(-15, 16):
        wins = []
        for k in fomc_idx:
            ka, kb = k + shift + 3, k + shift + 20
            if ka < 0 or kb >= n_sess:
                continue
            wins.append((ka, kb))
        w = weights_from_index_windows(ts, wins)
        m, _, _, _ = _metrics(ts, o, c, w, 1.0)
        shift_rows[str(shift)] = {"cagr": m["cagr"], "max_drawdown": m["max_drawdown"],
                                  "sharpe": m["sharpe"], "exposure": m["exposure"]}
    out["shift_test"] = {
        "note": "all FOMC dates shifted by N sessions; same 18-session hold",
        "by_shift": shift_rows,
        "peak_shift": max(shift_rows, key=lambda s: shift_rows[s]["cagr"]),
    }

    # --- cuts ------------------------------------------------------------
    cuts = {}
    for lab, a, b in (("2016-2019", date(2016, 1, 4), date(2019, 12, 31)),
                      ("2020-2021", date(2020, 1, 2), date(2021, 12, 31)),
                      ("2022-2023", date(2022, 1, 3), date(2023, 12, 29))):
        cuts[lab] = _slice(ts, o, c, w_primary, a, b)
    out["cuts"] = {"subperiods": cuts}

    ylogs = _year_logs(primary_deq)
    tot = float(np.log(primary_deq.iloc[-1] / primary_deq.iloc[0]))
    loo = {}
    for y, lg in ylogs.items():
        loo[str(y)] = {"year_return": float(np.exp(lg) - 1.0),
                       "ex_cagr": float(np.exp((tot - lg) / 7.0) - 1.0)}
    out["cuts"]["leave_one_year_out"] = loo

    # --- per-cycle event study ------------------------------------------
    cyc = []
    for k in fomc_idx:
        ka, kb = k + 3, k + 20
        if kb >= n_sess:
            continue
        _, first, last, _, _ = _sessions(ts)
        ia, ib = first[ka], last[kb]
        cyc.append({
            "fomc": str(sess[k]),
            "start": str(sess[ka]),
            "end": str(sess[kb]),
            "tqqq": float(c[ib, 1] / o[ia, 1] - 1.0),
            "qqq": float(c[ib, 0] / o[ia, 0] - 1.0),
            "held_sessions": int(kb - ka + 1),
        })
    tx = np.array([r["tqqq"] for r in cyc])
    qx = np.array([r["qqq"] for r in cyc])
    out["event_study"] = {
        "n_cycles": len(cyc),
        "tqqq": {"mean": float(tx.mean()), "median": float(np.median(tx)),
                 "sd": float(tx.std(ddof=1)),
                 "t": float(tx.mean() / (tx.std(ddof=1) / np.sqrt(len(tx)))),
                 "positive_share": float((tx > 0).mean()),
                 "worst": sorted(cyc, key=lambda r: r["tqqq"])[:5],
                 "best": sorted(cyc, key=lambda r: r["tqqq"])[-5:]},
        "qqq": {"mean": float(qx.mean()), "median": float(np.median(qx)),
                "sd": float(qx.std(ddof=1)),
                "t": float(qx.mean() / (qx.std(ddof=1) / np.sqrt(len(qx)))),
                "positive_share": float((qx > 0).mean())},
    }

    # --- MArch 2020 cancelled-meeting sensitivity ------------------------
    extra = FOMC_DATES + [date(2020, 3, 18)]
    w_alt = weights_from_index_windows(
        ts, event_windows(sess, day_of, extra, 3, 20))
    m_alt, _, _, _ = _metrics(ts, o, c, w_alt, 1.0)
    out["sensitivity_cancelled_mar2020"] = {
        "note": "adds the cancelled 2020-03-18 scheduled date; not used by the primary",
        "dev_1bp": m_alt,
    }

    # --- status ----------------------------------------------------------
    passed = (p["cagr"] > TQQQ_BAR["cagr"]
              and p["max_drawdown"] < TQQQ_BAR["max_drawdown"])
    out["passed_dev_bar"] = bool(passed)
    out["status"] = "passed_dev_only" if passed else "below_dev_bar"
    out["status_note"] = (
        "Development gates only.  The pass is concentrated in 2020 and the "
        "leave-one-year-out ex-2020 CAGR is below the bar; see report.md.  "
        "No holdout was loaded."
    )
    out["notes"] = [
        "TQQQ benchmark recomputed on the same 1-min panel is 36.15% / 82.29% / 0.80; "
        "the program bar is the published 36.72% / 82.29% / 0.82.",
        f"FOMC events: {len(FOMC_DATES)} scheduled, {len(fomc_idx)} in panel, "
        f"{out['event_count']['windows_used']} windows used.",
        "2020 March scheduled meeting was cancelled; emergency meetings are excluded "
        "because they were not knowable in advance.",
        "The +3/+20 boundaries came from a coarse dev offset scan, disclosed in "
        "report.md; the grid is a plateau test, not a selection menu.",
    ]

    (HERE / "result.json").write_text(json.dumps(out, indent=2, default=float),
                                      encoding="utf-8")
    print(f"\nwrote {HERE / 'result.json'}")
    print(f"primary 1bp: CAGR {p['cagr']*100:.2f}%  DD {p['max_drawdown']*100:.2f}%  "
          f"Sharpe {p['sharpe']:.2f}  exposure {p['exposure']*100:.1f}%  "
          f"corr {corr_t:.2f}  fills {p['fills']}  turnover {p['turnover']:.0f}x")


if __name__ == "__main__":
    main()
