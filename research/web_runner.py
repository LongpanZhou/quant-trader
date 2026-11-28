"""Execute one research strategy over a custom date range.

Usage:
    python research/web_runner.py --slug family-regime-switch \
        --start 2020-01-02 --end 2020-12-31 --params '{"ma":150,"vix":25}' --slippage 1

Prints one JSON object.  The Next.js `/api/research-backtest` route calls this
script.  The strategy tree is `research/strategies/<slug>/strategy.py`.
"""
from __future__ import annotations

import argparse
import importlib.util
import inspect
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
STRAT = ROOT / "research" / "strategies"
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(STRAT))
import bt  # noqa: E402
import run_holdout as R  # noqa: E402
from minute_marks import to_minutes  # noqa: E402

SYMBOLS = ("QQQ", "TQQQ", "BIL")
DATA_START = "2016-01-04"
DATA_END = "2026-10-23"
BARS_PER_YEAR = 252 * 390
SPECIAL = {"ratio-pairs", "time-of-day", "family-ml-microstructure",
           "ml-classifier", "ml-crash-overlay-winner"}


def load(slug: str):
    path = STRAT / slug / "strategy.py"
    if not path.exists():
        raise FileNotFoundError(f"unknown strategy: {slug}")
    spec = importlib.util.spec_from_file_location("web_" + slug.replace("-", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    sys.path.insert(0, str(path.parent))
    spec.loader.exec_module(mod)
    return mod


def _three(w, n: int):
    w = np.asarray(w, float)
    if w.ndim == 2 and w.shape[1] == 2:
        w = R.to_three(w, n)
    return w


def build_weights(slug: str, mod, ts, o, c, params: dict, end: str):
    if slug in ("ratio-pairs", "time-of-day"):
        P = mod.Params(**params) if params else mod.Params()
        out = mod.build_weights(ts, o, c, P)
        return _three(out[0] if isinstance(out, tuple) else out, len(ts))

    if slug == "family-ml-microstructure":
        tsd, od, cd = bt.panel(SYMBOLS, DATA_START, end, "1D", warmup_days=0)
        feat = mod.build_feature_panel(end)
        wd, _ = mod.build_weights(tsd, od, cd, features=feat)
        wm = mod.minute_weights(np.asarray(wd, float), ts)
        w = np.zeros((len(ts), 3))
        w[:, 1] = wm
        w[:, 2] = 1.0 - wm
        return w

    if slug == "ml-classifier":
        ts5, o5, c5 = bt.panel(SYMBOLS, DATA_START, end, "5min", warmup_days=0)
        tsd, od, cd = bt.panel(SYMBOLS, DATA_START, end, "1D", warmup_days=0)
        feat = mod.build_features(ts5, o5, c5, tsd, od, cd)
        wd, _ = mod.build_weights(tsd, feat, od, cd)
        return _three(to_minutes(tsd, np.asarray(wd, float), ts, "1D"), len(ts))

    if slug == "ml-crash-overlay-winner":
        tsd, od, cd = bt.panel(SYMBOLS, DATA_START, end, "1D", warmup_days=0)
        out = mod.build_weights(ts, o, c, tsd, od, cd, last_year=int(end[:4]))
        return _three(out[0] if isinstance(out, tuple) else out, len(ts))

    if hasattr(mod, "build_holdout_weights") and not params:
        out = mod.build_holdout_weights(ts, o, c)
    else:
        fn = mod.build_weights
        sig = inspect.signature(fn)
        kw = {}
        if "params" in sig.parameters:
            base = dict(getattr(mod, "PARAMS", {}) or {})
            base.update(params or {})
            kw["params"] = base
        # Pass only parameters the function accepts.
        for key, value in (params or {}).items():
            if key in sig.parameters and key != "params":
                kw[key] = value
        out = fn(ts, o, c, **kw)
    return _three(out[0] if isinstance(out, tuple) else out, len(ts))


def run(slug: str, start: str, end: str, params: dict | None = None,
        slippage_bps: float = 1.0, band: float = 0.02) -> dict:
    params = params or {}
    if not (DATA_START <= start < end <= DATA_END):
        raise ValueError(f"date range must satisfy {DATA_START} <= start < end <= {DATA_END}")
    ts, o, c = bt.panel(SYMBOLS, DATA_START, end, "1min", warmup_days=0)
    mod = load(slug)
    w = build_weights(slug, mod, ts, o, c, params, end)
    if w.shape != (len(ts), 3):
        raise ValueError(f"weights shape {w.shape}, expected {(len(ts), 3)}")
    r = bt.run(ts, o, c, w, start, band=band, slippage_bps=float(slippage_bps))
    s = bt.stats(r, BARS_PER_YEAR)
    eq = pd.Series(r["equity"], index=pd.to_datetime(r["ts"]))
    if eq.index.tz is not None:
        eq.index = eq.index.tz_localize(None)
    daily = eq.groupby(eq.index.normalize()).last()
    return {
        "ok": True,
        "slug": slug,
        "start": start,
        "end": end,
        "params": params,
        "slippage_bps": float(slippage_bps),
        "cagr": float(s["cagr"]),
        "max_drawdown": float(s["max_drawdown"]),
        "sharpe": float(s["sharpe"]),
        "sortino": float(s["sortino"]),
        "volatility": float(s["volatility"]),
        "fills": int(s["fills"]),
        "turnover": float(s["turnover"]),
        "daily_curve": {
            "dates": [str(d.date()) for d in daily.index],
            "values": [float(v) for v in daily.to_numpy()],
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True)
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--params", default="{}")
    ap.add_argument("--slippage", type=float, default=1.0)
    args = ap.parse_args()
    try:
        out = run(args.slug, args.start, args.end, json.loads(args.params), args.slippage)
        print(json.dumps(out))
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
