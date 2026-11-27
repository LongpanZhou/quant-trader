# Short-horizon dip reversal — report

**Slug:** `family-short-reversal`
**Window:** 2016-01-04 → 2023-12-29, development only. The 2024-2026
holdout was never loaded, inspected or used. A `holdout.json` and
`holdout_run.log` appeared in this folder at 15:11 from a separate process
after the development run; this agent did not read or use them.
**Execution:** `research/bt.py`, 1-minute marks, next-open fills, 2% band,
long-only, weights ≥ 0, sum ≤ 1. Headline 1 bp; 5 bp and 10 bp also reported.
**Primary:** QQQ down two sessions in a row **or** QQQ 3-session return
≤ −1.5%, signal at the 15:59 close; buy TQQQ at the next open at weight 1.0;
exit at the open after 5 held sessions, rolling the exit forward if a new
event fires; BIL otherwise.

---

## 1. Headline

| cost | CAGR | max DD | Sharpe | Sortino | vol | TQQQ exposure | fills | turnover |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **1 bp** | **45.89%** | **68.27%** | **0.94** | 1.32 | 59.4% | **62.96%** | 457 | 3,694x |
| 5 bp | 42.59% | 68.77% | 0.90 | 1.27 | 59.4% | 62.96% | 457 | 3,236x |
| 10 bp | 38.57% | 69.39% | 0.85 | 1.20 | 59.4% | 62.96% | 457 | 2,749x |

The stated bar is TQQQ **36.72% CAGR / 82.29% max DD / 0.82 Sharpe** on daily
closes. The local 1-minute `bt.benchmark` TQQQ is 36.15% / 82.29% / 0.80; the
0.57 pp difference is a mark-convention difference. The primary clears both
figures at 1 bp, 5 bp and 10 bp.

Ending equity at 1 bp is $2,040,495 from $100,000. The sleeve is in TQQQ 63.0%
of bars and in BIL the other 37.0%; the `bt.stats` "exposure" field is 100%
because BIL is an invested asset, so the TQQQ figure above is the relevant one.

Daily-return correlation to TQQQ is **0.894**. This is a timing overlay on
leveraged Nasdaq beta, not a diversifying alpha sleeve.

## 2. Benchmarks and leg attribution

| | CAGR | max DD | Sharpe | Calmar | TQQQ exposure |
|---|---:|---:|---:|---:|---:|
| primary 1 bp | 45.89% | 68.27% | 0.94 | 0.67 | 63.0% |
| `q2dn` only | 35.13% | 57.63% | 0.83 | 0.61 | 55.1% |
| `q3` only | 40.15% | 67.48% | 0.89 | 0.59 | 42.6% |
| TQQQ | 36.15% | 82.29% | 0.80 | 0.44 | 100% |
| QQQ | 18.91% | 37.30% | 0.90 | 0.51 | — |

Neither leg clears the CAGR bar alone: the 2-day streak is 35.13% (1.6 pp
short) and the 3-day return is 40.15% but at only 42.6% exposure. The union
gets 45.89% because the 2-day leg supplies exposure and the 3-day leg adds the
sharper-dip tilt. This is a genuine interaction, but it is also why the
strategy ends up as a 63%-invested dip-buying beta rather than a rare event
sleeve.

## 3. Yearly returns

| year | strategy | TQQQ | note |
|---|---:|---:|---|
| 2016 | +54.9% | +19.9% | caught the February bottom and the post-election rally |
| 2017 | +58.4% | +114.5% | lagged badly in a calm bull year |
| 2018 | **−33.2%** | −20.8% | worse than TQQQ: bought the Q4 2018 falling knife |
| 2019 | +132.2% | +148.2% | lagged |
| 2020 | **+235.3%** | +104.1% | the crash-recovery payoff |
| 2021 | +95.8% | +81.1% | beat TQQQ |
| 2022 | **−62.8%** | −79.4% | lost less than TQQQ, still catastrophic |
| 2023 | +112.5% | +192.0% | lagged the 2023 melt-up |

