# EEM/QQQ international relative leadership -- report

**Slug:** `family-international-relative`  
**Family:** `international-relative`  
**Window:** 2016-01-04 -> 2023-12-29, development only. The 2024-2026 holdout was not loaded.  
**Execution:** `research/bt.py`, 1-minute marks, next-open fills, 2% band, long-only, weights >= 0, sum <= 1. Headline 1 bp; 5 bp and 10 bp also reported.  
**Primary:** EEM/QQQ 60-session relative total-return z-score.  
**Verdict:** `dev_pass`  

**Verdict: `dev_pass`.** The primary earns **51.12% CAGR / 54.81% max DD / 1.10 Sharpe** at 1 bp, above the published TQQQ bar (36.72% / 82.29% / 0.82) with a lower drawdown. It is a development-only result; 2024-2026 is untouched.

---

## 1. Headline

| cost | CAGR | max DD | Sharpe | Sortino | vol | exposure | fills | turnover |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **1 bp** | 51.12% | 54.81% | 1.10 | 1.58 | 47.94% | 99.95% | 249 | 2,300x |
| 5 bp | 49.25% | 55.21% | 1.08 | 1.54 | 47.94% | 99.95% | 249 | 2,142x |
| 10 bp | 46.94% | 55.70% | 1.05 | 1.50 | 47.94% | 99.95% | 249 | 1,962x |

The stated bar is TQQQ **36.72% CAGR / 82.29% max DD / 0.82 Sharpe**. The local 1-minute benchmark is 36.15% / 82.29% / 0.80. Ending equity at 1 bp is **$2,702,340** from $100,000. There are **125** distinct fill events.

Average target weights: QQQ 48.5%, TQQQ 51.5%, BIL 0.0%.

## 2. Benchmarks

| | CAGR | max DD | Sharpe | vol |
|---|---:|---:|---:|---:|
| primary 1 bp | 51.12% | 54.81% | 1.10 | 47.94% |
| TQQQ | 36.15% | 82.29% | 0.80 | 66.55% |
| QQQ | 18.91% | 37.30% | 0.90 | 22.02% |

## 3. Yearly returns

| year | strategy | TQQQ | QQQ |
|---|---:|---:|---:|
| 2016 | 45.1% | 18.6% | 9.3% |
| 2017 | 81.0% | 113.0% | 31.5% |
| 2018 | -26.9% | -23.5% | -1.8% |
| 2019 | 153.4% | 130.5% | 38.4% |
| 2020 | 162.6% | 99.8% | 45.9% |
| 2021 | 57.2% | 90.9% | 29.2% |
| 2022 | -43.0% | -79.7% | -33.2% |
| 2023 | 123.6% | 204.9% | 55.9% |

## 4. Subperiods

| period | strategy CAGR | strategy DD | Sharpe | TQQQ CAGR | TQQQ DD |
|---|---:|---:|---:|---:|---:|
| 2016-2019 | 50.95% | 50.93% | 1.22 | 48.60% | 57.97% |
| 2020-2021 | 99.18% | 30.46% | 1.71 | 91.47% | 69.89% |
| 2022-2023 | 11.75% | 52.83% | 0.49 | -22.33% | 81.05% |

## 5. Eight-cell plateau

| # | params | CAGR | max DD | Sharpe | fills | pass |
|---:|---|---:|---:|---:|---:|---|
| 1 | lookback=60, norm_window=126, threshold=-0.75, mapping=binary | 45.26% | 60.63% | 1.01 | 229 | yes |
| 2 | lookback=60, norm_window=126, threshold=-0.5, mapping=binary | 44.23% | 52.89% | 1.02 | 213 | yes |
| 3 | lookback=60, norm_window=126, threshold=-0.75, mapping=ladder | 48.89% | 58.51% | 1.08 | 471 | yes |
| 4 | lookback=60, norm_window=126, threshold=-0.5, mapping=ladder | 45.11% | 51.48% | 1.06 | 455 | yes |
| 5 | lookback=60, norm_window=252, threshold=-0.75, mapping=binary | 48.71% | 64.08% | 1.04 | 231 | yes |
| 6 | lookback=60, norm_window=252, threshold=-0.5, mapping=binary | 51.12% | 54.81% | 1.10 | 249 | yes |
| 7 | lookback=60, norm_window=252, threshold=-0.75, mapping=ladder | 51.96% | 62.24% | 1.10 | 427 | yes |
| 8 | lookback=60, norm_window=252, threshold=-0.5, mapping=ladder | 55.64% | 51.74% | 1.20 | 477 | yes |

**8 of 8 cells pass** (100%). The plateau rule requires at least 5 of 8.

## 6. Ablations

| params | CAGR | max DD | Sharpe | fills | pass |
|---|---:|---:|---:|---:|---|
| lookback=20, norm_window=252, threshold=-0.5, mapping=binary | 24.48% | 83.91% | 0.68 | 363 | no |
| lookback=20, norm_window=252, threshold=-0.5, mapping=ladder | 17.45% | 87.17% | 0.57 | 577 | no |

## 7. Placebo

Circular shifts of the daily target sequence preserve the allocation path and exposure but destroy its alignment with returns.

| draws | CAGR p05 | CAGR p50 | CAGR p95 | CAGR max | real percentile | DD p50 |
|---:|---:|---:|---:|---:|---:|---:|
| 60 | 14.59% | 26.59% | 41.13% | 47.63% | 100% | 72.74% |

Sharpe percentile of the real result: 100%.

## 8. Correlation to the nine winners

| winner | correlation |
|---|---:|
| family-short-reversal | 0.80 |
| family-rebalance-flow | 0.79 |
| relative-value-tqqq | 0.79 |
| family-ml-microstructure | 0.77 |
| vol-scaled-crash-stop | 0.72 |
| family-session-timing | 0.67 |
| fomc-opex-window | 0.64 |
| family-intraday-microstructure-day | 0.56 |
| ratio-froth | 0.49 |

Range **0.49 .. 0.80**; maximum is `family-short-reversal`. The duplicate threshold is 0.95.

## 9. Static blend at the same average weights

| | CAGR | max DD | Sharpe |
|---|---:|---:|---:|
| strategy 1 bp | 51.12% | 54.81% | 1.10 |
| static average weights | 30.57% | 65.49% | 0.82 |

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
| 8 | `negative_subperiod` | no |
| 9 | `static_blend_matches` | no |

**Verdict: `dev_pass`.**

## 11. Interpretation

The 60-session EEM/QQQ spread is the strongest headline of the four:
**51.12%** CAGR with **54.81%** drawdown at 1 bp, and it still clears the bar at
10 bp (46.94%). All eight plateau cells pass, the placebo is beaten by none
of the 60 draws, and the static 49/51 QQQ/TQQQ blend only makes 30.57%.
The signal is not a repackaged average allocation.

The lookback is load-bearing. The 20-session ablation collapses to 24.5% with
83.9% drawdown: short-horizon EEM/QQQ moves are noise for this purpose. The
family is therefore a **slow macro** overlay, not a fast relative-strength
trade. The 8/8 plateau is a plateau in the normalisation window, threshold and
mapping, not in the lookback.

The two negative years are 2018 (-26.9%) and 2022 (-43.0%), both global
risk-off years. The 2022-2023 subperiod is still positive (11.7%) because
the 2023 recovery more than offsets the 2022 loss. Correlation to the existing
winners reaches 0.80 (`family-short-reversal`), so this is a high-beta cousin
of the TQQQ timing family, not an independent return stream.

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
