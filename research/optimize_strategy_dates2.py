"""Vectorize common ts.date / daily-return patterns across strategy files."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(r"C:\Users\27175\Desktop\quant-trader-research\research\revisit")
replacements = [
    ("pd.Series(ts.date)", "pd.Series(bt.session_dates(ts))"),
    ("pd.Series(ts.date.values)", "pd.Series(bt.session_dates(ts))"),
    ("pd.Index(ts.date)", "pd.Index(bt.session_dates(ts))"),
    ("pd.DatetimeIndex(ts.date)", "pd.DatetimeIndex(bt.session_dates(ts))"),
    ('pd.Series(result["equity"], index=result["ts"]).resample("1D").last().dropna()',
     'bt.daily_last(result["equity"], result["ts"]).dropna()'),
]

changed = []
for path in ROOT.rglob("strategy.py"):
    text = path.read_text(encoding="utf-8")
    if "import bt" not in text:
        continue
    original = text
    for old, new in replacements:
        text = text.replace(old, new)
    if text != original:
        path.write_text(text, encoding="utf-8")
        changed.append(str(path.relative_to(ROOT)))
print(f"changed {len(changed)} files")
for c in changed:
    print(" ", c)
