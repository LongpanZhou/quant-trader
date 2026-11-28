"""Export one research-detail JSON per published strategy.

Combines the old structured strategy page (decision, papers, provenance cards)
with the new full research record (report, hypothesis, spec, code, metrics).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVISIT = ROOT / "research" / "strategies"
NEW = REVISIT
WEB = ROOT / "web"
INDEX = WEB / "public" / "data" / "research" / "rebuild.json"
AUDIT = ROOT / "research" / "archive" / "revisit" / "WHY_UNDERPERFORM.md"
OUT = WEB / "public" / "data" / "research"
META = {s["slug"]: s for s in json.loads((NEW / "META.json").read_text(encoding="utf-8"))["strategies"]}
LIBRARY_STATUS = {
    s["slug"]: s.get("status", "verified-full")
    for s in json.loads((NEW / "LIBRARY.json").read_text(encoding="utf-8"))["strategies"]
}
VERIFIED_OVERRIDES = {
    "ratio-froth": {
        "verdict": "Verified - trend/ratio overlay",
        "reason": "Clean 2016-2026 rerun: dev 61.56% / 39.11% / 1.47, "
                  "holdout 64.88%, full 62.21% / 36.65% daily-close DD / 1.43. "
                  "Frozen wrapper and holdout in research/strategies/ratio-froth.",
    },
    "family-regime-switch": {
        "verdict": "Verified - period-dependent overlay",
        "reason": "Full 2016-2026: 63.59% / 31.22% / 1.57 vs ratio-froth "
                  "62.21% / 36.65% / 1.43. The lead is not current: 2025 "
                  "20.49% vs 83.35%, 2026 YTD 0.79% vs 29.83%, trailing 1y "
                  "13.67% vs 37.35%. Manual two-strategy overlay; research "
                  "record, not a live edge.",
    },
    "vol-scaled-crash-stop": {
        "verdict": "Verified - vol crash stop",
        "reason": "Shared-runner OHLC/ATR adapter: dev 57.84% / 39.29% / 1.42, "
                  "holdout 34.89%, full 51.46% / 39.29% / 1.29. Own-main cut "
                  "tests at 2020-03-12 and 2022-09-13 are exact.",
    },
}

URL_RE = re.compile(r"<?(https?://[^\s>)]+)>?")


def read(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def first(*paths: Path) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def rel(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def clean(text: str) -> str:
    text = re.sub(r"<https?://[^>]+>", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = text.replace("**", "").replace("`", "").replace("*", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip(" ,;:-–—")


def first_url(text: str) -> str | None:
    m = URL_RE.search(text)
    return m.group(1).rstrip(".,;") if m else None


def short_role(text: str) -> str:
    low = text.lower()
    if "reject" in low or "not used" in low:
        return "rejected"
    if "counter" in low:
        return "counter-evidence"
    if "inspired" in low:
        return "inspired"
    if "support" in low:
        return "supports"
    if "own" in low:
        return "own test"
    if "benchmark" in low:
        return "benchmark"
    if "test" in low:
        return "tested only"
    return "source"


def field(text: str, name: str) -> str:
    pattern = rf"\*{name}:\*\s*(.+?)(?=\n\s*-\s*\*|\n\s*###|\n\s*##|\Z)"
    m = re.search(pattern, text, re.S | re.I)
    return clean(m.group(1)) if m else ""


def extract_section(markdown: str, keywords: tuple[str, ...]) -> str:
    lines = markdown.splitlines()
    headings = [(i, line) for i, line in enumerate(lines) if line.startswith("## ")]
    for keyword in keywords:
        for i, line in headings:
            if keyword not in line.lower():
                continue
            end = len(lines)
            for j in range(i + 1, len(lines)):
                if lines[j].startswith("## "):
                    end = j
                    break
            return "\n".join(lines[i:end]).strip()
    return ""


def first_paragraph(markdown: str) -> str:
    text = re.sub(r"```.*?```", "", markdown, flags=re.S)
    for block in re.split(r"\n\s*\n", text):
        block = block.strip()
        if not block or block.startswith(("#", "|", ">", "-", "*", "1.", "2.")):
            continue
        return clean(block)
    return ""


def section_any(markdown: str, keywords: tuple[str, ...]) -> str:
    """Return the first ##/### section whose heading contains a keyword."""
    parts = re.split(r"(?m)^(#{2,3})\s+(.+)$", markdown or "")
    for i in range(1, len(parts) - 2, 3):
        title = parts[i + 1].lower()
        if any(key in title for key in keywords):
            return parts[i + 2].strip()
    return ""


