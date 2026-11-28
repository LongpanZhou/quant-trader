"""Family `rates-volatility` -- MOVE rates-volatility regime on TQQQ / QQQ / BIL.

Primary object: the level of rates volatility (the ICE BofA MOVE index), not
equity volatility.  The hypothesis is that a calm rates-vol regime is a
risk-on environment for long-duration growth equity (TQQQ), while a rates-vol
spike is a de-risking signal (BIL).  A 20-session change in MOVE is the second,
faster measure and is reported as an ablation, not as a plateau axis.

For each session ``k`` the signal uses MOVE's daily close through ``k``.  The
target is written at ``k``'s 15:59 close and filled at ``k+1``'s 09:30 open by
``research/bt.py``; ``research/external.daily_targets_to_weights`` performs the
bar mapping.  No same-day fill, no leverage beyond 100% TQQQ, weights >= 0 and
sum <= 1.

Primary cell: MOVE / 252-session median - 1 < 0 -> TQQQ, else BIL.
Plateau: 2 median windows x 2 thresholds x 2 mappings = 8 cells.

Run from the repo root:
    $env:PYTHONPATH = "C:/Users/27175/AppData/Local/Temp/opencode/pylibs"
    python research/new/family-rates-volatility/strategy.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[2] / "research"))
import cross_asset as ca  # noqa: E402

SLUG = "family-rates-volatility"
FAMILY = "rates-volatility"
PRIMARY_OBJECT = "MOVE rates-volatility level (20-session change as ablation)"

PARAMS = {
    "measure": "level",     # "level" | "chg20"
    "median_window": 252,
    "threshold": 0.0,       # calm if signal < threshold
    "mapping": "binary",    # "binary" (TQQQ/BIL) | "ladder" (TQQQ/QQQ/BIL)
}
BAND_LEVEL = 0.20
BAND_CHG = 0.10

GRID = [
    {"measure": "level", "median_window": 126, "threshold": 0.0, "mapping": "binary"},
    {"measure": "level", "median_window": 126, "threshold": 0.0, "mapping": "ladder"},
    {"measure": "level", "median_window": 126, "threshold": BAND_LEVEL, "mapping": "binary"},
    {"measure": "level", "median_window": 126, "threshold": BAND_LEVEL, "mapping": "ladder"},
    {"measure": "level", "median_window": 252, "threshold": 0.0, "mapping": "binary"},
    {"measure": "level", "median_window": 252, "threshold": 0.0, "mapping": "ladder"},
    {"measure": "level", "median_window": 252, "threshold": BAND_LEVEL, "mapping": "binary"},
    {"measure": "level", "median_window": 252, "threshold": BAND_LEVEL, "mapping": "ladder"},
]

ABLATIONS = [
    {"measure": "chg20", "median_window": 252, "threshold": 0.0, "mapping": "binary"},
    {"measure": "chg20", "median_window": 252, "threshold": 0.0, "mapping": "ladder"},
]


def signal(daily: pd.DataFrame, params: dict) -> tuple[pd.Series, float]:
    move = daily["MOVE"].astype(float)
    win = int(params.get("median_window", 252))
    if params["measure"] == "level":
        med = move.rolling(win, min_periods=max(60, win // 2)).median()
        s = move / med - 1.0
        band = BAND_LEVEL
    elif params["measure"] == "chg20":
        s = move / move.shift(20) - 1.0
        band = BAND_CHG
    else:
        raise ValueError(params["measure"])
    return s, float(band)


def daily_targets(daily: pd.DataFrame, params: dict) -> pd.DataFrame:
    """One target row per daily date, decided at that date's close."""
    s, band = signal(daily, params)
    th = float(params["threshold"])
    tq = (s < th).to_numpy()
    out = np.zeros((len(daily), 3))
    if params["mapping"] == "binary":
        out[tq] = (0.0, 1.0, 0.0)          # calm   -> TQQQ
        out[~tq] = (0.0, 0.0, 1.0)         # spike  -> BIL
    elif params["mapping"] == "ladder":
        mid = (s < th + band).to_numpy()
        out[tq] = (0.0, 1.0, 0.0)          # calm       -> TQQQ
        out[~tq & mid] = (1.0, 0.0, 0.0)   # warming up -> QQQ
        out[~mid] = (0.0, 0.0, 1.0)        # spike      -> BIL
    else:
        raise ValueError(params["mapping"])
    return pd.DataFrame(out, index=daily.index, columns=("QQQ", "TQQQ", "BIL"))


def build_targets(ts, params: dict | None = None) -> np.ndarray:
    p = dict(PARAMS)
    if params:
        p.update(params)
    daily = ca.daily_frame(ts, ["MOVE"])
    return ca.targets_for_sessions(ts, daily_targets(daily, p))


def build_weights(ts, opens, closes, params: dict | None = None) -> np.ndarray:
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
    daily = ca.daily_frame(ts, ["MOVE"])

    grid = []
    primary_ev = None
    for i, cell in enumerate(GRID, start=1):
        row = _run_cell(ts, o, c, daily, cell)
        ev = row.pop("_ev")
        row = {"cell": i, **row}
        grid.append(row)
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

    payload = {
        "slug": SLUG,
        "family": FAMILY,
        "primary_object": PRIMARY_OBJECT,
        "hypothesis": (
            "A calm rates-volatility regime (MOVE below its 252-session median) "
            "is risk-on for long-duration growth equity, so hold TQQQ; a rates-vol "
            "spike is a de-risking signal, so hold BIL. The 20-session MOVE change "
            "is the faster alternative and is tested as an ablation."
        ),
        "universe": ["TQQQ", "QQQ", "BIL", "MOVE (signal only, never held)"],
        "window": {"dev": [ca.START, ca.END], "holdout": "not loaded"},
        "benchmarks": {"tqqq": {k: float(v) for k, v in bench_tqqq.items()},
                       "qqq": {k: float(v) for k, v in bench_qqq.items()},
                       "published_bar": {"cagr": ca.TQQQ_BAR_CAGR,
                                         "max_drawdown": ca.TQQQ_BAR_DD}},
        "params": dict(PARAMS, band_level=BAND_LEVEL, band_chg=BAND_CHG),
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
        "verdict": "dev_pass" if not any(kills.values()) else "fail",
        "notes": [
            "MOVE's daily close is used through session k; the target is written "
            "at k's 15:59 close and filled at k+1's open, so there is no same-day fill.",
            "The 2024-2026 holdout is excluded by a Parquet date filter on every "
            "external and daily read.",
            "No price-trend gate, volatility targeting, drawdown event, calendar "
            "clock, opening-range/close-flow, ML or relative-strength ratio gate.",
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
