"""Rebuild SUMMARY.md from the published freeze and the current results.

The website uses the pre-tune curve where the post-freeze tune changed the
strategy.  This summary makes that explicit: it shows the pre-tune development
result, the uniform full-window result, and the post-tune variant if different.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "research" / "revisit"
CURVES = HERE / "curves_full"
ALL = ROOT / "web" / "public" / "data" / "compare" / "all.json"
OUT = HERE / "SUMMARY.md"


def website_metrics() -> dict[str, dict]:
    d = json.loads(ALL.read_text(encoding="utf-8"))
    return {m["id"]: m for m in d["metrics"]}


def dev(path: Path) -> dict | None:
    if not path.exists():
        return None
    d = json.loads(path.read_text(encoding="utf-8"))
    return ((d.get("windows") or {}).get("dev") or {}).get("1bp")


def main() -> None:
    metrics = website_metrics()
    rows = []
    for p in sorted(HERE.glob("*/result.json")):
        slug = p.parent.name
        cur = json.loads(p.read_text(encoding="utf-8"))
        pre_path = p.parent / "_before_tune" / "result.json"
        pre = dev(pre_path) if pre_path.exists() else None
        post = dev(p)
        # Only a material result change counts as a post-tune variant.  Several
        # strategies have a `_before_tune` snapshot but produced the same result
        # after the tune (refactor only); those stay on the current freeze.
        changed = bool(pre and post and abs(pre.get("cagr", 0) - post.get("cagr", 0)) > 0.001)
        frozen = (pre if changed else post) or {}
        full = metrics.get(slug, {})
        rows.append({
            "slug": slug,
            "idea": cur.get("idea", ""),
            "dev": frozen.get("cagr"),
            "dev_dd": frozen.get("max_drawdown"),
            "post": post.get("cagr") if changed else None,
            "full": full.get("cagr"),
            "full_dd": full.get("dd"),
            "full_sharpe": full.get("sharpe"),
            "freeze": "pre_tune" if changed else "current",
        })

    # The original Ratio froth has no revisit result.json; it is the agents2 run.
    full = metrics.get("ratio-froth", {})
    rows.append({
        "slug": "ratio-froth",
        "idea": "The original 165-day base + 4% stop + TQQQ/QQQ ratio overlay.",
        "dev": None, "dev_dd": None, "post": None,
        "full": full.get("cagr"), "full_dd": full.get("dd"),
        "full_sharpe": full.get("sharpe"), "freeze": "original",
    })
    rows.sort(key=lambda r: -(r["full"] or -9))

    lines = [
        "# Revisit summary — published freeze",
        "",
        "Uniform window **2016-01-04 → 2026-10-23**, next-open fills, 2% band,",
        "1 bp costs, daily-close marks. `Dev` is the frozen 2016-2023 development",
        "result (1-minute marks; pre-tune where the post-freeze tune changed the",
        "strategy). `Post` is the post-tune variant when it differs; the website",
        "keeps the pre-tune curve, not the variant. See",
        "`WHY_UNDERPERFORM.md` §3 and `audit/validity_A.md` … `validity_D.md`.",
        "",
        "| Strategy | Idea | Dev CAGR / DD | Post-tune dev | Full CAGR / DD / Sharpe | Freeze |",
        "|---|---|---:|---:|---:|---|",
    ]
    for r in rows:
        dev_s = f"{r['dev']*100:.2f}% / {r['dev_dd']*100:.2f}%" if r["dev"] is not None else "—"
        post_s = f"{r['post']*100:.2f}%" if r["post"] is not None else "—"
        full_s = (f"**{r['full']*100:.2f}%** / {r['full_dd']*100:.2f}% / "
                  f"{r['full_sharpe']:.2f}") if r["full"] is not None else "—"
        idea = r["idea"].replace("|", "/")[:110]
        lines.append(f"| `{r['slug']}` | {idea} | {dev_s} | {post_s} | {full_s} | {r['freeze']} |")

    lines += [
        "",
        "Notes:",
        "- `pre_tune` means the published curve is the pre-registered version and",
        "  the current `result.json` is a post-tune variant (see §3 of the audit).",
        "- The `holdout` results remain in the individual `result.json` files;",
        "  they are not used here and are not a clean holdout for tuned strategies.",
        "- The old pre-audit summary is preserved as `SUMMARY_pre_audit.md`.",
    ]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