def brief_paragraphs(markdown: str, limit: int = 2) -> str:
    """Readable prose/bullets from a section, without headings or tables."""
    blocks = re.split(r"\n\s*\n", re.sub(r"```.*?```", "", markdown or "", flags=re.S))
    out: list[str] = []
    for block in blocks:
        block = block.strip()
        if not block or block.startswith(("#", "|", ">")):
            continue
        if block.startswith(("-", "*")):
            out.extend(list_items(block, 3))
            break
        text = clean(block)
        if text:
            out.append(text)
        if len(out) >= limit and not text.endswith(":"):
            break
    return re.sub(
        r"\s*(?:The (?:family )?hypothesis is|The (?:economic )?claim is|That is)\s*$",
        "",
        " ".join(out)[:1400],
        flags=re.I,
    ).strip()


def section_first(markdown: str, keywords: tuple[str, ...]) -> str:
    """Return the first section matching the keywords in priority order."""
    for key in keywords:
        body = section_any(markdown, (key,))
        if body:
            return body
    return ""


def list_items(markdown: str, limit: int = 6) -> list[str]:
    """Bullets or numbered items from a section, with wrapped lines joined."""
    text = re.sub(r"```.*?```", "", markdown or "", flags=re.S)
    items: list[str] = []
    current: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            if current:
                items.append(current)
                current = None
            continue
        match = re.match(r"^(?:[-*]|\d+[.)])\s+(.*)$", line)
        if match:
            if current:
                items.append(current)
            current = match.group(1)
        elif line.startswith(("#", "|", ">")):
            if current:
                items.append(current)
                current = None
        elif current is not None:
            current += " " + line
    if current:
        items.append(current)
    cleaned = [clean(item) for item in items]
    return [item for item in cleaned if item][:limit]


FIELD_LABELS = {
    "source", "sources", "link", "links", "role", "confidence", "consequence",
    "exact claim used", "claim used", "why not used", "evidence", "implication",
    "design choice", "design choices", "shared research harness", "own test",
    "tested and rejected",
}


def source_labels(cards: list[dict], papers: list[dict], limit: int = 3) -> list[str]:
    """Citation-like source names from provenance cards or paper links."""
    labels: list[str] = []
    for card in cards:
        source = clean(card.get("source") or "")
        source = re.sub(r"\s*[—–-]\s*https?://\S+", "", source).strip(" .;")
        if not source or source.lower().strip(": ") in FIELD_LABELS:
            continue
        role = (card.get("role") or "").lower()
        if not any(key in role for key in ("inspired", "support", "source")):
            continue
        if len(source) < 8:
            continue
        if source not in labels:
            labels.append(source)
    for paper in papers:
        label = clean(paper.get("label") or "")
        if label and label.lower().strip(": ") not in FIELD_LABELS and len(label) >= 8:
            if label not in labels:
                labels.append(label)
    return labels[:limit]


def provenance_citations(markdown: str, limit: int = 2) -> list[str]:
    """Fallback: read '**Source:** ...' lines from prose provenance files."""
    citations: list[str] = []
    for match in re.finditer(r"\*\*Sources?:\*\*\s*(.+?)(?=\n\s*(?:[-*]|\n)|\Z)", markdown or "", flags=re.S):
        text = clean(match.group(1))
        text = re.sub(r"\s*https?://\S+", "", text).strip(" ,;")
        if text and text not in citations:
            citations.append(text)
        if len(citations) >= limit:
            break
    return citations


def first_prose(markdown: str) -> str:
    """First descriptive paragraph, skipping metadata and blockquotes."""
    text = re.sub(r"```.*?```", "", markdown or "", flags=re.S)
    for block in re.split(r"\n\s*\n", text):
        block = block.strip()
        if not block or block.startswith(("#", "|", ">", "-", "*")):
            continue
        if re.match(r"\*\*(?:Slug|Family|Window|Dev|Full|Status|Primary object|Execution|Date|Files|Original|Design date)\b", block):
            continue
        cleaned = clean(block)
        if len(cleaned) >= 50 and not cleaned.endswith(":"):
            return cleaned
    return ""


def looks_truncated(text: str) -> bool:
    low = (text or "").lower().rstrip(" .,;:")
    return low.endswith((
        " was", " were", " the", " and", " of", " to", " a", " an", " is",
        " with", " that", " for", " in", " on", " by", " its", " plus",
    ))


