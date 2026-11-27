"""Attach the eight repair outcomes to LIBRARY.json.

This does not change a published metric, curve, family or winner.  It records
which follow-up was produced, whether it has a full holdout, and whether the
original name is retired.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LIB = ROOT / "LIBRARY.json"

FULL = {
    "dynamic-leverage-throttle": "dynamic-leverage-throttle-v2",
    "drawdown-regime": "drawdown-regime-v2",
    "gap-capitulation-reversal": "gap-capitulation-reversal-v2",
    "stop-reentry-recovery": "stop-reentry-recovery-v2",
}
DEV_ONLY = {
    "gap-fill-fade": ("gap-fill-fade-v2", "b25_50_2x"),
}
RETIRED = {
    "vol-kelly-overlay": ("vol-kelly-overlay-v2", None),
    "volume-orderflow": ("volume-orderflow-v2", None),
    "drawdown-stop-overlay": ("drawdown-stop-overlay-v2", "h1_trend_vol_nostop_close"),
}

NOTES = {
    "dynamic-leverage-throttle": "18 entries, 3.41% average TQQQ weight; event mean +2.37% (p=0.019). Low-exposure diversifier, below the bar.",
    "drawdown-regime": "19 entries, 28.8% exposure; 2024-26 holdout has 0 entries and stays in BIL. Broader recovery sleeve, below the bar.",
    "gap-capitulation-reversal": "39 events / 26 starts, 7.3% average exposure; 5-session event mean +7.40% (t=3.27). Below the bar.",
    "stop-reentry-recovery": "56 events, one-session hold, 313 full fills; mostly QQQ beta. Below the bar.",
    "vol-kelly-overlay": "Count repair reaches 28 entries but the best grid p=0.223; no edge. Retired.",
    "volume-orderflow": "44 events but volume is not additive (p=0.36) and the close-location sign is backwards. Retired.",
    "drawdown-stop-overlay": "Primary 1-day trend/vol variant: 3.36% dev CAGR, 23.37% DD, 0.54 Sharpe, 1.14% TQQQ time. A static mix at the same exposure earns 1.96%/2.11%/1.13, so retire as a standalone; overlay-only.",
    "gap-fill-fade": "Small-gap/2x inverse variant: 3.21% dev CAGR, 4.69% DD, 1.09 Sharpe, 0.46% average short notional. Development-only satellite; t=2.73, 2018+2022 drive 80% of P&L.",
}


def main() -> None:
    lib = json.loads(LIB.read_text(encoding="utf-8"))
    by_slug = {r["slug"]: r for r in lib["strategies"]}

    for slug, v2 in FULL.items():
        rec = by_slug[slug]
        h = json.loads((ROOT / v2 / "holdout.json").read_text(encoding="utf-8"))
        full = h["windows"]["full"]["daily"]
        dev = h["windows"]["dev"]["daily"]
        rec["repair_status"] = "repaired-diversifier"
        rec["repair_source"] = f"research/new/{v2}/report.md"
        rec["repair_note"] = NOTES[slug]
        rec["repair_dev"] = {"cagr": dev["cagr"], "max_dd": dev["max_drawdown"],
                             "sharpe": dev["sharpe"]}
        rec["repair_full"] = {
            "cagr": full["cagr"], "max_dd": full["max_drawdown"],
            "sharpe": full["sharpe"],
            "fills": h["windows"]["full"]["1bp"]["fills"],
        }

    for slug, (v2, variant) in DEV_ONLY.items():
        rec = by_slug[slug]
        d = json.loads((ROOT / v2 / "result.json").read_text(encoding="utf-8"))
        c = d["variants"][variant]["costs"]["1bp"]
        rec["repair_status"] = "development-only"
        rec["repair_source"] = f"research/new/{v2}/report.md"
        rec["repair_note"] = NOTES[slug]
        rec["repair_dev"] = {"cagr": c["cagr"], "max_dd": c["max_drawdown"],
                             "sharpe": c["sharpe"], "fills": c["fills"]}
        rec["repair_full"] = None

    for slug, (v2, variant) in RETIRED.items():
        rec = by_slug[slug]
        d = json.loads((ROOT / v2 / "result.json").read_text(encoding="utf-8"))
        if variant is None:
            c = d["windows"]["dev"]["1bp"]
        else:
            c = d["variants"][variant]["costs"]["1bp"]
        rec["repair_status"] = "retired"
        rec["repair_source"] = f"research/new/{v2}/report.md"
        rec["repair_note"] = NOTES[slug]
        rec["repair_dev"] = {"cagr": c["cagr"], "max_dd": c["max_drawdown"],
                             "sharpe": c["sharpe"], "fills": c["fills"]}
        rec["repair_full"] = None
        rec["retired"] = True

    LIB.write_text(json.dumps(lib, indent=1), encoding="utf-8")
    print(f"updated {len(FULL) + len(DEV_ONLY) + len(RETIRED)} records in {LIB}")


if __name__ == "__main__":
    main()
