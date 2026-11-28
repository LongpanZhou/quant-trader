# Report: month-of-year seasonality on TQQQ

**Strategy:** `family-monthly-seasonality`
**Window:** development only, 2016-01-04 .. 2023-12-29, 1-minute marks, next-open
fills, 2% band, idle BIL.
**Bar:** TQQQ dev 36.72% CAGR / 82.29% max DD / 0.82 Sharpe (brief). The panel's
1 bp TQQQ buy-and-hold is 36.15% / 82.29% / 0.80.

## Verdict

**Passes the development bar and is the strongest of the four families.** The
centre earns **41.21% CAGR / 73.05% max DD / 0.89 Sharpe at 1 bp**, and still
earns **40.58% / 73.18% / 0.88 at 10 bp**. The cost drag is only 0.63 pp because
the strategy trades four times a year plus 2%-band rebalances (194x turnover,
309 fills). It survives ex-2020 (41.04% CAGR), September is the best of the
twelve single-month exclusions by a wide margin (41.34% vs 14.5-31.7%), and the
schedule shifted by one month in either direction falls to 27.4-29.4%.

The qualifier is important: the strategy **does not beat TQQQ in a typical
month**. Mean monthly excess is -0.11% (t = -0.19) and it wins only 33.3% of
months. It compounds faster because it avoids the 2022 bear market (strategy
-68.1% vs TQQQ -79.4%) and because the September exclusion removes four
consecutive bad Septembers (2020-2023). The 2016-2019 sub-period lags TQQQ
(39.8% vs 49.7%). This is a **seasonal risk-reduction tilt**, not a monthly
alpha.

## 1. What the strategy does

For each session, the target TQQQ weight is set by the calendar month:

```
Nov, Dec, Jan, Feb, Mar, Apr : 100% TQQQ
May, Jun, Jul, Aug, Oct      :  70% TQQQ + 30% BIL
September                    :   0% TQQQ + 100% BIL
```

- The month is known at the prior close. The target for the first session of a
  new month is set at the previous month's last close and filled at the next
  open. The harness's next-open rule is used unchanged.
- Idle is BIL. The cash-idle variant earns 40.83% at 1 bp, 0.38 pp less; BIL is
  the better idle asset because the strategy trades so rarely.
- No trend SMA, no realised vol, no drawdown state, no cross-sectional signal,
  no full-sample normalisation.

The rule is one seasonal schedule, not a search over twelve independent
monthly strategies. The September flat is the core claim; the 70% summer weight
is the 30% risk-reduction implementation of the same seasonal prior. The
single-month exclusions and shifted schedules in §4 are the placebos.

## 2. Headline development result

| cost | CAGR | max DD | Sharpe | Sortino | vol | ending equity |
|---:|---:|---:|---:|---:|---:|---:|
| 1 bp | **41.21%** | **73.05%** | **0.89** | 1.25 | 58.3% | $1.573m |
| 5 bp | 40.94% | 73.11% | 0.89 | 1.24 | 58.3% | $1.549m |
| 10 bp | 40.58% | 73.18% | 0.88 | 1.24 | 58.3% | $1.517m |
| TQQQ | 36.15% | 82.29% | 0.80 | 1.12 | 66.5% | $1.175m |

| cost | fills | turnover |
|---:|---:|---:|
| 1 bp | 309 | 194.1x |
| 5 bp | 309 | 192.1x |
| 10 bp | 307 | 189.0x |

Against the brief's 36.72% / 82.29% / 0.82 bar, the centre clears CAGR by
4.49 pp, cuts max DD by 9.24 pp, and lifts Sharpe by 0.07. The 10 bp result
still clears CAGR by 3.86 pp. The cost drag is small because turnover is only
194x starting equity over eight years.

**Exposure:** mean TQQQ weight **79.0%**, mean BIL weight **21.0%**. The
strategy is full-weight in **49.1%** of sessions (Nov-Apr), reduced to 70% in
**42.8%** (May-Oct ex-September), and out in **8.1%** (September). The harness
`exposure` field is 100% because BIL is an asset; the TQQQ weight is the
relevant number.

**Drawdown:** the max drawdown is the 2021-11-22 to 2022-12-28 bear market,
**-73.05%**, not 2020. This is still a high-risk TQQQ strategy; the DD
improvement over TQQQ is 9.2 pp, not a principal-protection story.

