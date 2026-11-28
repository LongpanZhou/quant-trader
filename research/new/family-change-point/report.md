# Sign CUSUM change-point - report

**Slug:** `family-change-point`
**Window:** 2016-01-04 -> 2023-12-29, development only. The 2024-2026
holdout was never loaded. A separate process deposited `holdout.json` / `holdout_run.log` in this folder after the development run; this agent did not read or use them.
**Execution:** `research/bt.py`, 1-minute marks, next-open fills, 2% band,
long-only, weights >= 0, sum <= 1. Headline 1 bp; 5 bp and 10 bp also reported.
**Primary:** sign CUSUM on QQQ daily closes, k = 0.00, h = 3.0. An up-break
buys TQQQ for 20 sessions; a down-break holds BIL for 20 sessions; a new break
replaces the direction and restarts the clock.

---

## 1. Headline

| cost | CAGR | max DD | Sharpe | Sortino | vol | TQQQ exposure | fills | turnover |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **1 bp** | **51.49%** | **56.25%** | **1.24** | 1.76 | 40.2% | **63.8%** | 167 | 1,360x |
| 5 bp | 50.22% | 56.46% | 1.22 | 1.73 | 40.2% | 63.8% | 167 | 1,296x |
| 10 bp | 48.66% | 56.72% | 1.19 | 1.69 | 40.2% | 63.8% | 167 | 1,220x |

The stated bar is TQQQ **36.72% CAGR / 82.29% max DD / 0.82 Sharpe**. The
local 1-minute benchmark is 36.15% / 82.29% / 0.80. The primary clears both at
1 bp, 5 bp and 10 bp, with a materially lower drawdown and lower volatility.

Ending equity at 1 bp is **$2,755,211** from $100,000. The sleeve is in TQQQ
63.8% of bars and BIL 36.2%.

Daily-return correlation to TQQQ is **0.593**; correlation to the nine current
winners ranges from **0.380 to 0.655**.

## 2. Benchmarks

| | CAGR | max DD | Sharpe | Calmar | TQQQ exposure |
|---|---:|---:|---:|---:|---:|
| primary 1 bp | 51.49% | 56.25% | 1.24 | 0.92 | 63.8% |
| TQQQ | 36.15% | 82.29% | 0.80 | 0.44 | 100% |
| QQQ | 18.91% | 37.30% | 0.90 | 0.51 | - |

## 3. Yearly returns and exposure

| year | strategy | TQQQ | TQQQ exposure | note |
|---|---:|---:|---:|---|
| 2016 | +35.6% | +19.9% | 58.3% | early up-breaks |
| 2017 | +65.9% | +114.5% | 79.7% | lags the calm melt-up |
| 2018 | **-31.3%** | -20.8% | 59.8% | whipsaw: up-breaks into the Q4 bear |
| 2019 | +127.8% | +148.2% | 69.8% | strong trend year |
| 2020 | +190.1% | +104.1% | 77.1% | crash-recovery |
| 2021 | +31.6% | +81.1% | 72.2% | lags |
| 2022 | **-17.8%** | -79.4% | 31.1% | down-breaks cut exposure |
| 2023 | +130.3% | +192.0% | 62.4% | strong but lags |

The profile is a trend-following overlay: it wins in directional years and
loses less than TQQQ in 2022, but it is *worse* than TQQQ in 2018 because the
CUSUM keeps declaring up-breaks inside a bear market. That is the whipsaw
failure mode, and it is the main reason the maximum drawdown is in 2018 rather
than 2020.

## 4. What the break statistic actually predicts

193 breaks (131 up, 62 down) over 2,012 sessions. The event study is the
cleanest test of the family hypothesis:

| leg | n | forward 20d mean | median | win | t | worst / best |
|---|---:|---:|---:|---:|---:|---:|
| up-break -> long TQQQ | 131 | **+4.20%** | +7.59% | 71.8% | **3.33** | -53.2% / +34.5% |
| down-break -> cash | 62 | **+1.01%** | +2.79% | 58.1% | **0.46** | -50.5% / +35.5% |

