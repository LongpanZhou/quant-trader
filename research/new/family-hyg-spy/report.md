# Credit-equity risk appetite — report

**Dev:** 21.79% CAGR / 78.00% DD / 0.69 Sharpe.  
**Full:** 19.37% CAGR / 78.00% DD / 0.65 Sharpe; 383 full fills.  
**2024-2026 holdout:** 13.84% CAGR / 41.33% DD / 0.55 Sharpe.

## Rules

When high-yield credit leads equities (HYG/SPY 20-session change in its top half), credit risk appetite supports TQQQ. Otherwise BIL.

## Why it is distinct

This is credit versus equity, not the removed HYG/IEF credit-spread variant. It measures risk appetite, not duration-adjusted spreads. Maximum signal Jaccard against the nine existing winners is below 0.56 and maximum raw correlation is below 0.63.

## Caveats

- The full result is below the TQQQ CAGR bar; this is an active research family, not a winner.
- The 2024-2026 holdout is reported above exactly as run; it is not used to tune the parameters.
- External daily series are committed under `data/external/`.
