"""Sanity-check two original 165-day curves against a fresh 2017-2023 run."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"C:\Users\27175\Desktop\quant-trader-research")
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

START, END = "2017-01-03", "2023-12-29"
COMPARE = ROOT / "web" / "public" / "data" / "compare" / "all.json"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def daily_stats(dates, values):
    s = pd.Series(values, index=pd.to_datetime(dates))
    s = s / s.iloc[0] * 100.0
    eq = s.to_numpy()
    peak = np.maximum.accumulate(eq)
    years = (s.index[-1] - s.index[0]).days / 365.25
    return {
        "cagr": (eq[-1] / eq[0]) ** (1 / years) - 1,
        "dd": -(eq / peak - 1).min(),
    }


def fresh(mod, ts, op, cl):
    w, _ = mod.build_weights(ts, op, cl)
    r = bt.run(ts, op, cl, w, START, band=0.02, slippage_bps=1.0)
    s = pd.Series(r["equity"], index=pd.DatetimeIndex(r["ts"]))
    s = s.groupby(s.index.date).last()
    return daily_stats(s.index, s.to_numpy())


def main():
    chart = json.loads(COMPARE.read_text())
    by_id = {s["id"]: s for s in chart["series"]}
    ts, op, cl = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1min")
    for key, path in (
        ("orig-a21", ROOT / "research" / "agents2" / "ratio-pairs" / "strategy.py"),
        ("orig-a17", ROOT / "research" / "agents2" / "overnight-crash-filter" / "strategy.py"),
    ):
        mod = load(key, path)
        live = fresh(mod, ts, op, cl)
        s = by_id[key]
        stored = daily_stats(chart["dates"], s["values"])
        print("=" * 60)
        print(key, s["name"])
        print(f"  chart : CAGR {stored['cagr']*100:7.2f}%  DD {stored['dd']*100:6.2f}%")
        print(f"  fresh : CAGR {live['cagr']*100:7.2f}%  DD {live['dd']*100:6.2f}%")
        print(f"  diff  : CAGR {(stored['cagr']-live['cagr'])*100:7.2f}pp  "
              f"DD {(stored['dd']-live['dd'])*100:6.2f}pp")


if __name__ == "__main__":
    main()
