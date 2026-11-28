# Family policy — final

The website lists every research strategy. The rule is about **above-TQQQ**
strategies: one verified winner per family. Non-performers remain research
records and do not affect the one-winner count.

## Verified above-TQQQ family winners (14)

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
| `close-location` | `family-close-location` | 66.23% | 62.76% | 1.26 |
| `crypto-risk-appetite` | `family-crypto-risk-appetite` | 46.50% | 52.33% | 1.19 |
| `change-point` | `family-change-point` | 45.29% | 54.10% | 1.13 |
| `hurst-persistence` | `family-hurst-persistence` | 43.00% | 56.25% | 1.04 |
| `rates-volatility` | `family-rates-volatility` | 38.80% | 43.01% | 1.05 |

## Rules

1. An above-TQQQ winner must be `verified-full`: frozen dev result, one-shot
   2024-2026 holdout, and the causality/freshness/weight audit.
2. Within a family, the highest verified full-window CAGR is the winner; ties
   break on Sharpe, then lower drawdown.
3. Non-performers and dev-only studies remain research records; they do not
   affect the one-winner count.
4. The 20 additions have signal Jaccard ≤0.66 against existing winners. The
   four highest raw-correlation names and the three remaining non-beater names
   above 0.70 were replaced on 2026-11-28. Every non-beater addition is now at
   or below 0.69 raw correlation. Close-location is the only ratio-froth
   beater; its raw correlation is 0.77, its Jaccard is 0.47, and its residual
   alpha is +37.8%/yr at t=2.80.
