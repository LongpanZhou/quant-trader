# Tail-hedge overlay — report

**Slug:** `family-tail-hedge-overlay`
**Window:** 2016-01-04 → 2023-12-29, development only. The 2024-2026
holdout was never loaded, inspected or used.
**Execution:** `research/bt.py`, 1-minute marks, next-open fills, 2% band,
long-only, weights ≥ 0, sum ≤ 1. Headline 1 bp; 5 bp and 10 bp also reported.
**Primary:** 100% TQQQ core; on the first minute close where TQQQ is ≤ −2.0%
from the session open, switch to 50% TQQQ + 50% synthetic inverse TQQQ from the
next minute's open through the next session's open; then re-enter 100% TQQQ.

> **Holdout note:** a `holdout.json` and `holdout_run.log` appeared in this
> directory from a separate process after the development run. This agent did
> not read, inspect or use them. Every number in this report and in
> `result.json` is development-only.

---

## 1. Headline

| cost | CAGR | max DD | Sharpe | Sortino | vol | invested | fills | turnover | ending equity |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **1 bp** | **90.84%** | **40.23%** | **1.66** | 2.40 | 45.1% | 100% | **3,985** | 57,321x | **$17,413,571** |
| 5 bp | 76.94% | 46.43% | 1.50 | 2.15 | 45.1% | 100% | 3,971 | 36,560x | $9,520,569 |
| 10 bp | 61.35% | 53.57% | 1.29 | 1.86 | 45.1% | 100% | 3,977 | 21,631x | $4,559,504 |

The `bt.stats` invested fraction is 100% because both TQQQ and the synthetic
inverse are invested assets. The useful exposure split is **mean TQQQ 86.35%,
mean inverse 13.65%, mean BIL 0%**. The inverse is held on **27.3% of bars**;
there are **742 trigger sessions out of 2,012 (36.9%)**. The mean hedge weight
while active is 50%.

Turnover is measured by `bt.py` against the *starting* equity, so it is
inflated by the 174x equity growth. The strategy trades a 50% switch on about
93 sessions per year; that is high, and the 5/10 bp rows show it.

## 2. Direct comparison with `ratio-froth` and the cash control

The cash control is the same trigger and the same 50% hedge, but the hedge
asset is BIL instead of the synthetic inverse.

| variant | cost | CAGR | max DD | Sharpe | Sortino | fills |
|---|---:|---:|---:|---:|---:|---:|
| **primary** | **1 bp** | **90.84%** | **40.23%** | **1.66** | 2.40 | 3,985 |
| cash control | 1 bp | 65.41% | 65.81% | 1.24 | 1.77 | 3,133 |
| `ratio-froth` | 1 bp | 61.56% | 39.11% | 1.47 | 2.09 | 619 |
| primary | 5 bp | 76.94% | 46.43% | 1.50 | 2.15 | 3,971 |
| cash control | 5 bp | 53.51% | 69.44% | 1.10 | 1.56 | 3,129 |
| `ratio-froth` | 5 bp | 56.62% | 41.75% | 1.39 | 1.97 | 619 |
| primary | 10 bp | 61.35% | 53.57% | 1.29 | 1.86 | 3,977 |
| cash control | 10 bp | 39.89% | 73.46% | 0.91 | 1.30 | 3,125 |
| `ratio-froth` | 10 bp | 50.67% | 45.03% | 1.28 | 1.82 | 619 |

**Target scorecard:**

| test | result |
|---|---|
| dev CAGR > 61.56% | **yes**, 90.84% |
| dev Sharpe > 1.47 | **yes**, 1.66 |
| dev max DD ≤ 39.11% | **no**, 40.23% (1.1 pp worse) |
| hedge adds CAGR vs cash | **yes**, +25.4 pp |
| hedge reduces DD vs cash | **yes**, −25.6 pp |
| ≥ 100 fills | **yes**, 3,985 |

At 0 bp the primary's DD is **38.95%**, slightly better than ratio-froth's
39.11%; the 1 bp cost adds 1.28 pp. The adjacent **h = 0.50, thr = −1.8%** grid
cell is a strict dominance at 1 bp — **79.55% / 37.68% / 1.56** — but it is not
the primary. The primary is the round 50% / −2.0% cell.

The inverse hedge clearly beats the cash control: the cash control keeps 50%
TQQQ exposure through the tail and therefore keeps a 65.8% drawdown, while the
inverse sleeve neutralises that half. The kill criterion is not met.

