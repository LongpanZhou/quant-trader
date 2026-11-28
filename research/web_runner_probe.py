"""Probe: can each research strategy build weights on a custom panel?

Loads the 2016-2020 panel once, resolves each visible research slug from
research/new or research/revisit, calls the generic build path, and reports
success/failure.  This is a scoping probe, not the web runner.
"""
from __future__ import annotations

import importlib.util
import inspect
import json
import sys
import traceback
from pathlib import Path

import numpy as np

ROOT = Path(r"C:\Users\27175\Desktop\quant-trader-research")
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(ROOT / "research" / "strategies"))
import bt  # noqa: E402
import run_holdout as R  # noqa: E402

START, END = "2020-01-02", "2020-12-31"
PANEL_START = "2016-01-04"


def resolve(slug: str):
    for base, tag in ((ROOT / "research" / "strategies", "strat_"),
                      (ROOT / "research" / "archive" / "new", "new_"),
                      (ROOT / "research" / "archive" / "revisit", "rev_")):
        path = base / slug / "strategy.py"
        if not path.exists():
            continue
        spec = importlib.util.spec_from_file_location(tag + slug.replace("-", "_"), path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        sys.path.insert(0, str(path.parent))
        spec.loader.exec_module(mod)
        return mod, path
    raise FileNotFoundError(slug)


def build(mod, ts, o, c, params):
    if hasattr(mod, "build_holdout_weights") and not params:
        out = mod.build_holdout_weights(ts, o, c)
    else:
        if not hasattr(mod, "build_weights"):
            raise AttributeError("no build_weights")
        fn = mod.build_weights
        sig = inspect.signature(fn)
        kw = {}
        if "params" in sig.parameters:
            base = dict(getattr(mod, "PARAMS", {}) or {})
            base.update(params or {})
            kw["params"] = base
        out = fn(ts, o, c, **kw)
    w = out[0] if isinstance(out, tuple) else out
    w = np.asarray(w, float)
    if w.ndim == 2 and w.shape[1] == 2:
        w = R.to_three(w, len(ts))
    return w


def main():
    meta = json.loads((ROOT / "web/public/data/research/rebuild.json").read_text(encoding="utf-8"))
    slugs = [s["slug"] for s in meta["strategies"]]
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), PANEL_START, END, "1min", warmup_days=0)
    print(f"panel {len(ts):,} bars {ts[0]} .. {ts[-1]}  strategies={len(slugs)}")
    ok = 0
    failures = []
    for i, slug in enumerate(slugs, 1):
        try:
            mod, path = resolve(slug)
            w = build(mod, ts, o, c, {})
            w = np.asarray(w, float)
            if w.shape != (len(ts), 3):
                raise ValueError(f"weights shape {w.shape}")
            r = bt.run(ts, o, c, w, START, band=0.02, slippage_bps=1.0)
            s = bt.stats(r, 252 * 390)
            print(f"{i:2d}/{len(slugs)} OK   {slug:40s} cagr={s['cagr']*100:7.2f}% fills={int(s['fills'])}")
            ok += 1
        except Exception as exc:
            failures.append((slug, type(exc).__name__, str(exc)[:160]))
            print(f"{i:2d}/{len(slugs)} FAIL {slug:40s} {type(exc).__name__}: {str(exc)[:100]}")
    print(f"\nOK {ok}/{len(slugs)}")
    print("failures:")
    for slug, kind, msg in failures:
        print(f"  {slug:40s} {kind}: {msg}")


if __name__ == "__main__":
    main()
