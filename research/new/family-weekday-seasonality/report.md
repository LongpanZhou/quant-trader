# Report: weekday seasonality — half-sized Friday de-risk

**Strategy:** `family-weekday-seasonality`
**Window:** development only, 2016-01-04 .. 2023-12-29, 1-minute marks, next-open
fills, 2% band, idle cash (BIL variant reported).
**Bar:** TQQQ dev 36.72% CAGR / 82.29% max DD / 0.82 Sharpe (brief). The panel's
1 bp TQQQ buy-and-hold is 36.15% / 82.29% / 0.80.

## Verdict

**Marginal pass.** The centre earns **43.46% CAGR / 72.63% max DD / 0.90 Sharpe
at 1 bp**, **40.58% / 73.23% / 0.87 at 5 bp**, and **37.06% / 73.97% / 0.83 at
10 bp**. It clears the brief's 36.72% CAGR bar at 10 bp by only **0.34 pp**, and
clears the panel TQQQ by 0.91 pp. The gross signal is strong and consistent
(ex-2020 43.28%, both halves beat TQQQ on a risk-adjusted basis), but the
weekly turnover is expensive: the full Friday de-risk earns 47.11% at 1 bp and
only 34.27% at 10 bp. The delivered 50% Friday de-risk is the cost-aware
midpoint, not the gross maximum.

This is a **real weekday effect with a cost problem**, not a robust
above-TQQQ winner. The 10 bp margin is inside the noise of a single dev window.
The report recommends the family as a candidate only with a low-cost execution
assumption (1-5 bp); at 10 bp it is essentially a tie with TQQQ.

## 1. What the strategy does

For each regular session:

```
w_tqqq(k) = 0.50   if weekday(k) == Friday
          = 1.00   otherwise
w_cash(k) = 1 - w_tqqq(k)
```

- The day of week is known at the prior close. The target for Friday is set at
  Thursday's 16:00 close (the 15:59 bar); the target for Monday is set at
  Friday's 16:00 close. Fills are at the next open. The harness's next-open
  rule is used unchanged.
- Idle is **cash** in the centre. BIL adds a second leg and roughly doubles the
  weekly turnover for a ~1.4%/yr yield on 10% of the book. The BIL-idle variant
  is a control (42.88% at 1 bp, 30.39% at 10 bp).
- No trend SMA, no realised vol, no drawdown state, no cross-sectional signal,
  no full-sample normalisation.

The rule is one weekday, not a search over five. The other four weekdays are
controls: the same 50% de-risk applied to Monday, Tuesday, Wednesday and
Thursday, plus the five weekday-only long strategies and Monday+Tuesday only.

## 2. Headline development result

| cost | CAGR | max DD | Sharpe | Sortino | vol | ending equity |
|---:|---:|---:|---:|---:|---:|---:|
| 1 bp | **43.46%** | **72.63%** | **0.90** | 1.28 | 60.7% | $1.784m |
| 5 bp | 40.58% | 73.23% | 0.87 | 1.23 | 60.7% | $1.517m |
| 10 bp | 37.06% | 73.97% | 0.83 | 1.17 | 60.7% | $1.239m |
| TQQQ | 36.15% | 82.29% | 0.80 | 1.12 | 66.5% | $1.175m |

| cost | fills | turnover |
|---:|---:|---:|
| 1 bp | 845 | 2,936.6x |
| 5 bp | 845 | 2,623.5x |
| 10 bp | 845 | 2,282.6x |

Against the brief's 36.72% / 82.29% / 0.82 bar, the centre clears CAGR by
6.74 pp at 1 bp, 3.86 pp at 5 bp, and only 0.34 pp at 10 bp. It cuts max DD by
9.66 pp at 1 bp and 8.32 pp at 10 bp. The Sharpe improves by 0.10 at 1 bp and
0.03 at 10 bp.

**Exposure:** mean TQQQ weight **90.0%**; 79.9% of sessions at 100%, 20.1% at
50%, none at zero. The harness `exposure` field is 90% because cash is not an
asset. The mean BIL weight is 0% in the centre.

**Drawdown:** the max drawdown is 2021-11-22 to 2023-01-05, **-72.63%**. The
strategy is still a high-risk TQQQ book; the DD improvement is 9.7 pp, not a
principal-protection story.

