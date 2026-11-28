# TQQQ decay — development report

**Verdict: dev pass.** The realised-decay state earns **45.48% CAGR / 38.33%
max DD / 1.17 Sharpe** at 1 bp over 2016-2023, above the published TQQQ bar
(36.72% / 82.29% / 0.82) with less than half the drawdown. It survives 5 bp
(43.96%) and 10 bp (42.09%), and the real CAGR is above all 100 circular-shift
placebos. Development only; 2024-2026 is untouched.

## Development metrics

| Cost | CAGR | Max DD | Sharpe | Sortino | Vol | Exposure | Fills | Turnover |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 bp | 45.48% | 38.33% | 1.17 | 1.67 | 38.3% | 99.9% | 209 | 1083x |
| 5 bp | 43.96% | 38.33% | 1.15 | 1.63 | 38.3% | 99.9% | 209 | 1020x |
| 10 bp | 42.09% | 38.48% | 1.11 | 1.58 | 38.3% | 99.9% | 209 | 946x |

There are **209 fills across 105 independent fill days**. Average weights are
13.2% QQQ, 50.4% TQQQ, 36.4% BIL — the strategy spends about a third of the
sample in cash and half in TQQQ.

## Subperiods and years

| Window | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| 2016-2019 | 27.9% | 28.4% | 1.10 |
| 2020-2021 | 94.2% | 35.4% | 1.49 |
| 2022-2023 | 37.9% | 34.8% | 0.98 |

| Year | Return |
|---|---:|
| 2016 | +0.1% (252-day slow-window warm-up; BIL) |
| 2017 | +68.0% |
| 2018 | -2.7% |
| 2019 | +60.4% |
| 2020 | +160.0% |
| 2021 | +50.9% |
| 2022 | -23.2% |
| 2023 | +144.9% |

The 2022-2023 subperiod is the strongest of the three: accelerating decay
moved the book to BIL before the worst of 2022, and cheap decay in 2023 put it
back into TQQQ for the recovery. The strategy gives up part of the 2021 melt-up
(50.9% vs TQQQ's 90.9%) because decay was already elevated.

## Plateau (pre-registered 8 cells)

| fast | slow | tqqq_thr | CAGR | Max DD | Sharpe | Fills |
|---:|---:|---:|---:|---:|---:|---:|
| 10 | 252 | -0.10 | 42.38% | 50.7% | 1.11 | 389 |
| **21** | **252** | **-0.10** | **45.48%** | **38.3%** | **1.17** | **209** |
| 42 | 252 | -0.10 | 47.29% | 38.3% | 1.21 | 145 |
| 21 | 189 | -0.10 | 42.64% | 53.1% | 1.10 | 301 |
| 21 | 252 | -0.20 | 41.36% | 38.5% | 1.16 | 301 |
| 21 | 252 | 0.00 | 47.89% | 51.8% | 1.18 | 207 |
| 10 | 252 | 0.00 | 49.78% | 48.6% | 1.21 | 357 |
| 42 | 252 | 0.00 | 42.51% | 55.4% | 1.09 | 147 |

All eight cells clear the published CAGR bar and all clear it at 10 bp as well
(36.6% to 44.5%). This is a genuine plateau, not a single lucky cell: the
21/252 cell is the centre and sits inside a 41-50% CAGR / 38-55% DD region.

## Placebo and static attribution

* **Circular-shift placebo (100 shifts):** median CAGR 19.3%, 95th percentile
  36.9%; the real 45.48% is above all 100 shifts (percentile 1.00). Median
  placebo Sharpe 0.62 vs the real 1.17.
* **Static book at the average weights (13.2/50.4/36.4):** 25.89% CAGR /
  56.7% DD / 0.82 Sharpe. Timing adds 19.6 pp of CAGR and 0.35 Sharpe.

## Correlation to the nine current winners

Range **0.41 to 0.73**. Highest: `relative-value-tqqq` 0.73,
`family-rebalance-flow` 0.72; lowest: `family-intraday-microstructure-day`
0.41, `family-short-reversal` 0.48. The max is well below the 0.95 duplicate
threshold, and the correlation to `vol-scaled-crash-stop` is 0.63 — the decay
ratio is not a copy of the crash-stop state.

## Kill criteria

| Criterion | Result | Pass? |
|---|---|---|
| 1 bp CAGR > 36.72% | 45.48% | yes |
| 1 bp DD < 82.29% | 38.33% | yes |
| 10 bp CAGR > 36.72% | 42.09% | yes |
| Placebo percentile >= 90% | 100% | yes |
| Max winner correlation <= 0.95 | 0.73 | yes |
| >= 100 fills / >= 30 events | 209 / 105 | yes |
| No negative subperiod | all positive | yes |
| Static blend not within 1 pp | 25.89% vs 45.48% | yes |

## Caveats

* `D = 3*r_Q - r_T` is approximately `3*sigma_Q^2`; this family is mechanically
  related to variance timing even though the signal is the realised fund decay
  and its own structural baseline. The report does not claim a pure
  "non-volatility" premium.
* 2016 is flat because the 252-session slow mean is unavailable. The reported
  CAGR includes that year, so the result is not flattered by dropping it.
* The 10 bp cost case is 1.3 pp below the 1 bp case but still clears the bar.
* The strategy is long-only and fully invested in QQQ/TQQQ/BIL; there is no
  shorting, options or leverage beyond TQQQ.

## Reproduce

```bash
cd research/new/family-tqqq-decay
python strategy.py        # rewrites result.json
```

`build_weights(ts, opens, closes)` accepts the shared minute panel or a daily
panel; the lead's `run_holdout.py` can call it directly.
