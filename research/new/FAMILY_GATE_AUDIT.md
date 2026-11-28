# Family-gate audit

The test is residual alpha and signal overlap, not raw correlation alone. Raw
daily-return correlation between two long-TQQQ strategies is dominated by
common TQQQ beta; the gate question is whether the strategy adds return beyond
the existing winner.

## The overlay's aggressive sleeve: `family-close-location`

| Statistic | Value |
|---|---:|
| Beta to TQQQ | 0.592 |
| R² to TQQQ | 0.597 |
| Alpha after TQQQ beta | +31.91%/yr, t=3.25 |
| Residual correlation with `family-short-reversal` | **0.289** |
| Residual correlation with the other seven winners | −0.249 to 0.006 |
| Alpha after all eight winners jointly | **+24.79%/yr, t=2.54** |
| Signal Jaccard vs `family-short-reversal` | 0.47 |
| Raw correlation vs `family-short-reversal` | 0.773 |

Conditional daily returns:

| Condition | Days | Mean daily | Annualised |
|---|---:|---:|---:|
| `family-short-reversal` risk-on | 1,740 | +18.18 bp | +45.8% |
| `family-short-reversal` in BIL | 977 | **+38.22 bp** | **+96.3%** |
| `ratio-froth` risk-on | 1,408 | +58.73 bp | +148.0% |
| `ratio-froth` in BIL | 1,309 | −10.48 bp | −26.4% |

The strategy earns more than twice as much per day when short-reversal is
flat, which is direct evidence that its close-location-value gate is not a
short-reversal copy. Its returns do overlap with ratio-froth's risk-on days;
that is the remaining caveat, and it is why close-location is not claimed as a
zero-correlation strategy.

**Decision (2026-11-28):** close-location is no longer one of the 20
independent families. It is retained only as the aggressive sleeve of the
regime-switch overlay. The 0.77 raw correlation is treated as a TQQQ-beta
artifact; the overlay itself is the beater at 63.59% CAGR / 31.40% DD /
1.58 Sharpe.

## Seven replacements

| Removed | Corr | Replaced by | Corr | Jaccard |
|---|---:|---|---:|---:|
| `vol-of-volume` | 0.84 | `skew-change` | 0.60 | 0.48 |
| `oil-shock` | 0.80 | `efa-spy` | 0.60 | 0.44 |
| `lowvol-rotation` | 0.79 | `qual-spy` | 0.61 | 0.49 |
| `beta-rotation` | 0.77 | `hyg-spy` | 0.63 | 0.54 |
| `realized-skew` | 0.74 | `mtum-spy` | 0.67 | 0.57 |
| `tqqq-decay` | 0.73 | `breakeven` | 0.60 | 0.48 |
| `style-rotation` | 0.71 | `sector-dispersion` | 0.64 | 0.55 |

Every non-beater addition is now at or below 0.69 raw correlation and 0.66
signal Jaccard. No non-beater addition exceeds 0.70 raw correlation;
close-location is retained only inside the regime-switch overlay.

## Final 20 gates

Kept: gold-miner stress, volume-skew, change-point, Hurst persistence,
sector rotation, breadth, crypto risk appetite, rates volatility,
energy rotation, yen carry, homebuilder, financials, retail,
SKEW tail-risk, EFA/SPY, QUAL/SPY, HYG/SPY, MTUM/SPY, breakeven,
sector dispersion.

The final site set is 44 strategies / 46 curves / 14 winners. The additional
winner is `family-regime-switch`, a disclosed composite overlay, not one of
the 20 independent families. Its aggressive sleeve is the close-location
strategy, which is no longer one of the 20.
