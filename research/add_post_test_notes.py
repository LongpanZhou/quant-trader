"""Prepend a post-test pointer to each rebuild report.

The 26 report.md files are pre-registrations written before the runs; their
status lines still say PENDING.  Do not rewrite them (the pre-registration is
evidence); add a dated pointer to the consolidated results instead.
"""
from pathlib import Path

HERE = Path(r"C:\Users\27175\Desktop\quant-trader-research\research\revisit")
SKIP = {"audit", "curves", "curves_full"}

NOTE = (
    "> **Post-test note (2026-11-27):** this file is the pre-registration, not\n"
    "> the result. The frozen development result is in `../SUMMARY.md`; the\n"
    "> full 2016-2026 audit, the post-tune variants and the research-validity\n"
    "> verdicts are in `../WHY_UNDERPERFORM.md`. The published website curve is\n"
    "> the freeze named in `../SUMMARY.md`.\n\n"
)

count = 0
for p in sorted(HERE.glob("*/report.md")):
    if p.parent.name in SKIP:
        continue
    text = p.read_text(encoding="utf-8")
    if "Post-test note (2026-11-27)" in text:
        continue
    p.write_text(NOTE + text, encoding="utf-8")
    count += 1
print(f"added post-test note to {count} reports")
