# `family-rates-volatility` -- hypothesis

**Slug:** `family-rates-volatility`
**Family:** `rates-volatility`
**Status:** reserve family; development-only test, 2016-01-04 .. 2023-12-29.
**Primary object:** the level of rates volatility (ICE BofA MOVE index), not
equity volatility.

> **Design provenance.** The family and its primary cell were chosen after
> daily-bar diagnostics on the development window. The 8-cell grid below is a
> robustness probe around that centre, not a clean out-of-sample
> pre-registration. The run is marked `exploratory: true` in `result.json`.

## 1. Economic hypothesis

Rates volatility is the price of uncertainty about the discount rate. When the
rates market is calm (MOVE low relative to its own recent history), long-duration
growth equity is cheap to finance and volatility drag is low; a 3x Nasdaq sleeve
can compound. When rates volatility spikes, the whole duration complex is
re-priced, correlations go to one and drawdowns cluster. The MOVE spike is
therefore a de-risking signal even before equity volatility reacts.

This is deliberately **not** an equity-volatility strategy. VIX, VIX3M and
realized QQQ volatility are not inputs. The test is whether the rates-vol
complex carries incremental timing information.

Testable implications:

1. TQQQ forward returns should be higher when MOVE is below its 252-session
   median than when it is above.
2. The strategy's worst drawdowns should cluster in MOVE spikes, and the BIL
   rung should cut the 2020/2022 drawdown relative to TQQQ.
3. The result should survive 1/5/10 bp, a circular-shift placebo, and should
   not be explained by a static average allocation.
4. Correlation to the nine existing winners should be moderate, because the
   signal is a different macro object.

## 2. Signal

Let \(M_t\) be the MOVE daily close and \(\mathrm{med}_{252}(M)_t\) its trailing
252-session median (minimum 120 observations):

\[
  \text{level}_t = \frac{M_t}{\mathrm{med}_{252}(M)_t} - 1 .
\]

The primary state is `calm` when \(\text{level}_t < 0\), i.e. MOVE is below its
own one-year median. No price trend, no equity volatility, no drawdown
threshold and no calendar clock enters the signal.

The secondary, faster measure is the 20-session change

\[
  \text{chg20}_t = \frac{M_t}{M_{t-20}} - 1 .
\]

It is reported as an **ablation**, not as a plateau axis, because it is a
different object (rate of change rather than level).

## 3. Allocation

Primary mapping (`binary`):

| state | QQQ | TQQQ | BIL |
|---|---:|---:|---:|
| \(\text{level} < 0\) (calm) | 0 | 1.00 | 0 |
| \(\text{level} \ge 0\) (spike) | 0 | 0 | 1.00 |

The `ladder` variant inserts a 1x rung between calm and spike:

| state | QQQ | TQQQ | BIL |
|---|---:|---:|---:|
| \(\text{level} < \theta\) | 0 | 1.00 | 0 |
| \(\theta \le \text{level} < \theta + 0.20\) | 1.00 | 0 | 0 |
| \(\text{level} \ge \theta + 0.20\) | 0 | 0 | 1.00 |

Long-only, weights \(\ge 0\), sum \(\le 1\). No leverage beyond 100% TQQQ. BIL
is the flat asset.

## 4. Execution and causality

- Signal uses MOVE's daily close through session \(k\).
- `targets[k]` is written at session \(k\)'s 15:59 close.
- It fills at session \(k+1\)'s 09:30 open through `research/bt.py`.
- `research/external.daily_targets_to_weights` maps the target to every bar;
  bars inside session \(k\) carry the target set at \(k-1\)'s close.
- No same-day fill; the 2% band is the only rebalance dead-band.
- The 2024-2026 holdout is excluded by a Parquet date filter at read time.

## 5. Pre-registered 8-cell plateau

The primary is cell 5: MOVE / 252-session median - 1 < 0 -> TQQQ, else BIL.
The other seven cells vary the normalisation window (126/252 sessions), the
calm threshold (0 / +20%) and the mapping (binary/ladder).

| # | median window | calm threshold | mapping |
|---:|---:|---:|---|
| 1 | 126 | 0.00 | binary |
| 2 | 126 | 0.00 | ladder |
| 3 | 126 | +0.20 | binary |
| 4 | 126 | +0.20 | ladder |
| 5 | 252 | 0.00 | binary (primary) |
| 6 | 252 | 0.00 | ladder |
| 7 | 252 | +0.20 | binary |
| 8 | 252 | +0.20 | ladder |

A plateau passes if at least 5 of 8 cells beat TQQQ's development bar
(36.72% CAGR / 82.29% max drawdown). The threshold is fixed before the run.

## 6. Ablations

| name | definition |
|---|---|
| `chg20_binary` | 20-session MOVE change < 0 -> TQQQ, else BIL |
| `chg20_ladder` | same, with a QQQ rung for 0..+10% |

These test whether the *level* matters beyond a simple rate-of-change signal.
They are expected to be weaker and noisier; a failure does not rescue the
primary, it only qualifies it.

## 7. Kill criteria (pre-registered)

1. 1 bp CAGR \(\le 36.72\%\) (published TQQQ development bar).
2. 1 bp max drawdown \(\ge 82.29\%\) (TQQQ bar).
3. 10 bp CAGR \(\le 36.72\%\).
4. Fewer than 5 of 8 plateau cells pass.
5. Circular-shift placebo CAGR percentile \(< 0.90\).
6. Daily-return correlation \(> 0.95\) with any of the nine winners
   (`ratio-froth`, `vol-scaled-crash-stop`, `relative-value-tqqq`,
   `fomc-opex-window`, `family-session-timing`, `family-short-reversal`,
   `family-rebalance-flow`, `family-intraday-microstructure-day`,
   `family-ml-microstructure`).
7. Fewer than 100 fills **and** fewer than 30 distinct fill events.
8. Any subperiod CAGR \(< 0\).
9. The static blend at the strategy's own average weights matches or beats the
   strategy (no timing value).

## 8. What would falsify the family

- The level signal works only at one window/threshold and the 8-cell plateau
  collapses.
- The placebo distribution contains the real result (timing is not special).
- The 20-session change is as good as the level (then the object is just
  short-term rates momentum, not a regime).
- The result is explained by the average TQQQ/BIL mix.
- Any of the nine winner correlations is above 0.95 (duplicate).

## 9. Data

| input | source | role |
|---|---|---|
| MOVE | `data/external/MOVE.parquet` | signal only |
| QQQ / TQQQ / BIL | `data/intraday-hf/*-1m.parquet` | execution and marks |
| QQQ daily | `data/intraday-hf/QQQ-1d-yahoo.parquet` | not used by this family |

MOVE history starts 2015-01-02, so the 252-session median is warm by the first
development session. Costs are 1 bp headline, 5 bp and 10 bp reported. The 2%
band applies to every rebalance.
