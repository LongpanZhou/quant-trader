# Intraday realized skew - report

**Slug:** `family-realized-skew`
**Window:** 2016-01-04 -> 2023-12-29, development only. The 2024-2026
holdout was never loaded. A separate process deposited `holdout.json` / `holdout_run.log` in this folder after the development run; this agent did not read or use them.
**Execution:** `research/bt.py`, 1-minute marks, next-open fills, 2% band,
long-only, weights >= 0, sum <= 1. Headline 1 bp; 5 bp and 10 bp also reported.
**Primary:** QQQ 5-minute realized skew, trailing 10-session mean. If
S10 < -0.10, hold TQQQ for 3 sessions; otherwise BIL. A new signal rolls the
exit forward.

---

## 1. Headline

| cost | CAGR | max DD | Sharpe | Sortino | vol | TQQQ exposure | fills | turnover |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **1 bp** | **40.66%** | **54.71%** | **0.99** | 1.42 | 44.7% | **54.4%** | 331 | 2,515x |
| 5 bp | 38.35% | 56.13% | 0.95 | 1.36 | 44.7% | 54.4% | 331 | 2,298x |
| 10 bp | **35.51%** | 57.85% | 0.91 | 1.30 | 44.7% | 54.4% | 331 | 2,056x |

The stated bar is TQQQ **36.72% CAGR / 82.29% max DD / 0.82 Sharpe**. The
local 1-minute benchmark is 36.15% / 82.29% / 0.80.

**The primary clears 1 bp and 5 bp but fails 10 bp (35.51% vs 36.72%).** That
is kill criterion #3, and it is a real fail, not a rounding issue. The
headline is a marginal pass, not a robust one.

Ending equity at 1 bp is **$1,524,613** from $100,000. The sleeve is in TQQQ
54.4% of bars and BIL 45.6%.

Daily-return correlation to TQQQ is **0.668**; correlation to the nine current
winners ranges from **0.451 to 0.730**.

## 2. Benchmarks

| | CAGR | max DD | Sharpe | Calmar | TQQQ exposure |
|---|---:|---:|---:|---:|---:|
| primary 1 bp | 40.66% | 54.71% | 0.99 | 0.74 | 54.4% |
| TQQQ | 36.15% | 82.29% | 0.80 | 0.44 | 100% |
| QQQ | 18.91% | 37.30% | 0.90 | 0.51 | - |

## 3. Yearly returns and exposure

| year | strategy | TQQQ | TQQQ exposure | note |
|---|---:|---:|---:|---|
| 2016 | +34.5% | +19.9% | 38.5% | early skew events |
| 2017 | +95.1% | +114.5% | 72.9% | close to TQQQ |
| 2018 | **+40.5%** | -20.8% | 40.2% | defensive |
| 2019 | +52.5% | +148.2% | 55.6% | badly lags |
| 2020 | +183.2% | +104.1% | 63.6% | crash-recovery |
| 2021 | **-6.0%** | +81.1% | 52.0% | loses money in a bull year |
| 2022 | **-36.9%** | -79.4% | 37.5% | loses less than TQQQ |
| 2023 | +57.1% | +192.0% | 74.8% | badly lags |

The profile is uneven. It is defensive in 2018 and 2022, but it actually loses
money in 2021 (-6.0%) and lags badly in 2019, 2021 and 2023. The strategy is
not a consistent TQQQ-beater; it is a negative-skew sleeve with a few very
good crash-recovery years.

## 4. What the signal actually trades

849 event days, 83 closed episodes. The event-forward return is the TQQQ
open-to-open return over the 3 sessions after the signal.

| statistic | event-forward (3 sessions) | closed episodes |
|---|---:|---:|
| n | 848 | 83 |
| mean | **+0.84%** | +4.19% |
| median | +1.08% | +4.21% |
| win rate | 58.8% | 66.3% |
| t-stat | **3.82** | 2.85 |
| bootstrap p(mean <= 0) | - | 0.0017 |
| 95% CI | - | +1.33% .. +7.08% |
| worst / best | -30.1% / +27.4% | -27.7% / +44.7% |

