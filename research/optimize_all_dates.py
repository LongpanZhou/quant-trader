"""Vectorize slow date conversions across every research/revisit Python file."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(r"C:\Users\27175\Desktop\quant-trader-research\research\revisit")
patterns = [
    (re.compile(r"np\.array\(\[(\w+)\.date\(\) for \1 in (\w+)\]\)"), r"bt.session_dates(\2)"),
    (re.compile(r"np\.asarray\(\[(\w+)\.date\(\) for \1 in (\w+)\]\)"), r"bt.session_dates(\2)"),
    (re.compile(r"pd\.Series\((\w+)\.date\)"), r"pd.Series(bt.session_dates(\1))"),
    (re.compile(r"pd\.Index\((\w+)\.date\)"), r"pd.Index(bt.session_dates(\1))"),
]

changed = []
for path in ROOT.rglob("*.py"):
    if path.name == "__full_tmp.py" or "__pycache__" in path.parts:
        continue
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
