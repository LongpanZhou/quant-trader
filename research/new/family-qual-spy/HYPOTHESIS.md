# Quality factor leadership

**Slug:** `family-qual-spy`  
**Family:** qual-spy  
**Primary object:** QUAL/SPY 60-session leadership  
**Window:** 2016-01-04 .. 2023-12-29 development; full holdout 2024-01-02..2026-10-23.

## Claim

When the quality factor lags the broad market (QUAL/SPY 60-session change in its bottom half), risk appetite favours high-beta growth; buy TQQQ. Otherwise BIL.

## Rules

- Signal uses the external daily series through the prior session; it is lagged one session.
- Target is written at the session close and filled at the next QQQ/TQQQ open.
- Long-only TQQQ/BIL, weights >=0, sum <=1, 2% band, 1 bp headline.
- 252-session percentile rank with a 0.45/0.55 deadband.
- No price-trend, realised-vol, calendar, opening-range, ML or risk-sizing gate.

## Falsifiers

- Full CAGR <=5% or fewer than 100 full fills (or 30 events).
- Signal Jaccard >0.70 against an existing winner.
- Raw daily-return correlation >0.70 against an existing winner.

## Caveat

The primary object is the quality factor, not growth/value or low-vol. It is a distinct factor gate with low overlap to style-rotation.
