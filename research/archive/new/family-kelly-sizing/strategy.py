"""family-kelly-sizing -- fractional Kelly sizing of the TQQQ/QQQ decision.

Primary object: the rolling Kelly fraction.  Two edges are estimated from daily
returns:

* ``f_q``   = mean(r_QQQ) / var(r_QQQ)          -- QQQ versus cash;
* ``f_lev`` = argmax_f E[log(1 + f (r_TQQQ - r_QQQ))] -- the TQQQ-over-QQQ
  overlay, evaluated with a fourth-order expansion of the log growth:

      g(f) = f*mu - 0.5*f^2*var + (1/3)*f^3*m3 - 0.25*f^4*m4

  so negative skew and fat tails reduce the Kelly fraction relative to the
  Gaussian ``mu/var``.  The leverage weight is ``clip(kappa * f_lev, 0, 1)``;
  QQQ takes the rest.  If ``f_q <= 0`` the QQQ edge itself is negative and the
  book goes to BIL.

The headline averages the 126/168/210-session estimates and uses
``kappa = 0.9``.  This is fractional Kelly with a hard 100% TQQQ cap.

Decision clock: moments use closes through session t; the target is executed at
the first bar open of t+1.

Run ``python strategy.py`` from this directory to regenerate ``result.json``.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import harness

SLUG = "family-kelly-sizing"
FAMILY = "kelly-sizing"
PRIMARY = ("rolling Kelly fraction from QQQ/TQQQ mean, variance, skew and "
           "kurtosis (fourth-order log-growth expansion)")

PARAMS = {
    "windows": (126, 168, 210),
    "kappa": 0.90,
    "tqqq_cap": 1.00,
    "grid_points": 201,
}

PLATEAU = [
    {"windows": (126,), "kappa": 0.80},
    {"windows": (126,), "kappa": 0.90},
    {"windows": (168,), "kappa": 0.80},
    {"windows": (168,), "kappa": 0.90},
    {"windows": (210,), "kappa": 0.80},
    {"windows": (210,), "kappa": 0.90},
    {"windows": (126, 168, 210), "kappa": 0.80},
    {"windows": (126, 168, 210), "kappa": 0.90},
]


def _moments(returns: np.ndarray):
    mu = float(returns.mean())
    d = returns - mu
    var = float((d * d).mean())
    m3 = float((d ** 3).mean())
    m4 = float((d ** 4).mean())
    return mu, var, m3, m4


def _overlay_kelly(ex: np.ndarray, grid: np.ndarray) -> float:
    """Fourth-order log-growth Kelly fraction on [0, 1]."""
    mu, var, m3, m4 = _moments(ex)
    g = (grid * mu - 0.5 * (grid ** 2) * var
         + (1.0 / 3.0) * (grid ** 3) * m3
         - 0.25 * (grid ** 4) * m4)
    return float(grid[int(np.argmax(g))])


def make_targets(dates, closes: np.ndarray, params: dict | None = None) -> np.ndarray:
    p = dict(PARAMS)
    if params:
        p.update(params)
    nd = len(dates)
    rets = np.diff(closes, axis=0) / closes[:-1]      # simple returns
    grid = np.linspace(0.0, 1.0, int(p["grid_points"]))
    acc_q = np.zeros(nd)
    acc_l = np.zeros(nd)
    cnt = np.zeros(nd)
    for win in p["windows"]:
        win = int(win)
        for i in range(win, nd):
            x = rets[i - win:i]
            rq = x[:, 0]
            rt = x[:, 1]
            mu_q, var_q, _, _ = _moments(rq)
            acc_q[i] += mu_q / var_q if var_q > 0 else -1.0
            acc_l[i] += _overlay_kelly(rt - rq, grid)
            cnt[i] += 1
    f_q = np.divide(acc_q, np.maximum(cnt, 1))
    f_lev = np.divide(acc_l, np.maximum(cnt, 1))

    w = np.zeros((nd, 3))
    w[:, 2] = 1.0
    valid = (cnt > 0) & (f_q > 0.0)
    wt = np.clip(float(p["kappa"]) * f_lev[valid], 0.0, float(p["tqqq_cap"]))
    w[valid, 1] = wt
    w[valid, 0] = 1.0 - wt
    w[valid, 2] = 0.0
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
            "cell": {"windows": list(cell["windows"]), "kappa": cell["kappa"]},
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
        "params": {k: (list(v) if isinstance(v, tuple) else v)
                   for k, v in PARAMS.items()},
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
        "timing": ("Moments use daily simple returns through session t; target "
                   "executed at the first bar open of t+1; 2% band."),
        "notes": ("The Kelly fraction is the maximiser of a fourth-order "
                  "log-growth expansion on the empirical overlay sample, so "
                  "skew and kurtosis enter explicitly. Fractional cap 0.9 and "
                  "a hard 100% TQQQ weight cap. No 2024-2026 rows are read."),
    }
    harness.write_result(Path(__file__).with_name("result.json"), payload)
    print(f"{SLUG}: {harness.summary_line(st)}")
    print("  10bp:", harness.summary_line(ev["stats"]["10bp"]))
    print("  corr range", payload["corr_range"], "verdict", verdict)
    print("  kills", [k for k, v in kills.items() if v])


if __name__ == "__main__":
    main()