def build_brief(hypothesis_md: str, report_md: str, spec_md: str,
                provenance_md: str, decision: str, papers: list[dict],
                rules: list[str], cards: list[dict] | None = None,
                tagline: str = "", summary: str = "") -> dict:
    labels = source_labels(cards or [], papers)
    if not labels:
        labels = provenance_citations(provenance_md)
    decision_text = decision
    if (looks_truncated(decision_text) or len(decision_text or "") < 60) and len(summary or "") > len(decision_text or ""):
        decision_text = summary

    # Where the idea came from.
    origin = ""
    if "where the idea came from" in (provenance_md or "").lower():
        origin = brief_paragraphs(section_any(provenance_md, ("where the idea came from",)), 2)
    if not origin and labels and (
        "close-location" in (decision_text or "").lower()
        and "ratio-froth" in (decision_text or "").lower()
    ):
        origin = (
            "No external paper is linked. This is a manual overlay of "
            + " and ".join(labels[:3])
            + ", built and selected inside this project."
        )
    if not origin and labels:
        origin = "The idea is adapted from " + "; ".join(labels) + "."
    if not origin:
        origin = (
            "No external paper is linked. This is an internal research hypothesis: the rule was "
            "generated and tested inside this project, so its origin is the research record below, "
            "not a published paper."
        )

    # How it works: prefer the saved mechanism/signal section when the one-line
    # decision is only a placeholder or benchmark boilerplate.
    low_decision = (decision_text or "").lower()
    placeholder = (
        len(decision_text or "") < 70
        or "full-window holdout" in low_decision
        or low_decision.startswith(("new ", "external "))
        or "stated bar" in low_decision
        or low_decision.startswith(("the original", "signal at the close"))
        or ("cagr" in low_decision and "sharpe" in low_decision)
    )
    mechanism_section = section_first(
        hypothesis_md,
        ("claim", "mechanism", "signal", "exact rules", "rules", "how it works",
         "economic hypothesis"),
    )
    mechanism = ""
    if not placeholder:
        mechanism = decision_text
    if not mechanism:
        mechanism = (
            first_paragraph(mechanism_section)
            or " ".join(list_items(mechanism_section, 4))
            or first_prose(hypothesis_md)
        )
    if not mechanism:
        mechanism = decision_text or summary

    steps = rules[:6]
    if not steps:
        steps = list_items(mechanism_section or section_first(
            report_md, ("exact rules", "rules", "mechanism", "signal")
        ), 6)

    # Why it could work: a full explanatory tagline first, then the
    # pre-registered claim/thesis, then the mechanism explanation.
    why = ""
    if len(tagline or "") >= 70 and not (tagline or "").lower().startswith(
        ("the original", "python port", "new ", "external ")
    ):
        why = tagline
    if not why:
        why = brief_paragraphs(section_first(
            hypothesis_md,
            ("claim", "thesis", "economic hypothesis", "rationale", "hypothesis",
             "expected effect", "idea"),
        ), 2)
    if not why:
        why = brief_paragraphs(section_first(
            report_md, ("standalone idea", "hypothesis", "claim", "thesis")
        ), 2)
    if not why:
        why = brief_paragraphs(section_first(hypothesis_md, ("mechanism",)), 2)
    if not why:
        why = first_prose(hypothesis_md)
    if not why:
        why = tagline or summary

    caveat = brief_paragraphs(section_first(
        report_md, ("recent performance", "not robust", "caveat", "limitation")
    ), 3)
    if not caveat:
        caveat = brief_paragraphs(section_first(
            provenance_md, ("recent performance", "not robust", "caveat", "limitation")
        ), 3)

    # What would falsify it: explicit falsifier sections first.
    falsifiers = list_items(section_first(
        hypothesis_md,
        ("falsifier", "what would prove", "what would falsify", "kill", "rejected if"),
    ), 6)
    if not falsifiers:
        falsifiers = list_items(section_first(
            report_md,
            ("falsifier", "what would prove", "what would falsify", "kill", "rejected if"),
        ), 6)
    if not falsifiers:
        falsifiers = list_items(section_first(
            hypothesis_md, ("caveat", "limitation", "failure mode")
        ), 4)
    if not falsifiers:
        falsifiers = [
            "A negative 2024-2026 holdout.",
            "Full-window CAGR at or below TQQQ's, or a drawdown at or above TQQQ's.",
            "The edge disappearing at 5-10 bp costs.",
        ]

    return {"origin": origin, "mechanism": mechanism, "steps": steps,
            "why": why, "falsifiers": falsifiers, "caveat": caveat}



