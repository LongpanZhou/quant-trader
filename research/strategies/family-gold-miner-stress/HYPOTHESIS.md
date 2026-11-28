# Gold-miner stress

**Slug:** `family-gold-miner-stress`  
**Family:** gold-miner-stress  
**Primary object:** GDX/GLD 20-session relative  
**Window:** 2016-01-04 .. 2023-12-29 development; full holdout
2024-01-02..2026-10-23.

## Claim

When gold miners (GDX) lag bullion (GLD) over 20 sessions, defensive demand is
concentrated in the metal rather than in miner equities. That miner stress is
treated as a fear signal: buy TQQQ contrarian for the next session. Otherwise
hold BIL.

This is a precious-metals stress gate, not a sector rotation and not the
removed gold safe-haven family. The signal is the miner/metal ratio, not the
gold price.

## Rules

- 20-session change in log(GDX/GLD).
- 252-session percentile rank, shifted one session; bottom half -> TQQQ.
- Target at the session close, next QQQ/TQQQ open.
- Long-only TQQQ/BIL, 2% band, 1 bp headline.
- No price-trend, realised-vol, calendar, opening-range, ML or risk-sizing gate.

## Falsifiers

- Full CAGR <=5% or fewer than 100 full fills (or 30 events).
- Signal Jaccard >0.70 against an existing winner.
- Raw daily-return correlation >0.70 against an existing winner.

## Caveat

The full drawdown is 65.72%, so this is a high-risk research family, not a
winner. The contrarian direction is deliberate; the reverse direction returned
only 12.25% with an 88.69% (intraday) drawdown.
