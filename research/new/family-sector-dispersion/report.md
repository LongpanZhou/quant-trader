# Sector dispersion — report

**Dev:** 23.23% CAGR / 67.86% DD / 0.73 Sharpe.  
**Full:** 16.76% CAGR / 67.86% DD / 0.61 Sharpe; 273 full fills.  
**2024-2026 holdout:** 2.09% CAGR / 34.18% DD / 0.22 Sharpe.

## Rules

When sector dispersion is low, the market is moving on broad macro factors; buy TQQQ. When dispersion is high, hold BIL.

## Why it is distinct

The primary object is cross-sectional dispersion, not relative sector leadership. It is not a sector-rotation gate. Maximum signal Jaccard against the nine existing winners is 0.55 and maximum raw correlation is 0.64.

## Caveats

- Full CAGR is below the TQQQ bar; this is an active research family, not a winner.
- The 2024-2026 holdout is reported exactly as run; it is not used to tune parameters.
- External daily series are committed under `data/external/`.
