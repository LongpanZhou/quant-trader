"""family-breadth -- equal-weight vs cap-weight breadth times TQQQ.

Primary object: the RSP/SPY relative return.  When equal-weight RSP keeps up
with or beats cap-weight SPY, the rally is broad and the strategy holds TQQQ.
When SPY pulls away from RSP, breadth is narrowing and the strategy holds QQQ
in the neutral band and BIL when narrowing is severe.

The signal is the average of the 20-day and 60-day relative-return z-scores,
each z-scored against its own trailing 252-session distribution.

Decision clock: RSP/SPY closes are 16:00 ET, the same session close used for
the decision; the target is filled at the next session's first bar open.
Long only, weights sum to 1, 2% band.

Run ``python strategy.py`` from this directory to regenerate ``result.json``.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ext_harness as H

SLUG = "family-breadth"
FAMILY = "breadth"
PRIMARY = "RSP/SPY 20/60-day relative-return z-score"

END = H.END

PARAMS = {
    "windows": (20, 60),
    "z_window": 252,
    "min_periods": 120,
    "tqqq_z": 0.50,
    "bil_z": -0.50,
}

# 8-cell sensitivity grid: the primary, three threshold neighbours at the
# 20/60 blend, and the 20-only / 60-only alternatives at two settings.
PLATEAU = [
    {"windows": (20, 60), "tqqq_z": 0.50, "bil_z": -0.50},
    {"windows": (20, 60), "tqqq_z": 0.50, "bil_z": -0.75},
    {"windows": (20, 60), "tqqq_z": 0.75, "bil_z": -0.50},
    {"windows": (20, 60), "tqqq_z": 0.75, "bil_z": -0.75},
    {"windows": (20,), "tqqq_z": 0.50, "bil_z": -0.50},
    {"windows": (20,), "tqqq_z": 0.75, "bil_z": -0.75},
    {"windows": (60,), "tqqq_z": 0.50, "bil_z": -0.50},
    {"windows": (60,), "tqqq_z": 0.75, "bil_z": -0.75},
]


def _score(ext: pd.DataFrame, windows) -> pd.Series:
    rel = np.log(ext["RSP"]) - np.log(ext["SPY"])
    parts = [H.rolling_z(rel.diff(int(w)), PARAMS["z_window"],
                         PARAMS["min_periods"])
             for w in windows]
    return sum(parts) / len(parts)


def make_targets(ext: pd.DataFrame, params: dict | None = None) -> np.ndarray:
    p = dict(PARAMS)
    if params:
        p.update(params)
    s = _score(ext, p["windows"])
    return H.state_weights(s, float(p["tqqq_z"]), float(p["bil_z"]))


def _limit(end):
    return pd.Timestamp(end) if end is not None else pd.Timestamp(END)


def _check_window(ts, limit) -> None:
    last = pd.Timestamp(ts[-1])
    if last.tzinfo is not None:
        last = last.tz_localize(None)
    if last.normalize() > limit:
        raise ValueError(
            "panel extends past the development window "
            f"{limit.date()}; 2024-2026 is not loaded")


def build_weights(ts, opens, closes, params: dict | None = None,
                  end=None) -> np.ndarray:
    """Minute weights; targets at session close t fill at t+1's open."""
    limit = _limit(end)
    _check_window(ts, limit)
    ext = H.aligned(ts, ["RSP", "SPY"], end=limit)
    return H.to_minutes(ts, make_targets(ext, params))


def main() -> None:
    ts, o, c = H.load_panel()
    ext = H.aligned(ts, ["RSP", "SPY"])
    targets = make_targets(ext)
    ev = H.evaluate(ts, o, c, targets, n_placebo=100)
    st = ev["stats"]["1bp"]
    kills = H.kill_checks(ev)
    plateau = H.plateau(ts, o, c,
                        lambda p: make_targets(ext, p), PLATEAU)
    causality = {
        "future_value_perturbation": H.perturb_audit(
            ext, make_targets, cutoff_offset=0),
        "close_to_next_open_mapping": H.mapping_audit(ts, targets),
    }
    ctrl_st, ctrl_ret = H.trend_control(ts, o, c, 0.50, -0.50)
    trend_control = {
        "name": "QQQ 20/60 momentum, same three-state map",
        "cagr": ctrl_st["cagr"],
        "max_drawdown": ctrl_st["max_drawdown"],
        "sharpe": ctrl_st["sharpe"],
        "corr_to_strategy": float(ev["_daily_ret"].corr(ctrl_ret)),
    }
    i = H.bt.start_index(ts, H.START)
    bench = H.bt.benchmark(c[i:, 1], ts[i:], H.BARS_PER_YEAR)
    payload = {
        "slug": SLUG,
        "family": FAMILY,
        "primary_object": PRIMARY,
        "dev": st,
        "windows": {"dev": {"1bp": ev["stats"]["1bp"],
                            "5bp": ev["stats"]["5bp"],
                            "10bp": ev["stats"]["10bp"]}},
        "window": {"dev": [H.START, H.END], "holdout": "not loaded"},
        "benchmark": {
            "tqqq_panel": bench,
            "tqqq_published_bar": H.TQQQ_BAR,
        },
        "params": {k: (list(v) if isinstance(v, tuple) else v)
                   for k, v in PARAMS.items()},
        "stats": ev["stats"],
        "events": ev["events"],
        "activity": {"fills": st["fills"], "events": ev["events"],
                     "fills_per_year": st["fills"] / st["years"],
                     "events_per_year": ev["events"] / st["years"]},
        "yearly": ev["yearly"],
        "subperiods": ev["subperiods"],
        "corr_winners": ev["corr_winners"],
        "corr_range": [min(ev["corr_winners"].values()),
                       max(ev["corr_winners"].values())],
        "avg_weights": ev["avg_weights"],
        "static_avg_weights": ev["static_avg_weights"],
        "plateau": plateau,
        "placebo": ev["placebo"],
        "causality_audit": causality,
        "trend_control": trend_control,
        "kill_checks": kills,
        "verdict": "dev_pass" if not any(kills.values()) else "fail",
        "timing": ("RSP/SPY daily closes through session t; target set at the "
                   "close of t, filled at the first bar open of t+1; 2% band; "
                   "long only."),
        "notes": ("RSP and SPY adjusted closes are read from data/external/ "
                  "and reindexed to the QQQ session calendar.  The development "
                  "run ends 2023-12-29 and does not load 2024-2026 prices."),
    }
    H.write_result(Path(__file__).with_name("result.json"), payload)
    print(f"{SLUG}: {H.summary_line(st)}")
    print("  10bp:", H.summary_line(ev["stats"]["10bp"]))
    print("  corr range", payload["corr_range"], "verdict", payload["verdict"])
    print("  kills", [k for k, v in kills.items() if v])


if __name__ == "__main__":
    main()