def parse_bullets(markdown: str) -> tuple[list[dict], list[dict]]:
    """Parse the rich 'Sources' bullets used by the rebuild provenance files."""
    cards: list[dict] = []
    rejected: list[dict] = []
    parts = re.split(r"^(#{2,3})\s+(.+)$", markdown, flags=re.M)
    for i in range(1, len(parts) - 2, 3):
        heading = clean(parts[i + 1])
        body = parts[i + 2]
        starts = [m.start() for m in re.finditer(r"^-\s+\*\*", body, flags=re.M)]
        for k, start in enumerate(starts):
            end = starts[k + 1] if k + 1 < len(starts) else len(body)
            chunk = body[start:end]
            chunk = re.sub(r"^-\s+\*\*", "", chunk, count=1)
            close = chunk.find("**")
            if close < 0:
                continue
            source = clean(chunk[:close])
            rest = chunk[close + 2:]
            url = first_url(rest)
            claim = field(rest, "Claims? used") or field(rest, "Claim")
            role_full = field(rest, "Role")
            confidence = field(rest, "Confidence")
            why = field(rest, "Why not used")
            if not claim:
                text = re.sub(r"^\s*[,–—-]\s*", "", rest)
                text = re.sub(r"^\*[^*]+\*\s*[–—-]\s*", "", text)
                claim = clean(text.split("<http")[0])
            low = heading.lower()
            role = short_role(role_full) if role_full else ""
            if not role:
                if "not used" in low or "rejected" in low or "counter" in low:
                    role = "rejected"
                elif "own test" in low:
                    role = "own test"
                elif "literature" in low or "source" in low:
                    role = "literature"
                elif "benchmark" in low:
                    role = "benchmark"
            if "not used" in low or "rejected" in low or role.lower().startswith("reject"):
                rejected.append({"source": source, "url": url,
                                 "why_rejected": why or claim})
            else:
                section_low = re.sub(r"^\d+[.)]?\s*", "", low).strip()
                paper_section = any(
                    k in section_low
                    for k in ("literature", "sources", "references", "papers", "benchmark")
                )
                own_section = "own test" in section_low
                generic_prov = section_low in {
                    "provenance", "source mapping", "sources and provenance",
                }

                if own_section or (generic_prov and not url):
                    cards.append({
                        "idea": source,
                        "source": "Own test" if own_section else (role or "report"),
                        "url": None,
                        "source_type": heading,
                        "role": "own test" if own_section else "report",
                        "role_detail": role_full,
                        "evidence": claim or clean(rest),
                        "confidence": confidence,
                    })
                elif paper_section:
                    cards.append({
                        "idea": claim or heading,
                        "source": source,
                        "url": url,
                        "source_type": heading,
                        "role": role or "literature",
                        "role_detail": role_full,
                        "evidence": "",
                        "confidence": confidence,
                    })
                else:
                    cards.append({
                        "idea": claim or heading,
                        "source": source,
                        "url": url,
                        "source_type": heading,
                        "role": role or "source",
                        "role_detail": role_full,
                        "evidence": "",
                        "confidence": confidence,
                    })
    return cards, rejected


def parse_citations(markdown: str) -> list[dict]:
    """Parse plain-bullet and numbered citation lists that the rich parser misses."""
    text = re.sub(r"```.*?```", "", markdown or "", flags=re.S)
    items: list[str] = []
    current: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        match = re.match(r"^(?:[-*]|\d+[.)])\s+(.*)$", line)
        if match:
            if current:
                items.append(current)
            current = match.group(1)
        elif not line:
            if current:
                items.append(current)
                current = None
        elif line.startswith(("#", "|", ">")):
            if current:
                items.append(current)
                current = None
        elif current is not None:
            current += " " + line
    if current:
        items.append(current)

    cards: list[dict] = []
    for item in items:
        cleaned = clean(item)
        low = cleaned.lower()
        if low.startswith(("own test", "tested and rejected", "no external")):
            continue
        url = first_url(item)
        if not url and not re.search(r"\b(?:19|20)\d{2}\b", cleaned):
            continue
        role_match = re.search(r"Role:?\s*(.+?)(?:\s+Confidence:|\Z)", cleaned, re.I)
        role_text = clean(role_match.group(1)) if role_match else ""
        source = re.sub(r"<?https?://\S+>?", "", cleaned)
        source = re.sub(r"Role:.*$", "", source, flags=re.I)
        source = re.sub(r"Confidence:.*$", "", source, flags=re.I)
        source = source.split(" — ")[0].split(" – ")[0].strip(" .,;:")
        if len(source) < 8:
            continue
        idea = role_text
        if not idea:
            parts = re.split(r"\s+[—–]\s+", cleaned, maxsplit=1)
            idea = clean(parts[1]) if len(parts) > 1 else "Cited source for this strategy."
        role = "inspired" if "inspir" in role_text.lower() else "source"
        cards.append({
            "idea": idea[:500],
            "source": source[:300],
            "url": url,
            "source_type": "provenance list",
            "role": role,
            "role_detail": role_text[:500],
            "confidence": "",
            "evidence": "",
        })
    return cards


