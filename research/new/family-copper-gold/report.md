# CPER/GLD copper-gold relative momentum -- report

**Slug:** `family-copper-gold`  
**Family:** `copper-gold`  
**Window:** 2016-01-04 -> 2023-12-29, development only. The 2024-2026 holdout was not loaded.  
**Execution:** `research/bt.py`, 1-minute marks, next-open fills, 2% band, long-only, weights >= 0, sum <= 1. Headline 1 bp; 5 bp and 10 bp also reported.  
**Primary:** CPER/GLD 60-session relative total-return z-score.  
**Verdict:** `fail`  

**Verdict: `fail`.** The primary earns **32.74% CAGR / 73.53% max DD / 0.82 Sharpe** at 1 bp, below the published TQQQ bar (36.72% / 82.29%). This is a negative result, reported in full; 2024-2026 is untouched.

---

## 1. Headline

| cost | CAGR | max DD | Sharpe | Sortino | vol | exposure | fills | turnover |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **1 bp** | 32.74% | 73.53% | 0.82 | 1.17 | 49.52% | 99.95% | 253 | 1,139x |
| 5 bp | 31.07% | 73.87% | 0.80 | 1.13 | 49.52% | 99.95% | 253 | 1,062x |
| 10 bp | 29.01% | 74.28% | 0.76 | 1.09 | 49.52% | 99.95% | 253 | 974x |

The stated bar is TQQQ **36.72% CAGR / 82.29% max DD / 0.82 Sharpe**. The local 1-minute benchmark is 36.15% / 82.29% / 0.80. Ending equity at 1 bp is **$959,868** from $100,000. There are **127** distinct fill events.

Average target weights: QQQ 34.8%, TQQQ 65.2%, BIL 0.0%.

## 2. Benchmarks

| | CAGR | max DD | Sharpe | vol |
|---|---:|---:|---:|---:|
| primary 1 bp | 32.74% | 73.53% | 0.82 | 49.52% |
| TQQQ | 36.15% | 82.29% | 0.80 | 66.55% |
| QQQ | 18.91% | 37.30% | 0.90 | 22.02% |

## 3. Yearly returns

| year | strategy | TQQQ | QQQ |
|---|---:|---:|---:|
| 2016 | 2.9% | 18.6% | 9.3% |
| 2017 | 109.1% | 113.0% | 31.5% |
| 2018 | -10.4% | -23.5% | -1.8% |
| 2019 | 69.4% | 130.5% | 38.4% |
| 2020 | 131.6% | 99.8% | 45.9% |
| 2021 | 73.4% | 90.9% | 29.2% |
| 2022 | -69.7% | -79.7% | -33.2% |
| 2023 | 119.8% | 204.9% | 55.9% |

## 4. Subperiods

| period | strategy CAGR | strategy DD | Sharpe | TQQQ CAGR | TQQQ DD |
|---|---:|---:|---:|---:|---:|
| 2016-2019 | 37.21% | 49.13% | 1.06 | 48.60% | 57.97% |
| 2020-2021 | 96.47% | 35.38% | 1.44 | 91.47% | 69.89% |
| 2022-2023 | -19.35% | 71.67% | -0.02 | -22.33% | 81.05% |

## 5. Eight-cell plateau

| # | params | CAGR | max DD | Sharpe | fills | pass |
|---:|---|---:|---:|---:|---:|---|
| 1 | lookback=60, norm_window=126, threshold=-0.75, mapping=binary | 33.55% | 76.50% | 0.83 | 245 | no |
| 2 | lookback=60, norm_window=126, threshold=-0.5, mapping=binary | 28.18% | 77.49% | 0.76 | 305 | no |
| 3 | lookback=60, norm_window=126, threshold=-0.75, mapping=ladder | 31.11% | 73.88% | 0.81 | 415 | no |
| 4 | lookback=60, norm_window=126, threshold=-0.5, mapping=ladder | 22.09% | 77.48% | 0.67 | 489 | no |
| 5 | lookback=60, norm_window=252, threshold=-0.75, mapping=binary | 33.06% | 76.56% | 0.81 | 217 | no |
| 6 | lookback=60, norm_window=252, threshold=-0.5, mapping=binary | 32.74% | 73.53% | 0.82 | 253 | no |
| 7 | lookback=60, norm_window=252, threshold=-0.75, mapping=ladder | 29.12% | 78.12% | 0.76 | 373 | no |
| 8 | lookback=60, norm_window=252, threshold=-0.5, mapping=ladder | 28.14% | 73.83% | 0.76 | 403 | no |

