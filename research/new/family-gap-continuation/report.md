# Gap continuation: development report

**Family:** `gap-continuation` (new). Primary mechanism: a large opening gap
plus first-30-minute confirmation continues through the session.

**Verdict: positive and robust, but below the program's 36.72% above-TQQQ CAGR
bar. It passes every integrity/robustness gate and is a genuine risk-adjusted
diversifier (Sharpe 0.94, max DD 15.5%, correlation <= 0.32 to every current
winner), not an above-TQQQ replacement.**

Development window 2016-01-04 .. 2023-12-29, 1-minute marks, next-open fills,
2% band, long-only, weights >= 0, sum <= 1. The panel is requested with
`end=2023-12-29`; no 2024-2026 bar is used. The only data inputs are the
shared QQQ/TQQQ/BIL panel; the signal itself uses QQQ open/close, and the
position is TQQQ.

---

## 1. Headline

| | CAGR | Max DD | Sharpe | Sortino | Vol | TQQQ weight (bar-time) | Fills | Turnover | Ending equity |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Primary, 1 bp** | **11.25%** | **15.45%** | **0.94** | **1.34** | 12.2% | 6.96% | 304 | 533x | $234,250 |
| Primary, 2 bp | 10.83% | 15.59% | 0.91 | 1.29 | 12.2% | 6.96% | 304 | 524x | $227,236 |
| Primary, 5 bp | 9.57% | 16.38% | 0.81 | 1.16 | 12.2% | 6.96% | 304 | 497x | $207,429 |
| Primary, 10 bp | 7.50% | 17.83% | 0.66 | 0.93 | 12.2% | 6.96% | 304 | 456x | $178,179 |
| Primary, 0 bp (gross) | 11.67% | 15.32% | 0.97 | 1.38 | 12.2% | 6.96% | 304 | 543x | $241,480 |
| TQQQ buy & hold (sim) | 36.15% | 82.29% | 0.80 | 1.12 | 66.5% | 100% | 1 | 1x | $1,175,165 |
| TQQQ bar from the brief | 36.72% | 82.29% | 0.82 | -- | -- | 100% | -- | -- | -- |

- The strategy is **25.5 pp below** the TQQQ CAGR bar at 1 bp. It is **not**
  an above-TQQQ replacement.
- It cuts max drawdown by **66.8 pp** (15.45% vs 82.29%) and raises Sharpe
  from 0.80 to 0.94. Sortino is 1.34 vs 1.12. The risk-adjusted profile is
  better than TQQQ even though the absolute return is lower.
- Cost sensitivity is mild: 5 bp costs 1.68 pp of CAGR, 10 bp costs 3.75 pp.
  The 5 bp and 10 bp results remain positive. Turnover is 533x initial equity
  over 8 years (~67x/yr), low because the book is flat most of the time.
- Exposure is **6.96% of 1-minute bars** and **1.88% of clock time** (152
  events x 358 held minutes / (2012 sessions x 1440)). The rest is cash at 0%.
- Daily correlation to TQQQ is **0.290**. This is a small, separate intraday
  sleeve, not a leveraged beta clone.
- Max drawdown episode: **2023-06-30 -> 2023-11-29, 15.45%**. This is also the
  main warning: 2023 was -13.9% and the 2022-23 subperiod CAGR is only 3.49%.

---

## 2. What it is

Universe: QQQ (signal), TQQQ (position), cash.

At the close of the 10:00 bar:

```
gap_k = QQQ_open(09:30) / QQQ_close(previous 15:59) - 1
r30_k = QQQ_close(10:00) / QQQ_open(09:30) - 1
```

If `gap_k >= +0.50%` and `r30_k >= +0.20%`, buy TQQQ at the **10:01 open**.
Sell at the **15:59 open**. Otherwise hold cash. No overnight position in the
primary rule.

**Clock.** The gap is known at 09:30. The confirmation is the 10:00 bar close.
The decision is taken at 10:00:00; the fill is the next bar open at 10:01. The
exit is decided at the 15:58 close and filled at the 15:59 open. There is no
same-bar fill. The previous close is the prior session's 15:59 close, so the
gap uses only completed data.