## 3. What the hedge actually does

740 episodes, measured from the trigger+1 open to the next session's open
(the actual exit fill).

| statistic | value |
|---|---:|
| episodes | 740 |
| mean TQQQ return over the hedge period | **−0.280%** |
| mean 50/50 portfolio return over the hedge period | **−0.024%** |
| mean log improvement per episode | **+0.364%** |
| total log improvement, 2016-2023 | **+2.695** (≈ +33.7%/yr log) |
| negative-logdiff episodes | **379 (51.2%)** |
| top 10 episodes' share of total logdiff | **63.4%** |
| top 20 episodes' share | **109%** |

The intraday and overnight legs both contribute:

| leg | mean TQQQ | mean 50/50 | mean logdiff |
|---|---:|---:|---:|
| intraday (trigger+1 open → 15:59) | −0.181% | −0.013% | +0.232% |
| overnight (15:59 → next open) | −0.087% | +0.000% | +0.145% |

The overnight leg is about **40% of the log edge**. This is why the primary
holds the hedge overnight and exits at the next open. Exiting at 15:59 instead
gives **69.29% / 75.51% / 1.23**; conditioning the overnight hold on a weak
close gives **71.21% / 65.36% / 1.36**. The next-open re-entry is a real part
of the result, not an execution detail.

**By year (sum of episode logdiff):**

| year | n | mean TQQQ | mean 50/50 | sum logdiff |
|---|---:|---:|---:|---:|
| 2016 | 68 | −0.070% | −0.016% | +0.078 |
| 2017 | 41 | +0.156% | +0.005% | −0.048 |
| 2018 | 100 | −0.689% | +0.000% | **+0.800** |
| 2019 | 68 | +0.200% | −0.019% | −0.124 |
| 2020 | 118 | −0.409% | −0.116% | **+0.625** |
| 2021 | 96 | +0.114% | −0.011% | −0.062 |
| 2022 | 156 | −0.819% | −0.005% | **+1.501** |
| 2023 | 93 | +0.124% | −0.004% | −0.076 |

2018 and 2022 together supply about **85%** of the total log edge; 2020 adds
**23%**; the calm years (2017, 2019, 2021, 2023) net negative. This is a
classic tail-hedge profile: many small bleed days, a handful of very large
saves. It is **not** an all-weather alpha.

**Calendar-year returns (primary, 1 bp):**

| year | primary | ratio-froth | cash control |
|---|---:|---:|---:|
| 2016 | +30.2% | +5% | +25% |
| 2017 | +104.9% | +114% | +108% |
| 2018 | **+56.9%** | −2% | +12% |
| 2019 | **+102.5%** | +52% | +117% |
| 2020 | **+311.0%** | +219% | +218% |
| 2021 | +71.7% | +85% | +82% |
| 2022 | **−11.4%** | −19% | −55% |
| 2023 | **+169.6%** | +155% | +191% |

(`ratio-froth` and cash-control years are rounded from the same daily-close
yearly calculation.)

The primary beats ratio-froth in 2016, 2018, 2019, 2020, 2022 and 2023, and
lags 2017 (104.9% vs 114%) and 2021 (71.7% vs 85%). The 2018 and 2022 rows are
the hedge: +56.9% versus −2% in 2018, and −11.4% versus −19% in 2022.

## 4. 8-cell parameter plateau

All cells at 1 bp, 1-minute marks, primary bolded.

| h | −1.6% | −1.8% | −2.0% | −2.2% |
|---:|---:|---:|---:|---:|
| 0.40 | 63.18 / 52.15 / 1.35 | 73.10 / 44.81 / 1.45 | 81.56 / 51.62 / 1.53 | 79.30 / 57.16 / 1.48 |
| 0.50 | 65.99 / 41.57 / 1.42 | 79.55 / 37.68 / 1.56 | **90.84 / 40.23 / 1.66** | 87.61 / 49.04 / 1.60 |

(values are CAGR / max DD / Sharpe)

**All 8 cells beat 61.56% CAGR.** The CAGR plateau is broad: 63.2% to 90.8%.
The drawdown plateau is narrower: only the h = 0.50 cells at −1.6%, −1.8% and
−2.0% have DD ≤ 41.6%. The h-profile is monotonic — 48.2% at h = 0.10, 60.3% at
h = 0.20, 71.3% at h = 0.30, 81.6% at h = 0.40, 90.8% at h = 0.50 — so the
primary sits at the **50% mandate cap**. h = 0.60-0.75 improves CAGR further
(≈98-106%) but is a net short during the hedge, outside the 10-50% hedge
mandate, and is not used.

