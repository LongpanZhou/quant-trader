"""Look-ahead cut test for the tuned build_weights (uses audit/worker.install_cut).

    python research/revisit/dynamic-leverage-throttle/tune_cut.py ref
    python research/revisit/dynamic-leverage-throttle/tune_cut.py "2020-03-12 11:07"
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "audit"))
import worker  # noqa: E402
from worker import bt  # noqa: E402

SCR = HERE / "_tune_cut_cache"


def build():
    sys.path.insert(0, str(HERE))
    import strategy as S
    ts, o, c = S.load_dev_panel()
    return ts, S.build_weights(ts, o, c)[0]


def main(cut):
    SCR.mkdir(exist_ok=True)
    ref = SCR / "ref.npz"
    if cut == "ref":
        ts, w = build()
        np.savez(ref, ts=ts.as_unit("ns").asi8, w=w)
        print(json.dumps({"ref_bars": len(ts)}))
        return 0
    worker.install_cut(cut, "dlt-tune")
    try:
        ts, w = build()
    finally:
        shutil.rmtree(bt.CACHE_DIR, ignore_errors=True)
    z = np.load(ref)
    n = len(ts)
    assert np.array_equal(z["ts"][:n], ts.as_unit("ns").asi8)
    diff = ~np.all(np.isclose(w, z["w"][:n], rtol=0, atol=1e-12), axis=1)
    early = diff[:max(n - 2, 0)]
    print(json.dumps({"cut": cut, "bars": n, "end": str(ts[-1]),
                      "diff_before_last2": int(early.sum()),
                      "pass": bool(early.sum() == 0)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