**Turnover / fills:** 194x, 309 fills. The 2% band produces some intra-month
rebalances because the 70% summer position drifts; the month-boundary trades
are only 32 events over eight years.

## 3. Pre-registered grid and plateau

The 8 cells were fixed in `HYPOTHESIS.md` before the final run. Every cell is
reported at 1 bp and 10 bp:

| # | summer weight | September | role | 1 bp CAGR | 1 bp DD | 1 bp Sharpe | 10 bp CAGR |
|---:|---:|---:|---|---:|---:|---:|---:|
| 1 | 60% | 0% | summer neighbour | 37.68% | 72.74% | 0.85 | 37.11% |
| 2 | 65% | 0% | summer neighbour | 39.52% | 72.74% | 0.87 | 38.92% |
| 3 | **70%** | **0%** | **centre** | **41.21%** | **73.05%** | **0.89** | **40.58%** |
| 4 | 75% | 0% | summer neighbour | 42.96% | 73.40% | 0.90 | 42.33% |
| 5 | 80% | 0% | summer neighbour | 44.55% | 73.70% | 0.92 | 43.92% |
| 6 | 85% | 0% | summer neighbour | 45.98% | 74.45% | 0.93 | 45.41% |
| 7 | 90% | 0% | summer neighbour | 47.48% | 75.29% | 0.94 | 46.99% |
| 8 | 70% | 25% | September partial | 38.17% | 74.97% | 0.85 | 37.65% |

All 8 cells clear the 36.72% CAGR bar at both 1 bp and 10 bp. The range is
37.11-46.99% at 10 bp; this is a plateau, not a spike. The centre is **not** the
highest-CAGR cell (the 90% summer cell is 46.99%); it was fixed at a round 30%
summer risk reduction before the final run. The September partial cell (25%
TQQQ in September) is 37.65% at 10 bp, still above the bar but 2.9 pp below the
flat-September centre, which confirms that the September exclusion is doing
real work.

The wider monthly diagnostics:

| month | TQQQ mean open-to-open | t | weight |
|---:|---:|---:|---:|
| Jan | +38.6 bp | 1.26 | 100% |
| Feb | +0.7 bp | 0.02 | 100% |
| Mar | +9.6 bp | 0.24 | 100% |
| Apr | +22.8 bp | 0.72 | 100% |
| May | +32.0 bp | 1.06 | 70% |
| Jun | +22.8 bp | 0.77 | 70% |
| Jul | +76.4 bp | 2.93 | 70% |
| Aug | +22.0 bp | 0.93 | 70% |
| **Sep** | **-40.3 bp** | **-1.32** | **0%** |
| Oct | +8.7 bp | 0.28 | 70% |
| Nov | +61.3 bp | 2.07 | 100% |
| Dec | -3.9 bp | -0.13 | 100% |

The classic November-April / May-October split is weak in this sample
(Nov-Apr +21.6 bp/day vs May-Oct +20.4 bp/day), which is why the pure
Sell-in-May control earns only 15.54% and fails. September is the standout.

## 4. Placebos and specificity

### 4.1 Single-month exclusions (deterministic)

Each row sets one month to zero and keeps the 70% summer schedule for the other
five summer months. The September row is the delivered schedule.

| off month | daily CAGR | | off month | daily CAGR |
|---|---:|---|---:|---:|
| Jan | 20.29% | | Jul | 15.25% |
| Feb | 31.65% | | Aug | 24.40% |
| Mar | 29.78% | | **Sep** | **41.34%** |
| Apr | 24.25% | | Oct | 27.51% |
| May | 23.07% | | Nov | 14.54% |
| Jun | 24.72% | | Dec | 31.39% |

September is the best single-month exclusion by **9.7 pp** over the next best
(February, 31.65%). This is the strongest specificity result in the family. A
random off-month would have to be September to match the centre.

### 4.2 Shifted schedule

| schedule | daily CAGR |
|---|---:|
| real (September off) | **41.34%** |
| shifted +1 month (October off) | 27.41% |
| shifted -1 month (August off) | 29.44% |

Both shifts lose 11.9-13.9 pp. The effect is tied to the September label, not to
a generic summer de-risk.

### 4.3 Random-month placebo

One random off month plus five random summer months, 1,000 draws:

