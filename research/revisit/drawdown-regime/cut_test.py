"""Look-ahead cut test for the tuned DDR (reuses audit/worker.install_cut).

    python research/revisit/drawdown-regime/cut_test.py
Builds headline weights on full dev data and on data truncated at each cut
(intraday cuts from TUNE_BRIEF plus the session-boundary cuts the audit used);
every weight before the cut must be identical. Scratch panels live in this
folder and are deleted afterwards.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
CUTS = ["2020-03-12 11:07", "2022-09-13 10:41", "2020-03-12 00:00", "2022-09-13 00:00"]
TMP = HERE / "_cut_tmp"


def build():
    sys.path.insert(0, str(HERE))
    import strategy as S
    ts, o, c = S.bt.panel(S.SYMS, S.DEV_START, S.DEV_END, "1min", warmup_days=500)
    return ts, S.build_weights(ts, o, c)[0]


def child(cut):
    sys.path.insert(0, str(HERE.parent / "audit"))
    import worker
    worker.CACHE = TMP
    TMP.mkdir(exist_ok=True)
    if cut != "ref":
        worker.install_cut(cut, "ddr-tune")
    ts, w = build()
    np.savez(TMP / f"w_{cut.replace(' ', '_').replace(':', '')}.npz", ts=ts.as_unit("ns").asi8, w=w)


def main():
    if len(sys.argv) > 1:
        return child(sys.argv[1])
    TMP.mkdir(exist_ok=True)
    try:
        subprocess.run([sys.executable, __file__, "ref"], check=True)
        ps = [subprocess.Popen([sys.executable, __file__, c]) for c in CUTS]
        assert all(p.wait() == 0 for p in ps), "cut run failed"
        z = np.load(TMP / "w_ref.npz")
        out = {}
        for cut in CUTS:
            y = np.load(TMP / f"w_{cut.replace(' ', '_').replace(':', '')}.npz")
            n = len(y["ts"])
            assert np.array_equal(z["ts"][:n], y["ts"]), "timestamps differ"
            diff = ~np.all(np.isclose(y["w"], z["w"][:n], rtol=0, atol=1e-12), axis=1)
            out[cut] = {"bars": n, "diff_total": int(diff.sum()),
                        "diff_before_last2": int(diff[:max(n - 2, 0)].sum()),
                        "pass": bool(diff[:max(n - 2, 0)].sum() == 0)}
            print(cut, out[cut])
        with open(HERE / "cut_test.json", "w", newline="\n", encoding="utf-8") as f:
            json.dump(out, f, indent=1)
    finally:
        shutil.rmtree(TMP, ignore_errors=True)


if __name__ == "__main__":
    main()
