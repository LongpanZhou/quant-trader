"""Development leaderboard for the new-strategy program.

Reads every `research/new/<slug>/result.json` and compares it with the TQQQ
development benchmark.  Only strategies that clear the pre-registered bar are
eligible for the one-shot holdout.

Usage:
    python research/new/leaderboard.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NEW = ROOT / "research" / "new"

TQQQ = {"cagr": 0.3672, "dd": 0.8229, "sharpe": 0.82}


def dev_block(d: dict) -> dict:
    windows = d.get("windows") or {}
    candidates = [
        windows.get("dev") or {},
        d.get("dev") or {},
        d.get("headline_1m") or {},
        d.get("primary") or {},
        d.get("headline") or {},
        d.get("results") or {},
    ]
    for block in candidates:
        if "cagr" in block:
            return block
        if "1bp" in block:
            return block["1bp"]
        sub = block.get("dev")
        if isinstance(sub, dict):
            if "cagr" in sub:
                return sub
            if "1bp" in sub:
                return sub["1bp"]
    return d.get("dev_1bp") or {}


def main() -> None:
    rows = []
    for p in sorted(NEW.glob("*/result.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        m = dev_block(d)
        if "cagr" not in m:
            rows.append((p.parent.name, None, None, None, None, None, "no dev 1bp"))
            continue
        info = d.get("info") or {}
        corr = (d.get("corr_vs_tqqq") or d.get("corr_daily_tqqq")
                or d.get("corr_tqqq_daily") or d.get("corr_tqqq")
                or d.get("corr_vs_165d_baseline") or info.get("corr_vs_tqqq")
                or info.get("corr"))
        exposure = (m.get("exposure") or m.get("tqqq_exposure")
                    or m.get("tqqq_weight_avg") or d.get("exposure")
                    or info.get("exposure") or info.get("tqqq_time"))
        pass_bar = m["cagr"] > TQQQ["cagr"] and m["max_drawdown"] < TQQQ["dd"]
        rows.append((
            p.parent.name, m["cagr"], m["max_drawdown"], m.get("sharpe"),
            exposure, corr, "PASS" if pass_bar else "below",
        ))

    print(f"{'slug':30s} {'devCAGR':>8s} {'devDD':>7s} {'Sharpe':>7s} "
          f"{'expo':>6s} {'corr':>6s}  status")
    print(f"{'TQQQ benchmark':30s} {TQQQ['cagr']*100:7.2f}% {TQQQ['dd']*100:6.2f}% "
          f"{TQQQ['sharpe']:7.2f} {'100%':>6s} {'1.00':>6s}")
    passers = []
    for slug, cagr, dd, sharpe, exposure, corr, status in rows:
        if cagr is None:
            print(f"{slug:30s} {'—':>8s} {'—':>7s} {'—':>7s} {'—':>6s} {'—':>6s}  {status}")
            continue
        if status == "PASS":
            passers.append(slug)
        exp = f"{exposure*100:5.1f}%" if isinstance(exposure, (int, float)) else "—"
        co = f"{corr:6.2f}" if isinstance(corr, (int, float)) else "—"
        print(f"{slug:30s} {cagr*100:7.2f}% {dd*100:6.2f}% "
              f"{(sharpe if sharpe is not None else float('nan')):7.2f} {exp:>6s} "
              f"{co:>6s}  {status}")
    print()
    print(f"passers: {len(passers)}  {' '.join(passers) if passers else '(none yet)'}")


if __name__ == "__main__":
    main()
