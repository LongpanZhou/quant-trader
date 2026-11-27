# Report: leveraged-ETF rebalance flow on TQQQ

**Strategy:** `family-rebalance-flow`
**Window:** development only, 2016-01-04 .. 2023-12-29, 1-minute marks, next-open
fills, 2% band, idle BIL.
**Bar:** TQQQ dev 36.72% CAGR / 82.29% max DD / 0.82 Sharpe.

## Verdict

**Passes the development bar, with an important qualifier.** The centre earns
**50.71% CAGR / 53.87% max DD / 1.16 Sharpe at 1 bp**, and still earns
**42.88% / 56.91% / 1.04 at 10 bp**. It survives ex-2020 (40.96% CAGR), the
pre-registered 8-cell grid is a broad plateau (all 8 cells pass), and the real
strategy beats 98% of 300 random-date placebos (p = 0.02).

The qualifier: this is a **risk-managed TQQQ beta with a mechanical-flow
de-risk overlay**, not independent alpha. The strategy trails TQQQ badly in
2019 (-52 pp) and 2023 (-78 pp), its average monthly excess over TQQQ is
+0.07% with t = 0.08, and it wins only 43.8% of months. The CAGR edge comes
from avoiding the left tail and from the disclosed vol-target sizing, not from
a steady monthly premium. It is a candidate for a drawdown-averse allocator,
not a return-maximising replacement for TQQQ.

## 1. What the strategy does

A 3x daily ETF must keep 3x its NAV in index exposure. After an index move
`r`, required exposure changes by `9 * NAV * r`, so the fund is a forced buyer
at the close after up days and a forced seller after down days. That demand is
concentrated in the closing auction and is temporary. The strategy tries to
identify the days when the closing flow actually held the close up, and
de-risks TQQQ for the next session.

For each session `k`:

```
q_cc(k)  = QQQ close(k) / QQQ close(k-1) - 1
q_l30(k) = QQQ close(k) / QQQ price_at_15:30(k) - 1
sigma(k) = annualised stdev of the last 20 TQQQ daily log returns through k-1

flow(k) = q_cc(k) > 1.25% and q_l30(k) > 0

w_tqqq(k+1) = 0                              if flow(k)
            = min(1, 0.50 / sigma(k))       otherwise
w_bil(k+1)  = 1 - w_tqqq(k+1)
```

- Decision at the 16:00 close (15:59 bar), filled at the next open.
- The 50% vol target is a **disclosed sizing overlay**, not the claimed edge.
- `sigma` is warmed with 2015 TQQQ daily closes, so the rule is live on
  2016-01-04. No 2024+ bar is loaded.
- No trend SMA, no drawdown/vol regime as a signal, no relative strength, no
  cross-sectional ranking, no full-sample normalisation.

The last-30-minute confirmation is the flow filter. If the day is up but the
last 30 minutes fade, the close was not held up by mechanical buying; those
days do **not** reverse (next-session TQQQ +31.4 bp, t = 0.82, n = 109). If the
day is up and the last 30 minutes are also up, the next session is weak
(-56.0 bp, t = -1.50, n = 176), and the effect strengthens with a larger
confirmation (-92.9 bp, t = -1.96 at > +0.1%). That asymmetry is the core
evidence for a closing-flow interpretation rather than a generic reversal.

## 2. Headline development result

| cost | CAGR | max DD | Sharpe | Sortino | vol | ending equity |
|---:|---:|---:|---:|---:|---:|---:|
| 1 bp | **50.71%** | **53.87%** | **1.16** | 1.63 | 43.81% | $2.64m |
| 5 bp | 47.13% | 55.25% | 1.10 | 1.55 | 43.82% | $2.18m |
| 10 bp | 42.88% | 56.91% | 1.04 | 1.45 | 43.83% | $1.73m |
| TQQQ | 36.15% | 82.29% | 0.80 | 1.12 | 66.55% | $1.18m |

The brief's TQQQ bar is 36.72% / 82.29% / 0.82; the panel's buy-and-hold TQQQ
run is 36.15% because the harness starts at the first minute and pays 1 bp on
the initial buy. On either number the centre clears the CAGR bar by about
14 pp and cuts the max drawdown by 28.4 pp.

**Exposure:** mean TQQQ weight **78.0%**, mean BIL weight **22.0%**, out of the
market for **8.7%** of sessions, at the full vol-target cap on 49.9% of
sessions. The harness `exposure` field is 100% because BIL is an asset, not
cash; the TQQQ weight is the relevant number.

**Correlation to TQQQ daily returns: 0.872.** This is a beta strategy, not a
diversifier.

