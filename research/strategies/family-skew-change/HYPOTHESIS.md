# SKEW tail-risk impulse

**Slug:** `family-skew-change`  
**Family:** skew-change  
**Primary object:** CBOE SKEW 20-session change  
**Window:** 2016-01-04 .. 2023-12-29 development; full holdout 2024-01-02..2026-10-23.

## Claim

When the 20-session change in CBOE SKEW is in its top half, tail-risk hedging demand is rising; buy TQQQ contrarian. Otherwise hold BIL.

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

The gate is tail-risk pricing, not realised volatility. It can buy into fear peaks that a volatility filter would avoid.
