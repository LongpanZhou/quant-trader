"""Replace ten overlapping new families with ten external-data families.

Run only after the external candidates have full holdouts.  Keeps the ten
distinct existing additions and swaps out the calendar/session/intraday/risk
overlaps.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NEW = ROOT / "research" / "new"
WEB = ROOT / "web" / "public" / "data"
LIB_PATH = NEW / "LIBRARY.json"
META_PATH = NEW / "META.json"

OVERLAPS = [
    "family-weekday-seasonality",
    "family-day-of-month",
    "family-monthly-seasonality",
    "family-cpi-nfp-release",
    "family-quarter-end-flow",
    "family-kelly-sizing",
    "family-dynamic-risk-parity",
    "family-volume-clock",
    "family-range-compression",
    "family-gap-continuation",
]
EXTERNAL = [
    "family-vix-term-structure",
    "family-credit-spread",
    "family-sector-rotation",
    "family-breadth",
    "family-crypto-risk-appetite",
    "family-small-cap-relative",
    "family-international-relative",
    "family-rates-volatility",
    "family-copper-gold",
    "family-energy-rotation",
]
NAMES = {
    "family-vix-term-structure": ("VIX term structure", "Implied-vol curve contango/backwardation"),
    "family-credit-spread": ("Credit risk appetite", "HYG/IEF credit-spread impulse"),
    "family-yield-curve": ("Yield-curve slope", "10y-3m Treasury slope"),
    "family-dollar-regime": ("Dollar regime", "UUP dollar impulse"),
    "family-gold-safe-haven": ("Gold safe-haven", "GLD/QQQ safe-haven demand"),
    "family-oil-shock": ("Oil shock", "USO energy shock"),
    "family-bond-equity-correlation": ("Bond-equity correlation", "TLT/QQQ rolling correlation"),
    "family-sector-rotation": ("Growth/defensive rotation", "XLK/XLU sector leadership"),
    "family-breadth": ("Equal-weight breadth", "RSP/SPY breadth"),
    "family-crypto-risk-appetite": ("Crypto risk appetite", "BTC momentum risk appetite"),
    "family-small-cap-relative": ("Small-cap relative", "IWM/QQQ small-cap leadership"),
    "family-international-relative": ("International relative", "EEM/QQQ global risk appetite"),
    "family-rates-volatility": ("Rates volatility", "MOVE rates-vol regime"),
    "family-copper-gold": ("Copper/gold", "CPER/GLD growth vs defensive"),
    "family-energy-rotation": ("Energy rotation", "XLE/XLK energy-vs-tech leadership"),
}


def load(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def report_text(slug: str) -> str:
    p = NEW / slug / "report.md"
    if not p.exists():
        return ""
    text = p.read_text(encoding="utf-8")
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    para = next((b for b in blocks if not b.startswith(("#", "|", ">", "-", "*", "1."))), "")
    return re.sub(r"\s+", " ", para).replace("**", "").replace("`", "")[:700]


def main() -> None:
    lib = load(LIB_PATH)
    meta = load(META_PATH)
    rows = []
    for slug in EXTERNAL:
        h = load(NEW / slug / "holdout.json")
        full = (((h.get("windows") or {}).get("full") or {}).get("daily") or {})
        full1 = (((h.get("windows") or {}).get("full") or {}).get("1bp") or {})
        dev = (((h.get("windows") or {}).get("dev") or {}).get("daily") or {})
        fills = full1.get("fills")
        if "cagr" not in full or fills is None or fills < 100 or full["cagr"] < 0.05:
            print(f"REJECT {slug}: full={full.get('cagr')} fills={fills}")
            continue
        rows.append((slug, dev, full, int(fills)))
    if len(rows) < 10:
        raise SystemExit(f"only {len(rows)} external families qualified; need 10")

    lib["strategies"] = [r for r in lib["strategies"] if r["slug"] not in OVERLAPS]
    meta["strategies"] = [r for r in meta["strategies"] if r["slug"] not in OVERLAPS]

    for slug, dev, full, fills in rows[:10]:
        name, mechanism = NAMES.get(slug, (slug.replace("family-", "").replace("-", " ").title(), ""))
        family = slug.removeprefix("family-")
        above = full["cagr"] > 0.3754 and full["max_drawdown"] < 0.8168
        summary = report_text(slug) or f"New {family} family; full-window holdout."
        lib["strategies"].append({
            "slug": slug, "name": name, "family": family,
            "tagline": mechanism, "summary": summary,
            "dev": {"cagr": dev.get("cagr"), "max_dd": dev.get("max_drawdown"),
                    "sharpe": dev.get("sharpe")},
            "full": {"cagr": full.get("cagr"), "max_dd": full.get("max_drawdown"),
                     "sharpe": full.get("sharpe")},
            "above_tqqq": above, "dev_above_tqqq": None,
            "status": "verified-full", "visible": True, "family_winner": above,
            "note": (f"External-data family added 2026-11-28. Full {full['cagr']*100:.2f}% CAGR / "
                     f"{full['max_drawdown']*100:.2f}% DD / {full['sharpe']:.2f} Sharpe; "
                     f"{fills} full fills. One-shot 2024-2026 holdout."),
            "source": f"research/new/{slug}/report.md",
        })
        meta["strategies"].append({
            "slug": slug, "name": name, "tagline": mechanism, "summary": summary,
            "verdict": "Verified - new external family",
            "reason": f"Full {full['cagr']*100:.2f}% CAGR / {full['max_drawdown']*100:.2f}% DD / "
                      f"{full['sharpe']:.2f} Sharpe; {fills} fills; "
                      f"{'above' if above else 'below'} the TQQQ bar.",
            "family": family, "visible": True,
        })

    LIB_PATH.write_text(json.dumps(lib, indent=1), encoding="utf-8")
    META_PATH.write_text(json.dumps(meta, indent=1), encoding="utf-8")

    for slug in OVERLAPS:
        for p in (
            NEW / "curves" / f"{slug}.json",
            WEB / "research" / f"{slug}.json",
            WEB / "research" / "code" / f"{slug}.py",
        ):
            if p.exists():
                p.unlink()
                print("deleted", p)

    print(f"library {len(lib['strategies'])}, meta {len(meta['strategies'])}")
    for slug, dev, full, fills in rows[:10]:
        print(f"{slug:40s} full {full['cagr']*100:6.2f}% fills {fills:5d}")


if __name__ == "__main__":
    main()