**Turnover:** 4,468x starting equity over the period, 1,520 fills. The flow
signal de-risks about 176 days in eight years (22/year); most of the fill
count is the daily vol-target rebalancing (and the two-asset BIL legs). At
10 bp the strategy still earns 42.88%, so the edge is not a 1 bp artefact, but
the cost drag is real (-7.8 pp from 1 bp to 10 bp).

## 3. Is the flow overlay doing anything beyond vol targeting?

This is the most important control. The vol target on its own, with no flow
signal, is already a respectable strategy:

| variant | CAGR | max DD | Sharpe | mean TQQQ weight |
|---|---:|---:|---:|---:|
| TQQQ buy & hold | 36.15% | 82.29% | 0.80 | 100% |
| 50% vol target only | 40.84% | 63.23% | 0.98 | 83.2% |
| flow only (0/1, no vol target) | 57.52% | 75.60% | 1.05 | 91.3% |
| **flow x 50% vol target (centre)** | **50.71%** | **53.87%** | **1.16** | **78.0%** |
| constant 78.0% TQQQ | 32.79% | 72.03% | 0.81 | 78.0% |

The flow overlay adds **+9.87 pp CAGR and -9.36 pp DD** over the vol-target-only
control. It also lifts the ex-2020 cut from 35.14% (vol-target-only, below the
bar) to 40.96%. The constant-exposure control at the same mean weight earns
only 32.79% with a 72.03% DD, so the timing is not merely a lower exposure.
The flow-only variant has a higher CAGR but a 75.60% DD and an ex-2020 of
36.73%, essentially exactly the bar; the vol target is what makes the result
investable. The combination is better than either component on a risk-adjusted
basis.

## 4. Pre-registered grid and plateau

The 8 cells were fixed in `HYPOTHESIS.md` before the final run. Every cell is
reported:

| # | vol target | q_cc threshold | last-30-min | role | CAGR | max DD | Sharpe |
|---:|---:|---:|---:|---|---:|---:|---:|
| 1 | 45% | 1.25% | > 0 | vol neighbour | 48.67% | 50.24% | 1.17 |
| 2 | 50% | 1.00% | > 0 | threshold neighbour | 47.64% | 49.43% | 1.12 |
| 3 | **50%** | **1.25%** | **> 0** | **centre** | **50.71%** | **53.87%** | **1.16** |
| 4 | 50% | 1.50% | > 0 | threshold neighbour | 47.86% | 59.75% | 1.11 |
| 5 | 55% | 1.25% | > 0 | vol neighbour | 52.99% | 57.72% | 1.16 |
| 6 | 60% | 1.25% | > 0 | vol neighbour | 54.43% | 61.13% | 1.15 |
| 7 | 50% | 1.25% | > +0.1% | confirmation neighbour | 54.85% | 55.83% | 1.21 |
| 8 | 50% | 1.25% | > +0.2% | confirmation neighbour | 51.09% | 56.31% | 1.15 |

All 8 cells clear 36.72% CAGR and 82.29% DD. The range is 47.64-54.85% CAGR
and 49.43-61.13% DD: a plateau, not a spike. The centre is not the
highest-CAGR cell (the +0.1% confirmation cell is 54.85%); it was fixed at
the natural zero line and a round 50% vol target rather than selected as the
best dev cell. That is the honest choice, and it means the headline is not the
product of picking the grid maximum.

The wider neighbour ladders are also broad:

| vol target | CAGR | max DD | | q_cc threshold | CAGR | max DD |
|---:|---:|---:|---|---:|---:|---:|
| 40% | 45.57% | 46.23% | | 0.75% | 42.15% | 47.36% |
| 45% | 48.67% | 50.24% | | 1.00% | 47.64% | 49.43% |
| 50% | 50.71% | 53.87% | | 1.25% | 50.71% | 53.87% |
| 55% | 52.99% | 57.72% | | 1.50% | 47.86% | 59.75% |
| 60% | 54.43% | 61.13% | | 2.00% | 47.53% | 60.51% |
| 70% | 55.40% | 67.08% | | 2.50% | 45.56% | 65.40% |
| 100% | 54.02% | 74.99% | | | | |

The last-30-minute confirmation ladder is 51.72% / 45.13% at -0.2%,
51.43% / 50.44% at -0.1%, 50.71% / 53.87% at 0, 54.85% / 55.83% at +0.1%,
51.09% / 56.31% at +0.2%. Every cell passes. The 40% vol-target and -0.2%
confirmation cells are lower-risk variants (DD 46% and 45%) at 45-52% CAGR.

## 5. Placebo

The placebo keeps the same 50% vol-target sizing and the same number of
de-risk days (176), but chooses the dates at random. 300 draws:

