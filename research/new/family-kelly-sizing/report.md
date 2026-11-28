# Kelly sizing — development report

**Verdict: numeric pass, weak-timing caveat (fails the pre-registered placebo
kill).** The skew-aware fractional-Kelly allocator earns **39.39% CAGR / 57.08%
max DD / 0.97 Sharpe** at 1 bp over 2016-2023, above the published TQQQ bar
(36.72% / 82.29% / 0.82) and still above it at 10 bp (37.61%). It clears the
activity floor with **686 fills across 329 independent fill days**. However,
the real CAGR is at the **88th percentile** of 100 circular-shift placebos,
below the pre-registered 90% threshold. The sizing adds 8.9 pp of CAGR over a
static book at the same average weights, but the timing edge is not as cleanly
distinguishable from a lucky allocation path as the beta or decay families.
Development only; 2024-2026 is untouched.

## Development metrics

| Cost | CAGR | Max DD | Sharpe | Sortino | Vol | Exposure | Fills | Turnover |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 bp | 39.39% | 57.08% | 0.97 | 1.37 | 44.5% | 99.9% | 686 | 450x |
| 5 bp | 38.61% | 57.13% | 0.96 | 1.35 | 44.5% | 99.9% | 690 | 438x |
| 10 bp | 37.61% | 57.19% | 0.94 | 1.33 | 44.5% | 99.9% | 688 | 422x |

Average weights are 14.8% QQQ, 64.9% TQQQ, 20.3% BIL. The book is aggressive:
it holds TQQQ about two-thirds of the time and uses BIL only when the QQQ Kelly
edge turns negative.

## Subperiods and years

| Window | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| 2016-2019 | 34.0% | 45.8% | 0.87 |
| 2020-2021 | 86.9% | 56.9% | 1.13 |
| 2022-2023 | 8.5% | 42.2% | 0.36 |

| Year | Return |
|---|---:|
| 2016 | +23.4% |
| 2017 | +103.9% |
| 2018 | -13.9% |
| 2019 | +38.1% |
| 2020 | +96.2% |
| 2021 | +84.7% |
| 2022 | -39.4% |
| 2023 | +94.2% |

The 2022 drawdown is the weak point: the overlay's rolling mean turns negative
only after the damage, and the QQQ gate moves the book to BIL late. The
2022-2023 subperiod is still positive because 2023 recovers strongly.

## Plateau (pre-registered 8 cells)

| windows | kappa | CAGR | Max DD | Sharpe | Fills |
|---|---:|---:|---:|---:|---:|
| 126 | 0.80 | 34.83% | 54.4% | 0.94 | 477 |
| 126 | 0.90 | 36.36% | 57.3% | 0.93 | 417 |
| 168 | 0.80 | 35.66% | 52.9% | 0.95 | 556 |
| 168 | 0.90 | 37.48% | 55.9% | 0.94 | 498 |
| 210 | 0.80 | 31.82% | 56.8% | 0.86 | 690 |
| 210 | 0.90 | 33.15% | 59.9% | 0.86 | 628 |
| 126/168/210 | 0.80 | 37.35% | 54.2% | 0.98 | 722 |
| **126/168/210** | **0.90** | **39.39%** | **57.1%** | **0.97** | **686** |

Six of eight cells clear the published CAGR bar. The 210-session corner does
not (31.8-33.2%): a three-quarter-year window is too slow for the 2022 regime
change. The multi-window average is the robust choice and is the primary cell.

## Placebo and static attribution

* **Circular-shift placebo (100 shifts):** median CAGR 23.2%, 5th-95th range
  14.2-55.3%; the real 39.39% is at the **88th percentile**, below the 90%
  kill. Median placebo Sharpe 0.66 vs the real 0.97; the Sharpe percentile is
  90%.
* **Static book at the average weights (14.8/64.9/20.3):** 30.45% CAGR / 67.1%
  DD / 0.81 Sharpe. The Kelly timing adds 8.9 pp of CAGR and 0.16 Sharpe, so
  it is not a pure static mix, but the improvement is smaller than for beta or
  decay.

The wide placebo upper tail is the honest problem: some rotations of the same
allocation path land the high-TQQQ book on 2020-2021 and compound faster than
the real path. The Kelly state is informative on average, but not sharply
separated from a lucky rotation at the 90% confidence level.

## Correlation to the nine current winners

Range **0.47 to 0.89**. Highest: `relative-value-tqqq` 0.89, `ratio-froth`
0.79, `family-rebalance-flow` 0.79. This is the most correlated of the four new
families, as expected for a high-TQQQ-weight sizer. It is below the 0.95
duplicate threshold.

## Kill criteria

| Criterion | Result | Pass? |
|---|---|---|
| 1 bp CAGR > 36.72% | 39.39% | yes |
| 1 bp DD < 82.29% | 57.08% | yes |
| 10 bp CAGR > 36.72% | 37.61% | yes |
| Placebo percentile >= 90% | 88% | **no** |
| Max winner correlation <= 0.95 | 0.89 | yes |
| >= 100 fills / >= 30 events | 686 / 329 | yes |
| No negative subperiod | all positive | yes |
| Static blend not within 1 pp | 30.45% vs 39.39% | yes |

## Assessment

This is a real, active, reproducible strategy with a genuine numeric pass, but
it is **not a clean accept under its own pre-registered rule**. The failure is
specifically the placebo confidence test, not the return, drawdown, cost,
activity or duplication tests. Two honest options for the lead:

1. Accept it as a numeric above-TQQQ family with an explicit "weak timing"
   note; the static-blend and 10 bp results support a real sizing contribution.
2. Keep it as a research record and use `family-beta-rotation` and
   `family-tqqq-decay` as the two accepted families.

The report deliberately does not relax the 90% threshold after seeing 88%.

## Caveats

* The Kelly fraction is estimated on a rolling empirical sample; it is not a
  forecast of future mean or variance. In a regime change the estimate is
  stale for up to the window length.
* The fourth-order expansion is a local approximation; the 201-point grid and
  the `f in [0,1]` cap keep it bounded, but it is not an exact empirical Kelly
  optimiser.
* 2018 (-13.9%) and 2022 (-39.4%) are large losses. The family is not
  crash-protected.
* Transaction costs are modest because the 2% band suppresses small rebalances,
  but turnover is 450x and the 10 bp case gives up 1.8 pp of CAGR.

## Reproduce

```bash
cd research/new/family-kelly-sizing
python strategy.py        # rewrites result.json
```

`build_weights(ts, opens, closes)` accepts the shared minute panel or a daily
panel; the lead's `run_holdout.py` can call it directly.
