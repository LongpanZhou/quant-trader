"""Look-ahead cut test for this strategy (tuning 2026-11-27).

    python research/revisit/opening-range-breakout/tune_cut.py ref
    python research/revisit/opening-range-breakout/tune_cut.py "2020-03-12 11:07"

Uses research/revisit/audit/worker.install_cut (read-only import). Every weight
before the last two bars of the truncated data must equal the full-data weight.
Optional 2nd arg: path of a strategy file (default: ./strategy.py) and config
JSON via 3rd arg.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "audit"))
import worker  # noqa: E402
from worker import bt  # noqa: E402

SCRATCH = Path(sys.argv[3]) if len(sys.argv) > 3 else HERE / "_cut_cache"


def load(path):
    spec = importlib.util.spec_from_file_location("orb_cut", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def weights(mod, cfg):
    ts, o, c, q, t, b = mod.load_dev()
    return ts, mod.build_weights(ts, o, c, q, t, cfg)[0]


def main():
    cut = sys.argv[1]
    cfg = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    SCRATCH.mkdir(exist_ok=True)
    tag = json.dumps(cfg, sort_keys=True)
    ref = SCRATCH / f"ref-{hashlib.md5(tag.encode()).hexdigest()[:10]}.npz"
    if cut == "ref":
        ts, w = weights(load(HERE / "strategy.py"), cfg)
        np.savez(ref, ts=ts.as_unit("ns").asi8, w=w)
        print(json.dumps({"ref": len(ts), "cfg": cfg}))
        return 0
    worker.CACHE = SCRATCH
    worker.install_cut(cut, "orb-tune")
    try:
        ts, w = weights(load(HERE / "strategy.py"), cfg)
    finally:
        shutil.rmtree(bt.CACHE_DIR, ignore_errors=True)
    z = np.load(ref)
    n = len(ts)
    assert np.array_equal(z["ts"][:n], ts.as_unit("ns").asi8), "timestamps differ"
    diff = ~np.all(np.isclose(w, z["w"][:n], rtol=0, atol=1e-12), axis=1)
    early = diff[:max(n - 2, 0)]
    print(json.dumps({"cut": cut, "cfg": cfg, "bars": n, "end": str(ts[-1]),
                      "diff_total": int(diff.sum()), "diff_before_last2": int(early.sum()),
                      "first_diff": str(ts[np.flatnonzero(early)[0]]) if early.any() else None,
                      "PASS": bool(not early.any())}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
