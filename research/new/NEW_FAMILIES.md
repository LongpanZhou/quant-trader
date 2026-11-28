# New-family programme — final

**Target:** 20 strategies with primary signals distinct from the ten existing
families, plus one that beats `ratio-froth` (full 62.21% CAGR).

**Final set:** 20 new families. Five clear the TQQQ full bar; fifteen are
active below it. Every addition has signal Jaccard ≤0.66 against the existing
winners, and every non-beater has raw correlation ≤0.69. The only remaining
exception is the ratio-froth beater itself, which is disclosed below.

| # | Family | Full CAGR | Full DD | Sharpe | Fills | Winner |
|---:|---|---:|---:|---:|---:|:--:|
| 1 | `close-location` | **66.23%** | 62.76% | 1.26 | 653 | yes |
| 2 | `crypto-risk-appetite` | 46.50% | 52.33% | 1.19 | 293 | yes |
| 3 | `change-point` | 45.29% | 54.10% | 1.13 | 229 | yes |
| 4 | `hurst-persistence` | 43.00% | 56.25% | 1.04 | 437 | yes |
| 5 | `rates-volatility` | 38.80% | 43.01% | 1.05 | 355 | yes |
| 6 | `energy-rotation` | 36.48% | 72.74% | 0.90 | 447 | no |
| 7 | `efa-spy` | 35.59% | 63.39% | 0.93 | 165 | no |
| 8 | `qual-spy` | 35.03% | 55.72% | 0.91 | 217 | no |
| 9 | `volume-skew` | 34.39% | 46.36% | 1.03 | 2,124 | no |
| 10 | `breadth` | 34.21% | 64.66% | 0.94 | 743 | no |
| 11 | `mtum-spy` | 34.06% | 59.62% | 0.89 | 179 | no |
| 12 | `financials-rotation` | 33.60% | 58.36% | 0.91 | 333 | no |
| 13 | `skew-change` | 32.19% | 56.50% | 0.90 | 577 | no |
| 14 | `sector-rotation` | 29.86% | 48.79% | 0.94 | 719 | no |
| 15 | `retail-rotation` | 27.82% | 56.21% | 0.90 | 329 | no |
| 16 | `homebuilder-rotation` | 24.97% | 59.43% | 0.75 | 333 | no |
| 17 | `breakeven` | 19.67% | 76.11% | 0.65 | 557 | no |
| 18 | `hyg-spy` | 19.37% | 78.60% | 0.66 | 383 | no |
| 19 | `yen-carry` | 18.21% | 71.47% | 0.59 | 399 | no |
| 20 | `sector-dispersion` | 16.76% | 68.95% | 0.61 | 273 | no |

## Beating ratio-froth

The drawdown-adjusted beater is `family-regime-switch`, a composite overlay
(not one of the 20 independent families): close-location in calm, ratio-froth
in stress.

| Full window | regime switch | ratio-froth |
|---|---:|---:|
| CAGR | **63.59%** | 62.21% |
| Max drawdown | **31.40%** | 36.65% |
| Sharpe | **1.58** | 1.43 |
| CAGR / DD | **2.02** | 1.70 |
| 5 bp / 10 bp CAGR | **59.19% / 53.87%** | 56.62% / 50.67% |

The raw-CAGR component is `family-close-location`: **66.23% / 62.26% / 57.43%**
at 1/5/10 bp, but 62.76% drawdown and 1.26 Sharpe. It wins on raw CAGR only.
See `RATIO_FROTH_BEATER.md`.

## Strict overlap result

All 20 additions have signal Jaccard ≤0.66 (`change-point`). The four highest
raw-correlation names were replaced first:

| Removed | Corr | Replaced by | Corr | Jaccard |
|---|---:|---|---:|---:|
| `vol-of-volume` | 0.84 | `skew-change` | 0.60 | 0.48 |
| `oil-shock` | 0.80 | `efa-spy` | 0.60 | 0.44 |
| `lowvol-rotation` | 0.79 | `qual-spy` | 0.61 | 0.49 |
| `beta-rotation` | 0.77 | `hyg-spy` | 0.63 | 0.54 |

The three remaining non-beater names above 0.70 were then replaced:

| Removed | Corr | Replaced by | Corr | Jaccard |
|---|---:|---|---:|---:|
| `realized-skew` | 0.74 | `mtum-spy` | 0.674 | 0.573 |
| `tqqq-decay` | 0.73 | `breakeven` | 0.602 | 0.481 |
| `style-rotation` | 0.71 | `sector-dispersion` | 0.643 | 0.551 |

**Every non-beater addition is now at or below 0.69 raw correlation.** The
only remaining exception is `close-location` at 0.77, and it is the only
strategy above ratio-froth's 62.21% CAGR.

## Why the beater exception remains

`close-location` has Jaccard **0.47**, residual alpha **+37.8%/yr at t=2.80**,
and +25.44%/yr alpha after short-reversal. No genuinely low-correlation family
clears 62.21%: crypto 46.50%, rates 38.80%, EFA/SPY 35.59%, QUAL/SPY 35.03%.
Returns above 62% require high TQQQ beta, which mechanically raises raw
correlation with the existing high-beta winners. See
`OBJECTIVE_FEASIBILITY.md`.

## Removed overlaps

Earlier removals: calendar/session/intraday/risk-sizing overlaps, tail-hedge,
dollar, gold, policy-liquidity, VIX term structure, credit spread. Then
vol-of-volume, oil-shock, low-vol, beta-rotation. Finally realized-skew,
tqqq-decay and style-rotation.
