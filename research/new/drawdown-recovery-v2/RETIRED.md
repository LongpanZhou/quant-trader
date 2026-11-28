# Retired from the visible library

**Date:** 2026-11-27.

`drawdown-recovery-v2` was removed from `LIBRARY.json`, `META.json` and the
website because its 2016-2026 record has only **35 fills / 18 entries** (27 dev
+ 8 holdout).  That is below the activity floor for a published family winner.

The low count is structural, not a fill-accounting bug: the strategy is binary
0/100 TQQQ, holds completed positions for an average of **126 sessions**, and
the 2% band never triggers a fractional rebalance.  The 35 fills are 18 buys +
17 sells; each moves the whole book.  The 80.7% “exposure” is time at 100%
TQQQ, not an 80% position size.

The source, curve and fill audit are retained unchanged:

- `strategy.py`, `result.json`, `holdout.json`, `report.md`
- `FILL_AUDIT.md` (35-row fill trace)
- `research/new/FILL_AGGREGATION_FIX.md` (runner fix example)
- `research/new/test_fill_aggregation.py` (regression case)

The regression test still uses this directory; do not delete it without
replacing that test case.  It is no longer a family winner or a visible
strategy.
