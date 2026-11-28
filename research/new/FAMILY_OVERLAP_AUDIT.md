# Family overlap audit

| New | Max corr | Against | Max alpha/yr | Alpha t | Jaccard | Against |
|---|---:|---|---:|---:|---:|---|
| `family-gold-miner-stress` | 0.69 | `relative-value-tqqq` | +10.46% | 0.75 | 0.54 | `family-session-timing` |
| `family-energy-rotation` | 0.69 | `relative-value-tqqq` | +22.16% | 1.67 | 0.56 | `family-session-timing` |
| `family-breadth` | 0.68 | `family-short-reversal` | +14.66% | 1.39 | 0.28 | `family-short-reversal` |
| `family-yen-carry` | 0.68 | `family-rebalance-flow` | -8.79% | -0.76 | 0.58 | `family-session-timing` |
| `family-change-point` | 0.68 | `family-rebalance-flow` | +30.00% | 2.67 | 0.66 | `family-session-timing` |
| `family-mtum-spy` | 0.67 | `relative-value-tqqq` | +18.95% | 1.54 | 0.57 | `family-session-timing` |
| `family-sector-rotation` | 0.66 | `relative-value-tqqq` | +17.15% | 1.82 | 0.31 | `vol-scaled-crash-stop` |
| `family-crypto-risk-appetite` | 0.65 | `family-rebalance-flow` | +30.02% | 2.73 | 0.47 | `family-session-timing` |
| `family-rates-volatility` | 0.65 | `relative-value-tqqq` | +25.81% | 2.39 | 0.56 | `family-session-timing` |
| `family-sector-dispersion` | 0.64 | `family-rebalance-flow` | +8.87% | 0.84 | 0.55 | `family-rebalance-flow` |
| `family-homebuilder-rotation` | 0.64 | `relative-value-tqqq` | +13.04% | 1.14 | 0.49 | `family-session-timing` |
| `family-hyg-spy` | 0.63 | `family-rebalance-flow` | +11.76% | 1.04 | 0.54 | `family-session-timing` |
| `family-qual-spy` | 0.61 | `family-short-reversal` | +17.10% | 1.47 | 0.49 | `family-session-timing` |
| `family-financials-rotation` | 0.61 | `family-short-reversal` | +19.16% | 1.55 | 0.40 | `family-session-timing` |
| `family-breakeven` | 0.60 | `family-rebalance-flow` | +8.57% | 0.75 | 0.48 | `family-session-timing` |
| `family-skew-change` | 0.60 | `relative-value-tqqq` | +19.63% | 1.73 | 0.48 | `family-session-timing` |
| `family-efa-spy` | 0.60 | `family-short-reversal` | +17.89% | 1.58 | 0.44 | `family-session-timing` |
| `family-hurst-persistence` | 0.60 | `relative-value-tqqq` | +28.93% | 2.35 | 0.44 | `family-session-timing` |
| `family-retail-rotation` | 0.57 | `relative-value-tqqq` | +18.07% | 1.87 | 0.37 | `family-session-timing` |
| `family-volume-skew` | 0.51 | `family-rebalance-flow` | +27.00% | 2.64 | 0.41 | `family-rebalance-flow` |

## Conclusion

All 20 additions have session-level TQQQ Jaccard ≤ 0.66; the maximum is
`change-point` at 0.656. Every addition is also at or below 0.693 raw
correlation; the maximum is `gold-miner-stress` at 0.693, then
`energy-rotation` at 0.69. Close-location was moved out of the 20 into the
regime-switch overlay and replaced by gold-miner stress, so the 20 itself now
has no >0.70 exception. The beater is the separate composite overlay:
63.59% CAGR / 31.40% DD / 1.58 Sharpe versus ratio-froth 62.21% / 36.65% /
1.43. See OBJECTIVE_FEASIBILITY.md.

