# Family overlap audit

| New | Max corr | Against | Max alpha/yr | Alpha t | Jaccard | Against |
|---|---:|---|---:|---:|---:|---|
| `family-policy-liquidity` | 0.86 | `relative-value-tqqq` | +25.92% | 1.84 | 0.87 | `family-session-timing` |
| `family-vol-of-volume` | 0.84 | `relative-value-tqqq` | +21.74% | 1.94 | 0.59 | `family-session-timing` |
| `family-oil-shock` | 0.80 | `relative-value-tqqq` | +21.01% | 1.47 | 0.66 | `family-session-timing` |
| `family-lowvol-rotation` | 0.79 | `family-short-reversal` | -14.69% | -1.43 | 0.52 | `family-session-timing` |
| `family-close-location` | 0.77 | `family-short-reversal` | +37.82% | 2.80 | 0.47 | `family-short-reversal` |
| `family-beta-rotation` | 0.77 | `family-rebalance-flow` | +16.08% | 1.62 | 0.27 | `family-session-timing` |
| `family-credit-spread` | 0.76 | `family-rebalance-flow` | +17.78% | 1.35 | 0.73 | `family-session-timing` |
| `family-vix-term-structure` | 0.75 | `family-rebalance-flow` | +20.15% | 1.57 | 0.81 | `family-session-timing` |
| `family-realized-skew` | 0.74 | `relative-value-tqqq` | +22.15% | 1.77 | 0.56 | `family-session-timing` |
| `family-tqqq-decay` | 0.73 | `family-rebalance-flow` | +24.95% | 2.39 | 0.53 | `relative-value-tqqq` |
| `family-style-rotation` | 0.71 | `relative-value-tqqq` | +24.39% | 1.80 | 0.61 | `family-session-timing` |
| `family-energy-rotation` | 0.69 | `relative-value-tqqq` | +22.16% | 1.67 | 0.56 | `family-session-timing` |
| `family-breadth` | 0.68 | `family-short-reversal` | +14.66% | 1.39 | 0.28 | `family-short-reversal` |
| `family-yen-carry` | 0.68 | `family-rebalance-flow` | -8.79% | -0.76 | 0.58 | `family-session-timing` |
| `family-change-point` | 0.68 | `family-rebalance-flow` | +30.00% | 2.67 | 0.66 | `family-session-timing` |
| `family-sector-rotation` | 0.66 | `relative-value-tqqq` | +17.15% | 1.82 | 0.31 | `vol-scaled-crash-stop` |
| `family-crypto-risk-appetite` | 0.65 | `family-rebalance-flow` | +30.02% | 2.73 | 0.47 | `family-session-timing` |
| `family-rates-volatility` | 0.65 | `relative-value-tqqq` | +25.81% | 2.39 | 0.56 | `family-session-timing` |
| `family-hurst-persistence` | 0.60 | `relative-value-tqqq` | +28.93% | 2.35 | 0.44 | `family-session-timing` |
| `family-volume-skew` | 0.51 | `family-rebalance-flow` | +27.00% | 2.64 | 0.41 | `family-rebalance-flow` |


## Conclusion

Seventeen of 20 new families have session-level TQQQ overlap below 0.70.
Three (policy-liquidity, VIX term structure, credit spread) are above 0.70 and
are flagged as overlapping. The only strategy above ratio-froth's 62.21% CAGR
is close-location (66.23%); its signal Jaccard is 0.47 and residual alpha is
+37.8%/yr at t=2.80, but its raw return correlation is 0.77. No independent
strategy above 62.21% exists in the current data. See OBJECTIVE_FEASIBILITY.md.
