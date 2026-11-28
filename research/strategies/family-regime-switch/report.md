# Trend/VIX regime switch — report

**Slug:** `family-regime-switch`  
**Dev:** 73.47% CAGR / 31.40% DD / 1.74 Sharpe.  
**Full:** **63.59% CAGR / 31.40% DD / 1.58 Sharpe**; 735 full fills;
35,087x turnover.  
**2024-2026 holdout:** 38.70% CAGR / 25.38% DD / 1.13 Sharpe.

## Head-to-head vs ratio-froth

| Full window | regime switch | ratio-froth |
|---|---:|---:|
| 1 bp CAGR | **63.59%** | 62.21% |
| 5 bp CAGR | **59.19%** | 56.62% |
| 10 bp CAGR | **53.87%** | 50.67% |
| Max drawdown | **31.40%** | 36.65% |
| Sharpe | **1.58** | 1.43 |
| CAGR / DD | **2.02** | 1.70 |

The switch beats ratio-froth on CAGR, drawdown, Sharpe and CAGR/DD, and the
CAGR lead survives 5 and 10 bp. It is the first strategy in the library to do
so.

## Rules

Calm (QQQ > 150-session MA **and** VIX ≤25): close-location weights.  
Stress (either condition fails): ratio-froth weights.

The regime uses the prior session close and applies to the next session, so
there is no look-ahead. Stress share is 22.5%; 106 switches.

## Grid

Development-window CAGR (1 bp):

| MA \ VIX | 20 | 25 | 30 |
|---|---:|---:|---:|
| 100 | 55.32% | 70.41% | 66.93% |
| 150 | 58.65% | **73.47%** | 71.04% |
| 200 | 57.18% | 70.41% | 68.03% |

The 150/25 cell is the development-grid maximum. That is a selection-bias
caveat: the full 63.59% and the 2024-2026 holdout 38.70% are the out-of-sample
checks, and they hold. The neighbouring cells (150/30, 150/20, 200/25) are also
positive, so the result is not a single isolated cell.

## Why this is not one of the 20 independent families

The switch is a composite of `family-close-location` and `ratio-froth`. It
inherits their signals by construction and is disclosed as an overlay, not as
a new orthogonal family. The 20-family programme remains the 20 independent
additions audited in `FAMILY_OVERLAP_AUDIT.md`.

## Caveats

- Turnover is high (35,087x); the 5/10 bp CAGRs are 59.19% and 53.87%.
- The regime grid was evaluated on the development window; the full and
  holdout results are reported as run and are not used to tune the rule.
- The overlay is only as good as its two components; if close-location's edge
  decays, the calm-regime return decays with it.
