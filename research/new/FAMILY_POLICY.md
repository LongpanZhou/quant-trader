# Family policy — final

The website lists every research strategy. The rule is about **above-TQQQ**
strategies: one verified winner per family. Non-performers remain research
records and do not affect the one-winner count.

## Verified above-TQQQ family winners (23)

| Family | Winner | Full CAGR | Full DD | Full Sharpe |
|---|---|---:|---:|---:|
| `trend-vol` | `ratio-froth` | 62.21% | 36.65% | 1.43 |
| `vol-crash` | `vol-scaled-crash-stop` | 51.32% | 37.88% | 1.26 |
| `relative` | `relative-value-tqqq` | 40.50% | 51.54% | 0.94 |
| `event-recovery` | — (no winner) | — | — | — |
| `calendar` | `fomc-opex-window` | 52.77% | 40.64% | 1.28 |
| `session-timing` | `family-session-timing` | 46.26% | 41.42% | 1.16 |
| `short-reversal` | `family-short-reversal` | 49.54% | 66.46% | 0.98 |
| `rebalance-flow` | `family-rebalance-flow` | 45.55% | 50.92% | 1.06 |
| `intraday-microstructure` | `family-intraday-microstructure-day` | 40.97% | 47.42% | 1.05 |
| `ml-microstructure` | `family-ml-microstructure` | 41.03% | 44.51% | 1.02 |
| `tail-hedge-overlay` | `family-tail-hedge-overlay` | 66.38% | 38.20% | 1.37 |
| `close-location` | `family-close-location` | 66.23% | 62.76% | 1.26 |
| `policy-liquidity` | `family-policy-liquidity` | 56.13% | 75.23% | 1.08 |
| `international-relative` | `family-international-relative` | 48.44% | 60.93% | 1.06 |
| `small-cap-relative` | `family-small-cap-relative` | 47.02% | 78.08% | 1.01 |
| `crypto-risk-appetite` | `family-crypto-risk-appetite` | 46.50% | 52.33% | 1.19 |
| `vol-of-volume` | `family-vol-of-volume` | 45.56% | 70.00% | 1.09 |
| `change-point` | `family-change-point` | 45.29% | 54.10% | 1.13 |
| `hurst-persistence` | `family-hurst-persistence` | 43.00% | 56.25% | 1.04 |
| `tqqq-decay` | `family-tqqq-decay` | 40.00% | 37.60% | 1.09 |
| `realized-skew` | `family-realized-skew` | 38.83% | 53.98% | 0.97 |
| `rates-volatility` | `family-rates-volatility` | 38.80% | 43.01% | 1.05 |
| `vix-term-structure` | `family-vix-term-structure` | 38.68% | 65.45% | 0.94 |
| `beta-rotation` | `family-beta-rotation` | 37.70% | 59.60% | 1.03 |

## Rules

1. An above-TQQQ winner must be `verified-full`: frozen dev result, one-shot
   2024-2026 holdout, and the causality/freshness/weight audit.
2. Within a family, the highest verified full-window CAGR is the winner; ties
   break on Sharpe, then lower drawdown.
3. Non-performers and dev-only studies remain research records; they do not
   affect the one-winner count.
4. The 20 new families are distinct primary signals. The ten overlap
   replacements are documented in `FAMILY_AUDIT.md`.
