"""family-beta-rotation -- QQQ-vs-SPY beta compression/expansion rotation.

Primary object: the rolling beta of QQQ to SPY, not relative-strength momentum.
The strategy holds TQQQ only when beta is compressed in its own recent history
and downside beta does not dominate upside beta; otherwise QQQ, and BIL when
beta is in the top of its one-year range and asymmetry is unfavourable.

Decision clock: a target is set from the close of session t (all inputs use
returns through that close) and executed at the next session's first bar open.
The backtester's 2% band and next-open fill rule are unchanged.

Run ``python strategy.py`` from this directory to regenerate ``result.json``.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# run_holdout.py loads this file by path without adding its directory to
# sys.path; make the local harness importable in both entry points.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness

SLUG = "family-beta-rotation"
FAMILY = "beta-rotation"
PRIMARY = "rolling QQQ-vs-SPY beta (level percentile and up/down asymmetry)"

PARAMS = {
    "beta_windows": (42, 63),
    "pct_lookback": 252,
    "pct_tqqq": 0.60,
    "pct_qqq": 0.80,
    "asym_window": 126,
    "asym_tqqq": 0.00,
    "asym_qqq": 0.15,
}

# 2 x 2 x 2 pre-registered grid: beta estimate, compression threshold,
# asymmetry threshold.  The primary cell is (blend, 0.60, 0.00).
PLATEAU = [
    {"beta_windows": (42, 63), "pct_tqqq": 0.50, "asym_tqqq": 0.00},
    {"beta_windows": (42, 63), "pct_tqqq": 0.60, "asym_tqqq": 0.00},
    {"beta_windows": (42, 63), "pct_tqqq": 0.50, "asym_tqqq": 0.05},
    {"beta_windows": (42, 63), "pct_tqqq": 0.60, "asym_tqqq": 0.05},
    {"beta_windows": (63,), "pct_tqqq": 0.50, "asym_tqqq": 0.00},
    {"beta_windows": (63,), "pct_tqqq": 0.60, "asym_tqqq": 0.00},
    {"beta_windows": (63,), "pct_tqqq": 0.50, "asym_tqqq": 0.05},
    {"beta_windows": (63,), "pct_tqqq": 0.60, "asym_tqqq": 0.05},
]


def _rolling_beta(rq: np.ndarray, rs: np.ndarray, win: int, nd: int) -> np.ndarray:
    out = np.full(nd, np.nan)
    for i in range(win, nd):
        x = rs[i - win:i]
        y = rq[i - win:i]
        vx = float(x.var())
        if vx > 0:
            out[i] = float(np.cov(y, x, ddof=0)[0, 1]) / vx
    return out


def _pct_rank(beta: np.ndarray, lookback: int) -> np.ndarray:
    nd = len(beta)
    pct = np.full(nd, np.nan)
    for i in range(lookback, nd):
        hist = beta[i - lookback:i]
        hist = hist[np.isfinite(hist)]
        if len(hist) > 100:
            pct[i] = float((hist < beta[i]).mean())
    return np.nan_to_num(pct, nan=0.5)


def _updown_beta(rq: np.ndarray, rs: np.ndarray, win: int, nd: int):
    bu = np.full(nd, np.nan)
    bd = np.full(nd, np.nan)
    for i in range(win, nd):
        y = rq[i - win:i]
        x = rs[i - win:i]
        up = x > 0
        dn = x < 0
        if int(up.sum()) > 5 and float(x[up].var()) > 0:
            bu[i] = float(np.cov(y[up], x[up], ddof=0)[0, 1]) / float(x[up].var())
        if int(dn.sum()) > 5 and float(x[dn].var()) > 0:
            bd[i] = float(np.cov(y[dn], x[dn], ddof=0)[0, 1]) / float(x[dn].var())
    return bu, bd


def make_targets(dates, closes: np.ndarray, spy: pd.Series,
                 params: dict | None = None) -> np.ndarray:
    p = dict(PARAMS)
    if params:
        p.update(params)
    nd = len(dates)
    rq = np.diff(np.log(closes[:, 0]))
    rs = np.diff(np.log(spy.to_numpy(dtype=float)))
    betas = [_rolling_beta(rq, rs, int(w), nd) for w in p["beta_windows"]]
    stack = np.vstack(betas)
    cnt = np.isfinite(stack).sum(axis=0)
    beta = np.nansum(stack, axis=0) / np.maximum(cnt, 1)
    beta[cnt == 0] = np.nan
    pct = _pct_rank(beta, int(p["pct_lookback"]))
    bu, bd = _updown_beta(rq, rs, int(p["asym_window"]), nd)
    asym = np.nan_to_num(bu - bd, nan=0.0)

    w = np.zeros((nd, 3))
    w[:, 2] = 1.0                       # BIL by default
    qqq = (pct < p["pct_qqq"]) | (asym < p["asym_qqq"])
    w[qqq] = np.array([1.0, 0.0, 0.0])
    tqqq = (pct < p["pct_tqqq"]) & (asym < p["asym_tqqq"])
    w[tqqq] = np.array([0.0, 1.0, 0.0])
    return w


def build_weights(ts, o, c, params: dict | None = None) -> np.ndarray:
    dates, closes = harness.daily_closes(ts, c)
    spy = harness.load_spy(dates)
    daily = make_targets(dates, closes, spy, params)
    if len(ts) == len(dates):
        return daily          # daily panel: caller applies the next-open shift
    return harness.expand(ts, daily)


def _plateau(ts, o, c, dates, closes, spy) -> list[dict]:
    out = []
    for cell in PLATEAU:
        w = harness.expand(ts, make_targets(dates, closes, spy, cell))
        st = harness.metrics(harness.simulate(ts, o, c, w, bp=1.0))
        out.append({
            "cell": {k: (list(v) if isinstance(v, tuple) else v)
                     for k, v in cell.items()},
            "cagr": st["cagr"], "max_drawdown": st["max_drawdown"],
            "sharpe": st["sharpe"], "fills": st["fills"],
            "turnover": st["turnover"],
        })
    return out


def main() -> None:
    ts, o, c = harness.load_panel()
    dates, closes = harness.daily_closes(ts, c)
    spy = harness.load_spy(dates)
    daily = make_targets(dates, closes, spy)
    ev = harness.evaluate(ts, o, c, daily, n_placebo=100)
    st = ev["stats"]["1bp"]
    max_corr = max(ev["corr_winners"].values())
    kills = {
        "cagr_below_published_tqqq_bar": st["cagr"] <= 0.3672,
        "drawdown_above_tqqq": st["max_drawdown"] >= 0.8229,
        "cost_10bp_below_bar": ev["stats"]["10bp"]["cagr"] <= 0.3672,
        "placebo_below_90pct": ev["placebo"]["cagr_percentile_of_real"] < 0.90,
        "correlation_above_0.95": max_corr > 0.95,
        "fewer_than_100_fills": st["fills"] < 100,
        "fewer_than_30_events": ev["events"] < 30,
        "negative_subperiod": any(v["cagr"] < 0 for v in ev["subperiods"].values()),
        "static_blend_matches": (ev["static_avg_weights"]["cagr"] >= st["cagr"] - 0.01),
    }
    verdict = "dev_pass" if not any(kills.values()) else "fail"
    payload = {
        "slug": SLUG, "family": FAMILY, "primary_object": PRIMARY,
        "dev": ev["stats"]["1bp"],
        "windows": {"dev": {"1bp": ev["stats"]["1bp"],
                            "5bp": ev["stats"]["5bp"],
                            "10bp": ev["stats"]["10bp"]}},
        "window": {"dev": [harness.START, harness.END], "holdout": "not loaded"},
        "benchmark": {
            "tqqq_panel": {"cagr": 0.3581, "max_drawdown": 0.823, "sharpe": 0.80},
            "tqqq_published_bar": {"cagr": 0.3672, "max_drawdown": 0.8229,
                                   "sharpe": 0.82},
        },
        "params": {k: (list(v) if isinstance(v, tuple) else v)
                   for k, v in PARAMS.items()},
        "stats": ev["stats"], "events": ev["events"],
        "yearly": ev["yearly"], "subperiods": ev["subperiods"],
        "corr_winners": ev["corr_winners"],
        "corr_range": [min(ev["corr_winners"].values()),
                       max(ev["corr_winners"].values())],
        "avg_weights": ev["avg_weights"],
        "static_avg_weights": ev["static_avg_weights"],
        "plateau": _plateau(ts, o, c, dates, closes, spy),
        "placebo": ev["placebo"],
        "kill_checks": kills, "verdict": verdict,
        "timing": ("Signal uses daily closes through session t; target executed "
                   "at the first bar open of t+1; 2% band; long only."),
        "notes": ("Beta uses local SPY daily adjusted closes, filtered to the "
                  "requested panel end before use. No 2024-2026 rows are read "
                  "during the development run."),
    }
    harness.write_result(Path(__file__).with_name("result.json"), payload)
    print(f"{SLUG}: {harness.summary_line(st)}")
    print("  10bp:", harness.summary_line(ev["stats"]["10bp"]))
    print("  corr range", payload["corr_range"], "verdict", verdict)
    print("  kills", [k for k, v in kills.items() if v])


if __name__ == "__main__":
    main()
