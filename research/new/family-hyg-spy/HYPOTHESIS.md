# Credit-equity risk appetite

**Slug:** `family-hyg-spy`  
**Family:** hyg-spy  
**Primary object:** HYG/SPY 20-session leadership  
**Window:** 2016-01-04 .. 2023-12-29 development; full holdout 2024-01-02..2026-10-23.

## Claim

When high-yield credit leads equities (HYG/SPY 20-session change in its top half), credit risk appetite supports TQQQ. Otherwise BIL.

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

This is credit versus equity, not the removed HYG/IEF credit-spread variant. It measures risk appetite, not duration-adjusted spreads.