Six of eight years are positive, but the profile is exactly what a dip-buying
overlay should look like: it wins in crash-recovery years (2016, 2020, 2021),
loses heavily in bear years (2018, 2022), and lags in calm melt-ups (2017,
2019, 2023). The 2020 and 2022 numbers are the honest measure of the
falling-knife risk.

## 4. What the signal actually trades

138 closed episodes from 522 signal days. Entry at the next open, exit at the
open after the rolling 5-session clock:

| statistic | value |
|---|---:|
| episodes | 138 |
| mean episode return | +3.00% |
| median | +3.99% |
| win rate | 65.9% |
| t-stat | 2.88 |
| bootstrap p(mean ≤ 0) | 0.0019 |
| bootstrap 95% CI | +0.96% .. +5.00% |
| worst / best | −49.48% / +45.75% |
| mean episode length | 9.18 sessions |
| median / max episode length | 7 / 29 sessions |

**By year:**

| year | n | mean | win |
|---|---:|---:|---:|
| 2016 | 16 | +3.55% | 69% |
| 2017 | 18 | +2.74% | 78% |
| 2018 | 16 | **−2.71%** | 38% |
| 2019 | 19 | +4.90% | 84% |
| 2020 | 18 | **+9.02%** | 83% |
| 2021 | 17 | +3.63% | 65% |
| 2022 | 17 | **−2.54%** | 47% |
| 2023 | 17 | +4.56% | 59% |

The arithmetic episode mean is positive in six of eight years, but 2018 and
2022 are negative, and those are the years where the episodes cluster. The
event-study mean is not the portfolio return: overlapping episodes in a crash
share the same bad days, so the union compounds far worse than the average
trade suggests. The 2022 cluster is the reason the portfolio loses 62.8% while
the average 2022 episode is only −2.54%.

The **episode length** is the first mandate problem. The rule is a rolling
5-session exit: a new 2-day-streak event during the hold resets the clock. The
mean episode is 9.18 sessions, the median 7, the maximum 29. This is not a
1-5 session trade; it is a persistent dip-buying position that goes flat only
after five sessions pass without a new dip.

## 5. Pre-registered grid and plateau

All at 1 bp, 1-minute marks. Cells 1-6 vary the 3-day threshold at hold 5;
cells 7-8 vary the hold at threshold −1.5%.

| # | 3-day threshold | hold | CAGR | max DD | Sharpe | TQQQ exp | episodes |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | −0.50% | 5 | 50.86% | 74.96% | 0.98 | 71.5% | 131 |
| 2 | −0.75% | 5 | 54.06% | 74.96% | 1.02 | 69.3% | 134 |
| 3 | −1.00% | 5 | 49.10% | 72.04% | 0.97 | 66.6% | 135 |
| 4 | **−1.50%** | **5** | **45.89%** | **68.27%** | **0.94** | **63.0%** | **138** |
| 5 | −2.00% | 5 | 43.27% | 67.75% | 0.91 | 60.9% | 142 |
| 6 | −3.00% | 5 | 43.22% | 67.48% | 0.92 | 58.5% | 143 |
| 7 | −1.50% | 3 | 27.95% | 66.39% | 0.73 | 47.9% | 211 |
| 8 | −1.50% | 4 | 28.05% | 69.78% | 0.72 | 56.1% | 166 |

**The threshold is a broad plateau; the exit is a spike.** All six threshold
cells clear the bar (43.2-54.1% CAGR, 67.5-75.0% DD), so the signal definition
is not a single-cell artefact. But the hold row collapses on both sides of 5:
h3 is 27.95%, h4 is 28.05%, h5 is 45.89%, and h6 (outside the mandate) is
30.40%. The 5-session exit is the only horizon that passes, and it passes by a
wide margin over its neighbours. That is not a plateau; it is a knife-edge.

