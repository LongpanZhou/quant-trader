"""Participation exhaustion v2 — repair of `volume-orderflow`.

DEVELOPMENT WINDOW ONLY (2016-01-04 .. 2023-12-29).  The 2024-2026 holdout is
never loaded or inspected.

Original failure
----------------
    rvol >= 1.5 AND QQQ intraday <= -0.8% AND clv >= 0

fires 3 times in 8 years.  The close-location condition is almost
self-contradictory on a down day: conditional on QQQ <= -0.8% intraday, only 5
sessions close in the upper half of their range.  The conjunction, not any
single component, is the bottleneck.

Repair (pre-registered count fix)
---------------------------------
Relax the volume floor from 1.5x to 1.3x the prior-20-session mean and the
close-location floor from the upper half (clv >= 0) to the upper
three-quarters (clv >= -0.5):

    event = (rvol >= 1.3) AND (QQQ intraday <= -0.8%) AND (clv >= -0.5)

Execution is unchanged from the original: buy 100% TQQQ at the next open, hold
5 sessions, exit at the following open, otherwise BIL.  Overlapping events
extend the window.

The report must show whether volume is doing any work.  If the high-volume
bucket is not better than the low-volume bucket inside the same decline/clv
filter, the participation-exhaustion mechanism is not supported and the
strategy is retired as a participation strategy even if the headline CAGR is
positive.

The 165-day QQQ SMA appears only as a benchmark/correlation reference, never as
a gate.  No old weight matrix or old `build_weights` is imported.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/new/volume-orderflow-v2/strategy.py
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

HERE = Path(__file__).resolve().parent
DEV_START, DEV_END = "2016-01-04", "2023-12-29"
SYMS = ("QQQ", "TQQQ", "BIL")
BPY = 252 * 390

PARAMS = dict(rvol_hi=1.30, rvol_n=20, intraday_lo=-0.008, clv_min=-0.50,
              hold=5, size=1.0)

GRID = [
    ("1 primary rvol1.3/clv-.50", dict(rvol_hi=1.30, clv_min=-0.50, hold=5, size=1.0)),
    ("2 rvol 1.2", dict(rvol_hi=1.20, clv_min=-0.50, hold=5, size=1.0)),
    ("3 rvol 1.5", dict(rvol_hi=1.50, clv_min=-0.50, hold=5, size=1.0)),
    ("4 clv -0.25", dict(rvol_hi=1.30, clv_min=-0.25, hold=5, size=1.0)),
    ("5 clv -0.75", dict(rvol_hi=1.30, clv_min=-0.75, hold=5, size=1.0)),
    ("6 hold 3", dict(rvol_hi=1.30, clv_min=-0.50, hold=3, size=1.0)),
    ("7 hold 10", dict(rvol_hi=1.30, clv_min=-0.50, hold=10, size=1.0)),
    ("8 half size", dict(rvol_hi=1.30, clv_min=-0.50, hold=5, size=0.5)),
]


# ---------------------------------------------------------------------------
# data / features
# ---------------------------------------------------------------------------
def load_panel(start=DEV_START, end=DEV_END):
    """QQQ/TQQQ/BIL 1-minute panel plus QQQ high, low and volume on that grid."""
    ts, opens, closes = bt.panel(SYMS, start, end, "1min")
    assert str(ts[-1].date()) <= end, "holdout data leaked into the panel"
    n, k = len(ts), len(SYMS)
    highs = np.empty((n, k))
    lows = np.empty((n, k))
    vols = np.empty((n, k))
    for j, sym in enumerate(SYMS):
        df = bt.load_1m(sym)
        df = df[(df["ts"] >= ts[0]) & (df["ts"] < ts[-1] + pd.Timedelta(minutes=1))]
        f = df.set_index("ts").reindex(ts)
        highs[:, j] = f["high"].ffill().bfill().to_numpy()
        lows[:, j] = f["low"].ffill().bfill().to_numpy()
        vols[:, j] = f["volume"].fillna(0.0).to_numpy()
    return ts, opens, closes, highs, lows, vols


def session_features(ts, opens, closes, highs, lows, vols, params=PARAMS):
    """Per-session QQQ aggregates and the event flag (all known at the close)."""
    dates, first, last = bt.day_bounds(ts)
    nd = len(first)
    qo = opens[first, 0]
    qc = closes[last, 0]
    qh = np.array([highs[f:l + 1, 0].max() for f, l in zip(first, last)])
    ql = np.array([lows[f:l + 1, 0].min() for f, l in zip(first, last)])
    qv = np.array([vols[f:l + 1, 0].sum() for f, l in zip(first, last)])

    base = pd.Series(qv).rolling(params["rvol_n"], min_periods=params["rvol_n"]).mean()
    base = base.shift(1).to_numpy()                     # prior sessions only
    with np.errstate(invalid="ignore", divide="ignore"):
        rvol = np.where(base > 0, qv / base, np.nan)

    intraday = qc / qo - 1.0
    rng = qh - ql
    clv = np.where(rng > 0, ((qc - ql) - (qh - qc)) / np.where(rng > 0, rng, 1.0), 0.0)
    event = (np.isfinite(rvol) & (rvol >= params["rvol_hi"])
             & (intraday <= params["intraday_lo"])
             & (clv >= params["clv_min"]))
    session_dates = np.array([d for d in dates[first]])
    return dict(dates=session_dates, first=first, last=last, nd=nd,
                qo=qo, qc=qc, qh=qh, ql=ql, qv=qv,
                rvol=rvol, intraday=intraday, clv=clv, event=event)


def component_counts(f, params=PARAMS):
    """Original and repaired component counts, for the diagnosis table."""
    rv, intr, clv = f["rvol"], f["intraday"], f["clv"]
    orig = (np.isfinite(rv) & (rv >= 1.5) & (intr <= -0.008) & (clv >= 0.0))
    now = (np.isfinite(rv) & (rv >= params["rvol_hi"])
           & (intr <= params["intraday_lo"]) & (clv >= params["clv_min"]))
    return dict(
        sessions=int(f["nd"]),
        original_rvol_1p5=int(np.nansum(rv >= 1.5)),
        original_intraday=int(np.nansum(intr <= -0.008)),
        original_clv_0=int(np.nansum(clv >= 0.0)),
        original_conjunction=int(np.nansum(orig)),
        repaired_rvol_1p3=int(np.nansum(rv >= 1.3)),
        repaired_clv_m05=int(np.nansum(clv >= -0.5)),
        repaired_conjunction=int(np.nansum(now)),
        original_events=3, original_entries=3, original_fills=13,
        original_exposure=0.00746,
    )


# ---------------------------------------------------------------------------
# weights
# ---------------------------------------------------------------------------
def holding_flags(event, hold):
    """W[d] = 1 if session d is inside a holding window.

    A signal at session d opens at the next open and covers sessions
    d+1 .. d+hold.  A new signal while long extends the window.
    """
    nd = len(event)
    w = np.zeros(nd, dtype=float)
    long_until = -1
    entries = []
    for d in range(nd):
        if d <= long_until:
            w[d] = 1.0
        if event[d]:
            if d > long_until:
                entries.append(d)
            long_until = max(long_until, d + hold)
    return w, entries


def build_weights(ts, opens, closes, highs, lows, vols, params=None, mask=None):
    """Return (weights, info).  weights[i] fills at bar i+1's open."""
    p = dict(PARAMS)
    if params:
        p.update(params)
    f = session_features(ts, opens, closes, highs, lows, vols, p)
    event = f["event"]
    if mask is not None:
        event = np.asarray(mask, bool) & np.isfinite(f["rvol"])
    W, entries = holding_flags(event, int(p["hold"]))
    day_id = np.repeat(np.arange(f["nd"]), np.diff(np.r_[f["first"], len(ts)]))

    n = len(ts)
    w = np.zeros((n, 3))
    w1 = W[day_id].copy()
    nxt = np.r_[W[1:], 0.0]
    w1[f["last"]] = nxt[day_id[f["last"]]]          # last bar -> next open
    w1 *= p["size"]
    w[:, 1] = w1
    w[:, 2] = 1.0 - w1

    info = dict(
        params={k: (int(v) if isinstance(v, (int, np.integer)) else float(v))
                for k, v in p.items()},
        events=int(event.sum()),
        event_dates=[str(f["dates"][k]) for k in np.flatnonzero(event)],
        entries=len(entries),
        entry_dates=[str(f["dates"][k + 1]) for k in entries if k + 1 < f["nd"]],
        sessions_long=int(W.sum()),
        exposure=float(W.mean()),
    )
    return w, info


