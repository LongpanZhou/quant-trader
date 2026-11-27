"""Look-ahead cut test for strategy.py (headline weights), dev data only.

    python research/revisit/ml-classifier/tune_cut.py

Builds the 1-minute headline weights on the full dev panel, then again with
every data source truncated at each cut (audit/worker.install_cut), and
checks that every weight before the cut (except the last two bars) is
unchanged.  The panel cache of the truncated runs goes to a scratch folder.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CUTS = ["2020-03-12 11:07", "2022-06-30 00:00", "2022-06-30 11:30", "2022-09-13 10:41"]


def build():
    sys.path.insert(0, str(HERE))
    import strategy as S
    ts5, o5, c5 = S.bt.panel(S.SYMBOLS, S.DEV_START, S.DEV_END, "5min")
    tsd, od, cd = S.bt.panel(S.SYMBOLS, S.DEV_START, S.DEV_END, "1D")
    ts1, o1, c1 = S.bt.panel(S.SYMBOLS, S.DEV_START, S.DEV_END, "1min")
    feats = S.build_features(ts5, o5, c5, tsd, od, cd)
    w, _ = S.build_weights(tsd, feats, od, cd)
    return ts1, S.to_minutes(tsd, w, ts1, "1D")


def child(cut: str, out: str):
    if cut != "ref":
        sys.path.insert(0, str(ROOT / "research" / "revisit" / "audit"))
        import worker
        worker.install_cut(cut, "ml-classifier-tune")
        shutil.rmtree(worker.bt.CACHE_DIR, ignore_errors=True)   # don't leave files in audit/
        worker.bt.CACHE_DIR = Path(tempfile.mkdtemp(prefix="mlc_cut_"))
    ts1, w1 = build()
    np.savez(out, ts=ts1.as_unit("ns").asi8, w=w1)


def main():
    if len(sys.argv) == 3:
        return child(sys.argv[1], sys.argv[2])
    tmp = Path(tempfile.mkdtemp(prefix="mlc_cutres_"))
    ref = tmp / "ref.npz"
    subprocess.run([sys.executable, __file__, "ref", str(ref)], check=True)
    z = np.load(ref)
    ok_all = True
    for cut in CUTS:
        out = tmp / (cut.replace(" ", "_").replace(":", "") + ".npz")
        subprocess.run([sys.executable, __file__, cut, str(out)], check=True)
        c = np.load(out)
        n = len(c["ts"])
        assert np.array_equal(c["ts"], z["ts"][:n]), "timestamps differ"
        diff = ~np.all(np.isclose(c["w"], z["w"][:n], rtol=0, atol=1e-12), axis=1)
        early = int(diff[:max(n - 2, 0)].sum())
        ok = early == 0
        ok_all &= ok
        print(json.dumps({"cut": cut, "bars": n, "diff_before_last2": early,
                          "diff_total": int(diff.sum()), "pass": ok}), flush=True)
    shutil.rmtree(tmp, ignore_errors=True)
    print("ALL PASS" if ok_all else "FAIL")
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