Why the spike? The 5-session clock is what keeps the sleeve invested through
the 2020 rebound and the 2022 bear in the exact pattern that produced the
result. At h4 the sleeve exits and re-enters at different points and misses
the largest rebound days; at h6 it stays too long and takes more of the bear.
The point estimate is path-dependent, not a smooth horizon effect.

## 6. Strict 1-5 session cap: the mandate problem

The primary uses a **rolling** 5-session exit: a new event during the hold
resets the clock. If instead the rule is a hard 5-session cap from the first
entry (new events are ignored while held), the same signals produce:

| exit rule | CAGR | max DD | Sharpe | TQQQ exp | episodes |
|---|---:|---:|---:|---:|---:|
| rolling 5-session (primary) | 45.89% | 68.27% | 0.94 | 63.0% | 138 |
| hard 5-session cap | **31.40%** | 67.48% | 0.77 | 52.7% | 212 |

The hard cap **fails the CAGR bar by 5.3 pp**. The pass therefore requires the
position to chain through dip clusters; it is not a strict 1-5 session
reversal. The average 9.2-session episode is the same fact from the other
side.

The strict grid shows where the edge actually lives:

| 3-day threshold | hard-cap CAGR | hard-cap DD | hard-cap Sharpe | exp |
|---:|---:|---:|---:|---:|
| −0.50% | 46.88% | 67.48% | 0.96 | 59.4% |
| −0.75% | 54.07% | 67.48% | 1.05 | 57.7% |
| −1.00% | 40.79% | 67.48% | 0.89 | 55.7% |
| **−1.50%** | **31.40%** | **67.48%** | **0.77** | **52.7%** |
| −2.00% | 28.72% | 67.48% | 0.74 | 51.2% |
| −3.00% | 24.52% | 67.48% | 0.68 | 48.9% |

The hard cap passes only at the **mild** end (−0.5% to −1.0%), where the
strategy is a 56-59%-invested dip-buying beta. It fails at the pre-registered
−1.5% primary and everywhere deeper. In other words: the family's edge is in
frequent shallow dips, not in the "short, sharp decline" the mandate
describes. The sharp-decline version needs the rolling exit to pass, and the
rolling exit is not a 1-5 session trade.

## 7. Placebo

Two placebos, each 100 full 1-minute backtests:

| | mean CAGR | sd | p95 | max | p(real ≥ placebo) | mean exposure |
|---|---:|---:|---:|---:|---:|---:|
| shifted signal dates | 24.57% | 12.06% | 45.57% | 53.66% | **0.05** | 62.9% |
| random entry days | 31.70% | 12.96% | 51.00% | 78.14% | **0.12** | 77.3% |

The **shift** placebo preserves the signal count and the clustering and is
exposure-matched (62.9% vs 63.0%). The real 45.89% is at the 95th percentile:
p = 0.05, borderline, not a clean rejection.

The literal **random-entry** placebo is not significant (p = 0.12), but it runs
at 77.3% exposure, i.e. it has more TQQQ beta than the real strategy. That
makes it conservative for the real result, but it also means it is not an
apples-to-apples test. The honest summary is that the signal timing is **weakly
distinguishable** from random dip-buying; the result is not a strong
statistical edge.

## 8. Cut tests and drawdown anatomy

| period | CAGR | max DD | Sharpe | TQQQ exp |
|---|---:|---:|---:|---:|
| 2016-2019 | 38.25% | 50.90% | 0.98 | 57.8% |
| 2020-2021 | 159.51% | 67.48% | 1.65 | 59.5% |
| 2022-2023 | **−10.24%** | 67.83% | 0.19 | **76.8%** |
| ex-2020 | **25.61%** | 68.27% | 0.71 | 56.1% |
| ex-2022 | 61.34% | 67.48% | 1.20 | 52.1% |

The 2022-2023 cut shows the problem clearly: the sleeve is **more** invested
(76.8%) in the worst two years than in any other cut. The 2-day-streak leg
keeps firing through the bear, and the rolling exit keeps the position on. The
2016-2019 cut passes the CAGR bar, which is the one piece of evidence that the
strategy is not *only* 2020. But ex-2020 is 25.61%, and the 2022-2023 cut is
negative. The pass is the net of a huge 2020-2021 and a catastrophic 2022.

