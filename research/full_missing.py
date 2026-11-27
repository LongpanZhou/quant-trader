"""Full 2016-2026 curves for the strategies missing from curves_full."""
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
import minute_marks  # noqa: E402

START, END = "2016-01-04", "2026-10-23"
OUT = ROOT / "research" / "revisit" / "curves_full"


def load(slug):
    path = ROOT / "research" / "revisit" / slug / "strategy.py"
    spec = importlib.util.spec_from_file_location("full_" + slug.replace("-", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def save(slug, ts, equity):
    s = pd.Series(equity, index=pd.DatetimeIndex(ts))
    daily = s.groupby(s.index.date).last()
    daily = daily / daily.iloc[0] * 100.0
    payload = {
        "slug": slug,
        "dates": [str(d) for d in daily.index],
        "values": [float(v) for v in daily.to_numpy()],
    }
    (OUT / f"{slug}.json").write_text(json.dumps(payload), encoding="utf-8")
    print("WROTE", slug, len(daily), daily.index[0], daily.index[-1],
          "last", round(float(daily.iloc[-1]), 1))


def main():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1min", warmup_days=0)

    for slug in ("intraday-momentum", "risk-parity-hrp"):
        mod = load(slug)
        w, _ = mod.build_weights(ts, o, c)
        r = bt.run(ts, o, c, w, START, band=0.02, slippage_bps=1.0)
        save(slug, r["ts"], r["equity"])

    mod = load("vol-scaled-crash-stop")
    cache = ROOT / "research" / "revisit" / "vol-scaled-crash-stop" / "dev_panel.npz"
    cache.unlink(missing_ok=True)
    vts, vo, vh, vl, vc = mod.load_dev_panel(START, END)
    dates = bt.session_dates(vts)
    first, last = bt.day_bounds_from_dates(dates)
    atr = mod.atr_series(vh, vl, vc, first, last)
    w, _ = mod.build_weights(vts, vo, vc, first, last, atr)
    r = bt.run(vts, vo, vc, w, START, band=0.02, slippage_bps=1.0)
    save("vol-scaled-crash-stop", r["ts"], r["equity"])

    # ml-classifier is intentionally omitted: its refit schedule contains a
    # second literal ("2023-12-01") that this direct builder does not extend,
    # so it would freeze the model at Dec-2023 and overwrite the corrected
    # curve.  Use `python research/capture_full.py ml-classifier` instead.
    print("SKIP ml-classifier (use capture_full.py; monthly-refit literal)")

    mod = load("ml-crash-overlay-winner")
    tsd, od, cd = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1D")
    w1, *_ = mod.build_weights(ts, o, c, tsd, od, cd, last_year=2026)
    r = bt.run(ts, o, c, w1, START, band=0.02, slippage_bps=1.0)
    save("ml-crash-overlay-winner", r["ts"], r["equity"])

    # original Ratio froth as just another strategy, full 2016-2026
    spec = importlib.util.spec_from_file_location(
        "old_ratio", ROOT / "research" / "agents2" / "ratio-pairs" / "strategy.py")
    old = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = old
    spec.loader.exec_module(old)
    w, _ = old.build_weights(ts, o, c)
    r = bt.run(ts, o, c, w, START, band=0.02, slippage_bps=1.0)
    save("ratio-froth", r["ts"], r["equity"])


if __name__ == "__main__":
    main()
