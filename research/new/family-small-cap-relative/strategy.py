"""Family `small-cap-relative` -- IWM/QQQ relative leadership on TQQQ/QQQ/BIL.

Primary object: the volatility-normalised 20-session total-return spread of
small caps (IWM) over large-cap Nasdaq (QQQ).  When small caps are not
underperforming by more than half a standard deviation, the regime is
risk-on and the strategy holds TQQQ.  When the spread breaks down, it steps
down to QQQ (large-cap defensive); the ladder variant adds a BIL rung on a
severe breakdown.

For each session ``k`` the signal uses both adjusted closes through ``k``.
The target is written at ``k``'s 15:59 close and filled at ``k+1``'s 09:30
open by ``research/bt.py``.  No same-day fill, weights >= 0, sum <= 1.

Primary cell: 20-session z > -0.5 -> TQQQ, else QQQ.
Plateau: 2 z-normalisation windows x 2 thresholds x 2 mappings = 8 cells.
The 60-session lookback is an explicit ablation.

Run from the repo root:
    $env:PYTHONPATH = "C:/Users/27175/AppData/Local/Temp/opencode/pylibs"
    python research/new/family-small-cap-relative/strategy.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[2] / "research"))
import cross_asset as ca  # noqa: E402

SLUG = "family-small-cap-relative"
FAMILY = "small-cap-relative"
PRIMARY_OBJECT = "IWM/QQQ 20-session relative total-return z-score"
LOOKBACK = 20

PARAMS = {"lookback": LOOKBACK, "norm_window": 252, "threshold": -0.50,
          "mapping": "binary"}

GRID = [
    {"lookback": LOOKBACK, "norm_window": 126, "threshold": -0.75, "mapping": "binary"},
    {"lookback": LOOKBACK, "norm_window": 126, "threshold": -0.50, "mapping": "binary"},
    {"lookback": LOOKBACK, "norm_window": 126, "threshold": -0.75, "mapping": "ladder"},
    {"lookback": LOOKBACK, "norm_window": 126, "threshold": -0.50, "mapping": "ladder"},
    {"lookback": LOOKBACK, "norm_window": 252, "threshold": -0.75, "mapping": "binary"},
    {"lookback": LOOKBACK, "norm_window": 252, "threshold": -0.50, "mapping": "binary"},
    {"lookback": LOOKBACK, "norm_window": 252, "threshold": -0.75, "mapping": "ladder"},
    {"lookback": LOOKBACK, "norm_window": 252, "threshold": -0.50, "mapping": "ladder"},
]

ABLATIONS = [
    {"lookback": 60, "norm_window": 252, "threshold": -0.50, "mapping": "binary"},
    {"lookback": 60, "norm_window": 252, "threshold": -0.50, "mapping": "ladder"},
]


def daily_targets(daily, params: dict):
    z = ca.relative_z(daily, "IWM", "QQQ", int(params["lookback"]),
                      norm_window=int(params["norm_window"]))
    return ca.map_relative(z, float(params["threshold"]), params["mapping"])


def build_targets(ts, params: dict | None = None):
    p = dict(PARAMS)
    if params:
        p.update(params)
    daily = ca.daily_frame(ts, ["IWM", "QQQ"])
    return ca.targets_for_sessions(ts, daily_targets(daily, p))


def build_weights(ts, opens, closes, params: dict | None = None):
    """Public interface: bar-level (n, 3) weight matrix, next-open fills."""
    return ca.weights(ts, build_targets(ts, params))


def _run_cell(ts, o, c, daily, cell, n_placebo=60):
    targets = ca.targets_for_sessions(ts, daily_targets(daily, cell))
    ev = ca.evaluate(ts, o, c, targets, n_placebo=n_placebo)
    st = ev["stats"]["1bp"]
    passed = bool(st["cagr"] > ca.TQQQ_BAR_CAGR and st["max_drawdown"] < ca.TQQQ_BAR_DD)
    return {
        "params": dict(cell),
        "1bp": st,
        "5bp": ev["stats"]["5bp"],
        "10bp": ev["stats"]["10bp"],
        "events": ev["events"],
        "pass": passed,
        "_ev": ev,
    }


def main() -> None:
    ts, o, c = ca.load_panel()
    daily = ca.daily_frame(ts, ["IWM", "QQQ"])

    grid = []
    primary_ev = None
    for i, cell in enumerate(GRID, start=1):
        row = _run_cell(ts, o, c, daily, cell)
        ev = row.pop("_ev")
        grid.append({"cell": i, **row})
        if cell == PARAMS:
            primary_ev = ev
    if primary_ev is None:
        raise RuntimeError("primary cell is not in GRID")

    ablations = []
    for cell in ABLATIONS:
        row = _run_cell(ts, o, c, daily, cell)
        row.pop("_ev")
        ablations.append(row)

    n_pass = sum(r["pass"] for r in grid)
    kills = ca.kill_checks(primary_ev, n_pass)
    st = primary_ev["stats"]["1bp"]

    i0 = ca.bt.start_index(ts, ca.START)
    bench_tqqq = ca.bt.benchmark(c[:, 1][i0:], ts[i0:], ca.BARS_PER_YEAR)
    bench_qqq = ca.bt.benchmark(c[:, 0][i0:], ts[i0:], ca.BARS_PER_YEAR)
    max_corr_slug = max(primary_ev["corr_winners"], key=primary_ev["corr_winners"].get)
    cut_tests = [ca.cut_test(ts, o, c, lambda a, b, d: build_weights(a, b, d))]

    payload = {
        "slug": SLUG,
        "family": FAMILY,
        "primary_object": PRIMARY_OBJECT,
        "status": "passed" if (st["cagr"] > ca.TQQQ_BAR_CAGR
                              and st["max_drawdown"] < ca.TQQQ_BAR_DD) else "negative_result",
        "passed": bool(st["cagr"] > ca.TQQQ_BAR_CAGR
                       and st["max_drawdown"] < ca.TQQQ_BAR_DD),
        "exploratory": True,
        "exploratory_reason": (
            "The primary cell was chosen after daily-bar diagnostics on the "
            "development window; the 8-cell grid is a robustness probe, not a "
            "clean out-of-sample pre-registration."
        ),
        "hypothesis": (
            "Small-cap leadership relative to large-cap Nasdaq is a risk-on "
            "signal. When IWM's 20-session total return is not more than half a "
            "standard deviation below QQQ's, hold TQQQ; when the spread breaks "
            "down, rotate to large-cap defensive QQQ (or BIL on a severe break)."
        ),
        "universe": ["TQQQ", "QQQ", "BIL", "IWM (signal only, never held)"],
        "window": {"dev": [ca.START, ca.END], "holdout": "not loaded"},
        "benchmarks": {"tqqq": {k: float(v) for k, v in bench_tqqq.items()},
                       "qqq": {k: float(v) for k, v in bench_qqq.items()},
                       "published_bar": {"cagr": ca.TQQQ_BAR_CAGR,
                                         "max_drawdown": ca.TQQQ_BAR_DD}},
        "params": dict(PARAMS),
        "primary": {
            "dev": {"1bp": st, "5bp": primary_ev["stats"]["5bp"],
                    "10bp": primary_ev["stats"]["10bp"]},
            "events": primary_ev["events"],
            "avg_weights": primary_ev["avg_weights"],
            "yearly": primary_ev["yearly"],
            "subperiods": primary_ev["subperiods"],
            "corr_winners": primary_ev["corr_winners"],
            "corr_range": [min(primary_ev["corr_winners"].values()),
                           max(primary_ev["corr_winners"].values())],
            "corr_max_name": max_corr_slug,
            "placebo": primary_ev["placebo"],
            "static_blend_same_avg": primary_ev["static_avg_weights"],
        },
        "grid": grid,
        "ablations": ablations,
        "plateau": {"cells": len(GRID), "pass_cells": int(n_pass),
                    "share": float(n_pass / len(GRID))},
        "kill_checks": kills,
        "cut_tests": cut_tests,
        "verdict": "dev_pass" if not any(kills.values()) else "fail",
        "notes": [
            "Both legs use total-return adjusted closes through session k; the "
            "target is written at k's 15:59 close and filled at k+1's open.",
            "The z-score normalises by the trailing 126/252-session standard "
            "deviation of the same 20-session spread (minimum 120 sessions).",
            "The 2024-2026 holdout is excluded by a Parquet date filter on every "
            "external and daily read.",
            "No price-trend gate, volatility targeting, drawdown event, calendar "
            "clock, opening-range/close-flow, ML or additional relative-strength "
            "ratio gate.",
            "Equity is marked on every 1-minute bar; costs are 1/5/10 bp.",
        ],
    }
    ca.write_result(HERE / "result.json", payload)

    print(f"{SLUG}: {ca.summary_line(st)}")
    print(f"  events {primary_ev['events']}  avg weights {primary_ev['avg_weights']}")
    print(f"  plateau {n_pass}/8  corr winners "
          f"{min(primary_ev['corr_winners'].values()):.2f}.."
          f"{max(primary_ev['corr_winners'].values()):.2f} "
          f"(max {max_corr_slug})  placebo pct "
          f"{primary_ev['placebo']['cagr_percentile_of_real']:.2f}")
    print(f"  kills: {[k for k, v in kills.items() if v]}")
    print("  grid (1bp):")
    for row in grid:
        s = row["1bp"]
        print(f"   {row['cell']} {row['params']}  CAGR {s['cagr']*100:6.2f}%  "
              f"DD {s['max_drawdown']*100:5.1f}%  Sharpe {s['sharpe']:.2f}  "
              f"fills {s['fills']}  {'PASS' if row['pass'] else 'fail'}")
    print("  ablations (1bp):")
    for row in ablations:
        s = row["1bp"]
        print(f"   {row['params']}  CAGR {s['cagr']*100:6.2f}%  "
              f"DD {s['max_drawdown']*100:5.1f}%  Sharpe {s['sharpe']:.2f}  "
              f"{'PASS' if row['pass'] else 'fail'}")


if __name__ == "__main__":
    main()
