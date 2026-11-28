# New-family programme — final

**Target:** 20 strategies with primary signals distinct from the ten existing
families, plus one that beats `ratio-froth` (full 62.21% CAGR).

**Final set:** 20 new families. Four clear the TQQQ full bar; sixteen are active
below it. **All 20 have signal Jaccard ≤0.66 and raw correlation ≤0.693**
against the existing winners. The separate beater is the regime-switch overlay.

| # | Family | Full CAGR | Full DD | Sharpe | Fills | Winner |
|---:|---|---:|---:|---:|---:|:--:|
| 1 | `crypto-risk-appetite` | 46.50% | 52.33% | 1.19 | 293 | yes |
| 2 | `change-point` | 45.29% | 54.10% | 1.13 | 229 | yes |
| 3 | `hurst-persistence` | 43.00% | 56.25% | 1.04 | 437 | yes |
| 4 | `rates-volatility` | 38.80% | 43.01% | 1.05 | 355 | yes |
| 5 | `energy-rotation` | 36.48% | 72.74% | 0.90 | 447 | no |
| 6 | `efa-spy` | 35.59% | 63.39% | 0.93 | 165 | no |
| 7 | `qual-spy` | 35.03% | 55.72% | 0.91 | 217 | no |
| 8 | `volume-skew` | 34.39% | 46.36% | 1.03 | 2,124 | no |
| 9 | `breadth` | 34.21% | 64.66% | 0.94 | 743 | no |
| 10 | `mtum-spy` | 34.06% | 59.62% | 0.89 | 179 | no |
| 11 | `financials-rotation` | 33.60% | 58.36% | 0.91 | 333 | no |
| 12 | `skew-change` | 32.19% | 56.50% | 0.90 | 577 | no |
| 13 | `sector-rotation` | 29.86% | 48.79% | 0.94 | 719 | no |
| 14 | `retail-rotation` | 27.82% | 56.21% | 0.90 | 329 | no |
| 15 | `homebuilder-rotation` | 24.97% | 59.43% | 0.75 | 333 | no |
| 16 | `gold-miner-stress` | 24.04% | 65.72% | 0.68 | 429 | no |
| 17 | `breakeven` | 19.67% | 76.11% | 0.65 | 557 | no |
| 18 | `hyg-spy` | 19.37% | 78.60% | 0.66 | 383 | no |
| 19 | `yen-carry` | 18.21% | 71.47% | 0.59 | 399 | no |
| 20 | `sector-dispersion` | 16.76% | 68.95% | 0.61 | 273 | no |

## Beating ratio-froth

The beater is `family-regime-switch`, a disclosed composite overlay (not one of
the 20 independent families): close-location in calm, ratio-froth in stress.

| Full window | regime switch | ratio-froth |
|---|---:|---:|
| CAGR | **63.59%** | 62.21% |
| Max drawdown | **31.40%** | 36.65% |
| Sharpe | **1.58** | 1.43 |
| CAGR / DD | **2.02** | 1.70 |
| 5 bp / 10 bp CAGR | **59.19% / 53.87%** | 56.62% / 50.67% |

2024-2026 holdout: 38.70% CAGR / 25.38% DD / 1.13 Sharpe. The close-location
strategy remains the overlay's aggressive sleeve, but it is no longer one of
the 20 published independent families.

## Strict overlap result

Every addition is now at or below 0.70 raw correlation. The highest remaining
values:

| Family | Max corr | Against | Jaccard |
|---|---:|---|---:|
| `gold-miner-stress` | 0.693 | relative-value | 0.537 |
| `energy-rotation` | 0.69 | relative-value | 0.56 |
| `breadth` | 0.68 | short-reversal | 0.28 |
| `yen-carry` | 0.68 | rebalance-flow | 0.58 |

Seven high-correlation names were replaced in the earlier passes; close-location
was replaced by gold-miner stress in the final pass so the 20 itself has no
exception. The beater is separate.

## Removed overlaps

Earlier removals: calendar/session/intraday/risk-sizing overlaps, tail-hedge,
dollar, gold, policy-liquidity, VIX term structure, credit spread,
vol-of-volume, oil-shock, low-vol, beta-rotation, realized-skew, tqqq-decay,
style-rotation, and finally close-location (moved to the overlay sleeve).
