# Breadth — development report

**Verdict: fail.** The RSP/SPY breadth state earns **35.62% CAGR / 64.66% max
DD / 1.00 Sharpe** at 1 bp over 2016-2023. It misses the published TQQQ CAGR
bar (36.72%) by 1.10 pp, falls to 32.01% at 5 bp and 27.63% at 10 bp, and has a
negative 2022-2023 subperiod (-12.61%). The signal is distinguishable from the
existing winners and from a QQQ trend proxy, and the placebo is positive, but
the family is not an above-TQQQ winner. 2024-2026 is untouched.

## Development metrics

| Cost | CAGR | Max DD | Sharpe | Sortino | Vol | Exposure | Fills | Turnover |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 bp | 35.62% | 64.66% | 1.00 | 1.46 | 37.5% | 100.0% | 539 | 2,877x |
| 5 bp | 32.01% | 66.20% | 0.93 | 1.36 | 37.5% | 100.0% | 539 | 2,487x |
| 10 bp | 27.63% | 68.11% | 0.84 | 1.22 | 37.5% | 100.0% | 539 | 2,080x |

There are **539 fills across 270 independent fill days** (about 68 fills and
34 events per year), well above the activity floor. Average weights are
**42.3% QQQ, 24.1% TQQQ, 33.6% BIL**.

The cost drag is 8.0 pp from 1 bp to 10 bp, the largest of the three families.
The RSP/SPY 20-day leg crosses its threshold frequently, and the full-book
state changes are expensive.

## Subperiods and years

| Window | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| 2016-2019 | 40.95% | 22.50% | 1.44 |
| 2020-2021 | 92.19% | 28.90% | 1.78 |
| 2022-2023 | -12.61% | 63.62% | 0.03 |

| Year | Return |
|---|---:|
| 2016 | +13.4% |
| 2017 | +18.8% |
| 2018 | +71.4% |
| 2019 | +66.6% |
| 2020 | +233.0% |
| 2021 | +15.4% |
| 2022 | -57.2% |
| 2023 | +82.5% |

The family worked well in 2016-2021, then broke in 2022. The breadth signal
turned defensive too late and then whipsawed; 2022 is -57.2% and the 2022-2023
subperiod is negative. 2023 recovers +82.5%, but not enough to repair the
subperiod. Excluding 2023, the CAGR is **30.37%** with a 0.86 Sharpe.

This is the clearest failure mode of the three: the economic object is real,
but the regime timing failed in the one period where a defensive signal should
have paid.

## Plateau (8 pre-registered cells)

| Windows | TQQQ z | BIL z | CAGR | Max DD | Sharpe | Fills | Turnover |
|---|---:|---:|---:|---:|---:|---:|---:|
| **20/60** | **+0.50** | **-0.50** | **35.62%** | **64.7%** | **1.00** | **539** | **2,877x** |
| 20/60 | +0.50 | -0.75 | 30.55% | 69.9% | 0.89 | 499 | 2,305x |
| 20/60 | +0.75 | -0.50 | 38.89% | 51.1% | 1.13 | 519 | 2,674x |
| 20/60 | +0.75 | -0.75 | 33.70% | 54.2% | 1.01 | 479 | 2,047x |
| 20 only | +0.50 | -0.50 | 37.23% | 68.6% | 1.04 | 683 | 3,400x |
| 20 only | +0.75 | -0.75 | 31.43% | 67.8% | 0.97 | 623 | 2,635x |
| 60 only | +0.50 | -0.50 | 29.90% | 69.1% | 0.86 | 433 | 2,212x |
| 60 only | +0.75 | -0.75 | 39.78% | 44.6% | 1.10 | 467 | 2,979x |

Three cells clear the 1 bp CAGR bar: the 20/60 blend at `+0.75/-0.50` (38.89%),
the 20-only at `+0.50/-0.50` (37.23%), and the 60-only at `+0.75/-0.75`
(39.78%). The primary is just below the bar. But every passing cell is a
different corner of the grid, the range is wide (29.90% to 39.78%), and none
of the passing cells is the pre-registered centre. This is parameter-sensitive,
not a plateau.

