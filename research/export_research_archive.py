"""Export the non-performing research archive and its detail pages."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEW = ROOT / "research" / "new"
WEB = ROOT / "web"
OUT = WEB / "public" / "data" / "research"
ARCHIVE = OUT / "archive.json"
CODE = OUT / "code"

sys.path.insert(0, str(ROOT / "research"))
import export_research_detail as ed  # noqa: E402

LIBRARY = json.loads((NEW / "LIBRARY.json").read_text(encoding="utf-8"))
ALL = json.loads((WEB / "public" / "data" / "compare" / "all.json").read_text(encoding="utf-8"))
VISIBLE = {m["id"] for m in ALL["metrics"]}


def metrics(entry: dict) -> tuple[dict, str]:
    if entry.get("full"):
        f = entry["full"]
        return ({"cagr": f["cagr"], "dd": f["max_dd"], "sharpe": f["sharpe"]},
                "2016-2026")
    d = entry["dev"]
    return ({"cagr": d["cagr"], "dd": d["max_dd"], "sharpe": d["sharpe"]},
            "2016-2023")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    CODE.mkdir(parents=True, exist_ok=True)
    rows = []
    for entry in LIBRARY["strategies"]:
        slug = entry["slug"]
        if not entry.get("source", "").startswith("research/new/"):
            continue
        if slug in VISIBLE or entry.get("above_tqqq"):
            continue
        base = NEW / slug
        report_path = ed.first(base / "report.md")
        hyp_path = ed.first(base / "HYPOTHESIS.md", base / "hypothesis.md")
        code_path = ed.first(base / "strategy.py")
        report_md = ed.read(report_path)
        hyp_md = ed.read(hyp_path)
        spec_md = ed.extract_section(report_md, ("spec", "rules", "signal", "universe",
                                                 "what the strategy does", "mechanism",
                                                 "exact rules"))
        if not spec_md:
            spec_md = ed.extract_section(hyp_md, ("exact rules", "rules", "mechanism"))
        prov_md = ed.extract_section(report_md, ("provenance", "sources", "evidence",
                                                 "papers", "literature", "relationship",
                                                 "differs", "existing work"))
        if not prov_md:
            prov_md = ("## Own test\n\n- **quant-trader research program** - "
                       "Development result and, where available, a one-shot 2024-2026 "
                       "holdout; see `report.md` and `strategy.py`.")
        cards, rejected = ed.parse_bullets(prov_md)
        for card in ed.parse_tables(prov_md):
            key = (card["source"], card["idea"])
            if key not in {(c["source"], c["idea"]) for c in cards}:
                cards.append(card)
        papers = []
        seen = set()
        for card in cards:
            if card.get("url") and card.get("source"):
                key = (card["source"], card["url"])
                if key not in seen:
                    seen.add(key)
                    papers.append({"label": card["source"], "url": card["url"]})
        m, window = metrics(entry)
        code = ed.read(code_path)
        (CODE / f"{slug}.py").write_text(code, encoding="utf-8")
        detail = {
            "slug": slug,
            "name": entry["name"],
            "tagline": entry.get("tagline", ""),
            "summary": entry.get("summary", ""),
            "metrics": m,
            "window": window,
            "archive": True,
            "has_curve": False,
            "assessment": {"verdict": entry.get("status", "failed"),
                           "reason": entry.get("note", "")},
            "paths": {
                "report": ed.rel(report_path),
                "hypothesis": ed.rel(hyp_path),
                "spec": None,
                "provenance": None,
                "code": ed.rel(code_path),
                "code_public": f"/data/research/code/{slug}.py",
            },
            "extracted": {"hypothesis": False, "spec": bool(spec_md),
                          "provenance": bool(prov_md)},
            "decision": entry.get("summary", ""),
            "rules": ed.parse_rules(spec_md),
            "papers": papers[:12],
            "provenance_cards": cards,
            "rejected_sources": rejected,
            "report_md": report_md,
            "hypothesis_md": hyp_md,
            "spec_md": spec_md,
            "provenance_md": prov_md,
            "code": code,
        }
        (OUT / f"{slug}.json").write_text(
            json.dumps(detail, indent=1, ensure_ascii=False), encoding="utf-8")
        rows.append({
            "slug": slug,
            "name": entry["name"],
            "family": entry.get("family", "other"),
            "tagline": entry.get("tagline", ""),
            "summary": entry.get("summary", ""),
            "metrics": m,
            "window": window,
            "status": entry.get("status", "failed"),
            "note": entry.get("note", ""),
        })
    rows.sort(key=lambda r: -r["metrics"]["cagr"])
    ARCHIVE.write_text(json.dumps({
        "generated": "2026-11-27",
        "note": "Development-only and below-TQQQ research, kept for completeness. "
                "These are not part of the one-winner-per-family above-TQQQ set.",
        "strategies": rows,
    }, indent=1), encoding="utf-8")
    print(f"wrote {ARCHIVE} ({len(rows)} entries)")


if __name__ == "__main__":
    main()
