# Weekly close-location / participation state model - pre-registration

**Status:** primary frozen before the final 8-cell 1-minute run.
**Window:** 2016-01-04 .. 2023-12-29 only. Nothing on or after
2024-01-01 is loaded or inspected by `strategy.py`.
**Family:** statistical / ML microstructure, weekly state.

## Frozen primary

```
id            ridge5_ms_clv5_vol5_f25
features      clv5, volr5
label         y5 = entry(d+5) / entry(d) - 1
model         ridge, L2 = 30, expanding training, monthly refit
hurdle        0.25 * training_mean(y5)
sizing        base_vt = clip(0.45 / sigma20, 0, 1), sigma20 from entry
              returns through session d-1 (shifted one day)
decision      every 5 sessions, at the 15:58 signal bar
fill          next bar open (15:59)
hold          5 sessions
```

The primary is frozen from the cost-robust weekly screen. It is not a
post-hoc promotion: the grid below is centred on this cell, and no other cell
will be promoted after the final run.

## Hypothesis

The shape of the trading session carries information about the next few
sessions that survives the next open:

- **Close location (CLV)** = where the session closed inside its own range,
  `2*(C-L)/(H-L) - 1`, bounded in [-1, +1]. A close near the high is late
  buying / short covering; a close near the low is capitulation. At a
  one-to-five-session horizon TQQQ mean-reverts against the close location:
  weak closes are followed by better returns than strong closes.
- **Participation (volume ratio)** = log(volume / trailing 20-session mean
  volume). High participation confirms that the session's close location was
  an event, not noise. The model may learn an interaction; the frozen cell is
  linear in the two features.

A walk-forward ridge model estimates the next **5-session** TQQQ return from
5-day trailing means of these session-shape features. The 5-session horizon is
deliberate: a daily gate on the same signal turns over too much to survive
5-10 bp costs, while the weekly state is persistent and cost-robust. It is
still a short-horizon microstructure state, not a slow trend, volatility or
relative-strength regime.

The position is TQQQ when the predicted 5-session return is at least
`0.25 * training_mean`, scaled by a 45% volatility budget; the remainder is
BIL. The volatility target is risk control only.

## Rules (exact)

Data: adjusted 1-minute QQQ/TQQQ/BIL bars, regular session.

```
For session d:
  signal bar   = second-to-last 1-minute bar (15:58 on a normal day)
  entry bar    = last 1-minute bar (15:59)
  O,H,L,C,V    = session open, and high/low/close/volume through the signal bar
  CLV_d        = 2*(C-L)/(H-L) - 1
  VOLR_d       = log(V / mean(V_{d-20..d-1}))
  clv5_d       = mean(CLV_{d-4..d})            # 5-day trailing mean
  volr5_d      = mean(VOLR_{d-4..d})
  y5_d         = entry_{d+5} / entry_d - 1     # next 5-session return

Model (walk-forward, monthly refit):
  features     = [clv5, volr5]
  training set = block starts every 5 sessions, expanding window,
                 labels realised at least 9 calendar days before the test month
  standardise  = training mean/std only, clip +/-5
  estimator    = ridge, L2 = 30, target standardised by training mean/std

Allocation (set at the 15:58 close of a block start, filled at the 15:59 open):
  sigma20      = annualised stdev of the last 20 entry-to-entry TQQQ returns
                 through session d-1 (shifted one day, causal)
  base_vt      = clip(0.45 / sigma20, 0, 1)
  w            = base_vt * 1{predicted y5 >= 0.25 * training_mean}
  remainder    = BIL
  hold         = 5 sessions, rebalance at the next block start
```

Before the first model prediction (2016-07-01), the default weight is 1.0
TQQQ. This warm-up is disclosed and is not part of the claimed edge.

Fills are next-open: the weight at bar 15:58 is executed at the open of bar
15:59. The 2% no-trade band and all slippage are handled by `research/bt.py`.

## Pre-registered grid (8 cells)

All cells use L2 = 30, expanding training, 5-session blocks, the same 45%
volatility budget, and the same `pred >= hurdle * training_mean` allocation.
The primary is cell 1; the grid is centred on it. No cell will be promoted
after the final run.

| # | id | features | refit | hurdle |
|---:|---|---|---|---:|
| 1 | `clv5_vol5_m_f25` **FROZEN PRIMARY** | clv5, volr5 | monthly | 0.25 |
| 2 | `clv5_vol5_m_f50` | clv5, volr5 | monthly | 0.50 |
| 3 | `clv5_vol5_m_f75` | clv5, volr5 | monthly | 0.75 |
| 4 | `clv5_vol5_q_f25` | clv5, volr5 | quarterly | 0.25 |
| 5 | `clv5_m_f25` | clv5 | monthly | 0.25 |
| 6 | `clv5_m_f50` | clv5 | monthly | 0.50 |
| 7 | `volr5_m_f25` | volr5 | monthly | 0.25 |
| 8 | `clv5_vol5_last5_m_f25` | clv5, volr5, last30_5 | monthly | 0.25 |

The grid isolates the feature contribution (cells 5-7), the hurdle (1-3), the
refit frequency (4), and a third feature (8).

## Pass criteria

- Dev CAGR > 36.72% and max DD < 82.29% at 1 bp.
- Target: max DD < 60%.
- Report 1/5/10 bp for the primary. A cell that only passes at 1 bp is a fail
  for the programme's purposes.
- Report the whole grid, not just the best cell.

## Falsifiers

- The label-shuffle or feature-shuffle placebo matches the real CAGR/DD.
- Shifting the features by one block (5 sessions) leaves the result intact.
- The cut test changes pre-cut weights.
- The edge is one year (2022) or one crash episode.
- A simple fixed rule on `clv5` matches the ML.
- The 5 bp or 10 bp CAGR falls below 36.72%.
- Removing `volr5` (cell 5) or `clv5` (cell 7) leaves the result unchanged, in
  which case the two-feature claim is not supported.

## What this is not

- Not a trend, volatility-regime, relative-strength or drawdown-recovery
  strategy. The primary predictors are session close location and volume
  participation, both from intraday 1-minute bars. `rng` (intraday range) is
  deliberately excluded from the primary and the grid: an exploratory screen
  showed a range filter is a volatility proxy and carries most of the daily
  gate result, which would violate the family mandate. The 45% vol target is
  risk control only.
- Not market-neutral: correlation to TQQQ will be high.
- Not a claim that the ML is additive over a simple close-location or volume
  threshold; the report tests that directly.

## Exploratory disclosure

Before freezing this cell, the following were examined on the development
window and are reported in `report.md`: (i) next-session open-to-open
classifiers/regressions on the full session-shape feature set; (ii) depth-1/2
CART trees with and without `rng`; (iii) daily close-location and volume
gates with hysteresis; (iv) a 1-session-label weekly variant; (v) the weekly
ridge feature/hurdle/refit surface. None of those is part of the pass
evidence. The frozen cell was chosen because the daily gate was cost-fragile
and the weekly two-feature state was cost-robust, not because it maximised a
single dev statistic.
