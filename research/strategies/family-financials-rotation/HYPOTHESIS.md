# Financials rotation

**Slug:** `family-financials-rotation`  
**Family:** financials-rotation  
**Window:** 2016-01-04 .. 2023-12-29 development; full holdout 2024-2026.

## Claim

Hold TQQQ when financials (XLF) lead technology (XLK) over 60 sessions; otherwise BIL.

## Rules

Signal at the close; fill next QQQ/TQQQ open; long-only TQQQ/BIL, 2% band, 1 bp headline. No trend/vol/calendar/opening-range/ML gate.

## Falsifiers

- Dev CAGR <=5% or fewer than 100 full fills.
- No positive plateau.
- Jaccard overlap >0.70 with an existing winner.
