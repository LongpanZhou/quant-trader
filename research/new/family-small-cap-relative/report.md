# IWM/QQQ small-cap relative leadership -- report

**Slug:** `family-small-cap-relative`  
**Family:** `small-cap-relative`  
**Window:** 2016-01-04 -> 2023-12-29, development only. The 2024-2026 holdout was not loaded.  
**Execution:** `research/bt.py`, 1-minute marks, next-open fills, 2% band, long-only, weights >= 0, sum <= 1. Headline 1 bp; 5 bp and 10 bp also reported.  
**Primary:** IWM/QQQ 20-session relative total-return z-score.  
**Verdict:** `fail`  

**Verdict: `fail`.** The headline clears the TQQQ bar (45.40% vs 36.72% CAGR, 78.08% vs 82.29% max DD) but the 2022-2023 subperiod is negative. The family is a high-beta Nasdaq overlay, not a defensive reserve.

---

## 1. Headline

| cost | CAGR | max DD | Sharpe | Sortino | vol | exposure | fills | turnover |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **1 bp** | 45.40% | 78.08% | 0.99 | 1.41 | 51.10% | 99.95% | 403 | 3,454x |
| 5 bp | 42.49% | 78.41% | 0.95 | 1.35 | 51.10% | 99.95% | 403 | 3,087x |
| 10 bp | 38.94% | 78.82% | 0.90 | 1.28 | 51.10% | 99.95% | 403 | 2,688x |

The stated bar is TQQQ **36.72% CAGR / 82.29% max DD / 0.82 Sharpe**. The local 1-minute benchmark is 36.15% / 82.29% / 0.80. Ending equity at 1 bp is **$1,985,882** from $100,000. There are **202** distinct fill events.

Average target weights: QQQ 37.8%, TQQQ 62.2%, BIL 0.0%.

## 2. Benchmarks

| | CAGR | max DD | Sharpe | vol |
|---|---:|---:|---:|---:|
| primary 1 bp | 45.40% | 78.08% | 0.99 | 51.10% |
| TQQQ | 36.15% | 82.29% | 0.80 | 66.55% |
| QQQ | 18.91% | 37.30% | 0.90 | 22.02% |

## 3. Yearly returns

| year | strategy | TQQQ | QQQ |
|---|---:|---:|---:|
| 2016 | 17.6% | 18.6% | 9.3% |
| 2017 | 74.7% | 113.0% | 31.5% |
| 2018 | 48.7% | -23.5% | -1.8% |
| 2019 | 71.5% | 130.5% | 38.4% |
| 2020 | 205.9% | 99.8% | 45.9% |
| 2021 | 59.9% | 90.9% | 29.2% |
| 2022 | -72.5% | -79.7% | -33.2% |
| 2023 | 156.7% | 204.9% | 55.9% |

## 4. Subperiods

| period | strategy CAGR | strategy DD | Sharpe | TQQQ CAGR | TQQQ DD |
|---|---:|---:|---:|---:|---:|
| 2016-2019 | 54.51% | 31.62% | 1.29 | 48.60% | 57.97% |
| 2020-2021 | 116.89% | 30.46% | 1.72 | 91.47% | 69.89% |
| 2022-2023 | -17.05% | 76.33% | 0.09 | -22.33% | 81.05% |

## 5. Eight-cell plateau

| # | params | CAGR | max DD | Sharpe | fills | pass |
|---:|---|---:|---:|---:|---:|---|
| 1 | lookback=20, norm_window=126, threshold=-0.75, mapping=binary | 51.80% | 76.84% | 1.05 | 403 | yes |
| 2 | lookback=20, norm_window=126, threshold=-0.5, mapping=binary | 45.61% | 79.09% | 1.00 | 435 | yes |
| 3 | lookback=20, norm_window=126, threshold=-0.75, mapping=ladder | 58.52% | 75.37% | 1.15 | 607 | yes |
| 4 | lookback=20, norm_window=126, threshold=-0.5, mapping=ladder | 49.89% | 77.42% | 1.07 | 721 | yes |
| 5 | lookback=20, norm_window=252, threshold=-0.75, mapping=binary | 55.77% | 77.44% | 1.10 | 367 | yes |
| 6 | lookback=20, norm_window=252, threshold=-0.5, mapping=binary | 45.40% | 78.08% | 0.99 | 403 | yes |
| 7 | lookback=20, norm_window=252, threshold=-0.75, mapping=ladder | 63.51% | 76.01% | 1.21 | 547 | yes |
| 8 | lookback=20, norm_window=252, threshold=-0.5, mapping=ladder | 48.51% | 75.94% | 1.05 | 713 | yes |

**8 of 8 cells pass** (100%). The plateau rule requires at least 5 of 8.

## 6. Ablations

