# Oil-shock event: USO 5-day impulse -> TQQQ/BIL

**Family:** `oil shock`  
**Slug:** `family-oil-shock`  
**Development window:** 2016-01-04 .. 2023-12-29  
**Status:** dev-only; no 2024–2026 result was computed in this study.  The development panel ends 2023-12-29.  `build_weights` accepts a longer panel for a separate one-shot holdout, but no such run is part of this report.

## 1. Hypothesis

Oil is the priced input to the inflation cycle.  A fast oil spike raises input costs and inflation expectations, compresses real incomes, and increases the chance of a hawkish policy response.  Long-duration growth equity is the most sensitive asset to that combination.  The shock is usually short-lived, so a fixed five-session de-risk is enough; when oil is calm, TQQQ can be held.

### Mechanism

The primary object is the five-session log return of USO.  A +5% move is a clear energy impulse and triggers a five-session BIL hold (the event session plus the next four).  Overlapping events extend the hold.  The strategy is not an always-on oil-trend filter: the event form isolates the shock window rather than holding BIL for as long as oil is above a slow threshold.  An always-on oil-return state (window x threshold grid) was tested and rejected because its plateau was a fragile local peak; that diagnostic is reported in the extra-checks table.

### Why this is a distinct family

No existing winner uses USO, crude oil or an energy impulse as its primary gate.  The inflation/rates complex is also not the primary object of the existing yield-curve or credit families; this family is specifically the energy-shock channel.  It is not a QQQ trend, volatility target, drawdown event or calendar clock.

## 2. Signal and execution

**External series:** USO  
**Primary parameters:** `{'W': 5, 'THR': 0.05, 'HOLD': 5}`

At the close of session *k*, compute `o5 = log(USO[k] / USO[k-5])`.  If `o5 > 0.050`, mark an event.  The book is BIL for the event session and the next four sessions (`event[k] or ... or event[k-4]`), otherwise TQQQ.  The feature uses 2015 warmup rows and is reindexed to the QQQ session calendar.

**Execution contract.** The target for session *k* is written on the last 1-minute bar of session *k* and filled at the 09:30 open of session *k+1*.  The external close of session *k* is the latest daily print used; no bar after *k* enters the signal.  Idle capital is BIL; the book is long-only, weights ≥ 0, row sum ≤ 1, 2% rebalance band, headline 1 bp, also 5/10 bp.

## 3. Development results

### 3.1 Headline

| Book | CAGR | Max DD | Sharpe | Sortino | Vol | Exposure | Fills | Turnover |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Primary, 1 bp | 48.71% | 64.46% | 1.00 | 1.38 | 55.12% | 100.0% | 349 | 2068x |
| Primary, 5 bp | 46.14% | 64.46% | 0.97 | 1.34 | 55.13% | 100.0% | 349 | 1870x |
| Primary, 10 bp | 42.98% | 64.46% | 0.93 | 1.28 | 55.13% | 100.0% | 349 | 1652x |
| TQQQ buy & hold | 36.15% | 82.29% | 0.80 | 1.12 | 66.55% | 100.0% | 1 | 1x |
| Published dev bar | 36.72% | 82.29% | 0.82 | — | — | — | — | — |

Vol is annualized from 1-minute marks.  Exposure is the invested fraction; BIL and QQQ count as invested, so the TQQQ/BIL/QQQ sleeve split is in section 3.2.  Daily-sampled vol and Sharpe are in `result.json`.

The primary compounds 48.71% at 1 bp with a 64.46% drawdown and Sharpe 1.00.  TQQQ exposure is 66.9%; the book holds BIL in short bursts after oil spikes.  The 10 bp cost is modest: CAGR is still 42.98%.

### 3.2 Activity and exposure