**Turnover / fills:** 2,937x, 845 fills. The strategy trades twice a week
(sell half at Friday open, buy half at Monday open) plus 2%-band rebalances.
It is the highest-turnover of the four families.

## 3. Pre-registered grid and the net-cost hump

The 8 cells were fixed in `HYPOTHESIS.md` before the final run. Every cell is
reported at 1 bp and 10 bp:

| # | Friday weight | role | 1 bp CAGR | 1 bp DD | 1 bp Sharpe | 10 bp CAGR | 10 bp DD |
|---:|---:|---|---:|---:|---:|---:|---:|
| 1 | 0% | full Friday de-risk (gross-max) | 47.11% | 61.41% | 0.95 | 34.27% | 64.85% |
| 2 | 20% | neighbour | 46.17% | 65.97% | 0.94 | 35.87% | 68.43% |
| 3 | 35% | neighbour | 44.97% | 69.28% | 0.92 | 36.60% | 71.13% |
| 4 | **50%** | **centre** | **43.46%** | **72.63%** | **0.90** | **37.06%** | **73.97%** |
| 5 | 65% | neighbour | 41.66% | 75.74% | 0.87 | 37.18% | 76.59% |
| 6 | 80% | neighbour | 39.59% | 78.64% | 0.85 | 37.05% | 79.07% |
| 7 | 90% | neighbour | 37.88% | 80.53% | 0.82 | 36.61% | 80.73% |
| 8 | 100% | TQQQ control | 36.15% | 82.29% | 0.80 | 36.14% | 82.29% |

The **gross** grid is monotonic: more Friday de-risk means more CAGR and less
DD. The **net-at-10 bp** grid is a hump: 34.27% at 0%, 35.87% at 20%, 36.60% at
35%, 37.06% at 50%, 37.18% at 65%, 37.05% at 80%, 36.61% at 90%, 36.14% at
100%. Only the 50-80% cells clear the 36.72% bar at 10 bp; the 0-35% and 90%
cells fall below. The centre is not the 10 bp maximum (65% is 0.12 pp higher);
it has the best drawdown among the cells that clear the bar.

This hump is the honest core of the result. The full de-risk is the strongest
signal and the weakest net trade; the half de-risk is the compromise.

## 4. Weekday diagnostics and controls

TQQQ open-to-open means by weekday, 2016-2023:

| weekday | n | mean | t | win rate |
|---|---:|---:|---:|---:|
| Monday | 373 | **+76.5 bp** | **3.68** | 0.61 |
| Tuesday | 413 | +19.9 bp | 1.11 | 0.55 |
| Wednesday | 413 | +2.0 bp | 0.09 | 0.51 |
| Thursday | 408 | +18.0 bp | 0.87 | 0.54 |
| Friday | 405 | **-6.7 bp** | **-0.30** | 0.53 |

The textbook "Monday weakness" is reversed in this sample: Monday is the
strongest session, Friday the weakest. The Monday effect is statistically
strong (t = 3.68); the Friday effect is not (t = -0.30), but Friday also has the
highest volatility (70.8% annualised vs 57-68% for the other days), so avoiding
it removes a lot of left-tail risk. The strategy is a **Friday de-risk**, not a
Monday-long.

Same 50% de-risk applied to each weekday:

| de-risk day | 1 bp CAGR | 1 bp DD | 1 bp Sharpe | 10 bp CAGR |
|---|---:|---:|---:|---:|
| Monday | 16.72% | 85.19% | 0.56 | 11.90% |
| Tuesday | 32.19% | 82.13% | 0.77 | 26.17% |
| Wednesday | 39.75% | 76.56% | 0.86 | 33.38% |
| Thursday | 33.74% | 79.17% | 0.79 | 27.71% |
| **Friday** | **43.46%** | **72.63%** | **0.90** | **37.06%** |

Friday is the best on CAGR, DD and Sharpe at both cost levels. Wednesday is
second (39.75% at 1 bp, 33.38% at 10 bp) but has a 76.56% DD and a 3.7 pp lower
10 bp CAGR. No other weekday beats Friday on both CAGR and DD, so the Friday
interpretation is identified (kill criterion 6 passes).

Weekday-only long strategies (100% TQQQ only on that day, cash otherwise):