Only 390-bar sessions are traded. Half-days and short sessions are skipped;
they still update the previous close. This is a data-quality rule.

---

## 3. Why the signal, not just the calendar

The event sample is 152 trades over 8 years, **19.0 events/year**. Per-event
gross return, entry 10:01 open to exit 15:59 open:

| Metric | Value |
|---|---:|
| Events | 152 |
| Mean | **+62.6 bp** |
| Median | +85.3 bp |
| Win rate | 64.5% |
| t-stat | **2.59** |
| Worst | -988 bp |
| Best | +1,358 bp |
| Sum of log returns | +0.882 |

The positive mean is not a single outlier: the median is higher than the mean,
and the win rate is 64.5%. The worst event (-9.9% on TQQQ) is a real gap-day
risk and is the reason the strategy needs the 15:59 exit rather than an
overnight hold.

The controls separate the two legs:

| Control | CAGR | Max DD | Sharpe | Fills | What it says |
|---|---:|---:|---:|---:|---|
| Gap only, **no** confirmation | 7.38% | 37.27% | 0.42 | 844 | The gap alone is weak and much riskier. |
| Confirmation only, **no** gap | 20.11% | 33.96% | 0.82 | 1,276 | The first-30-minute drive alone is a different, stronger-return / much-riskier trade. |
| Gap up, first 30m **down** (fade) | -0.28% | 35.08% | 0.08 | 382 | Fading the gap does not work in this sample. |
| Buy & hold TQQQ | 36.15% | 82.29% | 0.80 | 1 | The absolute-return bar. |

The gap filter is therefore a **risk selector**, not the whole return source:
it halves the confirmation-only CAGR but cuts its drawdown from 34.0% to
15.5% and raises Sharpe from 0.82 to 0.94. The family's claim is that the
*combination* is the trade; the report does not claim that the gap alone
carries the return.

---

## 4. Robustness

### 4.1 Pre-registered grid (8 cells)

All cells use the 10:01 -> 15:59 clock and TQQQ 1.0. The centre is cell 4.

| Cell | Gap | r30 | 1 bp CAGR | 1 bp DD | 1 bp Sharpe | 5 bp CAGR | Fills |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.30% | 0.00% | 6.38% | 34.34% | 0.44 | 2.69% | 706 |
| 2 | 0.30% | 0.20% | 10.84% | 20.15% | 0.82 | 8.41% | 442 |
| 3 | 0.50% | 0.00% | 7.68% | 25.20% | 0.58 | 5.22% | 462 |
| **4** | **0.50%** | **0.20%** | **11.25%** | **15.45%** | **0.94** | **9.57%** | **304** |
| 5 | 0.75% | 0.00% | 5.26% | 24.59% | 0.47 | 3.85% | 270 |
| 6 | 0.75% | 0.20% | 9.33% | 15.36% | 0.90 | 8.35% | 180 |
| 7 | 1.00% | 0.00% | 3.27% | 29.22% | 0.35 | 2.40% | 170 |
| 8 | 1.00% | 0.20% | 8.50% | 17.80% | 0.96 | 7.85% | 120 |

**8/8 cells are positive at 1 bp and 8/8 at 5 bp.** The 1 bp CAGR range is
3.27% to 11.25%; the centre is the best cell, but cell 8 has the highest
Sharpe (0.96) with only 60 events. The plateau is broad in sign, not in level.
The monotone pattern (confirmation always helps; a larger gap lowers CAGR but
also lowers drawdown) is economically consistent, not a random ridge.

### 4.2 Neighbours (not used to choose the centre)

