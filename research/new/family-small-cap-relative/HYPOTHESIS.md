# `family-small-cap-relative` -- hypothesis

**Slug:** `family-small-cap-relative`
**Family:** `small-cap-relative`
**Status:** reserve family; development-only test, 2016-01-04 .. 2023-12-29.
**Primary object:** IWM/QQQ 20-session relative total-return z-score.

> **Design provenance.** The family and its primary cell were chosen after
> daily-bar diagnostics on the development window. The 8-cell grid below is a
> robustness probe around that centre, not a clean out-of-sample
> pre-registration. The run is marked `exploratory: true` in `result.json`.

## 1. Economic hypothesis

Small caps are the more domestically cyclical, more credit-sensitive end of the
US equity market. When small caps lead large-cap Nasdaq, the market is paying
for domestic growth and risk appetite is broad; when small caps lag, leadership
is narrowing into large-cap quality/defensiveness. The IWM/QQQ spread is
therefore a risk-appetite thermometer that is available daily and is not a
price-trend gate on QQQ itself.

The mapping is asymmetric:

- small-cap leadership intact -> hold TQQQ (3x Nasdaq);
- small-cap leadership broken -> step down to QQQ (1x large-cap defensive);
- severe breakdown -> BIL (flat).

The family is explicitly a **beta-timing overlay**, not a market-neutral
spread. It is expected to be highly correlated with TQQQ and to have a high
drawdown. The test is whether the relative signal improves the return/drawdown
trade-off versus holding TQQQ.

Testable implications:

1. TQQQ forward returns should be higher when IWM is not underperforming QQQ
   than when it is.
2. The signal should cut the worst 2022-type drawdown by rotating to QQQ/BIL.
3. The 20-session horizon should react faster than 60 sessions; the 60-session
   lookback is an ablation, not the primary.
4. The result should survive 1/5/10 bp and a circular-shift placebo.

## 2. Signal

For each session \(t\), with total-return adjusted closes \(I_t\) (IWM) and
\(Q_t\) (QQQ):

\[
  r^{(L)}_t = \log\frac{I_t}{I_{t-L}} - \log\frac{Q_t}{Q_{t-L}},
  \qquad
  z_t = \frac{r^{(L)}_t}{\mathrm{sd}_{252}(r^{(L)})_t}.
\]

The primary uses \(L=20\). The denominator is the trailing 252-session standard
deviation of the same \(L\)-session spread (minimum 120 observations), so the
threshold is in standard-deviation units and does not drift with the level of
volatility. No QQQ price trend, no volatility targeting, no drawdown event and
no calendar clock enters the signal.

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

The primary is cell 6 (20-session z, 252-session normalisation, threshold
-0.50, binary). The grid varies the z normalisation window (126/252 sessions),
the threshold (-0.75/-0.50) and the mapping (binary/ladder).

| # | lookback | norm window | threshold | mapping |
|---:|---:|---:|---:|---|
| 1 | 20 | 126 | -0.75 | binary |
| 2 | 20 | 126 | -0.50 | binary |
| 3 | 20 | 126 | -0.75 | ladder |
| 4 | 20 | 126 | -0.50 | ladder |
| 5 | 20 | 252 | -0.75 | binary |
| 6 | 20 | 252 | -0.50 | binary (primary) |
| 7 | 20 | 252 | -0.75 | ladder |
| 8 | 20 | 252 | -0.50 | ladder |

A plateau passes if at least 5 of 8 cells beat TQQQ's development bar
(36.72% CAGR / 82.29% max drawdown).

## 6. Ablations

| name | definition |
|---|---|
| `lookback_60_binary` | 60-session spread, same threshold and mapping |
| `lookback_60_ladder` | 60-session spread, ladder mapping |

The 60-session lookback is the slower alternative named in the brief. It is
expected to be more robust but less responsive; the comparison shows whether
the 20-session choice is load-bearing.

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

Criterion 8 is the most likely failure for this family: the IWM/QQQ spread can
stay positive while the whole equity market falls, so the strategy can be long
TQQQ through a broad bear market.

## 8. What would falsify the family

- The signal only works at one threshold/window and the plateau collapses.
- The placebo distribution contains the real result.
- The average TQQQ/QQQ mix explains the result (no timing value).
- The 2022 drawdown is not reduced relative to TQQQ.
- A subperiod is negative, which would show the overlay does not protect in a
  broad bear market.

## 9. Data

| input | source | role |
|---|---|---|
| IWM | `data/external/IWM.parquet` | signal only |
| QQQ daily | `data/intraday-hf/QQQ-1d-yahoo.parquet` | signal leg |
| QQQ / TQQQ / BIL | `data/intraday-hf/*-1m.parquet` | execution and marks |

IWM history starts 2015-01-02, so the 252-session normalisation is warm by the
first development session. Costs are 1 bp headline, 5 bp and 10 bp reported.
The 2% band applies to every rebalance.