## 5. Subperiods

| period | primary CAGR / DD / Sharpe | cash control | ratio-froth |
|---|---:|---:|---:|
| 2016-2019 | **75.76% / 34.75% / 1.68** | 62.95% / 44.50% / 1.39 | 37.07% / 39.11% / 1.13 |
| 2020-2021 | **170.73% / 29.26% / 2.28** | 143.01% / 51.51% / 1.79 | 146.51% / 31.40% / 2.06 |
| 2022-2023 | **58.18% / 38.23% / 1.13** | 15.50% / 62.80% / 0.54 | 45.40% / 24.17% / 1.32 |

The primary beats ratio-froth on CAGR in all three cuts. The 2022-2023 cut is
the weak spot: higher CAGR, but a worse DD (38.23% vs 24.17%) and a worse Sharpe
(1.13 vs 1.32). The 2016-2019 cut is strong, but 2018 Q4 is most of it.

## 6. Placebo / randomized trigger dates

250 full 1-minute backtests per placebo, seeded at 2026.

| placebo | mean CAGR | sd | p95 | max | p(real ≤ placebo) |
|---|---:|---:|---:|---:|---:|
| random sessions, real bar-offset distribution | 23.89% | 12.14 | 45.44% | 74.84% | **0.00 (0/250)** |
| shifted trigger sessions | 23.84% | 12.05 | 44.60% | 76.84% | **0.00 (0/250)** |
| random sessions at 10:30 | 25.78% | 14.45 | 49.13% | 82.95% | **0.00 (0/250)** |

The real 90.84% is above every one of the 750 placebo draws. The nearest
placebo maximum (82.95%) is still 7.9 pp below the real result, so the signal is
significant but not overwhelmingly separated from the luckiest random draw.

A same-session random-bar placebo is **not** used: it selects sessions using a
future trigger (it knows the session will eventually trigger) and is therefore
not a causal test. In an earlier diagnostic it produced a higher CAGR than the
real strategy, which is exactly the hindsight-selection artifact one expects.

## 7. Idea-space tests

### 7.1 Cash-only control (idea 2)

**65.41% / 65.81% / 1.24** at 1 bp, 3,133 fills. The inverse hedge adds
**+25.4 pp CAGR** and **−25.6 pp DD** versus cash at the same trigger. Kill
criterion not met: the inverse hedge adds both.

### 7.2 Confirmation by QQQ underperformance / trend (idea 3)

| variant | CAGR | max DD | Sharpe | fills |
|---|---:|---:|---:|---:|
| no confirmation (primary) | **90.84%** | **40.23%** | **1.66** | 3,985 |
| TQQQ < 3×QQQ (any underperformance) | 67.38% | 62.46% | 1.31 | 3,381 |
| TQQQ < 3×QQQ − 10 bp | 47.90% | 69.99% | 0.98 | 1,335 |
| TQQQ < 3×QQQ − 20 bp | 37.99% | 76.88% | 0.84 | 535 |
| QQQ 3-session return < 0 | 31.48% | 79.80% | 0.78 | 2,123 |
| QQQ above 20-day SMA | 61.32% | 77.97% | 1.09 | 1,909 |
| QQQ 3d < 0 and 20d above SMA | 33.38% | 82.87% | 0.77 | 591 |

Every confirmation filter hurts badly. The best hedges are sudden drops in
otherwise strong markets, not ongoing downtrends or days when TQQQ is already
underperforming 3× QQQ. Breadth data is not in the panel, so QQQ
underperformance was the available proxy; it does not help. The primary uses no
confirmation.

### 7.3 Hedge cost budget (idea 4)

| cap | CAGR | max DD | Sharpe | fills |
|---|---:|---:|---:|---:|
| no cap (primary, ~93/yr) | **90.84%** | **40.23%** | **1.66** | 3,985 |
| 180 episodes/year | 90.84% | 40.23% | 1.66 | 3,985 |
| 120 episodes/year | 85.10% | 43.13% | 1.56 | 3,785 |
| 90 episodes/year | 82.90% | 59.61% | 1.49 | 3,365 |
| 60 episodes/year | 59.13% | 70.18% | 1.14 | 2,491 |

