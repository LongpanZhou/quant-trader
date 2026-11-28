# Crypto risk appetite — development report

**Verdict: dev pass.** The BTC 20/60-day risk-appetite switch earns **53.66%
CAGR / 52.33% max DD / 1.28 Sharpe** at 1 bp over 2016-2023. It beats the
published TQQQ CAGR bar (36.72%) at 1, 5 and 10 bp (53.66% / 52.12% / 50.21%),
has all three subperiods positive, and is strongly non-random (placebo 99th
percentile). It is the only one of the three families that clears every
pre-registered kill check. The caveats are real: 2022 is -42.4%, 2023 alone is
+310.4%, and the 60-day-only variant is weak. 2024-2026 is untouched.

## Development metrics

| Cost | CAGR | Max DD | Sharpe | Sortino | Vol | Exposure | Fills | Turnover |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 bp | 53.66% | 52.33% | 1.28 | 1.85 | 39.9% | 100.0% | 201 | 1,152x |
| 5 bp | 52.12% | 52.94% | 1.25 | 1.82 | 39.9% | 100.0% | 201 | 1,088x |
| 10 bp | 50.21% | 53.68% | 1.22 | 1.77 | 39.9% | 100.0% | 201 | 1,013x |

There are **201 fills across 101 independent fill days** (about 25 fills and
13 events per year). This is just above the 100-fill / 30-event floor; the
strategy is a low-activity regime switch, not a high-turnover system. Average
weights are **8.9% QQQ (warm-up only), 47.7% TQQQ, 43.3% BIL**.

The cost drag is only 3.45 pp from 1 bp to 10 bp because the state changes are
infrequent and the book is binary. The result is not cost-fragile.

## Subperiods and years

| Window | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| 2016-2019 | 32.78% | 30.62% | 1.20 |
| 2020-2021 | 107.81% | 30.46% | 1.69 |
| 2022-2023 | 52.58% | 52.02% | 1.09 |

| Year | Return |
|---|---:|
| 2016 | +4.0% |
| 2017 | +96.1% |
| 2018 | +15.9% |
| 2019 | +21.5% |
| 2020 | +173.3% |
| 2021 | +64.3% |
| 2022 | -42.4% |
| 2023 | +310.4% |

All three subperiods are positive, but the path is uneven. 2022 is -42.4%:
BTC had several bear-market rallies that flipped the signal to TQQQ before
further equity declines. 2023 is +310.4%: BTC momentum turned negative in
mid-July and stayed negative through late October, so the strategy held BIL
through the Aug-Oct QQQ drawdown and re-entered before the November-December
rally. Excluding 2023, the CAGR is **33.90%** with a 0.94 Sharpe.

The 2023 dependence is the main caveat. The strategy is not a smooth
all-weather compounder; it is a regime switch that can have a large single
year.

## Plateau (8 pre-registered cells)

| Windows | TQQQ z | BIL z | CAGR | Max DD | Sharpe | Fills | Turnover |
|---|---:|---:|---:|---:|---:|---:|---:|
| **20/60** | **0.00** | **0.00** | **53.66%** | **52.3%** | **1.28** | **201** | **1,152x** |
| 20/60 | 0.00 | -0.25 | 46.71% | 61.3% | 1.15 | 389 | 2,373x |
| 20/60 | +0.25 | 0.00 | 51.18% | 57.0% | 1.35 | 393 | 2,546x |
| 20/60 | +0.25 | -0.25 | 44.58% | 65.3% | 1.21 | 455 | 2,918x |
| 20 only | 0.00 | 0.00 | 49.43% | 47.6% | 1.20 | 309 | 1,815x |
| 20 only | +0.25 | -0.25 | 46.09% | 56.8% | 1.22 | 509 | 3,193x |
| 60 only | 0.00 | 0.00 | 20.44% | 83.7% | 0.67 | 145 | 536x |
| 60 only | +0.25 | -0.25 | 31.09% | 72.8% | 0.91 | 281 | 1,115x |

The six 20/60-blend and 20-only cells span **44.58% to 53.66%**, all above the
1 bp bar. The 60-only cells collapse to 20.44% and 31.09% and breach the
drawdown bar (83.7% and 72.8%). The fast 20-day BTC leg is essential; the
60-day leg alone is not a viable risk-appetite signal. The primary is the best
cell, but it is also the mechanism centre (positive/negative trend, no neutral
band), not a corner selected after the fact.