| | CAGR |
|---|---:|
| real strategy (1-min, 1 bp) | 50.71% |
| real strategy (daily approximation) | 51.57% |
| placebo mean | 37.17% |
| placebo p95 | 48.94% |
| placebo p99 | 56.11% |
| placebo max | 60.90% |
| p-value (draws >= real) | **0.02** |

The specific flow dates matter: the real strategy is above the 95th percentile
of random de-risk calendars. It is not above the 99th percentile, and 2% of
random draws beat it, so the placebo is supportive but not overwhelming. This
is a single dev window with 176 signal days, not a large-sample test.

## 6. Cut tests

All cuts are computed from the daily equity curve, excluding the stated
period, and compared with TQQQ over the same remaining days.

| cut | strategy CAGR | strategy DD | TQQQ CAGR | TQQQ DD |
|---|---:|---:|---:|---:|
| ex-2016 | 55.26% | 50.92% | 38.66% | 81.68% |
| ex-2018 | 59.13% | 50.92% | 46.60% | 81.68% |
| **ex-2020** | **40.96%** | 50.92% | 27.84% | 81.68% |
| ex-2022 | 74.89% | 38.12% | 77.75% | 69.89% |
| ex-2023 | 42.83% | 50.92% | 21.49% | 81.68% |
| drop best month (2018-01) | 46.68% | 50.92% | - | - |

The critical cut is **ex-2020: 40.96%**, which is still 4.2 pp above the
36.72% bar. The edge is not one crash. Removing 2022 leaves 74.89%, slightly
below TQQQ's 77.75% over the same remaining days but with a 38.12% DD versus
69.89%. Removing 2023 leaves 42.83%, still above the bar. Removing the single
best month (2018-01) leaves 46.68%.

The two halves are consistent: 2016-2019 earns 51.26% CAGR with a 38.96% DD;
2020-2023 earns 49.25% with a 53.87% DD. The max drawdown is the 2021-11-22 to
2022-10-13 bear market (-53.87%), not 2020.

## 7. Yearly and monthly behaviour

| year | strategy | TQQQ | difference |
|---:|---:|---:|---:|
| 2016 | +22.47% | +19.86% | +2.61 pp |
| 2017 | +114.85% | +114.54% | +0.31 pp |
| 2018 | +0.71% | -20.76% | +21.47 pp |
| 2019 | +96.13% | +148.23% | -52.10 pp |
| 2020 | +132.76% | +104.14% | +28.62 pp |
| 2021 | +83.08% | +81.05% | +2.03 pp |
| 2022 | -47.75% | -79.39% | +31.64 pp |
| 2023 | +113.72% | +192.05% | -78.33 pp |

The pattern is exactly what a risk-managed TQQQ should look like: it wins in
the two bad years (2018, 2022) and in 2020, roughly matches in 2016/2017/2021,
and gives up a lot in the smooth bull years 2019 and 2023. The 2022 loss is
still -47.75%; this is not a principal-protected product.

Monthly, over 96 months:

- mean strategy-minus-TQQQ excess: **+0.07%**, t = 0.08;
- median excess: 0.00%;
- win rate: **43.8%**;
- top 10 months contribute 26.2% of the strategy's total log return; TQQQ's
  return over those same dates is 50.7% of TQQQ's total log. The strategy is
  **less** dependent on its best months than TQQQ is;
- worst months: 2022-01 -24.0% (TQQQ -25.5%), 2018-10 -24.0% (-26.6%),
  2019-05 -23.5% (-24.1%), 2022-09 -18.2% (-30.5%), 2021-09 -16.9% (-16.9%).

The zero average monthly excess is the honest core of the result: the strategy
does not out-earn TQQQ in a typical month. It compounds faster because it
avoids the extreme left tail (2022-09 is the clearest example) and because the
vol target reduces drag. That is a risk-management result, not a monthly alpha.

## 8. Event study: what part of the reversal is actually captured?

For the 176 flow-confirmed events:

| window | mean TQQQ return | t |
|---|---:|---:|
| signal close -> next open (gap) | -47.15 bp | -1.66 |
| next open -> next close (intraday) | -39.79 bp | -1.35 |
| next close -> following open | -16.65 bp | -0.72 |
| skipped open-to-open (intraday + following overnight) | -56.04 bp | -1.50 |

This is the most important honesty check on the mechanism. The naive flow story
predicts a **close-to-open** reversal. The harness fills at the next open, so
the strategy cannot sell at the closing print: it holds through the -47 bp
gap, then sells at the next open. The implementable edge is the **post-open
continuation** (-56 bp, t = -1.50). The combined signal-close-to-following-open
move is about -103 bp, but only the post-open part is tradable. The gap itself
is not harvested. The result is still positive and cost-robust, but the report
should not claim that the strategy captures the closing-auction reversal
directly.

