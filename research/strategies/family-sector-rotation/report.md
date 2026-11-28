# Sector rotation — development report

**Verdict: fail (cost-fragile, narrow plateau).** The XLK/XLU leadership state
earns **37.65% CAGR / 48.79% max DD / 1.09 Sharpe** at 1 bp over 2016-2023.
That clears the published TQQQ CAGR bar (36.72%) by only 0.93 pp, cuts the
drawdown from 82.29% to 48.79%, and is strongly non-random (placebo 98th
percentile). But it fails at 5 bp (34.11%) and 10 bp (29.83%), and only two of
the eight pre-registered cells clear the 1 bp bar. The result is a genuine
risk-management signal, not a cost-robust above-TQQQ winner. 2024-2026 is
untouched.

## Development metrics

| Cost | CAGR | Max DD | Sharpe | Sortino | Vol | Exposure | Fills | Turnover |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 bp | 37.65% | 48.79% | 1.09 | 1.58 | 35.1% | 100.0% | 519 | 2,210x |
| 5 bp | 34.11% | 51.58% | 1.01 | 1.47 | 35.1% | 100.0% | 519 | 1,913x |
| 10 bp | 29.83% | 54.86% | 0.92 | 1.33 | 35.1% | 100.0% | 519 | 1,603x |

There are **519 fills across 260 independent fill days** (about 65 fills and
33 events per year), comfortably above the 100-fill / 30-event floor. Average
weights are **45.8% QQQ, 29.0% TQQQ, 25.2% BIL**. The book is always fully
invested in one of those three assets.

The cost drag is large: 7.8 pp of CAGR from 1 bp to 10 bp. The 20-day leg
crosses its threshold often, and each state change trades the full book. This
is the family's central weakness.

## Subperiods and years

| Window | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| 2016-2019 | 26.37% | 28.55% | 1.11 |
| 2020-2021 | 64.50% | 31.62% | 1.37 |
| 2022-2023 | 33.71% | 29.21% | 0.89 |

| Year | Return |
|---|---:|
| 2016 | +11.6% |
| 2017 | +25.6% |
| 2018 | +7.1% |
| 2019 | +61.0% |
| 2020 | +185.4% |
| 2021 | -4.0% |
| 2022 | -13.5% |
| 2023 | +104.1% |

All three subperiods are positive, so the subperiod kill does not fire. But
2021 and 2022 are negative years: the sector signal was early in 2021 and
whipsawed in 2022. The result is carried by 2020 (+185%) and 2023 (+104%).
Excluding 2023, the CAGR is **29.93%** with a 0.95 Sharpe, so the full-window
headline overstates the typical year.

## Plateau (8 pre-registered cells)

| Windows | TQQQ z | BIL z | CAGR | Max DD | Sharpe | Fills | Turnover |
|---|---:|---:|---:|---:|---:|---:|---:|
| **20/60** | **+0.50** | **-0.50** | **37.65%** | **48.8%** | **1.09** | **519** | **2,210x** |
| 20/60 | +0.50 | -0.75 | 38.23% | 51.8% | 1.09 | 457 | 2,172x |
| 20/60 | +0.75 | -0.50 | 27.96% | 47.7% | 0.96 | 491 | 1,561x |
| 20/60 | +0.75 | -0.75 | 28.50% | 50.7% | 0.96 | 429 | 1,523x |
| 20 only | +0.50 | -0.50 | 30.18% | 60.5% | 0.94 | 753 | 3,109x |
| 20 only | +0.75 | -0.75 | 25.55% | 57.9% | 0.87 | 609 | 2,126x |
| 60 only | +0.50 | -0.50 | 20.89% | 69.3% | 0.72 | 495 | 1,348x |
| 60 only | +0.75 | -0.75 | 27.69% | 59.0% | 0.91 | 329 | 1,263x |

This is **not a plateau; it is a narrow ridge**. Only the two 20/60 cells with
`tqqq_z = 0.50` clear the 1 bp bar. Raising the TQQQ threshold to 0.75 costs
about 9-10 pp, and both single-horizon families fail. The 20-day leg carries
the timing information, but it is also the source of the turnover. The blend
is the only configuration that works, which is a real fragility.

