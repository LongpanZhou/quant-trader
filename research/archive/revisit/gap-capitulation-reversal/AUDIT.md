# Audit — gap-capitulation-reversal

Auditor: lead agent (programmatic). Date: 2026-11-26.
The agent that wrote the strategy did not run this audit.

**Result: PASS for the development gate. Holdout run once after the freeze.**

## Checks

- Look-ahead cut test at 2020-03-12 11:07 and 2022-09-13 10:41: PASS, 409,459 and 654,958 bars before each cut identical to the full-panel weights.
- Reproduction: PASS. Dev 1 bp 4.180% CAGR / 12.486% DD / 0.576 Sharpe (0.0003 pp difference from the stored file).
- No shared base: the signal is QQQ gap/intraday decline, 20-day oversold and relative volume; the 165-day base is used only for correlation.
- Correlation with the old 165-day base: 0.027 (limit 0.60).
- Maximum pairwise correlation with the other survivors: 0.229 (limit 0.70).
- Development 1 bp headline: 4.18% CAGR / 12.49% DD / 0.58 Sharpe.
- Holdout, single frozen run: 5.99% CAGR / 2.29% DD / 1.89 Sharpe at 1 bp.

- Harness: weights set at bar i fill at bar i+1's open; 2% band; 1-minute equity marks; 1/5/10 bp costs. Half-days are truncated at 13:00 by the shared `bt.load_1m` fix.
- Data: QQQ/TQQQ/BIL adjusted 1-minute archive, 2,012 development sessions. The 2026-05-26 bad prints are in TQQQ highs; these four strategies use QQQ closes/lows for their signals and QQQ is clean on that date, so the holdout is unaffected. SPY is benchmark-only; no 2016-2023 SPY 1-minute history exists.
- Overfitting controls present in the agent report: parameter neighbourhood, sub-periods, placebo and/or event bootstrap where the event count requires it.

## Notes

- A mid-session truncation makes the last available bar look like a session close; that legitimately changes an "exit at the last bar" rule. The cut test therefore builds through the end of the cut session and compares only bars strictly before the cut. All four pass.
- The holdout starts flat on 2024-01-02, matching the development window helpers. It was not used to choose parameters.

## Verdict

Passed. Keep the development and holdout numbers side by side; do not promote the strategy on development alone.
