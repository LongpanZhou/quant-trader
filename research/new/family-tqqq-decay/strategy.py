"""family-tqqq-decay -- TQQQ-vs-3x-QQQ realised decay timing.

Primary object: the realised log-return shortfall of TQQQ against a 3x daily
QQQ synthetic, measured as ``3 * r_QQQ - r_TQQQ`` and scaled by its own
252-session structural level.  When the recent decay is materially below its
structural level the leveraged fund is cheap per unit of trend; when decay is
accelerating the book moves to QQQ or BIL.

Decision clock: all inputs use closes through session t; the target is executed
at the first bar open of t+1.  No 2024-2026 data is used or inspected.

Run ``python strategy.py`` from this directory to regenerate ``result.json``.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import harness

SLUG = "family-tqqq-decay"
FAMILY = "tqqq-decay"
PRIMARY = "realised TQQQ-vs-3x-QQQ compounding decay relative to its structural level"

PARAMS = {
    "fast_window": 21,
    "slow_window": 252,
    "tqqq_threshold": -0.10,   # decay at least 10% below its structural level
    "qqq_threshold": 0.20,     # up to 20% above the structural level -> QQQ
}

# Pre-registered 8 cells: fast window, slow window, TQQQ threshold.
PLATEAU = [
    {"fast_window": 10, "slow_window": 252, "tqqq_threshold": -0.10},
    {"fast_window": 21, "slow_window": 252, "tqqq_threshold": -0.10},
    {"fast_window": 42, "slow_window": 252, "tqqq_threshold": -0.10},
    {"fast_window": 21, "slow_window": 189, "tqqq_threshold": -0.10},
    {"fast_window": 21, "slow_window": 252, "tqqq_threshold": -0.20},
    {"fast_window": 21, "slow_window": 252, "tqqq_threshold": 0.00},
    {"fast_window": 10, "slow_window": 252, "tqqq_threshold": 0.00},
    {"fast_window": 42, "slow_window": 252, "tqqq_threshold": 0.00},
]


def _rolling_mean(x: np.ndarray, win: int) -> np.ndarray:
    out = np.full(len(x), np.nan)
    cs = np.concatenate([[0.0], np.cumsum(x)])
    for i in range(win, len(x)):
        out[i] = (cs[i] - cs[i - win]) / win
    return out


def make_targets(dates, closes: np.ndarray, params: dict | None = None) -> np.ndarray:
    p = dict(PARAMS)
    if params:
        p.update(params)
    nd = len(dates)
    rq = np.diff(np.log(closes[:, 0]))
    rt = np.diff(np.log(closes[:, 1]))
    drag = np.concatenate([[0.0], 3.0 * rq - rt])
    fast = _rolling_mean(drag, int(p["fast_window"]))
    slow = _rolling_mean(drag, int(p["slow_window"]))
    ratio = fast / np.maximum(slow, 1e-5) - 1.0

    w = np.zeros((nd, 3))
    w[:, 2] = 1.0
    qqq = ratio < p["qqq_threshold"]
    w[qqq] = np.array([1.0, 0.0, 0.0])
    tqqq = ratio < p["tqqq_threshold"]
    w[tqqq] = np.array([0.0, 1.0, 0.0])
    return w


def build_weights(ts, o, c, params: dict | None = None) -> np.ndarray:
    dates, closes = harness.daily_closes(ts, c)
    daily = make_targets(dates, closes, params)
    if len(ts) == len(dates):
        return daily
    return harness.expand(ts, daily)


def _plateau(ts, o, c, dates, closes) -> list[dict]:
    out = []
    for cell in PLATEAU:
        w = harness.expand(ts, make_targets(dates, closes, cell))
        st = harness.metrics(harness.simulate(ts, o, c, w, bp=1.0))
        out.append({
            "cell": dict(cell),
            "cagr": st["cagr"], "max_drawdown": st["max_drawdown"],
            "sharpe": st["sharpe"], "fills": st["fills"],
            "turnover": st["turnover"],
        })
    return out


def main() -> None:
    ts, o, c = harness.load_panel()
    dates, closes = harness.daily_closes(ts, c)
    daily = make_targets(dates, closes)
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
        "params": dict(PARAMS),
        "stats": ev["stats"], "events": ev["events"],
        "yearly": ev["yearly"], "subperiods": ev["subperiods"],
        "corr_winners": ev["corr_winners"],
        "corr_range": [min(ev["corr_winners"].values()),
                       max(ev["corr_winners"].values())],
        "avg_weights": ev["avg_weights"],
        "static_avg_weights": ev["static_avg_weights"],
        "plateau": _plateau(ts, o, c, dates, closes),
        "placebo": ev["placebo"],
        "kill_checks": kills, "verdict": verdict,
        "timing": ("Diagnostic drag uses close-to-close returns through session "
                   "t; target executed at the first bar open of t+1; 2% band."),
        "notes": ("Drag is measured on the actual TQQQ and QQQ adjusted closes, "
                  "not on a variance model. It embeds 3x variance drag plus "
                  "financing/tracking noise. No 2024-2026 rows are read."),
    }
    harness.write_result(Path(__file__).with_name("result.json"), payload)
    print(f"{SLUG}: {harness.summary_line(st)}")
    print("  10bp:", harness.summary_line(ev["stats"]["10bp"]))
    print("  corr range", payload["corr_range"], "verdict", verdict)
    print("  kills", [k for k, v in kills.items() if v])


if __name__ == "__main__":
    main()