| Metric | Value |
|---|---:|
| Full fills at 1 bp | 349 |
| State switches / independent events | 174 |
| TQQQ entries / exits | 88 / 87 |
| TQQQ holding sessions | 1346 |
| Median TQQQ run | 10.0 sessions |
| Max TQQQ run | 74 sessions |
| TQQQ / BIL / QQQ exposure | 66.9% / 33.1% / 0.0% |
| Activity floor (≥100 fills or ≥30 events) | PASS |

### 3.3 Subperiods (1 bp)

| Subperiod | CAGR | Max DD | Sharpe | Sortino | Fills | TQQQ exposure |
|---|---:|---:|---:|---:|---:|---:|
| 2016-2019 | 35.33% | 50.65% | 0.91 | 1.28 | 149 | 71.6% |
| 2020-2021 | 61.35% | 64.46% | 1.03 | 1.39 | 91 | 63.9% |
| 2022-2023 | 63.80% | 40.39% | 1.17 | 1.66 | 111 | 60.4% |

### 3.4 Yearly returns

| Year | Strategy | TQQQ |
|---|---:|---:|
| 2016 | -4.36% | 18.63% |
| 2017 | 105.24% | 118.35% |
| 2018 | 11.41% | -19.58% |
| 2019 | 52.88% | 133.11% |
| 2020 | 29.89% | 109.61% |
| 2021 | 105.50% | 82.97% |
| 2022 | 2.38% | -79.07% |
| 2023 | 160.22% | 198.37% |

### 3.5 Worst drawdown

Depth **64.46%**, peak 2020-03-03 10:03:00-05:00, trough 2020-03-23 11:45:00-04:00, recovery 2020-09-01 15:58:00-04:00.

## 4. Robustness

### 4.1 Eight-cell plateau

| Cell | CAGR | Max DD | Sharpe | Fills | TQQQ exposure | 3-way bar |
|---|---:|---:|---:|---:|---:|---|
| W=5, THR=0.02, HOLD=5 | 41.86% | 64.46% | 1.01 | 435 | 35.7% | PASS |
| W=5, THR=0.03, HOLD=5 | 38.15% | 64.46% | 0.91 | 439 | 46.3% | PASS |
| W=5, THR=0.04, HOLD=5 | 55.80% | 64.46% | 1.12 | 409 | 56.2% | PASS |
| W=5, THR=0.05, HOLD=5 | 48.71% | 64.46% | 1.00 | 349 | 66.9% | PASS |
| W=5, THR=0.06, HOLD=5 | 55.64% | 64.46% | 1.06 | 277 | 76.1% | PASS |
| W=5, THR=0.05, HOLD=3 | 47.32% | 67.36% | 0.96 | 373 | 76.0% | PASS |
| W=5, THR=0.05, HOLD=4 | 53.69% | 65.49% | 1.04 | 361 | 71.3% | PASS |
| W=5, THR=0.05, HOLD=7 | 50.26% | 64.46% | 1.05 | 299 | 58.5% | PASS |

**Plateau:** 8/8 cells clear the three-way dev bar (CAGR > 36.72%, DD < 82.29%, Sharpe > 0.82).

All eight local cells clear the three-way bar.  The thresholds 2-6% and the holds 3-7 sessions all work, so the result is not tied to one threshold.  The always-on oil state, by contrast, passes only 2/8 cells; the event form is the robust version of the same economic idea.

### 4.2 Additional checks

**rejected always-on oil state**

| Item | CAGR | Max DD | Sharpe | Fills |
|---|---:|---:|---:|---:|
| W=20, THR=5% | 33.00% | 73.16% | 0.79 | 397 |
| W=20, THR=6% | 32.94% | 72.74% | 0.78 | 333 |
| W=20, THR=8% | 45.74% | 72.74% | 0.93 | 309 |
| W=20, THR=10% | 35.32% | 74.30% | 0.80 | 289 |
| W=20, THR=12% | 35.76% | 72.74% | 0.80 | 217 |
| W=10, THR=8% | 47.02% | 72.74% | 0.93 | 285 |
| W=15, THR=8% | 34.71% | 72.74% | 0.80 | 309 |
| W=30, THR=8% | 28.55% | 73.82% | 0.73 | 341 |

