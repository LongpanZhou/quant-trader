"""Own look-ahead cut test for strategy.build_weights (pattern of audit/cut_direct.py, cache kept in _tune/)."""
import sys, json, subprocess, shutil
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
AUD = HERE.parents[1] / "audit"
sys.path.insert(0, str(AUD))
import worker  # noqa
worker.CACHE = HERE / "cutcache"
from worker import bt  # noqa
REF = HERE / "cutcache" / "ref.npz"

def weights():
    sys.path.insert(0, str(HERE.parent))
    import strategy as S
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), S.DEV_START, S.DEV_END, "1min")
    return ts, S.build_weights(ts, o, c)[0]

if sys.argv[1] == "ref":
    (HERE / "cutcache").mkdir(exist_ok=True)
    ts, w = weights(); np.savez(REF, ts=ts.as_unit("ns").asi8, w=w); print("ref", len(ts))
elif sys.argv[1] == "all":
    subprocess.run([sys.executable, __file__, "ref"], check=True)
    for cut in ("2020-03-12 11:07", "2022-09-13 10:41"):
        subprocess.run([sys.executable, __file__, cut], check=True)
    shutil.rmtree(HERE / "cutcache", ignore_errors=True)
else:
    cut = sys.argv[1]
    worker.install_cut(cut, "intraday-momentum-tune")
    ts, w = weights()
    z = np.load(REF); n = len(ts)
    assert np.array_equal(z["ts"][:n], ts.as_unit("ns").asi8)
    diff = ~np.all(np.isclose(w, z["w"][:n], rtol=0, atol=1e-12), axis=1)
    early = diff[:max(n - 2, 0)]
    print(json.dumps({"cut": cut, "bars": n, "end": str(ts[-1]), "diff_total": int(diff.sum()),
                      "diff_before_last2": int(early.sum()), "PASS": not early.any()}))
