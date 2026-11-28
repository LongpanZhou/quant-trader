"""Remove the near-flat strategies from the visible library and site.

Criterion: full-window daily-close CAGR below 5% (2016-2026, 10.8 years).
None of the removed names is a family winner.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NEW = ROOT / "research" / "new"
REV = ROOT / "research" / "revisit"
WEB = ROOT / "web" / "public" / "data"

FLAT = [
    "drawdown-stop-overlay",
    "opening-range-breakout",
    "donchian-breakout",
    "drawdown-regime",
    "vol-kelly-overlay",
    "ensemble-signals",
    "daily-regime-minute-entry",
    "stop-reentry-recovery",
    "gap-fill-fade",
    "dynamic-leverage-throttle",
    "volume-orderflow",
    "winner-ensemble-blend",
    "gap-capitulation-reversal",
]


def main() -> None:
    all_data = json.loads((WEB / "compare" / "all.json").read_text(encoding="utf-8"))
    metrics = {m["id"]: m for m in all_data["metrics"]}
    for slug in FLAT:
        m = metrics[slug]
        assert not m.get("family_winner"), slug
        assert m["cagr"] < 0.05, (slug, m["cagr"])
        print(f"{slug:34s} {m['cagr']*100:6.2f}%  {m['dd']*100:5.2f}% DD")

    lib = json.loads((NEW / "LIBRARY.json").read_text(encoding="utf-8"))
    before = len(lib["strategies"])
    lib["strategies"] = [r for r in lib["strategies"] if r["slug"] not in FLAT]
    (NEW / "LIBRARY.json").write_text(json.dumps(lib, indent=1), encoding="utf-8")

    meta = json.loads((NEW / "META.json").read_text(encoding="utf-8"))
    meta["strategies"] = [r for r in meta["strategies"] if r["slug"] not in FLAT]
    (NEW / "META.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")

    removed = []
    for slug in FLAT:
        for p in (
            REV / "curves_full" / f"{slug}.json",
            NEW / "curves" / f"{slug}.json",
            WEB / "research" / f"{slug}.json",
            WEB / "research" / "code" / f"{slug}.py",
        ):
            if p.exists():
                p.unlink()
                removed.append(str(p.relative_to(ROOT)))

    note = [
        "# Near-flat strategy removal",
        "",
        "Criterion: full-window 2016-2026 daily-close CAGR below **5%**.",
        "None of these was a family winner.  Source strategy directories are",
        "retained for provenance, but their curves, detail pages, library",
        "records and site cards are removed.",
        "",
        "| Removed | Full CAGR | Full DD |",
        "|---|---:|---:|",
    ]
    for slug in FLAT:
        m = metrics[slug]
        note.append(f"| `{slug}` | {m['cagr']*100:.2f}% | {m['dd']*100:.2f}% |")
    (NEW / "FLAT_REMOVAL.md").write_text("\n".join(note) + "\n", encoding="utf-8")

    print(f"library {before} -> {len(lib['strategies'])}")
    print(f"meta {len(meta['strategies'])}")
    print(f"deleted {len(removed)} files")


if __name__ == "__main__":
    main()
