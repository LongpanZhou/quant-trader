"""Replace common pandas groupby(date) daily-return helpers with bt.daily_last."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(r"C:\Users\27175\Desktop\quant-trader-research\research\revisit")
pairs = [
    (
        's = pd.Series(equity, index=ts)\n    return s.groupby(s.index.date).last().pct_change().dropna()',
        'return bt.daily_last(equity, ts).pct_change().dropna()',
    ),
    (
        'eq = pd.Series(result["equity"], index=result["ts"])\n    return eq.groupby(eq.index.date).last().pct_change().dropna()',
        'return bt.daily_last(result["equity"], result["ts"]).pct_change().dropna()',
    ),
    (
        'eq = pd.Series(result["equity"], index=pd.DatetimeIndex(result["ts"]))\n    e = eq.groupby(eq.index.date).last()\n    return e.pct_change().dropna()',
        'return bt.daily_last(result["equity"], pd.DatetimeIndex(result["ts"])).pct_change().dropna()',
    ),
    (
        'eq = pd.Series(res["equity"], index=ts)\n    d = eq.groupby(eq.index.date).last()\n    return d.pct_change().dropna()',
        'return bt.daily_last(res["equity"], ts).pct_change().dropna()',
    ),
    (
        'eq = pd.Series(r["equity"], index=r["ts"])\n    return eq.resample("1D").last().dropna().pct_change().dropna()',
        'return bt.daily_last(r["equity"], r["ts"]).pct_change().dropna()',
    ),
    (
        'eq = pd.Series(r["equity"], index=r["ts"])\n    return eq.resample("1D").last().dropna().pct_change().dropna()',
        'return bt.daily_last(r["equity"], r["ts"]).pct_change().dropna()',
    ),
]

changed = []
for path in ROOT.rglob("strategy.py"):
    text = path.read_text(encoding="utf-8")
    if "import bt" not in text:
        continue
    original = text
    for old, new in pairs:
        text = text.replace(old, new)
    if text != original:
        path.write_text(text, encoding="utf-8")
        changed.append(str(path.relative_to(ROOT)))
print(f"changed {len(changed)} files")
for c in changed:
    print(" ", c)