The 60-only `+0.75/-0.75` cell is the best (39.78% / 44.6% / 1.10), but it is a
slower, stricter corner; it still fails at 10 bp (32.61% in the development
screen). It is reported as a sensitivity, not promoted to the headline after
the fact.

## Placebo and static attribution

* **Circular-shift placebo (100 shifts):** median CAGR 16.4%, 95th percentile
  34.8%; the real 35.62% is at the 96th percentile. Median placebo Sharpe 0.60
  vs the real 1.00 (90th percentile). Median placebo max DD 58.3% vs the real
  64.7%.
* **Static book at the average weights (42.3/24.1/33.6):** 20.04% CAGR / 42.3%
  DD / 0.86 Sharpe. The timing adds **15.58 pp** of CAGR and 0.15 Sharpe.

The placebo says the dates carry information, but the static comparison also
shows the timing is not a free lunch: the dynamic strategy takes more
drawdown than the static mix in this sample.

## Correlation to the nine current winners

| Winner | Correlation |
|---|---:|
| ratio-froth | 0.376 |
| vol-scaled-crash-stop | 0.560 |
| relative-value-tqqq | 0.595 |
| fomc-opex-window | 0.506 |
| family-session-timing | 0.531 |
| family-short-reversal | 0.629 |
| family-rebalance-flow | 0.624 |
| family-intraday-microstructure-day | 0.483 |
| family-ml-microstructure | 0.579 |

Range **0.38 to 0.63**. The highest are `family-short-reversal` (0.629) and
`family-rebalance-flow` (0.624); the lowest is `ratio-froth` (0.376). No
correlation approaches 0.95. Daily-return correlation with the other two new
families is 0.37 (sector) and 0.51 (crypto).

A same-map **QQQ 20/60 momentum** control (`+/-0.50`, TQQQ/BIL/QQQ) earns
18.55% CAGR / 63.7% DD / 0.72 Sharpe and correlates only **0.376** with this
strategy. Breadth is the most orthogonal of the three families to a QQQ trend
proxy.

## Kill criteria

| Criterion | Result | Pass? |
|---|---|---:|
| 1 bp CAGR > 36.72% | 35.62% | **no** |
| 1 bp max DD < 82.29% | 64.66% | yes |
| 10 bp CAGR > 36.72% | 27.63% | **no** |
| Placebo percentile >= 90% | 96% | yes |
| Max winner correlation <= 0.95 | 0.629 | yes |
| >= 100 fills / >= 30 events | 539 / 270 | yes |
| No negative subperiod | 2022-2023 -12.61% | **no** |
| Static blend not within 1 pp | 20.04% vs 35.62% | yes |
| Causality audit | 25/25 perturb, 25/25 mapping | yes |

Three kills fire: the 1 bp CAGR bar, the 10 bp cost bar, and the negative
2022-2023 subperiod. The verdict is **fail**.

## Caveats

* **The primary fails by 1.1 pp at 1 bp.** This is not a rounding issue; the
  5 bp and 10 bp results are materially worse.
* **2022 is the failure.** The signal did not turn defensive early enough and
  then whipsawed; -57.2% is worse than the strategy's own static mix.
* **The plateau is parameter-sensitive.** The passing cells are scattered
  corners, and the best cell is a slower 60-day variant that also fails at
  10 bp.
* **Breadth can stay narrow for a long time.** The 2023 mega-cap rally is the
  obvious counterexample; the strategy recovered, but the 2022-2023 subperiod
  is still negative.
* **2016 is partly a warm-up year.** The 60-day z-score needs 120 observations,
  so early 2016 is QQQ; +13.4% is not a full TQQQ year.
* **Same-session ETF close.** RSP/SPY close at 16:00 ET, the same close used
  for the decision; the fill is the next session's open.
* **Development only.** No 2024-2026 data was read.

## Reproduce

```bash
cd research/strategies/family-breadth
python strategy.py        # rewrites result.json
```

`build_weights(ts, opens, closes)` returns `(n, 3)` minute weights and accepts
either the shared minute panel or a daily panel. The development guard rejects
panels extending past 2023-12-29 unless the caller supplies `end`.
