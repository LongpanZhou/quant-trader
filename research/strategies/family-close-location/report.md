# Close location value - report

**Slug:** `family-close-location`
**Window:** 2016-01-04 -> 2023-12-29, development only. The 2024-2026
holdout was never loaded. A separate process deposited `holdout.json` / `holdout_run.log` in this folder after the development run; this agent did not read or use them.
**Execution:** `research/bt.py`, 1-minute marks, next-open fills, 2% band,
long-only, weights >= 0, sum <= 1. Headline 1 bp; 5 bp and 10 bp also reported.
**Primary:** CLV of the QQQ session (1-minute closes). If CLV < -0.80, hold
TQQQ for 5 sessions; otherwise BIL. A new event rolls the exit forward.

---

## 1. Headline

| cost | CAGR | max DD | Sharpe | Sortino | vol | TQQQ exposure | fills | turnover |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **1 bp** | **79.32%** | **65.98%** | **1.37** | 1.95 | 53.3% | **45.8%** | 501 | 12,911x |
| 5 bp | 74.88% | 66.41% | 1.32 | 1.88 | 53.3% | 45.8% | 501 | 11,107x |
| 10 bp | 69.48% | 66.94% | 1.26 | 1.80 | 53.3% | 45.8% | 501 | 9,220x |

The stated bar is TQQQ **36.72% CAGR / 82.29% max DD / 0.82 Sharpe**. The
local 1-minute benchmark is 36.15% / 82.29% / 0.80. The primary clears both at
1 bp, 5 bp and 10 bp.

Ending equity at 1 bp is **$10,594,516** from $100,000. The sleeve is in TQQQ
45.8% of bars and BIL 54.2%.

This is the strongest of the four new families, but it is also the most
volatile: a 66% drawdown, a -49.8% calendar year in 2022, and ~12,900x
turnover. The headline CAGR should be read with those three facts in view.

Daily-return correlation to TQQQ is **0.789**; correlation to the nine current
winners ranges from **0.425 to 0.789**.

## 2. Benchmarks

| | CAGR | max DD | Sharpe | Calmar | TQQQ exposure |
|---|---:|---:|---:|---:|---:|
| primary 1 bp | 79.32% | 65.98% | 1.37 | 1.20 | 45.8% |
| TQQQ | 36.15% | 82.29% | 0.80 | 0.44 | 100% |
| QQQ | 18.91% | 37.30% | 0.90 | 0.51 | - |

## 3. Yearly returns and exposure

| year | strategy | TQQQ | TQQQ exposure | note |
|---|---:|---:|---:|---|
| 2016 | +65.0% | +19.9% | 39.7% | caught the February bottom and the post-election rally |
| 2017 | +39.7% | +114.5% | 25.1% | lags the calm bull |
| 2018 | **+47.5%** | -20.8% | 43.4% | the low-CLV bounce works in the Q4 bear |
| 2019 | +127.7% | +148.2% | 42.1% | close to TQQQ |
| 2020 | **+269.8%** | +104.1% | 52.6% | the crash-recovery payoff |
| 2021 | +105.5% | +81.1% | 44.8% | beats TQQQ |
| 2022 | **-49.8%** | -79.4% | 63.7% | loses less than TQQQ, still catastrophic |
| 2023 | **+257.1%** | +192.0% | 55.2% | beats TQQQ |

The profile is exactly what a dip-buying sleeve should look like: positive in
every development year, but with a -49.8% year in 2022 and a 66% peak-to-trough
drawdown. It beats TQQQ in 2016, 2018, 2020, 2021 and 2023 and lags in the calm
bull years 2017 and 2019. Unlike the Hurst and change-point families, it does
**not** depend on 2020: ex-2020 CAGR is 52.0%.

## 4. What the signal actually trades

226 event days, 125 closed episodes. The event-forward return is the TQQQ
open-to-open return over the 5 sessions after the signal.

| statistic | event-forward (5 sessions) | closed episodes |
|---|---:|---:|
| n | 226 | 125 |
| mean | **+2.92%** | +4.38% |
| median | +3.80% | +5.86% |
| win rate | 65.0% | 73.6% |
| t-stat | **4.31** | 4.60 |
| bootstrap p(mean <= 0) | 0.0000 | 0.0000 |
| 95% CI | +1.60% .. +4.24% | +2.48% .. +6.19% |
| worst / best | -42.0% / +31.9% | -34.7% / +29.2% |

