"""Robustness checks for drawdown-regime-v2 (dev window only).

    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/new/drawdown-regime-v2/robustness.py
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

spec = importlib.util.spec_from_file_location("ddr_v2", HERE / "strategy.py")
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)


def cagr(r):
    return float(bt.stats(r, S.BPY)["cagr"])


def main():
    ts, o, c = bt.panel(S.SYMS, S.DEV_START, S.DEV_END, "1min", warmup_days=500)
    w, info = S.build_weights(ts, o, c)
    r = bt.run(ts, o, c, w, S.DEV_START, 0.02, 1.0)
    base = cagr(r)

    dates, first, last = S._sessions(ts)
    T = info["targets"]
    loo = {}
    for e in info["episodes"]:
        Tm = T.copy()
        Tm[e["entry_i"]:e.get("exit_i", len(Tm))] = 0
        wm = S.weights_from_targets(Tm, first, last)
        loo[e["entry_date"]] = cagr(bt.run(ts, o, c, wm, S.DEV_START, 0.02, 1.0))

    rng = np.random.default_rng(7)
    shifts = rng.integers(60, len(T) - 60, size=100)
    ws = [S.weights_from_targets(np.roll(T, int(s)), first, last) for s in shifts]
    rp = bt.run_many(ts, o, c, ws, S.DEV_START, 0.02, 1.0)
    pc = np.array([cagr(x) for x in rp])

    eq = pd.Series(r["equity"], index=r["ts"])
    de = eq.groupby(eq.index.date).last()
    dd = de / de.cummax() - 1.0
    trough = dd.idxmin()
    peak = de[:trough].idxmax()

    out = {
        "base_cagr": base,
        "max_dd_window": {"peak": str(peak), "trough": str(trough),
                          "daily_dd": float(dd.min())},
        "leave_one_episode_out": {
            "n": len(loo), "min": float(min(loo.values())),
            "max": float(max(loo.values())), "by_entry": loo},
        "placebo_circular_shift": {
            "n": int(len(pc)), "median_cagr": float(np.median(pc)),
            "p90_cagr": float(np.quantile(pc, 0.9)),
            "p_cagr_ge_strategy": float((pc >= base).mean())},
        "note": "Development window only; no 2024+ data loaded.",
    }
    (HERE / "robustness.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
