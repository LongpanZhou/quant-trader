# Multi-horizon quiet capitulation reversal — report

**Slug:** `capitulation-reversal-v2`
**Window:** 2016-01-04 .. 2023-12-29 (development only; the 2024-2026 holdout
was not loaded by this agent). Note: a `holdout.json` and `holdout_run.log`
appeared in this folder at 04:30 from a separate process after the development
run; this agent did not read or use them.
**Execution:** `research/bt.py`, 1-minute marks, next-open fills, 2% band,
long-only, weights >= 0, sum <= 1. Headline cost 1 bp; 5 bp and 10 bp also
reported.
**Primary:** QQQ -3% over 3 sessions **or** -5% over 10 **or** -8% over 15, on
volume <= 1.2x the prior 20-day average; buy TQQQ at the event-day close; hold
one session.

---

## 1. Headline

| cost | CAGR | max DD | Sharpe | Sortino | vol | TQQQ exposure | fills | turnover |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **1 bp** | **39.75%** | **26.44%** | **1.46** | **2.26** | 25.1% | **5.88%** | 743 | 4257x |
| 5 bp | 34.67% | 28.18% | 1.32 | 2.02 | 25.1% | 5.88% | 743 | 3508x |
| 10 bp | 28.58% | 30.30% | 1.13 | 1.72 | 25.0% | 5.88% | 743 | 2777x |

The stated bar is TQQQ 36.72% CAGR / 82.29% max DD / 0.82 Sharpe. **At 1 bp the
primary passes both legs** (39.75% > 36.72%, 26.44% < 82.29%). **At 5 bp it
fails the CAGR leg** (34.67% < 36.72%) while still beating the drawdown leg by
54 pp. The local `bt.benchmark` TQQQ is 36.15% / 82.29% / 0.80; the 0.57 pp
difference from the task's 36.72% is a bar-convention difference, and the
strategy clears both figures at 1 bp.

The strategy holds TQQQ on 5.88% of bars (119 events, one session each) and
BIL otherwise. Ending equity at 1 bp is $1,447,614 from $100,000.

## 2. Benchmarks

| | CAGR | max DD | Sharpe | Calmar |
|---|---:|---:|---:|---:|
| strategy 1 bp | 39.75% | 26.44% | 1.46 | 1.50 |
| TQQQ | 36.15% | 82.29% | 0.80 | 0.44 |
| QQQ | 18.91% | 37.30% | 0.90 | 0.51 |
| 165-day QQQ SMA baseline | 44.76% | 58.76% | 1.03 | 0.76 |

Daily-return correlation is **0.392 to TQQQ** and **0.061 to the 165-day
baseline**. The strategy is a diversifying, cash-heavy sleeve; it does not beat
the 165-day baseline on CAGR (39.75% vs 44.76%) but has a much lower drawdown
(26.4% vs 58.8%) and a higher Sharpe (1.46 vs 1.03).

## 3. Yearly returns

| year | strategy | TQQQ | note |
|---|---:|---:|---|
| 2016 | +12.5% | +19.9% | 4 events |
| 2017 | +0.7% | +114.5% | no real event; cash drag |
| 2018 | +40.1% | -20.8% | 14 events, 78% win |
| 2019 | +17.0% | +148.2% | 4 events |
| 2020 | +178.4% | +104.1% | 20 events, +5.7% mean |
| 2021 | -3.6% | +81.1% | 2 events, mean -1.0%; one large loss |
| 2022 | +117.5% | -79.4% | 67 events, +1.6% mean |
| 2023 | +33.6% | +192.0% | 8 events, 88% win |

Six of eight years are positive. The strategy's best years are the volatile,
mean-reverting ones (2018, 2020, 2022); it lags badly in calm bull years (2017,
2019, 2023), which is expected for a 5.9%-exposure sleeve. The 2021 loss is two
events with a mean of -1.0% (one large loss, one small gain), so it is not
evidence of a broken edge, but it is also not a meaningful sample.

## 4. Event study

119 events. Entry at the event-day 15:59 open, exit at the next session's 15:59
open:

| statistic | value |
|---|---:|
| mean | +2.60% |
| median | +2.07% |
| win rate | 64.7% |
| t-stat | 4.33 |
| bootstrap 95% CI | +1.42% .. +3.76% |
| bootstrap p(mean <= 0) | 0.0000 |
| worst / best | -14.40% / +22.20% |