**The up-break leg works; the down-break leg does not.** Up-breaks are followed
by a strong positive 20-session TQQQ return (t = 3.33). Down-breaks are
followed by a mildly positive return (t = 0.46), not a continued decline. The
"new direction down" half of the hypothesis is false on this sample. The cash
window after a down-break is a risk-control choice (it cuts 2022 exposure to
31.1%), not an alpha source; it gives up some rebound.

The 42 closed episodes (contiguous TQQQ runs) have a mean +10.69%, median
+6.72%, win 59.5%, t = 2.75, bootstrap p = 0.0012, 95% CI +3.44% .. +18.58%.
The episode mean is larger than the event mean because the position chains
through overlapping up-breaks and stays long through the strongest runs.

## 5. Pre-registered 8-cell grid

All at 1 bp, 1-minute marks. The primary is cell 1.

| # | k | h | hold | CAGR | max DD | Sharpe | TQQQ exp | fills |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | **0.00** | **3.0** | **20** | **51.49%** | **56.25%** | **1.24** | **63.8%** | 167 |
| 2 | 0.00 | 4.0 | 20 | 34.14% | 58.9% | 0.92 | 62.1% | 143 |
| 3 | 0.00 | 5.0 | 20 | 45.24% | 51.7% | 1.15 | 56.8% | 123 |
| 4 | 0.00 | 6.0 | 20 | 38.12% | 55.1% | 1.05 | 49.9% | 131 |
| 5 | 0.10 | 3.0 | 20 | 49.55% | 57.2% | 1.21 | 62.8% | 171 |
| 6 | 0.10 | 5.0 | 20 | 43.23% | 49.8% | 1.18 | 45.9% | 111 |
| 7 | 0.20 | 3.0 | 20 | 36.10% | 68.3% | 0.98 | 61.3% | 159 |
| 8 | 0.10 | 3.0 | 15 | 46.27% | 59.6% | 1.17 | 59.3% | 199 |

**6 of 8 cells clear the bar.** The plateau is decent in `k` at the two lower
values (0.00 and 0.10 pass at h=3), while **k=0.20 is 36.10%, just below the
bar**, and the hold dimension passes at both 15 and 20. It has a hole at
**h=4.0** (34.14%), which is the clearest sign of threshold sensitivity: the
break count drops from 131 up-breaks at h=3 to 96 at h=4, and the missing
breaks are not random. The h=5 and h=6 cells recover above the bar, so the
hole is not a monotone decay; it is a discrete-count effect.

The result is not a single-cell spike, but it is not a smooth plateau either.
The report treats h=4 as a genuine weakness.

## 6. Subperiods and drawdown anatomy

| period | CAGR | max DD | Sharpe | TQQQ exp |
|---|---:|---:|---:|---:|
| 2016-2019 | 38.03% | 56.3% | 1.16 | 66.9% |
| 2020-2021 | 98.76% | 33.3% | 1.61 | 74.8% |
| 2022-2023 | **38.88%** | 35.5% | 0.99 | 46.4% |
| ex-2020 | **33.18%** | 56.3% | 1.01 | 54.1% |
| ex-2022 | 55.52% | 56.3% | 1.37 | 59.9% |

The 2022-2023 cut is positive (38.9%) because down-breaks cut exposure to
46.4%; that is the risk-control value of the statistic. But **ex-2020 is
33.18%, below the 36.72% TQQQ bar**, and the 2016-2019 cut is only 38.0% with
a 56.3% drawdown. The full-window pass is helped by 2020.

**Worst drawdowns:**

| peak -> trough | depth | context |
|---|---:|---|
| 2018-09-05 -> 2019-01-08 | **-56.3%** | CUSUM keeps buying up-breaks into the Q4 2018 bear |
| 2021-11-22 -> 2022-06-30 | -47.9% | long into the first half of the 2022 bear |
| 2020-09-03 -> 2020-09-11 | -33.3% | September 2020 growth sell-off |

