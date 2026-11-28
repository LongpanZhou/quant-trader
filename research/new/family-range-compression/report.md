# Range compression — report

**Slug:** `family-range-compression`  
**Development:** 2016-01-04 .. 2023-12-29, 1-minute marks, next-open fills, 2% band, 1 bp headline.  
**Full holdout:** 2024-01-02 .. 2026-10-23, run once after the dev freeze.

## Result

| Window | CAGR | Max DD | Sharpe | Fills |
|---|---:|---:|---:|---:|
| Dev | 18.03% | 68.82% | 0.65 | 719 |
| Holdout | 13.56% | 30.23% | 0.57 | 254 |
| Full | 16.55% | 68.82% | 0.62 | 973 |

The family is active and positive but below the TQQQ full-window CAGR bar. It
is a research record, not a family winner. The drawdown is high because the
strategy is 100% TQQQ for three-session bursts and holds BIL otherwise.

## Rules and clock

NR7 range compression at the 15:59 close; TQQQ at the next open; three-session
hold; BIL otherwise. No trend, vol, calendar, opening-range or ML input.

## Caveats

- The signal does not know the direction of the expansion; the long-only
  implementation buys TQQQ unconditionally.
- Full-window DD 68.82% is close to the TQQQ bar and well above the winner.
- Three-session bursts are cost-sensitive; the 1 bp result is the headline.
