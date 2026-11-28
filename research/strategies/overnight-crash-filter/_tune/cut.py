"""Look-ahead cut test for the current strategy.py defaults.

    python cut.py "2020-03-12 11:07"      # one cut, run in its own process
    python cut.py                          # both brief cuts
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
CUTS = ("2020-03-12 11:07", "2022-09-13 10:41")


def one(cut):
    sys.path.insert(0, str(HERE.parents[1] / "audit"))
    import worker  # read-only use of the audit helper
    worker.CACHE = HERE / "cut_cache"           # keep scratch panels in our own folder
    import pandas as pd
    from common import load_strategy, bt, DEV_START, DEV_END
    mod = load_strategy()
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END, "1min", warmup_days=0)
    w_full, _ = mod.build_weights(ts, o, c)
    worker.install_cut(cut, "overnight-crash-filter")
    ts2, o2, c2 = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END, "1min", warmup_days=0)
    w_cut, _ = mod.build_weights(ts2, o2, c2)
    m = len(ts2)
    assert (ts[:m] == ts2).all()
    diff = np.flatnonzero(np.abs(w_full[:m] - w_cut).max(axis=1) > 1e-12)
    # the last bar of truncated data is end-of-data; anything earlier must match
    bad = diff[diff < m - 2]
    print(f"cut {cut}: bars before cut {m}, differing bars {len(diff)} "
          f"(at {[str(ts2[i]) for i in diff[:3]]}), before end-of-data: {len(bad)}")
    return len(bad)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        sys.exit(1 if one(sys.argv[1]) else 0)
    rc = 0
    for cut in CUTS:
        rc |= subprocess.call([sys.executable, __file__, cut], cwd=str(HERE))
    print("CUT TEST", "PASS" if rc == 0 else "FAIL")
    sys.exit(rc)
