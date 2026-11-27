# Family policy — final

The website lists every research strategy. The strict rule is about
**above-TQQQ** strategies: only **one verified winner per family** is counted
in the above-TQQQ set. Non-performers may appear in the research archive in any
family.

## Verified above-TQQQ family winners

| Family | Winner | Full CAGR | Full DD | Full Sharpe |
|---|---|---:|---:|---:|
| `trend-vol` | `fast-trend-vol` | 44.61% | 40.26% | 1.06 |
| `vol-crash` | `vol-term-structure` | 42.48% | 35.80% | 1.15 |
| `relative` | `relative-value-tqqq` | 40.50% | 51.54% | 0.94 |
| `event-recovery` | `drawdown-recovery-v2` | 49.99% | 41.11% | 1.12 |
| `calendar` | `fomc-opex-window` | 52.77% | 40.64% | 1.28 |
| `session-timing` | `family-session-timing` | 46.26% | 41.42% | 1.16 |
| `short-reversal` | `family-short-reversal` | 49.54% | 66.46% | 0.98 |
| `rebalance-flow` | `family-rebalance-flow` | 45.55% | 50.92% | 1.06 |
| `intraday-microstructure` | `family-intraday-microstructure-day` | 40.97% | 47.42% | 1.05 |
| `ml-microstructure` | `family-ml-microstructure` | 41.03% | 44.51% | 1.02 |

## Legacy above-bar records, not family winners

`ratio-froth` (62.21% full) and `vol-scaled-crash-stop` (51.32% full) are above
the bar but have no frozen 2024-2026 holdout. They remain research records and
are not counted as family winners. The verified alternatives are
`fast-trend-vol` and `vol-term-structure`.

## Rules

1. An above-TQQQ winner must be `verified-full`: frozen dev result, one-shot
   2024-2026 holdout, and the causality/freshness/weight audit.
2. Within a family, the highest verified full-window CAGR is the winner; ties
   break on Sharpe, then lower drawdown.
3. Non-performers and dev-only studies are listed in the research archive; they
   do not affect the one-winner-per-family count.
4. The six new families are `calendar`, `session-timing`, `short-reversal`,
   `rebalance-flow`, `intraday-microstructure` and `ml-microstructure`. None
   shares a primary signal family with the four existing winners.
