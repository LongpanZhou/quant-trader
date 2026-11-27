"""Build the 27 uniform Research-library cards from the All-strategies data."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(r"C:\Users\27175\Desktop\quant-trader-research")
HERE = ROOT / "research" / "revisit"
ALL = ROOT / "web" / "public" / "data" / "compare" / "all.json"
OUT = ROOT / "web" / "public" / "data" / "research" / "rebuild.json"


def main():
    all_data = json.loads(ALL.read_text())
    rows = []
    for m in all_data["metrics"]:
        if m.get("benchmark"):
            continue
        slug = m["id"]
        if slug == "ratio-froth":
            tagline = (
                "The original 165-day shared-base leader, included as a strategy "
                "for the same-window comparison."
            )
            summary = "No separate treatment; same 2016-2026 window and metrics."
        else:
            d = json.loads((HERE / slug / "result.json").read_text())
            tagline = d.get("idea", "")
            summary = d.get("hypothesis", "")
        rows.append({
            "slug": slug,
            "name": m["name"],
            "tagline": tagline,
            "summary": summary,
            "cagr": m["cagr"],
            "dd": m["dd"],
            "sharpe": m["sharpe"],
        })
    rows.sort(key=lambda r: -r["cagr"])
    OUT.write_text(json.dumps({
        "generated": "2026-11-27",
        "window": "2016-2026",
        "strategies": rows,
    }, indent=1), encoding="utf-8")
    print(f"wrote {OUT} ({len(rows)} rows)")


if __name__ == "__main__":
    main()

