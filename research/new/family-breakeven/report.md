# Breakeven inflation — report

**Dev:** 31.23% CAGR / 60.28% DD / 0.87 Sharpe.  
**Full:** 19.67% CAGR / 74.96% DD / 0.65 Sharpe; 557 full fills.  
**2024-2026 holdout:** -7.88% CAGR / 65.62% DD / 0.00 Sharpe.

## Rules

When inflation compensation is rising (TIP/IEF 10-session change in its top half), easier real rates support TQQQ; otherwise BIL.

## Why it is distinct

The primary object is TIP/IEF inflation compensation, not oil, energy or credit. It replaces the oil-shock family, which had 0.80 raw correlation. Maximum signal Jaccard against the nine existing winners is 0.48 and maximum raw correlation is 0.60.

## Caveats

- Full CAGR is below the TQQQ bar; this is an active research family, not a winner.
- The 2024-2026 holdout is reported exactly as run; it is not used to tune parameters.
- External daily series are committed under `data/external/`.