| Neighbour | 1 bp CAGR | 1 bp DD | Sharpe | 5 bp CAGR |
|---|---:|---:|---:|---:|
| Gap 0.40% | 10.97% | 14.51% | 0.88 | 8.93% |
| Gap 0.60% | 8.43% | 15.84% | 0.77 | 7.11% |
| r30 0.10% | 9.31% | 20.65% | 0.74 | 7.28% |
| r30 0.30% | 7.79% | 12.14% | 0.80 | 6.62% |
| r30 0.50% | 5.80% | 14.50% | 0.77 | 5.24% |
| Entry 10:16 | 9.28% | 15.69% | 0.81 | 7.63% |
| Entry 10:31 | 6.82% | 13.98% | 0.64 | 5.20% |
| Entry 11:01 | 7.83% | 15.92% | 0.76 | 6.20% |
| Exit 15:30 | 11.26% | 15.29% | 0.99 | 9.58% |
| Exit 15:45 | 11.79% | 15.41% | 1.01 | 10.10% |
| **Next-open exit** | **15.69%** | **20.22%** | **0.95** | **13.94%** |
| Size 0.50 | 5.71% | 7.96% | 0.94 | 4.91% |
| QQQ execution | 3.80% | 5.59% | 0.92 | 2.23% |
| TQQQ signal 1.5%/0.5% | 10.85% | 17.06% | 0.89 | 9.06% |

The result is stable to the entry minute and the signal asset. The
next-open exit is stronger in CAGR (15.69%) and keeps Sharpe at 0.95, but it
adds overnight risk and overlaps the session-timing family. It is reported as
a neighbour, not promoted, to keep this family a pure intraday continuation
trade. The QQQ execution has a lower CAGR but the same Sharpe (0.92) and a
much lower drawdown (5.59%), confirming that the signal is in QQQ and TQQQ is
mainly a capital-efficiency choice.

### 4.3 Placebos

| Placebo | Draws | Real CAGR | Placebo mean | Placebo p95 | Max | p-value | Real DD percentile |
|---|---:|---:|---:|---:|---:|---:|---:|
| Random days, same count, 10:01 -> 15:59 | 200 | 11.25% | -0.25% | 5.67% | 11.89% | **0.005** | 99.5% |
| Random entry 10:01-10:30, same signal days | 200 | 11.25% | 9.25% | 10.28% | 10.89% | **0.000** | 15.5% |
| Stale signal (previous session) | 1 | 11.25% | -- | -- | -- | -- | -- |

- The random-day placebo is the strong result: random calendar days with the
  same clock average -0.25% CAGR and only 5.67% at the 95th percentile. The
  real result is at the 99.5th percentile and its drawdown is better than
  99.5% of random-day draws. The gap/confirmation signal is selecting the
  days, not riding calendar drift.
- The random-entry placebo is weaker evidence. The real 11.25% beats all 200
  random-entry draws (max 10.89%), p=0.000, but the mean random entry still
  earns 9.25%. The 10:01 timing adds about 2.0 pp of CAGR, not the whole
  edge. The real drawdown is *worse* than 84.5% of random-entry draws (15.45%
  vs a 14.65% mean), so the early entry is a return choice, not a drawdown
  reducer.
- The stale signal loses money (-3.64% CAGR, -42.7% DD), so the same-day gap
  and confirmation are doing the work.

### 4.4 Subperiods and yearly

| Period | CAGR | Max DD |
|---|---:|---:|
| 2016-2019 | 10.61% | 14.77% |
| 2020-2021 | 20.10% | 14.51% |
| 2022-2023 | **3.49%** | 15.45% |

| Year | Strategy | TQQQ |
|---|---:|---:|
| 2016 | +9.17% | +19.86% |
| 2017 | +7.59% | +114.54% |
| 2018 | +19.29% | -20.76% |
| 2019 | +6.71% | +148.23% |
| 2020 | +25.95% | +104.14% |
| 2021 | +16.21% | +81.05% |
| 2022 | +24.31% | -79.39% |
| 2023 | **-13.89%** | +192.05% |

The strategy is positive in 7 of 8 calendar years and in all three
subperiods, but 2023 is a clear loss and the 2022-23 CAGR is only 3.49%. The
2023 drawdown is the current max-DD episode. The cut tests (excluding one year
at a time) range from 9.30% to 15.40% CAGR, so no single year carries the
result, but excluding 2023 *raises* CAGR to 15.40% — the 2023 loss is a real
drag, not a hidden dependency.

