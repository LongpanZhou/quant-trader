# MOVE rates-volatility regime -- report

**Slug:** `family-rates-volatility`  
**Family:** `rates-volatility`  
**Window:** 2016-01-04 -> 2023-12-29, development only. The 2024-2026 holdout was not loaded.  
**Execution:** `research/bt.py`, 1-minute marks, next-open fills, 2% band, long-only, weights >= 0, sum <= 1. Headline 1 bp; 5 bp and 10 bp also reported.  
**Primary:** MOVE rates-volatility level (20-session change as ablation).  
**Verdict:** `dev_pass`  

**Verdict: `dev_pass`.** The primary earns **41.71% CAGR / 38.33% max DD / 1.18 Sharpe** at 1 bp, above the published TQQQ bar (36.72% / 82.29% / 0.82) with a lower drawdown. It is a development-only result; 2024-2026 is untouched.

---

## 1. Headline

| cost | CAGR | max DD | Sharpe | Sortino | vol | exposure | fills | turnover |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **1 bp** | 41.71% | 38.33% | 1.18 | 1.66 | 34.84% | 99.95% | 233 | 1,635x |
| 5 bp | 40.07% | 38.33% | 1.15 | 1.61 | 34.83% | 99.95% | 233 | 1,529x |
| 10 bp | 38.04% | 38.33% | 1.10 | 1.55 | 34.82% | 99.95% | 233 | 1,407x |

The stated bar is TQQQ **36.72% CAGR / 82.29% max DD / 0.82 Sharpe**. The local 1-minute benchmark is 36.15% / 82.29% / 0.80. Ending equity at 1 bp is **$1,617,473** from $100,000. There are **117** distinct fill events.

Average target weights: QQQ 0.0%, TQQQ 48.4%, BIL 51.6%.

## 2. Benchmarks

| | CAGR | max DD | Sharpe | vol |
|---|---:|---:|---:|---:|
| primary 1 bp | 41.71% | 38.33% | 1.18 | 34.84% |
| TQQQ | 36.15% | 82.29% | 0.80 | 66.55% |
| QQQ | 18.91% | 37.30% | 0.90 | 22.02% |

## 3. Yearly returns

| year | strategy | TQQQ | QQQ |
|---|---:|---:|---:|
| 2016 | -14.8% | 18.6% | 9.3% |
| 2017 | 68.7% | 113.0% | 31.5% |
| 2018 | 50.8% | -23.5% | -1.8% |
| 2019 | 47.6% | 130.5% | 38.4% |
| 2020 | 212.1% | 99.8% | 45.9% |
| 2021 | 11.9% | 90.9% | 29.2% |
| 2022 | -7.8% | -79.7% | -33.2% |
| 2023 | 51.7% | 204.9% | 55.9% |

## 4. Subperiods

| period | strategy CAGR | strategy DD | Sharpe | TQQQ CAGR | TQQQ DD |
|---|---:|---:|---:|---:|---:|
| 2016-2019 | 35.55% | 31.04% | 1.17 | 48.60% | 57.97% |
| 2020-2021 | 83.18% | 35.38% | 1.61 | 91.47% | 69.89% |
| 2022-2023 | 17.15% | 30.89% | 0.65 | -22.33% | 81.05% |

## 5. Eight-cell plateau

| # | params | CAGR | max DD | Sharpe | fills | pass |
|---:|---|---:|---:|---:|---:|---|
| 1 | measure=level, median_window=126, threshold=0.0, mapping=binary | 28.78% | 50.87% | 0.90 | 301 | no |
| 2 | measure=level, median_window=126, threshold=0.0, mapping=ladder | 32.67% | 56.10% | 0.95 | 463 | no |
| 3 | measure=level, median_window=126, threshold=0.2, mapping=binary | 34.27% | 71.15% | 0.84 | 165 | no |
| 4 | measure=level, median_window=126, threshold=0.2, mapping=ladder | 37.28% | 68.97% | 0.87 | 257 | yes |
| 5 | measure=level, median_window=252, threshold=0.0, mapping=binary | 41.71% | 38.33% | 1.18 | 233 | yes |
| 6 | measure=level, median_window=252, threshold=0.0, mapping=ladder | 46.02% | 38.33% | 1.22 | 377 | yes |
| 7 | measure=level, median_window=252, threshold=0.2, mapping=binary | 49.47% | 56.69% | 1.08 | 145 | yes |
| 8 | measure=level, median_window=252, threshold=0.2, mapping=ladder | 46.29% | 55.71% | 1.02 | 261 | yes |

**5 of 8 cells pass** (62%). The plateau rule requires at least 5 of 8.

## 6. Ablations

| params | CAGR | max DD | Sharpe | fills | pass |
|---|---:|---:|---:|---:|---|
| measure=chg20, median_window=252, threshold=0.0, mapping=binary | 31.94% | 66.21% | 0.88 | 409 | no |
| measure=chg20, median_window=252, threshold=0.0, mapping=ladder | 28.71% | 70.89% | 0.81 | 707 | no |

## 7. Placebo

Circular shifts of the daily target sequence preserve the allocation path and exposure but destroy its alignment with returns.

| draws | CAGR p05 | CAGR p50 | CAGR p95 | CAGR max | real percentile | DD p50 |
|---:|---:|---:|---:|---:|---:|---:|
| 60 | -1.68% | 17.91% | 32.90% | 35.72% | 100% | 72.74% |

Sharpe percentile of the real result: 100%.

## 8. Correlation to the nine winners

| winner | correlation |
|---|---:|
| vol-scaled-crash-stop | 0.57 |
| family-rebalance-flow | 0.56 |
| relative-value-tqqq | 0.56 |
| family-ml-microstructure | 0.50 |
| ratio-froth | 0.48 |
| family-session-timing | 0.41 |
| fomc-opex-window | 0.40 |
| family-intraday-microstructure-day | 0.33 |
| family-short-reversal | 0.33 |

Range **0.33 .. 0.57**; maximum is `vol-scaled-crash-stop`. The duplicate threshold is 0.95.

## 9. Static blend at the same average weights

| | CAGR | max DD | Sharpe |
|---|---:|---:|---:|
| strategy 1 bp | 41.71% | 38.33% | 1.18 |
| static average weights | 23.70% | 51.87% | 0.82 |

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

The MOVE level is the strongest of the four reserve signals. The primary holds
TQQQ only when rates volatility is below its own one-year median and sits in
BIL otherwise. Over 2016-2023 it compounds at **41.71%** with a **38.33%**
maximum drawdown, versus TQQQ's 36.15% / 82.29%. It survives 10 bp
(38.04%), the circular-shift placebo is beaten by none of the 60 draws, and
the static 48/52 TQQQ/BIL blend at the strategy's own average weights only
makes 23.70%. The timing is doing the work.

The weakness is the plateau's 126-session window: those four cells are weaker
than the 252-session cells, and three of the four fail. The 20-session change
is a genuinely worse object: it loses roughly 10 pp of
CAGR after next-open execution and fails at every cost. So the family is a
**level** strategy, not a rates-momentum strategy. The five passing cells are
enough for the house 5/8 plateau rule, but the result is not uniformly robust.

2016 and 2022 are the negative years (-14.8% and -7.8%). The 2016 rate
scare produced repeated MOVE spikes while the equity market recovered, so the
binary BIL rung whipsawed; 2022 was a sustained rates-vol bear market that the
signal caught late. The three subperiods are all positive, and the worst
drawdown is 38.3% rather than TQQQ's 82.3%, so the family is a credible
low-drawdown reserve rather than a return-maximising one.

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
