# SKEW tail-risk impulse — report

**Dev:** 43.88% CAGR / 54.33% DD / 1.08 Sharpe.  
**Full:** 32.20% CAGR / 54.33% DD / 0.90 Sharpe; 577 full fills.  
**2024-2026 holdout:** 4.00% CAGR / 42.79% DD / 0.29 Sharpe.

## Rules

When the 20-session change in CBOE SKEW is in its top half, tail-risk hedging demand is rising; buy TQQQ contrarian. Otherwise hold BIL.

## Why it is distinct

The gate is tail-risk pricing, not realised volatility. It can buy into fear peaks that a volatility filter would avoid. Maximum signal Jaccard against the nine existing winners is below 0.56 and maximum raw correlation is below 0.63.

## Caveats

- The full result is below the TQQQ CAGR bar; this is an active research family, not a winner.
- The 2024-2026 holdout is reported above exactly as run; it is not used to tune the parameters.
- External daily series are committed under `data/external/`.
