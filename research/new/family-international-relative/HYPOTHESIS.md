# `family-international-relative` -- hypothesis

**Slug:** `family-international-relative`
**Family:** `international-relative`
**Status:** reserve family; development-only test, 2016-01-04 .. 2023-12-29.
**Primary object:** EEM/QQQ 60-session relative total-return z-score.

> **Design provenance.** The family and its primary cell were chosen after
> daily-bar diagnostics on the development window. The 8-cell grid below is a
> robustness probe around that centre, not a clean out-of-sample
> pre-registration. The run is marked `exploratory: true` in `result.json`.

## 1. Economic hypothesis

Emerging-market equities are the high-beta end of the global growth cycle. When
EEM leads large-cap Nasdaq, global risk appetite and non-US growth are strong;
when EEM lags, the market is paying for US large-cap quality and defensiveness.
The EEM/QQQ spread is a global risk-on/off thermometer that is available daily
and is not a price-trend gate on QQQ itself.

The mapping is asymmetric:

- global risk-on (EEM leadership intact) -> hold TQQQ;
- US-only / defensive (EEM leadership broken) -> QQQ;
- severe breakdown -> BIL.

The family is a **beta-timing overlay**, not a market-neutral spread. It is
expected to be highly correlated with the TQQQ/QQQ complex. The test is whether
the relative signal improves the return/drawdown trade-off versus TQQQ.

Testable implications:

1. TQQQ forward returns should be higher when EEM is not underperforming QQQ
   than when it is.
2. The signal should de-risk before or during global risk-off episodes
   (2018, 2022), cutting the drawdown relative to TQQQ.
3. The 60-session horizon should be the right speed for a macro risk-on signal;
   the 20-session lookback is an ablation, not the primary.
4. The result should survive 1/5/10 bp and a circular-shift placebo.

## 2. Signal

For each session \(t\), with total-return adjusted closes \(E_t\) (EEM) and
\(Q_t\) (QQQ):

\[
  r^{(L)}_t = \log\frac{E_t}{E_{t-L}} - \log\frac{Q_t}{Q_{t-L}},
  \qquad
  z_t = \frac{r^{(L)}_t}{\mathrm{sd}_{252}(r^{(L)})_t}.
\]

The primary uses \(L=60\). The denominator is the trailing 252-session standard
deviation of the same \(L\)-session spread (minimum 120 observations), so the
threshold is in standard-deviation units. No QQQ price trend, no volatility
targeting, no drawdown event and no calendar clock enters the signal.

## 3. Allocation

Primary mapping (`binary`):

| state | QQQ | TQQQ | BIL |
|---|---:|---:|---:|
| \(z_t > -0.50\) (leadership intact) | 0 | 1.00 | 0 |
| \(z_t \le -0.50\) (breakdown) | 1.00 | 0 | 0 |

The `ladder` variant adds a flat rung on a severe breakdown:

| state | QQQ | TQQQ | BIL |
|---|---:|---:|---:|
| \(z_t > \theta\) | 0 | 1.00 | 0 |
| \(\theta - 0.50 < z_t \le \theta\) | 1.00 | 0 | 0 |
| \(z_t \le \theta - 0.50\) | 0 | 0 | 1.00 |

Long-only, weights \(\ge 0\), sum \(\le 1\). No leverage beyond 100% TQQQ.

## 4. Execution and causality

- Both legs use total-return adjusted closes through session \(k\).
- `targets[k]` is written at session \(k\)'s 15:59 close.
- It fills at session \(k+1\)'s 09:30 open through `research/bt.py`.
- `research/external.daily_targets_to_weights` maps the target to every bar;
  bars inside session \(k\) carry the target set at \(k-1\)'s close.
- No same-day fill; the 2% band is the only rebalance dead-band.
- The 2024-2026 holdout is excluded by a Parquet date filter at read time.

## 5. Pre-registered 8-cell plateau

The primary is cell 6 (60-session z, 252-session normalisation, threshold
-0.50, binary). The grid varies the z normalisation window (126/252 sessions),
the threshold (-0.75/-0.50) and the mapping (binary/ladder).

| # | lookback | norm window | threshold | mapping |
|---:|---:|---:|---:|---|
| 1 | 60 | 126 | -0.75 | binary |
| 2 | 60 | 126 | -0.50 | binary |
| 3 | 60 | 126 | -0.75 | ladder |
| 4 | 60 | 126 | -0.50 | ladder |
| 5 | 60 | 252 | -0.75 | binary |
| 6 | 60 | 252 | -0.50 | binary (primary) |
| 7 | 60 | 252 | -0.75 | ladder |
| 8 | 60 | 252 | -0.50 | ladder |

A plateau passes if at least 5 of 8 cells beat TQQQ's development bar
(36.72% CAGR / 82.29% max drawdown).

## 6. Ablations

| name | definition |
|---|---|
| `lookback_20_binary` | 20-session spread, same threshold and mapping |
| `lookback_20_ladder` | 20-session spread, ladder mapping |

The 20-session lookback is the faster alternative named in the brief. It is
expected to be noisier; the comparison shows whether the 60-session choice is
load-bearing. A failure at 20 sessions does not rescue the primary, it only
qualifies the family as horizon-specific.

## 7. Kill criteria (pre-registered)

1. 1 bp CAGR \(\le 36.72\%\).
2. 1 bp max drawdown \(\ge 82.29\%\).
3. 10 bp CAGR \(\le 36.72\%\).
4. Fewer than 5 of 8 plateau cells pass.
5. Circular-shift placebo CAGR percentile \(< 0.90\).
6. Daily-return correlation \(> 0.95\) with any of the nine winners.
7. Fewer than 100 fills **and** fewer than 30 distinct fill events.
8. Any subperiod CAGR \(< 0\).
9. The static blend at the strategy's own average weights matches or beats the
   strategy.

Criterion 8 is a real risk: the strategy is always long QQQ or TQQQ, and 2018
and 2022 contain sharp global risk-off legs.

## 8. What would falsify the family

- The signal only works at one threshold/window and the plateau collapses.
- The placebo distribution contains the real result.
- The average TQQQ/QQQ mix explains the result (no timing value).
- The 20-session spread is as good as the 60-session spread (then the signal
  is just short-term noise, not a macro regime).
- A subperiod is negative.

## 9. Data

| input | source | role |
|---|---|---|
| EEM | `data/external/EEM.parquet` | signal only |
| QQQ daily | `data/intraday-hf/QQQ-1d-yahoo.parquet` | signal leg |
| QQQ / TQQQ / BIL | `data/intraday-hf/*-1m.parquet` | execution and marks |

EEM history starts 2015-01-02, so the 252-session normalisation is warm by the
first development session. Costs are 1 bp headline, 5 bp and 10 bp reported.
The 2% band applies to every rebalance.
