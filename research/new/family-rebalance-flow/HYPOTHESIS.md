# Hypothesis: leveraged-ETF rebalance flow, QQQ closing-window de-risk

**Slug:** `family-rebalance-flow`
**Window:** development only, 2016-01-04 .. 2023-12-29, 1-minute marks.
**Bar:** TQQQ dev 36.72% CAGR / 82.29% max DD / 0.82 Sharpe.
**Status:** pre-registered before the final `strategy.py` run. No 2024+ bar is
loaded anywhere in this directory.

## 1. Claim

A 3x daily ETF must keep its swap/derivative exposure at 3x its net assets.
When the index moves by `r` during the day, net assets move by about `3r` and
the required notional exposure moves by

```
Delta exposure = 3 * Delta NAV = 3 * (3 * NAV * r) = 9 * NAV * r
```

so the fund must **buy** roughly `9 * NAV * r` of exposure at the close after
an up day, and sell the same size after a down day. The trade is concentrated
in the closing auction and is large relative to a normal day's volume. That
mechanical demand is price pressure, not information: it should reverse.

The claim is **directional and mechanical**, not a trend or volatility regime:

- after a large **up** day the fund is a forced buyer at the close; the close
  is pushed above fair value and the next session reverses;
- after a large **down** day the fund is a forced seller; the close is pushed
  below fair value and the next session bounces;
- the effect should be strongest when the closing window itself is in the
  direction of the flow, because that is when the rebalance is visible in the
  price. If the day is up but the last 30 minutes fade, the close was not
  held up by the flow and the next-day reversal should be absent.

This is a long-only implementation. We cannot short the reversal, and the
harness fills at the next open, so we cannot trade the closing print. What we
can do is **de-risk TQQQ for the session after a flow-confirmed up day**. The
mirror trade (buy after a closing sell-off) was tested and rejected; it is
reported in the report as a checked alternative, not the delivered strategy.

The rest of the time the strategy holds a volatility-targeted TQQQ position.
The vol target is a **disclosed sizing overlay**, not the claimed edge. A
decomposition against the vol-target-only and constant-exposure controls is in
the report.

## 2. Exact rules (centre)

Universe: QQQ (signal), TQQQ (position), BIL (idle).

For session `k` (a regular US session), let:

```
q_cc(k)  = QQQ close(k) / QQQ close(k-1) - 1          # total daily move
q_l30(k) = QQQ close(k) / QQQ price_at_15:30(k) - 1   # last 30 minutes
sigma(k) = annualised stdev of the last 20 completed TQQQ daily log returns
           through close(k)                           # 20-day realised vol
flow(k)  = (q_cc(k) > 0.0125) and (q_l30(k) > 0)
```

Target TQQQ weight for session `k+1`:

```
w_tqqq(k+1) = 0                                  if flow(k)
            = min(1, 0.50 / sigma(k))            otherwise
w_bil(k+1)  = 1 - w_tqqq(k+1)
```

- The decision is taken at the 16:00 close of session `k` (the 15:59 bar) and
  filled at the next open (09:30 of `k+1`). The harness's next-open rule is
  used unchanged.
- `price_at_15:30` is the close of the 15:29 bar. On half-days it is 30
  minutes before the closing bar, so the window is still 30 minutes.
- `sigma` is warmed with TQQQ daily adjusted closes from 2015-01-02 ..
  2015-12-31, so the strategy is live on 2016-01-04. The 2015 file is used
  only for the rolling vol; no 2024+ bar is loaded.
- Idle weight is BIL, not zero-return cash.
- The 2% rebalance band is the harness default. Headline cost is 1 bp; 5 bp
  and 10 bp are reported.
- No moving average, no drawdown state, no relative strength, no cross-
  sectional signal, no full-sample normalisation.

## 3. Pre-registered grid (8 cells)

The centre is **vol target 50%, q_cc threshold 1.25%, last-30-min > 0**. The
grid is a local neighbourhood around it, fixed before the final run:

| # | vol target | q_cc threshold | last-30-min confirm | role |
|---:|---:|---:|---:|---|
| 1 | 45% | 1.25% | > 0 | vol neighbour |
| 2 | 50% | 1.00% | > 0 | threshold neighbour |
| 3 | **50%** | **1.25%** | **> 0** | **centre** |
| 4 | 50% | 1.50% | > 0 | threshold neighbour |
| 5 | 55% | 1.25% | > 0 | vol neighbour |
| 6 | 60% | 1.25% | > 0 | vol neighbour |
| 7 | 50% | 1.25% | > +0.1% | confirmation neighbour |
| 8 | 50% | 1.25% | > +0.2% | confirmation neighbour |

No cell is selected on the holdout. Every cell is reported, including the
failures.

## 4. Pilot scan disclosure

A coarse scan of the dev window was run before fixing the grid. It covered:

- q_cc thresholds 0.5 .. 2.5%;
- vol targets 40 .. 100%;
- last-30-minute confirmations -0.2 .. +0.3%.

It showed a broad region rather than a single spike: thresholds 1.0 .. 1.5%
and vol targets 45 .. 60% all clear the bar at 1 bp, and the last-30-minute
confirmation adds value (the > +0.1% cell is the strongest; the fade group,
up days whose last 30 minutes are down, does not reverse). The centre was
fixed at the natural zero line and a round 50% vol target rather than at the
strongest pilot cell. The grid above is the local neighbourhood of that
choice. The pilot also produced two rejected ideas that the report must show:

1. **Pure de-risk without the vol target**: higher CAGR but 75% DD and a
   below-bar ex-2020. It is not the delivered centre.
2. **Closing-sell-off bounce** (buy TQQQ after a last-30-minute sell-off):
   strong conditional mean (+86 bp, t = 3.1) but a threshold ridge and a
   1 bp-only result; it does not survive 5/10 bp. It is not the delivered
   centre.

## 5. Falsification criteria

The hypothesis is rejected if any of the following holds on the dev window:

1. Centre CAGR <= 36.72% or max DD >= 82.29% at 1 bp.
2. Centre CAGR <= 36.72% at 10 bp (the effect is a 1 bp artefact).
3. The flow overlay does not improve both CAGR and DD over the vol-target-
   only control at the same vol target.
4. Ex-2020 centre CAGR <= 36.72% (the edge is one crash).
5. The random-date placebo beats the centre with p > 0.10.
6. The centre is a single spike: the immediate threshold neighbours (1.0%
   and 1.5%) and the immediate vol neighbours (45% and 55%) all fall below
   the bar.

Criterion 3 is the one that separates this from a plain vol-target strategy.
Criterion 4 is the one that separates it from the repo's existing
crash-avoidance family.

## 6. What would make this a real holdout candidate

The strategy is long TQQQ about 78% of the time by weight, with a 50%
vol budget, and goes to BIL for the session after a flow-confirmed up day
(about 9% of sessions). It should beat TQQQ in drawdowns and whipsaws and lag
it in smooth bull years (2019 and 2023 are the expected weak years). It is a
candidate for the one-shot holdout only if the lead wants a risk-managed TQQQ
with a mechanical flow overlay, not an independent market-neutral alpha.