| | CAGR |
|---|---:|
| real (daily approximation) | 41.34% |
| placebo mean | 31.39% |
| placebo p95 | 45.51% |
| placebo p99 | 51.60% |
| placebo max | 56.21% |
| p-value (draws >= real) | **0.123** |

This is the weak test. A random summer set can accidentally include a strong
month such as November, so the random-month distribution is wide; 12.3% of
random schedules beat the real one. The single-month and shifted-month tests
are the identified placebos; the random-month p is reported as a secondary
diagnostic, not a kill criterion.

## 5. Controls and decomposition

| variant | CAGR | max DD | Sharpe | mean TQQQ weight |
|---|---:|---:|---:|---:|
| TQQQ buy & hold | 36.15% | 82.29% | 0.80 | 100% |
| Nov-Apr only | 15.54% | 72.74% | 0.54 | 49.1% |
| September-off only | 50.35% | 76.68% | 0.96 | 91.9% |
| centre, cash idle | 40.83% | 73.14% | 0.88 | 79.0% |
| constant 79.0% TQQQ | 32.76% | 72.55% | 0.81 | 79.0% |
| **centre** | **41.21%** | **73.05%** | **0.89** | **79.0%** |

The constant-exposure control at the same mean weight earns 32.76% with a
72.55% DD. The seasonal schedule adds **+8.45 pp CAGR and -0.5 pp DD** over
constant exposure. That is the value of the timing, not merely the lower
average weight. The September-only version earns a higher CAGR (50.35%) but
holds 91.9% average TQQQ and has a 76.68% DD; it also has only 33 fills and 8
independent annual events, so it fails the activity floor. The 70% summer
weight is what makes the strategy a lower-risk product with enough monthly
decisions (32 events, 309 fills).

## 6. Sub-periods and yearly behaviour

| period | strategy CAGR | strategy DD | TQQQ CAGR | TQQQ DD |
|---|---:|---:|---:|---:|
| 2016-2019 | 39.83% | 53.50% | 49.67% | 56.77% |
| 2020-2023 | 40.63% | 72.12% | 24.11% | 81.57% |
| **ex-2020** | **41.04%** | **72.12%** | **28.35%** | 81.57% |

| year | strategy | TQQQ | difference |
|---:|---:|---:|---:|
| 2016 | +6.8% | +19.9% | -13.1 pp |
| 2017 | +101.9% | +114.5% | -12.7 pp |
| 2018 | -21.1% | -20.8% | -0.4 pp |
| 2019 | +126.3% | +148.2% | -21.9 pp |
| 2020 | +104.8% | +104.1% | +0.7 pp |
| 2021 | +89.1% | +81.1% | +8.0 pp |
| 2022 | -68.1% | -79.4% | +11.3 pp |
| 2023 | +231.3% | +192.0% | +39.3 pp |

The pattern is a risk-reduction profile: it lags in the smooth 2016-2017 bull,
roughly matches in 2018-2020, wins in 2021-2023, and cuts the 2022 loss by
11.3 pp. The 2016-2019 half is the weak half (39.8% vs 49.7%); the ex-2020
result is still 41.04%, 12.7 pp above the TQQQ ex-2020 bar.

## 7. Monthly behaviour

Over 96 months:

- mean strategy-minus-TQQQ excess: **-0.11%**, t = **-0.19**;
- median excess: 0.00%;
- win rate: **33.3%** (32 of 96 months);
- top 10 months contribute **62.6%** of the strategy's total log return; TQQQ's
  return over those same dates is 70.1% of TQQQ's total log. The strategy is
  **less** dependent on its best months than TQQQ, but still concentrated;
- best months: 2023-01 +32.6%, 2023-11 +33.5%, 2020-11 +33.8%, 2020-04
  +45.7%, 2023-03 +28.5%;
- worst months: 2020-03 -37.7%, 2022-04 -37.3%, 2018-12 -26.8%, 2022-12
  -26.5%, 2022-01 -25.5%.

The low win rate and zero mean excess are the honest core: the strategy does not
out-earn TQQQ in a typical month. It wins by losing less in the bad months and
by compounding through the 2022 drawdown. An allocator who needs monthly alpha
should not use it.

## 8. Correlations to the nine current winners

Daily-return Pearson correlation, development window only (2024+ never read):

