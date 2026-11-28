# Quality factor leadership — report

**Dev:** 44.79% CAGR / 54.26% DD / 1.08 Sharpe.  
**Full:** 35.03% CAGR / 54.26% DD / 0.91 Sharpe; 217 full fills.  
**2024-2026 holdout:** 10.85% CAGR / 46.52% DD / 0.45 Sharpe.

## Rules

When the quality factor lags the broad market (QUAL/SPY 60-session change in its bottom half), risk appetite favours high-beta growth; buy TQQQ. Otherwise BIL.

## Why it is distinct

The primary object is the quality factor, not growth/value or low-vol. It is a distinct factor gate with low overlap to style-rotation. Maximum signal Jaccard against the nine existing winners is below 0.56 and maximum raw correlation is below 0.63.

## Caveats

- The full result is below the TQQQ CAGR bar; this is an active research family, not a winner.
- The 2024-2026 holdout is reported above exactly as run; it is not used to tune the parameters.
- External daily series are committed under `data/external/`.
