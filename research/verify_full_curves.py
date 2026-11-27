"""Verify every 2016-2026 full curve against the frozen development result.

The website's uniform comparison reads `research/revisit/curves_full/*.json`.
A curve is only trustworthy if its 2016-01-04 .. 2023-12-29 slice reproduces the
strategy's frozen `result.json` development metrics. The dev result is marked on
1-minute bars while the curve is marked on daily closes, so small differences
are expected; a multi-point gap means the curve came from different code.

Usage:
    python research/verify_full_curves.py
    python research/verify_full_curves.py --tolerance-cagr 0.02 --tolerance-dd 0.03
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "research" / "revisit"
CURVES = HERE / "curves_full"
DEV_END = pd.Timestamp("2023-12-29")


def daily_metrics(values: list[float], dates: list[str]) -> dict[str, float]:
    s = pd.Series(values, index=pd.to_datetime(dates)).dropna()
    s = s[s.index <= DEV_END]
    if len(s) < 2:
        return {}
    eq = s.to_numpy(dtype=float)
    years = (s.index[-1] - s.index[0]).days / 365.25
    peak = np.maximum.accumulate(eq)
    rets = np.diff(eq) / eq[:-1]
    return {
        "cagr": float((eq[-1] / eq[0]) ** (1 / years) - 1) if years > 0 else 0.0,
        "dd": float(-(eq / peak - 1).min()),
        "sharpe": float(rets.mean() / rets.std() * np.sqrt(252)) if rets.std() else 0.0,
        "start": str(s.index[0].date()),
        "end": str(s.index[-1].date()),
        "n": int(len(s)),
    }


def load_dev(path: Path) -> dict[str, float] | None:
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    windows = d.get("windows") or {}
    m = ((windows.get("dev") or {}).get("1bp")
         or (windows.get("dev") or {}).get("5bp")
         or {})
    if "cagr" not in m:
        return None
    return m


def result_candidates(slug: str) -> list[tuple[str, dict[str, float]]]:
    """The current post-tune result and, if tuned, the frozen pre-tune result."""
    out = []
    cur = HERE / slug / "result.json"
    if cur.exists():
        m = load_dev(cur)
        if m is not None:
            out.append(("current", m))
    pre = HERE / slug / "_before_tune" / "result.json"
    if pre.exists():
        m = load_dev(pre)
        if m is not None:
            out.append(("pre_tune", m))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tolerance-cagr", type=float, default=0.02,
                    help="absolute CAGR gap that counts as stale (default 2 pp)")
    ap.add_argument("--dd-warning", type=float, default=0.05,
                    help="absolute DD gap worth printing as a mark difference (default 5 pp)")
    args = ap.parse_args()

    paths = sorted(CURVES.glob("*.json"))
    print(f"{'slug':32s} {'curveCAGR':>9s} {'resultCAGR':>10s} {'dCAGR':>7s} "
          f"{'curveDD':>8s} {'resultDD':>8s} {'dDD':>7s}  {'status':10s} freeze")
    stale = []
    missing = []
    for path in paths:
        d = json.loads(path.read_text(encoding="utf-8"))
        slug = d["slug"]
        m = daily_metrics(d["values"], d["dates"])
        cands = result_candidates(slug)
        if not m:
            missing.append((slug, "no dev slice"))
            continue
        if not cands:
            print(f"{slug:32s} {m['cagr']*100:8.2f}% {'n/a':>10s} {'-':>7s} "
                  f"{m['dd']*100:7.2f}% {'n/a':>8s} {'-':>7s}  {'no result':10s} -")
            continue
        # The published curve may belong to the frozen pre-tune result rather
        # than the current post-tune result.  Pick the freeze that actually
        # reproduces the curve instead of calling a pre-registered curve stale.
        freeze, r = min(cands, key=lambda kv: abs(m["cagr"] - kv[1]["cagr"]))
        dc = m["cagr"] - r["cagr"]
        dd = m["dd"] - r["max_drawdown"]
        # Staleness is judged on CAGR: the dev result is marked on 1-minute bars
        # and the curve on daily closes, so drawdown can legitimately differ.
        bad = abs(dc) > args.tolerance_cagr
        status = "STALE?" if bad else ("ok (DD mark)" if abs(dd) > args.dd_warning else "ok")
        if bad:
            stale.append((slug, dc, dd, freeze))
        print(f"{slug:32s} {m['cagr']*100:8.2f}% {r['cagr']*100:9.2f}% "
              f"{dc*100:+6.1f}pp {m['dd']*100:7.2f}% {r['max_drawdown']*100:7.2f}% "
              f"{dd*100:+6.1f}pp  {status:10s} {freeze}")

    print()
    print(f"curves: {len(paths)}  stale: {len(stale)}  missing: {len(missing)}")
    if stale:
        print("stale curves (regenerate before trusting the full-window ranking):")
        for slug, dc, dd, freeze in sorted(stale, key=lambda x: x[0]):
            print(f"  {slug:32s} dCAGR {dc*100:+6.1f}pp  dDD {dd*100:+6.1f}pp  ({freeze})")
    if missing:
        print("missing dev slices:")
        for slug, why in missing:
            print(f"  {slug}: {why}")
    return 1 if stale or missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
