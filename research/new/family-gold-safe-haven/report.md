# Gold safe-haven shock: GLD 5-day impulse -> TQQQ/BIL

**Family:** `gold safe haven`  
**Slug:** `family-gold-safe-haven`  
**Development window:** 2016-01-04 .. 2023-12-29  
**Status:** dev-only; no 2024–2026 result was computed in this study.  The development panel ends 2023-12-29.  `build_weights` accepts a longer panel for a separate one-shot holdout, but no such run is part of this report.

## 1. Hypothesis

Gold is the oldest safe-haven asset.  A fast, large gold rally is a market signal that demand for safety or a real-rate hedge has risen.  If that demand is genuine, equity risk should be reduced for a short window; if gold is quiet, the fear premium is low and TQQQ can be held.

### Mechanism

The primary object is a *gold shock*: the five-session log return of GLD above +3.5%.  This is deliberately short-horizon.  A 20-session gold trend is a different object (a gold bull/bear trend) and is not used.  The event triggers a three-session BIL hold, which covers the event session and the next two; overlapping events extend the hold.  The signal is absolute GLD momentum, not GLD/QQQ relative strength, so it does not duplicate the existing QQQ/SPY relative-value family.

### Why this is a distinct family

No existing winner uses gold, a safe-haven commodity, as its primary gate.  The event families use FOMC/OpEx dates, the session families use intraday clocks, the trend families use QQQ or TQQQ price, and the volatility families use realised or implied vol.  A fast GLD impulse is a distinct cross-asset fear state.

## 2. Signal and execution

**External series:** GLD  
**Primary parameters:** `{'W': 5, 'THR': 0.035, 'HOLD': 3}`

At the close of session *k*, compute `g5 = log(GLD[k] / GLD[k-5])`.  If `g5 > 0.035`, mark an event.  The book is BIL for the event session and the next two sessions (`event[k] or event[k-1] or event[k-2]`), otherwise TQQQ.  The feature uses 2015 warmup rows and is reindexed to the QQQ session calendar.

**Execution contract.** The target for session *k* is written on the last 1-minute bar of session *k* and filled at the 09:30 open of session *k+1*.  The external close of session *k* is the latest daily print used; no bar after *k* enters the signal.  Idle capital is BIL; the book is long-only, weights ≥ 0, row sum ≤ 1, 2% rebalance band, headline 1 bp, also 5/10 bp.

## 3. Development results

### 3.1 Headline

| Book | CAGR | Max DD | Sharpe | Sortino | Vol | Exposure | Fills | Turnover |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Primary, 1 bp | 42.91% | 74.90% | 0.89 | 1.25 | 61.41% | 100.0% | 121 | 796x |
| Primary, 5 bp | 42.05% | 74.98% | 0.88 | 1.23 | 61.41% | 100.0% | 121 | 771x |
| Primary, 10 bp | 40.98% | 75.08% | 0.87 | 1.21 | 61.41% | 100.0% | 121 | 741x |
| TQQQ buy & hold | 36.15% | 82.29% | 0.80 | 1.12 | 66.55% | 100.0% | 1 | 1x |
| Published dev bar | 36.72% | 82.29% | 0.82 | — | — | — | — | — |

The primary returns 42.91% CAGR at 1 bp with a 74.90% drawdown and Sharpe 0.89.  It is in TQQQ 92.6% of sessions, so the gold shock is a sparse overlay.  The 2022-23 subperiod is the problem: -9.0% CAGR, because gold shocks in 2022 were not reliable equity risk-off signals.

### 3.2 Activity and exposure

| Metric | Value |
|---|---:|
| Full fills at 1 bp | 121 |
| State switches / independent events | 60 |
| TQQQ entries / exits | 31 / 30 |
| TQQQ holding sessions | 1863 |
| Median TQQQ run | 26.0 sessions |
| Max TQQQ run | 551 sessions |
| TQQQ / BIL / QQQ exposure | 92.6% / 7.4% / 0.0% |
| Activity floor (≥100 fills or ≥30 events) | PASS |

### 3.3 Subperiods (1 bp)

| Subperiod | CAGR | Max DD | Sharpe | Sortino | Fills | TQQQ exposure |
|---|---:|---:|---:|---:|---:|---:|
| 2016-2019 | 44.28% | 58.62% | 1.00 | 1.41 | 37 | 95.0% |
| 2020-2021 | 115.52% | 58.20% | 1.42 | 1.93 | 53 | 88.3% |
| 2022-2023 | -8.98% | 74.90% | 0.22 | 0.31 | 33 | 91.8% |

### 3.4 Yearly returns

| Year | Strategy | TQQQ |
|---|---:|---:|
| 2016 | 17.49% | 18.63% |
| 2017 | 119.21% | 118.35% |
| 2018 | -19.58% | -19.58% |
| 2019 | 108.45% | 133.11% |
| 2020 | 160.30% | 109.61% |
| 2021 | 82.77% | 82.97% |
| 2022 | -69.75% | -79.07% |
| 2023 | 178.51% | 198.37% |

### 3.5 Worst drawdown

Depth **74.90%**, peak 2022-03-29 15:35:00-04:00, trough 2022-12-28 15:45:00-05:00, recovery not recovered in dev.

## 4. Robustness

### 4.1 Eight-cell plateau