**0 of 8 cells pass** (0%). The plateau rule requires at least 5 of 8.

## 6. Ablations

| params | CAGR | max DD | Sharpe | fills | pass |
|---|---:|---:|---:|---:|---|
| lookback=20, norm_window=252, threshold=-0.5, mapping=binary | 29.81% | 83.00% | 0.77 | 373 | no |
| lookback=20, norm_window=252, threshold=-0.75, mapping=binary | 35.71% | 80.06% | 0.84 | 297 | no |

## 7. Placebo

Circular shifts of the daily target sequence preserve the allocation path and exposure but destroy its alignment with returns.

| draws | CAGR p05 | CAGR p50 | CAGR p95 | CAGR max | real percentile | DD p50 |
|---:|---:|---:|---:|---:|---:|---:|
| 60 | 16.16% | 28.98% | 40.65% | 45.08% | 62% | 75.60% |

Sharpe percentile of the real result: 72%.

## 8. Correlation to the nine winners

| winner | correlation |
|---|---:|
| relative-value-tqqq | 0.85 |
| family-rebalance-flow | 0.84 |
| family-short-reversal | 0.78 |
| family-ml-microstructure | 0.78 |
| vol-scaled-crash-stop | 0.75 |
| family-session-timing | 0.68 |
| fomc-opex-window | 0.67 |
| ratio-froth | 0.61 |
| family-intraday-microstructure-day | 0.55 |

Range **0.55 .. 0.85**; maximum is `relative-value-tqqq`. The duplicate threshold is 0.95.

## 9. Static blend at the same average weights

| | CAGR | max DD | Sharpe |
|---|---:|---:|---:|
| strategy 1 bp | 32.74% | 73.53% | 0.82 |
| static average weights | 32.73% | 71.21% | 0.81 |

## 10. Kill criteria -- verdict

| # | criterion | triggered? |
|---:|---|---|
| 1 | `cagr_1bp_below_tqqq_bar` | **yes** |
| 2 | `drawdown_1bp_above_tqqq` | no |
| 3 | `cagr_10bp_below_tqqq_bar` | **yes** |
| 4 | `plateau_below_5_of_8` | **yes** |
| 5 | `placebo_below_90th` | **yes** |
| 6 | `winner_correlation_above_0.95` | no |
| 7 | `fewer_than_100_fills_and_30_events` | no |
| 8 | `negative_subperiod` | **yes** |
| 9 | `static_blend_matches` | **yes** |

**Verdict: `fail`.**

## 11. Interpretation

The copper/gold family is a clean negative. The primary makes **32.74%** at
1 bp, below TQQQ's 36.72%, with a **73.53%** drawdown. None of the eight plateau
cells passes, the 10 bp result is 29.01%, the placebo is only at the 62%
percentile, the static 35/65 QQQ/TQQQ blend matches the strategy, and the
2022-2023 subperiod is negative (-19.4%). Six of the nine kill criteria
trigger.

The best cell is the 126-session / -0.75 / binary variant at 33.55%, still
3.2 pp below the bar. The 20-session ablation is no better (29.8-35.7%). The
copper/gold ratio is a slow, noisy macro object; over 2016-2023 it does not
add usable timing information to a 3x Nasdaq sleeve. That is a useful
negative result: it closes off a plausible-sounding cross-asset idea rather
than hiding it in a parameter search.

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
