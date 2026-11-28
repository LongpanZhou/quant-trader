# Hypothesis: month-of-year seasonality — full winter, reduced summer, flat September

**Slug:** `family-monthly-seasonality`
**Window:** development only, 2016-01-04 .. 2023-12-29, 1-minute marks.
**Bar:** TQQQ dev 36.72% CAGR / 82.29% max DD / 0.82 Sharpe (brief). The
panel's 1 bp TQQQ buy-and-hold is 36.29% / 81.57% / 0.80.
**Status:** pre-registered before the final `strategy.py` run. No 2024+ bar is
loaded anywhere in this directory.

## 1. Claim

The month of the year is an ex-ante clock with two well-documented equity
seasonals:

- the **Halloween / Sell-in-May effect**: returns are stronger from November
  through April than from May through October, because the summer period
  carries lower risk appetite, thinner liquidity and a higher realised
  volatility;
- the **September effect**: September is the weakest calendar month, on
  average, across long US equity samples. It follows the summer and precedes
  the fourth-quarter inflow season; it is also a heavy new-issue and
  tax-related month.

The claim is that a long-only TQQQ book should be **fully invested in
November-April, reduced by 30% in the May-October weak season, and flat in
September**. The September flat is the core of the claim; the summer reduction
is a risk-budget implementation of the same seasonal prior, not a separate
signal.

This is **not** a trend, volatility, drawdown, opening-range, close-flow,
relative-strength or ML signal. The only input is the calendar month. The
decision is known at the previous close.

## 2. Exact rules (centre)

Universe: QQQ (not used), TQQQ (position), BIL (idle).

For session `k` (a regular US session), target TQQQ weight:

```
w_tqqq(k) = 1.00   if month(k) in {Nov, Dec, Jan, Feb, Mar, Apr}
          = 0.70   if month(k) in {May, Jun, Jul, Aug, Oct}
          = 0.00   if month(k) == Sep
w_bil(k)  = 1 - w_tqqq(k)
```

- The month is known at the prior close. The target for the first session of a
  new month is set at the last close of the previous month and filled at the
  next open. The harness's next-open rule is used unchanged.
- Idle weight is BIL, not cash. The strategy trades only at month boundaries
  and on 2%-band rebalances, so the extra BIL leg is cheap; the cash version
  is reported as a control.
- The 2% rebalance band is the harness default. Headline cost is 1 bp; 5 bp
  and 10 bp are reported.
- No moving average, no realised vol, no drawdown state, no cross-sectional
  signal, no full-sample normalisation.

## 3. Pre-registered grid (8 cells)

The centre is **summer weight 70%, September weight 0%**. The grid is a local
neighbourhood around it, fixed before the final run:

| # | May-Oct weight | September weight | role |
|---:|---:|---:|---|
| 1 | 60% | 0% | summer neighbour |
| 2 | 65% | 0% | summer neighbour |
| 3 | **70%** | **0%** | **centre** |
| 4 | 75% | 0% | summer neighbour |
| 5 | 80% | 0% | summer neighbour |
| 6 | 85% | 0% | summer neighbour |
| 7 | 90% | 0% | summer neighbour |
| 8 | 70% | 25% | September partial |

Every cell is reported, including the failures. The centre is not the
highest-CAGR cell (the 90% summer cell is); it was fixed at a round 30% summer
risk reduction before the final run.

## 4. Pilot scan disclosure

A coarse scan of the dev window was run before fixing the grid. It covered:

- each calendar month's TQQQ open-to-open mean and t-stat;
- the classic November-April / May-October split;
- single-month exclusions (each month set to zero);
- summer weights 50-100%;
- cash vs BIL idle.

It showed that the classic **November-April** split is weak in this sample
(Nov-Apr mean +21.6 bp/day vs May-Oct +20.4 bp/day), so a pure Sell-in-May
strategy earns only 15.7% CAGR and fails the bar. The **September** month is
the standout: TQQQ mean -40.4 bp/day (t = -1.33), and the ex-September book
earns 50.6% before the summer reduction. The September effect is concentrated
in 2020-2023 (-17.7%, -17.0%, -27.3%, -17.2% monthly TQQQ returns), so the
report must show ex-2020 and the sub-periods. The 70% summer weight is the
30% risk-reduction centre, not the grid maximum. The pilot also produced two
rejected ideas reported in `report.md`:

1. **Pure Sell-in-May (Nov-Apr long, May-Oct flat)**: 15.7% daily-approximation
   CAGR, below the bar. The classic split is not strong enough here.
2. **September-off only with no summer reduction**: 50.4% at 1 bp but only 33
   fills and 8 independent annual events. It fails the activity floor and is
   not the delivered rule.

## 5. Falsification criteria

The hypothesis is rejected if any of the following holds on the dev window:

1. Centre 10 bp CAGR <= 36.72% or max DD >= 82.29%.
2. Ex-2020 centre CAGR <= 28.35% (TQQQ ex-2020).
3. September is not the best single-month exclusion: some other month set to
   zero produces a higher 1 bp CAGR than September-off.
4. The schedule shifted by one month in either direction beats the real
   schedule on 1 bp CAGR.
5. The 8-cell grid is a spike: the immediate summer neighbours (60% and 80%)
   both fall below 36.72% at 10 bp.
6. The entire edge is one year: 2020 contributes more than 50% of the total
   log return.

The random-month placebo (one random off month, five random summer months) is
reported as a secondary diagnostic, not a kill criterion. It is a weak test
because a random summer set can accidentally include a strong month such as
November; the shifted-month and single-month tests are the identified
placebos.

## 6. What would make this a real holdout candidate

The strategy is long TQQQ for two-thirds of the year at full weight, 70% in the
summer and flat in September. It should trail TQQQ in a smooth bull year
(2016-2019 is the expected weak half), beat it in the 2020-2023 volatility
regime, and cut the max drawdown by roughly 8-10 pp. It is a candidate for the
one-shot holdout only if the ex-2020 result stays above the TQQQ ex-2020 bar
and the September exclusion remains the best single-month exclusion. If the
edge is only the 2020-2023 Septembers, the honest verdict is "a real but
regime-dependent seasonal tilt," not a standalone replacement for TQQQ.
