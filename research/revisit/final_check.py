"""Final consistency check for the uniform All-strategies data.

Checks:
- every visible full 2016-2026 curve exists and is well formed;
- all.json has the same dates and one series/metric per curve;
- every series covers the full window with no nulls;
- every metric is reproducible from its own daily-close series;
- no editorial fields (group/status/holdout/corr) leaked into the metrics;
- the old chart data is still present.

The per-curve freeze validation (pre-tune vs current result.json) lives in
`research/verify_full_curves.py`.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "research" / "revisit"
CURVES_FULL = HERE / "curves_full"
NEW = ROOT / "research" / "new"
NEW_CURVES = NEW / "curves"
META = {s["slug"] for s in json.loads((NEW / "META.json").read_text(encoding="utf-8"))["strategies"]
        if s.get("visible", True)}
COMPARE = ROOT / "web" / "public" / "data" / "compare"

errors: list[str] = []


def stats(values: list[float], dates: list[str]) -> dict[str, float]:
    from datetime import date

    eq = np.asarray(values, dtype=float)
    years = (date.fromisoformat(dates[-1]) - date.fromisoformat(dates[0])).days / 365.25
    peak = np.maximum.accumulate(eq)
    rets = np.diff(eq) / eq[:-1]
    return {
        "cagr": float((eq[-1] / eq[0]) ** (1 / years) - 1) if years > 0 else 0.0,
        "dd": float(-(eq / peak - 1).min()),
        "sharpe": float(rets.mean() / rets.std() * np.sqrt(252)) if rets.std() else 0.0,
    }


# --- development results --------------------------------------------------- #
results = {}
for p in sorted(HERE.glob("*/result.json")):
    d = json.loads(p.read_text(encoding="utf-8"))
    m = (((d.get("windows") or {}).get("dev") or {}).get("1bp") or {})
    if "cagr" not in m:
        errors.append(f"{p.parent.name}: no dev 1bp")
    results[p.parent.name] = d
print(f"result.json files: {len(results)}")

# --- full curves ----------------------------------------------------------- #
curves = {}
for p in sorted(CURVES_FULL.glob("*.json")):
    d = json.loads(p.read_text(encoding="utf-8"))
    slug = d.get("slug", p.stem)
    if len(d.get("dates", [])) != len(d.get("values", [])):
        errors.append(f"{slug}: full curve dates/values length mismatch")
    if not d.get("dates"):
        errors.append(f"{slug}: empty full curve")
    curves[slug] = d
for p in sorted(NEW_CURVES.glob("*.json")):
    d = json.loads(p.read_text(encoding="utf-8"))
    slug = d.get("slug", p.stem)
    if slug not in META:
        continue
    if len(d.get("dates", [])) != len(d.get("values", [])):
        errors.append(f"{slug}: full curve dates/values length mismatch")
    if not d.get("dates"):
        errors.append(f"{slug}: empty full curve")
    curves[slug] = d
expected_curves = len(list(CURVES_FULL.glob("*.json"))) + len(META)
print(f"full curves: {len(curves)} (expected {expected_curves})")
if len(curves) != expected_curves:
    errors.append(f"expected {expected_curves} full curves, got {len(curves)}")

# --- all.json -------------------------------------------------------------- #
all_data = json.loads((COMPARE / "all.json").read_text(encoding="utf-8"))
dates = all_data.get("dates", [])
series = all_data.get("series", [])
metrics = all_data.get("metrics", [])
print(f"all.json: {len(dates)} days, {len(series)} curves, {len(metrics)} metrics, "
      f"{all_data.get('start')}..{all_data.get('end')}")
if len(dates) != 2718:
    errors.append(f"expected 2718 days, got {len(dates)}")
if dates and (dates[0] != "2016-01-04" or dates[-1] != "2026-10-23"):
    errors.append(f"unexpected date range {dates[0]}..{dates[-1]}")

by_id = {s["id"]: s for s in series}
for s in series:
    vals = s.get("values", [])
    if len(vals) != len(dates):
        errors.append(f"{s['id']}: {len(vals)} values for {len(dates)} dates")
    if any(v is None for v in vals):
        errors.append(f"{s['id']}: contains nulls")
    if any(v <= 0 for v in vals):
        errors.append(f"{s['id']}: non-positive equity")

for m in metrics:
    s = by_id.get(m["id"])
    if s is None:
        errors.append(f"{m['id']}: metric has no series")
        continue
    calc = stats(s["values"], dates)
    for field in ("cagr", "dd", "sharpe"):
        if abs(calc[field] - m[field]) > 1e-9:
            errors.append(f"{m['id']}: {field} {m[field]} != recomputed {calc[field]}")

strategy_metrics = [m for m in metrics if not m.get("benchmark")]
bench_metrics = [m for m in metrics if m.get("benchmark")]
print(f"strategies: {len(strategy_metrics)}  benchmarks: {len(bench_metrics)}")
if len(strategy_metrics) != expected_curves:
    errors.append(f"expected {expected_curves} strategies, got {len(strategy_metrics)}")
if len(bench_metrics) != 2:
    errors.append(f"expected 2 benchmarks, got {len(bench_metrics)}")

for m in metrics:
    for forbidden in ("group", "status", "holdout", "corr"):
        if forbidden in m:
            errors.append(f"{m['id']}: forbidden field {forbidden}")

# --- preserved old data ---------------------------------------------------- #
old = json.loads((COMPARE / "research.json").read_text(encoding="utf-8"))
arch = json.loads((COMPARE / "all-original.json").read_text(encoding="utf-8"))
print(f"research.json (old): {len(old['series'])} curves, {len(old['metrics'])} metrics")
print(f"all-original.json: {len(arch['series'])} curves, {len(arch['metrics'])} metrics")
if len(old["series"]) != 10 or len(arch["series"]) != 10:
    errors.append("old chart data was not preserved")

if errors:
    print("\nERRORS")
    for e in errors:
        print(" -", e)
    raise SystemExit(1)
print("\nALL CHECKS PASS")
