"""Pairwise development correlations for the four audited survivors."""
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

HERE = ROOT / "research" / "revisit"
DEV_START, DEV_END = "2016-01-04", "2023-12-29"
SLUGS = ["ratio-pairs", "intraday-seasonality", "intraday-mean-reversion",
         "gap-capitulation-reversal"]


def load_mod(slug):
    path = HERE / slug / "strategy.py"
    spec = importlib.util.spec_from_file_location("corr_" + slug.replace("-", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def daily(result):
    eq = pd.Series(result["equity"], index=result["ts"])
    return eq.groupby(eq.index.date).last().pct_change().dropna()


def main():
    ts, op, cl = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END, "1min",
                          warmup_days=0)
    series = {}
    for slug in SLUGS:
        mod = load_mod(slug)
        if slug == "ratio-pairs":
            w, _ = mod.build_weights(ts, op, cl)
            r, _ = mod.run_window(w, ts, op, cl, DEV_START, DEV_END, 1.0)
        elif slug == "intraday-seasonality":
            w, _ = mod.build_weights(ts, op, cl, **mod.BASE)
            r = mod.simulate_window(ts, op, cl, w, (DEV_START, DEV_END), 1.0)
        elif slug == "intraday-mean-reversion":
            w, _ = mod.build_weights(ts, op, cl)
            r, _, _, _ = mod.run_window(ts, op, cl, w, DEV_START, DEV_END, 1.0)
        else:
            qlow, qvol = mod.daily_extras(ts)
            w, _ = mod.build_weights(ts, op, cl, qlow, qvol)
            r, _ = mod.window_metrics(ts, op, cl, w, DEV_START, 1.0)
        series[slug] = daily(r)
        print(f"{slug:30s} days={len(series[slug])}")

    frame = pd.DataFrame(series).dropna()
    corr = frame.corr()
    print("\npairwise correlation")
    print(corr.round(3).to_string())

    # old 165-day baseline daily returns
    mod = load_mod("ratio-pairs")
    base = mod.baseline_weights(ts, cl)
    rb, _ = mod.run_window(base, ts, op, cl, DEV_START, DEV_END, 1.0)
    b = daily(rb)
    vs_base = {s: float(frame[s].corr(b.reindex(frame.index))) for s in frame}
    print("\nvs 165d baseline:", {k: round(v, 3) for k, v in vs_base.items()})

    off = corr.to_numpy()[np.triu_indices(len(corr), 1)]
    out = {
        "set": "audited survivors",
        "period": [DEV_START, DEV_END],
        "strategies": SLUGS,
        "pairwise": {a: {b: float(corr.loc[a, b]) for b in SLUGS} for a in SLUGS},
        "vs_165d_baseline": vs_base,
        "average_pairwise": float(off.mean()),
        "max_pairwise": float(off.max()),
        "min_pairwise": float(off.min()),
        "original_set_average": 0.86,
        "note": ("Original 26 shared-base strategies averaged about 0.86 pairwise. "
                 "This matrix covers only the strategies that passed their development "
                 "gates and were frozen for the holdout."),
    }
    (HERE / "correlations.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("\nwrote", HERE / "correlations.json")


if __name__ == "__main__":
    main()