| Cell | CAGR | Max DD | Sharpe | Fills | TQQQ exposure | 3-way bar |
|---|---:|---:|---:|---:|---:|---|
| W=5, THR=0.03, HOLD=3 | 36.86% | 74.64% | 0.83 | 169 | 89.0% | PASS |
| W=5, THR=0.035, HOLD=3 | 42.91% | 74.90% | 0.89 | 121 | 92.5% | PASS |
| W=5, THR=0.04, HOLD=3 | 39.39% | 82.01% | 0.85 | 93 | 94.8% | PASS |
| W=5, THR=0.045, HOLD=3 | 39.27% | 79.51% | 0.85 | 81 | 95.8% | PASS |
| W=5, THR=0.03, HOLD=4 | 28.97% | 79.05% | 0.73 | 169 | 86.9% | fail |
| W=5, THR=0.035, HOLD=4 | 38.26% | 78.25% | 0.84 | 113 | 91.0% | PASS |
| W=5, THR=0.04, HOLD=4 | 40.78% | 79.67% | 0.87 | 89 | 93.7% | PASS |
| W=5, THR=0.045, HOLD=4 | 45.15% | 76.84% | 0.92 | 77 | 94.8% | PASS |

**Plateau:** 7/8 cells clear the three-way dev bar (CAGR > 36.72%, DD < 82.29%, Sharpe > 0.82).

The plateau varies the two parameters that define the shock, threshold and hold, at the hypothesised five-session lookback.  7/8 local cells clear the bar; only the 3.0%/4-session cell fails.  The local plateau is therefore broad, but the extra horizon table is a warning: a 10- or 20-session gold window is a different, much weaker signal.

### 4.2 Additional checks

**horizon (THR=3.5%, HOLD=3)**

| Item | CAGR | Max DD | Sharpe | Fills |
|---|---:|---:|---:|---:|
| W=3 | 29.94% | 82.13% | 0.73 | 77 |
| W=10 | 9.63% | 82.03% | 0.46 | 163 |
| W=20 | 3.78% | 83.42% | 0.34 | 169 |

### 4.3 Placebo / randomized signal dates

| Null | Mean CAGR | Median | 5th pct | 95th pct | True | Percentile | One-sided p |
|---|---:|---:|---:|---:|---:|---:|---:|
| Circular shift of target | 34.83% | 33.54% | 22.63% | 49.00% | 42.91% | 0.87 | 0.139 |
| Circular shift of primary feature | 32.24% | 31.87% | 18.51% | 49.87% | 42.91% | 0.91 | 0.099 |

The true CAGR is around the 88th percentile of both circular-shift nulls.  The placebo does not reject the signal, but it does not establish it either; with 100 draws and a sparse event process, the p-values are only indicative.

### 4.4 Correlation with the nine existing winners

| Winner | Correlation | n |
|---|---:|---:|
| `relative-value-tqqq` | 0.845 | 2011 |
| `family-rebalance-flow` | 0.835 | 2011 |
| `family-short-reversal` | 0.812 | 2011 |
| `family-ml-microstructure` | 0.797 | 2011 |
| `vol-scaled-crash-stop` | 0.760 | 2011 |
| `family-session-timing` | 0.674 | 2011 |
| `fomc-opex-window` | 0.619 | 2011 |
| `ratio-froth` | 0.588 | 2011 |
| `family-intraday-microstructure-day` | 0.572 | 2011 |

Range **0.572 .. 0.845** (mean 0.723); highest with `relative-value-tqqq`.  Correlation with TQQQ itself is **0.914** (beta 0.84).

The book is long TQQQ most of the time and therefore shares the existing risk-on exposure.  The highest correlation is near the 0.85 redundancy line; the gold gate is distinct, but the return stream is not very independent.

## 5. Kill criteria

| # | Criterion | Observed | Triggered |
|---|---|---|---|
| 1 | Activity floor: >=100 full fills or >=30 independent events | 121 fills; 60 state switches | no |
| 2 | No three-way dev improvement over TQQQ buy & hold | CAGR 42.91% vs 36.15%; DD 74.90% vs 82.29%; Sharpe 0.89 vs 0.80 | no |
| 3 | Plateau: >=5 of 8 local cells clear the three-way dev bar | 7/8 cells pass | no |
| 4 | Placebo: one-sided p <= 0.20 for at least one circular-shift null | target p=0.139; feature p=0.099 | no |
| 5 | Redundancy: maximum correlation with an existing winner <= 0.85 | 0.845 (relative-value-tqqq) | no |
| 6 | Subperiod: no negative-CAGR development subperiod | 2022-2023 -8.98% | YES |

**1 of 6 kill criteria triggered.**

## 6. Honest verdict

**Reject as a standalone winner.**  The 1 bp headline looks good, but the result is not robust where it matters: the 2022-23 subperiod loses money, the five-session horizon is essential (10- and 20-session windows collapse to 9.6% and 3.8% CAGR), and correlation with the existing winners is near the redundancy threshold.  A safe-haven signal that fails in the one inflationary bear market in the sample is not a reliable hedge.

## 7. Limitations and next steps

GLD is an ETF with expense and tracking error; the daily close is a 16:00 print used at the 15:59 target write, the programme's standard convention.  The event definition uses only price, not gold ETF flows, real yields or the VIX, so it cannot distinguish a genuine flight to safety from a commodity supply shock.  The 2022 failure suggests the signal should be conditioned on the sign of the stock-bond correlation or on real yields, but that would add a second primary object and is outside this family.

## 8. Reproduction

```powershell
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
$env:BT_THREADS = "1"
python research/new/family-gold-safe-haven/strategy.py
```

The script rebuilds `result.json` and this report from the development window only.
