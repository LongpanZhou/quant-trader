# New-family programme — final

**Target:** add 20 strategies, each with a distinct primary family, and find one
that beats `ratio-froth` (full 62.21% CAGR / 36.65% DD / 1.43 Sharpe).

**Added:** 20 strategies, 11 above the TQQQ bar. Full-window metrics are
2016-01-04..2026-10-23 daily-close; the one-shot 2024-2026 holdout is included.

| # | Family | Full CAGR | Full DD | Full Sharpe | Fills | Winner |
|---:|---|---:|---:|---:|---:|:--:|
| 1 | `tail-hedge-overlay` | 66.38% | 38.20% | 1.37 | 5,325 | yes |
| 2 | `close-location` | **66.23%** | 62.76% | 1.26 | 653 | yes |
| 3 | `policy-liquidity` | 56.13% | 75.23% | 1.08 | 439 | yes |
| 4 | `autocorrelation-regime` | 48.29% | 64.23% | 1.00 | 793 | yes |
| 5 | `vol-of-volume` | 45.56% | 70.00% | 1.09 | 1,921 | yes |
| 6 | `change-point` | 45.29% | 54.10% | 1.13 | 229 | yes |
| 7 | `hurst-persistence` | 43.00% | 56.25% | 1.04 | 437 | yes |
| 8 | `weekday-seasonality` | 42.84% | 72.17% | 0.90 | 1,134 | yes |
| 9 | `tqqq-decay` | 40.00% | 37.60% | 1.09 | 329 | yes |
| 10 | `realized-skew` | 38.83% | 53.98% | 0.97 | 439 | yes |
| 11 | `beta-rotation` | 37.70% | 59.60% | 1.03 | 225 | yes |
| 12 | `kelly-sizing` | 35.86% | 56.90% | 0.90 | 979 | no |
| 13 | `day-of-month` | 35.29% | 59.80% | 0.90 | 1,360 | no |
| 14 | `monthly-seasonality` | 34.46% | 72.12% | 0.81 | 387 | no |
| 15 | `volume-clock` | 29.65% | 26.69% | 1.24 | 1,614 | no |
| 16 | `range-compression` | 16.55% | 67.90% | 0.60 | 973 | no |
| 17 | `dynamic-risk-parity` | 26.21% | 50.60% | 0.89 | 319 | no |
| 18 | `quarter-end-flow` | 25.50% | 52.00% | 0.83 | 1,333 | no |
| 19 | `cpi-nfp-release` | 9.97% | 25.10% | 0.68 | 521 | no |
| 20 | `gap-continuation` | 6.63% | 44.70% | 0.59 | 412 | no |

## The ratio-froth beater

`family-close-location` beats `ratio-froth` on CAGR at 1, 5 and 10 bp:
**66.23% / 62.26% / 57.43%** vs **62.21% / 56.62% / 50.67%**. It is long-only
TQQQ and does not use a synthetic short. It does **not** beat ratio-froth on
drawdown or Sharpe; see `RATIO_FROTH_BEATER.md`.

`family-tail-hedge-overlay` also has a higher full CAGR (66.38% at 1 bp) but is
cost-fragile (40.42% at 10 bp) and uses a synthetic inverse sleeve. It is a
second, qualified result.

## Rejected / not added

- `family-lunch-reversal`: -6.96% dev CAGR; falsified.
- `family-power-hour-momentum`: 4.44% dev, below the 5% full-window floor.
- `family-vwap-reversion`: -19.08% dev; falsified.
- `family-lead-lag-spillover` was not added: the orthogonalized residual has
  t = -0.84 and the result is common-factor short-term reversal, not an
  independent family. It was replaced by `family-range-compression`.

All 20 active entries have at least 100 full-window fills; the minimum is 225.
