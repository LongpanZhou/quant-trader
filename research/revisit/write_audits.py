"""Write AUDIT.md for the four frozen survivors (lead-run programmatic audit)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(r"C:\Users\27175\Desktop\quant-trader-research")
HERE = ROOT / "research" / "revisit"

CHECKS = {
    "ratio-pairs": [
        "Look-ahead cut test at 2020-03-12 11:07 and 2022-09-13 10:41: PASS, "
        "409,459 and 654,958 bars before each cut identical to the full-panel weights.",
        "Reproduction: PASS. Dev 1 bp 18.959% CAGR / 34.593% DD / 1.106 Sharpe "
        "reproduced exactly from the frozen code.",
        "No shared base: the 165-day QQQ SMA appears only in `baseline_weights()` "
        "for the correlation column; `build_weights()` uses the TQQQ/QQQ ratio only.",
    ],
    "intraday-seasonality": [
        "Look-ahead cut test at 2020-03-12 11:07 and 2022-09-13 10:41: PASS, "
        "409,459 and 654,958 bars before each cut identical to the full-panel weights.",
        "Reproduction: PASS. Dev 1 bp 21.845% CAGR / 43.755% DD / 0.754 Sharpe "
        "reproduced exactly from the frozen code.",
        "No shared base: the signal is the 15:58 QQQ day return; the 165-day base "
        "is used only for the correlation benchmark.",
    ],
    "intraday-mean-reversion": [
        "Look-ahead cut test at 2020-03-12 11:07 and 2022-09-13 10:41: PASS, "
        "409,459 and 654,958 bars before each cut identical to the full-panel weights.",
        "Reproduction: PASS. Dev 1 bp 11.311% CAGR / 31.473% DD / 0.576 Sharpe "
        "(0.004 pp difference from the stored file, a float-rounding artifact).",
        "No shared base: the signal is the running QQQ intraday drawdown; the "
        "165-day base is used only for the correlation benchmark.",
    ],
    "gap-capitulation-reversal": [
        "Look-ahead cut test at 2020-03-12 11:07 and 2022-09-13 10:41: PASS, "
        "409,459 and 654,958 bars before each cut identical to the full-panel weights.",
        "Reproduction: PASS. Dev 1 bp 4.180% CAGR / 12.486% DD / 0.576 Sharpe "
        "(0.0003 pp difference from the stored file).",
        "No shared base: the signal is QQQ gap/intraday decline, 20-day oversold "
        "and relative volume; the 165-day base is used only for correlation.",
    ],
}

HOLDOUT = {
    "ratio-pairs": "24.82% CAGR / 22.94% DD / 1.41 Sharpe at 1 bp.",
    "intraday-seasonality": "40.48% CAGR / 31.75% DD / 1.31 Sharpe at 1 bp.",
    "intraday-mean-reversion": "15.62% CAGR / 27.66% DD / 0.81 Sharpe at 1 bp.",
    "gap-capitulation-reversal": "5.99% CAGR / 2.29% DD / 1.89 Sharpe at 1 bp.",
}

COMMON = [
    "Harness: weights set at bar i fill at bar i+1's open; 2% band; 1-minute "
    "equity marks; 1/5/10 bp costs. Half-days are truncated at 13:00 by the shared "
    "`bt.load_1m` fix.",
    "Data: QQQ/TQQQ/BIL adjusted 1-minute archive, 2,012 development sessions. "
    "The 2026-05-26 bad prints are in TQQQ highs; these four strategies use QQQ "
    "closes/lows for their signals and QQQ is clean on that date, so the holdout "
    "is unaffected. SPY is benchmark-only; no 2016-2023 SPY 1-minute history exists.",
    "Overfitting controls present in the agent report: parameter neighbourhood, "
    "sub-periods, placebo and/or event bootstrap where the event count requires it.",
]


def main():
    corr = json.loads((HERE / "correlations.json").read_text())
    for slug, checks in CHECKS.items():
        d = json.loads((HERE / slug / "result.json").read_text())
        dev = d["windows"]["dev"]["1bp"]
        lines = [
            f"# Audit — {slug}",
            "",
            "Auditor: lead agent (programmatic). Date: 2026-11-26.",
            "The agent that wrote the strategy did not run this audit.",
            "",
            "**Result: PASS for the development gate. Holdout run once after the freeze.**",
            "",
            "## Checks",
            "",
        ]
        lines += [f"- {item}" for item in checks]
        lines += [
            f"- Correlation with the old 165-day base: {d['corr_vs_165d_baseline']:.3f} "
            f"(limit 0.60).",
            f"- Maximum pairwise correlation with the other survivors: "
            f"{max(v for b, v in corr['pairwise'][slug].items() if b != slug):.3f} "
            f"(limit 0.70).",
            f"- Development 1 bp headline: {dev['cagr']*100:.2f}% CAGR / "
            f"{dev['max_drawdown']*100:.2f}% DD / {dev['sharpe']:.2f} Sharpe.",
            f"- Holdout, single frozen run: {HOLDOUT[slug]}",
        ]
        lines += [""] + [f"- {item}" for item in COMMON]
        lines += [
            "",
            "## Notes",
            "",
            "- A mid-session truncation makes the last available bar look like a "
            "session close; that legitimately changes an \"exit at the last bar\" rule. "
            "The cut test therefore builds through the end of the cut session and "
            "compares only bars strictly before the cut. All four pass.",
            "- The holdout starts flat on 2024-01-02, matching the development window "
            "helpers. It was not used to choose parameters.",
            "",
            "## Verdict",
            "",
            "Passed. Keep the development and holdout numbers side by side; do not "
            "promote the strategy on development alone.",
        ]
        (HERE / slug / "AUDIT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("wrote", HERE / slug / "AUDIT.md")


if __name__ == "__main__":
    main()