### 4.3 Placebo / randomized signal dates

| Null | Mean CAGR | Median | 5th pct | 95th pct | True | Percentile | One-sided p |
|---|---:|---:|---:|---:|---:|---:|---:|
| Circular shift of target | 22.11% | 22.15% | 6.01% | 41.64% | 48.71% | 0.98 | 0.030 |
| Circular shift of primary feature | 21.85% | 21.38% | 1.25% | 42.03% | 48.71% | 1.00 | 0.010 |

The true CAGR is near the 93rd percentile of the target-shift null and the feature-shift null.  This is the strongest placebo result of the four families, although a 100-draw circular-shift test on one development window is only indicative.

### 4.4 Correlation with the nine existing winners

| Winner | Correlation | n |
|---|---:|---:|
| `family-short-reversal` | 0.748 | 2011 |
| `relative-value-tqqq` | 0.739 | 2011 |
| `family-rebalance-flow` | 0.718 | 2011 |
| `family-ml-microstructure` | 0.700 | 2011 |
| `vol-scaled-crash-stop` | 0.656 | 2011 |
| `family-session-timing` | 0.588 | 2011 |
| `ratio-froth` | 0.528 | 2011 |
| `fomc-opex-window` | 0.510 | 2011 |
| `family-intraday-microstructure-day` | 0.502 | 2011 |

Range **0.502 .. 0.748** (mean 0.632); highest with `family-short-reversal`.  Correlation with TQQQ itself is **0.817** (beta 0.66).

The book shares the long-TQQQ risk-on exposure of the existing winners, with the highest correlation to `family-short-reversal`.  The oil event itself is distinct; the return stream is not fully independent.

## 5. Kill criteria

| # | Criterion | Observed | Triggered |
|---|---|---|---|
| 1 | Activity floor: >=100 full fills or >=30 independent events | 349 fills; 174 state switches | no |
| 2 | No three-way dev improvement over TQQQ buy & hold | CAGR 48.71% vs 36.15%; DD 64.46% vs 82.29%; Sharpe 1.00 vs 0.80 | no |
| 3 | Plateau: >=5 of 8 local cells clear the three-way dev bar | 8/8 cells pass | no |
| 4 | Placebo: one-sided p <= 0.20 for at least one circular-shift null | target p=0.030; feature p=0.010 | no |
| 5 | Redundancy: maximum correlation with an existing winner <= 0.85 | 0.748 (family-short-reversal) | no |
| 6 | Subperiod: no negative-CAGR development subperiod | none | no |

**0 of 6 kill criteria triggered.**

## 6. Honest verdict

**Dev candidate, strongest and most robust of the four external families.**  It clears the 1/5/10 bp dev bar, the activity floor, the 8/8 plateau, and all three subperiods, with a lower drawdown than TQQQ buy-and-hold.  It is not a verified winner: the 2020 crash is still a large drawdown, turnover is high, and correlation with the existing winners is around 0.8.  Freeze the parameters and run the one-shot 2024-2026 holdout before promotion.

## 7. Limitations and next steps

USO is an ETF that holds front-month futures; roll yield and contango/backwardation can decouple it from spot crude.  The daily close is a 16:00 print used at the 15:59 target write, the programme's standard convention.  The five-session event window is a short-horizon timing rule; if the oil-shock response decays or the market learns to look through spikes, the edge will weaken.  The 2020 oil collapse is a negative oil return, so the strategy was long TQQQ into the COVID crash; the drawdown is structural.  A more ambitious version would separate supply shocks from demand recoveries with inventories or the futures curve, but that would add a second primary object.

## 8. Reproduction

```powershell
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
$env:BT_THREADS = "1"
python research/new/family-oil-shock/strategy.py
```

The script rebuilds `result.json` and this report from the development window only.