The maximum drawdown is 2018, not 2020. That is the whipsaw risk: the
detector's up-breaks are real in trending years, but in a choppy bear the
up-breaks are false and the position is long into the decline. 2018 is also
the only calendar year where the strategy is worse than TQQQ (-31.3% vs
-20.8%).

## 7. Placebo

Two placebos, each 100 full 1-minute backtests:

| | mean CAGR | sd | p95 | max | p(real >= placebo) |
|---|---:|---:|---:|---:|---:|
| circular shift of the state | 23.2% | 14.3% | 47.2% | 73.0% | **0.03** |
| random permutation of the state | 23.4% | 14.8% | 51.4% | 69.4% | **0.05** |

The shift placebo is significant at 5% (p = 0.03); the permutation is exactly
at the boundary (p = 0.05). The p95 of the shift placebo is 47.2%, only 4.3 pp
below the real 51.5%, and the placebo maximum is 73.0%. The timing is
**weakly distinguishable** from a random long-bias with the same exposure.
This is the weakest statistical result of the four families.

## 8. Correlation to the nine current winners

| winner | correlation |
|---|---:|
| family-rebalance-flow | 0.655 |
| vol-scaled-crash-stop | 0.627 |
| relative-value-tqqq | 0.627 |
| ratio-froth | 0.550 |
| family-ml-microstructure | 0.541 |
| fomc-opex-window | 0.512 |
| family-session-timing | 0.492 |
| family-short-reversal | 0.380 |
| family-intraday-microstructure-day | 0.380 |
| TQQQ | 0.593 |

All nine correlations are below 0.85; the maximum is 0.66. The break statistic
is not a duplicate of any existing family. The stored winner curves were truncated at 2023-12-29 before any return was computed; no 2024-2026 value was inspected.

## 9. Causality and implementation

- `x[d]` uses the QQQ 15:59 close and the prior 15:59 close. The break is
  known at 15:59 and fills at the next 09:30 open.
- The CUSUM recursion is causal and resets only on a detected break. No
  full-sample scaling, no volatility estimate, no moving average.
- Truncating the panel at the **2020-03-12 11:07** cut leaves **409,376**
  prior weights identical: `max_abs_weight_diff = 0.0`.
- Long-only, weights are 0 or 1, sum <= 1, BIL is the flat asset. 2% band;
  167 fills; 1 bp headline plus 5/10 bp.
- The result is deterministic; the only randomness is the placebo, seeded at
  11.

## 10. Kill criteria - verdict

| # | criterion | value | triggered? |
|---:|---|---:|---|
| 1 | 1 bp CAGR <= 36.72% or DD >= 82.29% | 51.49% / 56.25% | no |
| 2 | fewer than 5/8 grid cells pass | 6/8 | no |
| 3 | 10 bp CAGR <= 36.72% | 48.66% | no |
| 4 | shift-placebo p > 0.05 | 0.03 | no |
| 5 | shuffle-placebo p > 0.05 | 0.05 | boundary |
| 6 | ex-2020 CAGR <= 25% | 33.18% | no |
| 7 | correlation to a winner > 0.85 | 0.655 max | no |
| 8 | < 100 fills or < 30 breaks | 167 / 193 | no |
| 9 | pre-cut max weight diff > 1e-12 | 0.0 | no |
| 10 | down-break forward t > 2 | 0.46 | no |

**Verdict: dev pass, fragile.** The primary clears the TQQQ bar at 1/5/10 bp
with a 56% drawdown, 6/8 grid cells pass, and the up-break leg is a real
event-level effect (t = 3.33). The weaknesses are equally clear: the down-break
leg is unsupported (t = 0.46), the h=4 cell is a 17 pp hole, the shuffle
placebo is exactly at p = 0.05, ex-2020 CAGR is 33.18% (below the bar), and
2018 is worse than TQQQ. This is a marginal, not a robust, family winner.
