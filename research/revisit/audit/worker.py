"""Run one strategy under an engine hook and save its headline weights.

    python research/revisit/audit/worker.py <slug> dev
    python research/revisit/audit/worker.py <slug> full

dev   runs the strategy exactly as shipped and keeps the engine call whose
      CAGR and max drawdown match result.json windows.dev.1bp (the headline).
full  runs the same source with its data end moved from 2023-12-29 to
      2026-10-23 (the panel end), so the frozen rules are applied to the full
      ten years of 1-minute data. It keeps the call that reproduces the dev
      headline's ts on the dev window and runs to 2026.

The strategy directory is snapshotted before and restored after, so neither
mode changes result.json, logs or caches. Output: audit/cache/<slug>-<mode>.npz
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
HERE = ROOT / "research" / "revisit"
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

sys.path.insert(0, str(HERE))
from run_all import RUNS  # noqa: E402

BARS = 252 * 390
CACHE = HERE / "audit" / "cache"

# Literal dev-end dates and what they become in full mode. 2023-12-30 is an
# exclusive dev end in overnight-crash-filter; 2023-12-01 is the last monthly
# refit in ml-classifier's walk-forward schedule.
FULL_DATES = {
    '"2023-12-29"': '"2026-10-23"',
    '"2023-12-30"': '"2026-10-24"',
    '"2023-12-01"': '"2026-10-01"',
}


# Intraday cut points (both inside the dev window, mid-session).
CUTS = {"cut1": "2020-03-12 11:07", "cut2": "2022-09-13 10:41"}


def install_cut(cut: str, slug: str) -> None:
    """Make every data source stop just before `cut`.

    1-minute bars: keep bars that start before the cut (the 11:06 bar closes
    at 11:07, so it is known). Daily files: drop the cut session itself, whose
    daily bar is not complete yet. Adjustment factors still come from the
    full daily file, as they do in the normal run. bt.panel's disk cache is
    pointed at a scratch folder so no truncated panel is reused elsewhere.
    """
    import shutil
    cut_ts = pd.Timestamp(cut, tz="America/New_York")
    cut_day = cut_ts.date()
    tmp = CACHE / f"panel-{slug}-{cut_ts:%Y%m%d}"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True, exist_ok=True)
    bt.CACHE_DIR = tmp

    orig_read = pd.read_parquet
    orig_load = bt.load_1m
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


def snapshot(d: Path) -> dict[Path, bytes]:
    return {p: p.read_bytes() for p in d.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts}


def restore(d: Path, snap: dict[Path, bytes]) -> list[str]:
    touched = []
    for p in list(d.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts and p not in snap:
            p.unlink()
            touched.append(f"removed {p.name}")
    for p, data in snap.items():
        if not p.exists() or p.read_bytes() != data:
            p.write_bytes(data)
            touched.append(f"restored {p.name}")
    return touched


class Hook:
    """Wrap bt.simulate / bt.simulate_many and inspect every engine call."""

    def __init__(self, mode: str, slug: str):
        self.mode = mode
        self.calls = 0
        self.best = None
        self.best_score = -1.0
        if mode == "dev":
            res = json.loads((HERE / slug / "result.json").read_text(encoding="utf-8"))
            self.target = res["windows"]["dev"]["1bp"]
        else:
            z = np.load(CACHE / f"{slug}-dev.npz")
            self.dev_ts = z["ts"]
            self.dev_w = z["weights"]

    def consider(self, ts, opens, closes, weights, kw, result):
        self.calls += 1
        if ts is None:
            return
        ts_i8 = np.asarray(pd.DatetimeIndex(ts).as_unit("ns").asi8)
        if self.mode == "dev":
            try:
                s = bt.stats(result, BARS)
            except Exception:
                return
            if (abs(s["cagr"] - self.target["cagr"]) < 1e-6
                    and abs(s["max_drawdown"] - self.target["max_drawdown"]) < 1e-6
                    and self.best is None):
                self.best = (ts_i8, opens, closes, weights, kw)
            return
        # full: same start as the dev headline, longer, weights agree on overlap
        # cut:  same start, shorter (data stops at the cut), agree on overlap
        n = len(self.dev_ts)
        if self.mode.startswith("cut"):
            n = len(ts_i8)
            if n >= len(self.dev_ts) or n < 1000 or ts_i8[0] != self.dev_ts[0]:
                return
            if not np.array_equal(ts_i8, self.dev_ts[:n]):
                return
            w = np.asarray(weights)
            if w.shape[1] != self.dev_w.shape[1]:
                return
            # the last two bars before the cut are allowed to differ (end of
            # data handling); everything earlier must be identical
            m = max(n - 2, 0)
            agree = float(np.mean(np.all(np.isclose(w[:m], self.dev_w[:m], rtol=0, atol=1e-12), axis=1)))
            if agree > self.best_score or (agree == self.best_score and n > len(self.best[0])):
                self.best_score = agree
                self.best = (ts_i8, opens, closes, weights, kw)
            return
        if len(ts_i8) <= n or ts_i8[0] != self.dev_ts[0]:
            return
        if not np.array_equal(ts_i8[:n], self.dev_ts):
            return
        w = np.asarray(weights)[:n]
        if w.shape != self.dev_w.shape:
            return
        agree = float(np.mean(np.all(np.isclose(w, self.dev_w, rtol=0, atol=1e-12), axis=1)))
        if agree > self.best_score:
            self.best_score = agree
            self.best = (ts_i8, opens, closes, weights, kw)

    def install(self):
        orig_sim, orig_many = bt.simulate, bt.simulate_many
        hook = self

        def simulate(ts, opens, closes, weights, band=0.02, slippage_bps=1.0,
                     start_equity=bt.START_EQUITY):
            r = orig_sim(ts, opens, closes, weights, band=band,
                         slippage_bps=slippage_bps, start_equity=start_equity)
            hook.consider(ts, opens, closes, weights,
                          dict(band=band, slippage_bps=slippage_bps,
                               start_equity=start_equity), r)
            return r

        def simulate_many(ts, opens, closes, weights_list, band=0.02,
                          slippage_bps=1.0, start_equity=bt.START_EQUITY, threads=None):
            rs = orig_many(ts, opens, closes, weights_list, band=band,
                           slippage_bps=slippage_bps, start_equity=start_equity,
                           threads=threads)
            for w, r in zip(weights_list, rs):
                hook.consider(ts, opens, closes, w,
                              dict(band=band, slippage_bps=slippage_bps,
                                   start_equity=start_equity), r)
            return rs

        bt.simulate, bt.simulate_many = simulate, simulate_many


def main() -> int:
    slug, mode = sys.argv[1], sys.argv[2]
    flags, env_extra = RUNS[slug]
    os.environ.update(env_extra)
    path = HERE / slug / "strategy.py"
    src = path.read_text(encoding="utf-8-sig")
    if mode == "full":
        for a, b in FULL_DATES.items():
            src = src.replace(a, b)
        # vol-scaled-crash-stop caches its dev panel regardless of dates
        src = src.replace("if CACHE.exists():", "if False:")
        # vol-kelly-overlay caches dev realised vol regardless of dates
        src = src.replace("if cache.exists():", "if False:")

    if mode.startswith("cut"):
        src = src.replace("if CACHE.exists():", "if False:")
        src = src.replace("if cache.exists():", "if False:")
        install_cut(CUTS[mode], slug)

    CACHE.mkdir(parents=True, exist_ok=True)
    hook = Hook(mode, slug)
    hook.install()
    snap = snapshot(path.parent)
    t0 = time.perf_counter()
    err = None
    sys.argv = [str(path), *flags]
    sys.path.insert(0, str(path.parent))
    g = {"__name__": "__main__", "__file__": str(path)}
    try:
        exec(compile(src, str(path), "exec"), g)
    except SystemExit as e:
        if e.code not in (0, None):
            err = f"SystemExit {e.code}"
    except Exception as e:  # report, don't hide
        import traceback
        traceback.print_exc()
        err = f"{type(e).__name__}: {e}"
    finally:
        touched = restore(path.parent, snap)
        if mode.startswith("cut"):
            import shutil
            shutil.rmtree(bt.CACHE_DIR, ignore_errors=True)
    secs = time.perf_counter() - t0

    meta = {"slug": slug, "mode": mode, "calls": hook.calls, "error": err,
            "seconds": round(secs, 1), "restored": touched,
            "match_score": hook.best_score if mode != "dev" else None}
    if hook.best is None:
        meta["found"] = False
        print(json.dumps(meta))
        (CACHE / f"{slug}-{mode}.json").write_text(json.dumps(meta), encoding="utf-8")
        return 3
    ts_i8, o, c, w, kw = hook.best
    np.savez(CACHE / f"{slug}-{mode}.npz", ts=ts_i8, opens=np.asarray(o, float),
             closes=np.asarray(c, float), weights=np.asarray(w, float))
    meta.update(found=True, kw=kw, bars=int(len(ts_i8)), k=int(np.asarray(w).shape[1]))
    (CACHE / f"{slug}-{mode}.json").write_text(json.dumps(meta), encoding="utf-8")
    print(json.dumps(meta))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
