"""Own look-ahead cut test (tuning 2026-11-27), same semantics as
audit/worker.py:install_cut: 1-minute bars before the cut, daily files without
the cut session. Every weight before the cut must be unchanged."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import strategy as S  # noqa: E402

ts, op, cl = S.load(S.DEV_END)
w_full, _ = S.build_weights(ts, op, cl)
orig_read = pd.read_parquet
ok = True
for cut in ("2020-03-12 11:07", "2022-09-13 10:41"):
    c = pd.Timestamp(cut, tz="America/New_York")

    def rp(*a, _d=c.date(), **k):
        df = orig_read(*a, **k)
        if "date" in df.columns and "ts" not in df.columns:
            df = df[pd.to_datetime(df["date"]).dt.date < _d]
        return df

    pd.read_parquet = rp
    n = int(ts.searchsorted(c))
    w_cut, _ = S.build_weights(ts[:n], op[:n], cl[:n])
    pd.read_parquet = orig_read
    same = np.array_equal(w_full[:n], w_cut)
    # the cut session's own bars are allowed to differ only if the rule used
    # an incomplete session; daily rules decide from the prior close, so all
    # bars before the cut should match exactly.
    print(f"cut {cut}: {n:,} bars before cut, identical={same}, "
          f"max|diff|={np.abs(w_full[:n] - w_cut).max():.3g}")
    ok &= same
print("PASS" if ok else "FAIL")
