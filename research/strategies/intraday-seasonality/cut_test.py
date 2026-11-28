"""Look-ahead cut test for intraday-seasonality (tuning, 2026-11-27).

Same truncation as audit/worker.py:install_cut (1-minute bars kept only if
they start before the cut; daily files lose the cut session), but the panel
cache is pointed at a temp folder outside audit/. Builds the headline weights
on the full dev panel and on each truncated panel; every weight before the
last two bars of the truncated panel must be identical.

    python research/strategies/intraday-seasonality/cut_test.py
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import strategy as S  # noqa: E402
import bt  # noqa: E402

CUTS = ["2020-03-12 11:07", "2022-09-13 10:41"]
DEV = S.WINDOWS["dev"]


def install_cut(cut: str, tmp: Path) -> None:
    cut_ts = pd.Timestamp(cut, tz="America/New_York")
    cut_day = cut_ts.date()
    bt.CACHE_DIR = tmp
    orig_read, orig_load = pd.read_parquet, bt.load_1m
    state = {"inside": 0}

    def read_parquet(*a, **k):
        df = orig_read(*a, **k)
        if state["inside"]:
            return df
        if "date" in df.columns and "ts" not in df.columns:
            d = pd.to_datetime(df["date"])
            d = d.dt.tz_localize(None) if d.dt.tz is not None else d
            df = df[d.dt.date < cut_day]
        elif "ts" in df.columns:
            t = pd.to_datetime(df["ts"], utc=True).dt.tz_convert("America/New_York")
            df = df[t < cut_ts]
        return df

    def load_1m(symbol):
        state["inside"] += 1
        try:
            df = orig_load(symbol)
        finally:
            state["inside"] -= 1
        return df[df["ts"] < cut_ts].reset_index(drop=True)

    pd.read_parquet = read_parquet
    bt.load_1m = load_1m


def build():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), DEV[0], DEV[1], "1min")
    return ts, S.build_weights(ts, o, c, **S.BASE)[0]


def child(cut: str, out: str) -> None:
    tmp = Path(tempfile.mkdtemp(prefix="is-cut-"))
    try:
        if cut != "ref":
            install_cut(cut, tmp)
        ts, w = build()
        np.savez(out, ts=ts.as_unit("ns").asi8, w=w)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    if len(sys.argv) == 3:
        return child(sys.argv[1], sys.argv[2])
    tmpd = Path(tempfile.mkdtemp(prefix="is-cutres-"))
    paths = {c: str(tmpd / f"{i}.npz") for i, c in enumerate(["ref"] + CUTS)}
    for c, p in paths.items():
        subprocess.run([sys.executable, __file__, c, p], check=True)
    ref = np.load(paths["ref"])
    res = []
    for c in CUTS:
        z = np.load(paths[c])
        n = len(z["ts"])
        assert np.array_equal(ref["ts"][:n], z["ts"]), "timestamps differ"
        diff = ~np.all(np.isclose(z["w"], ref["w"][:n], rtol=0, atol=1e-12), axis=1)
        early = int(diff[: max(n - 2, 0)].sum())
        res.append({"cut": c, "bars": n, "diff_before_last2": early,
                    "diff_total": int(diff.sum()), "pass": early == 0})
        print(f"{c}: {n:,} bars, {early} differ before the last 2, "
              f"{'PASS' if early == 0 else 'FAIL'}")
    shutil.rmtree(tmpd, ignore_errors=True)
    with open(HERE / "cut_test.json", "w", newline="\n", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1)


if __name__ == "__main__":
    main()