def parse_tables(markdown: str) -> list[dict]:
    """Parse provenance tables such as | Rule / claim | Source | Role | Evidence |."""
    cards: list[dict] = []
    lines = markdown.splitlines()
    i = 0
    while i < len(lines):
        if not lines[i].strip().startswith("|"):
            i += 1
            continue
        block = []
        while i < len(lines) and lines[i].strip().startswith("|"):
            block.append(lines[i].strip())
            i += 1
        if len(block) < 3:
            continue
        headers = [clean(c) for c in block[0].strip("|").split("|")]
        lower = [h.lower() for h in headers]
        if not any("source" in h for h in lower):
            continue
        if not any(any(k in h for k in ("rule", "claim", "item", "assumption")) for h in lower):
            continue

        def col(*keys: str) -> str | None:
            for h, l in zip(headers, lower):
                if any(k in l for k in keys):
                    return h
            return None

        source_col = col("source")
        idea_col = col("rule", "claim", "item", "assumption")
        role_col = col("role", "support")
        evidence_col = col("evidence", "notes", "detail")
        conf_col = col("confidence")
        rows = []
        for line in block[2:]:
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) == len(headers):
                rows.append(dict(zip(headers, cells)))
        for row in rows:
            source = clean(row.get(source_col, "")) if source_col else ""
            evidence = clean(row.get(evidence_col, "")) if evidence_col else ""
            role_full = clean(row.get(role_col, "")) if role_col else ""
            cards.append({
                "idea": clean(row.get(idea_col, "")) if idea_col else source,
                "source": source,
                "url": first_url(row.get(source_col, "") + " " + row.get(evidence_col or "", "")),
                "source_type": "provenance table",
                "role": short_role(role_full) if role_full else "source",
                "role_detail": role_full,
                "evidence": evidence,
                "confidence": clean(row.get(conf_col, "")) if conf_col else "",
            })
    return cards


def parse_rules(markdown: str) -> list[str]:
    rules = []
    for line in markdown.splitlines():
        m = re.match(r"^\s*(?:\d+[.)]|[-*])\s+(.+)$", line)
        if not m:
            continue
        text = clean(m.group(1))
        if len(text) < 12:
            continue
        if text.lower().startswith(("claim", "role", "confidence", "why not")):
            continue
        rules.append(text)
    return rules[:8]


def parse_assessments() -> dict[str, dict[str, str]]:
    text = read(AUDIT)
    if not text:
        return {}
    section = text.split("## 2. Research validity")[1].split("### Cross-cutting")[0]
    out: dict[str, dict[str, str]] = {}
    for line in section.splitlines():
        if not line.startswith("| "):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4 or not cells[0].isdigit():
            continue
        m = re.search(r"`([^`]+)`", cells[1])
        if not m:
            continue
        out[m.group(1)] = {
            "verdict": cells[2].replace("*", "").strip(),
            "reason": "|".join(cells[3:]).strip(),
        }
    return out