The event-level edge is positive and statistically strong (t = 3.82), but the
events are **highly overlapping**: 849 event days cluster into 83 episodes
because a negative-skew regime persists for days. The independent evidence is
closer to 83 episodes than 849 events. The episode-level t is 2.85, still
positive but less impressive.

The distribution of S10 is centred at **-0.043** (min -0.888, max +0.734), so
the -0.10 threshold selects roughly the lower half of the distribution, not a
rare tail. This is a regime sleeve, not a rare-event strategy.

## 5. Pre-registered 8-cell grid

All at 1 bp, 1-minute marks. The primary is cell 1.

| # | S10 threshold | hold | CAGR | max DD | Sharpe | TQQQ exp | fills |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | **-0.10** | **3** | **40.66%** | **54.71%** | **0.99** | **54.4%** | 331 |
| 2 | -0.05 | 3 | 38.33% | 69.1% | 0.92 | 62.4% | 323 |
| 3 | -0.15 | 3 | **21.08%** | 62.2% | 0.67 | 46.4% | 347 |
| 4 | -0.20 | 3 | **16.77%** | 52.9% | 0.61 | 36.8% | 315 |
| 5 | -0.10 | 2 | 34.01% | 61.0% | 0.90 | 49.4% | 403 |
| 6 | -0.10 | 4 | 43.50% | 61.7% | 1.02 | 58.4% | 283 |
| 7 | -0.10 | 5 | 42.13% | 59.5% | 0.98 | 61.9% | 255 |
| 8 | -0.10 | 6 | 44.65% | 62.2% | 1.00 | 65.1% | 231 |

**5 of 8 cells clear the bar** - exactly the minimum for the plateau test.
The failures are informative:

- The **extreme negative tail fails badly**: -0.15 -> 21.08%, -0.20 -> 16.77%.
  A crash-skew session is not a buy signal. This is the opposite of the naive
  "more negative skew -> bigger bounce" reading, and it is the most important
  finding in this family.
- The short hold (h2) fails at 34.01%; h4/h5/h6 all pass at 42-45%. The
  effect needs 4-6 sessions, not 2.
- The mild threshold (-0.05) passes at 38.33% but with a 69.1% drawdown.

The primary is not a single-cell spike, but the threshold dimension is a
one-sided ridge: only the mild-negative region works.

## 6. Subperiods and drawdown anatomy

| period | CAGR | max DD | Sharpe | TQQQ exp |
|---|---:|---:|---:|---:|
| 2016-2019 | 51.82% | 29.6% | 1.42 | 51.7% |
| 2020-2021 | 65.90% | 39.6% | 1.21 | 57.7% |
| 2022-2023 | **1.34%** | 44.7% | 0.29 | 56.0% |
| ex-2020 | **24.04%** | 54.7% | 0.75 | 46.4% |
| ex-2022 | 49.58% | 39.6% | 1.23 | 49.7% |

**Ex-2020 CAGR is 24.04%, which triggers kill criterion #6 (<= 25%).** The
strategy is a 2020-dependent sleeve: 2020 alone returns +183.2%, and without
it the CAGR is below TQQQ and below the 25% floor. The 2022-2023 cut is
+1.34%, essentially flat over two years.

**Worst drawdowns:**

| peak -> trough | depth | context |
|---|---:|---|
| 2021-02-17 -> 2022-11-09 | **-54.7%** | long through the 2021-2022 bear; the negative-skew regime stays on |
| 2020-09-03 -> 2020-09-21 | -38.3% | September 2020 growth sell-off |
| 2020-02-25 -> 2020-02-28 | -31.9% | the first COVID crash week |

