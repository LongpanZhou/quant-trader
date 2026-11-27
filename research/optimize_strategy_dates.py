"""Replace slow per-timestamp date conversions with bt.session_dates()."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(r"C:\Users\27175\Desktop\quant-trader-research\research\revisit")
patterns = [
    (re.compile(r"np\.array\(\[(\w+)\.date\(\) for \1 in (\w+)\]\)"), r"bt.session_dates(\2)"),
    (re.compile(r"np\.asarray\(\[(\w+)\.date\(\) for \1 in (\w+)\]\)"), r"bt.session_dates(\2)"),
    (re.compile(r"np\.array\(\[(\w+)\.date\(\) for \1 in (\w+)\]\s*\)"), r"bt.session_dates(\2)"),
]

changed = []
for path in ROOT.rglob("strategy.py"):
    text = path.read_text(encoding="utf-8")
    if "import bt" not in text:
        continue
    original = text
    for pattern, repl in patterns:
        text = pattern.sub(repl, text)
    if text != original:
        path.write_text(text, encoding="utf-8")
        changed.append(str(path.relative_to(ROOT)))
print(f"changed {len(changed)} files")
for c in changed:
    print(" ", c)