**Worst drawdowns:**

| peak → trough | depth | context |
|---|---:|---|
| 2021-12-28 → 2022-10-13 | **−68.3%** | the 2022 bear; the strategy buys every 2-day dip all the way down |
| 2020-02-25 → 2020-05-14 | −67.5% | the COVID crash; the rebound rescued the year |
| 2018-02-02 → 2019-03-13 | −50.9% | the Q4 2018 bear; 2018 is −33.2% vs TQQQ −20.8% |
| 2023-08-03 → 2023-12-29 | −37.0% | a late-2023 drawdown in a strong year |

The maximum drawdown is **68.27%, in 2022**, not 2020. That is the exact
falling-knife scenario the mandate warns about: a sustained bear keeps firing
the 2-day-streak leg, the rolling exit keeps the sleeve fully invested, and
the 3x fund compounds down. The strategy loses less than TQQQ (−68.3% vs
−82.3%) but it is still a catastrophic drawdown, well above the "ideally
<60%" target. 2018 is worse than TQQQ on both return and drawdown, which is
the clearest evidence that the dip signal has no bear-market protection.

## 9. Allowed risk overlays

The mandate allows a hard stop and vol-target sizing as risk overlays. They
were tested; none is used in the primary because none improves the trade-off:

| overlay | CAGR | max DD | Sharpe | TQQQ exp |
|---|---:|---:|---:|---:|
| primary | **45.89%** | **68.27%** | **0.94** | 63.0% |
| stop 10% + 5d block | 39.07% | 71.64% | 0.94 | 51.4% |
| stop 12% + 5d block | 37.38% | 70.68% | 0.90 | 52.8% |
| stop 15% + 5d block | 34.17% | 78.66% | 0.84 | 54.3% |
| vol target 40% | 41.65% | 68.27% | 0.89 | 62.7% |
| vol target 50% | 42.86% | 68.27% | 0.90 | 62.8% |
| vol target 60% | 43.69% | 68.27% | 0.91 | 62.8% |
| profit target 6% + 5d block | 25.63% | 74.92% | 0.69 | 51.6% |
| profit target 8% + 5d block | 28.62% | 67.54% | 0.73 | 54.7% |
| profit target 10% + 5d block | 30.37% | 67.54% | 0.75 | 56.1% |

Every overlay lowers CAGR. The stops do not lower the drawdown either: the
10% stop has a *higher* DD (71.6%) than the primary because it locks in losses
and re-enters after a 5-session block, missing the rebound. A stop without a
re-entry block is nullified entirely: the 2-day-streak signal fires on the
stop day and re-enters at the same open. The vol target scales the whole
position but leaves the drawdown essentially unchanged because the 2022
exposure is already at the vol-target cap. The profit target caps the rebound
days that are the reason the strategy works. There is no free risk overlay
here; the falling-knife risk is in the signal, not in the position sizing.

## 10. Causality and implementation

- All signals use QQQ closes through **15:59 ET**; the target is written on the
  15:59 bar and fills at the **09:30 open** of the next session. No signal uses
  the 16:00 print.
- Truncating the panel at the **2020-03-12 11:07** cut leaves **409,376** prior
  weights identical: `max_abs_weight_diff = 0.0`. The 11:07 bar is a
  maintenance bar; the position was set at the 2020-03-11 close. The partial
  day cannot change any pre-cut weight because the builder only uses the prior
  complete session's close for a new signal.
- No full-sample normalisation. No 20/50/100/150/165/200-day moving average,
  no volatility/drawdown regime as the primary signal, no relative-strength
  gate, no drawdown-recovery circuit breaker.
- The 20-session warm-up is a data warm-up, not a trend filter. The strategy
  has no trend filter at all.
- Long-only, weights are 0 or 1, sum ≤ 1, BIL is the flat asset. 2% band;
  457 fills; 1 bp headline plus 5/10 bp.
