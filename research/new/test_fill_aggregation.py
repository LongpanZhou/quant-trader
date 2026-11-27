"""Regression test for per-window fill/turnover aggregation.

Run:
    python research/new/test_fill_aggregation.py

Checks, for two frozen strategies:
  * the full-window fill-log totals equal the old (compiled) full-run totals;
  * full fills/notional equal dev + holdout window slices;
  * each window's turnover equals its traded notional / its starting equity;
  * the full-window row still matches the existing holdout.json full row.

This is read-only: it does not write any holdout.json or strategy file.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(ROOT / "research" / "new"))
import bt  # noqa: E402
import run_holdout as R  # noqa: E402

CASES = ["drawdown-recovery-v2", "family-session-timing"]


def build_weights(slug: str, ts, o, c) -> np.ndarray:
    mod = R.load(slug)
    out = R.build_full(mod, ts, o, c)
    w = out[0] if isinstance(out, tuple) else out
    return R.to_three(np.asarray(w, dtype=float), len(ts))


def main() -> None:
    print("loading full 1-minute panel ...")
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), R.START, R.END, "1min",
                        warmup_days=0)
    print(f"panel {len(ts):,} bars {ts[0]} .. {ts[-1]}")

    rows = []
    for slug in CASES:
        t0 = time.time()
        w = build_weights(slug, ts, o, c)
        print(f"{slug}: weights {w.shape} ({time.time()-t0:.1f}s), simulating ...")

        # fill_log=True keeps the compiled metrics and adds the Python log.
        r_log = bt.run(ts, o, c, w, R.START, band=0.02, slippage_bps=1.0,
                       fill_log=True)
        r_ref = bt.run(ts, o, c, w, R.START, band=0.02, slippage_bps=1.0)
        assert r_log["fills"] == len(r_log["fills_log"]), "log length != fills"
        assert r_log["fills"] == r_ref["fills"], "fill count changed"
        assert abs(r_log["turnover"] - r_ref["turnover"]) < 1e-12, "turnover changed"
        # Full-run sanity: log notional / $100k must equal the old turnover.
        log_notional = sum(float(x["notional"]) for x in r_log["fills_log"])
        assert abs(log_notional / 100_000.0 - r_ref["turnover"]) < 1e-9

        dev = R.minute_stats(r_log, R.START, R.DEV_END)
        hold = R.minute_stats(r_log, "2024-01-02", R.END)
        full = R.minute_stats(r_log, R.START, R.END)
        ten = R.minute_stats(r_log, R.TEN, R.END)
        five = R.minute_stats(r_log, R.FIVE, R.END)

        # The core partition check.
        assert full["fills"] == dev["fills"] + hold["fills"], "fills do not add"
        assert abs(full["traded_notional"] - dev["traded_notional"]
                   - hold["traded_notional"]) < 1e-6, "notional does not add"
        # Full-window totals still equal the old full-run totals.
        assert full["fills"] == r_ref["fills"], "full fills != old full fills"
        assert abs(full["turnover"] - r_ref["turnover"]) < 1e-9, \
            "full turnover != old full turnover"
        ref_notional = r_ref["turnover"] * 100_000.0
        assert abs(full["traded_notional"] - ref_notional) <= max(
            1e-4, 1e-12 * abs(ref_notional)), \
            "full notional != old full notional"
        # Window denominator is the first marked equity in that window.
        for win in (dev, hold, full, ten, five):
            assert win["turnover_denominator"] == "window_start_equity"
            assert abs(win["turnover"] - win["traded_notional"]
                       / win["turnover_start_equity"]) < 1e-12

        old_path = ROOT / "research" / "new" / slug / "holdout.json"
        if old_path.exists():
            old = json.loads(old_path.read_text(encoding="utf-8"))
            old_full = old["windows"]["full"]["1bp"]
            assert full["fills"] == int(old_full["fills"]), \
                "full fills != old JSON full fills"
            assert abs(full["turnover"] - old_full["turnover"]) < 1e-6, \
                "full turnover != old JSON full turnover"
            old_label = f"{int(old_full['fills'])}/{old_full['turnover']:.2f}"
        else:
            old_label = "no old json"

        rows.append((slug, dev, hold, full, ten, five, old_label))
        print(f"  dev {dev['fills']} / {dev['turnover']:.2f}x  "
              f"hold {hold['fills']} / {hold['turnover']:.2f}x  "
              f"full {full['fills']} / {full['turnover']:.2f}x  "
              f"old full {old_label}  ({time.time()-t0:.1f}s)")

    print("\nslug                     dev fills/turn   hold fills/turn   "
          "full fills/turn   old full")
    for slug, dev, hold, full, ten, five, old_label in rows:
        print(f"{slug:24s} {dev['fills']:5d}/{dev['turnover']:9.2f}x "
              f"{hold['fills']:5d}/{hold['turnover']:8.2f}x "
              f"{full['fills']:6d}/{full['turnover']:9.2f}x  {old_label}")
    print("\nOK: fill totals and per-window notional partition cleanly.")


if __name__ == "__main__":
    main()
