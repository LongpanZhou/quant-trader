"""Tail-hedge overlay on a 100% TQQQ core — `family-tail-hedge-overlay`.

DEVELOPMENT WINDOW ONLY (2016-01-04 .. 2023-12-29).  The 2024-2026 holdout is
never loaded.

Rules
-----
Core: 100% TQQQ.

Hedge trigger: at any minute close of session d, if TQQQ is at least 2.0% below
that session's open, the first such bar is the trigger.  The target written on
the trigger bar fills at the next minute's open.  From that fill the book is

    50% TQQQ + 50% synthetic inverse TQQQ

for the rest of the session *and overnight*.  The 15:59 target is 100% TQQQ,
so the hedge is exited at the next session's open and the core is re-entered.
There is no trend filter, no volatility target, no drawdown-recovery state, no
calendar rule, no ML and no relative-strength gate.

Synthetic inverse TQQQ
----------------------
The local panel has no inverse ETF.  We build a constant-notional -1x TQQQ NAV
from the same adjusted TQQQ 1-minute bars:

    inv_open[t]  = inv_close[t-1] * (1 - (TQQQ_open[t]  / TQQQ_close[t-1] - 1))
    inv_close[t] = inv_open[t]    * (1 - (TQQQ_close[t] / TQQQ_open[t]  - 1)
                                       - cost_per_bar)

with `cost_yr = 1.5%/yr` (net borrow + financing; the short rebate is ignored,
which is conservative).  This is a *synthetic long-only sleeve*, not a real
short position.  The backtest holds it as a long asset; `research/bt.py`
charges slippage on the traded notional exactly as it does for TQQQ.  The
result therefore depends on the synthetic being implementable as a
constant-notional total-return swap or a continuously rebalanced short.  A
daily-reset, no-intraday-rebalance variant and a -1x QQQ variant are reported
as robustness checks.

Execution
---------
`build_weights(ts, opens, closes)` takes the standard QQQ/TQQQ/BIL panel and
returns weights in the synthetic panel space

    column 0 = TQQQ, column 1 = synthetic inverse TQQQ, column 2 = BIL.

The primary must therefore be simulated with `build_panel(...)`; see `main()`.
Weights are >= 0, row sum <= 1, next-open fills, 2% band, 1 bp headline and
5/10 bp reported.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    $env:BT_THREADS = "1"
    python research/new/family-tail-hedge-overlay/strategy.py
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

DEV_START, DEV_END = "2016-01-04", "2023-12-29"
BPY = 252 * 390
OUT = Path(__file__).resolve().parent

PARAMS = dict(
    h=0.50,             # hedge fraction of equity (max 50% by mandate)
    thr=-0.020,         # TQQQ drawdown from session open
    cost_yr=0.015,      # synthetic borrow + financing, no short rebate
    hedge_asset=1,      # 1 = synthetic inverse TQQQ, 2 = BIL (cash control)
)


# ---------------------------------------------------------------------------
# synthetic inverse NAV
# ---------------------------------------------------------------------------
def inverse_nav(opens, closes, cost_yr=0.015, bars_per_year=BPY):
    """Constant-notional -1x NAV from one asset's minute bars.

    Returns (inv_open, inv_close).  The recursion uses only bars up to t, so
    truncating the input produces the same NAV up to the cut.
    """
    o = np.asarray(opens, dtype=float)
    c = np.asarray(closes, dtype=float)
    n = len(o)
    per_bar = float(cost_yr) / bars_per_year
    io = np.empty(n)
    ic = np.empty(n)
    io[0] = 1.0
    ic[0] = 1.0 - (c[0] / o[0] - 1.0) - per_bar
    prev_c, prev_i = c[0], ic[0]
    for t in range(1, n):
        gap = o[t] / prev_c - 1.0
        io[t] = prev_i * (1.0 - gap)
        intra = c[t] / o[t] - 1.0
        ic[t] = io[t] * (1.0 - intra - per_bar)
        prev_c, prev_i = c[t], ic[t]
    return io, ic


def inverse_nav_daily_bounds(opens, closes, first, last, cost_yr=0.015,
                             bars_per_year=BPY):
    o = np.asarray(opens, dtype=float)
    c = np.asarray(closes, dtype=float)
    n = len(o)
    per_bar = float(cost_yr) / bars_per_year
    io = np.empty(n)
    ic = np.empty(n)
    f0, l0 = int(first[0]), int(last[0])
    base0 = 1.0
    for t in range(f0, l0 + 1):
        io[t] = base0 * (1.0 - (o[t] / o[f0] - 1.0))
        ic[t] = base0 * (1.0 - (c[t] / o[f0] - 1.0))
    for k in range(1, len(first)):
        f, l = int(first[k]), int(last[k])
        gap = o[f] / c[int(last[k - 1])] - 1.0
        base = ic[int(last[k - 1])] * (1.0 - gap - per_bar * (l - f + 1))
        for t in range(f, l + 1):
            io[t] = base * (1.0 - (o[t] / o[f] - 1.0))
            ic[t] = base * (1.0 - (c[t] / o[f] - 1.0))
    return io, ic


def build_panel(ts, opens, closes, cost_yr=0.015, kind="minute"):
    """Return the synthetic (n,3) panel [TQQQ, INV, BIL]."""
    dates, first, last = bt.day_bounds(ts)
    if kind == "minute":
        inv_o, inv_c = inverse_nav(opens[:, 1], closes[:, 1], cost_yr)
    elif kind == "daily":
        inv_o, inv_c = inverse_nav_daily_bounds(
            opens[:, 1], closes[:, 1], first, last, cost_yr)
    else:
        raise ValueError(kind)
    syn_o = np.column_stack([opens[:, 1], inv_o, opens[:, 2]])
    syn_c = np.column_stack([closes[:, 1], inv_c, closes[:, 2]])
    return syn_o, syn_c


# ---------------------------------------------------------------------------
# weights
# ---------------------------------------------------------------------------
def build_weights(ts, opens, closes, params=None):
    """Return (n,3) weights in the [TQQQ, INV, BIL] synthetic panel space.

    `opens`/`closes` are the standard QQQ/TQQQ/BIL panel.  Column 0 is used
    only for the QQQ confirmation diagnostics and column 1 for the TQQQ
    trigger.  The primary hedge asset is column 1 of the synthetic panel.
    """
    p = dict(PARAMS)
    if params:
        p.update(params)
    h = float(p["h"])
    thr = float(p["thr"])
    hedge_asset = int(p["hedge_asset"])

    n = len(ts)
    day = bt.day_ids(ts)
    _, first, last = bt.day_bounds(ts)
    sess_open_t = opens[first, 1][day]
    ret_from_open = closes[:, 1] / sess_open_t - 1.0

    w = np.zeros((n, 3))
    w[:, 0] = 1.0
    for k in range(1, len(first)):
        f, l = int(first[k]), int(last[k])
        hit = np.flatnonzero(ret_from_open[f:l + 1] <= thr)
        if len(hit) == 0:
            continue
        b = f + int(hit[0])
        # A trigger on the last bar has no later bar in the session to fill
        # before the overnight re-entry; ignore it.
        if b >= l:
            continue
        # Hedge from the next open through the session close, then hold it
        # overnight: the 15:59 target is TQQQ, so the exit fills at the next
        # session's open.
        w[b:l, :] = 0.0
        w[b:l, 0] = 1.0 - h
        w[b:l, hedge_asset] = h
        w[l, :] = 0.0
        w[l, 0] = 1.0
    return w


# ---------------------------------------------------------------------------
# evaluation helpers
# ---------------------------------------------------------------------------
def _run(w, ts, opens, closes, slip=1.0, start=DEV_START, end=DEV_END):
    if start == DEV_START and end == DEV_END:
        r = bt.run(ts, opens, closes, w, start, band=0.02,
                   slippage_bps=slip)
    else:
        i = bt.start_index(ts, start)
        j = int(ts.searchsorted(
            pd.Timestamp(end, tz="America/New_York"), side="right"))
        r = bt.simulate(ts[i:j], opens[i:j], closes[i:j], w[i:j],
                        band=0.02, slippage_bps=slip)
    return r, bt.stats(r, BPY)


def _metrics(w, ts, opens, closes, slip=1.0, start=DEV_START, end=DEV_END):
    r, s = _run(w, ts, opens, closes, slip, start, end)
    return {
        "cagr": s["cagr"], "max_drawdown": s["max_drawdown"],
        "sharpe": s["sharpe"], "sortino": s["sortino"],
        "volatility": s["volatility"], "exposure": s["exposure"],
        "fills": s["fills"], "turnover": s["turnover"],
        "ending_equity": s["ending_equity"], "years": s["years"],
    }


def _daily_returns(result):
    eq = pd.Series(result["equity"], index=result["ts"])
    de = eq.groupby(eq.index.date).last()
    de.index = pd.to_datetime(de.index)
    return de.pct_change().dropna()


def _yearly(result):
    eq = pd.Series(result["equity"], index=result["ts"])
    de = eq.groupby(eq.index.date).last()
    idx = pd.to_datetime(de.index)
    yr = de.groupby(idx.year).last()
    yr0 = de.groupby(idx.year).first()
    return {int(y): {"strategy": float(yr[y] / yr0[y] - 1.0)} for y in yr.index}


def _dd_anatomy(result):
    eq = result["equity"]
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    j = int(np.argmin(dd))
    i = int(np.argmax(eq[:j + 1]))
    de = pd.Series(eq, index=result["ts"]).groupby(result["ts"].date).last()
    dpeak = de.cummax()
    ddd = de / dpeak - 1.0
    return {
        "minute_max_drawdown": float(-dd[j]),
        "minute_peak": str(result["ts"][i]),
        "minute_trough": str(result["ts"][j]),
        "daily_close_max_drawdown": float(-ddd.min()),
    }


def _episode_study(ts, opens, closes, w, params=None):
    """Full hedge-period attribution: trigger+1 open -> next session open."""
    p = dict(PARAMS)
    if params:
        p.update(params)
    thr = float(p["thr"])
    h = float(p["h"])
    day = bt.day_ids(ts)
    _, first, last = bt.day_bounds(ts)
    sess_open_t = opens[first, 1][day]
    ret_from_open = closes[:, 1] / sess_open_t - 1.0
    syn_o, syn_c = build_panel(ts, opens, closes, p["cost_yr"], "minute")
    rows = []
    for k in range(1, len(first)):
        f, l = int(first[k]), int(last[k])
        hit = np.flatnonzero(ret_from_open[f:l + 1] <= thr)
        if len(hit) == 0:
            continue
        b = f + int(hit[0])
        if b >= l:
            continue
        nb = int(first[k + 1]) if k + 1 < len(first) else len(ts) - 1
        tq = syn_o[nb, 0] / syn_o[b + 1, 0] - 1.0  # next open / entry open
        iv = syn_o[nb, 1] / syn_o[b + 1, 1] - 1.0
        port = (1.0 - h) * tq + h * iv
        rows.append((str(bt.session_dates(ts)[l]), b - f, tq, iv, port,
                     float(np.log1p(port) - np.log1p(tq))))
    ep = pd.DataFrame(rows, columns=["date", "bar", "tqqq", "inv", "port", "logdiff"])
    if len(ep) == 0:
        return {"n": 0}
    ep["year"] = pd.to_datetime(ep["date"]).dt.year
    s = ep.sort_values("logdiff", ascending=False)
    total = float(s["logdiff"].sum())
    top = {str(n): float(s.head(n)["logdiff"].sum()) for n in (1, 5, 10, 20)}
    return {
        "n_episodes": int(len(ep)),
        "mean_tqqq_hedge_period": float(ep["tqqq"].mean()),
        "mean_port_hedge_period": float(ep["port"].mean()),
        "mean_logdiff": float(ep["logdiff"].mean()),
        "sum_logdiff": total,
        "negative_episodes": int((s["logdiff"] < 0).sum()),
        "negative_fraction": float((s["logdiff"] < 0).mean()),
        "top_logdiff_sums": top,
        "top10_share": float(top["10"] / total) if total != 0 else None,
        "by_year": {
            int(y): {
                "n": int(len(g)),
                "mean_tqqq": float(g["tqqq"].mean()),
                "mean_port": float(g["port"].mean()),
                "sum_logdiff": float(g["logdiff"].sum()),
            }
            for y, g in ep.groupby("year")
        },
        "worst_15": [
            {"date": r.date, "bar": int(r.bar), "tqqq": float(r.tqqq),
             "port": float(r.port), "logdiff": float(r.logdiff)}
            for r in ep.nsmallest(15, "tqqq").itertuples()
        ],
    }


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main():
    ts, o0, c0 = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END, "1min")
    assert ts[-1].date() <= pd.Timestamp(DEV_END).date(), "holdout leaked"
    dates, first, last = bt.day_bounds(ts)
    nd = len(first)

    syn_o, syn_c = build_panel(ts, o0, c0, PARAMS["cost_yr"], "minute")
    w = build_weights(ts, o0, c0)
    w_cash = build_weights(ts, o0, c0, {"hedge_asset": 2})

    out = {
        "agent": "family-tail-hedge-overlay",
        "family": "tail-hedge / convexity overlay",
        "window": {"dev": [DEV_START, DEV_END], "holdout": "not loaded"},
        "idea": "A fast TQQQ crash signal opens a 50% synthetic inverse TQQQ "
                "hedge for the rest of the session and overnight, then the "
                "book re-enters TQQQ at the next open. The hedge truncates "
                "the left tail; it is not a trend gate or a vol target.",
        "execution": {
            "engine": "research/bt.py", "marks": "1min",
            "fills": "next open", "band": 0.02,
            "headline_bps": 1.0, "also_bps": [5.0, 10.0],
            "long_only": True, "weight_sum_max": 1.0,
            "panel": "synthetic [TQQQ, inverse TQQQ, BIL]",
        },
        "params": dict(PARAMS),
        "synthetic": {
            "construction": "constant-notional -1x TQQQ NAV from the same "
                            "adjusted 1-minute bars, rebalanced every minute",
            "cost_yr": PARAMS["cost_yr"],
            "cost_note": "net borrow + financing; the short rebate is ignored, "
                         "which is conservative",
            "not_a_real_short": True,
            "disclosure": "Column 1 is a synthetic long-only sleeve. The "
                          "portfolio never carries a negative weight. The "
                          "result assumes the synthetic can be implemented as "
                          "a constant-notional total-return swap or a "
                          "continuously rebalanced short, and bt.py charges "
                          "slippage on its traded notional.",
        },
        "windows": {"dev": {}},
        "benchmarks": {},
        "cash_control": {},
        "ratio_froth": {},
        "grid": [],
        "confirmation_variants": {},
        "budget_variants": {},
        "overnight_variants": {},
        "cost_sensitivity": {},
        "borrow_sensitivity": {},
        "construction_variants": {},
        "subperiods": {},
        "placebo": {},
        "correlations": {},
        "yearly": {},
        "dd_anatomy": {},
        "episode_study": {},
        "weights": {},
        "precut": {},
        "status": None,
    }

    # headline costs
    for slip, lab in ((1.0, "1bp"), (5.0, "5bp"), (10.0, "10bp")):
        out["windows"]["dev"][lab] = _metrics(w, ts, syn_o, syn_c, slip)

    # cash control
    for slip, lab in ((1.0, "1bp"), (5.0, "5bp"), (10.0, "10bp")):
        out["cash_control"][lab] = _metrics(w_cash, ts, syn_o, syn_c, slip)

    # benchmarks
    out["benchmarks"]["tqqq_minute"] = bt.benchmark(c0[:, 1], ts, BPY)
    out["benchmarks"]["qqq_minute"] = bt.benchmark(c0[:, 0], ts, BPY)
    out["benchmarks"]["tqqq_note"] = (
        "bt.benchmark on 1-minute marks; the task bar is 36.72% CAGR / 82.29% "
        "max DD / 0.82 Sharpe on daily-close marks.")

    # ratio-froth reference
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "ratio_froth", ROOT / "research" / "new" / "ratio-froth" / "strategy.py")
    rf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rf)
    w_rf, _ = rf.build_weights(ts, o0, c0)
    for slip, lab in ((1.0, "1bp"), (5.0, "5bp"), (10.0, "10bp")):
        r = bt.run(ts, o0, c0, w_rf, DEV_START, band=0.02,
                   slippage_bps=slip)
        s = bt.stats(r, BPY)
        out["ratio_froth"][lab] = {
            "cagr": s["cagr"], "max_drawdown": s["max_drawdown"],
            "sharpe": s["sharpe"], "sortino": s["sortino"],
            "volatility": s["volatility"], "fills": s["fills"],
            "turnover": s["turnover"], "ending_equity": s["ending_equity"],
        }

    # 8-cell plateau
    for h in (0.40, 0.50):
        for thr in (-0.016, -0.018, -0.020, -0.022):
            pp = {"h": h, "thr": thr}
            ww = build_weights(ts, o0, c0, pp)
            m = _metrics(ww, ts, syn_o, syn_c, 1.0)
            out["grid"].append({"name": f"h={h:.2f} thr={thr*100:.1f}%",
                                "h": h, "thr": thr, **m})

    # confirmation variants (idea 3)
    _, _, _ = bt.day_bounds(ts)
    day = bt.day_ids(ts)
    sess_open_t = o0[first, 1][day]
    sess_open_q = o0[first, 0][day]
    ret_t = c0[:, 1] / sess_open_t - 1.0
    ret_q = c0[:, 0] / sess_open_q - 1.0
    qc = c0[last, 0]
    q3 = pd.Series(qc).pct_change(3).to_numpy()
    q20 = pd.Series(qc).rolling(20).mean().to_numpy()

    def build_filtered(thr=-0.020, qqq_under=None, q3_neg=False, q20_up=False,
                       h=0.50):
        n = len(ts)
        ww = np.zeros((n, 3))
        ww[:, 0] = 1.0
        for k in range(1, nd):
            f, l = int(first[k]), int(last[k])
            cond = ret_t[f:l + 1] <= thr
            if qqq_under is not None:
                cond &= ret_t[f:l + 1] < 3.0 * ret_q[f:l + 1] - qqq_under
            if q3_neg:
                cond &= np.isfinite(q3[k - 1]) and q3[k - 1] < 0
            if q20_up:
                cond &= np.isfinite(q20[k - 1]) and qc[k - 1] > q20[k - 1]
            hit = np.flatnonzero(cond)
            if len(hit) == 0:
                continue
            b = f + int(hit[0])
            if b >= l:
                continue
            ww[b:l, :] = 0.0
            ww[b:l, 0] = 1.0 - h
            ww[b:l, 1] = h
            ww[l, :] = 0.0
            ww[l, 0] = 1.0
        return ww

    for name, kwargs in (
        ("no_confirmation_primary", {}),
        ("tqqq_worse_than_3x_qqq", {"qqq_under": 0.0}),
        ("tqqq_worse_than_3x_qqq_minus_10bp", {"qqq_under": 0.001}),
        ("tqqq_worse_than_3x_qqq_minus_20bp", {"qqq_under": 0.002}),
        ("qqq_3session_return_negative", {"q3_neg": True}),
        ("qqq_above_20d_sma", {"q20_up": True}),
        ("qqq_3d_negative_and_20d_up", {"q3_neg": True, "q20_up": True}),
    ):
        ww = build_filtered(**kwargs)
        out["confirmation_variants"][name] = _metrics(
            ww, ts, syn_o, syn_c, 1.0)

    # budget variants (idea 4): cap the number of hedges per calendar year
    def build_budget(max_episodes):
        n = len(ts)
        ww = np.zeros((n, 3))
        ww[:, 0] = 1.0
        used = {}
        for k in range(1, nd):
            f, l = int(first[k]), int(last[k])
            hit = np.flatnonzero(ret_t[f:l + 1] <= PARAMS["thr"])
            if len(hit) == 0:
                continue
            b = f + int(hit[0])
            if b >= l:
                continue
            yr = dates[l].year
            if used.get(yr, 0) >= max_episodes:
                continue
            used[yr] = used.get(yr, 0) + 1
            ww[b:l, :] = 0.0
            ww[b:l, 0] = 1.0 - PARAMS["h"]
            ww[b:l, 1] = PARAMS["h"]
            ww[l, :] = 0.0
            ww[l, 0] = 1.0
        return ww

    for cap in (60, 90, 120, 180):
        out["budget_variants"][f"max_{cap}_per_year"] = _metrics(
            build_budget(cap), ts, syn_o, syn_c, 1.0)

    # overnight variants (idea 5)
    lo = np.minimum.reduceat(c0[:, 1], first)[day]
    hi = np.maximum.reduceat(c0[:, 1], first)[day]
    close_pos = (c0[:, 1] - lo) / np.maximum(hi - lo, 1e-9)

    def build_exit(mode="weak_only", h=0.50, thr=-0.020, weak_close=0.3):
        n = len(ts)
        ww = np.zeros((n, 3))
        ww[:, 0] = 1.0
        for k in range(1, nd):
            f, l = int(first[k]), int(last[k])
            hit = np.flatnonzero(ret_t[f:l + 1] <= thr)
            if len(hit) == 0:
                continue
            b = f + int(hit[0])
            if b >= l:
                continue
            if mode == "always_overnight":
                end = l
            elif mode == "weak_only":
                weak = c0[l, 1] < o0[f, 1] or close_pos[l] < weak_close
                end = l if weak else l - 1
            elif mode == "close":
                end = l - 1
            else:
                raise ValueError(mode)
            ww[b:end, :] = 0.0
            ww[b:end, 0] = 1.0 - h
            ww[b:end, 1] = h
            ww[end:l + 1, :] = 0.0
            ww[end:l + 1, 0] = 1.0
        return ww

    for name, mode in (("always_overnight_primary", "always_overnight"),
                       ("weak_close_only_overnight", "weak_only"),
                       ("exit_at_1559_no_overnight", "close")):
        out["overnight_variants"][name] = _metrics(
            build_exit(mode=mode), ts, syn_o, syn_c, 1.0)

    # cost sensitivity already in windows; keep a compact 0/2bp table too
    for slip in (0.0, 2.0):
        out["cost_sensitivity"][f"{slip:.0f}bp"] = _metrics(
            w, ts, syn_o, syn_c, slip)
    out["cost_sensitivity"]["note"] = (
        "1/5/10 bp are in windows; 0 and 2 bp show the slope. The strategy is "
        "cost-sensitive because it trades a 50% switch on ~93 sessions/year.")

    # borrow cost sensitivity
    for cost in (0.0, 0.015, 0.05, 0.10):
        so, sc = build_panel(ts, o0, c0, cost, "minute")
        out["borrow_sensitivity"][f"{cost*100:.1f}%/yr"] = _metrics(
            w, ts, so, sc, 1.0)

    # construction variants
    so_d, sc_d = build_panel(ts, o0, c0, PARAMS["cost_yr"], "daily")
    out["construction_variants"]["daily_reset_no_intraday"] = _metrics(
        w, ts, so_d, sc_d, 1.0)
    # inverse QQQ instead of inverse TQQQ
    invq_o, invq_c = inverse_nav(o0[:, 0], c0[:, 0], PARAMS["cost_yr"])
    q_o = np.column_stack([o0[:, 1], invq_o, o0[:, 2]])
    q_c = np.column_stack([c0[:, 1], invq_c, c0[:, 2]])
    out["construction_variants"]["inverse_qqq"] = _metrics(
        w, ts, q_o, q_c, 1.0)

    # subperiods
    for name, a, bnd in (("2016-2019", "2016-01-04", "2019-12-31"),
                         ("2020-2021", "2020-01-02", "2021-12-31"),
                         ("2022-2023", "2022-01-03", "2023-12-29")):
        out["subperiods"][name] = {
            "primary": _metrics(w, ts, syn_o, syn_c, 1.0, a, bnd),
            "cash_control": _metrics(w_cash, ts, syn_o, syn_c, 1.0, a, bnd),
            "ratio_froth": _metrics(w_rf, ts, o0, c0, 1.0, a, bnd),
        }

    # placebo: random trigger dates and shifted dates
    rng = np.random.default_rng(2026)
    real_sessions, real_bars = [], []
    for k in range(1, nd):
        f, l = int(first[k]), int(last[k])
        hit = np.flatnonzero(ret_t[f:l + 1] <= PARAMS["thr"])
        if len(hit):
            real_sessions.append(k)
            real_bars.append(int(hit[0]))
    real_sessions = np.array(real_sessions)
    real_bars = np.array(real_bars)
    n_sig = len(real_sessions)

    def build_sessions(session_ids, bar_offsets):
        n = len(ts)
        ww = np.zeros((n, 3))
        ww[:, 0] = 1.0
        for k, off in zip(session_ids, bar_offsets):
            f, l = int(first[k]), int(last[k])
            b = f + int(off)
            if b >= l:
                continue
            ww[b:l, :] = 0.0
            ww[b:l, 0] = 1.0 - PARAMS["h"]
            ww[b:l, 1] = PARAMS["h"]
            ww[l, :] = 0.0
            ww[l, 0] = 1.0
        return ww

    real_cagr = out["windows"]["dev"]["1bp"]["cagr"]

    def summarize(vals):
        a = np.asarray(vals, dtype=float)
        return {
            "n_draws": int(len(a)),
            "mean_cagr": float(a.mean()),
            "std_cagr": float(a.std(ddof=1)),
            "p95_cagr": float(np.quantile(a, 0.95)),
            "max_cagr": float(a.max()),
            "p_value": float((a >= real_cagr).mean()),
        }

    n_draws = 250
    rand_cagr = []
    for _ in range(n_draws):
        kk = rng.choice(np.arange(1, nd - 1), n_sig, replace=False)
        bb = rng.choice(real_bars, n_sig, replace=True)
        ww = build_sessions(kk, bb)
        _, ss = _run(ww, ts, syn_o, syn_c, 1.0)
        rand_cagr.append(ss["cagr"])
    shift_cagr = []
    for _ in range(n_draws):
        sh = int(rng.integers(1, nd - 1))
        kk = ((real_sessions - 1 + sh) % (nd - 2)) + 1
        ww = build_sessions(kk, real_bars)
        _, ss = _run(ww, ts, syn_o, syn_c, 1.0)
        shift_cagr.append(ss["cagr"])
    t1030 = int(np.flatnonzero(
        ts[first[1]:last[1] + 1].strftime("%H:%M") == "10:30")[0])
    fixed_cagr = []
    for _ in range(n_draws):
        kk = rng.choice(np.arange(1, nd - 1), n_sig, replace=False)
        ww = build_sessions(kk, np.full(n_sig, t1030))
        _, ss = _run(ww, ts, syn_o, syn_c, 1.0)
        fixed_cagr.append(ss["cagr"])
    out["placebo"] = {
        "real_cagr": real_cagr,
        "real_trigger_sessions": int(n_sig),
        "real_trigger_share_of_sessions": float(n_sig / nd),
        "random_sessions_real_bar_offsets": summarize(rand_cagr),
        "shifted_sessions": summarize(shift_cagr),
        "random_sessions_1030_bar": summarize(fixed_cagr),
        "note": "Random and shifted placebos preserve the number of triggers "
                "and (for the random-session draw) the intraday bar-offset "
                "distribution. A same-session random-bar placebo is not used: "
                "it selects sessions using a future trigger and is therefore "
                "not causal.",
    }

    # correlations vs ratio-froth and the other eight winners
    r1 = _run(w, ts, syn_o, syn_c, 1.0)[0]
    rs = _daily_returns(r1)
    curve_dir = ROOT / "research" / "new" / "curves"
    winners = ["ratio-froth", "vol-scaled-crash-stop", "relative-value-tqqq",
               "fomc-opex-window", "family-session-timing",
               "family-short-reversal", "family-rebalance-flow",
               "family-intraday-microstructure-day", "family-ml-microstructure"]
    for slug in winners:
        p = curve_dir / f"{slug}.json"
        if not p.exists():
            out["correlations"][slug] = None
            continue
        d = json.load(open(p))
        q = pd.Series(d["values"], index=pd.to_datetime(d["dates"]))
        q = q.pct_change().dropna()
        j = rs.index.intersection(q.index)
        out["correlations"][slug] = {
            "n": int(len(j)),
            "corr": float(np.corrcoef(rs.loc[j], q.loc[j])[0, 1]),
        }

    # yearly and drawdown anatomy
    out["yearly"] = _yearly(r1)
    out["dd_anatomy"] = _dd_anatomy(r1)
    out["episode_study"] = _episode_study(ts, o0, c0, w)

    # weights / exposure diagnostics
    out["weights"] = {
        "mean_tqqq": float(w[:, 0].mean()),
        "mean_inverse": float(w[:, 1].mean()),
        "mean_bil": float(w[:, 2].mean()),
        "bars_with_inverse": float((w[:, 1] > 0).mean()),
        "trigger_sessions": int(n_sig),
        "trigger_share": float(n_sig / nd),
        "note": "bt.stats exposure is 1.0 because TQQQ and the synthetic "
                "inverse are both invested assets; the TQQQ/inverse split is "
                "the relevant exposure.",
    }

    # pre-cut causality: truncate at 2020-03-12 11:07 and compare prior weights
    cut = int(ts.searchsorted(
        pd.Timestamp("2020-03-12 11:07", tz="America/New_York")))
    pre = bt.start_index(ts, "2020-03-12")
    w_cut = build_weights(ts[:cut], o0[:cut], c0[:cut])
    inv_cut_o, inv_cut_c = inverse_nav(o0[:cut, 1], c0[:cut, 1],
                                       PARAMS["cost_yr"])
    out["precut"] = {
        "cut": "2020-03-12 11:07 America/New_York",
        "bars_compared": int(pre),
        "max_abs_weight_diff": float(np.max(np.abs(
            w_cut[:pre, 1] - w[:pre, 1]))),
        "max_abs_inverse_nav_diff": float(np.max(np.abs(
            inv_cut_c[:pre] - syn_c[:pre, 1]))),
        "note": "all weights and the synthetic NAV through the 2020-03-11 "
                "15:59 close are identical; the 11:07 cut is mid-session and "
                "cannot change any prior target.",
    }

    dev = out["windows"]["dev"]["1bp"]
    out["status"] = (
        "dev_pass" if (dev["cagr"] > 0.6156 and dev["max_drawdown"] < 0.50)
        else "dev_fail")
    out["kill_criteria"] = {
        "hedge_adds_cagr_vs_cash": bool(
            dev["cagr"] > out["cash_control"]["1bp"]["cagr"]),
        "hedge_reduces_dd_vs_cash": bool(
            dev["max_drawdown"] < out["cash_control"]["1bp"]["max_drawdown"]),
        "beats_ratio_froth_cagr": bool(
            dev["cagr"] > out["ratio_froth"]["1bp"]["cagr"]),
        "beats_ratio_froth_sharpe": bool(
            dev["sharpe"] > out["ratio_froth"]["1bp"]["sharpe"]),
        "no_worse_ratio_froth_dd": bool(
            dev["max_drawdown"] <= out["ratio_froth"]["1bp"]["max_drawdown"]),
    }

    (OUT / "result.json").write_text(json.dumps(out, indent=2, default=float))
    print(json.dumps({
        "status": out["status"],
        "windows": out["windows"]["dev"],
        "cash_control": out["cash_control"]["1bp"],
        "ratio_froth": out["ratio_froth"]["1bp"],
        "kill_criteria": out["kill_criteria"],
        "placebo": out["placebo"],
        "dd_anatomy": out["dd_anatomy"],
        "weights": out["weights"],
    }, indent=2, default=float))
    print("wrote", OUT / "result.json")


if __name__ == "__main__":
    main()
