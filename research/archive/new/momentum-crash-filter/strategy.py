"""Momentum with a crash brake on TQQQ.

Hold TQQQ while QQQ 20- or 60-session total-return momentum is positive.
Override to BIL when a fast drawdown from a 20-session high is confirmed by
either a 5/20-day volatility spike or a sharp 3-day loss.  Re-enter TQQQ on a
close at or above the prior 5-session high with positive 20-session momentum.

Development window only: 2016-01-04 .. 2023-12-29.
The 2024-2026 holdout is never loaded by this file.

Run from the repository root:

    python research/new/momentum-crash-filter/strategy.py

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
BARS_PER_YEAR_1M = 252 * 390
BARS_PER_YEAR_1D = 252
START_EQUITY = 100_000.0
BAR_CAGR = 0.3672
BAR_DD = 0.8229

# Frozen core.  Every key is overridable for the pre-registered grid.
PARAMS = dict(
    mom_fast=20,
    mom_slow=60,
    mom_buf=0.0,
    dd_win=20,
    dd_t=-0.08,
    va_t=1.50,
    loss_t=-0.06,
    reentry=5,
    re_mom=True,
    warm=max(20, 60),
    min_periods=20,
)


# ---------------------------------------------------------------------------
# signals
# ---------------------------------------------------------------------------
def _daily_bars(ts, o, c):
    """Aggregate a daily or 1-minute panel to session opens/closes."""
    dates, first, last = bt.day_bounds(ts)
    return dates, o[first], c[last], first, last


def _features(daily_close, p):
    """Causal daily features from QQQ closes through session t."""
    qc = daily_close[:, 0]
    n = len(qc)
    s = pd.Series(qc)
    r = np.diff(np.log(qc), prepend=np.log(qc[0]))

    rv5 = pd.Series(r).rolling(5, min_periods=5).std().to_numpy() * np.sqrt(252.0)
    rv20 = (
        pd.Series(r)
        .rolling(20, min_periods=p["min_periods"])
        .std()
        .to_numpy()
        * np.sqrt(252.0)
    )
    va = rv5 / rv20

    dd20 = qc / s.rolling(p["dd_win"], min_periods=p["dd_win"]).max().to_numpy() - 1.0
    r3 = pd.Series(np.log(qc)).diff(3).to_numpy()
    hi5 = s.rolling(p["reentry"], min_periods=p["reentry"]).max().shift(1).to_numpy()

    r20 = qc / s.shift(p["mom_fast"]).to_numpy() - 1.0
    r60 = qc / s.shift(p["mom_slow"]).to_numpy() - 1.0
    return qc, r20, r60, va, dd20, r3, hi5


def _daily_targets(daily_close, p):
    """State machine at session closes; weights execute at the next open."""
    qc, r20, r60, va, dd20, r3, hi5 = _features(daily_close, p)
    n = len(qc)
    crash = (dd20 < p["dd_t"]) & ((va > p["va_t"]) | (r3 < p["loss_t"]))
    crash = np.nan_to_num(crash.astype(float)).astype(bool)

    wd = np.zeros((n, 3))
    state = np.zeros(n, dtype=np.int8)
    trigger = np.zeros(n, dtype=np.int8)
    off = False
    for t in range(n):
        if off:
            reclaim = np.isfinite(hi5[t]) and qc[t] >= hi5[t]
            mom_ok = (not p["re_mom"]) or (np.isfinite(r20[t]) and r20[t] > 0)
            if reclaim and mom_ok:
                off = False
        elif crash[t]:
            off = True
            trigger[t] = 1
        momentum_on = (r20[t] > p["mom_buf"]) or (r60[t] > p["mom_buf"])
        if t < p["warm"]:
            momentum_on = True
        state[t] = 1 if (momentum_on and not off) else 0
        wd[t] = TQQQ if state[t] else BIL
    return wd, state, crash, trigger


def build_weights(ts, o, c, params=None):
    """Build the (n, 3) target-weight matrix for a daily or 1-minute panel.

    `weights[i]` is the target set from bar i's close and is executed at
    bar i+1's open by bt.simulate.  For a 1-minute panel the session-close
    decision is written on the 15:59 bar, so it fills at the next 09:30 open;
    every other bar in a session carries the position already held.
    """
    p = dict(PARAMS)
    if params:
        p.update(params)
    dates, do, dc, first, last = _daily_bars(ts, o, c)
    wd, state, crash, trigger = _daily_targets(dc, p)
    n = len(ts)
    if len(first) == n:  # daily panel: one bar per session
        return wd

    w = np.empty((n, 3))
    for d in range(len(first)):
        prev = wd[d - 1] if d > 0 else TQQQ
        w[first[d] : last[d] + 1] = prev
        w[last[d]] = wd[d]
    return w


# ---------------------------------------------------------------------------
# metrics
# ---------------------------------------------------------------------------
def _yearly(eq, bench, ts):
    """Calendar-year returns from the first bar of the slice."""
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


def _ex_year_bench(ts, bench, drop_years):
    de = pd.Series(bench, index=ts).groupby(ts.date).last()
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
    }


# ---------------------------------------------------------------------------
# diagnostics on daily marks
# ---------------------------------------------------------------------------
def _run_daily(ts, o, c, w, cost=1.0):
    res = bt.run(ts, o, c, w, START, band=0.02, slippage_bps=cost)
    return bt.stats(res, BARS_PER_YEAR_1D)


def _grid(ts, o, c):
    cells = [
        ("core", {}),
        ("dd_early_-6.0", {"dd_t": -0.06}),
        ("dd_late_-10.0", {"dd_t": -0.10}),
        ("vol_tight_1.80", {"va_t": 1.80}),
        ("loss_tight_-4.0", {"loss_t": -0.04}),
        ("loss_loose_-8.0", {"loss_t": -0.08}),
        ("reentry_fast_3", {"reentry": 3}),
        ("reentry_slow_7", {"reentry": 7}),
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


def _neighbours(ts, o, c):
    cells = [
        ("buf_-0.5", {"mom_buf": -0.005}),
        ("buf_-1.0", {"mom_buf": -0.01}),
        ("buf_-2.0", {"mom_buf": -0.02}),
        ("buf_+1.0", {"mom_buf": 0.01}),
        ("dd_win_15", {"dd_win": 15}),
        ("dd_win_30", {"dd_win": 30}),
        ("reentry_10", {"reentry": 10}),
        ("reentry_15", {"reentry": 15}),
        ("reentry_20", {"reentry": 20}),
        ("no_reentry_mom", {"re_mom": False}),
        ("no_crash", {"dd_t": -9.9}),
    ]
    out = []
    for name, over in cells:
        w = build_weights(ts, o, c, over)
        st = _run_daily(ts, o, c, w)
        out.append(
            {
                "variant": name,
                "overrides": over,
                "cagr": float(st["cagr"]),
                "max_drawdown": float(st["max_drawdown"]),
                "sharpe": float(st["sharpe"]),
                "fills": int(st["fills"]),
                "time_in_tqqq": float((w[:, 1] > 0.5).mean()),
            }
        )
    return out


def _component_weights(daily_close, p, use_mom, crash_mode, re_mom):
    """Component rules for attribution (daily marks)."""
    qc, r20, r60, va, dd20, r3, hi5 = _features(daily_close, p)
    n = len(qc)
    if crash_mode == "both":
        crash = (dd20 < p["dd_t"]) & ((va > p["va_t"]) | (r3 < p["loss_t"]))
    elif crash_mode == "dd_loss":
        crash = (dd20 < p["dd_t"]) & (r3 < p["loss_t"])
    elif crash_mode == "dd_vol":
        crash = (dd20 < p["dd_t"]) & (va > p["va_t"])
    elif crash_mode == "loss":
        crash = r3 < p["loss_t"]
    elif crash_mode == "vol":
        crash = va > p["va_t"]
    elif crash_mode == "none":
        crash = np.zeros(n, dtype=bool)
    else:
        raise ValueError(crash_mode)
    crash = np.nan_to_num(crash.astype(float)).astype(bool)

    w = np.zeros((n, 3))
    off = False
    for t in range(n):
        if off:
            reclaim = np.isfinite(hi5[t]) and qc[t] >= hi5[t]
            mom_ok = (not re_mom) or (np.isfinite(r20[t]) and r20[t] > 0)
            if reclaim and mom_ok:
                off = False
        elif crash[t]:
            off = True
        on = True
        if use_mom:
            on = (r20[t] > p["mom_buf"]) or (r60[t] > p["mom_buf"])
            if t < p["warm"]:
                on = True
        w[t] = TQQQ if (on and not off) else BIL
    return w


def _components(ts, o, c, daily_close):
    p = dict(PARAMS)
    cells = [
        ("momentum_only", True, "none", False),
        ("crash_only_re5", False, "both", False),
        ("crash_only_re5_mom", False, "both", True),
        ("dd_plus_loss", True, "dd_loss", True),
        ("dd_plus_vol", True, "dd_vol", True),
        ("loss_only", True, "loss", True),
        ("vol_only", True, "vol", True),
    ]
    out = []
    for name, use_mom, mode, re_mom in cells:
        w = _component_weights(daily_close, p, use_mom, mode, re_mom)
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


def _placebo(ts, o, c, w, n_draws=500, seed=20261127):
    state = (w[:, 1] > 0.5).astype(np.int8)
    n = len(state)
    rng = np.random.default_rng(seed)
    cagr, dd, sharpe = [], [], []
    for _ in range(n_draws):
        shift = int(rng.integers(20, n - 20))
        ss = np.roll(state, shift)
        ww = np.where(ss[:, None] == 1, TQQQ, BIL)
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
        "method": "circular shift of the full TQQQ/BIL state vector; preserves spell lengths and exposure",
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
        "share_placebo_cagr_above_bar": float(100.0 * np.mean(arr_c > BAR_CAGR)),
        "share_placebo_dd_below_60pct": float(100.0 * np.mean(arr_d < 0.60)),
        "share_placebo_joint_pass": float(
            100.0 * np.mean((arr_c > BAR_CAGR) & (arr_d < BAR_DD))
        ),
    }


def _cut_tests(ts, o, c, w, cuts):
    out = {}
    for cut in cuts:
        stamp = pd.Timestamp(cut, tz="America/New_York").replace(hour=15, minute=59)
        j = int(ts.searchsorted(stamp, side="right"))
        if j <= 0 or j >= len(ts):
            out[cut] = {"error": "cut outside panel"}
            continue
        wt = build_weights(ts[:j], o[:j], c[:j])
        m = min(len(wt), j)
        diff = np.flatnonzero(
            (w[:m, 1] != wt[:m, 1]) | (w[:m, 2] != wt[:m, 2])
        )
        out[cut] = {
            "bars_compared": int(m),
            "weight_differences": int(len(diff)),
            "first_difference_bar": int(diff[0]) if len(diff) else None,
            "identical": bool(len(diff) == 0),
        }
    return out


def _spell_stats(daily_open, daily_close, w):
    """Descriptive attribution of defensive spells on daily marks.

    `off` is set at the close of day t and filled at the next open, so the
    TQQQ move actually avoided runs from open[t+1] to open[exit+1].
    """
    o = daily_open[:, 1]
    off = w[:, 2] > 0.5
    n = len(off)
    starts = np.flatnonzero(np.diff(off.astype(np.int8)) == 1) + 1
    ends = np.flatnonzero(np.diff(off.astype(np.int8)) == -1)
    lens, moves = [], []
    for s in starts:
        cand = ends[ends >= s]
        entry = min(int(s) + 1, n - 1)
        if len(cand) == 0:
            exit_px = o[-1]
            length = n - int(s)
        else:
            e = int(cand[0])
            exit_px = o[min(e + 2, n - 1)]
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


def _event_study(daily_close, trigger):
    qc = daily_close[:, 0]
    n = len(qc)
    tc = daily_close[:, 1]
    tbool = np.asarray(trigger).astype(bool)
    fwd10 = np.full(n, np.nan)
    fwd10[:-10] = tc[10:] / tc[:-10] - 1.0
    fwd20 = np.full(n, np.nan)
    fwd20[:-20] = tc[20:] / tc[:-20] - 1.0
    ok10 = np.isfinite(fwd10)
    ok20 = np.isfinite(fwd20)
    return {
        "crash_triggers": int(tbool.sum()),
        "crash_share": float(tbool.mean()),
        "fwd10_tqqq_mean_after_crash": float(np.nanmean(fwd10[tbool & ok10])) if np.any(tbool & ok10) else None,
        "fwd10_tqqq_mean_all": float(np.nanmean(fwd10[ok10])),
        "fwd10_tqqq_negative_share_after_crash": float(np.nanmean(fwd10[tbool & ok10] < 0)) if np.any(tbool & ok10) else None,
        "fwd10_tqqq_negative_share_all": float(np.nanmean(fwd10[ok10] < 0)),
        "fwd10_tqqq_min_after_crash": float(np.nanmin(fwd10[tbool & ok10])) if np.any(tbool & ok10) else None,
        "fwd10_tqqq_p10_after_crash": float(np.nanpercentile(fwd10[tbool & ok10], 10)) if np.any(tbool & ok10) else None,
        "fwd10_tqqq_min_all": float(np.nanmin(fwd10[ok10])),
        "fwd10_tqqq_p10_all": float(np.nanpercentile(fwd10[ok10], 10)),
        "fwd20_tqqq_mean_after_crash": float(np.nanmean(fwd20[tbool & ok20])) if np.any(tbool & ok20) else None,
        "fwd20_tqqq_mean_all": float(np.nanmean(fwd20[ok20])),
        "fwd20_tqqq_negative_share_after_crash": float(np.nanmean(fwd20[tbool & ok20] < 0)) if np.any(tbool & ok20) else None,
        "fwd20_tqqq_min_after_crash": float(np.nanmin(fwd20[tbool & ok20])) if np.any(tbool & ok20) else None,
        "fwd20_tqqq_p10_after_crash": float(np.nanpercentile(fwd20[tbool & ok20], 10)) if np.any(tbool & ok20) else None,
        "fwd20_tqqq_min_all": float(np.nanmin(fwd20[ok20])),
        "fwd20_tqqq_p10_all": float(np.nanpercentile(fwd20[ok20], 10)),
    }


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

    episode_list = [
        ("2018-08-30", "2018-12-24"),
        ("2020-02-20", "2020-03-20"),
        ("2021-11-22", "2022-12-28"),
        ("2023-01-01", "2023-12-29"),
    ]
    episodes = _episodes(core1m["_dates"], core1m["_equity"], core1m["_bench"], episode_list)

    print("daily panel for the grid / diagnostics ...")
    tsd, od, cd = bt.panel(SYMBOLS, START, END, "1D", warmup_days=0)
    wD = build_weights(tsd, od, cd)
    daily_core = _run_daily(tsd, od, cd, wD)
    daily_core_metrics = {
        "cagr": float(daily_core["cagr"]),
        "max_drawdown": float(daily_core["max_drawdown"]),
        "sharpe": float(daily_core["sharpe"]),
        "fills": int(daily_core["fills"]),
        "time_in_tqqq": float((wD[:, 1] > 0.5).mean()),
    }

    grid = _grid(tsd, od, cd)
    neighbours = _neighbours(tsd, od, cd)
    components = _components(tsd, od, cd, cd)
    placebo = _placebo(tsd, od, cd, wD, n_draws=500)
    cuts = _cut_tests(ts, o, c, w, ["2018-12-21", "2020-03-12", "2022-09-13"])
    spells = _spell_stats(od, cd, wD)

    _, _, _, trigger_d = _daily_targets(cd, dict(PARAMS))
    event = _event_study(cd, trigger_d)

    ex2020 = _ex_year(core1m, [2020])
    ex2022 = _ex_year(core1m, [2022])
    ex_both = _ex_year(core1m, [2020, 2022])
    bench_ex2020 = _ex_year_bench(
        core1m["_dates"], core1m["_bench"], [2020]
    )
    bench_ex2022 = _ex_year_bench(
        core1m["_dates"], core1m["_bench"], [2022]
    )
    bench_ex_both = _ex_year_bench(
        core1m["_dates"], core1m["_bench"], [2020, 2022]
    )

    grid_pass = sum(
        1 for g in grid if g["cagr"] > BAR_CAGR and g["max_drawdown"] < BAR_DD
    )
    verdict = {
        "dev_1bp_cagr": core_public["cagr"],
        "dev_1bp_max_drawdown": core_public["max_drawdown"],
        "dev_1bp_sharpe": core_public["sharpe"],
        "bar_cagr": BAR_CAGR,
        "bar_max_drawdown": BAR_DD,
        "beats_cagr_bar": bool(core_public["cagr"] > BAR_CAGR),
        "beats_dd_bar": bool(core_public["max_drawdown"] < BAR_DD),
        "dd_below_60pct": bool(core_public["max_drawdown"] < 0.60),
        "pass": bool(core_public["cagr"] > BAR_CAGR and core_public["max_drawdown"] < BAR_DD),
        "beats_at_5bp": bool(
            results["5bp"]["cagr"] > BAR_CAGR
            and results["5bp"]["max_drawdown"] < BAR_DD
        ),
        "beats_at_10bp": bool(
            results["10bp"]["cagr"] > BAR_CAGR
            and results["10bp"]["max_drawdown"] < BAR_DD
        ),
        "grid_cells_passing": int(grid_pass),
        "grid_cells_total": int(len(grid)),
        "plateau": bool(grid_pass >= 6),
        "ex2020_beats_tqqq_ex2020": bool(
            ex2020["cagr"] > bench_ex2020["cagr"]
        ),
        "placebo_timing_value": bool(
            placebo["observed_percentile"]["cagr"] >= 90.0
            and placebo["share_placebo_cagr_above_bar"] <= 20.0
        ),
        "cut_tests_clean": bool(all(v.get("identical") for v in cuts.values())),
    }

    payload = {
        "strategy": "momentum-crash-filter",
        "version": "1.0",
        "window": {
            "dev_start": START,
            "dev_end": END,
            "holdout_loaded": False,
            "bars": "1-minute regular session, next-open fills, 2% band",
        },
        "bar": {"cagr": BAR_CAGR, "max_drawdown": BAR_DD, "sharpe": 0.82},
        "params": {k: v for k, v in PARAMS.items()},
        "headline_1m": results,
        "core_1m": core_public,
        "daily_core": daily_core_metrics,
        "episodes_1m": episodes,
        "defensive_spells_daily": spells,
        "event_study_daily": event,
        "grid_daily": grid,
        "neighbours_daily": neighbours,
        "components_daily": components,
        "placebo_daily": placebo,
        "cut_tests_1m": cuts,
        "ex_year_1m": {
            "ex_2020": ex2020,
            "ex_2022": ex2022,
            "ex_2020_and_2022": ex_both,
            "tqqq_ex_2020": bench_ex2020,
            "tqqq_ex_2022": bench_ex2022,
            "tqqq_ex_2020_and_2022": bench_ex_both,
        },
        "verdict": verdict,
        "notes": [
            "Development window only. 2024-2026 is never used or inspected; every panel ends 2023-12-29.",
            "All signals use QQQ daily open/close through the decision close.",
            "The 1-minute archive starts 2016-01-04, so the first 60 sessions have no 60-session momentum history and are default-long TQQQ; the crash brake is active from session 20.",
            "Costs are 1/5/10 bp on traded notional; the 1 bp run is the headline.",
            "The core thresholds were fixed on a daily-mark screen before this single 1-minute evaluation.",
        ],
    }

    out_path = HERE / "result.json"
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