The confirmation asymmetry is consistent with the flow story: up days whose
last 30 minutes fade have a next-session return of **+31.4 bp** (t = 0.82),
while flow-confirmed up days have **-56.0 bp** (t = -1.50). The difference
between the two groups is about 87 bp. That is the cleanest evidence that the
signal is not just "the market went up".

## 9. Rejected alternatives (and why)

Two alternatives were tested and are not the delivered centre. They are
reported because they are the obvious ways to overfit this family.

### 9.1 Pure de-risk without the vol target

Dropping the vol target and holding 100% TQQQ except on flow days gives
**57.52% CAGR / 75.60% DD / 1.05 Sharpe** at 1 bp. It has a higher headline
CAGR but a much worse drawdown, and its ex-2020 CAGR is 36.73%, essentially
exactly the bar (versus 40.96% for the centre). It is a crash-avoidance bet,
not a robust flow strategy. The delivered centre keeps the vol target
precisely to avoid this.

### 9.2 Closing-sell-off bounce

The mirror trade — buy TQQQ after a last-30-minute QQQ sell-off — has a strong
conditional mean (+85.8 bp, t = 3.1, n = 366). As a standalone strategy it
earns **38.54% / 53.11% / 1.06** at 1 bp. But:

- it dies at 5 bp (31.08%) and 10 bp (22.32%);
- it is a threshold ridge: -0.15% gives 32.69%, -0.20% gives 38.54%, -0.25%
  gives 27.75%;
- its ex-2020 CAGR is 36.67%, essentially exactly the bar.

It was rejected as a 1 bp artefact. The delivered strategy uses the **up-day**
side of the same flow, where the de-risk is a smaller, more robust trade.

### 9.3 Month-end / quarter-end calendar

The brief allowed a hardcoded month-end/quarter-end calendar. It was not used:
the repo already has a passing `turn-of-month` calendar strategy (41.41% dev),
and a calendar variant of this family would duplicate that family rather than
test the daily leveraged-rebalance flow. The daily close-to-close signal is the
more direct proxy for the 9 x NAV x r rebalance demand.

## 10. Limitations

1. **The flow is inferred, not measured.** We do not observe TQQQ's AUM,
   swap notional, or the actual closing-auction trades. The signal is the
   index move and the closing-window move, which the rebalance formula maps
   to a flow. The mechanism is consistent with the data, not directly proven.
2. **The close-to-open reversal is not captured.** With next-open fills the
   strategy holds through the gap and harvests the post-open continuation.
   The event-study t-stat is -1.50, not the -3 or better that the raw
   close-to-open story would suggest.
3. **This is TQQQ beta.** Correlation 0.872, mean weight 78%, and a 43.8%
   monthly win rate. It is not a diversifier and not market-neutral.
4. **The vol target is a disclosed overlay.** The flow overlay is incremental
   (+9.87 pp CAGR, -9.36 pp DD over vol-target-only), but the vol target
   contributes a large part of the risk reduction. A reader who rejects vol
   targeting should look at the flow-only row (57.52% / 75.60%), which has a
   worse drawdown.
5. **The threshold is a pilot choice.** The plateau is broad (0.75-2.5% all
   pass), but the centre is not the grid maximum. The exact 1.25% and the
   zero last-30-minute line are natural choices, not uniquely identified.
6. **The sample is one bull/bear cycle.** 176 signal days, 96 months. The
   placebo p = 0.02 is supportive but the p99 draw is 56.11%, above the real
   51.57% daily approximation. A different cycle with different closing
   auction mechanics or different leveraged-ETF AUM could change the effect.
7. **2019 and 2023 are large opportunity costs.** The strategy gives up 52 pp
   and 78 pp versus TQQQ in those years. An allocator who cannot tolerate that
   tracking error should not use it.

## 11. Final verdict

**The family can beat the bar on this dev window, but not as independent
alpha.** The deliverable is a mechanical-flow de-risk overlay on a
vol-targeted TQQQ position:

- 50.71% CAGR / 53.87% DD / 1.16 Sharpe at 1 bp;
- 42.88% CAGR at 10 bp;
- ex-2020 40.96%, above the 36.72% bar;
- all 8 pre-registered cells pass, 47.64-54.85% CAGR;
- random-date placebo p = 0.02;
- exact pre-cut weights (causality truncation test passes).

It is a legitimate holdout candidate **if** the lead wants a lower-drawdown
TQQQ with a mechanical flow trigger and can accept large bull-year
underperformance. It is not a replacement for TQQQ in a return-maximising
book, and it should not be described as market-neutral, all-weather, or
independent alpha. The honest one-line description is: *a 50%-vol TQQQ
position that steps aside for one session after a large up day whose close was
held up by the closing flow.*