## Placebo and static attribution

* **Circular-shift placebo (100 shifts):** median CAGR 16.9%, 95th percentile
  33.0%; the real 37.65% is above 98 of 100 shifts (percentile 0.98). Median
  placebo Sharpe 0.61 vs the real 1.09 (percentile 0.98). Median placebo max
  DD 62.4% vs the real 48.8%.
* **Static book at the average weights (45.8/29.0/25.2):** 22.40% CAGR / 47.6%
  DD / 0.84 Sharpe. The timing adds **15.25 pp** of CAGR and 0.25 Sharpe, so
  the state is not just a disguised fixed mix.

## Correlation to the nine current winners

| Winner | Correlation |
|---|---:|
| ratio-froth | 0.504 |
| vol-scaled-crash-stop | 0.619 |
| relative-value-tqqq | 0.641 |
| fomc-opex-window | 0.536 |
| family-session-timing | 0.526 |
| family-short-reversal | 0.543 |
| family-rebalance-flow | 0.644 |
| family-intraday-microstructure-day | 0.427 |
| family-ml-microstructure | 0.572 |

Range **0.43 to 0.64**. The highest are `family-rebalance-flow` (0.644) and
`relative-value-tqqq` (0.641); the lowest is
`family-intraday-microstructure-day` (0.427). No correlation approaches the
0.95 duplicate threshold. Daily-return correlation with the other two new
families is 0.37 (breadth) and 0.59 (crypto).

A same-map **QQQ 20/60 momentum** control (`±0.50`, TQQQ/BIL/QQQ) earns
18.55% CAGR / 63.7% DD / 0.72 Sharpe and correlates **0.735** with this
strategy. The sector signal adds 19.1 pp of CAGR, but the 0.735 correlation
says part of the edge is tech-beta timing rather than a pure sector effect.
That is a further reason not to call this a clean new winner.

## Kill criteria

| Criterion | Result | Pass? |
|---|---|---:|
| 1 bp CAGR > 36.72% | 37.65% | yes (marginal) |
| 1 bp max DD < 82.29% | 48.79% | yes |
| 10 bp CAGR > 36.72% | 29.83% | **no** |
| Placebo percentile >= 90% | 98% | yes |
| Max winner correlation <= 0.95 | 0.644 | yes |
| >= 100 fills / >= 30 events | 519 / 260 | yes |
| No negative subperiod | all positive | yes |
| Static blend not within 1 pp | 22.40% vs 37.65% | yes |
| Causality audit | 25/25 perturb, 25/25 mapping | yes |

The only failed kill is the 10 bp cost check. Because the 1 bp margin is also
under 1 pp and the plateau is a narrow ridge, the honest verdict is **fail**,
not "pass with caveats."

## Caveats

* **Cost fragility is structural.** The 20-day leg is the source of both the
  alpha and the turnover; slowing it to 60 days removes the alpha.
* **The plateau is narrow.** Only the 20/60 blend at `tqqq_z = 0.50` clears the
  1 bp bar. The result is not robust to a modestly stricter entry threshold.
* **Two negative years.** 2021 (-4.0%) and 2022 (-13.5%) show the signal can
  be early and can whipsaw. The 2020 and 2023 tails carry the headline.
* **2016 is partly a warm-up year.** The 60-day z-score needs 120 observations,
  so early 2016 is QQQ; +11.6% is not a full TQQQ year.
* **Partial QQQ-trend overlap.** The 0.735 correlation to a same-map QQQ
  momentum control is high, even though the CAGR difference is large.
* **Same-session ETF close.** XLK/XLU close at 16:00 ET, the same close used
  for the decision; the fill is the next session's open. This is a standard
  daily-close convention, not a same-bar fill.
* **Development only.** No 2024-2026 data was read. The result is a frozen
  development record, not a holdout claim.

## Reproduce

```bash
cd research/strategies/family-sector-rotation
python strategy.py        # rewrites result.json
```

`build_weights(ts, opens, closes)` returns `(n, 3)` minute weights and accepts
either the shared minute panel or a daily panel. The development guard rejects
panels extending past 2023-12-29 unless the caller supplies `end`.
