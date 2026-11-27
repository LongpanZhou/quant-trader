import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
OUT = WEB / "public" / "data" / "catalog" / "strategies.json"

presets_meta = json.loads((WEB / "public" / "data" / "strategies.json").read_text(encoding="utf-8"))
research = json.loads((WEB / "public" / "data" / "research" / "rebuild.json").read_text(encoding="utf-8"))

items = []
for strategy in presets_meta["strategies"]:
    slug = strategy["slug"]
    ten = json.loads((WEB / "public" / "data" / slug / "10y.json").read_text(encoding="utf-8"))
    five = json.loads((WEB / "public" / "data" / slug / "5y.json").read_text(encoding="utf-8"))
    items.append({
        "id": f"preset:{slug}",
        "slug": slug,
        "kind": "preset",
        "name": strategy["name"],
        "group": "Preset",
        "status": "Runnable",
        "tagline": strategy["tagline"],
        "summary": strategy["description"],
        "window": "10y/5y",
        "metrics": {
            "cagr10": ten["metrics"]["cagr"],
            "dd10": ten["metrics"]["maxDrawdown"],
            "cagr5": five["metrics"]["cagr"],
            "dd5": five["metrics"]["maxDrawdown"],
        },
        "href": f"/strategies/{slug}",
        "runnable": True,
        "accent": strategy.get("accent", "#9ae6a5"),
        "tags": strategy.get("tags", []),
        "papersCount": 0,
        "provenanceCount": 0,
    })

for s in research["strategies"]:
    slug = s["slug"]
    items.append({
        "id": f"research:{slug}",
        "slug": slug,
        "kind": "research",
        "name": s["name"],
        "group": "Strategy",
        "status": "Strategy",
        "tagline": s.get("tagline", ""),
        "summary": s.get("summary", ""),
        "window": "2016-2026",
        "cagr": s["cagr"],
        "dd": s["dd"],
        "sharpe": s["sharpe"],
        "metrics": {
            "cagr10": s["cagr"],
            "dd10": s["dd"],
            "cagr5": s["cagr"],
            "dd5": s["dd"],
        },
        "href": f"/research/{slug}",
        "runnable": False,
        "accent": "#9ae6a5",
        "tags": ["2016-2026"],
        "papersCount": 0,
        "provenanceCount": 0,
    })

items.sort(key=lambda item: (0 if item["runnable"] else 1, -item.get("cagr", item["metrics"]["cagr10"])))

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps({"generated": "2026-11-27", "strategies": items}, indent=1), encoding="utf-8")
print(f"wrote {OUT} ({OUT.stat().st_size/1024:.0f} KB) with {len(items)} strategies")
