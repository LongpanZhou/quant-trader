"""Look-ahead cut test: build weights on arrays truncated at the cut; earlier weights must match."""
import numpy as np, pandas as pd
from common import *

ts, O, C, H, L, dates, first, last = load()
w_full, _ = S.build_weights(ts, O, C, H, L)
for cut in ("2020-03-12 11:07", "2022-09-13 10:41"):
    j = int(ts.searchsorted(pd.Timestamp(cut, tz="America/New_York")))  # bars starting before cut
    tsc = ts[:j]
    _, f2, l2 = S._sessions(tsc)
    io, ic = S.inverse_qqq(O[:j, :3], C[:j, :3], f2, l2)
    Oc = np.column_stack([O[:j, :3], io]); Cc = np.column_stack([C[:j, :3], ic])
    w_cut, _ = S.build_weights(tsc, Oc, Cc, H[:j], L[:j])
    diff = np.flatnonzero(np.any(np.abs(w_cut - w_full[:j]) > 1e-12, axis=1))
    early = diff[diff < j - 2]
    print(cut, "bars", j, "differing bars", len(diff), "before last-2:", len(early), "PASS" if len(early) == 0 else "FAIL")
    # also check inverse price identical
    print("  inv price identical:", np.allclose(io, O[:j, 3]) and np.allclose(ic, C[:j, 3]))