The maximum drawdown is a 21-month bear-market grind, not a single crash.
Negative skew persists through a bear market, so the sleeve stays long and
compounds down. That is the family's structural weakness.

## 7. Placebo

Two placebos, each 100 full 1-minute backtests:

| | mean CAGR | sd | p95 | max | p(real >= placebo) |
|---|---:|---:|---:|---:|---:|
| circular shift of the target | 21.6% | 14.7% | 45.2% | 61.6% | **0.08** |
| random event days | 30.5% | 11.1% | 49.5% | 56.1% | **0.17** |

Neither placebo rejects at 5%. The shift placebo is closer (p = 0.08), but its
p95 is 45.2%, *above* the real 40.66%. The random-entry placebo runs at 80.3%
average exposure (vs 54.4% real), so it has more beta and is not
exposure-matched; it still beats the real strategy 17% of the time.

The honest conclusion: the event-level skew edge is real (t = 3.82), but the
portfolio timing is **not statistically distinguishable from a random
long-biased sleeve** at conventional thresholds.

## 8. Correlation to the nine current winners

| winner | correlation |
|---|---:|
| relative-value-tqqq | 0.730 |
| family-rebalance-flow | 0.694 |
| family-ml-microstructure | 0.648 |
| vol-scaled-crash-stop | 0.608 |
| family-short-reversal | 0.605 |
| ratio-froth | 0.570 |
| family-session-timing | 0.552 |
| fomc-opex-window | 0.521 |
| family-intraday-microstructure-day | 0.451 |
| TQQQ | 0.668 |

All nine correlations are below 0.85; the maximum is 0.73. The skew sleeve is
moderately correlated with relative-value and rebalance-flow, but not a
duplicate. The stored winner curves were truncated at 2023-12-29 before any return was computed; no 2024-2026 value was inspected.

## 9. Causality and implementation

- Each session's realized skew uses 5-minute closes from 09:34 to 15:59 ET.
  The 10-day mean ends at the 15:59 close of day d; the target fills at the
  next 09:30 open. No 16:00 print is used.
- The overnight gap is excluded by construction.
- Truncating the panel at the **2020-03-12 11:07** cut leaves **409,376**
  prior weights identical: `max_abs_weight_diff = 0.0`.
- No full-sample normalisation, no volatility scaling, no moving average, no
  drawdown/capitulation event, no calendar clock, no opening-range/VWAP, no
  relative strength, no ML.
- Long-only, weights are 0 or 1, sum <= 1, BIL is the flat asset. 2% band;
  331 fills; 1 bp headline plus 5/10 bp.
- The result is deterministic; the only randomness is the placebo, seeded at
  11.

## 10. Kill criteria - verdict

| # | criterion | value | triggered? |
|---:|---|---:|---|
| 1 | 1 bp CAGR <= 36.72% or DD >= 82.29% | 40.66% / 54.71% | no |
| 2 | fewer than 5/8 grid cells pass | 5/8 | no |
| 3 | 10 bp CAGR <= 36.72% | **35.51%** | **yes** |
| 4 | shift-placebo p > 0.05 | **0.08** | **yes** |
| 5 | random-entry placebo p > 0.05 | **0.17** | **yes** |
| 6 | ex-2020 CAGR <= 25% | **24.04%** | **yes** |
| 7 | correlation to a winner > 0.85 | 0.730 max | no |
| 8 | < 100 fills or < 30 events | 331 / 849 | no |
| 9 | pre-cut max weight diff > 1e-12 | 0.0 | no |
| 10 | event-forward t <= 1.5 | 3.82 | no |

**Verdict: marginal / not validated.** Four of the ten kill criteria are
triggered: 10 bp cost, both placebos, and the ex-2020 floor. The event-level
skew premium is real and statistically strong, but the portfolio expression is
too close to a long-biased random sleeve, too dependent on 2020, and too
expensive at 10 bp. The family is an honest negative-to-marginal result: the
statistical object is interesting, the tradable edge is not robust.
