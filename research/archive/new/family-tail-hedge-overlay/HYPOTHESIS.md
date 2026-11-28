# Tail-hedge overlay — hypothesis

**Slug:** `family-tail-hedge-overlay`
**Window:** 2016-01-04 → 2023-12-29, development only. The 2024-2026 holdout
was never loaded, inspected or used.
**Target:** `ratio-froth` dev **61.56% CAGR / 39.11% max DD / 1.47 Sharpe**
(1-minute marks, 1 bp, 2016-01-04..2023-12-29).

> **Holdout note:** a `holdout.json` and `holdout_run.log` appeared in this
> directory from a separate process after the development run. This agent did
> not read, inspect or use them. Every number in this document and in
> `result.json` is development-only.

## Mechanism

A 100% TQQQ core carries a fat left tail: after a fast intraday drawdown, the
sell-off often continues into the close and the next open. A 50% synthetic
inverse TQQQ sleeve, opened only after a −2.0% TQQQ drawdown from the session
open, neutralises the core during that tail. The book re-enters TQQQ at the
next session's open, so it keeps the rebound.

This is a **tail-hedge / convexity overlay**, not a 100-250 day trend gate, not
volatility targeting, not a drawdown-recovery state machine, not a calendar
clock, not an opening-range/close-flow rule, not ML and not relative strength.
The hedge is the primary mechanism; the core is a constant 100% TQQQ.

## Exact rules

1. **Core:** 100% TQQQ at all times when not hedged.
2. **Trigger:** at any minute close of session *d*, if
   `TQQQ_close <= TQQQ_session_open * (1 - 0.020)`, that bar is the trigger.
   Use the first trigger of the session. The target written on the trigger bar
   fills at the **next minute's open**. The trigger uses only bars at or before
   the fill bar.
3. **Hedge:** from that fill, hold **50% TQQQ + 50% synthetic inverse TQQQ**
   for the rest of the session **and overnight**. The 15:59 target is 100%
   TQQQ, so the hedge is exited and the core is re-entered at the next
   session's open.
4. A trigger on the last bar (15:59) is ignored: there is no later bar in the
   session to fill before the overnight re-entry.
5. **No confirmation filter in the primary.** QQQ-underperformance, QQQ
   3-session-negative and QQQ-20-day-SMA filters are tested and rejected
   (section 7 of `report.md`).
6. Weights are long-only, ≥ 0, row sum ≤ 1. Next-open fills, 2% band, 1 bp
   headline, 5/10 bp reported.

## Synthetic inverse TQQQ

The local panel has no inverse ETF. The hedge asset is a **constant-notional
−1x TQQQ NAV** built from the same adjusted 1-minute bars:

```
inv_open[t]  = inv_close[t-1] * (1 - (TQQQ_open[t]  / TQQQ_close[t-1] - 1))
inv_close[t] = inv_open[t]    * (1 - (TQQQ_close[t] / TQQQ_open[t]  - 1)
                                   - cost_per_bar)
```

with `cost_yr = 1.5%/yr` net borrow + financing. The short rebate is ignored,
which is conservative. This is a **synthetic long-only sleeve**, not a real
short position: the portfolio never carries a negative weight. The backtest
holds it as a long asset and `research/bt.py` charges slippage on its traded
notional like any other asset. The result therefore assumes the synthetic can
be implemented as a constant-notional total-return swap or a continuously
rebalanced short. A daily-reset, no-intraday-rebalance variant and a −1x QQQ
variant are reported as robustness checks.

## Why it might work

- After the first −2% trigger, the rest-of-day TQQQ return is negative on
  average: **−0.181% across 740 episodes**, versus **−0.087% overnight**.
- A 50/50 TQQQ/inverse book is nearly flat during the hedge period (mean
  **−0.024%**) while 100% TQQQ loses **−0.280%**. The hedge does not need to
  make money on average; it needs to truncate the left tail. The geometric
  value of avoiding a −10% to −15% day is much larger than the cost of missing
  a +5% rebound.
- Re-entering at the next open is a real part of the result: exiting at 15:59
  (no overnight hedge) cuts CAGR from 90.84% to 69.29% and raises max DD from
  40.23% to 75.51%; conditioning the overnight hold on a weak close gives
  71.21% / 65.36%.
- The inverse's convexity is what turns a −15% TQQQ day into a roughly flat
  portfolio day; the log improvement on those days is what compounds.

## Primary and 8-cell grid

The 8-cell grid is **h ∈ {0.40, 0.50} × thr ∈ {−1.6%, −1.8%, −2.0%, −2.2%}**.
The primary is the round **h = 0.50, thr = −2.0%** cell, **not** the best cell
in the grid. The −1.8% cell is a strict dominance (79.55% / 37.68% / 1.56) but
is not the primary. The grid was fixed before the final run; it is not a blind
pre-registration, because the development window was used for exploration.

## Falsifiers / kill criteria

1. Primary 1 bp CAGR ≤ 61.56% → fail.
2. Primary max DD ≥ 50% → fail.
3. Hedge does not add CAGR versus the cash control → retire.
4. Hedge does not reduce DD versus the cash control → retire.
5. Fewer than 6 of the 8 grid cells above 61.56% CAGR → not a plateau.
6. Placebo p > 0.05 → weak signal.
7. 10 bp CAGR < 61.56% → cost-fragile; report it as such.
8. Pre-cut weight or synthetic-NAV diff > 0 → look-ahead.
9. Fewer than 100 full-window fills → dead/low-fill.

## What would make us retire it

- The inverse hedge's 1 bp CAGR is not above the cash control at the same
  trigger, or its DD is not lower.
- Random trigger dates with the same frequency and timing produce a similar
  CAGR.
- The 5/10 bp results collapse below ratio-froth's 1 bp bar.
- The tail concentration is extreme (top 10 > 80% of the log edge) and the
  sample has fewer than ~10 independent tail events. The current top-10 share
  is **63.4%**, which is high but not disqualifying; the report treats it as a
  major limitation, not as proof of a robust all-weather edge.
