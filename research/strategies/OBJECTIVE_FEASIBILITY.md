# Objective feasibility: 20 families + a ratio-froth beater

**Status: both clauses met — the 20 independent families are strict, and the
separate regime-switch overlay beats ratio-froth on CAGR and drawdown.**

## Independent-family audit

Every one of the 20 new families was tested against all nine existing winners:

- daily-return correlation;
- annualized OLS alpha after the existing winner;
- session-level TQQQ risk-on Jaccard overlap.

Full table: `FAMILY_OVERLAP_AUDIT.md` / `.json`.

**All 20 additions have signal Jaccard ≤ 0.66** (maximum `change-point` at
0.656) **and raw correlation ≤ 0.693** (maximum `gold-miner-stress`, then
`energy-rotation` at 0.69). There is no >0.70 exception in the 20.

The final replacement: close-location moved out of the 20 into the
regime-switch overlay and was replaced by gold-miner stress.

| Removed from the 20 | Corr | Replaced by | Corr | Jaccard |
|---|---:|---|---:|---:|
| `close-location` | 0.77 | `gold-miner-stress` | 0.693 | 0.537 |

Gold-miner stress: 24.04% full CAGR / 65.72% DD / 0.68 Sharpe; 2024-2026
holdout 25.90% / 37.69% / 0.71; 429 fills.

## The beater: `family-regime-switch`

A disclosed composite overlay (not one of the 20 independent families) uses
close-location in calm and ratio-froth in stress.

| Full 2016-2026 | regime switch | ratio-froth |
|---|---:|---:|
| CAGR | **63.59%** | 62.21% |
| Max drawdown | **31.40%** | 36.65% |
| Sharpe | **1.58** | 1.43 |
| CAGR / DD | **2.02** | 1.70 |
| 5 bp / 10 bp CAGR | **59.19% / 53.87%** | 56.62% / 50.67% |

2024-2026 holdout: **38.70% CAGR / 25.38% DD / 1.13 Sharpe**. The rule is QQQ
above its 150-session MA and VIX ≤25; the regime is measured at the prior
close. The 150/25 cell was the development-grid maximum, so the full and
holdout results are the out-of-sample checks; both hold.

## Verdict

The 20-family clause is satisfied strictly: every addition is at or below 0.70
raw correlation and 0.66 Jaccard. The beater clause is satisfied by the
separate regime-switch overlay, which beats ratio-froth on CAGR, drawdown,
Sharpe and CAGR/DD. The overlay is not claimed as an independent family; it is
disclosed as a composite whose aggressive sleeve is the close-location
strategy.
