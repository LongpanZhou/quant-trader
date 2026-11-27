"""Direct full-history curve for strategies whose main() is hard to extend.

DEPRECATED.  This script calls the current `build_weights` defaults, which for
`dual-speed-regime` are the post-tune `overnight=True, idle="cash"` variant and
for `ensemble-signals` include the post-tune warm-up.  Re-running it would
overwrite the published pre-tune curves.  Use the frozen curve on disk, or
`capture_full.py` only if you intend to adopt the post-tune variant.
"""
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

START, END = "2016-01-04", "2026-10-23"
TEN, FIVE = "2017-01-03", "2021-10-25"
BARS = 252 * 390
OUT = ROOT / "research" / "revisit" / "curves_full"


def load(slug):
    path = ROOT / "research" / "revisit" / slug / "strategy.py"
    spec = importlib.util.spec_from_file_location("full_" + slug.replace("-", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def stats_at(r, start):
    i = bt.start_index(r["ts"], start)
    rr = {k: (np.asarray(v)[i:] if isinstance(v, (list, np.ndarray)) else v)
          for k, v in r.items()}
    rr["ts"] = pd.DatetimeIndex(r["ts"])[i:]
    s = bt.stats(rr, BARS)
    return {k: float(s[k]) for k in ("cagr", "max_drawdown", "sharpe", "sortino",
                                     "volatility", "fills", "turnover", "exposure",
                                     "ending_equity") if k in s}


def main():
    raise SystemExit(
        "full_direct.py is deprecated: it would overwrite the published pre-tune "
        "curves with the current build_weights defaults. Use the frozen curve, "
        "or capture_full.py only if you intend to adopt the post-tune variant."
    )
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1min", warmup_days=0)
    for slug in ("dual-speed-regime", "ensemble-signals"):
        mod = load(slug)
        w, _ = mod.build_weights(ts, o, c)
        r = bt.run(ts, o, c, w, START, band=0.02, slippage_bps=1.0)
        eq = pd.Series(r["equity"], index=pd.DatetimeIndex(r["ts"]))
        daily = eq.groupby(eq.index.date).last()
        daily = daily / daily.iloc[0] * 100.0
        payload = {
            "slug": slug,
            "dates": [str(d) for d in daily.index],
            "values": [float(v) for v in daily.to_numpy()],
            "metrics": {"full": stats_at(r, START), "10y": stats_at(r, TEN),
                        "5y": stats_at(r, FIVE)},
        }
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / f"{slug}.json").write_text(json.dumps(payload), encoding="utf-8")
        print("WROTE", slug, len(daily), "days", daily.index[0], daily.index[-1])


if __name__ == "__main__":
    main()
