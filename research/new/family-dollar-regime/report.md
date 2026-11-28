# Dollar-impulse regime: UUP 60-day impulse -> TQQQ/BIL

**Family:** `dollar regime`  
**Slug:** `family-dollar-regime`  
**Development window:** 2016-01-04 .. 2023-12-29  
**Status:** dev-only; no 2024–2026 result was computed in this study.  The development panel ends 2023-12-29.  `build_weights` accepts a longer panel for a separate one-shot holdout, but no such run is part of this report.

## 1. Hypothesis

The dollar is the price of global dollar liquidity.  When the trade-weighted dollar appreciates sharply, foreign borrowers' dollar liabilities grow, cross-border credit is squeezed, and long-duration US growth equity is vulnerable.  A flat or weaker dollar is the opposite regime: global liquidity is stable or expanding, which is a tailwind for TQQQ.

### Mechanism

The signal is deliberately a *dollar impulse*, not a QQQ trend or volatility state.  UUP tracks the ICE US Dollar Index, a broad basket dominated by EUR, JPY, GBP, CAD, SEK and CHF.  A 60-session log return above +3% is a large move (about the top quintile of the development distribution) and has historically clustered around funding stress, Fed tightening scares and risk-off episodes.  The strategy pays a small whipsaw cost for being in BIL during those episodes and stays long TQQQ otherwise.

### Why this is a distinct family

The primary object is a cross-asset currency impulse.  None of the nine existing winners uses UUP or any FX series as its gate: ratio-froth uses a QQQ/TQQQ ratio, vol-scaled-crash-stop uses realised volatility, relative-value-tqqq uses QQQ/SPY, the event families use calendar or session clocks, and the microstructure families use intraday order flow.  The dollar impulse is an external macro state, not another trend/vol/calendar variant.

## 2. Signal and execution

**External series:** UUP  
**Primary parameters:** `{'W': 60, 'THR': 0.03}`

At the close of session *k*, compute `u60 = log(UUP[k] / UUP[k-60])`.  If `u60 <= 0.030`, the target is TQQQ 1.0; otherwise it is BIL 1.0.  The feature is computed on the external daily calendar with 2015 warmup rows, then reindexed to the QQQ session calendar.  The first session already has a finite 60-day impulse.

**Execution contract.** The target for session *k* is written on the last 1-minute bar of session *k* and filled at the 09:30 open of session *k+1*.  The external close of session *k* is the latest daily print used; no bar after *k* enters the signal.  Idle capital is BIL; the book is long-only, weights ≥ 0, row sum ≤ 1, 2% rebalance band, headline 1 bp, also 5/10 bp.

## 3. Development results

### 3.1 Headline

| Book | CAGR | Max DD | Sharpe | Sortino | Vol | Exposure | Fills | Turnover |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Primary, 1 bp | 41.24% | 72.11% | 0.90 | 1.24 | 55.93% | 100.0% | 131 | 682x |
| Primary, 5 bp | 40.31% | 72.24% | 0.89 | 1.23 | 55.94% | 100.0% | 131 | 660x |
| Primary, 10 bp | 39.17% | 72.41% | 0.88 | 1.21 | 55.95% | 100.0% | 131 | 633x |
| TQQQ buy & hold | 36.15% | 82.29% | 0.80 | 1.12 | 66.55% | 100.0% | 1 | 1x |
| Published dev bar | 36.72% | 82.29% | 0.82 | — | — | — | — | — |

Vol is annualized from 1-minute marks.  Exposure is the invested fraction; BIL and QQQ count as invested, so the TQQQ/BIL/QQQ sleeve split is in section 3.2.  Daily-sampled vol and Sharpe are in `result.json`.

At 1 bp the book returns 41.24% CAGR with a 72.11% max drawdown and Sharpe 0.90; at 10 bp the CAGR is still 39.17%.  TQQQ exposure is 79.9%, so the book is selectively de-risked rather than a permanent BIL overlay.

### 3.2 Activity and exposure

| Metric | Value |
|---|---:|
| Full fills at 1 bp | 131 |
| State switches / independent events | 65 |
| TQQQ entries / exits | 33 / 32 |
| TQQQ holding sessions | 1608 |
| Median TQQQ run | 13.0 sessions |
| Max TQQQ run | 321 sessions |
| TQQQ / BIL / QQQ exposure | 79.9% / 20.1% / 0.0% |
| Activity floor (≥100 fills or ≥30 events) | PASS |

### 3.3 Subperiods (1 bp)

| Subperiod | CAGR | Max DD | Sharpe | Sortino | Fills | TQQQ exposure |
|---|---:|---:|---:|---:|---:|---:|
| 2016-2019 | 54.69% | 53.05% | 1.19 | 1.69 | 63 | 83.4% |
| 2020-2021 | 35.48% | 72.11% | 0.79 | 1.05 | 41 | 90.2% |
| 2022-2023 | 20.35% | 63.81% | 0.62 | 0.88 | 29 | 62.6% |

### 3.4 Yearly returns

| Year | Strategy | TQQQ |
|---|---:|---:|
| 2016 | 52.85% | 18.63% |
| 2017 | 95.81% | 118.35% |
| 2018 | -22.04% | -19.58% |
| 2019 | 144.32% | 133.11% |
| 2020 | 30.55% | 109.61% |
| 2021 | 44.24% | 82.97% |
| 2022 | -48.59% | -79.07% |
| 2023 | 185.36% | 198.37% |

### 3.5 Worst drawdown

