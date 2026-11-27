"""Crash early-warning overlay on TQQQ.

Default: 100% TQQQ.  De-risk to BIL when a composite of

  A) realised-volatility acceleration,
  B) drawdown acceleration, and
  C) overnight gap stress

confirms that a pullback is deepening (score >= 2 with B mandatory).
Re-enter on a 10-day closing high.  No moving-average gate, no stop-loss.

Development window only: 2016-01-04 .. 2023-12-29.
The 2024-2026 holdout is never loaded by this file.

Run from the repository root:

    python research/new/crash-early-warning/strategy.py

It writes result.json next to this file.  Fills are delegated to
research/bt.py (next-open, 2% band, slippage on traded notional).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

START = "2016-01-04"
END = "2023-12-29"
SYMBOLS = ("QQQ", "TQQQ", "BIL")

TQQQ = np.array([0.0, 1.0, 0.0])
BIL = np.array([0.0, 0.0, 1.0])
QQQ = np.array([1.0, 0.0, 0.0])

# Exact pre-registered core.  Every key is overridable for the grid.
PARAMS = dict(
    va_t=1.40,          # RV5 / RV20 threshold
    vol_floor=0.18,     # RV5 must also be at least 18% annualised
    dd_t=-0.05,         # QQQ 60-day drawdown threshold
    dd_acc=-0.02,       # 5-day drawdown velocity threshold
    gap_t=1.60,         # |gap|_3 / |gap|_20 threshold
    gap3_t=-0.015,      # 3-day cumulative log gap threshold
    enter=2,            # score >= enter ...
    require_b=True,     # ... and B (drawdown acceleration) is mandatory
    reentry=10,         # re-enter on the prior N-day closing high
    defensive="BIL",    # BIL, QQQ or MIX
    min_periods=10,     # no pre-2016 data exists; start signals after 10 sessions
)

BARS_PER_YEAR_1M = 252 * 390
START_EQUITY = 100_000.0


# ---------------------------------------------------------------------------
# signal construction
# ---------------------------------------------------------------------------
def _daily_bars(ts, o, c):
    """Aggregate a daily or 1-minute panel to session opens/closes."""
    dates, first, last = bt.day_bounds(ts)
    return dates, o[first], c[last], first, last


def _rolling_std(x, window, min_periods):
    return (
        pd.Series(x).rolling(window, min_periods=min_periods).std().to_numpy()
        * np.sqrt(252.0)
    )


def _features(daily_open, daily_close, p):
    """Causal daily features from QQQ only.  All inputs are through close t."""
    qo = daily_open[:, 0]
    qc = daily_close[:, 0]
    n = len(qc)

    r = np.diff(np.log(qc), prepend=np.log(qc[0]))
    rv5 = _rolling_std(r, 5, 5)
    rv20 = _rolling_std(r, 20, p["min_periods"])
    va = rv5 / rv20

    hi60 = pd.Series(qc).rolling(60, min_periods=p["min_periods"]).max().to_numpy()
    dd60 = qc / hi60 - 1.0
    dd5 = dd60 - pd.Series(dd60).shift(5).to_numpy()

    prev_close = np.r_[qc[0], qc[:-1]]
    gap = qo / prev_close - 1.0
    gabs3 = pd.Series(np.abs(gap)).rolling(3, min_periods=2).mean().to_numpy()
    gabs20 = (
        pd.Series(np.abs(gap))
        .rolling(20, min_periods=p["min_periods"])
        .mean()
        .to_numpy()
    )
    gs = gabs3 / gabs20
    gap3 = (
        pd.Series(np.log(qo / prev_close))
        .rolling(3, min_periods=2)
        .sum()
        .to_numpy()
    )

    hi_reentry = (
        pd.Series(qc).rolling(p["reentry"]).max().shift(1).to_numpy()
    )

    A = (va > p["va_t"]) & (rv5 > p["vol_floor"])
    B = (dd60 < p["dd_t"]) & (dd5 < p["dd_acc"])
    C = (gs > p["gap_t"]) | (gap3 < p["gap3_t"])
    # NaN comparisons are False; be explicit for older numpy/pandas.
    A = np.nan_to_num(A.astype(float)).astype(bool)
    B = np.nan_to_num(B.astype(float)).astype(bool)
    C = np.nan_to_num(C.astype(float)).astype(bool)
    score = A.astype(np.int8) + B.astype(np.int8) + C.astype(np.int8)
    return qc, score, B, hi_reentry


def _daily_targets(daily_open, daily_close, p):
    """Target weights set at each session close (executed next open)."""
    qc, score, B, hi = _features(daily_open, daily_close, p)
    n = len(qc)
    wd = np.zeros((n, 3))
    off = False
    for t in range(n):
        if not off:
            if score[t] >= p["enter"] and (bool(B[t]) if p["require_b"] else True):
                off = True
        else:
            if np.isfinite(hi[t]) and qc[t] >= hi[t]:
                off = False
        if off:
            wd[t] = QQQ if p["defensive"] == "QQQ" else (
                BIL if p["defensive"] == "BIL" else np.array([0.5, 0.0, 0.5])
            )
        else:
            wd[t] = TQQQ
    return wd, off


def build_weights(ts, o, c, params=None):
    """Build the (n, 3) target-weight matrix for a daily or 1-minute panel.

    `weights[i]` is the target set from bar i's close and is executed at
    bar i+1's open by bt.simulate.  For a 1-minute panel the session-close
    decision is written on the 15:59 bar, so it fills at the next 09:30
    open; every other bar in a session carries the position already held.
    """
    p = dict(PARAMS)
    if params:
        p.update(params)
    dates, do, dc, first, last = _daily_bars(ts, o, c)
    wd, off = _daily_targets(do, dc, p)
    n = len(ts)
    if len(first) == n:  # daily panel: one bar per session
        return wd

    w = np.empty((n, 3))
    for d in range(len(first)):
        prev = wd[d - 1] if d > 0 else TQQQ
        w[first[d] : last[d] + 1] = prev
        # The close-of-session decision lives on the last bar and fills at
        # the next session's open.
        w[last[d]] = wd[d]
    return w


# ---------------------------------------------------------------------------
# metrics
# ---------------------------------------------------------------------------
def _yearly(eq, bench, ts):
    """Calendar-year returns, year-end to year-end from the first bar."""
    es = pd.Series(eq, index=ts)
    bs = pd.Series(bench, index=ts)
    ye = es.groupby(ts.date).last()
    yb = bs.groupby(ts.date).last()
    y0 = pd.Series(ye.values, index=pd.to_datetime(ye.index)).groupby(lambda x: x.year).last()
    b0 = pd.Series(yb.values, index=pd.to_datetime(yb.index)).groupby(lambda x: x.year).last()
    out = {}
    years = list(y0.index)
    first_bench = float(bench[0])
    for k, y in enumerate(years):
        base = START_EQUITY if k == 0 else float(y0[years[k - 1]])
        bbase = first_bench if k == 0 else float(b0[years[k - 1]])
        out[int(y)] = {
            "strategy": float(y0[y] / base - 1.0),
            "benchmark": float(b0[y] / bbase - 1.0),
        }
    return out


def _metrics(ts, o, c, w, cost_bps, bars_per_year, start=START):
    res = bt.run(ts, o, c, w, start, band=0.02, slippage_bps=cost_bps)
    st = bt.stats(res, bars_per_year)
    i = bt.start_index(ts, start)
    b = bt.benchmark(c[i:, 1], ts[i:], bars_per_year)
    eq = res["equity"]
    rr = np.diff(eq) / eq[:-1]
    rt = np.diff(c[i:, 1]) / c[i:-1, 1]
    corr_bar = float(np.corrcoef(rr, rt)[0, 1]) if len(rr) > 2 else float("nan")

    es = pd.Series(eq, index=ts[i:])
    de = es.groupby(ts[i:].date).last().pct_change().dropna()
    dt = pd.Series(c[i:, 1], index=ts[i:]).groupby(ts[i:].date).last().pct_change().dropna()
    corr_daily = float(de.corr(dt)) if len(de) > 2 else float("nan")

    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    j = int(np.argmin(dd))
    pk = int(np.argmax(eq[: j + 1]))

    ww = w[i:]
    return {
        "cost_bps": float(cost_bps),
        "cagr": float(st["cagr"]),
        "total_return": float(st["total_return"]),
        "max_drawdown": float(st["max_drawdown"]),
        "sharpe": float(st["sharpe"]),
        "sortino": float(st["sortino"]),
        "volatility": float(st["volatility"]),
        "exposure_any_asset": float(st["exposure"]),
        "tqqq_weight_avg": float(ww[:, 1].mean()),
        "time_in_tqqq": float((ww[:, 1] > 0.5).mean()),
        "time_in_bil": float((ww[:, 2] > 0.5).mean()),
        "fills": int(st["fills"]),
        "turnover_x_start_equity": float(st["turnover"]),
        "ending_equity": float(st["ending_equity"]),
        "corr_tqqq_bar": corr_bar,
        "corr_tqqq_daily": corr_daily,
        "max_dd_peak": str(pd.Timestamp(ts[i + pk]).date()),
        "max_dd_trough": str(pd.Timestamp(ts[i + j]).date()),
        "benchmark": {
            "cagr": float(b["cagr"]),
            "max_drawdown": float(b["max_drawdown"]),
            "sharpe": float(b["sharpe"]),
            "volatility": float(b["volatility"]),
        },
        "yearly": _yearly(eq, c[i:, 1], ts[i:]),
        "_equity": eq,
        "_bench": c[i:, 1],
        "_dates": ts[i:],
    }


def _public(m):
    return {k: v for k, v in m.items() if not k.startswith("_")}


def _episodes(ts, eq, bench, episodes):
    out = []
    for a, b in episodes:
        m = (ts >= pd.Timestamp(a, tz="America/New_York")) & (
            ts <= pd.Timestamp(b, tz="America/New_York")
        )
        e, t = eq[m], bench[m]
        if len(e) < 2:
            continue
        dd_e = float((e / np.maximum.accumulate(e) - 1.0).min())
        dd_t = float((t / np.maximum.accumulate(t) - 1.0).min())
        out.append(
            {
                "start": a,
                "end": b,
                "tqqq_max_dd": dd_t,
                "strategy_max_dd": dd_e,
                "avoided_dd_pp": 100.0 * (dd_e - dd_t),
                "tqqq_return": float(t[-1] / t[0] - 1.0),
                "strategy_return": float(e[-1] / e[0] - 1.0),
            }
        )
    return out


def _ex_year(m, drop_years):
    """Compound daily returns excluding calendar years, then recompute stats."""
    eq = m["_equity"]
    dates = m["_dates"]
    de = pd.Series(eq, index=dates).groupby(dates.date).last()
    dr = de.pct_change().dropna()
    keep = ~np.isin(pd.to_datetime(dr.index).year, list(drop_years))
    r = dr[keep].to_numpy()
    curve = START_EQUITY * np.cumprod(1.0 + r)
    years = len(r) / 252.0
    peak = np.maximum.accumulate(curve)
    return {
        "excluded_years": list(drop_years),
        "cagr": float((curve[-1] / START_EQUITY) ** (1.0 / years) - 1.0),
        "max_drawdown": float(-(curve / peak - 1.0).min()),
        "sharpe": float(np.mean(r) / np.std(r, ddof=0) * np.sqrt(252.0)),
        "n_days": int(len(r)),
    }


# ---------------------------------------------------------------------------
# diagnostics
# ---------------------------------------------------------------------------
def _daily_weights_from_off(off):
    w = np.zeros((len(off), 3))
    w[off, 2] = 1.0
    w[~off, 1] = 1.0
    return w


def _daily_weights_from_condition(cond, hi, qc, defensive=BIL):
    n = len(qc)
    w = np.zeros((n, 3))
    off = False
    for t in range(n):
        if (not off) and bool(cond[t]):
            off = True
        elif off and np.isfinite(hi[t]) and qc[t] >= hi[t]:
            off = False
        w[t] = defensive if off else TQQQ
    return w


def _run_daily(ts, o, c, w, cost=1.0):
    res = bt.run(ts, o, c, w, START, band=0.02, slippage_bps=cost)
    return bt.stats(res, 252)


def _grid(ts, o, c):
    cells = [
        ("core", {}),
        ("vol_lo_1.20", {"va_t": 1.20}),
        ("vol_hi_1.60", {"va_t": 1.60}),
        ("dd_early_-4.0", {"dd_t": -0.04}),
        ("dd_late_-7.0", {"dd_t": -0.07}),
        ("gap_lo_1.40", {"gap_t": 1.40}),
        ("gap_hi_2.00", {"gap_t": 2.00}),
        ("gap3_lo_-1.0", {"gap3_t": -0.010}),
    ]
    out = []
    for name, over in cells:
        w = build_weights(ts, o, c, over)
        st = _run_daily(ts, o, c, w)
        out.append(
            {
                "cell": name,
                "overrides": over,
                "cagr": float(st["cagr"]),
                "max_drawdown": float(st["max_drawdown"]),
                "sharpe": float(st["sharpe"]),
                "fills": int(st["fills"]),
                "time_in_tqqq": float((w[:, 1] > 0.5).mean()),
            }
        )
    return out


def _components(ts, o, c):
    p = PARAMS
    qc, score, B, hi = _features(
        o, c, p
    )  # o/c here are daily opens/closes
    # Recompute A and C from the feature definitions so each component can be
    # tested on its own with exactly the same thresholds.
    qo = o[:, 0]
    r = np.diff(np.log(qc), prepend=np.log(qc[0]))
    rv5 = _rolling_std(r, 5, 5)
    rv20 = _rolling_std(r, 20, p["min_periods"])
    va = rv5 / rv20
    hi60 = pd.Series(qc).rolling(60, min_periods=p["min_periods"]).max().to_numpy()
    dd60 = qc / hi60 - 1.0
    dd5 = dd60 - pd.Series(dd60).shift(5).to_numpy()
    prev_close = np.r_[qc[0], qc[:-1]]
    gap = qo / prev_close - 1.0
    gabs3 = pd.Series(np.abs(gap)).rolling(3, min_periods=2).mean().to_numpy()
    gabs20 = pd.Series(np.abs(gap)).rolling(20, min_periods=p["min_periods"]).mean().to_numpy()
    gs = gabs3 / gabs20
    gap3 = pd.Series(np.log(qo / prev_close)).rolling(3, min_periods=2).sum().to_numpy()
    A = np.nan_to_num(((va > p["va_t"]) & (rv5 > p["vol_floor"])).astype(float)).astype(bool)
    B = np.nan_to_num(((dd60 < p["dd_t"]) & (dd5 < p["dd_acc"])).astype(float)).astype(bool)
    C = np.nan_to_num(((gs > p["gap_t"]) | (gap3 < p["gap3_t"])).astype(float)).astype(bool)
    s = A.astype(np.int8) + B.astype(np.int8) + C.astype(np.int8)

    conds = {
        "A_vol_only": A,
        "B_dd_only": B,
        "C_gap_only": C,
        "A_and_B": A & B,
        "A_and_C": A & C,
        "B_and_C": B & C,
        "score3_unanimous": s >= 3,
        "score2_no_B_gate": s >= 2,
        "core_score2_plus_B": (s >= 2) & B,
    }
    out = []
    for name, cond in conds.items():
        w = _daily_weights_from_condition(cond, hi, qc)
        st = _run_daily(ts, o, c, w)
        out.append(
            {
                "rule": name,
                "cagr": float(st["cagr"]),
                "max_drawdown": float(st["max_drawdown"]),
                "sharpe": float(st["sharpe"]),
                "fills": int(st["fills"]),
                "time_in_tqqq": float((w[:, 1] > 0.5).mean()),
            }
        )
    return out


def _reentry_horizons(ts, o, c):
    out = []
    for n in (10, 15, 20):
        w = build_weights(ts, o, c, {"reentry": n})
        st = _run_daily(ts, o, c, w)
        out.append(
            {
                "reentry_days": n,
                "cagr": float(st["cagr"]),
                "max_drawdown": float(st["max_drawdown"]),
                "sharpe": float(st["sharpe"]),
                "fills": int(st["fills"]),
                "time_in_tqqq": float((w[:, 1] > 0.5).mean()),
            }
        )
    return out


def _placebo(ts, o, c, w, n_draws=500, seed=20261127):
    off = w[:, 2] > 0.5
    n = len(off)
    rng = np.random.default_rng(seed)
    cagr, dd, sharpe = [], [], []
    for _ in range(n_draws):
        shift = int(rng.integers(20, n - 20))
        oo = np.roll(off, shift)
        ww = _daily_weights_from_off(oo)
        st = _run_daily(ts, o, c, ww)
        cagr.append(st["cagr"])
        dd.append(st["max_drawdown"])
        sharpe.append(st["sharpe"])
    core = _run_daily(ts, o, c, w)
    arr_c = np.array(cagr)
    arr_d = np.array(dd)
    arr_s = np.array(sharpe)
    return {
        "n_draws": n_draws,
        "method": "circular shift of the defensive-day vector; preserves spell lengths and exposure",
        "observed": {
            "cagr": float(core["cagr"]),
            "max_drawdown": float(core["max_drawdown"]),
            "sharpe": float(core["sharpe"]),
        },
        "placebo": {
            "cagr_mean": float(arr_c.mean()),
            "cagr_p05": float(np.percentile(arr_c, 5)),
            "cagr_p95": float(np.percentile(arr_c, 95)),
            "dd_mean": float(arr_d.mean()),
            "dd_p05": float(np.percentile(arr_d, 5)),
            "dd_p95": float(np.percentile(arr_d, 95)),
            "sharpe_mean": float(arr_s.mean()),
            "sharpe_p95": float(np.percentile(arr_s, 95)),
        },
        "observed_percentile": {
            "cagr": float(100.0 * np.mean(arr_c < core["cagr"])),
            "max_drawdown": float(100.0 * np.mean(arr_d < core["max_drawdown"])),
            "sharpe": float(100.0 * np.mean(arr_s < core["sharpe"])),
        },
        "share_placebo_cagr_above_bar": float(100.0 * np.mean(arr_c > 0.3672)),
        "share_placebo_dd_below_60pct": float(100.0 * np.mean(arr_d < 0.60)),
    }


def _spell_stats(daily_open, daily_close, w):
    """Descriptive attribution of the defensive spells (daily marks).

    The TQQQ move is measured from the entry fill (next open after the
    decision close) to the exit fill (next open after the re-entry close),
    i.e. the return actually held in BIL.
    """
    o = daily_open[:, 1]
    c = daily_close[:, 1]
    off = w[:, 2] > 0.5
    n = len(off)
    starts = np.flatnonzero(np.diff(off.astype(np.int8)) == 1) + 1
    ends = np.flatnonzero(np.diff(off.astype(np.int8)) == -1)
    lens, moves = [], []
    for s in starts:
        e = ends[ends > s]
        entry = min(int(s) + 1, n - 1)
        if len(e) == 0:
            exit_px = c[-1]
            length = n - 1 - int(s)
        else:
            e = int(e[0])
            exit_px = o[min(e + 1, n - 1)]
            length = e - int(s) + 1
        lens.append(int(length))
        moves.append(float(exit_px / o[entry] - 1.0))
    moves = np.array(moves)
    return {
        "n_spells": int(len(lens)),
        "median_length_sessions": float(np.median(lens)) if lens else None,
        "mean_length_sessions": float(np.mean(lens)) if lens else None,
        "max_length_sessions": int(np.max(lens)) if lens else None,
        "share_spells_tqqq_up": float(np.mean(moves > 0)) if len(moves) else None,
        "mean_tqqq_move_down_spells": float(np.mean(moves[moves < 0])) if np.any(moves < 0) else None,
        "mean_tqqq_move_up_spells": float(np.mean(moves[moves > 0])) if np.any(moves > 0) else None,
        "total_sessions_defensive": int(off.sum()),
        "share_sessions_defensive": float(off.mean()),
    }


def _event_study(daily_close, daily_open):
    """Conditional forward returns of the warning state (analysis only)."""
    qc, score, B, _ = _features(daily_open, daily_close, PARAMS)
    n = len(qc)
    r = np.diff(np.log(qc), prepend=np.log(qc[0]))
    rv5 = _rolling_std(r, 5, 5)
    fwd10 = np.full(n, np.nan)
    fwd10[:-10] = qc[10:] / qc[:-10] - 1.0
    high = (score >= 2) & B
    ok = np.isfinite(fwd10)
    return {
        "warning_days": int(high.sum()),
        "warning_share": float(high.mean()),
        "fwd10_tqqq_mean_warning": float(np.nanmean(fwd10[high & ok])),
        "fwd10_tqqq_mean_other": float(np.nanmean(fwd10[~high & ok])),
        "fwd10_tqqq_negative_share_warning": float(np.nanmean(fwd10[high & ok] < 0)),
        "fwd10_tqqq_negative_share_other": float(np.nanmean(fwd10[~high & ok] < 0)),
        "rv5_autocorr_lag1": float(pd.Series(rv5).autocorr(1)),
        "rv5_mean_warning": float(np.nanmean(rv5[high])),
        "rv5_mean_all": float(np.nanmean(rv5)),
    }


def _cut_tests(ts, o, c, w, cuts):
    """Rebuild weights on data truncated at a session close; compare prefixes."""
    out = {}
    for cut in cuts:
        stamp = pd.Timestamp(cut, tz="America/New_York").replace(hour=15, minute=59)
        j = int(ts.searchsorted(stamp, side="right"))
        if j <= 0 or j >= len(ts):
            out[cut] = {"error": "cut outside panel"}
            continue
        wt = build_weights(ts[:j], o[:j], c[:j])
        m = min(len(wt), j)
        diff = np.flatnonzero((w[:m, 1] != wt[:m, 1]) | (w[:m, 2] != wt[:m, 2]))
        out[cut] = {
            "bars_compared": int(m),
            "weight_differences": int(len(diff)),
            "first_difference_bar": int(diff[0]) if len(diff) else None,
            "identical": bool(len(diff) == 0),
        }
    return out


# ---------------------------------------------------------------------------
def main():
    print("loading 1-minute panel (dev window only) ...")
    ts, o, c = bt.panel(SYMBOLS, START, END, "1min", warmup_days=0)
    print(f"  {len(ts):,} bars  {ts[0]} -> {ts[-1]}")
    w = build_weights(ts, o, c)

    results = {}
    for cost in (1.0, 5.0, 10.0):
        m = _metrics(ts, o, c, w, cost, BARS_PER_YEAR_1M)
        results[f"{int(cost)}bp"] = _public(m)
        print(
            f"  {cost:4.1f} bp: CAGR {m['cagr']*100:6.2f}%  DD {m['max_drawdown']*100:5.2f}%  "
            f"Sharpe {m['sharpe']:4.2f}  fills {m['fills']}  tqqq {m['tqqq_weight_avg']*100:.1f}%"
        )
    core1m = _metrics(ts, o, c, w, 1.0, BARS_PER_YEAR_1M)
    core_public = results["1bp"]

    # Conservative neighbour: same signal, slower 15-day-high re-entry.
    # Reported alongside the pre-registered 10-day core, not substituted for it.
    w15 = build_weights(ts, o, c, {"reentry": 15})
    variant = {}
    variant_m1 = None
    for cost in (1.0, 5.0, 10.0):
        m15 = _metrics(ts, o, c, w15, cost, BARS_PER_YEAR_1M)
        variant[f"{int(cost)}bp"] = _public(m15)
        if cost == 1.0:
            variant_m1 = m15
    variant_ex2020 = _ex_year(variant_m1, [2020])

    episode_list = [
        ("2018-08-30", "2018-12-24"),
        ("2020-02-20", "2020-03-20"),
        ("2021-11-22", "2022-12-28"),
    ]
    episodes = _episodes(core1m["_dates"], core1m["_equity"], core1m["_bench"], episode_list)

    print("daily panel for the grid / diagnostics ...")
    tsd, od, cd = bt.panel(SYMBOLS, START, END, "1D", warmup_days=500)
    i = bt.start_index(tsd, START)
    tsD, oD, cD = tsd[i:], od[i:], cd[i:]
    wD = build_weights(tsD, oD, cD)
    daily_core = _run_daily(tsD, oD, cD, wD)

    grid = _grid(tsD, oD, cD)
    components = _components(tsD, oD, cD)
    reentry = _reentry_horizons(tsD, oD, cD)
    placebo = _placebo(tsD, oD, cD, wD, n_draws=500)
    cuts = _cut_tests(ts, o, c, w, ["2018-12-24", "2020-03-12", "2022-09-13"])
    spells = _spell_stats(oD, cD, wD)
    event = _event_study(cD, oD)

    ex2020 = _ex_year(core1m, [2020])
    ex2022 = _ex_year(core1m, [2022])
    ex_both = _ex_year(core1m, [2020, 2022])

    bar = 0.3672
    dd_bar = 0.8229
    verdict = {
        "dev_1bp_cagr": core_public["cagr"],
        "dev_1bp_max_drawdown": core_public["max_drawdown"],
        "dev_1bp_sharpe": core_public["sharpe"],
        "bar_cagr": bar,
        "bar_max_drawdown": dd_bar,
        "beats_cagr_bar": bool(core_public["cagr"] > bar),
        "beats_dd_bar": bool(core_public["max_drawdown"] < dd_bar),
        "dd_below_60pct": bool(core_public["max_drawdown"] < 0.60),
        "pass": bool(core_public["cagr"] > bar and core_public["max_drawdown"] < dd_bar),
        "beats_at_5bp": bool(results["5bp"]["cagr"] > bar and results["5bp"]["max_drawdown"] < dd_bar),
        "beats_at_10bp": bool(results["10bp"]["cagr"] > bar and results["10bp"]["max_drawdown"] < dd_bar),
    }

    payload = {
        "strategy": "crash-early-warning",
        "version": "1.0",
        "window": {
            "dev_start": START,
            "dev_end": END,
            "holdout_loaded": False,
            "bars": "1-minute regular session, next-open fills, 2% band",
        },
        "bar": {"cagr": bar, "max_drawdown": dd_bar, "sharpe": 0.82},
        "params": {k: v for k, v in PARAMS.items()},
        "headline_1m": results,
        "core_1m": core_public,
        "conservative_variant_1m": {
            "description": "same signal, 15-day-high re-entry instead of 10-day",
            "metrics": variant,
            "ex_2020": variant_ex2020,
        },
        "core_daily": {
            "cagr": float(daily_core["cagr"]),
            "max_drawdown": float(daily_core["max_drawdown"]),
            "sharpe": float(daily_core["sharpe"]),
            "fills": int(daily_core["fills"]),
            "time_in_tqqq": float((wD[:, 1] > 0.5).mean()),
        },
        "episodes_1m": episodes,
        "defensive_spells_daily": spells,
        "event_study_daily": event,
        "grid_daily": grid,
        "components_daily": components,
        "reentry_daily": reentry,
        "placebo_daily": placebo,
        "cut_tests_1m": cuts,
        "ex_year_1m": {"ex_2020": ex2020, "ex_2022": ex2022, "ex_2020_and_2022": ex_both},
        "verdict": verdict,
        "notes": [
            "Development window only. 2024-2026 is never used or inspected; every panel ends 2023-12-29.",
            "All signals use QQQ daily open/close through the decision close.",
            "First 10 sessions of 2016 are default TQQQ: the 1-minute archive starts 2016-01-04, so there is no warm-up history.",
            "Costs are 1/5/10 bp on traded notional; the 1 bp run is the headline.",
        ],
    }

    out_path = HERE / "result.json"
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
