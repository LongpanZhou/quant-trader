"""Write the verified new-strategy curves from their one-shot holdout runs."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NEW = ROOT / "research" / "new"
CURVES = NEW / "curves"
META = json.loads((NEW / "META.json").read_text(encoding="utf-8"))


def main() -> None:
    CURVES.mkdir(parents=True, exist_ok=True)
    for strategy in META["strategies"]:
        slug = strategy["slug"]
        holdout = json.loads((NEW / slug / "holdout.json").read_text(encoding="utf-8"))
        curve = holdout["daily_curve"]
        dates, values = curve["dates"], curve["values"]
        if len(dates) != len(values):
            raise SystemExit(f"{slug}: holdout curve length mismatch")
        if dates[0] != "2016-01-04" or dates[-1] != "2026-10-23":
            raise SystemExit(f"{slug}: unexpected curve range {dates[0]}..{dates[-1]}")
        (CURVES / f"{slug}.json").write_text(json.dumps({
            "slug": slug,
            "dates": dates,
            "values": values,
        }), encoding="utf-8")
        print(f"{slug:30s} {len(dates)} days  {values[-1]/values[0]:8.2f}x")


if __name__ == "__main__":
    main()