| variant | CAGR | max DD | Sharpe |
|---|---:|---:|---:|
| Monday only | 36.36% | 40.62% | 1.25 |
| Tuesday only | 5.96% | 58.55% | 0.35 |
| Wednesday only | -4.83% | 66.59% | -0.01 |
| Thursday only | 3.81% | 45.99% | 0.28 |
| Friday only | -9.31% | 84.35% | -0.15 |
| Monday+Tuesday only | 45.83% | 48.42% | 1.15 |

Monday-only has the best risk-adjusted profile (36.36% CAGR, 40.62% DD, 1.25
Sharpe) but only 20% exposure and 2,683x turnover; at 10 bp it falls to 25.37%.
Monday+Tuesday is 45.83% at 1 bp but 32.75% at 10 bp. Both are cost-fragile and
are controls, not the centre. The 50% Friday de-risk keeps 90% average exposure
and is the most cost-robust weekday variant.

## 5. Placebo

The placebo keeps the 50% Friday weight and the same number of Friday days
(405) but chooses the dates at random. 1,000 draws, daily open-to-open
approximation:

| | CAGR |
|---|---:|
| real strategy (1-min, 1 bp) | 43.46% |
| real strategy (daily approximation) | 44.17% |
| placebo mean | 33.79% |
| placebo p95 | 44.71% |
| placebo p99 | 48.35% |
| placebo max | 55.22% |
| p-value (draws >= real) | **0.055** |

The real calendar is above the 95th percentile of random 405-day de-risk
calendars (p = 0.055). It is not above the 99th percentile; 5.5% of random
draws beat it. The placebo is supportive but not overwhelming. This is a single
dev window with 405 Friday events.

## 6. Sub-periods and yearly behaviour

| period | strategy CAGR | strategy DD | TQQQ CAGR | TQQQ DD |
|---|---:|---:|---:|---:|
| 2016-2019 | 46.36% | 52.41% | 49.67% | 56.77% |
| 2020-2023 | 38.67% | 72.17% | 24.11% | 81.57% |
| **ex-2020** | **43.28%** | **72.17%** | **28.35%** | 81.57% |

| year | strategy | TQQQ | difference |
|---:|---:|---:|---:|
| 2016 | +17.6% | +19.9% | -2.3 pp |
| 2017 | +90.1% | +114.5% | -24.4 pp |
| 2018 | -14.0% | -20.8% | +6.7 pp |
| 2019 | +140.3% | +148.2% | -7.9 pp |
| 2020 | +200.0% | +104.1% | +95.9 pp |
| 2021 | +68.1% | +81.1% | -13.0 pp |
| 2022 | -69.1% | -79.4% | +10.3 pp |
| 2023 | +147.9% | +192.0% | -44.2 pp |

The ex-2020 result (43.28%) is almost identical to the full 43.46%, so the edge
is not one year: 2020 was a huge absolute year (+200.0%) because the Friday
de-risk avoided the 2020 Friday crashes (-47.3% of Friday returns in 2020), but
the strategy compounds at the same rate outside it. The weak years are
the smooth bull years 2017 and 2023, exactly as a Friday risk-off should be.
The 2022 loss is still -69.1%; this is not a protected product.

## 7. Monthly behaviour

Over 96 months:

- mean strategy-minus-TQQQ excess: **+0.03%**, t = 0.06;
- median excess: **-0.49%**;
- win rate: **44.8%**;
- top 10 months contribute **56.4%** of total log return;
- best months: 2020-04 +38.5%, 2022-07 +36.5%, 2020-08 +30.9%, 2020-11
  +30.2%, 2023-11 +29.3%;
- worst months: 2022-04 -28.1%, 2022-06 -28.0%, 2022-12 -27.9%, 2018-10
  -27.5%, 2022-09 -27.0%.

The zero mean excess and 44.8% win rate are the honest core: the strategy does
not out-earn TQQQ in a typical month. It wins by losing less in the bad months
and by compounding through the 2022 drawdown.

## 8. Correlations to the nine current winners

Daily-return Pearson correlation, development window only:

| winner | correlation |
|---|---:|
| ratio-froth | 0.600 |
| vol-scaled-crash-stop | 0.772 |
| relative-value-tqqq | 0.873 |
| fomc-opex-window | 0.673 |
| family-session-timing | 0.711 |
| family-short-reversal | 0.863 |
| family-rebalance-flow | 0.850 |
| family-intraday-microstructure-day | 0.589 |
| family-ml-microstructure | 0.842 |