| winner | correlation |
|---|---:|
| ratio-froth | 0.555 |
| vol-scaled-crash-stop | 0.724 |
| relative-value-tqqq | 0.826 |
| fomc-opex-window | 0.620 |
| family-session-timing | 0.679 |
| family-short-reversal | 0.857 |
| family-rebalance-flow | 0.800 |
| family-intraday-microstructure-day | 0.569 |
| family-ml-microstructure | 0.814 |

Range **0.555-0.857**, mean **0.716**. This is a TQQQ-beta strategy with a
seasonal tilt; it is not a diversifier. The lowest correlations are to
ratio-froth (0.555) and the intraday-microstructure day strategy (0.569), both
of which have different clocks and exposure profiles.

## 9. Causality and no look-ahead

- The month is known at the prior close; the target for the first session of a
  new month is set at the previous month's last close and filled at the next
  open.
- The 2015 data is not used; the first decision is 2016-01-04. No warmup
  indicator is needed.
- Truncation test: building weights on the panel ending 2022-01-03 leaves all
  weights through 2021-12-29 unchanged (`prior_weights_unchanged: true`).
- No 2024+ bar is loaded in `strategy.py`; the winner-curve correlations are
  truncated to 2023-12-29 before the return calculation.

## 10. Kill criteria and result

| criterion | result | pass? |
|---|---|---|
| 10 bp CAGR <= 36.72% or DD >= 82.29% | 40.58% / 73.18% | pass |
| ex-2020 CAGR <= 28.35% | 41.04% | pass |
| September not the best single-month exclusion | September 41.34% vs next 31.65% | pass |
| shifted +/-1 month beats the real schedule | 27.41% / 29.44% vs 41.34% | pass |
| 8-cell grid spike (60% and 80% both fail) | 37.11% / 43.92% at 10 bp | pass |
| 2020 contributes > 50% of total log | 2020 share ~26% | pass |

All six criteria pass; the verdict is **positive**. The random-month placebo
p = 0.123 is the one weak diagnostic and is disclosed as such.

## 11. Limitations

1. **No monthly alpha.** Mean excess is -0.11% (t = -0.19) and the win rate is
   33.3%. The CAGR edge is drawdown avoidance and compounding, not a steady
   premium. The strategy lags TQQQ in 2016, 2017 and 2019.
2. **September is a 2020-2023 effect.** September TQQQ returns were +5.4%,
   -1.3%, +1.2%, +5.1%, -17.7%, -17.0%, -27.3%, -17.2% in 2016-2023. The
   exclusion is profitable only in the last four years. The ex-2020 result
   (41.04%) is still strong, but the September-specific part of the edge is
   regime-dependent.
3. **The random-month placebo p = 0.123.** The single-month and shifted-month
   tests are strong, but the random schedule test is not. A reader who insists
   on a random-calendar placebo should treat the result as suggestive, not
   proven.
4. **70% summer weight is a choice.** The grid shows higher summer weights earn
   more (90% -> 47.48% at 1 bp) with only 2.2 pp more DD. The centre is a
   risk-budget choice, not the optimum. A more aggressive allocator could use
   80-90%.
5. **This is still TQQQ.** Correlation to TQQQ is high (the strategy is 79%
   TQQQ on average), and the 2022 loss is -68.1%. It is not a hedge.
6. **One cycle.** 96 months, 32 seasonal transitions. The result is a single
   bull/bear cycle; the 2020-2023 September run is four observations.

## 12. Final verdict

**The family passes the development bar and is a legitimate holdout candidate
as a seasonal risk-reduction tilt, not as a TQQQ replacement.** The deliverable
is:

- 41.21% CAGR / 73.05% DD / 0.89 Sharpe at 1 bp;
- 40.58% CAGR / 73.18% DD / 0.88 Sharpe at 10 bp;
- ex-2020 41.04%, 12.7 pp above the TQQQ ex-2020 bar;
- September is the best of twelve single-month exclusions by 9.7 pp;
- shifted schedules lose 11.9-13.9 pp;
- all 8 pre-registered cells pass at 1 bp and 10 bp;
- exact pre-cut weights (causality truncation test passes).

The honest one-line description: *a 79%-average TQQQ book that is full-weight
from November to April, 70% from May to October, and flat in September.* It is
a candidate for an allocator who wants TQQQ-like returns with a smaller
drawdown and can accept lagging the smooth bull years.
