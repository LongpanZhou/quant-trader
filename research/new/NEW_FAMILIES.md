# New-family programme — final

**Target:** 20 strategies with primary signals distinct from the ten existing
families, plus one that beats `ratio-froth` (full 62.21% CAGR).

**Final set:** 20 new families. Thirteen clear the TQQQ full bar; seven are
active below it. The ten overlapping calendar/session/intraday/risk-sizing
names were replaced with cross-asset families built on `data/external/`.

| # | Family | Full CAGR | Full DD | Sharpe | Fills | Winner |
|---:|---|---:|---:|---:|---:|:--:|
| 1 | `tail-hedge-overlay` | 66.38% | 38.20% | 1.37 | 5,325 | yes |
| 2 | `close-location` | **66.23%** | 62.76% | 1.26 | 653 | yes |
| 3 | `policy-liquidity` | 56.13% | 75.23% | 1.08 | 439 | yes |
| 4 | `international-relative` | 48.44% | 60.93% | 1.06 | 359 | yes |
| 5 | `small-cap-relative` | 47.02% | 78.08% | 1.01 | 511 | yes |
| 6 | `crypto-risk-appetite` | 46.50% | 52.33% | 1.19 | 293 | yes |
| 7 | `vol-of-volume` | 45.56% | 70.00% | 1.09 | 1,921 | yes |
| 8 | `change-point` | 45.29% | 54.10% | 1.13 | 229 | yes |
| 9 | `hurst-persistence` | 43.00% | 56.25% | 1.04 | 437 | yes |
| 10 | `tqqq-decay` | 40.00% | 37.60% | 1.09 | 329 | yes |
| 11 | `realized-skew` | 38.83% | 53.98% | 0.97 | 439 | yes |
| 12 | `rates-volatility` | 38.80% | 43.01% | 1.05 | 355 | yes |
| 13 | `vix-term-structure` | 38.68% | 65.45% | 0.94 | 241 | yes |
| 14 | `beta-rotation` | 37.70% | 59.60% | 1.03 | 225 | yes |
| 15 | `energy-rotation` | 36.48% | 72.74% | 0.90 | 447 | no |
| 16 | `volume-skew` | 34.39% | 46.36% | 1.03 | 2,124 | no |
| 17 | `breadth` | 34.21% | 64.66% | 0.94 | 743 | no |
| 18 | `credit-spread` | 33.17% | 77.46% | 0.85 | 183 | no |
| 19 | `sector-rotation` | 29.86% | 48.79% | 0.94 | 719 | no |
| 20 | `copper-gold` | 28.60% | 73.53% | 0.76 | 347 | no |

## The ratio-froth beater

`family-close-location` beats `ratio-froth` on CAGR at 1, 5 and 10 bp:
**66.23% / 62.26% / 57.43%** vs **62.21% / 56.62% / 50.67%**. It is long-only
TQQQ and uses no synthetic short. It does not beat ratio-froth on drawdown or
Sharpe; see `RATIO_FROTH_BEATER.md`.

## Replaced overlaps

Removed because they reused an existing gate: `weekday-seasonality`,
`day-of-month`, `monthly-seasonality`, `cpi-nfp-release`, `quarter-end-flow`
(calendar); `kelly-sizing`, `dynamic-risk-parity` (risk sizing);
`volume-clock`, `range-compression`, `gap-continuation` (session/intraday/
short-reversal).

Replaced by external-data families: VIX term structure, credit spread, sector
rotation, breadth, crypto risk appetite, small-cap relative, international
relative, rates volatility, copper/gold, energy rotation.

`FAMILY_AUDIT.md` records the gate-by-gate audit. `lead-lag-spillover` and
`autocorrelation-regime` were also removed earlier for novelty failure.
