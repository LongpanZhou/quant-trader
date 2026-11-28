# New-family programme — final

**Target:** 20 strategies with primary signals distinct from the ten existing
families, plus one that beats `ratio-froth` (full 62.21% CAGR).

**Final set:** 20 new families. Eight clear the TQQQ full bar; twelve are active
below it. The four highest raw-correlation additions were replaced on
2026-11-28 with low-overlap gates; the full 20×9 audit is in
`FAMILY_OVERLAP_AUDIT.md`.

| # | Family | Full CAGR | Full DD | Sharpe | Fills | Winner |
|---:|---|---:|---:|---:|---:|:--:|
| 1 | `close-location` | **66.23%** | 62.76% | 1.26 | 653 | yes |
| 2 | `crypto-risk-appetite` | 46.50% | 52.33% | 1.19 | 293 | yes |
| 3 | `change-point` | 45.29% | 54.10% | 1.13 | 229 | yes |
| 4 | `hurst-persistence` | 43.00% | 56.25% | 1.04 | 437 | yes |
| 5 | `tqqq-decay` | 40.00% | 37.60% | 1.09 | 329 | yes |
| 6 | `realized-skew` | 38.83% | 53.98% | 0.97 | 439 | yes |
| 7 | `rates-volatility` | 38.80% | 43.01% | 1.05 | 355 | yes |
| 8 | `style-rotation` | 37.98% | 69.89% | 0.92 | 341 | yes |
| 9 | `energy-rotation` | 36.48% | 72.74% | 0.90 | 447 | no |
| 10 | `efa-spy` | 35.59% | 63.39% | 0.93 | 165 | no |
| 11 | `qual-spy` | 35.03% | 55.72% | 0.91 | 217 | no |
| 12 | `volume-skew` | 34.39% | 46.36% | 1.03 | 2,124 | no |
| 13 | `breadth` | 34.21% | 64.66% | 0.94 | 743 | no |
| 14 | `financials-rotation` | 33.60% | 58.36% | 0.91 | 333 | no |
| 15 | `skew-change` | 32.19% | 56.50% | 0.90 | 577 | no |
| 16 | `sector-rotation` | 29.86% | 48.79% | 0.94 | 719 | no |
| 17 | `retail-rotation` | 27.82% | 56.21% | 0.90 | 329 | no |
| 18 | `homebuilder-rotation` | 24.97% | 59.43% | 0.75 | 333 | no |
| 19 | `hyg-spy` | 19.37% | 78.60% | 0.66 | 383 | no |
| 20 | `yen-carry` | 18.21% | 71.47% | 0.59 | 399 | no |

## The ratio-froth beater

`family-close-location` beats `ratio-froth` on CAGR at 1, 5 and 10 bp:
**66.23% / 62.26% / 57.43%** vs **62.21% / 56.62% / 50.67%**. It is long-only
TQQQ and uses no synthetic short. It does not beat ratio-froth on drawdown or
Sharpe; see `RATIO_FROTH_BEATER.md`.

## The four low-overlap replacements

The audit identified four additions whose raw correlation with an existing
winner exceeded 0.77. They were replaced with gates from unused data
dimensions:

| Removed | Corr | Replaced by | Corr | Jaccard | Full CAGR | Holdout CAGR |
|---|---:|---|---:|---:|---:|---:|
| `vol-of-volume` | 0.84 | `skew-change` | 0.60 | 0.48 | 32.19% | 4.00% |
| `oil-shock` | 0.80 | `efa-spy` | 0.60 | 0.44 | 35.59% | 37.16% |
| `lowvol-rotation` | 0.79 | `qual-spy` | 0.61 | 0.49 | 35.03% | 10.85% |
| `beta-rotation` | 0.77 | `hyg-spy` | 0.63 | 0.54 | 19.37% | 12.79% |

The new gates are CBOE SKEW tail-risk pricing, EFA/SPY developed-market
relative, QUAL/SPY quality-factor leadership, and HYG/SPY credit-equity risk
appetite. Pairwise correlations among the four are 0.38–0.61; pairwise
Jaccard is 0.27–0.40.

## Overlap audit

All 20 were tested against all nine existing winners for return correlation,
conditional alpha and signal Jaccard. Maximum Jaccard is 0.66
(`change-point`). The remaining raw correlations above 0.70 are:

| Family | Max corr | Against | Alpha t | Jaccard |
|---|---:|---|---:|---:|
| `close-location` | 0.77 | short-reversal | 2.80 | 0.47 |
| `realized-skew` | 0.74 | relative-value | 1.77 | 0.56 |
| `tqqq-decay` | 0.73 | rebalance-flow | 2.39 | 0.53 |
| `style-rotation` | 0.71 | relative-value | 1.80 | 0.61 |

Each has positive residual alpha and Jaccard ≤0.61. No strategy above 62.21%
has lower raw correlation than close-location; the strict zero-correlation
version of the objective is therefore not achievable with this data. See
`OBJECTIVE_FEASIBILITY.md`.

## Removed overlaps

Earlier removals: calendar/session/intraday/risk-sizing overlaps, tail-hedge,
dollar, gold, policy-liquidity, VIX term structure, credit spread. This turn:
`vol-of-volume`, `oil-shock`, `lowvol-rotation`, `beta-rotation`.