A 120-episode/year budget costs 5.7 pp CAGR and 2.9 pp DD; tighter caps fail
the target. The hedge cost is not the binding constraint; the tail events are.
The primary uses no budget.

### 7.4 Overnight-only-when-close-weak (idea 5)

| variant | CAGR | max DD | Sharpe |
|---|---:|---:|---:|
| always hold overnight, exit next open (primary) | **90.84%** | **40.23%** | **1.66** |
| hold overnight only when close weak | 71.21% | 65.36% | 1.36 |
| exit at 15:59, no overnight | 69.29% | 75.51% | 1.23 |

The unconditional overnight hold is the best of the three. Conditioning the
overnight hold on a weak close removes the hedge on exactly the days when the
overnight continuation does not look weak at 15:59 but still gaps down.

### 7.5 Trigger-time distribution

Timing is not an opening-only artifact:

| window | episodes | share | mean rest-of-day TQQQ |
|---|---:|---:|---:|
| first 15 min | 103 | 13.9% | −0.21% |
| first 30 min | 227 | 30.6% | −0.28% |
| first 60 min | 372 | 50.1% | −0.32% |
| after 60 min | 370 | 49.9% | −0.04% |

## 8. Synthetic construction and costs

**Construction:** the hedge asset is a constant-notional −1x TQQQ NAV built
recursively from the same 1-minute bars, rebalanced every minute, with
1.5%/yr net borrow + financing and no short rebate. It is a **synthetic
long-only sleeve**, not a real short: the portfolio never carries a negative
weight. `bt.py` charges slippage on the synthetic notional.

**Borrow sensitivity (1 bp):**

| borrow + financing | CAGR | max DD | Sharpe |
|---|---:|---:|---:|
| 0.0%/yr | 91.23% | 40.10% | 1.67 |
| 1.5%/yr (primary) | 90.84% | 40.23% | 1.66 |
| 5.0%/yr | 89.96% | 40.56% | 1.65 |
| 10.0%/yr | 88.75% | 41.12% | 1.64 |

Borrow is not the main cost; the 50% switch and its slippage are.

**Construction variants (1 bp):**

| variant | CAGR | max DD | Sharpe |
|---|---:|---:|---:|
| minute-rebalanced inverse TQQQ (primary) | 90.84% | 40.23% | 1.66 |
| daily-reset, no intraday rebalance | 91.66% | 41.84% | 1.67 |
| inverse QQQ instead of inverse TQQQ | 73.38% | 58.88% | 1.39 |

The result is not a minute-rebalancing artifact: the daily-reset version is
slightly better on CAGR and slightly worse on DD. Inverse QQQ is a much weaker
hedge because 50% of a −1x QQQ sleeve only neutralises one-third of the TQQQ
beta.

**Slippage sensitivity:**

| cost | CAGR | max DD | Sharpe |
|---|---:|---:|---:|
| 0 bp | 94.58% | 38.95% | 1.71 |
| 1 bp | 90.84% | 40.23% | 1.66 |
| 2 bp | 87.24% | 41.70% | 1.62 |
| 5 bp | 76.94% | 46.43% | 1.50 |
| 10 bp | 61.35% | 53.57% | 1.29 |
| 20 bp | 33.64% | 65.33% | 0.87 |

This is the main practical caveat. The 1 bp headline is the task convention,
but a 50% switch on ~93 sessions per year is a high-turnover implementation.
At 5 bp the strategy still beats ratio-froth on CAGR and Sharpe, but its DD is
46.43% versus 41.75%; at 10 bp the CAGR is 61.35% and the DD is 53.57%. The
advantage is real but cost-sensitive.

## 9. Correlations to `ratio-froth` and the other eight winners

Daily returns over the dev window, n = 2,011 sessions.

| strategy | correlation |
|---|---:|
| `ratio-froth` | 0.596 |
| `vol-scaled-crash-stop` | **0.846** |
| `relative-value-tqqq` | 0.692 |
| `fomc-opex-window` | 0.585 |
| `family-session-timing` | 0.602 |
| `family-short-reversal` | 0.601 |
| `family-rebalance-flow` | 0.709 |
| `family-intraday-microstructure-day` | 0.652 |
| `family-ml-microstructure` | 0.673 |

The strategy is a TQQQ timing overlay, not a diversifying alpha sleeve. Its
highest correlation is with `vol-scaled-crash-stop` (0.846), another
de-risking strategy. The mechanism is different — a crash-contingent inverse
hedge rather than a vol/ATR de-risk — but the return stream is in the same
TQQQ-beta complex.