The threshold neighbours show the expected trade-off: adding a neutral QQQ
band (`+0.25/-0.25`) lowers CAGR to 44.58% and raises DD to 65.3%, while
keeping more QQQ exposure. The binary switch is the better expression of this
signal.

## Placebo and static attribution

* **Circular-shift placebo (100 shifts):** median CAGR 16.7%, 95th percentile
  41.4%; the real 53.66% is above 99 of 100 shifts (percentile 0.99). Median
  placebo Sharpe 0.56 vs the real 1.28 (97th percentile). Median placebo max
  DD 69.1% vs the real 52.3%.
* **Static book at the average weights (8.9/47.7/43.3):** 24.55% CAGR / 53.6%
  DD / 0.83 Sharpe. The timing adds **29.11 pp** of CAGR and 0.45 Sharpe. This
  is the largest timing contribution of the three families.

## Correlation to the nine current winners

| Winner | Correlation |
|---|---:|
| ratio-froth | 0.566 |
| vol-scaled-crash-stop | 0.624 |
| relative-value-tqqq | 0.670 |
| fomc-opex-window | 0.544 |
| family-session-timing | 0.558 |
| family-short-reversal | 0.497 |
| family-rebalance-flow | 0.675 |
| family-intraday-microstructure-day | 0.415 |
| family-ml-microstructure | 0.614 |

Range **0.42 to 0.67**. The highest are `family-rebalance-flow` (0.675) and
`relative-value-tqqq` (0.670); the lowest is
`family-intraday-microstructure-day` (0.415). No correlation approaches 0.95.
Daily-return correlation with the other two new families is 0.59 (sector) and
0.51 (breadth).

A same-map **QQQ 20/60 momentum** control (binary TQQQ/BIL) earns 28.64% CAGR /
64.3% DD / 0.87 Sharpe and correlates **0.582** with this strategy. The BTC
signal adds 25.0 pp of CAGR; it is not a QQQ price-trend proxy. The correlation
is moderate because both are risk-on/off switches, but the timing and the
magnitude are different.

## Kill criteria

| Criterion | Result | Pass? |
|---|---|---:|
| 1 bp CAGR > 36.72% | 53.66% | yes |
| 1 bp max DD < 82.29% | 52.33% | yes |
| 10 bp CAGR > 36.72% | 50.21% | yes |
| Placebo percentile >= 90% | 99% | yes |
| Max winner correlation <= 0.95 | 0.675 | yes |
| >= 100 fills / >= 30 events | 201 / 101 | yes |
| No negative subperiod | all positive | yes |
| Static blend not within 1 pp | 24.55% vs 53.66% | yes |
| Causality audit | 25/25 perturb, 25/25 mapping | yes |

The verdict is **dev_pass**. The margin over the TQQQ bar is 16.9 pp at 1 bp
and 13.5 pp at 10 bp, so this is not a marginal pass.

## Caveats

* **2023 dependence.** 2023 is +310.4%; excluding it, CAGR is 33.90% and
  Sharpe 0.94. The full-window headline is flattered by one exceptional year.
* **2022 drawdown.** -42.4% in 2022. BTC bear-market rallies repeatedly turned
  the signal on before equity declines resumed. The max DD is 52.3%, not a
  crash-proof profile.
* **The 60-day-only variant fails.** 20.44% CAGR / 83.7% DD. The fast 20-day
  leg carries the edge; this is a fast risk-appetite switch, not a slow trend.
* **Activity is just above the floor.** 201 fills / 101 events. A slightly
  slower signal would fall below the 100-fill floor.
* **Timestamp correction.** The one-session BTC lag is required because Yahoo
  BTC daily bars close after the US equity close. Without the lag the result
  is higher; that version is not causal and is not used.
* **2016 is a warm-up year.** The z-score needs about 180 sessions, so early
  2016 is QQQ; +4.0% is not a full TQQQ year.
* **No crypto position.** BTC is a signal series only; the traded assets are
  QQQ, TQQQ and BIL.
* **Development only.** No 2024-2026 data was read.

## Reproduce

```bash
cd research/new/family-crypto-risk-appetite
python strategy.py        # rewrites result.json
```

`build_weights(ts, opens, closes)` returns `(n, 3)` minute weights and accepts
either the shared minute panel or a daily panel. The development guard rejects
panels extending past 2023-12-29 unless the caller supplies `end`.
