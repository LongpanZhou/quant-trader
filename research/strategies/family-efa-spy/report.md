# Developed-market relative — report

**Dev:** 35.54% CAGR / 50.22% DD / 0.93 Sharpe.  
**Full:** 35.59% CAGR / 59.22% DD / 0.91 Sharpe; 165 full fills.  
**2024-2026 holdout:** 38.45% CAGR / 59.22% DD / 0.92 Sharpe.

## Rules

When developed markets lag the US (EFA/SPY 60-session change in its bottom half), US growth leadership supports TQQQ. Otherwise hold BIL.

## Why it is distinct

This is EFA/SPY, not the earlier EEM/QQQ variant: developed-market relative leadership, inverse direction, and a much lower correlation. Maximum signal Jaccard against the nine existing winners is below 0.56 and maximum raw correlation is below 0.63.

## Caveats

- The full result is below the TQQQ CAGR bar; this is an active research family, not a winner.
- The 2024-2026 holdout is reported above exactly as run; it is not used to tune the parameters.
- External daily series are committed under `data/external/`.
