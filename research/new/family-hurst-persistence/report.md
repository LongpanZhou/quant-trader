# Rolling Hurst / variance ratio - report

**Slug:** `family-hurst-persistence`
**Window:** 2016-01-04 -> 2023-12-29, development only. The 2024-2026
holdout was never loaded. A separate process deposited `holdout.json` / `holdout_run.log` in this folder after the development run; this agent did not read or use them.
**Execution:** `research/bt.py`, 1-minute marks, next-open fills, 2% band,
long-only, weights >= 0, sum <= 1. Headline 1 bp; 5 bp and 10 bp also reported.
**Primary:** rolling Hurst of QQQ daily returns, W = 252, q = 5; expanding
30/70 percentile thresholds over the prior 1,260 estimates (minimum 60).
TQQQ 1.0 when H <= q30, or when q30 < H < q70 and the QQQ 5-day return is
positive; BIL otherwise.

---

## 1. Headline

| cost | CAGR | max DD | Sharpe | Sortino | vol | TQQQ exposure | fills | turnover |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **1 bp** | **53.13%** | **60.40%** | **1.17** | 1.64 | 45.7% | **46.6%** | 341 | 5,005x |
| 5 bp | 50.53% | 60.46% | 1.13 | 1.58 | 45.7% | 46.6% | 341 | 4,543x |
| 10 bp | 47.35% | 60.54% | 1.08 | 1.52 | 45.7% | 46.6% | 341 | 4,030x |

The stated bar is TQQQ **36.72% CAGR / 82.29% max DD / 0.82 Sharpe** on daily
closes. The local 1-minute `bt.benchmark` TQQQ is 36.15% / 82.29% / 0.80; the
0.57 pp difference is a mark-convention difference. The primary clears both at
1 bp, 5 bp and 10 bp.

Ending equity at 1 bp is **$3,002,942** from $100,000. The sleeve is in TQQQ
46.6% of bars and in BIL the other 53.4%.

Daily-return correlation to TQQQ is **0.679**. Correlation to the nine current
winners ranges from **0.346 to 0.621**. This is a timing overlay on leveraged
Nasdaq beta, not a diversifying alpha.

## 2. Benchmarks

| | CAGR | max DD | Sharpe | Calmar | TQQQ exposure |
|---|---:|---:|---:|---:|---:|
| primary 1 bp | 53.13% | 60.40% | 1.17 | 0.88 | 46.6% |
| TQQQ | 36.15% | 82.29% | 0.80 | 0.44 | 100% |
| QQQ | 18.91% | 37.30% | 0.90 | 0.51 | - |

## 3. Yearly returns and exposure

| year | strategy | TQQQ | TQQQ exposure | note |
|---|---:|---:|---:|---|
| 2016 | **0.1%** | +19.9% | 0.0% | structural Hurst warm-up; no signal |
| 2017 | +35.1% | +114.5% | 49.8% | first trades from late March 2017 |
| 2018 | **+37.8%** | -20.8% | 18.3% | high-H cash state avoids the Q4 bear |
| 2019 | +126.9% | +148.2% | 88.9% | low-H state stays long |
| 2020 | **+196.6%** | +104.1% | 96.8% | low-H crash state is fully long |
| 2021 | +58.6% | +81.1% | 69.8% | lags the melt-up |
| 2022 | **+7.4%** | -79.4% | 8.8% | high-H state is almost entirely cash |
| 2023 | +42.0% | +192.0% | 40.0% | lags the AI melt-up |

The strategy is a **defensive regime overlay**: it wins in 2018 and 2022 by
being out, lags the calm melt-ups of 2017, 2021 and 2023, and is fully
invested in the 2020 crash-recovery. The 2016 zero is a warm-up artefact: a
252-day estimator cannot produce a signal before 2017.

## 4. What the Hurst state actually contains

The estimate is uniformly below 0.5: mean **0.433**, min **0.287**, max
**0.511**, and only one day above 0.50. The original "H > 0.5 -> trend" leg is
therefore untestable in absolute terms.

| state | share of days | forward 20d TQQQ mean | forward 20d win |
|---|---:|---:|---:|
| low H (<= q30) | 33.6% | positive | - |
| high H (>= q70) | 29.9% | **negative** | - |

The high-H state is not a trend-continuation state in QQQ; it is
disproportionately a persistent-downside / high-volatility state. The scan
that produced the rule found:

