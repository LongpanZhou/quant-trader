# `family-copper-gold` -- hypothesis

**Slug:** `family-copper-gold`
**Family:** `copper-gold`
**Status:** reserve family; development-only test, 2016-01-04 .. 2023-12-29.
**Primary object:** CPER/GLD 60-session relative total-return z-score.

> **Design provenance.** The family and its primary cell were chosen after
> daily-bar diagnostics on the development window. The 8-cell grid below is a
> robustness probe around that centre, not a clean out-of-sample
> pre-registration. The run is marked `exploratory: true` in `result.json`.

## 1. Economic hypothesis

Copper is an industrial metal; gold is a monetary/defensive real asset. The
copper/gold ratio is therefore a coarse real-economy risk-appetite measure:
copper leadership suggests industrial demand and growth, gold leadership
suggests defensive/real-asset demand. The hypothesis is that a rising
CPER/GLD ratio is risk-on for long-duration growth equity (TQQQ), while gold
leadership is a de-risking signal (QQQ/BIL).

The ratio is slow and noisy. It is not a price-trend gate on QQQ, not equity
volatility, and not a relative-strength ratio on QQQ itself; it is a separate
macro object.

Testable implications:

1. TQQQ forward returns should be higher when copper is not underperforming
   gold than when it is.
2. The 60-session horizon should be more robust than 20 sessions for a
   macro ratio; 20 sessions is an ablation.
3. The result should survive 1/5/10 bp and a circular-shift placebo.
4. If the ratio is too slow, the strategy will simply be a high-beta Nasdaq
   sleeve with a weak overlay; that is a negative result, not a hidden pass.

## 2. Signal

For each session \(t\), with total-return adjusted closes \(C_t\) (CPER) and
\(G_t\) (GLD):

\[
  r^{(L)}_t = \log\frac{C_t}{C_{t-L}} - \log\frac{G_t}{G_{t-L}},
  \qquad
  z_t = \frac{r^{(L)}_t}{\mathrm{sd}_{252}(r^{(L)})_t}.
\]

The primary uses \(L=60\). The denominator is the trailing 252-session standard
deviation of the same \(L\)-session spread (minimum 120 observations). No QQQ
price trend, no volatility targeting, no drawdown event and no calendar clock
enters the signal.

## 3. Allocation

Primary mapping (`binary`):

| state | QQQ | TQQQ | BIL |
|---|---:|---:|---:|
| \(z_t > -0.50\) (growth leadership) | 0 | 1.00 | 0 |
| \(z_t \le -0.50\) (gold leadership) | 1.00 | 0 | 0 |

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
| `lookback_20_binary` | 20-session spread, threshold -0.50 |
| `lookback_20_binary_loose` | 20-session spread, threshold -0.75 |

The 20-session lookback is the faster alternative named in the brief. It is
expected to be noisier and more whipsaw-prone.

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

## 8. What would falsify the family

- The primary does not beat TQQQ on CAGR (the most likely outcome).
- The plateau is empty, i.e. no threshold/window/mapping combination works.
- The placebo distribution contains the real result.
- The static average allocation matches the timing strategy.
- A subperiod is negative.

A clean negative result is acceptable and useful: it says the copper/gold ratio
is not a usable risk-on/off signal for a 3x Nasdaq sleeve over 2016-2023.

## 9. Data

| input | source | role |
|---|---|---|
| CPER, GLD | `data/external/CPER.parquet`, `data/external/GLD.parquet` | signal only |
| QQQ daily | `data/intraday-hf/QQQ-1d-yahoo.parquet` | not used by this family |
| QQQ / TQQQ / BIL | `data/intraday-hf/*-1m.parquet` | execution and marks |

CPER and GLD history start 2015-01-02, so the 252-session normalisation is warm
by the first development session. CPER is a small, low-volume ETF; it is used
only as a signal and is never held. Costs are 1 bp headline, 5 bp and 10 bp
reported. The 2% band applies to every rebalance.