Both the event-level and the episode-level edges are strong and statistically
significant. The episode mean is larger than the event mean because the
position chains through overlapping CLV events and stays long through the
strongest runs. The worst event is -42.0% (a crash that kept falling), which
is the falling-knife risk.

### The high-CLV side fails

The continuation hypothesis was tested and rejected. In the same harness:

| rule | dev CAGR | dev max DD |
|---|---:|---:|
| CLV > +0.8, hold 2 | **-7.58%** | 84.6% |
| CLV > +0.8, hold 3 | **-1.35%** | 88.7% |
| CLV > +0.6, hold 5 | +27.94% | 87.8% |

A close at the session high is not a continuation signal for QQQ/TQQQ; it is
followed by weak or negative returns. The family's edge is entirely on the
low-CLV reversal side. (These high-CLV cells use the same minute-close CLV as
the primary; the earlier true-daily-high/low scan gave the same sign.)

### CLV versus a plain down-day rule

The obvious competing explanation is that CLV < -0.80 is just a down day. In
the same harness with the same 5-session rolling exit:

| rule | events | CAGR | max DD | Sharpe | TQQQ exp |
|---|---:|---:|---:|---:|---:|
| QQQ down day -> TQQQ, h5 | 871 | 38.84% | **81.8%** | 0.83 | 93.8% |
| QQQ 2-day down streak -> TQQQ, h5 | 366 | 35.13% | 57.6% | 0.83 | 55.1% |
| QQQ 3-day return <= -1.5% -> TQQQ, h5 | 349 | 40.15% | 67.5% | 0.89 | 42.6% |
| **CLV < -0.80 -> TQQQ, h5** | **226** | **79.32%** | **65.98%** | **1.37** | **45.8%** |

The CLV rule is not a re-parameterised down-day rule: it doubles the CAGR of
the plain down-day rule at a lower drawdown and much lower exposure. The
location of the close inside the range carries information beyond the sign of
the day.

## 5. Pre-registered 8-cell grid

All at 1 bp, 1-minute marks. The primary is cell 3.

| # | CLV threshold | hold | CAGR | max DD | Sharpe | TQQQ exp | fills |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | -0.60 | 5 | 61.27% | 77.7% | 1.11 | 64.0% | 511 |
| 2 | -0.70 | 5 | 78.60% | 72.1% | 1.32 | 55.9% | 511 |
| 3 | **-0.80** | **5** | **79.32%** | **65.98%** | **1.37** | **45.8%** | 501 |
| 4 | -0.90 | 5 | 51.60% | **55.2%** | 1.14 | 31.2% | 401 |
| 5 | -0.80 | 3 | 61.72% | 57.0% | 1.28 | 30.6% | 653 |
| 6 | -0.80 | 4 | 59.57% | 71.6% | 1.19 | 38.6% | 577 |
| 7 | -0.80 | 6 | 60.14% | 74.8% | 1.13 | 52.0% | 419 |
| 8 | -0.80 | 8 | 48.72% | 81.2% | 0.97 | 61.8% | 323 |

**All 8 cells clear the bar.** The plateau is broad in the threshold (all four
thresholds pass) and in the hold (3 through 8 all pass). The point estimates
vary from 48.7% to 79.3%, so the exact cell is still path-dependent, but there
is no single-cell spike. The shallower thresholds have much higher exposure
and drawdown; the deeper threshold (-0.90) has a lower CAGR but the best
drawdown (55.2%).

The h5 spike (79.3% versus 59.6% at h4 and 60.1% at h6) is the main
path-dependence. The neighbours still clear the bar comfortably, so the family
does not rely on the exact 5-session clock, but the point estimate does.

## 6. Subperiods and drawdown anatomy

| period | CAGR | max DD | Sharpe | TQQQ exp |
|---|---:|---:|---:|---:|
| 2016-2019 | 65.17% | 35.4% | 1.60 | 37.6% |
| 2020-2021 | 180.76% | 63.0% | 1.83 | 48.3% |
| 2022-2023 | **35.65%** | 66.0% | 0.80 | 59.9% |
| ex-2020 | **52.03%** | 66.0% | 1.20 | 39.2% |
| ex-2022 | 91.97% | 63.0% | 1.66 | 37.9% |

The 2016-2019 cut is 65.2% and ex-2020 is 52.0%, both above the TQQQ bar. The
weakest cut is 2022-2023 at 35.65%, just below the bar, because the sleeve is
more invested (59.9%) in the 2022 bear than in any other cut. The strategy is
not a 2020-only result.

**Worst drawdowns:**

