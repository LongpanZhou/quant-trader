"""Export the 26 rebuild results for the All-strategies page.

The standalone Rebuild page is gone; the All-strategies page is the single
canonical place for strategy updates.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "research" / "revisit"
OUT = ROOT / "web" / "public" / "data" / "compare" / "rebuild.json"

STATUS = {
    "ratio-pairs": "passed",
    "intraday-seasonality": "passed",
    "intraday-mean-reversion": "passed",
    "gap-capitulation-reversal": "passed",
}

REASON = {
    "ratio-pairs": "Passed dev gates; holdout 24.82%/22.94%.",
    "intraday-seasonality": "Passed dev gates; holdout 40.48%/31.75%.",
    "intraday-mean-reversion": "Passed dev gates; holdout 15.62%/27.66%.",
    "gap-capitulation-reversal": "Passed dev gates; holdout 5.99%/2.29%.",
    "daily-regime-minute-entry": "Negative dev CAGR; the break short does not survive costs.",
    "donchian-breakout": "Negative dev CAGR; 5/10 bp destroy it.",
    "drawdown-regime": "Negative dev CAGR; the deep-drawdown re-risk is too rare and mistimed.",
    "drawdown-stop-overlay": "Negative dev CAGR; the stop only helped the old base.",
    "dual-speed-regime": "5.4% CAGR and Sharpe 0.36; below QQQ on risk-adjusted terms.",
    "dynamic-leverage-throttle": "2.65% CAGR with only 5 entries.",
    "ensemble-signals": "Negative dev CAGR; the vol state machine loses without the base.",
    "event-risk-overlay": "26.94%/39.04% and corr 0.34, but fails its own DD>30% gate.",
    "gap-fill-fade": "1.42% CAGR, below BIL; the short is too small to matter.",
    "intraday-momentum": "Corr 0.62 with the old base; fails the <0.60 rule.",
    "letf-rebalance-flow": "13.2%/41.8%; dominated by QQQ on return and drawdown.",
    "ml-classifier": "20.69%/36.04%, corr 0.58; QQQ has higher Sharpe and lower DD.",
    "ml-crash-overlay-winner": "15.80%/22.42%, corr 0.50; 10 bp loses to QQQ on Sharpe.",
    "opening-range-breakout": "Negative dev CAGR; the reclaim has no net edge.",
    "overnight-crash-filter": "10.37%/27.62%, but fails its conditioning gates.",
    "risk-parity-hrp": "Corr 0.78 with the old base; still TQQQ beta.",
    "stop-reentry-recovery": "Only 1 event in 2,012 sessions.",
    "time-of-day": "Conditioning does not beat the unconditional overnight hold.",
    "vol-kelly-overlay": "1.8% CAGR and Sharpe 0.25.",
    "vol-scaled-crash-stop": "Highest rebuild return (57.84%/39.29%) but corr 0.71.",
    "volume-orderflow": "Only 3 events in 2,012 sessions.",
    "winner-ensemble-blend": "0.3% CAGR; the streams do not combine.",
}

LABEL = {
    "passed": "Passed",
    "rejected": "Rejected",
    "retired_overlay_only": "Retired",
}


def pack(m: dict | None) -> dict | None:
    if not isinstance(m, dict) or "cagr" not in m:
        return None
    return {k: float(m[k]) for k in ("cagr", "max_drawdown", "sharpe", "fills") if k in m}


def main():
    research = json.loads(
        (ROOT / "web" / "public" / "data" / "research" / "strategies.json").read_text()
    )
    names = {s["slug"]: s.get("name", s["slug"]) for s in research["strategies"]}
    rows = []
    for path in sorted(HERE.glob("*/result.json")):
        slug = path.parent.name
        d = json.loads(path.read_text())
        w = d.get("windows") or {}
        dev = w.get("dev") or {}
        hold = w.get("holdout") or {}
        ten = w.get("10y") or {}
        five = w.get("5y") or {}
        status = STATUS.get(slug, d.get("status", "rejected"))
        if status not in LABEL:
            status = "rejected"
        rows.append({
            "slug": slug,
            "name": names.get(slug, slug.replace("-", " ").title()),
            "status": status,
            "statusLabel": LABEL[status],
            "idea": d.get("idea", ""),
            "reason": REASON.get(slug, ""),
            "dev": pack(dev.get("1bp")),
            "dev5": pack(dev.get("5bp")),
            "dev10": pack(dev.get("10bp")),
            "holdout": pack(hold.get("1bp")),
            "tenY": pack(ten.get("1bp")),
            "fiveY": pack(five.get("1bp")),
            "corr": d.get("corr_vs_165d_baseline"),
        })
    order = {"passed": 0, "rejected": 1, "retired_overlay_only": 2}
    rows.sort(key=lambda r: (order[r["status"]], -(r["dev"]["cagr"] if r["dev"] else -9)))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "generated": "2026-11-26",
        "title": "Rebuild 2026 audit",
        "note": ("26 strategies rebuilt without the shared 165-day base. "
                 "Development 2016-2023; holdout 2024-2026 only for the four "
                 "strategies that passed their pre-registered gates."),
        "strategies": rows,
    }, indent=1), encoding="utf-8")
    print(f"wrote {OUT} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
