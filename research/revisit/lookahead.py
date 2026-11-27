"""Look-ahead cut test for the four audited survivors.

Build weights on data truncated at the cut, then compare every weight strictly
before the cut with the full-development-panel weights.  A causal strategy must
be identical.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"C:\Users\27175\Desktop\quant-trader-research")
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

HERE = ROOT / "research" / "revisit"
SYMS = ("QQQ", "TQQQ", "BIL")
DEV_START, DEV_END = "2016-01-04", "2023-12-29"
CUTS = ["2020-03-12 11:07", "2022-09-13 10:41"]
SLUGS = ["ratio-pairs", "intraday-seasonality", "intraday-mean-reversion",
         "gap-capitulation-reversal"]


def load_mod(slug):
    path = HERE / slug / "strategy.py"
    spec = importlib.util.spec_from_file_location("la_" + slug.replace("-", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def weights_for(mod, slug, ts, op, cl):
    if slug == "ratio-pairs":
        return mod.build_weights(ts, op, cl)[0]
    if slug == "intraday-seasonality":
        return mod.build_weights(ts, op, cl, **mod.BASE)[0]
    if slug == "intraday-mean-reversion":
        return mod.build_weights(ts, op, cl)[0]
    qlow, qvol = mod.daily_extras(ts)
    return mod.build_weights(ts, op, cl, qlow, qvol)[0]


def main():
    ts, op, cl = bt.panel(SYMS, DEV_START, DEV_END, "1min", warmup_days=0)
    print(f"full {len(ts):,} bars")
    for slug in SLUGS:
        mod = load_mod(slug)
        w_full = weights_for(mod, slug, ts, op, cl)
        print("=" * 70)
        print(slug, "full weights", w_full.shape, "finite", np.isfinite(w_full).all())
        for cut in CUTS:
            cut_ts = pd.Timestamp(cut, tz="America/New_York")
            # Build on data through the end of the cut session.  Compare only
            # bars strictly before the cut, so terminal liquidation at the end
            # of the truncated panel cannot create a false positive.
            k = int(np.searchsorted(ts, cut_ts))
            end = int(np.searchsorted(ts, cut_ts.normalize() + pd.Timedelta(days=1)))
            ts_s, op_s, cl_s = ts[:end], op[:end], cl[:end]
            w_s = weights_for(mod, slug, ts_s, op_s, cl_s)
            same = np.allclose(w_full[:k], w_s[:k], rtol=0, atol=1e-12)
            if same:
                print(f"  {cut}: PASS ({k:,} bars before cut identical)")
            else:
                diff = np.abs(w_full[:k] - w_s[:k]).max()
                idx = int(np.argmax(np.abs(w_full[:k] - w_s[:k]).max(axis=1)))
                print(f"  {cut}: FAIL max diff {diff:.3e} first bar {ts[idx]}")


if __name__ == "__main__":
    main()
