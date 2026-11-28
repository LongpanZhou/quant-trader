# Range compression -> expansion

**Slug:** `family-range-compression`  
**Family:** range-compression  
**Window:** 2016-01-04 .. 2023-12-29, development only. No 2024+ bar is loaded.

## Claim

A session whose QQQ range is the narrowest of the last seven sessions (NR7)
marks a coiled market. The next move is an expansion; hold TQQQ for three
sessions to capture the directional resolution. This is a range-compression
signal, not an opening-range breakout, VWAP rule, volume clock, or trend gate.

## Rules

1. At the 15:59 close compute the session range of QQQ 1-minute closes:
   `rng[d] = (high - low) / close`.
2. Signal if `rng[d] < min(rng[d-7 .. d-1])`.
3. Buy TQQQ at the next session's open; hold three sessions (rolling if a new
   signal arrives); otherwise hold BIL.
4. Long-only, weights >= 0, sum <= 1; next-open fills; 2% band; 1 bp headline.

## Falsifiers

- Dev CAGR <= 5%.
- Fewer than 100 full-window fills.
- No positive event forward return or no parameter plateau.
- Correlation > 0.70 with an existing family winner.
