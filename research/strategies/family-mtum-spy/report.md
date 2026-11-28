# Momentum factor leadership — report

**Dev:** 38.24% CAGR / 57.97% DD / 0.92 Sharpe.  
**Full:** 34.06% CAGR / 57.97% DD / 0.88 Sharpe; 179 full fills.  
**2024-2026 holdout:** 23.00% CAGR / 37.39% DD / 0.75 Sharpe.

## Rules

When the momentum factor leads the broad market (MTUM/SPY 60-session change in its top half), trend persistence supports TQQQ; otherwise BIL.

## Why it is distinct

The primary object is the momentum factor, not growth/value or quality. Correlation with style-rotation is 0.39 and Jaccard 0.36. Maximum signal Jaccard against the nine existing winners is 0.57 and maximum raw correlation is 0.67.

## Caveats

- Full CAGR is below the TQQQ bar; this is an active research family, not a winner.
- The 2024-2026 holdout is reported exactly as run; it is not used to tune parameters.
- External daily series are committed under `data/external/`.
