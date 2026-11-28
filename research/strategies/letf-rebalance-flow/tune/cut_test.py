"""Look-ahead cut test (own copy of audit/worker.install_cut logic; caches in
this folder). Usage: python cut_test.py [module_path]"""
import importlib.util, shutil, sys
from pathlib import Path
import numpy as np
import pandas as pd
from common import bt, DEV0, DEV1, HERE

MOD = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "strategy.py"
CUTS = sys.argv[2].split(",") if len(sys.argv) > 2 else ["2020-03-12 11:07", "2022-09-13 10:41"]


def loadmod():
    spec = importlib.util.spec_from_file_location("s_" + str(abs(hash(str(MOD)))), MOD)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def build():
    m = loadmod()
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), DEV0, DEV1, "1min", warmup_days=0)
    return ts, m.build_weights(ts, o, c)[0]


ts0, w0 = build()
orig_read, orig_load, orig_cache = pd.read_parquet, bt.load_1m, bt.CACHE_DIR
for cut in CUTS:
    cut_ts = pd.Timestamp(cut, tz="America/New_York"); cut_day = cut_ts.date()
    tmp = HERE / f"_cutcache_{cut_ts:%Y%m%d}"; shutil.rmtree(tmp, ignore_errors=True); tmp.mkdir()
    bt.CACHE_DIR = tmp
    state = {"inside": 0}

    def rp(*a, **k):
        df = orig_read(*a, **k)
        if state["inside"]:
            return df
        if "date" in df.columns and "ts" not in df.columns:
            d = pd.to_datetime(df["date"]); d = d.dt.tz_localize(None) if d.dt.tz is not None else d
            df = df[d.dt.date < cut_day]
        elif "ts" in df.columns:
            t = pd.to_datetime(df["ts"], utc=True).dt.tz_convert("America/New_York"); df = df[t < cut_ts]
        return df

    def l1(sym):
        state["inside"] += 1
        try:
            df = orig_load(sym)
        finally:
            state["inside"] -= 1
        return df[df["ts"] < cut_ts].reset_index(drop=True)

    pd.read_parquet, bt.load_1m = rp, l1
    try:
        ts1, w1 = build()
    finally:
        pd.read_parquet, bt.load_1m, bt.CACHE_DIR = orig_read, orig_load, orig_cache
        shutil.rmtree(tmp, ignore_errors=True)
    n = len(ts1)
    assert np.array_equal(ts0[:n].as_unit("ns").asi8, ts1.as_unit("ns").asi8)
    diff = ~np.all(np.isclose(w0[:n], w1, rtol=0, atol=1e-12), axis=1)
    early = diff[:max(n - 2, 0)]
    print(f"cut {cut}: bars {n:,} end {ts1[-1]} differ total {int(diff.sum())} "
          f"before last 2: {int(early.sum())} -> {'PASS' if not early.any() else 'FAIL'}"
          + (f" first {ts1[np.flatnonzero(early)[0]]}" if early.any() else ""))
