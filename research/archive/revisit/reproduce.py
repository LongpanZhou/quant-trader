"""Recompute the development headline from the frozen full-panel weights."""
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
    spec = importlib.util.spec_from_file_location("rep_" + slug.replace("-", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def main():
    ts, op, cl = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, "2026-10-23", "1min",
                          warmup_days=0)
    for slug in SLUGS:
        mod = load_mod(slug)
        if slug == "ratio-pairs":
            w, _ = mod.build_weights(ts, op, cl)
            _, s = mod.run_window(w, ts, op, cl, DEV_START, DEV_END, 1.0)
        elif slug == "intraday-seasonality":
            w, _ = mod.build_weights(ts, op, cl, **mod.BASE)
            s = mod.metrics(mod.simulate_window(ts, op, cl, w, (DEV_START, DEV_END), 1.0))
        elif slug == "intraday-mean-reversion":
            w, _ = mod.build_weights(ts, op, cl)
            _, s, _, _ = mod.run_window(ts, op, cl, w, DEV_START, DEV_END, 1.0)
        else:
            qlow, qvol = mod.daily_extras(ts)
            w, _ = mod.build_weights(ts, op, cl, qlow, qvol)
            i0 = bt.start_index(ts, DEV_START)
            i1 = int(np.searchsorted(ts, pd.Timestamp(DEV_END, tz="America/New_York"))) + 1
            r = bt.simulate(ts[i0:i1], op[i0:i1], cl[i0:i1], w[i0:i1],
                            band=0.02, slippage_bps=1.0)
            s = bt.stats(r, 252 * 390)
        stored = json.loads((HERE / slug / "result.json").read_text())["windows"]["dev"]["1bp"]
        print("=" * 60)
        print(slug)
        for key in ("cagr", "max_drawdown", "sharpe"):
            print(f"  {key:14s} reproduced {s[key]*100:8.3f}%  stored {stored[key]*100:8.3f}%  "
                  f"diff {abs(s[key]-stored[key])*100:.4f}pp")


if __name__ == "__main__":
    main()