# ---------------------------------------------------------------------------
# evaluation helpers
# ---------------------------------------------------------------------------
def dev_slice(ts, start=DEV_START, end=DEV_END):
    i = bt.start_index(ts, start)
    end_ts = pd.Timestamp(end, tz="America/New_York") + pd.Timedelta(days=1)
    j = int(ts.searchsorted(end_ts, side="left"))
    return slice(i, j)


def run_metrics(ts, op, cl, w, start=DEV_START, end=DEV_END, slip=1.0):
    s = dev_slice(ts, start, end)
    r = bt.simulate(ts[s], op[s], cl[s], w[s], band=0.02, slippage_bps=slip)
    st = bt.stats(r, BPY)
    st["tqqq_exposure"] = float(np.mean(w[s][:, 1]))
    return r, st


def daily_returns(result):
    eq = pd.Series(result["equity"], index=result["ts"])
    return eq.groupby(eq.index.date).last().pct_change().dropna()


def subperiods(ts, op, cl, w):
    out = {}
    for label, a, b in (("2016-2019", "2016-01-04", "2019-12-31"),
                        ("2020-2021", "2020-01-02", "2021-12-31"),
                        ("2022-2023", "2022-01-03", "2023-12-29")):
        _, s = run_metrics(ts, op, cl, w, a, b, 1.0)
        out[label] = {k: float(s[k]) for k in
                      ("cagr", "max_drawdown", "sharpe", "volatility",
                       "tqqq_exposure", "fills", "turnover")}
    return out


