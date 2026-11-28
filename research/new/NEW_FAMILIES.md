# New-family programme — final

**Target:** 20 strategies with primary signals distinct from the ten existing
families, plus one that beats `ratio-froth` (full 62.21% CAGR).

**Final set:** 20 new families. Eleven clear the TQQQ full bar; nine are active
below it. Every remaining addition has session-level TQQQ Jaccard **≤ 0.66**
against the existing winners; the full audit is in `FAMILY_OVERLAP_AUDIT.md`.

| # | Family | Full CAGR | Full DD | Sharpe | Fills | Winner |
|---:|---|---:|---:|---:|---:|:--:|
| 1 | `close-location` | **66.23%** | 62.76% | 1.26 | 653 | yes |
| 2 | `oil-shock` | 46.95% | 64.46% | 0.97 | 349 | yes |
| 3 | `crypto-risk-appetite` | 46.50% | 52.33% | 1.19 | 293 | yes |
| 4 | `vol-of-volume` | 45.56% | 70.00% | 1.09 | 1,921 | yes |
| 5 | `change-point` | 45.29% | 54.10% | 1.13 | 229 | yes |
| 6 | `hurst-persistence` | 43.00% | 56.25% | 1.04 | 437 | yes |
| 7 | `tqqq-decay` | 40.00% | 37.60% | 1.09 | 329 | yes |
| 8 | `realized-skew` | 38.83% | 53.98% | 0.97 | 439 | yes |
| 9 | `rates-volatility` | 38.80% | 43.01% | 1.05 | 355 | yes |
| 10 | `style-rotation` | 37.98% | 69.89% | 0.92 | 341 | yes |
| 11 | `beta-rotation` | 37.70% | 59.60% | 1.03 | 225 | yes |
| 12 | `energy-rotation` | 36.48% | 72.74% | 0.90 | 447 | no |
| 13 | `volume-skew` | 34.39% | 46.36% | 1.03 | 2,124 | no |
| 14 | `breadth` | 34.21% | 64.66% | 0.94 | 743 | no |
| 15 | `financials-rotation` | 33.60% | 58.36% | 0.91 | 333 | no |
| 16 | `sector-rotation` | 29.86% | 48.79% | 0.94 | 719 | no |
| 17 | `retail-rotation` | 27.82% | 56.21% | 0.90 | 329 | no |
| 18 | `homebuilder-rotation` | 24.97% | 59.43% | 0.75 | 333 | no |
| 19 | `yen-carry` | 18.21% | 71.47% | 0.59 | 399 | no |
| 20 | `lowvol-rotation` | 13.31% | 70.95% | 0.51 | 295 | no |

## The ratio-froth beater

`family-close-location` beats `ratio-froth` on CAGR at 1, 5 and 10 bp:
**66.23% / 62.26% / 57.43%** vs **62.21% / 56.62% / 50.67%**. It is long-only
TQQQ and uses no synthetic short. It does not beat ratio-froth on drawdown or
Sharpe; see `RATIO_FROTH_BEATER.md`.

## Overlap audit

All 20 were tested against all nine existing winners for return correlation,
conditional alpha and signal Jaccard. Maximum remaining Jaccard is 0.66
(`change-point`); the other 19 are ≤ 0.61. Close-location has Jaccard 0.47 and
residual alpha +37.8%/yr (t=2.80), but raw correlation 0.77; see
`OBJECTIVE_FEASIBILITY.md`.

## Removed overlaps

Calendar/session/intraday/risk-sizing overlaps were replaced by external
families. Tail-hedge, dollar and gold were replaced after the residual-alpha
audit. Policy-liquidity, VIX term structure and credit spread were replaced by
homebuilder, financials and retail after they exceeded 0.70 signal Jaccard.

`lead-lag-spillover`, `autocorrelation-regime` and `natural-gas-shock` were
also rejected for overlap/novelty.
