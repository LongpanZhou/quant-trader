"""Validate every LIBRARY_ENTRY.json written by the research agents."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NEW = ROOT / "research" / "new"
FAMILIES = {
    "trend-vol", "vol-crash", "relative", "event-recovery", "calendar",
    "session-timing", "short-reversal", "intraday-microstructure",
    "rebalance-flow", "ml-microstructure", "other",
}
REQUIRED = {
    "slug", "name", "family", "tagline", "summary", "dev", "full",
    "above_tqqq", "status", "caveat", "source", "visible",
}

errors: list[str] = []
entries = []
for path in sorted(NEW.glob("*/LIBRARY_ENTRY.json")):
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        errors.append(f"{path.parent.name}: invalid JSON: {exc}")
        continue
    missing = REQUIRED - set(d)
    if missing:
        errors.append(f"{path.parent.name}: missing {sorted(missing)}")
        continue
    if d["family"] not in FAMILIES:
        errors.append(f"{d['slug']}: unknown family {d['family']}")
    if d["status"] not in {"failed", "dev-only", "verified-full"}:
        errors.append(f"{d['slug']}: unknown status {d['status']}")
    full = d.get("full")
    if full:
        above = full["cagr"] > 0.3754 and full["max_drawdown"] < 0.8168
        if bool(d["above_tqqq"]) != above:
            errors.append(f"{d['slug']}: above_tqqq={d['above_tqqq']} but metrics say {above}")
    elif d["above_tqqq"]:
        errors.append(f"{d['slug']}: above_tqqq true without a full holdout")
    entries.append(d)

slugs = [e["slug"] for e in entries]
dupes = {s for s in slugs if slugs.count(s) > 1}
if dupes:
    errors.append(f"duplicate slugs: {sorted(dupes)}")

print(f"entries: {len(entries)}")
for e in entries:
    print(f"{e['slug']:28s} {e['family']:24s} {e['status']:13s} above={e['above_tqqq']}")
if errors:
    print("\nERRORS")
    for e in errors:
        print(" -", e)
    raise SystemExit(1)
print("\nALL ENTRIES VALID")
