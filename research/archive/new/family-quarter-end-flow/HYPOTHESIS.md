# Hypothesis: quarter-end rebalancing flow — the 2+2 session window

**Slug:** `family-quarter-end-flow`
**Window:** development only, 2016-01-04 .. 2023-12-29, 1-minute marks.
**Bar:** TQQQ dev 36.72% CAGR / 82.29% max DD / 0.82 Sharpe (brief). The
panel's 1 bp TQQQ buy-and-hold is 36.29% / 81.57% / 0.80.
**Status:** pre-registered before the final `strategy.py` run. No 2024+ bar is
loaded anywhere in this directory.

## 1. Claim

Calendar-quarter ends are a distinct rebalancing clock, different from the
month-end and turn-of-month clocks. Pension funds, target-date funds, insurers
and balanced mandates rebalance back to policy weights at quarter-end. The
flow is mechanical and concentrated in the last two sessions of the quarter
and the first two sessions of the new quarter:

- into quarter-end, the rebalancing demand is usually **buying** equities
  after a strong quarter (the equity share has drifted above target) or
  **selling** after a weak quarter; the sign is conditional on the quarter's
  return, but the unconditional window has historically been positive because
  the average quarter is positive and the window catches the inflow;
- at the start of the new quarter, the flow reverses and the first sessions
  can be weak.

The tested claim is deliberately **unconditional and long-only**: the 2+2
session window has a higher TQQQ open-to-open return than the rest of the
quarter. We do not use the quarter's return sign, because that would turn the
study into a momentum/flow-conditioning strategy and duplicate the trend
family. The strategy is a **positive-flow tilt**: a strategic 50% TQQQ book is
raised to 100% during the window. If the window is not special, the tilt will
not beat a constant-exposure control or a window shifted by one week.

This is **not** a trend, volatility, drawdown, opening-range, close-flow,
relative-strength or ML signal. The only input is the calendar quarter. The
decision is known at the previous close.

## 2. Exact rules (centre)

Universe: QQQ (not used), TQQQ (position), BIL (idle).

For each calendar quarter, the window is:

- the **last two regular sessions** of March, June, September and December;
- plus the **first two regular sessions** of January, April, July and October.

For session `k`:

```
w_tqqq(k) = 1.00   if k is in the 2+2 quarter-end window
          = 0.50   otherwise
w_bil(k)  = 1 - w_tqqq(k)
```

- The window is known from the calendar at the prior close. The target for the
  first window session is set at the previous close and filled at the next
  open; the exit target (0.50) is set at the last window session's close and
  filled at the next open. The harness's next-open rule is used unchanged.
- Idle weight is BIL, not cash.
- The 2% rebalance band is the harness default. Headline cost is 1 bp; 5 bp
  and 10 bp are reported.
- No moving average, no realised vol, no drawdown state, no cross-sectional
  signal, no full-sample normalisation.

## 3. Pre-registered grid (8 cells)

The centre is **base 50%, 2+2 window, full weight in the window**. The grid is
a local neighbourhood plus the required placebo, fixed before the final run:

| # | base weight | window | role |
|---:|---:|---|---|
| 1 | 30% | last 2 + first 2 | base neighbour |
| 2 | **50%** | **last 2 + first 2** | **centre** |
| 3 | 70% | last 2 + first 2 | base neighbour |
| 4 | 90% | last 2 + first 2 | base neighbour |
| 5 | 50% | last 2 only | window neighbour |
| 6 | 50% | first 2 only | window neighbour |
| 7 | 50% | last 2 + first 2, shifted +5 sessions | **placebo** |
| 8 | 0% | last 2 + first 2 | window-only |

Every cell is reported, including the failures. No cell is selected on the
holdout.

## 4. Pilot scan disclosure

A coarse scan of the dev window was run before fixing the grid. It covered:

- last N and first N sessions of the quarter for N = 1..7;
- the 2+2 window and its components;
- base weights 0-100%;
- a window shifted by +5 and -5 sessions;
- a conditional version that de-risks the first two sessions after an up
  quarter (pension selling).

It showed that the 2+2 window is **positive but weak**: last-2 mean +48.7 bp
(t = 1.19), first-2 mean +3.2 bp (t = 0.07), combined window about +26 bp over
four sessions. The window-only strategy earns only 4.3% CAGR and is below the
repo's 5% "dead" floor. The 50% base tilt is the smallest base that keeps the
strategy alive and still gives the window a meaningful 2x exposure step. The
shifted +5-session window is **better** than the real window (11.75% vs 4.29%
window-only; 30.07% vs 25.86% at base 50%), which is the central negative
result. The conditional pension-selling version de-risks the first two
sessions after an up quarter and earns 36.9% gross, but it is a momentum
condition, not the unconditional flow claim, and it is not the delivered
centre. The pilot also produced two rejected ideas reported in `report.md`:

1. **De-risk the last two sessions** (the pension-selling direction): 19.7%
   at 1 bp with an 85% DD. The data rejects the negative-flow direction.
2. **Window-only**: 4.29% CAGR, below the 5% floor. It is not a viable
   standalone.

## 5. Falsification criteria

The hypothesis is rejected if any of the following holds on the dev window:

1. Centre 10 bp CAGR <= 36.72% (the family is expected to fail this).
2. The shifted +5-session placebo beats the real window on 1 bp CAGR and
   Sharpe.
3. The window-only strategy earns less than 5% CAGR (it is effectively dead).
4. The 2+2 window's conditional mean is not positive (t < 1.0).
5. The real window's 1 bp CAGR is below the constant-exposure control at the
   same average TQQQ weight.
6. The window is a single-quarter artefact: removing the best quarter drops
   the centre below the constant-exposure control.

Criterion 2 is the decisive placebo. Criterion 3 is the activity/viability
test. If the shifted window is better, the "quarter-end flow" interpretation
is not identified and the family must be rejected even if the base-50%
strategy has a respectable Sharpe.

## 6. What would make this a real holdout candidate

The strategy is a 50/50 TQQQ/BIL book that doubles equity exposure for four
sessions around each quarter boundary. It should have a lower drawdown than
TQQQ (roughly 50-55% vs 82%) at a materially lower CAGR (roughly 25% vs 36%).
It is a candidate for the one-shot holdout only if the window tilt adds
something over a constant 56% TQQQ control *and* the shifted-window placebo is
worse. If the shifted window is better, the honest verdict is "quarter-end is
not a special clock; the result is a generic 50/50 risk profile."
