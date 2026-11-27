"""Write research/revisit/SUMMARY.md from the frozen result files."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\27175\Desktop\quant-trader-research")
sys.path.insert(0, str(ROOT / "research"))
import compare_agents as ca  # noqa: E402

HERE = ROOT / "research" / "revisit"

STATUS = {
    "ratio-pairs": "passed",
    "intraday-seasonality": "passed",
    "intraday-mean-reversion": "passed",
    "gap-capitulation-reversal": "passed",
    "daily-regime-minute-entry": "rejected",
    "donchian-breakout": "rejected",
    "drawdown-regime": "rejected",
    "drawdown-stop-overlay": "rejected",
    "dual-speed-regime": "rejected",
    "dynamic-leverage-throttle": "rejected",
    "ensemble-signals": "rejected",
    "event-risk-overlay": "rejected",
    "gap-fill-fade": "rejected",
    "intraday-momentum": "rejected",
    "letf-rebalance-flow": "rejected",
    "ml-classifier": "rejected",
    "ml-crash-overlay-winner": "rejected",
    "opening-range-breakout": "rejected",
    "overnight-crash-filter": "rejected",
    "risk-parity-hrp": "rejected",
    "stop-reentry-recovery": "retired_overlay_only",
    "time-of-day": "retired_overlay_only",
    "vol-kelly-overlay": "rejected",
    "vol-scaled-crash-stop": "rejected",
    "volume-orderflow": "retired_overlay_only",
    "winner-ensemble-blend": "rejected",
}

REASON = {
    "ratio-pairs": "Passed dev gates: 18.96%/34.59%, corr 0.53; holdout 24.82%/22.94%.",
    "intraday-seasonality": "Passed dev gates: 21.84%/43.75%, corr 0.26; holdout 40.48%/31.75%.",
    "intraday-mean-reversion": "Passed dev gates: 11.31%/31.47%, corr 0.13; holdout 15.62%/27.66%.",
    "gap-capitulation-reversal": "Passed dev gates: 4.18%/12.49%, corr 0.03; holdout 5.99%/2.29%.",
    "daily-regime-minute-entry": "Negative dev CAGR; the 4% break short does not survive costs.",
    "donchian-breakout": "Negative dev CAGR; 5/10 bp destroy it.",
    "drawdown-regime": "Negative dev CAGR; the deep-drawdown re-risk is too rare and mistimed.",
    "drawdown-stop-overlay": "Negative dev CAGR; the stop is only useful on the old base.",
    "dual-speed-regime": "5.4% CAGR and Sharpe 0.36; below cash/QQQ on risk-adjusted terms.",
    "dynamic-leverage-throttle": "2.65% CAGR with only 5 entries; no usable standalone edge.",
    "ensemble-signals": "Negative dev CAGR; the vol state machine loses money without the old base.",
    "event-risk-overlay": "Strong 26.94%/39.04% and corr 0.34, but fails its own DD>30% gate.",
    "gap-fill-fade": "1.42% CAGR, below BIL; the short is too small to matter.",
    "intraday-momentum": "Corr 0.62 with the old base; fails the <0.60 diversity rule.",
    "letf-rebalance-flow": "13.2%/41.8%; dominated by QQQ on both return and drawdown.",
    "ml-classifier": "20.69%/36.04%, corr 0.58; QQQ has higher Sharpe and lower DD.",
    "ml-crash-overlay-winner": "15.80%/22.42%, corr 0.50; the 10 bp result loses to QQQ on Sharpe.",
    "opening-range-breakout": "Negative dev CAGR; the reclaim has no net edge.",
    "overnight-crash-filter": "10.37%/27.62%, but fails its conditioning/robustness gates.",
    "risk-parity-hrp": "Corr 0.78 with the old base; the risk model is still TQQQ beta.",
    "stop-reentry-recovery": "Only 1 event in 2,012 sessions; the signal is effectively empty.",
    "time-of-day": "Retired: conditioning does not beat the unconditional overnight hold (F1/F2).",
    "vol-kelly-overlay": "1.8% CAGR and Sharpe 0.25; no standalone edge.",
    "vol-scaled-crash-stop": ("Highest rebuild return (57.84%/39.29%) but corr 0.71; "
                              "fails the <0.60 independence rule."),
    "volume-orderflow": "Only 3 events in 2,012 sessions; effectively empty.",
    "winner-ensemble-blend": "0.3% CAGR; the two streams do not combine into a standalone edge.",
}

BENCH = {"10y": (0.3938, 0.8229), "5y": (0.1429, 0.8229)}


def original(slug: str, data: dict, window: str):
    try:
        m = ca.headline_metrics(slug, data, window)
        if m:
            return float(m["cagr"]), float(m["max_drawdown"])
    except Exception:
        pass
    return None


def main():
    rows = []
    for path in sorted(HERE.glob("*/result.json")):
        slug = path.parent.name
        d = json.loads(path.read_text())
        dev = (d.get("windows") or {}).get("dev") or {}
        m = dev.get("1bp") or {}
        hold = (d.get("windows") or {}).get("holdout") or {}
        hm = hold.get("1bp") or {}
        corr = d.get("corr_vs_165d_baseline")
        # original result file
        odata = None
        for base in (ROOT / "research" / "agents", ROOT / "research" / "agents2"):
            p = base / slug / "result.json"
            if p.exists():
                odata = json.loads(p.read_text())
                break
        o10 = original(slug, odata, "10y") if odata else None
        rows.append(dict(slug=slug, idea=d.get("idea", ""), status=STATUS.get(slug, "rejected"),
                         reason=REASON.get(slug, ""), dev=m, hold=hm, corr=corr,
                         o10=o10))

    def pct(x):
        return f"{x*100:.2f}%" if isinstance(x, (int, float)) else "—"

    lines = []
    lines.append("# Revisit summary: 26 standalone rebuilds\n")
    lines.append("Development 2016-01-04 → 2023-12-29. Holdout 2024-01-02 → 2026-10-23, "
                 "run once for the four strategies that passed their dev gates. "
                 "All marks are 1-minute, fills are next-open, costs are 1 bp unless stated. "
                 "TQQQ dev benchmark: 36.39% CAGR / 82.29% max DD; holdout: 43.59% / 62.21%.\n")
    lines.append("| Strategy | Idea | Status | Original 10y CAGR/DD | Rebuild dev 1 bp | Holdout 1 bp | Corr vs 165d |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in rows:
        idea = r["idea"].replace("|", "/")
        if len(idea) > 105:
            idea = idea[:102] + "..."
        o = f"{pct(r['o10'][0])} / {pct(r['o10'][1])}" if r["o10"] else "—"
        dev = f"{pct(r['dev'].get('cagr'))} / {pct(r['dev'].get('max_drawdown'))}"
        hold = f"{pct(r['hold'].get('cagr'))} / {pct(r['hold'].get('max_drawdown'))}" if r["hold"] else "not run"
        corr = f"{r['corr']:.2f}" if isinstance(r["corr"], (int, float)) else "—"
        lines.append(f"| `{r['slug']}` | {idea} | **{r['status']}** | {o} | {dev} | {hold} | {corr} |")

    lines.append("\n## Why each strategy got its status\n")
    for r in rows:
        lines.append(f"- **{r['slug']} — {r['status']}.** {r['reason']}")

    lines.append("\n## Correlations and diversity\n")
    c = json.loads((HERE / "correlations.json").read_text())
    lines.append(f"- Passed rebuilds: {', '.join(c['strategies'])}.")
    lines.append(f"- Average pairwise correlation among the passed set: **{c['average_pairwise']:.3f}**; "
                 f"maximum **{c['max_pairwise']:.3f}** (limit 0.70).")
    lines.append(f"- Correlation vs the old 165-day base: "
                 + ", ".join(f"{k} {v:.2f}" for k, v in c["vs_165d_baseline"].items()) + " (limit 0.60).")
    lines.append(f"- The original 26 shared-base strategies averaged about {c['original_set_average']:.2f} pairwise.")

    lines.append("\n## Honest overall assessment\n")
    lines.append(
        "Removing the shared 165-day TQQQ base destroyed most of the reported returns. "
        "Only four rebuilds passed their pre-registered development gates: ratio-pairs, "
        "intraday-seasonality, intraday-mean-reversion and gap-capitulation-reversal. "
        "They are genuinely independent — average pairwise correlation 0.21, and all four are "
        "below 0.60 versus the old base — but their dev CAGRs are 4–22%, far below TQQQ's 36.4%. "
        "Two of them beat TQQQ over the last five years: intraday-seasonality (26.07% / 43.75% "
        "vs 14.29% / 82.29%) and ratio-pairs (17.11% / 34.59%). Over the full ten years TQQQ still "
        "wins on CAGR, though with an 82% drawdown.\n\n"
        "The highest-return standalone rebuild is vol-scaled-crash-stop at 57.84% / 39.29% dev, "
        "which beats TQQQ on both return and drawdown at 1–5 bp. It is not independent: its daily "
        "correlation with the old base is 0.71, so it is best described as a better-managed TQQQ "
        "exposure rather than a new edge. event-risk-overlay is the strongest genuinely low-correlation "
        "strategy at 26.94% / 39.04% (corr 0.34), but it fails its own 30% drawdown gate.\n\n"
        "Most of the other 22 ideas were overlays: stops, filters and risk rules that added value only "
        "on top of the old trend base. Several signals were effectively empty after the base was removed "
        "(stop-reentry: 1 event; volume-orderflow: 3 events). The evidence supports the original suspicion: "
        "the shared base was doing most of the work."
    )
    (HERE / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote", HERE / "SUMMARY.md")
    print(f"{len(rows)} strategies, {sum(1 for r in rows if r['status'] == 'passed')} passed")


if __name__ == "__main__":
    main()