| scan variant | dev CAGR | dev max DD |
|---|---:|---:|
| always long in the top H tercile | **-8.8%** | 85.9% |
| high H + 5-day up -> long | **-11.8%** | 84.6% |
| low H + 5-day down -> long | +22.2% | 56.7% |
| low H always -> long | +32.0% | 64.1% |

The scan used full-sample thresholds, so these numbers illustrate the sign of
each leg, not the final expanding-threshold rule. The final 8-cell grid is in
section 6.

The low-H side is the tradable side. The primary keeps the low-H leg, adds the
neutral-band 5-day-up leg for exposure, and stays in cash in the high-H state.

## 5. Entries and episodes

85 entries / 85 closed episodes from 938 active days. The episode return is
the TQQQ open-to-open return from the first held session to the session after
the position is closed.

| statistic | value |
|---|---:|
| episodes | 85 |
| mean episode return | +5.81% |
| median | +1.38% |
| win rate | 56.5% |
| t-stat | 1.92 |
| bootstrap p(mean <= 0) | 0.0004 |
| bootstrap 95% CI | +1.49% .. +12.87% |
| worst / best | -11.94% / +243.7% |

The distribution is **strongly right-skewed**: one 2020 episode returns
+243.7%, while the median episode is only +1.4%. The bootstrap p is small but
the t-stat is 1.92; the positive mean is carried by a few crash-recovery
episodes, not by a uniform per-entry edge.

The entry-forward study (next open to the open 20 sessions later) gives:

| statistic | value |
|---|---:|
| n | 85 |
| mean | +5.00% |
| median | +7.59% |
| win | 67.1% |
| t | 3.21 |
| worst / best | -28.9% / +50.0% |

## 6. Pre-registered 8-cell grid

All at 1 bp, 1-minute marks. The primary is cell 1.

| # | W | q | band | CAGR | max DD | Sharpe | TQQQ exp | fills |
|---:|---:|---:|---|---:|---:|---:|---:|---:|
| 1 | **252** | **5** | **30/70** | **53.13%** | **60.40%** | **1.17** | **46.6%** | 341 |
| 2 | 252 | 2 | 30/70 | 33.98% | 68.0% | 0.89 | 40.2% | 333 |
| 3 | 252 | 10 | 30/70 | 51.74% | **43.3%** | 1.20 | 43.1% | 273 |
| 4 | 126 | 5 | 30/70 | 54.70% | 65.8% | 1.17 | 49.4% | 389 |
| 5 | 126 | 2 | 30/70 | 36.96% | 70.4% | 0.94 | 45.2% | 357 |
| 6 | 126 | 10 | 30/70 | 27.44% | 57.0% | 0.76 | 50.8% | 357 |
| 7 | 252 | 5 | 25/75 | 47.22% | 65.5% | 1.07 | 47.5% | 365 |
| 8 | 252 | 5 | 35/65 | 52.28% | 64.1% | 1.17 | 45.3% | 249 |

**6 of 8 cells clear the bar.** The failures are W252/q2 (33.98%) and
W126/q10 (27.44%). The one-year window is the important choice: W=252/q=5 and
W=252/q=10 both pass, and W=126/q=5 passes. The q=10 cell at W=252 has a
materially better drawdown (43.3%) at a slightly lower CAGR, which is a useful
robustness check: the result is not specific to the 5-day VR horizon.

This is a plateau in the window dimension and in the quantile band, but not in
the VR horizon: q=2 fails at W=252 and q=10 fails at W=126. The report treats
those failures as genuine limitations, not as noise to be averaged away.

## 7. Subperiods and drawdown anatomy

| period | CAGR | max DD | Sharpe | TQQQ exp |
|---|---:|---:|---:|---:|
| 2016-2019 | 41.12% | 27.6% | 1.43 | 39.1% |
| 2020-2021 | 120.73% | 60.4% | 1.42 | 83.3% |
| 2022-2023 | **23.72%** | 30.0% | 0.85 | 24.6% |
| ex-2020 | **34.25%** | 32.8% | 1.16 | 34.4% |
| ex-2022 | 52.39% | 60.4% | 1.17 | 45.5% |

