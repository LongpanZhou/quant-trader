# Portfolio health audit

All library strategies except the eight under repair. Flags are diagnostics, not verdicts.

**Follow-up:** the eight excluded names are resolved in `REPAIRS.md` (four
full-holdout re-specifications, three retired, one development-only).  The only
visible low-fill winner, `drawdown-recovery-v2` (**27 dev / 35 full**), was
removed from the library because it is below the activity floor; see
`FAMILY_POLICY.md`.

| slug | family | dev CAGR | dev DD | Sharpe | fills | actual exposure | curve vol | flags |
|---|---|---:|---:|---:|---:|---:|---:|---|
| `drawdown-recovery-v2` | event-recovery | 57.63% | 43.39% | 1.25 | 27 dev / 35 full | — | 45.90% | removed (35 full fills) |
| `ensemble-signals` | vol-crash | -6.34% | 76.04% | -0.05 | 768 | — | 31.74% | negative-edge, weak-sharpe |
| `winner-ensemble-blend` | other | 0.30% | 32.67% | 0.08 | 773 | — | 10.76% | weak-sharpe |
| `daily-regime-minute-entry` | intraday-microstructure | 0.91% | 61.74% | 0.15 | 1309.0 | — | 20.12% | weak-sharpe |
| `opening-range-breakout` | intraday-microstructure | -2.10% | 17.22% | -0.53 | 2865 | — | 3.83% | negative-edge, weak-sharpe, tiny-vol |
| `ml-regime-v2` | vol-crash | 59.61% | 42.89% | 1.28 | 103 | — | 38.74% | ok |
| `cross-asset-momentum` | relative | 40.00% | 42.89% | 1.08 | 129 | — | 38.59% | ok |
| `crash-early-warning` | vol-crash | — | — | — | 135.0 | — | 46.80% | ok |
| `tqqq-52week-high` | trend-vol | 43.30% | 37.42% | 1.18 | 151 | — | 38.63% | ok |
| `ema-ribbon-trend` | trend-vol | 46.77% | 44.13% | 1.09 | 164 | 73.63% | 46.04% | ok |
| `donchian-trend` | trend-vol | 49.14% | 43.95% | 1.10 | 167 | — | 46.81% | ok |
| `relative-value-tqqq` | relative | 43.65% | 54.65% | 1.01 | 192 | — | 48.96% | ok |
| `momentum-crash-filter` | trend-vol | — | — | — | 217.0 | — | 47.98% | ok |
| `macro-event-tqqq` | calendar | 51.06% | 48.83% | 1.17 | 253 | 55.78% | 44.94% | ok |
| `ml-classifier` | ml-microstructure | 20.69% | 36.04% | 0.81 | 253 | — | 30.06% | ok |
| `ratio-pairs` | relative | 18.96% | 34.59% | 1.11 | 288 | — | 17.82% | ok |
| `pre-holiday` | calendar | 4.23% | 31.22% | 0.34 | 335 | 9.19% | 15.78% | ok |
| `intraday-mean-reversion` | short-reversal | 11.31% | 31.47% | 0.58 | 353 | — | 18.94% | ok |
| `dual-momentum-tqqq` | relative | 41.15% | 57.95% | 0.98 | 356 | — | — | ok |
| `fast-trend-vol` | trend-vol | 51.51% | 42.54% | 1.20 | 374 | — | 44.27% | ok |
| `turn-of-month` | calendar | 41.41% | 49.21% | 0.98 | 387 | — | 47.23% | ok |
| `intraday-momentum` | session-timing | 13.51% | 63.98% | 0.57 | 401.0 | — | 29.63% | ok |
| `vol-term-structure` | vol-crash | — | — | — | 409.0 | — | 36.75% | ok |
| `qqq-spy-relative` | relative | 44.36% | 55.03% | 1.06 | 452 | — | 44.69% | ok |
| `family-short-reversal` | short-reversal | 45.89% | 68.27% | 0.94 | 457 | 62.96% | 59.02% | ok |
| `ml-crash-overlay-winner` | ml-microstructure | 15.80% | 22.42% | 0.81 | 461 | — | 21.48% | ok |
| `intraday-close-momentum` | vol-crash | 46.21% | 53.87% | 1.08 | 590 | — | 46.67% | ok |
| `letf-rebalance-flow` | rebalance-flow | 13.20% | 41.80% | 0.52 | 601 | — | 32.64% | ok |
| `fomc-opex-window` | calendar | 58.26% | 42.60% | 1.36 | 617 | — | 39.21% | ok |
| `capitulation-reversal-v2` | event-recovery | 39.75% | 26.44% | 1.46 | 743 | 5.88% | 23.63% | ok |
| `overnight-drift-filter` | session-timing | 44.29% | 59.71% | 1.12 | 745 | — | 41.22% | ok |
| `risk-parity-hrp` | other | 5.70% | 18.46% | 0.65 | 767 | — | 9.80% | ok |
| `family-ml-microstructure` | ml-microstructure | 49.81% | 45.93% | 1.18 | 859 | — | 43.17% | ok |
| `event-risk-overlay` | calendar | 26.94% | 39.04% | 1.08 | 885 | — | 23.85% | ok |
| `ratio-froth` | trend-vol | 61.56% | 36.65% | 1.45 | 919.0 | — | 39.37% | ok |
| `spy-confirmed-trend` | trend-vol | — | — | — | — | — | — | ok |
| `tqqq-fast-drawdown-stop` | vol-crash | — | — | — | — | — | — | ok |
| `tqqq-vol-target-aggressive` | vol-crash | — | — | — | — | — | — | ok |
| `intraday-seasonality` | rebalance-flow | 21.84% | 43.75% | 0.75 | 1101.0 | 11.66% | 28.83% | ok |
| `orb-tqqq-volume` | intraday-microstructure | 17.89% | 21.38% | 1.02 | 1144 | — | 16.81% | ok |
| `donchian-breakout` | trend-vol | 13.40% | 15.02% | 1.00 | 1187 | — | 15.15% | ok |
| `time-of-day` | session-timing | 19.70% | 31.81% | 0.97 | 1223 | — | 20.15% | ok |
| `family-rebalance-flow` | rebalance-flow | 50.71% | 53.87% | 1.16 | 1520 | — | 45.50% | ok |
| `overnight-intraday-trend` | session-timing | 64.63% | 35.66% | 1.42 | 1837 | — | — | ok |
| `vol-of-vol-timing` | vol-crash | — | — | — | 1842.0 | — | 40.40% | ok |
| `always-long-vol-target` | vol-crash | — | — | — | 1931.0 | — | 44.10% | ok |
| `dual-speed-regime` | intraday-microstructure | 28.76% | 45.45% | 1.07 | 2735 | — | 20.54% | ok |
| `overnight-crash-filter` | session-timing | 10.37% | 27.62% | 0.76 | 3248 | — | 14.64% | ok |
| `family-intraday-microstructure-day` | intraday-microstructure | 44.12% | 46.72% | 1.13 | 3737 | — | 40.43% | ok |
| `vol-scaled-crash-stop` | vol-crash | 57.65% | 37.88% | 1.39 | 3950.0 | — | 38.77% | ok |
| `family-session-timing` | session-timing | 56.31% | 37.86% | 1.34 | 4048 | — | 39.46% | ok |
