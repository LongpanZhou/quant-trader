# CPER/GLD growth-vs-defensive

**Slug:** `family-copper-gold`  
**Family:** copper-gold  
**Window:** 2016-01-04 .. 2023-12-29 development; full holdout 2024-01-02..2026-10-23.  

## Claim

When copper leads gold, growth/industrial demand supports TQQQ; when gold leads, hold BIL.

## Rules

- Signal uses the external daily series through the prior close.
- Target is written at the session close and filled at the next QQQ/TQQQ open.
- Long-only TQQQ/BIL, weights >=0, sum <=1, 2% band, 1 bp headline.
- No 100-250 day price trend gate, vol target, drawdown event, calendar clock, opening range/close flow, ML or relative-strength ratio gate.

## Falsifiers

- Dev CAGR <=5% or fewer than 100 full fills.
- No positive plateau/placebo.
- Correlation above 0.70 with an existing winner.
