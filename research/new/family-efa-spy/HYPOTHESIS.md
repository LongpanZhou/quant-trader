# Developed-market relative

**Slug:** `family-efa-spy`  
**Family:** efa-spy  
**Primary object:** EFA/SPY 60-session leadership  
**Window:** 2016-01-04 .. 2023-12-29 development; full holdout 2024-01-02..2026-10-23.

## Claim

When developed markets lag the US (EFA/SPY 60-session change in its bottom half), US growth leadership supports TQQQ. Otherwise hold BIL.

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

This is EFA/SPY, not the earlier EEM/QQQ variant: developed-market relative leadership, inverse direction, and a much lower correlation.
