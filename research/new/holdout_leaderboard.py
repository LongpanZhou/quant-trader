"""Full-window leaderboard for strategies with a one-shot holdout.

Compares the daily-close full 2016-2026 result with TQQQ's daily-close full
result (the website's benchmark), and reports the 2024-2026 holdout separately.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NEW = ROOT / "research" / "new"


def main() -> None:
    rows = []
    for p in sorted(NEW.glob("*/holdout.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        w = d.get("windows") or {}
        full = (w.get("full") or {}).get("daily") or {}
        hold = (w.get("holdout") or {}).get("daily") or {}
        dev = (w.get("dev") or {}).get("daily") or {}
        tq = ((d.get("benchmarks") or {}).get("tqqq") or {}).get("full") or {}
        if "cagr" not in full:
            continue
        beat = full["cagr"] > tq.get("cagr", 0.3754) and full["max_drawdown"] < tq.get("max_drawdown", 0.8168)
        rows.append((p.parent.name, dev, hold, full, tq, "PASS full" if beat else "below full"))

    print(f"{'slug':30s} {'devCAGR':>8s} {'holdCAGR':>9s} {'fullCAGR':>9s} "
          f"{'fullDD':>7s} {'tqqqCAGR':>9s}  status")
    n = 0
    for slug, dev, hold, full, tq, status in rows:
        if status == "PASS full":
            n += 1
        print(f"{slug:30s} {dev.get('cagr',0)*100:7.2f}% {hold.get('cagr',0)*100:8.2f}% "
              f"{full['cagr']*100:8.2f}% {full['max_drawdown']*100:6.2f}% "
              f"{tq.get('cagr',0)*100:8.2f}%  {status}")
    print(f"\nfull-window passers: {n}")


if __name__ == "__main__":
    main()