| Cut | Strategy CAGR | Strategy DD | TQQQ ex-year CAGR |
|---|---:|---:|---:|
| ex-2016 | 11.55% | 14.91% | 38.66% |
| ex-2017 | 11.79% | 14.91% | 27.06% |
| ex-2018 | 10.14% | 14.91% | 46.60% |
| ex-2019 | 11.92% | 14.91% | 25.90% |
| ex-2020 | 9.30% | 14.91% | 27.84% |
| ex-2021 | 10.56% | 14.91% | 30.34% |
| ex-2022 | 9.50% | 14.91% | 77.75% |
| ex-2023 | 15.40% | 10.10% | 21.49% |

---

## 5. Correlation to the nine current winners

Daily returns, 2016-01-04 .. 2023-12-29, 2,011 overlapping days.

| Winner | Correlation |
|---|---:|
| ratio-froth | 0.097 |
| vol-scaled-crash-stop | 0.213 |
| relative-value-tqqq | 0.220 |
| fomc-opex-window | 0.178 |
| family-session-timing | 0.147 |
| family-short-reversal | 0.282 |
| family-rebalance-flow | 0.223 |
| family-intraday-microstructure-day | **0.318** |
| family-ml-microstructure | 0.227 |

Range **0.097 .. 0.318**, well below the 0.70 independence gate. The highest
correlation is with `family-intraday-microstructure-day` (0.318), which also
trades a first-30-minute signal; the overlap is real but small because this
family waits for 10:01 and requires a large gap. It is not a duplicate.

---

## 6. Kill criteria

| Criterion | Value | Failed? |
|---|---:|---|
| 1 bp CAGR below 36.72% TQQQ bar | 11.25% | **FAIL** |
| 5 bp CAGR below 0 | 9.57% | pass |
| Fewer than 30 independent events | 152 | pass |
| Fewer than 100 fills | 304 | pass |
| Fewer than 6/8 grid cells positive at 1 bp | 8/8 | pass |
| Negative CAGR in 2+ of 3 subperiods | 0 of 3 | pass |
| Placebo random-day p-value > 0.10 | 0.005 | pass |
| Correlation > 0.70 with a winner | 0.318 | pass |
| Weight drift before a truncation cut | 0.0 | pass |

**Only the absolute-return bar fails.** The strategy is honest about that: it
is not an above-TQQQ strategy. It is a low-exposure, low-drawdown,
near-uncorrelated intraday sleeve with a statistically meaningful event mean
(t = 2.59) and a placebo result that random days do not reproduce.

---

## 7. Risks and limitations

1. **2023 decay.** The 2023 result is -13.9%, and 2022-23 CAGR is 3.49%. The
   effect may be weakening as gap continuation becomes more widely traded, or
   2023 may be a single bad year. The development window cannot distinguish
   these; the honest read is that the recent edge is thin.
2. **Long-only asymmetry.** The book cannot trade gap-down continuation. The
   measured effect may be symmetric in reality; this strategy only harvests
   the long half.
3. **Event concentration.** 152 events, 19/year. The t-stat is 2.59, but a
   handful of large gap days carry a meaningful share of the return (best
   +13.6%, worst -9.9%).
4. **Gap definition.** The gap uses the previous 15:59 close, not an official
   opening auction print. The 09:30 open in the 1-minute archive is the first
   regular-session trade; this is the correct causal input for this panel.
5. **Execution.** TQQQ at the 10:01 and 15:59 opens with a 2% band. The 5 bp
   and 10 bp columns show the strategy survives plausible costs, but a real
   implementation also faces borrow/locate and market-impact costs that the
   flat-bps model does not capture.

## 8. Verdict

**Fail on the program's above-TQQQ CAGR bar; pass on activity, cost stress,
plateau, subperiods, placebo, independence and causality.** The gap and
first-30-minute confirmation select a real continuation event (+62.6 bp mean,
t = 2.59). The best honest description is a small, diversifying intraday
sleeve, not a replacement for TQQQ. If the program only promotes
above-TQQQ strategies, this family should stay in the research archive. If it
also values low-drawdown, near-uncorrelated sleeves, this is the strongest of
the four new families.
