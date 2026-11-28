# Trend/VIX regime switch

**Slug:** `family-regime-switch`  
**Family:** regime-switch (portfolio overlay, not one of the 20 independent
families)  
**Primary object:** QQQ 150-session trend and VIX level  
**Window:** 2016-01-04 .. 2023-12-29 development; full holdout
2024-01-02..2026-10-23.

## Claim

Use the aggressive close-location strategy when the market is calm, and the
defensive ratio-froth strategy when it is not:

- **Calm:** QQQ close is above its 150-session moving average **and** VIX ≤25.
- **Stress:** either condition fails; use ratio-froth's weights for that
  session.

The regime is measured at the prior session close, so execution is causal.
This is a portfolio overlay of two existing strategies, not a new independent
signal family. It exists to answer the specific requirement of beating
ratio-froth on both CAGR and drawdown.

## Rules

- Long-only TQQQ/BIL, weights ≥0, sum ≤1, 2% band, 1 bp headline.
- Calm sessions inherit close-location's minute weights.
- Stress sessions inherit ratio-froth's minute weights.
- No shorting, no leverage beyond TQQQ, no look-ahead.
- Stress share 22.5%; 106 regime switches over the full window.

## Falsifiers

- Full CAGR ≤62.21% or max drawdown ≥36.65%.
- Negative 2024-2026 holdout.
- No improvement at 5/10 bp costs.