| params | CAGR | max DD | Sharpe | fills | pass |
|---|---:|---:|---:|---:|---|
| lookback=60, norm_window=252, threshold=-0.5, mapping=binary | 38.17% | 76.36% | 0.92 | 267 | yes |
| lookback=60, norm_window=252, threshold=-0.5, mapping=ladder | 37.90% | 75.57% | 0.94 | 503 | yes |

## 7. Placebo

Circular shifts of the daily target sequence preserve the allocation path and exposure but destroy its alignment with returns.

| draws | CAGR p05 | CAGR p50 | CAGR p95 | CAGR max | real percentile | DD p50 |
|---:|---:|---:|---:|---:|---:|---:|
| 60 | 15.20% | 24.66% | 47.97% | 54.06% | 93% | 75.07% |

Sharpe percentile of the real result: 95%.

## 8. Correlation to the nine winners

| winner | correlation |
|---|---:|
| family-rebalance-flow | 0.83 |
| family-short-reversal | 0.82 |
| relative-value-tqqq | 0.80 |
| family-ml-microstructure | 0.80 |
| vol-scaled-crash-stop | 0.76 |
| family-session-timing | 0.69 |
| fomc-opex-window | 0.65 |
| family-intraday-microstructure-day | 0.58 |
| ratio-froth | 0.55 |

Range **0.55 .. 0.83**; maximum is `family-rebalance-flow`. The duplicate threshold is 0.95.

## 9. Static blend at the same average weights

| | CAGR | max DD | Sharpe |
|---|---:|---:|---:|
| strategy 1 bp | 45.40% | 78.08% | 0.99 |
| static average weights | 32.18% | 70.04% | 0.81 |

## 10. Kill criteria -- verdict

| # | criterion | triggered? |
|---:|---|---|
| 1 | `cagr_1bp_below_tqqq_bar` | no |
| 2 | `drawdown_1bp_above_tqqq` | no |
| 3 | `cagr_10bp_below_tqqq_bar` | no |
| 4 | `plateau_below_5_of_8` | no |
| 5 | `placebo_below_90th` | no |
| 6 | `winner_correlation_above_0.95` | no |
| 7 | `fewer_than_100_fills_and_30_events` | no |
| 8 | `negative_subperiod` | **yes** |
| 9 | `static_blend_matches` | no |

**Verdict: `fail`.**

## 11. Interpretation

The small-cap family passes the headline test but fails the consistency test.
At 1 bp it makes **45.40%** with a **78.08%** drawdown; all eight plateau cells
pass; the real result is at the 93rd percentile of the circular-shift placebo;
and the static 38/62 QQQ/TQQQ blend only makes 32.18%. But 2022 is
**-72.5%** and the 2022-2023 subperiod is **-17.1%**. The IWM/QQQ spread stayed positive for much of
2022 because large-cap growth fell harder than small caps, so the strategy
stayed in TQQQ through the Nasdaq bear market. The signal is a risk-appetite
thermometer, not a crash detector.

Every plateau cell has a 75-79% drawdown. This is a levered Nasdaq beta
overlay with a small-cap tilt, not a defensive reserve. The 8/8 plateau is
therefore less impressive than it looks: the whole surface is high-return,
high-drawdown. Correlation to the existing winners reaches 0.83
(`family-rebalance-flow`), the highest of the four families.

The family is reported as a **negative result on the kill criteria** because
of the negative subperiod, even though the 1 bp headline clears the TQQQ bar.
A user who only cares about eight-year CAGR/DD could use it; a user who cares
about surviving 2022 should not.

## 12. Causality and implementation

- Truncating the panel at **2020-03-12 11:07** leaves **409,460** prior weights identical (`max_abs_weight_diff = 0.0e+00`, pass = True).
- Signals use daily closes through session k; the target is written at k's 15:59 close and filled at k+1's 09:30 open.
- Signal legs are the external daily adjusted closes in `data/external/` (QQQ's leg is the local `QQQ-1d-yahoo.parquet`); execution prices are the local 1-minute QQQ/TQQQ/BIL panel.
- No same-day fill, no full-sample normalisation, no price-trend gate, no volatility targeting, no drawdown event, no calendar clock, no opening-range/close-flow, no ML and no relative-strength ratio gate.
- Long-only, weights 0/1 or a two-asset split, sum <= 1; BIL is the flat asset. The 2% band is the only rebalance dead-band.

## 13. Caveats

- Development-only: 2016-2023. The 2024-2026 holdout was physically excluded from every Parquet read.
- A separate process deposited `holdout.json` / `holdout_run.log` in this folder after the development run; this agent did not read or use them.
- The primary cell was chosen after daily-bar diagnostics on the same window; the 8-cell grid is a robustness probe, not a clean out-of-sample pre-registration.
- The 1-minute panel starts in 2016, so the sample cannot cover 2000/2008.
- Costs are 1/5/10 bp on traded notional; the 2% band is fixed.