## 10. Causality and implementation

- All signals use TQQQ closes through the trigger bar; the target fills at the
  **next minute's open**. No signal uses the fill bar's future.
- The synthetic inverse NAV is recursive: `inv_close[t]` depends only on bars
  up to `t`.
- **Pre-cut test:** truncate the panel at 2020-03-12 11:07 ET and rebuild.
  **409,376 bars compared; max abs weight diff = 0.0; max abs synthetic-NAV
  diff = 0.0.** The 11:07 bar is mid-session and cannot change any prior
  target.
- No full-sample normalisation, no trend/vol/drawdown state, no calendar, no
  ML, no relative-strength gate.
- 2% band, 1 bp headline, 5/10 bp reported. Long-only, row sum ≤ 1.
- Deterministic; the only randomness is the seeded placebo (2026).

## 11. Verdict

**Literal target: yes on CAGR and Sharpe; no on drawdown at 1 bp.**

- Higher dev CAGR than `ratio-froth`: **90.84% vs 61.56%**.
- Higher Sharpe: **1.66 vs 1.47**.
- Max DD: **40.23% vs 39.11%**, 1.1 pp worse at 1 bp; **38.95% at 0 bp**,
  slightly better.
- Fills: **3,985**, well above the 100 floor.
- The cash control is clearly worse (**65.41% / 65.81% / 1.24**), so the
  inverse hedge adds both CAGR and DD reduction. The kill criterion is not met.
- The adjacent −1.8% grid cell is a strict dominance
  (**79.55% / 37.68% / 1.56**) but is not the primary.

**What supports the result:**

- The hedge adds +25.4 pp CAGR and −25.6 pp DD versus the cash control at the
  same trigger.
- All 8 grid cells beat 61.56% CAGR; the CAGR plateau is broad.
- The placebo is significant: 0/250 random or shifted draws reach the real
  CAGR.
- The primary beats ratio-froth CAGR in all three subperiods.
- The pre-cut audit is exactly zero.

**What limits the claim:**

1. **Tail concentration.** 2018 and 2022 supply about 85% of the log edge;
   51.2% of hedge episodes lose money; the top 10 episodes supply 63.4%. The
   effective sample is a handful of crash events, not a broad cross-section.
2. **The hedge is at the 50% cap.** The h-profile is monotonic; h = 0.50 is
   the best allowed, not an interior optimum. h = 0.60-0.75 would be a net
   short and is outside the mandate.
3. **Cost sensitivity.** 10 bp CAGR is 61.35% with 53.57% DD; 5 bp is 76.94%
   with 46.43% DD. The 1 bp headline is optimistic for this turnover.
4. **Correlation.** 0.846 to `vol-scaled-crash-stop`; this is a TQQQ timing
   overlay, not a new diversifier.
5. **2022-2023 is the weak cut.** CAGR is higher than ratio-froth, but DD
   (38.23% vs 24.17%) and Sharpe (1.13 vs 1.32) are worse.
6. **Synthetic execution.** The inverse is not a real short; the result
   assumes a constant-notional −1x TQQQ swap with 1.5%/yr borrow and 1 bp
   slippage. Real swap spreads, margin and borrow terms could be worse.

**Honest description:** a crash-contingent 50% inverse TQQQ hedge that truncates
the left tail of a 100% TQQQ core. It beats `ratio-froth` on development CAGR
and Sharpe and is within 1.1 pp of its drawdown at 1 bp. It is not a robust
all-weather strategy: the edge is concentrated in 2018 and 2022, the hedge sits
at the mandate cap, and the result is cost-sensitive. I would keep it as a
strong development result and a genuinely different family mechanism, but I
would not promote it as a validated winner without the 2024-2026 holdout and a
live-implementation cost check.

## 12. Files

- `HYPOTHESIS.md` — mechanism, exact rules, synthetic construction, grid,
  falsifiers.
- `strategy.py` — `build_weights(ts, opens, closes)`, `build_panel(...)` and
  `main()`; writes `result.json`.
- `result.json` — headline windows, cash control, ratio-froth, 8-cell grid,
  confirmation/budget/overnight variants, cost and borrow sensitivity,
  construction variants, subperiods, placebo, correlations, yearly, drawdown
  anatomy, episode study, pre-cut audit.
- `report.md` — this file.
- `robustness.md` — compact tables for the auxiliary tests.
