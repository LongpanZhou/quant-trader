"""Look-ahead cut test: build weights on data truncated at a cut and compare
with the full-dev weights on every minute before the cut (last 2 bars excepted).
Usage: python tune/cut_test.py "<cut>"   (one cut per process; install_cut patches globals)
"""
import sys, warnings, json; warnings.filterwarnings("ignore")
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(ROOT / "research")); sys.path.insert(0, str(ROOT / "research" / "revisit" / "audit"))
import numpy as np, pandas as pd
import bt
cut = sys.argv[1]
import strategy as S
# full-dev reference (unpatched)
ts1, o1, c1 = bt.panel(S.SYMS, S.DEV_START, S.DEV_END, "1min")
tsd, od, cd = bt.panel(S.SYMS, S.DEV_START, S.DEV_END, "1D")
ref = S.build_weights(ts1, o1, c1, tsd, od, cd)[0]
ref_ts = ts1.as_unit("ns").asi8
import worker  # read-only use of install_cut
import tempfile
worker.CACHE = Path(tempfile.mkdtemp())   # keep scratch panels out of audit/cache
worker.install_cut(cut, "ml-crash-overlay-winner")
ts1c, o1c, c1c = bt.panel(S.SYMS, S.DEV_START, S.DEV_END, "1min")
tsdc, odc, cdc = bt.panel(S.SYMS, S.DEV_START, S.DEV_END, "1D")
cw = S.build_weights(ts1c, o1c, c1c, tsdc, odc, cdc)[0]
n = len(ts1c)
assert np.array_equal(ts1c.as_unit("ns").asi8, ref_ts[:n])
m = n - 2
diff = ~np.all(np.isclose(cw[:m], ref[:m], rtol=0, atol=1e-12), axis=1)
out = {"cut": cut, "bars_before_cut": int(n), "bars_compared": int(m), "bars_differ": int(diff.sum()),
       "last_ts": str(ts1c[-1]), "pass": bool(diff.sum() == 0)}
if diff.any():
    out["first_diff"] = str(ts1c[np.flatnonzero(diff)[0]])
print(json.dumps(out))