def main() -> None:
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    assessments = parse_assessments()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "code").mkdir(parents=True, exist_ok=True)
    total = 0
    missing = []

    for row in index["strategies"]:
        slug = row["slug"]
        base = REVISIT / slug

        report_path = first(base / "report.md")
        hyp_path = first(base / "HYPOTHESIS.md", base / "hypothesis.md")
        spec_path = first(base / "SPEC.md", base / "spec.md")
        prov_path = first(base / "PROVENANCE.md", base / "provenance.md")
        code_path = first(base / "strategy.py")

        for name, path in (("report", report_path), ("hypothesis", hyp_path),
                           ("spec", spec_path), ("provenance", prov_path),
                           ("code", code_path)):
            if path is None:
                missing.append(f"{slug}:{name}")

        report_md = read(report_path)
        hypothesis_md = read(hyp_path)
        spec_md = read(spec_path)
        provenance_md = read(prov_path)
        extracted = {"hypothesis": False, "spec": False, "provenance": False}

        if not hypothesis_md:
            hypothesis_md = extract_section(report_md, ("hypothesis", "idea"))
            extracted["hypothesis"] = bool(hypothesis_md)
        if not spec_md:
            spec_md = extract_section(report_md, ("spec", "rules", "signal", "universe",
                                                  "what the strategy does", "what it trades",
                                                  "what the strategy is", "mechanism",
                                                  "exact rules"))
            if not spec_md and slug in META:
                spec_md = extract_section(hypothesis_md, ("exact rules", "rules", "mechanism",
                                                           "exact primary rule", "primary rule"))
            extracted["spec"] = bool(spec_md)
        if not provenance_md:
            provenance_md = extract_section(
                report_md,
                ("provenance", "sources", "evidence", "papers", "literature",
                 "relationship", "differs", "existing work"),
            )
            if not provenance_md and slug in META:
                provenance_md = (
                    "## Own test\n\n"
                    "- **quant-trader research program** - Pre-registered development test "
                    "on 2016-2023 and a one-shot 2024-2026 holdout; implementation and "
                    "results are in `report.md` and `strategy.py`."
                )
            extracted["provenance"] = bool(provenance_md)

        cards, rejected = parse_bullets(provenance_md)
        seen = {(c["source"], c["idea"]) for c in cards}
        for card in parse_tables(provenance_md):
            key = (card["source"], card["idea"])
            if key not in seen:
                seen.add(key)
                cards.append(card)
        if not cards:
            for card in parse_citations(provenance_md):
                key = (card["source"], card["idea"])
                if key not in seen:
                    seen.add(key)
                    cards.append(card)

        papers = []
        paper_seen = set()
        for card in cards:
            if card.get("url") and card.get("source"):
                key = (card["source"], card["url"])
                if key not in paper_seen:
                    paper_seen.add(key)
                    papers.append({"label": card["source"], "url": card["url"]})

        rules = parse_rules(spec_md)
        if slug in META:
            decision = META[slug]["summary"]
        else:
            decision = (
                first_paragraph(extract_section(report_md, ("idea", "hypothesis")))
                or row.get("summary", "")
            )
        if looks_truncated(decision) or len(decision) < 60:
            decision = row.get("summary", "") or decision
        if "stated bar" in decision.lower():
            alt = " ".join(list_items(section_first(
                hypothesis_md, ("position rule", "exact rules", "rules")
            ), 3)) or first_prose(hypothesis_md)
            if alt:
                decision = alt
        assessment = (
            VERIFIED_OVERRIDES.get(slug)
            or ({"verdict": META[slug]["verdict"], "reason": META[slug]["reason"]}
                if slug in META else assessments.get(slug, {}))
        )

        code = read(code_path)
        code_public = f"/data/research/code/{slug}.py"
        (OUT / "code" / f"{slug}.py").write_text(code, encoding="utf-8")

        detail = {
            "slug": slug,
            "name": row["name"],
            "tagline": row.get("tagline", ""),
            "summary": row.get("summary", ""),
            "metrics": {
                "cagr": row.get("cagr"),
                "dd": row.get("dd"),
                "sharpe": row.get("sharpe"),
            },
            "status": LIBRARY_STATUS.get(slug, "verified-full"),
            "assessment": assessment,
            "paths": {
                "report": rel(report_path),
                "hypothesis": rel(hyp_path),
                "spec": rel(spec_path),
                "provenance": rel(prov_path),
                "code": rel(code_path),
                "code_public": code_public,
            },
            "extracted": extracted,
            "decision": decision,
            "rules": rules,
            "papers": papers[:12],
            "brief": build_brief(hypothesis_md, report_md, spec_md, provenance_md,
                                 decision, papers, rules, cards,
                                 row.get("tagline", ""), row.get("summary", "")),
            "provenance_cards": cards,
            "rejected_sources": rejected,
            "report_md": report_md,
            "hypothesis_md": hypothesis_md,
            "spec_md": spec_md,
            "provenance_md": provenance_md,
            "code": code,
        }
        out_path = OUT / f"{slug}.json"
        text = json.dumps(detail, indent=1, ensure_ascii=False)
        out_path.write_text(text, encoding="utf-8")
        total += len(text.encode("utf-8"))

    print(f"wrote {len(index['strategies'])} detail files, {total/1024/1024:.2f} MB")
    if missing:
        print("missing standalone sections:", ", ".join(missing))


if __name__ == "__main__":
    main()