**Decomposition:**

| leg | mean | t | win |
|---|---:|---:|---:|
| overnight 15:59 -> 09:30 | +0.80% | 2.30 | 58% |
| intraday 09:30 -> 15:59 | +1.78% | 3.77 | 66% |
| full close-to-close | +2.60% | 4.33 | 65% |

Both legs are positive; the intraday leg is larger. The close entry captures the
0.80% overnight that a next-open entry would miss. This is the main reason the
close-entry design beats the earlier next-open version.

**By leg combination (rows overlap; the single-leg rows are exclusive of the
deeper legs):**

| leg | n | mean | win |
|---|---:|---:|---:|
| q3 only | 34 | +1.48% | 59% |
| q10 only | 31 | +2.11% | 68% |
| q15 only | 11 | +4.39% | 91% |
| q10 & q15 | 25 | +5.38% | 72% |
| all three | 8 | +6.99% | 75% |

The deeper and overlapping events carry the strongest returns. The q3-only
sleeve is the weakest part of the primary; it adds event count and
diversification, not the core edge.

**By year:**

| year | n | mean | win |
|---|---:|---:|---:|
| 2016 | 4 | +3.21% | 75% |
| 2018 | 14 | +2.73% | 79% |
| 2019 | 4 | +3.84% | 75% |
| 2020 | 20 | +5.70% | 75% |
| 2021 | 2 | -1.00% | 50% |
| 2022 | 67 | +1.59% | 55% |
| 2023 | 8 | +3.03% | 88% |

The per-event mean is positive in every year with n >= 4. 2022 has the most
events and the weakest per-event mean; its large P&L contribution comes from
frequency (67 events), not from a higher edge.

## 5. Pre-registered grid and plateau

All at 1 bp, 1-minute marks.

| # | variant | n | exposure | CAGR | max DD | Sharpe |
|---|---|---:|---:|---:|---:|---:|
| 1 | core q10 only | 71 | 3.50% | 28.85% | 17.01% | 1.33 |
| 2 | core q15 only | 39 | 1.93% | 22.99% | 15.42% | 1.29 |
| 3 | core q10 \| q15 | 85 | 4.19% | 34.53% | 16.87% | 1.46 |
| 4 | **primary** (q3 \| q10 \| q15) | 119 | 5.88% | **39.75%** | **26.44%** | **1.46** |
| 5 | primary, q3 -2.5% | 129 | 6.33% | 41.09% | 26.44% | 1.48 |
| 6 | primary, q3 -3.5% | 109 | 5.38% | 38.74% | 21.09% | 1.47 |
| 7 | primary, rvol 1.15 | 102 | 5.03% | 30.63% | 26.44% | 1.31 |
| 8 | primary, rvol 1.25 | 131 | 6.42% | 27.50% | 38.38% | 1.01 |

The **q3 threshold is a plateau**: rows 4-6 give 38.7-41.1% CAGR, 21-26% DD and
Sharpe 1.47-1.48. The **volume cap is a cliff**: 1.15 gives 30.6%, 1.20 gives
39.75%, 1.25 gives 27.5% with a 38.4% DD. The 1.2 cutoff is the fragile
parameter. The core without q3 is 34.53% / 16.87% / 1.46 at 1 bp; its cost
sensitivity is 31.05% / 17.80% / 1.35 at 5 bp and 26.82% / 19.09% / 1.20 at
10 bp.

## 6. Placebo

200 random-event backtests with the same count (119), entry (event close), hold
(one session) and size rule:

| | value |
|---|---:|
| placebo mean CAGR | 1.73% |
| placebo sd | 5.47% |
| placebo p95 | 10.71% |
| placebo max | 16.08% |
| p(real >= placebo) | 0.000 |

The real 39.75% is far outside the random-event distribution. The event timing,
not the 5.9% exposure or the close-entry mechanics, carries the result.

## 7. Cut tests and concentration

| period | CAGR | max DD | Sharpe |
|---|---:|---:|---:|
| 2016-2019 | 16.77% | 12.54% | 1.38 |
| 2020-2021 | 64.11% | 15.39% | 1.77 |
| 2022-2023 | 71.19% | 26.44% | 1.67 |
| ex-2020 | 22.99% | 26.44% | 1.14 |
| ex-2022 | 27.02% | 15.39% | 1.44 |