| peak -> trough | depth | context |
|---|---:|---|
| 2022-04-05 -> 2022-10-13 | **-66.0%** | the 2022 bear; low-CLV events keep firing |
| 2020-02-26 -> 2020-03-23 | -63.0% | the COVID crash; the rebound rescued the year |
| 2021-12-16 -> 2022-02-24 | -45.8% | the start of the 2022 decline |

The maximum drawdown is 2022, not 2020. That is the falling-knife failure
mode: a close at the low in a sustained bear keeps generating events, and the
5-session hold compounds down. 2022 is -49.8% versus TQQQ -79.4%; the strategy
loses less but still loses half its equity.

## 7. Placebo

Two placebos, each 100 full 1-minute backtests:

| | mean CAGR | sd | p95 | max | p(real >= placebo) |
|---|---:|---:|---:|---:|---:|
| circular shift of the target | 20.1% | 11.6% | 38.1% | 43.7% | **0.00** |
| random event days | 15.5% | 13.6% | 38.5% | 55.2% | **0.00** |

The shift placebo preserves the event count, clustering and exact exposure;
the random-entry placebo draws the same number of event days uniformly and
runs at 44.8% average exposure (almost exactly the real 45.8%). The real
79.32% is above the maximum of both 100-draw sets. The timing is clearly
distinguishable from both placebos.

## 8. Correlation to the nine current winners

| winner | correlation |
|---|---:|
| family-short-reversal | **0.789** |
| relative-value-tqqq | 0.652 |
| family-ml-microstructure | 0.636 |
| family-rebalance-flow | 0.610 |
| family-session-timing | 0.554 |
| vol-scaled-crash-stop | 0.534 |
| fomc-opex-window | 0.460 |
| family-intraday-microstructure-day | 0.450 |
| ratio-froth | 0.425 |
| TQQQ | 0.789 |

The maximum correlation is 0.789, to `family-short-reversal`, just below the
0.85 kill threshold. CLV is a refined dip-buying signal and it shares the
short-reversal beta, but the CLV object adds a large amount of return at lower
exposure. The report discloses the overlap rather than claiming independence. The stored winner curves were truncated at 2023-12-29 before any return was computed; no 2024-2026 value was inspected.

## 9. Causality and implementation

- CLV uses the 1-minute QQQ closes from 09:30 to 15:59 ET. The 15:59 close is
  the decision point; the target fills at the next 09:30 open. No 16:00 print
  is used.
- `high`/`low` are the max/min of the 1-minute closes, not the official daily
  high/low. The correlation with the official daily CLV is 0.997 and the mean
  absolute difference is 0.033.
- Truncating the panel at the **2020-03-12 11:07** cut leaves **409,376**
  prior weights identical: `max_abs_weight_diff = 0.0`.
- No full-sample normalisation, no moving average, no volatility targeting,
  no drawdown/capitulation event, no calendar clock, no opening-range/VWAP, no
  relative strength, no ML.
- Long-only, weights are 0 or 1, sum <= 1, BIL is the flat asset. 2% band;
  501 fills; 1 bp headline plus 5/10 bp.
- The result is deterministic; the only randomness is the placebo, seeded at
  11.

## 10. Kill criteria - verdict

| # | criterion | value | triggered? |
|---:|---|---:|---|
| 1 | 1 bp CAGR <= 36.72% or DD >= 82.29% | 79.32% / 65.98% | no |
| 2 | fewer than 5/8 grid cells pass | 8/8 | no |
| 3 | 10 bp CAGR <= 36.72% | 69.48% | no |
| 4 | shift-placebo p > 0.05 | 0.00 | no |
| 5 | random-entry placebo p > 0.05 | 0.00 | no |
| 6 | ex-2020 CAGR <= 25% | 52.03% | no |
| 7 | correlation to short-reversal > 0.85 | 0.789 | no |
| 8 | < 100 fills or < 30 events | 501 / 226 | no |
| 9 | pre-cut max weight diff > 1e-12 | 0.0 | no |
| 10 | event-forward t <= 1.5 | 4.31 | no |

**Verdict: dev pass, strong.** All ten kill criteria are clear. The primary
clears the TQQQ bar at 1/5/10 bp, all 8 grid cells pass, both placebos reject
at p = 0.00, ex-2020 CAGR is 52.0%, and the event-level t-stat is 4.31. The
caveats are the 66% drawdown, the -49.8% 2022, the 12,900x turnover, and the
0.789 correlation to `family-short-reversal`. This is a high-return,
high-risk, capacity-constrained dip-buying sleeve, not a low-risk alpha.
