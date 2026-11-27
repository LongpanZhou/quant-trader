r"""Rank round-2 agents against the current winner and TQQQ.

Run from the repo root:

    $env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
    python research/compare_agents2.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research"))
from compare_agents import find_metrics  # noqa: E402

AGENTS = ROOT / "research" / "agents2"
WINNER = {"10y": (0.5880, 0.4456), "5y": (0.4988, 0.3349)}
TQQQ = {"10y": (0.3928, 0.8168), "5y": (0.1347, 0.8168)}


def main() -> None:
    rows = []
    for path in sorted(AGENTS.glob("*/result.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as error:
            print(f"skip {path}: {error}")
            continue
        name = path.parent.name
        ten, _ = find_metrics(data, "10y")
        five, _ = find_metrics(data, "5y")
        if not ten or not five:
            print(f"skip {name}: no 10y/5y candidate metrics")
            continue
        c10, d10 = float(ten["cagr"]), float(ten["max_drawdown"])
        c5, d5 = float(five["cagr"]), float(five["max_drawdown"])
        beat_tqqq = (
            c10 > TQQQ["10y"][0] and d10 < TQQQ["10y"][1]
            and c5 > TQQQ["5y"][0] and d5 < TQQQ["5y"][1]
        )
        strict = (
            c10 > WINNER["10y"][0] and d10 < WINNER["10y"][1]
            and c5 > WINNER["5y"][0] and d5 < WINNER["5y"][1]
        )
        lower_dd = (
            d10 < WINNER["10y"][1] and d5 < WINNER["5y"][1]
            and c10 > WINNER["10y"][0] - 0.02
            and c5 > WINNER["5y"][0] - 0.02
        )
        rows.append((name, c10, d10, c5, d5, beat_tqqq, strict, lower_dd))

    rows.sort(key=lambda r: (r[6], r[7], r[1]), reverse=True)
    print(f"{'agent':32s} {'10y CAGR':>9s} {'10y DD':>8s} {'5y CAGR':>8s} {'5y DD':>7s}  "
          f"{'TQQQ':>5s} {'WIN':>4s} {'DD':>3s}")
    for name, c10, d10, c5, d5, beat_tqqq, strict, lower_dd in rows:
        print(
            f"{name:32s} {c10*100:8.2f}% {d10*100:7.2f}% "
            f"{c5*100:7.2f}% {d5*100:6.2f}%  "
            f"{'Y' if beat_tqqq else 'N':>5s} {'Y' if strict else 'N':>4s} "
            f"{'Y' if lower_dd else 'N':>3s}"
        )
    print("\nWIN = strictly higher CAGR and lower DD than the winner on both windows")
    print("DD  = lower DD than the winner on both, CAGR within 2pp")


if __name__ == "__main__":
    main()