def event_stats(f, mask, hold, op, cl):
    """Forward TQQQ open-to-open returns for the event mask."""
    nd = f["nd"]
    first, last = f["first"], f["last"]
    r, e = [], []
    for d in np.flatnonzero(mask):
        if d + hold + 1 >= nd:
            continue
        entry = op[first[d + 1], 1]
        exit_ = op[first[d + hold + 1], 1]
        r.append(exit_ / entry - 1.0)
        e.append((exit_ / entry - 1.0)
                 - 3.0 * (op[first[d + hold + 1], 0] / op[first[d + 1], 0] - 1.0))
    r = np.asarray(r)
    e = np.asarray(e)
    if len(r) < 3:
        return dict(n=int(len(r)))
    t = float(r.mean() / r.std(ddof=1) * np.sqrt(len(r))) if r.std(ddof=1) > 0 else None
    rng = np.random.default_rng(7)
    boot = rng.choice(r, (20000, len(r)), replace=True).mean(axis=1)
    order = np.argsort(r)
    return dict(
        n=int(len(r)), mean=float(r.mean()), median=float(np.median(r)),
        win=float((r > 0).mean()), t=t, std=float(r.std(ddof=1)),
        bootstrap_p=float((boot <= 0).mean()),
        ci95_low=float(np.quantile(boot, 0.025)),
        ci95_high=float(np.quantile(boot, 0.975)),
        min=float(r.min()), max=float(r.max()),
        mean_ex_top5=float(r[order[:-5]].mean()) if len(r) > 5 else None,
        excess_mean_pp=float(e.mean() * 100.0),
    )


def bucket_returns(f, mask, op, hold):
    nd = f["nd"]
    r = []
    for d in np.flatnonzero(mask):
        if d + hold + 1 >= nd:
            continue
        r.append(op[f["first"][d + hold + 1], 1] / op[f["first"][d + 1], 1] - 1.0)
    return np.asarray(r)


