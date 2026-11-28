# Beta rotation — development report

**Verdict: dev pass.** The QQQ-vs-SPY beta state earns **42.96% CAGR / 47.72%
max DD / 1.15 Sharpe** at 1 bp over 2016-2023, above the published TQQQ bar
(36.72% / 82.29% / 0.82) with a much lower drawdown. The result survives 5 bp
(41.88%) and 10 bp (40.55%) and the circular-shift placebo (real CAGR is at the
100th percentile of 100 timing-scrambled paths). It is a development-only
result; 2024-2026 is untouched.

## Development metrics

| Cost | CAGR | Max DD | Sharpe | Sortino | Vol | Exposure | Fills | Turnover |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 bp | 42.96% | 47.72% | 1.15 | 1.65 | 37.3% | 99.9% | 151 | 732x |
| 5 bp | 41.88% | 47.80% | 1.13 | 1.62 | 37.3% | 99.9% | 151 | 702x |
| 10 bp | 40.55% | 48.22% | 1.10 | 1.59 | 37.3% | 99.9% | 151 | 666x |

There are **151 fills across 76 independent fill days** (the activity floor is
100 fills or 30 events). Average weights are 69.0% QQQ, 27.9% TQQQ, 3.1% BIL.

## Subperiods and years

| Window | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| 2016-2019 | 27.3% | 30.6% | 1.12 |
| 2020-2021 | 116.8% | 33.9% | 1.34 |
| 2022-2023 | 17.4% | 47.0% | 0.59 |

| Year | Return |
|---|---:|
| 2016 | +20.0% |
| 2017 | +49.1% |
| 2018 | -1.8% |
| 2019 | +44.9% |
| 2020 | +174.0% |
| 2021 | +78.3% |
| 2022 | -39.4% |
| 2023 | +131.9% |

The 2022 loss is the main weakness: beta expansion is a slow risk signal, so
the strategy gives back a large part of the bear market before the BIL state
takes over. The 2023 recovery and the 2020-2021 trend do the heavy lifting.

## Plateau (pre-registered 2 x 2 x 2)

| Beta | pct_tqqq | asym_tqqq | CAGR | Max DD | Sharpe | Fills |
|---|---:|---:|---:|---:|---:|---:|
| blend 42/63 | 0.50 | 0.00 | 37.41% | 47.4% | 1.08 | 139 |
| **blend 42/63** | **0.60** | **0.00** | **42.96%** | **47.7%** | **1.15** | **151** |
| blend 42/63 | 0.50 | 0.05 | 42.79% | 51.0% | 1.10 | 151 |
| blend 42/63 | 0.60 | 0.05 | 49.81% | 54.6% | 1.12 | 135 |
| single 63 | 0.50 | 0.00 | 30.56% | 57.9% | 0.92 | 143 |
| single 63 | 0.60 | 0.00 | 39.15% | 52.9% | 1.05 | 139 |
| single 63 | 0.50 | 0.05 | 32.42% | 63.4% | 0.90 | 127 |
| single 63 | 0.60 | 0.05 | 43.24% | 58.8% | 1.01 | 101 |

Six of eight cells clear the published CAGR bar. The two single-63 low-
compression cells (0.50) do not, which is the honest soft spot: the fast 42-day
beta matters. The headline uses the 42/63 blend at the centre of the grid, not
the best cell (the best cell is 49.81% at asym 0.05).

## Placebo and static attribution

* **Circular-shift placebo (100 shifts):** median CAGR 21.2%, 95th percentile
  35.8%; the real 42.96% is above all 100 shifts (percentile 1.00). Median
  placebo Sharpe 0.69 vs the real 1.15.
* **Static book at the average weights (69.0/27.9/3.1):** 25.33% CAGR / 53.5%
  DD / 0.85 Sharpe. The timing adds 17.6 percentage points of CAGR and 0.30
  Sharpe, so the beta state is not just a disguised fixed mix.

## Correlation to the nine current winners

Range **0.52 to 0.78**. Highest: `family-rebalance-flow` 0.78,
`relative-value-tqqq` 0.76; lowest: `family-intraday-microstructure-day` 0.52,
`ratio-froth` 0.57. No correlation approaches the 0.95 duplicate threshold.

## Kill criteria

| Criterion | Result | Pass? |
|---|---|---|
| 1 bp CAGR > 36.72% | 42.96% | yes |
| 1 bp DD < 82.29% | 47.72% | yes |
| 10 bp CAGR > 36.72% | 40.55% | yes |
| Placebo percentile >= 90% | 100% | yes |
| Max winner correlation <= 0.95 | 0.78 | yes |
| >= 100 fills / >= 30 events | 151 / 76 | yes |
| No negative subperiod | all positive | yes |
| Static blend not within 1 pp | 25.33% vs 42.96% | yes |

## Caveats

* Beta uses local SPY daily closes, not the QQQ/TQQQ/BIL 1-minute panel. The
  regressor is daily by construction; the traded panel remains the shared
  1-minute data.
* The 42-day beta is the fast end of the grid. The 63-day-only result is
  39.15%, still a pass, but the gap is a real sensitivity.
* 2022 is -39.4%. This is a risk-on/risk-off family, not a crash-proof one.
* The 2016 partial year uses the QQQ fallback while the 252-day percentile
  warms up; it is not a full TQQQ year.

## Reproduce

```bash
cd research/new/family-beta-rotation
python strategy.py        # rewrites result.json
```

`build_weights(ts, opens, closes)` accepts the shared minute panel or a daily
panel; the lead's `run_holdout.py` can call it directly.