- The output is deterministic; the only randomness is the placebo, seeded at
  11.

## 11. Honest verdict

**Literal dev pass: yes. Robust family edge: no.**

**Falsifier scorecard (from `HYPOTHESIS.md`):**

| # | falsifier | result | fired? |
|---:|---|---|---|
| 1 | primary 1 bp CAGR ≤ 36.72% | 45.89% | no |
| 2 | primary max DD ≥ 82.29% | 68.27% | no |
| 3 | threshold is a single-cell spike | all six threshold cells pass (43.2-54.1%) | no |
| 4 | h3/h4 fall > 5 pp below h5 | h3 27.95%, h4 28.05%, h5 45.89% | **yes** |
| 5 | ex-2020 CAGR < 36.72% | 25.61% | **yes** |
| 6 | placebo p > 0.05 | shift 0.05, random-entry 0.12 | **partly** |
| 7 | 10 bp CAGR < 36.72% | 38.57% | no |

Two falsifiers fire outright and a third is borderline. The literal pass is
real, but the pre-registered robustness tests do not support a family claim.

What the evidence supports:

- The pre-registered primary earns **45.89% CAGR / 68.27% DD / 0.94 Sharpe**
  at 1 bp, and still 38.57% at 10 bp. It clears the stated 36.72% / 82.29% bar
  on both legs at all three cost levels.
- The threshold is a genuine plateau: all six threshold cells clear the bar,
  and the result is not a single-threshold artefact.
- The 2016-2019 cut is 38.25%, so the strategy is not purely a 2020 bet.

What breaks the claim:

1. **The exit is a spike, not a plateau.** h3 = 27.95%, h4 = 28.05%, h5 =
   45.89%, h6 = 30.40%. The result is tied to the exact 5-session clock.
2. **The strict 1-5 session cap fails.** The primary's 45.89% requires a
   rolling exit; a hard 5-session cap gives 31.40% and fails the bar. The mean
   episode is 9.2 sessions (max 29), so this is not a 1-5 session reversal.
3. **The pass is 2020-dependent.** Ex-2020 CAGR is 25.61%; the 2020-2021 cut
   is 159.5% and the 2022-2023 cut is −10.2%. The strategy is a crash-recovery
   and bull-beta overlay, not an all-weather reversal premium.
4. **2022 is a disaster.** The max drawdown is −68.3% (2021-12-28 to
   2022-10-13), and 2022 is −62.8% calendar. 2018 is −33.2% vs TQQQ −20.8%.
   The falling-knife risk is realized, not hypothetical.
5. **The placebo is only borderline.** The exposure-matched shift test gives
   p = 0.05; the random-entry test gives p = 0.12. The timing edge is weak.
6. **The DD is above the ideal.** 68.27% is below the hard 82.29% bar but well
   above the "ideally <60%" target.

The honest description is: **a high-beta, 63%-invested TQQQ dip-buying overlay
that clears the literal development bar because of the 2020-2021 crash
recovery, with a −68% 2022 drawdown and a pass that depends on a rolling
5-session exit rather than a strict 1-5 session hold.** If the mandate is read
as a hard 1-5 session cap, the family **fails** (31.40% at the pre-registered
primary; the only strict passes are the mild −0.5% to −1.0% variants, which
are high-exposure dip-buying beta rather than sharp-decline reversal).

I would not promote this as a validated standalone TQQQ beater. It is worth
keeping as a marginal, clearly labelled research result; the next step would
be a different regime treatment for 2022 (explicitly outside this mandate) or
a genuinely different short-horizon signal, not more tuning of the 5-session
clock.

## 12. Files

- `HYPOTHESIS.md` — mechanism, exact rules, pre-registered grid, falsifiers.
- `strategy.py` — `build_weights(ts, o, c)` and `main()`; writes `result.json`.
- `result.json` — metrics, grid, strict grid, cuts, placebos, event study,
  overlays, yearly, pre-cut test.
- `report.md` — this file.
