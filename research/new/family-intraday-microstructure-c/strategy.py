"""Opening-drive intraday microstructure — frozen lead implementation.

At the decision minute (default 10:00 ET), hold TQQQ through 15:59 when QQQ is
above both the session open and the session VWAP proxy (mean QQQ close from
09:30 to the decision minute). Otherwise hold BIL. No daily trend, no
volatility/drawdown regime, no overnight position.
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
SYMBOLS = ("QQQ", "TQQQ", "BIL")
BARS_PER_YEAR = 252 * 390
BASE = dict(dec_min=30, thr=0.0)
GRID = [
    ("dec25_thr0", dict(dec_min=25, thr=0.0)),
    ("dec30_thr-0.1", dict(dec_min=30, thr=-0.001)),
    ("dec30_thr0_primary", dict(dec_min=30, thr=0.0)),
    ("dec30_thr0.1", dict(dec_min=30, thr=0.001)),
    ("dec35_thr0", dict(dec_min=35, thr=0.0)),
]


def build_weights(ts, o, c, params: dict | None = None) -> np.ndarray:
    p = dict(BASE)
    if params:
        p.update(params)
    dec = int(p["dec_min"])
    thr = float(p["thr"])
    dates = bt.session_dates(ts)
    first, last = bt.day_bounds_from_dates(dates)
    q_open = o[first, 0]
    w = np.zeros((len(ts), 3))
    w[:, 2] = 1.0
    for s in range(len(first)):
        f, l = int(first[s]), int(last[s])
        d = min(f + dec, l)
        vwap = float(np.mean(c[f:d + 1, 0]))
        px = float(c[d, 0])
        if px > q_open[s] * (1.0 + thr) and px > vwap:
            w[d:l + 1, 1] = 1.0
            w[d:l + 1, 2] = 0.0
    return w


def run(ts, o, c, w, slip=1.0):
    r = bt.run(ts, o, c, w, DEV_START, band=0.02, slippage_bps=slip)
    return r, bt.stats(r, BARS_PER_YEAR)


def main() -> None:
    ts, o, c = bt.panel(SYMBOLS, DEV_START, DEV_END, "1min", warmup_days=0)
    rows = []
    primary = None
    for name, params in GRID:
        w = build_weights(ts, o, c, params)
        r, s = run(ts, o, c, w, 1.0)
        row = {
            "cell": name, "params": params,
            "cagr": s["cagr"], "max_drawdown": s["max_drawdown"],
            "sharpe": s["sharpe"], "fills": s["fills"],
            "turnover": s["turnover"],
        }
        rows.append(row)
        if name == "dec30_thr0_primary":
            primary = (w, r, s, row)
    w, r, s, row = primary
    costs = {}
    for slip in (1.0, 5.0, 10.0):
        _, cs = run(ts, o, c, w, slip)
        costs[f"{int(slip)}bp"] = {
            "cagr": cs["cagr"], "max_drawdown": cs["max_drawdown"],
            "sharpe": cs["sharpe"],
        }
    # yearly
    eq = pd.Series(r["equity"], index=pd.DatetimeIndex(r["ts"]))
    daily = eq.groupby(eq.index.date).last()
    daily.index = pd.to_datetime(daily.index)
    yearly = {}
    for y, g in daily.groupby(daily.index.year):
        yearly[str(y)] = float(g.iloc[-1] / g.iloc[0] - 1.0)
    result = {
        "slug": "family-intraday-microstructure-c",
        "family": "intraday-microstructure",
        "window": {"dev": [DEV_START, DEV_END], "holdout": "not loaded"},
        "primary": {
            "cell": "dec30_thr0_primary",
            "params": BASE,
            "1bp": {k: s[k] for k in ("cagr", "max_drawdown", "sharpe",
                                       "fills", "turnover")},
        },
        "grid": rows,
        "costs": costs,
        "yearly": yearly,
        "rules": (
            "At 10:00 ET hold TQQQ through 15:59 when QQQ is above the session "
            "open and above the session VWAP proxy (mean close 09:30-10:00); "
            "otherwise BIL. No daily trend, no vol/drawdown regime, flat overnight."
        ),
        "notes": {
            "family_purity": "Intraday price action only; no daily trend or vol state.",
            "cost_fragility": "The edge is 1 bp only; 5 bp is far below the bar.",
            "grid": "The 10:00 no-threshold cell is the centre; neighbours are weaker.",
        },
        "passed_dev_bar": bool(s["cagr"] > 0.3672 and s["max_drawdown"] < 0.8229),
        "status": "dev_pass" if s["cagr"] > 0.3672 and s["max_drawdown"] < 0.8229 else "below_dev_bar",
    }
    out = Path(__file__).resolve().parent / "result.json"
    out.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("status", "passed_dev_bar", "primary", "costs")}, indent=1))
    print("wrote", out)


if __name__ == "__main__":
    main()