The 2016-2019 cut is 41.1%, so the strategy is not only a 2020 trade. But
**ex-2020 is 34.25%, below the 36.72% TQQQ bar**, and the 2022-2023 cut is
23.7%. The full-window pass is helped materially by 2020. The honest summary
is: a defensive overlay with a real 2018/2022 drawdown benefit, whose return
premium over TQQQ depends on the 2020 crash-recovery.

**Worst drawdowns:**

| peak -> trough | depth | context |
|---|---:|---|
| 2020-02-20 -> 2020-03-23 | **-60.4%** | the COVID crash; the low-H state is fully long |
| 2020-09-03 -> 2020-09-21 | -38.3% | the September 2020 growth sell-off |
| 2021-02-17 -> 2021-03-05 | -32.8% | the February 2021 yield spike |

The maximum drawdown is in the 2020 crash, exactly the failure mode the
family predicts: the low-H state is the high-volatility crash state, and the
strategy is 96.8% invested in 2020.

## 8. Placebo

Two placebos, each 100 full 1-minute backtests:

| | mean CAGR | sd | p95 | max | p(real >= placebo) |
|---|---:|---:|---:|---:|---:|
| circular shift of the state | 18.8% | 10.9% | 35.9% | 45.2% | **0.00** |
| random permutation of the state | 15.1% | 13.4% | 37.1% | 44.5% | **0.00** |

The shift placebo preserves the state durations and the exact exposure; the
permutation preserves exposure but destroys clustering. The real 53.13% is
above the maximum of both 100-draw sets. The timing is distinguishable from
both placebos.

## 9. Correlation to the nine current winners

| winner | correlation |
|---|---:|
| relative-value-tqqq | 0.621 |
| family-short-reversal | 0.570 |
| family-rebalance-flow | 0.532 |
| ratio-froth | 0.493 |
| family-ml-microstructure | 0.492 |
| vol-scaled-crash-stop | 0.482 |
| family-session-timing | 0.461 |
| family-intraday-microstructure-day | 0.346 |
| fomc-opex-window | 0.346 |
| TQQQ | 0.679 |

All nine correlations are below 0.85; the maximum is 0.62. The Hurst state is
not a duplicate of any existing family. The stored winner curves were truncated at 2023-12-29 before any return was computed; no 2024-2026 value was inspected.

## 10. Causality and implementation

- `H[d]` uses QQQ close-to-close returns through the **15:59 ET** close. The
  target is written on that bar and fills at the **09:30 open** of the next
  session. No 16:00 print is used.
- Thresholds use only H estimates up to and including day d; the lookback is
  1,260 observations with a 60-observation minimum.
- Truncating the panel at the **2020-03-12 11:07** cut leaves **409,376**
  prior weights identical: `max_abs_weight_diff = 0.0`.
- No full-sample normalisation. No moving average, no volatility targeting,
  no drawdown/capitulation event, no calendar clock, no opening-range or
  close-flow, no relative strength, no ML.
- Long-only, weights are 0 or 1, sum <= 1, BIL is the flat asset. 2% band;
  341 fills; 1 bp headline plus 5/10 bp.
- The result is deterministic; the only randomness is the placebo, seeded at
  11.

## 11. Kill criteria - verdict

| # | criterion | value | triggered? |
|---:|---|---:|---|
| 1 | 1 bp CAGR <= 36.72% or DD >= 82.29% | 53.13% / 60.40% | no |
| 2 | fewer than 5/8 grid cells pass | 6/8 | no |
| 3 | 10 bp CAGR <= 36.72% | 47.35% | no |
| 4 | shift-placebo p > 0.05 | 0.00 | no |
| 5 | shuffle-placebo p > 0.05 | 0.00 | no |
| 6 | ex-2020 CAGR <= 25% | 34.25% | no |
| 7 | correlation to a winner > 0.85 | 0.621 max | no |
| 8 | < 100 fills or < 30 entries | 341 / 85 | no |
| 9 | pre-cut max weight diff > 1e-12 | 0.0 | no |

**Verdict: dev pass, with a 2020-dependence caveat.** The primary clears the
TQQQ bar at 1/5/10 bp, 6/8 grid cells pass, both placebos reject at p = 0.00,
and the maximum winner correlation is 0.62. The caveats are real: 2016 is
cash (estimator warm-up), ex-2020 CAGR is 34.25% (below the TQQQ bar), and the
episode mean is carried by a handful of right-tail 2020-2021 entries. The
family is a useful defensive regime overlay, not a stand-alone replacement for
TQQQ.