def bucket_stats(f, mask, op, cl, hold, label):
    """Event count and mean forward return for a sub-mask."""
    r = bucket_returns(f, mask, op, hold)
    if len(r) < 2:
        return {"label": label, "n": int(len(r))}
    return {"label": label, "n": int(len(r)), "mean": float(r.mean()),
            "median": float(np.median(r)), "win": float((r > 0).mean()),
            "t": float(r.mean() / r.std(ddof=1) * np.sqrt(len(r)))
            if r.std(ddof=1) > 0 else None}


def attribution(f, op, cl, hold=5):
    """Does volume add anything inside the same decline/close filter?"""
    base = (f["intraday"] <= PARAMS["intraday_lo"]) & (f["clv"] >= PARAMS["clv_min"])
    rv = f["rvol"]
    out = {
        "base_filter": {"n": int(np.nansum(base))},
        "volume_buckets": [],
        "high_vs_low": {},
        "no_volume_control": {},
        "close_buckets": [],
    }
    for lo, hi, lab in [(0.0, 1.0, "rvol < 1.0"), (1.0, 1.2, "1.0-1.2"),
                        (1.2, 1.5, "1.2-1.5"), (1.5, 2.0, "1.5-2.0"),
                        (2.0, 99.0, ">= 2.0")]:
        out["volume_buckets"].append(
            bucket_stats(f, base & (rv >= lo) & (rv < hi), op, cl, hold, lab))
    hi = base & (rv >= 1.3)
    lo = base & (rv < 1.3)
    out["high_vs_low"] = {
        "high": bucket_stats(f, hi, op, cl, hold, "rvol >= 1.3"),
        "low": bucket_stats(f, lo, op, cl, hold, "rvol < 1.3"),
    }
    rh = bucket_returns(f, hi, op, hold)
    rl = bucket_returns(f, lo, op, hold)
    if len(rh) > 2 and len(rl) > 2:
        diff = float(rh.mean() - rl.mean())
        rng = np.random.default_rng(11)
        boot = np.array([rng.choice(rh, len(rh), replace=True).mean()
                         - rng.choice(rl, len(rl), replace=True).mean()
                         for _ in range(5000)])
        out["high_vs_low"]["difference"] = diff
        out["high_vs_low"]["difference_p_boot"] = float((boot <= 0).mean())
        out["high_vs_low"]["difference_ci95"] = [
            float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))]
    out["no_volume_control"] = {"n_events": int(np.nansum(base))}
    for cv_lo, cv_hi, lab in [(-1.01, -0.8, "clv < -0.8"), (-0.8, -0.5, "-0.8..-0.5"),
                              (-0.5, -0.25, "-0.5..-0.25"), (-0.25, 0.0, "-0.25..0"),
                              (0.0, 1.01, ">= 0")]:
        out["close_buckets"].append(
            bucket_stats(f, (f["intraday"] <= -0.008) & (f["clv"] >= cv_lo)
                         & (f["clv"] < cv_hi), op, cl, hold, lab))
    return out


def benchmark_weights(ts, cl, n=165):
    dates, first, last = bt.day_bounds(ts)
    qc = cl[last, 0]
    sma = pd.Series(qc).rolling(n).mean().to_numpy()
    reg = np.zeros(len(first), bool)
    reg[1:] = qc[:-1] > sma[:-1]
    day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, len(ts)]))
    w = np.zeros((len(ts), 3))
    w[:, 1] = reg[day_id].astype(float)
    w[:, 2] = 1.0 - w[:, 1]
    return w


