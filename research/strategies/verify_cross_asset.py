"""Verify the four reserve cross-asset strategies end to end.

Checks, for each slug:
  * ``build_weights(ts, opens, closes)`` returns an (n, 3) long-only matrix;
  * re-simulating it reproduces the stored 1 bp result;
  * a panel truncation leaves every prior weight unchanged.

Run from the repo root:
    python research/strategies/verify_cross_asset.py
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "research"))
import cross_asset as ca  # noqa: E402

SLUGS = [
    "family-rates-volatility",
    "family-international-relative",
    "family-small-cap-relative",
    "family-copper-gold",
]


def load_module(slug: str):
    path = HERE / slug / "strategy.py"
    spec = importlib.util.spec_from_file_location(slug.replace("-", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> None:
    ts, o, c = ca.load_panel()
    print(f"panel {len(ts):,} bars  {ts[0]} .. {ts[-1]}")
    all_ok = True
    for slug in SLUGS:
        mod = load_module(slug)
        w = mod.build_weights(ts, o, c)
        ok_shape = w.shape == (len(ts), 3)
        ok_long = bool(w.min() >= -1e-12 and w.sum(axis=1).max() <= 1.0 + 1e-9)
        res = ca.simulate(ts, o, c, w, bp=1.0)
        st = ca.metrics(res)
        d = json.loads((HERE / slug / "result.json").read_text(encoding="utf-8"))
        stored = d["primary"]["dev"]["1bp"]
        diff = abs(st["cagr"] - stored["cagr"])
        cut = ca.cut_test(ts, o, c, lambda a, b, cc: mod.build_weights(a, b, cc))
        ok = ok_shape and ok_long and diff < 1e-9 and cut["pass"]
        all_ok &= ok
        print(
            f"{slug:34s} shape={w.shape} long={ok_long} "
            f"cagr={st['cagr']*100:6.2f}% stored_diff={diff:.1e} "
            f"cut_diff={cut['max_abs_weight_diff']:.1e} "
            f"{'OK' if ok else 'FAIL'}"
        )
    print("ALL OK" if all_ok else "FAILURES PRESENT")


if __name__ == "__main__":
    main()