Depth **72.11%**, peak 2020-02-19 14:44:00-05:00, trough 2020-04-13 11:08:00-04:00, recovery 2021-01-20 09:30:00-05:00.

## 4. Robustness

### 4.1 Eight-cell plateau

| Cell | CAGR | Max DD | Sharpe | Fills | TQQQ exposure | 3-way bar |
|---|---:|---:|---:|---:|---:|---|
| W=60, THR=0.02 | 36.42% | 64.33% | 0.87 | 255 | 68.3% | fail |
| W=60, THR=0.025 | 38.03% | 64.57% | 0.88 | 207 | 75.0% | PASS |
| W=60, THR=0.03 | 41.24% | 72.11% | 0.90 | 131 | 79.9% | PASS |
| W=60, THR=0.035 | 39.86% | 71.66% | 0.88 | 109 | 83.6% | PASS |
| W=60, THR=0.04 | 40.28% | 71.66% | 0.87 | 101 | 86.9% | PASS |
| W=20, THR=0.03 | 35.78% | 77.54% | 0.81 | 133 | 94.3% | fail |
| W=40, THR=0.03 | 38.08% | 71.66% | 0.84 | 153 | 86.4% | PASS |
| W=80, THR=0.03 | 45.12% | 67.27% | 0.96 | 213 | 73.6% | PASS |

**Plateau:** 6/8 cells clear the three-way dev bar (CAGR > 36.72%, DD < 82.29%, Sharpe > 0.82).

The plateau is a local cross: five thresholds at the 60-session window plus three nearby windows at the 3% threshold.  The 3.0-4.0% cells all clear the bar; the 2.0% and 2.5% cells do not.  The signal therefore has a usable plateau but is not threshold-insensitive at the low end.

### 4.2 Placebo / randomized signal dates

| Null | Mean CAGR | Median | 5th pct | 95th pct | True | Percentile | One-sided p |
|---|---:|---:|---:|---:|---:|---:|---:|
| Circular shift of target | 27.15% | 27.38% | 12.70% | 43.17% | 41.24% | 0.92 | 0.089 |
| Circular shift of primary feature | 27.19% | 26.42% | 12.52% | 44.84% | 41.24% | 0.90 | 0.109 |

The circular-shift nulls preserve the holding-length distribution and the marginal distribution of the dollar impulse.  The true CAGR sits near the 90th percentile of the target-shift null and near the 80th percentile of the feature-shift null.  The evidence is suggestive, not overwhelming: a 100-draw placebo on eight years of daily regimes has limited power.

### 4.3 Correlation with the nine existing winners

| Winner | Correlation | n |
|---|---:|---:|
| `relative-value-tqqq` | 0.836 | 2011 |
| `family-rebalance-flow` | 0.781 | 2011 |
| `family-ml-microstructure` | 0.764 | 2011 |
| `family-short-reversal` | 0.718 | 2011 |
| `vol-scaled-crash-stop` | 0.695 | 2011 |
| `ratio-froth` | 0.640 | 2011 |
| `family-session-timing` | 0.618 | 2011 |
| `fomc-opex-window` | 0.557 | 2011 |
| `family-intraday-microstructure-day` | 0.502 | 2011 |

Range **0.502 .. 0.836** (mean 0.679); highest with `relative-value-tqqq`.  Correlation with TQQQ itself is **0.842** (beta 0.70).

The book is still a long-TQQQ risk-on book most of the time, so it correlates with the existing risk-on winners.  The highest link is with `relative-value-tqqq`, which also rotates equity exposure; the dollar gate itself is distinct.  A correlation above 0.85 would have triggered the redundancy kill criterion.

## 5. Kill criteria

| # | Criterion | Observed | Triggered |
|---|---|---|---|
| 1 | Activity floor: >=100 full fills or >=30 independent events | 131 fills; 65 state switches | no |
| 2 | No three-way dev improvement over TQQQ buy & hold | CAGR 41.24% vs 36.15%; DD 72.11% vs 82.29%; Sharpe 0.90 vs 0.80 | no |
| 3 | Plateau: >=5 of 8 local cells clear the three-way dev bar | 6/8 cells pass | no |
| 4 | Placebo: one-sided p <= 0.20 for at least one circular-shift null | target p=0.089; feature p=0.109 | no |
| 5 | Redundancy: maximum correlation with an existing winner <= 0.85 | 0.836 (relative-value-tqqq) | no |
| 6 | Subperiod: no negative-CAGR development subperiod | none | no |

**0 of 6 kill criteria triggered.**

## 6. Honest verdict

This is a solid dev candidate, not a verified winner.  It clears the bar and the activity floor, has a 6/8 plateau, and positive returns in all three subperiods.  The caveats are real: the edge is concentrated in 2016-19, the 2022-23 subperiod only returns 20.4%, the 2.0-2.5% threshold cells fail, and correlation with `relative-value-tqqq` is 0.836.  The one-shot holdout is the only way to know whether the dollar impulse survives.

## 7. Limitations and next steps

UUP is a fund with its own expenses and tracking error, and the daily close is a 16:00 print while the target is written at 15:59; the one-minute gap is the same convention used by the rest of the programme.  The 60-day impulse is a slow signal and can be late at turning points.  The development window contains only one major dollar cycle (2016-2023), so the threshold is not estimated on a long sample.  The next step is a frozen one-shot 2024-2026 holdout and a check of the dollar impulse against a trade-weighted Fed broad index (not just UUP) before any promotion.

## 8. Reproduction

```powershell
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
$env:BT_THREADS = "1"
python research/new/family-dollar-regime/strategy.py
```

The script rebuilds `result.json` and this report from the development window only.