def placebo(ts, op, cl, hi, lo, vol, f, n_draws=200, seed=11):
    n_ev = int(f["event"].sum())
    if n_ev < 1:
        return None
    eligible = np.array([k for k in range(20, f["nd"] - PARAMS["hold"] - 2)
                         if str(f["dates"][k]) >= DEV_START])
    rng = np.random.default_rng(seed)
    cagrs, dds = [], []
    for _ in range(n_draws):
        pick = rng.choice(eligible, n_ev, replace=False)
        m = np.zeros(f["nd"], bool)
        m[pick] = True
        wg, _ = build_weights(ts, op, cl, hi, lo, vol, dict(PARAMS), mask=m)
        _, s = run_metrics(ts, op, cl, wg, DEV_START, DEV_END, 1.0)
        cagrs.append(float(s["cagr"]))
        dds.append(float(s["max_drawdown"]))
    cagrs = np.asarray(cagrs)
    w_real, _ = build_weights(ts, op, cl, hi, lo, vol, dict(PARAMS))
    _, sr = run_metrics(ts, op, cl, w_real, DEV_START, DEV_END, 1.0)
    return dict(n_draws=int(n_draws), real_cagr=float(sr["cagr"]),
                placebo_mean=float(np.mean(cagrs)),
                placebo_std=float(np.std(cagrs, ddof=1)),
                placebo_p95=float(np.quantile(cagrs, 0.95)),
                placebo_max=float(np.max(cagrs)),
                percentile=float((cagrs < sr["cagr"]).mean()),
                p_value=float((cagrs >= sr["cagr"]).mean()))


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main():
    ts, op, cl, hi, lo, vol = load_panel()
    assert str(ts[-1].date()) <= DEV_END, "holdout data leaked into the panel"
    f = session_features(ts, op, cl, hi, lo, vol, PARAMS)
    w, info = build_weights(ts, op, cl, hi, lo, vol, dict(PARAMS))
    s = dev_slice(ts)
    exp_dev = float(np.mean(w[s][:, 1]))
    session_dev = np.array([str(d) >= DEV_START for d in f["dates"]])
    event_dev = f["event"] & session_dev
    entries_dev = [d for d in info["entry_dates"] if d >= DEV_START]

    comp = component_counts(f)
    out = {
        "agent": "volume-orderflow-v2",
        "original": "research/revisit/volume-orderflow",
        "status": "pending",
        "idea": "A well-above-normal-volume QQQ intraday decline that closes off "
                "the low marks absorbed supply; buy TQQQ for five sessions.",
        "hypothesis": "Participation-conditioned supply climaxes forecast positive "
                      "five-session TQQQ returns after costs.",
        "why_changed": "The original rvol>=1.5 / intraday<=-0.8% / clv>=0 "
                       "conjunction fired 3 times in 8 years.  On a down day the "
                       "close is almost never in the upper half of the range, so "
                       "the close-location leg was the binding, nearly "
                       "self-contradictory condition.",
        "universe": ["QQQ (signal)", "TQQQ (3x expression)", "BIL (cash)"],
        "window": {"dev": [DEV_START, DEV_END], "holdout": "not loaded"},
        "params": PARAMS,
        "diagnostics": {
            "component_counts": comp,
            "events": int(event_dev.sum()),
            "entries": len(entries_dev),
            "tqqq_exposure": exp_dev,
            "sessions_long": int(info["sessions_long"]),
            "event_dates": [d for d in info["event_dates"] if d >= DEV_START],
            "entry_dates": entries_dev,
        },
        "event_study": {
            "h3": event_stats(f, event_dev, 3, op, cl),
            "h5": event_stats(f, event_dev, 5, op, cl),
            "h10": event_stats(f, event_dev, 10, op, cl),
        },
        "attribution": attribution(f, op, cl, 5),
        "windows": {"dev": {}, "holdout": None, "10y": None, "5y": None},
        "subperiods": {},
        "yearly": {},
        "grid": [],
        "benchmarks": {},
        "corr_vs_165d_baseline": None,
        "placebo": None,
        "verdict": None,
    }

    r1 = None
    for slip, tag in ((1.0, "1bp"), (5.0, "5bp"), (10.0, "10bp")):
        r, st = run_metrics(ts, op, cl, w, DEV_START, DEV_END, slip)
        out["windows"]["dev"][tag] = {
            "cagr": float(st["cagr"]), "max_drawdown": float(st["max_drawdown"]),
            "sharpe": float(st["sharpe"]), "sortino": float(st["sortino"]),
            "volatility": float(st["volatility"]), "fills": int(st["fills"]),
            "turnover": float(st["turnover"]), "ending_equity": float(st["ending_equity"]),
            "tqqq_exposure": float(st["tqqq_exposure"]),
        }
        if slip == 1.0:
            r1 = r

    out["subperiods"] = subperiods(ts, op, cl, w)
    i = bt.start_index(ts, DEV_START)
    out["yearly"] = {int(k): {"strategy": float(v["strategy"]),
                              "benchmark": float(v["benchmark"])}
                     for k, v in bt.yearly(ts[i:], r1["equity"], cl[i:, 1]).items()}

    for name, col in (("tqqq", 1), ("qqq", 0), ("bil", 2)):
        b = bt.benchmark(cl[i:, col], ts[i:], BPY)
        out["benchmarks"][name] = {k: float(b[k]) for k in
                                   ("cagr", "max_drawdown", "volatility", "sharpe")}
    bw = benchmark_weights(ts, cl)
    rb, sb = run_metrics(ts, op, cl, bw, DEV_START, DEV_END, 1.0)
    out["benchmarks"]["baseline_165d"] = {
        "cagr": float(sb["cagr"]), "max_drawdown": float(sb["max_drawdown"]),
        "sharpe": float(sb["sharpe"]), "volatility": float(sb["volatility"]),
    }
    sr = daily_returns(r1)
    br = daily_returns(rb)
    j = sr.index.intersection(br.index)
    out["corr_vs_165d_baseline"] = float(np.corrcoef(sr.loc[j], br.loc[j])[0, 1])

    # pre-registered grid (1bp)
    for name, pp in GRID:
        wg, gi = build_weights(ts, op, cl, hi, lo, vol, pp)
        _, sg = run_metrics(ts, op, cl, wg, DEV_START, DEV_END, 1.0)
        out["grid"].append({
            "name": name, "params": {k: pp[k] for k in pp},
            "events": int(gi["events"]),
            "entries": len([d for d in gi["entry_dates"] if d >= DEV_START]),
            "tqqq_exposure": float(np.mean(wg[s][:, 1])),
            "cagr": float(sg["cagr"]), "max_drawdown": float(sg["max_drawdown"]),
            "sharpe": float(sg["sharpe"]), "fills": int(sg["fills"]),
        })

    out["placebo"] = placebo(ts, op, cl, hi, lo, vol, f, n_draws=200)

    # no-volume control: identical decline/clv filter, same 5-session hold
    base_ev = ((f["intraday"] <= PARAMS["intraday_lo"])
               & (f["clv"] >= PARAMS["clv_min"]) & session_dev)
    w_nv, info_nv = build_weights(ts, op, cl, hi, lo, vol, dict(PARAMS), mask=base_ev)
    _, s_nv = run_metrics(ts, op, cl, w_nv, DEV_START, DEV_END, 1.0)
    out["attribution"]["no_volume_control"].update({
        "n_events": int(info_nv["events"]),
        "entries": len([d for d in info_nv["entry_dates"] if d >= DEV_START]),
        "tqqq_exposure": float(np.mean(w_nv[s][:, 1])),
        "cagr": float(s_nv["cagr"]),
        "max_drawdown": float(s_nv["max_drawdown"]),
        "sharpe": float(s_nv["sharpe"]),
    })

    # attribution: does volume add?
    hv = out["attribution"]["high_vs_low"]
    dev1 = out["windows"]["dev"]["1bp"]
    nv = out["attribution"]["no_volume_control"]
    diff = hv.get("difference")
    diff_p = hv.get("difference_p_boot")
    volume_works = (hv.get("high", {}).get("n", 0) >= 10
                    and hv.get("low", {}).get("n", 0) >= 10
                    and diff is not None and diff > 0 and diff_p is not None
                    and diff_p < 0.10
                    and dev1["sharpe"] > nv.get("sharpe", 0.0))
    clv_grid = {g["name"]: g for g in out["grid"]}
    clv_cells = [clv_grid[n]["cagr"] for n in
                 ("4 clv -0.25", "1 primary rvol1.3/clv-.50", "5 clv -0.75")]
    clv_plateau = all(c > 0.03 for c in clv_cells)
    h5 = out["event_study"]["h5"]
    bil = out["benchmarks"]["bil"]["cagr"]
    sub = out["subperiods"]
    checks = {
        "enough_events": out["diagnostics"]["events"] >= 20,
        "forward_edge": h5.get("mean", -1) > 0 and (h5.get("t") or 0) >= 1.5,
        "volume_attribution": bool(volume_works),
        "clv_plateau": bool(clv_plateau),
        "one_episode": not (sub["2020-2021"]["cagr"] > 0
                            and sub["2016-2019"]["cagr"] <= 0
                            and sub["2022-2023"]["cagr"] <= 0),
        "beats_bil_10bp": out["windows"]["dev"]["10bp"]["cagr"] > bil,
        "placebo_95": out["placebo"]["percentile"] >= 0.95,
    }
    reasons = []
    if not checks["volume_attribution"]:
        reasons.append(
            "volume is not additive: the high-volume bucket is not significantly "
            f"better than the low-volume bucket (diff {diff*100:+.2f}pp, "
            f"one-sided p {diff_p:.2f}), and the same decline/clv rule without "
            f"volume has a higher Sharpe ({nv['sharpe']:.2f} vs {dev1['sharpe']:.2f})")
    if not checks["clv_plateau"]:
        reasons.append(
            "the close-location result is a spike at clv >= -0.5 "
            f"(CAGRs {clv_cells[0]*100:.1f}% / {clv_cells[1]*100:.1f}% / "
            f"{clv_cells[2]*100:.1f}% at -0.25 / -0.50 / -0.75)")
    if not checks["one_episode"]:
        reasons.append("the 2020-21 sub-period carries the result")
    if not checks["beats_bil_10bp"]:
        reasons.append("10bp CAGR does not beat BIL")
    if not checks["placebo_95"]:
        reasons.append("the placebo percentile is below 95%")
    if not reasons:
        reasons.append("all pre-registered checks passed")
    out["verdict"] = {
        "checks": checks, "n_checks_passed": int(sum(checks.values())),
        "status": "passed_dev" if all(checks.values()) else "retired",
        "reason": "; ".join(reasons),
        "volume_high_vs_low": {"difference_pp": diff * 100 if diff is not None else None,
                               "one_sided_p": diff_p},
        "no_volume_control_sharpe": nv.get("sharpe"),
    }
    out["status"] = out["verdict"]["status"]

    (HERE / "result.json").write_text(json.dumps(out, indent=2, default=float))
    print(f"events {out['diagnostics']['events']}  entries {out['diagnostics']['entries']}  "
          f"exposure {exp_dev*100:.2f}%")
    for tag in ("1bp", "5bp", "10bp"):
        d = out["windows"]["dev"][tag]
        print(f"  {tag:4s} CAGR {d['cagr']*100:6.2f}%  DD {d['max_drawdown']*100:5.2f}%  "
              f"Sharpe {d['sharpe']:4.2f}  fills {d['fills']:3d}")
    print(f"  h5 mean {h5.get('mean', float('nan'))*100:+.3f}%  t {h5.get('t', float('nan')):.2f}")
    print(f"  volume high {hv['high'].get('mean', float('nan'))*100:+.2f}% (n={hv['high'].get('n')}) "
          f"vs low {hv['low'].get('mean', float('nan'))*100:+.2f}% (n={hv['low'].get('n')})")
    print("  subperiods: " + "  ".join(f"{k} {v['cagr']*100:+.1f}%" for k, v in sub.items()))
    print("  event dates:", ", ".join(out["diagnostics"]["event_dates"]))
    print("  entry dates:", ", ".join(out["diagnostics"]["entry_dates"]))
    print("  verdict:", out["verdict"])
    print("wrote", HERE / "result.json")


if __name__ == "__main__":
    main()
