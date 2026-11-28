# VIX term structure — pre-registration

**Family:** `vix-term-structure`  
**Directory:** `research/new/family-vix-term-structure/`  
**Development window:** 2016-01-04 .. 2023-12-29. No 2024-2026 row enters any
feature, result or robustness calculation. External series are truncated at the
development end before the features are computed.  
**Status:** development-only study. The lead runs the one-shot holdout.

## 1. Hypothesis

The implied-volatility curve is a direct price of near-term versus medium-term
uncertainty. When the curve is in **contango** (VIX below VIX3M), near-term
protection is cheap relative to three-month protection: the market is calm and
the marginal buyer of protection is not panicking. When the curve inverts
(VIX above VIX3M), near-term fear is elevated relative to the three-month
outlook: dealers are marking up crash insurance and the equity risk premium is
being repriced. A long TQQQ book should be held in the calm state and moved to
BIL when the curve inverts or when the ratio rises quickly enough to signal a
new stress impulse.

The claim is about the **shape of the index-option surface**, not about price
trend, realised volatility, drawdown, calendar dates, opening-range flow,
machine learning or relative strength. VIX and VIX3M are the only signal inputs.

## 2. Why this is a new family

The primary signal is the VIX/VIX3M ratio. The strategy does not use:

- a 100-250 day moving-average trend gate;
- volatility targeting / vol-of-vol scaling of a price series;
- a drawdown, capitulation or crash event;
- a calendar date window (FOMC, OpEx, turn-of-month, holidays);
- an opening-range, closing-flow or intraday-microstructure signal;
- an ML classifier;
- a QQQ/SPY or TQQQ/QQQ relative-strength gate.

The only price inputs are QQQ/TQQQ/BIL marks for execution. The decision
variable is the implied-vol term structure.

## 3. Exact definitions

For each external close date `t`:

```
vr_t   = VIX_t / VIX3M_t
d20_t  = vr_t - vr_{t-20}
```

`VIX` is the CBOE 30-day implied-volatility index and `VIX3M` the 3-month
index. The external files are Yahoo daily series; for an index the adjusted
close equals the close. Both series start 2015-01-02, so the first 2016
session has more than a full year of warm-up. The feature frame is truncated at
the development end before any feature is calculated. The ratio and its
20-session change are computed on the external calendar and then reindexed to
the QQQ session calendar with a forward fill; no QQQ bar is used to form the
signal.

## 4. State machine and exact rules

A three-condition hysteresis with a deadband:

```
if vr_t >= 1.05  or  d20_t >= +0.10   ->  risk-off  (100% BIL)
elif vr_t <= 0.95  and d20_t <= +0.05 ->  risk-on   (100% TQQQ)
else                                  ->  hold previous state
```

- The **1.05 upper level** is the inversion trigger. The 0.95 lower level is the
  re-entry trigger; the 0.95-1.05 band is the deadband. The state is not
  flipped by a ratio that merely crosses 1.00.
- The **+0.10 20-session change** is the stress-impulse trigger. A ratio that
  rises by 0.10 in a month is a repricing of near-term fear even if the curve
  has not inverted. Re-entry requires the 20-session change to have fallen back
  to +0.05 or less *and* the level to be at or below 0.95, so a bear-market
  rally that only partly normalises the curve does not immediately re-lever.
- An unavailable feature does not trade; the previous state is held.
- The initial state (before the first decision) is risk-on.

The decision is taken from the session's official external close and written
at that session's 15:59 bar; it fills at the next session's 09:30 open. No
intraday information is used. Idle capital is BIL, not cash.

## 5. Pre-registered parameter box

Centre: `lower = 0.95`, `upper = 1.05`, `chg_thr = 0.10`, 20-session change.

The 8-cell plateau is the 2 x 2 x 2 box:

| axis | low | high |
|---|---|---|
| lower level | 0.93 | 0.97 |
| upper level | 1.03 | 1.07 |
| 20-day change trigger | 0.08 | 0.12 |

Every cell must be reported. The centre is a round-number cell inside the box,
not the grid maximum.

## 6. Falsifiers / kill criteria (pre-registered)

The family is rejected if any of the following holds on the development window:

1. **Return:** 1 bp CAGR is below the TQQQ development bar of 36.72%, or the
   Sharpe is below 0.82, or max drawdown is worse than 82.29%.
2. **Activity:** fewer than 100 full fills and fewer than 30 independent state
   changes. A strategy that sits in one state is dead, not defensive.
3. **Plateau:** fewer than 6 of the 8 box cells clear the TQQQ CAGR bar, or the
   centre is the maximum of the box (a knife-edge selection).
4. **Placebo:** circular-shift placebo p-value above 0.10 on CAGR.
5. **Subperiod:** the 2022-2023 CAGR is below -25% while BIL is available; a
   crash filter that still loses a quarter a year in the bear market has not
   isolated the term-structure effect.
6. **Overlap:** correlation above 0.85 with any of the nine existing winners.
7. **Cost:** 10 bp CAGR below the TQQQ 1 bp bar (36.72%), i.e. the edge is
   entirely a zero-cost artefact.

These are stated before the headline run. A negative result is reported as a
negative result.
