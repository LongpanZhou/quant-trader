# Family overlap audit

| New | Max corr | Against | Max alpha/yr | Alpha t | Jaccard | Against |
|---|---:|---|---:|---:|---:|---|
| `family-close-location` | 0.77 | `family-short-reversal` | +37.82% | 2.80 | 0.47 | `family-short-reversal` |
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
| `family-homebuilder-rotation` | 0.64 | `relative-value-tqqq` | +13.04% | 1.14 | 0.49 | `family-session-timing` |
| `family-hyg-spy` | 0.63 | `family-rebalance-flow` | +11.76% | 1.04 | 0.54 | `family-session-timing` |
| `family-qual-spy` | 0.61 | `family-short-reversal` | +17.10% | 1.47 | 0.49 | `family-session-timing` |
| `family-financials-rotation` | 0.61 | `family-short-reversal` | +19.16% | 1.55 | 0.40 | `family-session-timing` |
| `family-skew-change` | 0.60 | `relative-value-tqqq` | +19.63% | 1.73 | 0.48 | `family-session-timing` |
| `family-efa-spy` | 0.60 | `family-short-reversal` | +17.89% | 1.58 | 0.44 | `family-session-timing` |
| `family-hurst-persistence` | 0.60 | `relative-value-tqqq` | +28.93% | 2.35 | 0.44 | `family-session-timing` |
| `family-retail-rotation` | 0.57 | `relative-value-tqqq` | +18.07% | 1.87 | 0.37 | `family-session-timing` |
| `family-volume-skew` | 0.51 | `family-rebalance-flow` | +27.00% | 2.64 | 0.41 | `family-rebalance-flow` |

## Conclusion

All 20 additions have session-level TQQQ Jaccard ≤ 0.66; the maximum is
`change-point` at 0.656. The four highest raw-correlation names were
replaced: vol-of-volume (0.84), oil-shock (0.80), low-vol (0.79) and
beta-rotation (0.77) are now skew-change (0.60), EFA/SPY (0.60),
QUAL/SPY (0.61) and HYG/SPY (0.63). The remaining >0.70 names are
realized-skew (0.74), tqqq-decay (0.73), style-rotation (0.71) and
close-location (0.77); each has residual alpha t>=1.77 and Jaccard
<=0.61. Close-location is the only strategy above ratio-froth's 62.21%
CAGR (66.23%); its Jaccard is 0.47 and residual alpha is +37.8%/yr at
t=2.80. No strategy above 62.21% has lower raw correlation. See
OBJECTIVE_FEASIBILITY.md.