The strategy is positive in all three sub-periods, but 2022-2023 dominates.
Excluding 2020 or 2022 still leaves 23-27% CAGR with a 15-26% DD, so the edge is
not a single year; the point estimate is still regime-tilted.

**Top-event concentration:**

| exclusion | CAGR | max DD | Sharpe |
|---|---:|---:|---:|
| none | 39.75% | 26.44% | 1.46 |
| top 1 event | 36.45% | 26.44% | 1.38 |
| top 3 events | 30.09% | 26.44% | 1.25 |
| top 5 events | 25.74% | 26.44% | 1.11 |
| top 10 events | 17.14% | 26.74% | 0.83 |

Removing the single best event puts the CAGR at 36.45%, i.e. essentially at the
bar; removing the top three drops it to 30.1%. The 1 bp pass depends on a
handful of large events. This is the second fragility, alongside the volume
cliff.

The maximum drawdown is -26.44%, from 2022-03-08 to 2022-05-04 — a 2022
event-cluster drawdown, not a 2020 crash. It is well inside the 82.29% TQQQ
drawdown but is the reason the strategy is not a low-vol replacement for cash.

## 8. Causality and implementation

- All signals use QQQ data through **15:58 ET**; the target is written on the
  15:58 bar and fills at the **15:59 open**. The signal is not computed from
  the official 16:00 close.
- Daily volume is summed through 15:58, not the full session, so the volume
  ratio is causal.
- Truncating the panel at **2022-01-03** leaves every prior weight identical
  (586,637 bars compared). No full-sample normalization, no future data.
- The 2024-2026 holdout was never loaded; the panel's end is 2023-12-29.

## 9. Sample adequacy

119 events over 8 years, ~15/year, 5.9% of sessions, one session each. The
event mean is +2.60% with t = 4.33 and a bootstrap CI of +1.42% to +3.76%; that
is large enough to reject a zero mean. It is **not** large enough to rule out
regime dependence: 87 of 119 events (73%) are in 2020-2022, and 2021 has two
events. The q3-only leg has 34 events and a +1.48% mean; the q10/q15 core has 85
events and a +3.05% mean (t=4.23). The core is the statistically stronger
object; the q3 leg is the diversifying sleeve.

## 10. Honest verdict

**Marginal 1 bp pass. Not a validated standalone.**

- It clears the stated bar at 1 bp: 39.75% vs 36.72% CAGR, 26.44% vs 82.29% max
  DD, Sharpe 1.46 vs 0.82, Calmar 1.50 vs 0.44.
- It fails the CAGR leg at 5 bp (34.67%) and 10 bp (28.58%).
- The volume cap at 1.2 is a cliff; the P&L is concentrated in the top 3-5
  events; 73% of events are in 2020-2022. The pass is not robust enough to
  promote without the holdout.
- The **robust core** (q10/q15, no q3) is 34.53% / 16.87% / 1.46 at 1 bp, 31.05%
  at 5 bp, 26.82% at 10 bp. It is a clean risk-adjusted improvement — Sharpe
  1.46 vs 0.80, Calmar 2.05 vs 0.44, DD 16.9% vs 82.3% — at the cost of 5.2 pp
  of CAGR versus the primary, and 2.2 pp below the bar. If robustness matters
  more than the headline, the core is the better strategy.
- The honest description is: a **marginal 1 bp TQQQ-beater with a strong
  risk-adjusted profile and two known fragilities**, not a clean replacement
  for TQQQ. Do not quote the 39.75% as a validated result until the holdout is
  run on the frozen file.

## 11. What it is not

It is not `gap-capitulation-reversal` with a new parameter: the event horizon
(3/10/15-day cumulative vs one-day close/intraday), entry (close vs next open),
hold (1 vs 3 sessions), vehicle (always TQQQ vs QQQ/TQQQ switch) and exit (time
only vs event-low + hard stop) are all different. It is not
`intraday-mean-reversion` (no intraday trigger; close-to-close hold), and not
`gap-fill-fade` (long TQQQ; no gap fade; no short). It uses no 165-day base, no
old stop and no old weight matrix; the 165-day baseline appears only in the
correlation/benchmark table.

## 12. Files

- `HYPOTHESIS.md` — mechanism, exact rules, falsifiers, pre-registered grid.
- `strategy.py` — `build_weights(ts, o, c)` and `main()`; writes `result.json`.
- `result.json` — metrics, event dates, grid, cuts, placebo, yearly.
- `report.md` — this file.