Range **0.589-0.873**, mean **0.753**. This is TQQQ beta with a weekday tilt,
not a diversifier. The lowest correlation is to the intraday-microstructure day
strategy (0.589) and ratio-froth (0.600).

## 9. Causality and no look-ahead

- The weekday is known at the prior close. The Friday target is set at
  Thursday's close; the Monday target at Friday's close. No same-day
  information is used.
- No warmup indicator is needed; the first decision is 2016-01-04.
- Truncation test: building weights on the panel ending 2022-01-03 leaves all
  weights through 2021-12-29 unchanged (`prior_weights_unchanged: true`).
- No 2024+ bar is loaded in `strategy.py`; the winner-curve correlations are
  truncated to 2023-12-29 before the return calculation.

## 10. Kill criteria and result

| criterion | result | pass? |
|---|---|---|
| 10 bp CAGR <= 36.72% or DD >= 82.29% | 37.06% / 73.97% | pass (thin) |
| 10 bp margin below 0.25 pp | +0.34 pp | pass (thin) |
| ex-2020 CAGR <= 28.35% | 43.28% | pass |
| placebo p > 0.10 | p = 0.055 | pass |
| grid spike (35% and 65% both fail at 10 bp) | 36.60% / 37.18% | pass |
| another weekday beats Friday on 10 bp CAGR and DD | none | pass |
| 2020 share > 50% of total log | ~38% | pass |

All seven criteria pass, but the first two are only barely. The verdict is
**positive with a cost-fragility warning**. The 10 bp result is a tie with TQQQ
within any reasonable error bar.

## 11. Limitations

1. **The 10 bp margin is 0.34 pp.** At 5 bp the margin is 3.86 pp; at 10 bp it
   is 0.34 pp. The strategy is a 1-5 bp idea, not a 10 bp idea. An allocator
   with 10 bp all-in costs should treat it as TQQQ with a lower drawdown, not
   as an above-TQQQ winner.
2. **The Friday mean is not statistically strong.** Friday TQQQ open-to-open is
   -6.7 bp (t = -0.30). The edge is mostly the removal of high-volatility
   Friday left tails, not a negative Friday drift. The placebo p = 0.055 and
   the gross grid are supportive, but this is not a t > 3 anomaly.
3. **The full de-risk is better gross and worse net.** Full Friday de-risk:
   47.11% at 1 bp, 34.27% at 10 bp. The 50% centre is a cost compromise. If the
   reader has a different cost model, the optimal Friday weight changes
   (65-80% at 10 bp).
4. **Monday-only looks better risk-adjusted at 1 bp** (36.36% / 40.62% / 1.25)
   but is 25.37% at 10 bp. The weekday effect is not uniquely a Friday effect in
   the gross data; Friday is the only weekday whose de-risk is cost-robust.
5. **2020 is a large positive year** (+200.0% vs TQQQ +104.1%). The Friday
   de-risk avoided the 2020 Friday crashes. Ex-2020 is still strong (43.28%),
   but the 2020 contribution is visible.
6. **One cycle.** 405 Friday events, 96 months. The result is a single
   bull/bear cycle.

## 12. Final verdict

**The family passes the development bar, but only as a low-cost weekday
overlay.** The deliverable is:

- 43.46% CAGR / 72.63% DD / 0.90 Sharpe at 1 bp;
- 40.58% CAGR / 73.23% DD / 0.87 Sharpe at 5 bp;
- 37.06% CAGR / 73.97% DD / 0.83 Sharpe at 10 bp;
- ex-2020 43.28%, both halves above TQQQ on a risk-adjusted basis;
- Friday is the best of the five same-de-risk weekdays on CAGR and DD;
- random-calendar placebo p = 0.055;
- exact pre-cut weights (causality truncation test passes).

The honest one-line description: *a TQQQ book that is fully invested Monday to
Thursday and half-invested on Friday, using cash rather than BIL to keep the
weekly turnover down.* It is a candidate for an allocator with 1-5 bp execution
costs who wants a smaller drawdown; at 10 bp it is a tie with TQQQ, not a
winner.
