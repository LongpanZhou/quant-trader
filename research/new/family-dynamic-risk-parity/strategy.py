"""family-dynamic-risk-parity -- rolling covariance risk-contribution allocator.

Primary object: the risk-contribution vector of a long-only QQQ/TQQQ/BIL book.
The optimiser equalises the risk contribution of QQQ and TQQQ from a 63-session
covariance estimate; BIL is the residual asset.  With a near-singular covariance
matrix (TQQQ is 3x QQQ, correlation ~0.99) the equal-risk solution collapses to
a slow-moving 75/25 QQQ/TQQQ mix, which is the central empirical finding of this
family.

Decision clock: covariance uses daily log returns through session t; the target
is executed at the first bar open of t+1.

Run ``python strategy.py`` from this directory to regenerate ``result.json``.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import harness

SLUG = "family-dynamic-risk-parity"
FAMILY = "dynamic-risk-parity"
PRIMARY = "rolling covariance risk-contribution vector (equal-risk QQQ/TQQQ sleeve)"

PARAMS = {
    "window": 63,
    "risk_budget_tqqq": 0.50,   # TQQQ share of the risky sleeve's risk
}

PLATEAU = [
    {"window": 21, "risk_budget_tqqq": 0.50},
    {"window": 42, "risk_budget_tqqq": 0.50},
    {"window": 63, "risk_budget_tqqq": 0.50},
    {"window": 126, "risk_budget_tqqq": 0.50},
    {"window": 252, "risk_budget_tqqq": 0.50},
    {"window": 63, "risk_budget_tqqq": 0.40},
    {"window": 63, "risk_budget_tqqq": 0.60},
    {"window": 63, "risk_budget_tqqq": 0.70},
]


def _erc_two_asset(sigma_t: float, sigma_q: float, rho: float,
                   budget_t: float) -> tuple[float, float]:
    """Long-only two-asset ERC weights for a TQQQ risk budget.

    Solves RC_T / RC_Q = (1 - b) / b for t = w_Q / w_T.  The solution is the
    positive root of a quadratic; a 1e-12 ridge keeps the covariance usable.
    """
    s1 = max(float(sigma_t), 1e-12)
    s2 = max(float(sigma_q), 1e-12)
    rho = float(np.clip(rho, -0.999, 0.999))
    target = (1.0 - budget_t) / budget_t
    a = s2 * s2
    bcoef = rho * s1 * s2 * (1.0 - target)
    c = -target * s1 * s1
    disc = max(bcoef * bcoef - 4.0 * a * c, 0.0)
    t = (-bcoef + np.sqrt(disc)) / (2.0 * a)
    w_t = 1.0 / (1.0 + t)
    return w_t, 1.0 - w_t


def make_targets(dates, closes: np.ndarray, params: dict | None = None) -> np.ndarray:
    p = dict(PARAMS)
    if params:
        p.update(params)
    nd = len(dates)
    win = int(p["window"])
    lr = np.diff(np.log(closes), axis=0)
    w = np.zeros((nd, 3))
    # Before the covariance is available the book is QQQ, not cash, so the
    # comparison against TQQQ is not helped by a long warm-up in BIL.
    w[:, 0] = 1.0
    for i in range(win, nd):
        x = lr[i - win:i]
        s = np.cov(x.T, ddof=0)
        st = float(np.sqrt(max(s[1, 1], 1e-12)))
        sq = float(np.sqrt(max(s[0, 0], 1e-12)))
        rho = float(s[0, 1] / (st * sq))
        wt, wq = _erc_two_asset(st, sq, rho, float(p["risk_budget_tqqq"]))
        w[i, 0] = wq
        w[i, 1] = wt
        w[i, 2] = 0.0
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
        "timing": ("Covariance uses daily log returns through session t; target "
                   "executed at the first bar open of t+1; 2% band."),
        "notes": ("BIL is excluded from the risk budget because a near-zero-vol "
                  "asset would otherwise absorb almost all of the capital. The "
                  "risky sleeve is QQQ/TQQQ. No 2024-2026 rows are read."),
    }
    harness.write_result(Path(__file__).with_name("result.json"), payload)
    print(f"{SLUG}: {harness.summary_line(st)}")
    print("  10bp:", harness.summary_line(ev["stats"]["10bp"]))
    print("  corr range", payload["corr_range"], "verdict", verdict)
    print("  kills", [k for k, v in kills.items() if v])


if __name__ == "__main__":
    main()
