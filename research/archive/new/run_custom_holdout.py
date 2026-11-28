"""One-shot holdout for a strategy that needs a custom (synthetic) panel.

The strategy module may expose `build_panel(ts, opens, closes)` returning
(synthetic_opens, synthetic_closes).  `build_weights(ts, opens, closes)` is
called on the standard QQQ/TQQQ/BIL panel, exactly as in the development run.
Everything else matches `run_holdout.py`.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
NEW = ROOT / "research" / "new"
CURVES = NEW / "curves"
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402
import run_holdout as R  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    args = ap.parse_args()
    slug = args.slug

    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), R.START, R.END, "1min", warmup_days=0)
    mod = R.load(slug)
    if not hasattr(mod, "build_panel"):
        raise SystemExit(f"{slug}: no build_panel(); use run_holdout.py")

    out = mod.build_weights(ts, o, c)
    w = np.asarray(out[0] if isinstance(out, tuple) else out, dtype=float)
    if w.shape != (len(ts), 3):
        raise SystemExit(f"{slug}: build_weights returned {w.shape}")
    if (w < -1e-9).any() or (w.sum(axis=1) > 1.001).any():
        raise SystemExit(f"{slug}: invalid weights")

    po, pc = mod.build_panel(ts, o, c)
    r = bt.run(ts, po, pc, w, R.START, band=0.02, slippage_bps=1.0, fill_log=True)
    daily = R.daily_curve(r["equity"], pd.DatetimeIndex(r["ts"]))

    def bench(col: int) -> pd.Series:
        s = pd.Series(c[:, col], index=pd.DatetimeIndex(ts))
        d = s.groupby(s.index.date).last()
        d.index = pd.to_datetime(d.index)
        return d / d.iloc[0] * 100.0

    tqqq, qqq = bench(1), bench(0)
    windows = {
        "dev": (R.START, R.DEV_END),
        "holdout": ("2024-01-02", R.END),
        "full": (R.START, R.END),
        "10y": (R.TEN, R.END),
        "5y": (R.FIVE, R.END),
    }
    result = {
        "slug": slug,
        "generated": pd.Timestamp.now(tz="UTC").isoformat(),
        "windows": {},
        "daily_curve": {
            "dates": [str(d.date()) for d in daily.index],
            "values": [float(v) for v in daily.to_numpy()],
        },
        "benchmarks": {
            sym: {
                "dev": R.daily_stats(curve, R.START, R.DEV_END),
                "holdout": R.daily_stats(curve, "2024-01-02", R.END),
                "full": R.daily_stats(curve, R.START, R.END),
                "10y": R.daily_stats(curve, R.TEN, R.END),
                "5y": R.daily_stats(curve, R.FIVE, R.END),
            }
            for sym, curve in (("tqqq", tqqq), ("qqq", qqq))
        },
        "panel": "custom synthetic panel from strategy.build_panel()",
    }
    for name, (lo, hi) in windows.items():
        result["windows"][name] = {
            "1bp": R.minute_stats(r, lo, hi),
            "daily": R.daily_stats(daily, lo, hi),
        }

    path = NEW / slug / "holdout.json"
    path.write_text(json.dumps(result, indent=1), encoding="utf-8")
    CURVES.mkdir(parents=True, exist_ok=True)
    (CURVES / f"{slug}.json").write_text(json.dumps({
        "slug": slug,
        "dates": result["daily_curve"]["dates"],
        "values": result["daily_curve"]["values"],
    }), encoding="utf-8")

    for name in ("dev", "holdout", "full"):
        s = result["windows"][name]["1bp"]
        print(f"{name:7s} {s['cagr']*100:6.2f}% CAGR {s['max_drawdown']*100:6.2f}% DD "
              f"{s['sharpe']:5.2f} Sharpe fills {s['fills']}")
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
