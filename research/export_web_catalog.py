"""Write the website's one strategy catalog (web/public/data/catalog/strategies.json).

Every strategy gets one entry and one page, /strategies/<slug>. A strategy that
has a bot.toml in research/strategies/<slug>/ is also run by the Rust bot, so its
settings can be adjusted and re-run in the lab (`adjustable: true`).
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
STRATEGIES = ROOT / "research" / "strategies"
OUT = WEB / "public" / "data" / "catalog" / "strategies.json"

bot_meta = {
    s["slug"]: s
    for s in json.loads((WEB / "public" / "data" / "strategies.json").read_text(encoding="utf-8"))["strategies"]
}
library = json.loads((WEB / "public" / "data" / "research" / "rebuild.json").read_text(encoding="utf-8"))


def adjustable(slug: str) -> bool:
    return (STRATEGIES / slug / "bot.toml").exists() and slug in bot_meta


def bot_metrics(slug: str) -> dict:
    ten = json.loads((WEB / "public" / "data" / slug / "10y.json").read_text(encoding="utf-8"))
    five = json.loads((WEB / "public" / "data" / slug / "5y.json").read_text(encoding="utf-8"))
    return {
        "cagr10": ten["metrics"]["cagr"],
        "dd10": ten["metrics"]["maxDrawdown"],
        "cagr5": five["metrics"]["cagr"],
        "dd5": five["metrics"]["maxDrawdown"],
    }


def entry(slug: str, name: str, tagline: str, summary: str) -> dict:
    can_adjust = adjustable(slug)
    bot = bot_meta.get(slug, {})
    return {
        "id": slug,
        "slug": slug,
        "name": name,
        "status": "Adjustable" if can_adjust else "Strategy",
        "tagline": tagline,
        "summary": summary,
        "href": f"/strategies/{slug}",
        "adjustable": can_adjust,
        "accent": bot.get("accent", "#9ae6a5"),
        "tags": bot.get("tags", []),
    }


items = []
seen = set()
for s in library["strategies"]:
    slug = s["slug"]
    seen.add(slug)
    item = entry(slug, s["name"], s.get("tagline", ""), s.get("summary", ""))
    item.update({
        "window": "2016-2026",
        "cagr": s["cagr"],
        "dd": s["dd"],
        "sharpe": s["sharpe"],
        "metrics": {"cagr10": s["cagr"], "dd10": s["dd"], "cagr5": s["cagr"], "dd5": s["dd"]},
    })
    items.append(item)

# Strategies the bot trades that have no 2016-2026 curve yet (e.g. the S&P 500
# rule, whose Python port is still to do) are listed with the bot's 10y/5y runs.
for slug, s in bot_meta.items():
    if slug in seen:
        continue
    item = entry(slug, s["name"], s["tagline"], s["description"])
    item.update({"window": "10y/5y", "metrics": bot_metrics(slug)})
    items.append(item)

items.sort(key=lambda item: (item["window"] != "2016-2026", -item.get("cagr", item["metrics"]["cagr10"])))

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps({"generated": "2026-11-28", "strategies": items}, indent=1), encoding="utf-8")
print(f"wrote {OUT} ({OUT.stat().st_size/1024:.0f} KB) with {len(items)} strategies, "
      f"{sum(i['adjustable'] for i in items)} adjustable")
