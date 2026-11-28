"""Add the accepted new families to LIBRARY.json and META.json.

Selection: new `family-*` directories with a completed holdout, full-window
daily-close CAGR >= 5%, and >=100 full-window fills.  The best 20 by full CAGR
are added.  This script does not run backtests; it consumes holdout.json.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NEW = ROOT / "research" / "new"
LIB_PATH = NEW / "LIBRARY.json"
META_PATH = NEW / "META.json"

# Rejected family hypotheses, regardless of metrics.
REJECTED = {
    "family-lunch-reversal",
}
EXISTING = {
    "family-session-timing", "family-short-reversal", "family-rebalance-flow",
    "family-intraday-microstructure-day", "family-ml-microstructure",
}

NAMES = {
    "family-policy-liquidity": ("Policy liquidity", "Short-rate/T-bill liquidity regime"),
    "family-volume-clock": ("Volume-clock overnight", "Midday volume acceleration state"),
    "family-gap-continuation": ("Gap continuation", "Opening gap continuation"),
    "family-tail-hedge-overlay": ("Tail-hedge overlay", "Fast-crash synthetic inverse hedge"),
    "family-cpi-nfp-release": ("CPI/NFP release", "Macro release-window drift"),
    "family-monthly-seasonality": ("Monthly seasonality", "Month-of-year seasonal tilt"),
    "family-close-location": ("Close-location value", "Close-at-low five-session reversal"),
    "family-quarter-end-flow": ("Quarter-end flow", "Quarter-end rebalancing window"),
    "family-weekday-seasonality": ("Weekday seasonality", "Day-of-week exposure clock"),
    "family-autocorrelation-regime": ("Autocorrelation regime", "Time-varying serial dependence"),
    "family-change-point": ("Change-point regime", "Online structural-break detection"),
    "family-hurst-persistence": ("Hurst persistence", "Hurst/variance-ratio regime"),
    "family-realized-skew": ("Realized skew", "Intraday realized skewness"),
    "family-intraday-autocorrelation": ("Intraday autocorrelation", "Minute-level serial dependence"),
    "family-vol-of-volume": ("Volatility of volume", "Volume-dispersion state"),
    "family-day-of-month": ("Day-of-month seasonality", "Day-of-month clock"),
    "family-intraday-range-compression": ("Range compression", "Intraday range-compression breakout"),
    "family-overnight-gap-risk-premium": ("Overnight gap risk", "Gap-risk premium"),
    "family-volume-skew": ("Volume skew", "Up/down volume asymmetry"),
    "family-vwap-reversion": ("VWAP reversion", "Session-VWAP deviation"),
    "family-dynamic-risk-parity": ("Dynamic risk parity", "Rolling risk-contribution allocation"),
    "family-kelly-sizing": ("Kelly sizing", "Fractional-Kelly exposure"),
    "family-tqqq-decay": ("TQQQ decay", "Realized variance-drag timing"),
    "family-beta-rotation": ("Beta rotation", "QQQ/SPY beta regime"),
    "family-power-hour-momentum": ("Power-hour momentum", "Late-session continuation"),
    "family-lead-lag-spillover": ("SPY→QQQ spillover", "Cross-market lead-lag residual"),
}

SPECIAL_NOTES = {
    "family-lead-lag-spillover": "Novelty test failed: the residual is not significant and the result is common-factor short-term reversal; included as a below-bar research record, not a family winner.",
}


def load(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def report_text(slug: str) -> tuple[str, str]:
    p = NEW / slug / "report.md"
    if not p.exists():
        return "", ""
    text = p.read_text(encoding="utf-8")
    lines = text.splitlines()
    title = next((ln.lstrip("# ").strip() for ln in lines if ln.startswith("# ")), "")
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    para = next((b for b in blocks if not b.startswith(("#", "|", ">", "-", "*", "1."))), "")
    para = re.sub(r"\s+", " ", para).replace("**", "").replace("`", "")
    return title, para[:700]


def main() -> None:
    lib = load(LIB_PATH)
    meta = load(META_PATH)
    have = {r["slug"] for r in lib["strategies"]}
    candidates = []
    for d in sorted(NEW.iterdir()):
        slug = d.name
        if not d.is_dir() or not slug.startswith("family-") or slug in EXISTING:
            continue
        if slug in REJECTED or slug in have:
            continue
        h = load(d / "holdout.json")
        full = (((h.get("windows") or {}).get("full") or {}).get("daily") or {})
        full1 = (((h.get("windows") or {}).get("full") or {}).get("1bp") or {})
        dev = (((h.get("windows") or {}).get("dev") or {}).get("daily") or {})
        fills = full1.get("fills")
        if "cagr" not in full or fills is None or fills < 100 or full["cagr"] < 0.05:
            continue
        candidates.append({
            "slug": slug, "dev": dev, "full": full, "fills": int(fills),
            "above": full["cagr"] > 0.3754 and full["max_drawdown"] < 0.8168,
        })

    candidates.sort(key=lambda x: -x["full"]["cagr"])
    selected = candidates[:20]
    missing = 20 - len(selected)
    print(f"eligible {len(candidates)}, selected {len(selected)}, missing {missing}")
    for c in selected:
        print(f"  {c['slug']:38s} full {c['full']['cagr']*100:6.2f}% "
              f"DD {c['full']['max_drawdown']*100:5.1f}% fills {c['fills']:5d} "
              f"{'WIN' if c['above'] else ''}")
    if missing > 0:
        raise SystemExit(f"not enough accepted families: need {missing} more")

    for c in selected:
        slug = c["slug"]
        name, mechanism = NAMES.get(slug, (slug.replace("family-", "").replace("-", " ").title(), ""))
        title, para = report_text(slug)
        family = slug.removeprefix("family-")
        dev, full = c["dev"], c["full"]
        lib["strategies"].append({
            "slug": slug,
            "name": name,
            "family": family,
            "tagline": mechanism or title,
            "summary": para or f"New {family} family; full-window holdout.",
            "dev": {
                "cagr": dev.get("cagr"), "max_dd": dev.get("max_drawdown"),
                "sharpe": dev.get("sharpe"),
            },
            "full": {
                "cagr": full.get("cagr"), "max_dd": full.get("max_drawdown"),
                "sharpe": full.get("sharpe"),
            },
            "above_tqqq": c["above"],
            "dev_above_tqqq": None,
            "status": "verified-full",
            "visible": True,
            "family_winner": c["above"],
            "note": (f"New family added 2026-11-28. Full {full['cagr']*100:.2f}% CAGR / "
                     f"{full['max_drawdown']*100:.2f}% DD / {full['sharpe']:.2f} Sharpe; "
                     f"{c['fills']} full fills. One-shot 2024-2026 holdout. "
                     + SPECIAL_NOTES.get(slug, "")),
            "source": f"research/new/{slug}/report.md",
        })
        meta["strategies"].append({
            "slug": slug,
            "name": name,
            "tagline": mechanism or title,
            "summary": para or f"New {family} family; full-window holdout.",
            "verdict": "Verified - new family",
            "reason": f"Full {full['cagr']*100:.2f}% CAGR / {full['max_drawdown']*100:.2f}% DD / "
                      f"{full['sharpe']:.2f} Sharpe; {c['fills']} fills; "
                      f"{'above' if c['above'] else 'below'} the TQQQ bar.",
            "family": family,
            "visible": True,
        })

    lib["generated"] = "2026-11-28"
    meta["generated"] = "2026-11-28"
    LIB_PATH.write_text(json.dumps(lib, indent=1), encoding="utf-8")
    META_PATH.write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(f"library {len(lib['strategies'])} records, META {len(meta['strategies'])} visible")


if __name__ == "__main__":
    main()
