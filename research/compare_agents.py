r"""Summarize research/agents*/*/result.json and check pass/fail vs TQQQ.

Run from the repo root:

    $env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
    python research/compare_agents.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "research" / "agents"
AGENTS2 = ROOT / "research" / "agents2"
TQQQ = {"10y": (0.3928, 0.8168), "5y": (0.1388, 0.8168)}

# Agents that tested several variants name their promoted variant in the report.
PREFERRED = {
    "drawdown-stop-overlay": "v1_threshold_stop_10dhigh",
    "time-of-day": "V2",
}

# Explicit headline locations for schemas the generic parser cannot read.
# "{w}" is the window ("10y" or "5y"). Each path is the agent's declared final
# variant at 1 bp (see that agent's report.md / result.json headline field).
HEADLINES = {
    "overnight-crash-filter": "primary/metrics/{w}/costs/1bp",
    "drawdown-regime": "variants/dd08_stop2/costs/1bp/{w}",
    "dual-speed-regime": "windows/1bp/{w}",
    "event-risk-overlay": "variants/opex_flat_bil/costs/1bp/{w}",
    "stop-reentry-recovery": "variants/combo/{w}",
    "vol-scaled-crash-stop": "variants/atr70_cap4_bil/windows/{w}",
    "winner-ensemble-blend": "windows/WE75/{w}/1bp",
}


def headline_metrics(slug: str, data: dict, window: str):
    """Headline metrics for one agent: explicit path first, then the generic parser."""
    path = HEADLINES.get(slug)
    if path:
        node = data
        for part in path.format(w=window).split("/"):
            node = node.get(part) if isinstance(node, dict) else None
        if isinstance(node, dict) and "cagr" in node:
            return normalise(node)
        raise KeyError(f"{slug}: headline path {path!r} missing for {window}")
    metrics, _ = find_metrics(data, window, PREFERRED.get(slug))
    return metrics


def normalise(metrics: dict) -> dict:
    """Map agent-specific drawdown keys onto the common `max_drawdown` key."""
    if not isinstance(metrics, dict) or "cagr" not in metrics:
        return metrics
    out = dict(metrics)
    if "max_drawdown" not in out:
        for key in ("max_drawdown_1m_marked", "max_drawdown_5m_marked", "max_drawdown_daily_marked", "max_dd", "dd"):
            if key in out:
                out["max_drawdown"] = out[key]
                break
    return out


def find_metrics(data: dict, window: str, preferred: str | None = None):
    """Best-effort extraction across agent result schemas."""
    primary = data.get("primary")
    if isinstance(primary, dict):
        if "windows" in primary:
            w = primary["windows"].get(window)
            if isinstance(w, dict) and "cagr" in w:
                return normalise(w), None
        block = primary.get(window)
        if isinstance(block, dict):
            for key in ("1bp", "1_bp", "primary"):
                candidate = block.get(key)
                if isinstance(candidate, dict) and "cagr" in candidate:
                    return normalise(candidate), block.get("tqqq")
            if "cagr" in block:
                return normalise(block), None
    # Flat metric blocks keyed by window and cost, e.g. {"10y_1bp": {...}}.
    metrics = data.get("metrics")
    if isinstance(metrics, dict):
        candidate = metrics.get(f"{window}_1bp")
        if isinstance(candidate, dict) and "cagr" in candidate:
            return normalise(candidate), None

    w = data.get("windows", {}).get(window, {})
    if not isinstance(w, dict):
        return None, None
    for key in ("1bp", "1_bp", "primary", "results"):
        block = w.get(key)
        if isinstance(block, dict):
            cand = block.get("metrics") or block.get("candidate") or block.get("strategy") or block
            tq = block.get("tqqq") or block.get("benchmark")
            if isinstance(cand, dict) and "cagr" in cand:
                return normalise(cand), tq
    if isinstance(w, dict) and "cagr" in w:
        return normalise(w), w.get("tqqq")
    # Variant-based schemas: scan for a key ending in _1bp for this window.
    variants = data.get("variants")
    if isinstance(variants, dict):
        names = list(variants)
        if preferred and preferred in variants:
            names = [preferred] + [n for n in names if n != preferred]
        for name in names:
            block = variants.get(name)
            if not isinstance(block, dict):
                continue
            candidate = block.get(f"{window}_1bp")
            if isinstance(candidate, dict) and "cagr" in candidate:
                return normalise(candidate), None

    # drawdown-stop-overlay: variants[<name>][<start-date>]["1bp"].
    if isinstance(variants, dict):
        dates = {"10y": "2017-01-03", "5y": "2021-10-25"}
        start = dates.get(window)
        names = list(variants)
        if preferred and preferred in variants:
            names = [preferred] + [n for n in names if n != preferred]
        for name in names:
            block = variants.get(name)
            if not isinstance(block, dict):
                continue
            dated = block.get(start) if start else None
            if isinstance(dated, dict):
                candidate = dated.get("1bp")
                if isinstance(candidate, dict) and "cagr" in candidate:
                    return normalise(candidate), None

    # Flat schemas used by some agents.
    for prefix in ("", "strategy_", "candidate_"):
        cagr = data.get(f"{prefix}cagr_{window}") or data.get(f"{window}_{prefix}cagr")
        dd = data.get(f"{prefix}max_dd_{window}") or data.get(f"{window}_{prefix}max_dd")
        if cagr is not None and dd is not None:
            return {"cagr": cagr, "max_drawdown": dd}, None
    return None, None


def main() -> None:
    rows = []
    paths = sorted(AGENTS.glob("*/result.json")) + sorted(AGENTS2.glob("*/result.json"))
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as error:
            print(f"skip {path}: {error}")
            continue
        name = path.parent.name
        ten = headline_metrics(name, data, "10y")
        five = headline_metrics(name, data, "5y")
        if not ten or not five:
            print(f"skip {name}: no 10y/5y candidate metrics")
            continue
        c10, d10 = float(ten["cagr"]), float(ten["max_drawdown"])
        c5, d5 = float(five["cagr"]), float(five["max_drawdown"])
        pass10 = c10 > TQQQ["10y"][0] and d10 < TQQQ["10y"][1]
        pass5 = c5 > TQQQ["5y"][0] and d5 < TQQQ["5y"][1]
        rows.append(
            {
                "agent": name,
                "cagr10": c10,
                "dd10": d10,
                "cagr5": c5,
                "dd5": d5,
                "pass10": pass10,
                "pass5": pass5,
                "pass": pass10 and pass5,
            }
        )

    rows.sort(key=lambda r: (r["pass"], r["cagr10"]), reverse=True)
    print(f"{'agent':32s} {'10y CAGR':>9s} {'10y DD':>8s} {'5y CAGR':>8s} {'5y DD':>7s}  pass")
    for r in rows:
        print(
            f"{r['agent']:32s} {r['cagr10']*100:8.2f}% {r['dd10']*100:7.2f}% "
            f"{r['cagr5']*100:7.2f}% {r['dd5']*100:6.2f}%  "
            f"10y={'Y' if r['pass10'] else 'N'} 5y={'Y' if r['pass5'] else 'N'}"
        )
    winners = [r for r in rows if r["pass"]]
    print(f"\n{len(winners)} candidate(s) pass both windows vs TQQQ.")
    for r in winners:
        print(f"  {r['agent']}: 10y {r['cagr10']*100:.2f}%/{r['dd10']*100:.2f}%, "
              f"5y {r['cagr5']*100:.2f}%/{r['dd5']*100:.2f}%")

    # ------------------------------------------------------------------ #
    # Revisit rebuilds: their own group, dev is the headline because the
    # 10y/5y windows are only available for the audited survivors.
    # ------------------------------------------------------------------ #
    revisit = ROOT / "research" / "revisit"
    print("\nRevisit rebuilds (dev 2016-2023; holdout only for audited survivors)")
    print(f"{'agent':32s} {'status':22s} {'dev CAGR':>9s} {'dev DD':>8s} "
          f"{'holdout':>18s} {'corr':>6s}")
    rev_rows = []
    for path in sorted(revisit.glob("*/result.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as error:
            print(f"skip {path}: {error}")
            continue
        dev = (data.get("windows") or {}).get("dev") or {}
        m = dev.get("1bp") or {}
        if "cagr" not in m:
            continue
        hold = ((data.get("windows") or {}).get("holdout") or {}).get("1bp") or {}
        rev_rows.append({
            "agent": path.parent.name,
            "status": data.get("status", "—"),
            "cagr": float(m["cagr"]),
            "dd": float(m["max_drawdown"]),
            "hold": (f"{hold['cagr']*100:.2f}%/{hold['max_drawdown']*100:.2f}%"
                     if "cagr" in hold else "not run"),
            "corr": data.get("corr_vs_165d_baseline"),
        })
    rev_rows.sort(key=lambda r: r["cagr"], reverse=True)
    for r in rev_rows:
        corr = f"{r['corr']:.2f}" if isinstance(r["corr"], (int, float)) else "—"
        print(f"{r['agent']:32s} {r['status']:22s} {r['cagr']*100:8.2f}% "
              f"{r['dd']*100:7.2f}% {r['hold']:>18s} {corr:>6s}")
    print(f"\n{len(rev_rows)} rebuild(s); "
          f"{sum(1 for r in rev_rows if r['status'] == 'passed')} passed their dev gates.")


if __name__ == "__main__":
    main()
