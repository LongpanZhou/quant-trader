# Winners audit: ratio froth and the vol-scaled crash system

**Scope.** Read-only attribution of the only two strategies that beat TQQQ over
2016-01-04 .. 2026-10-23. No parameter was tuned, no rule was changed, and no
2024-2026 result was used to select anything. All runs use `research/bt.py`
(next-bar-open fills, 2% band, 1 bp one-way, $100k start, 1-minute bars). All
performance figures are **daily marks** (last bar of each session), matching the
published `curves_full` files; minute-mark drawdowns are noted separately.

**Headline reproduced from current code**

| | CAGR | max DD (daily) | max DD (1-min) | Sharpe | ending multiple | fills |
|---|---:|---:|---:|---:|---:|---:|
| Ratio froth | **62.21%** | **36.65%** | 39.11% | **1.43** | 185.8x | 919 |
| Vol-scaled crash system | **51.32%** | **37.88%** | 39.29% | **1.26** | 87.7x | 3,950 |
| TQQQ buy & hold | 37.54% | 81.68% | 82.29% | 0.82 | 30.6x | 1 |
| QQQ buy & hold | 19.64% | 35.11% | 37.30% | 0.92 | 6.96x | 1 |
| BIL buy & hold | 2.16% | 0.19% | — | — | 1.26x | 1 |

Both `curves_full` files reproduce **exactly** (max absolute relative difference
0.0) from a fresh run of the current code on the same 2,718-session window.

**Bottom line.** Neither winner is a standalone edge:

* **Ratio froth is the banned old base in disguise.** It contains the 165-day
  QQQ SMA gate and the 4% armed stop unchanged. Those two rules alone produce
  **52.89% CAGR / 41.62% DD** — 85% of the headline CAGR and 89% of its
  drawdown reduction versus TQQQ. The ratio overlay adds 9.3 pp CAGR / 5.0 pp
  DD. Its daily returns are **0.942 correlated** with the old base. Its
  2024-2026 "holdout" is in-sample: the overlay was designed and its
  MA/threshold grid chosen on 2017-2026 and 2021-2026 windows.
* **The vol-scaled system is crash-avoidance / TQQQ-beta timing, not a
  standalone alpha.** It is long TQQQ 85.8% of bars (72.0% average weight,
  beta 0.47). A constant blend with the same average exposure earns 32.12% /
  67.48% DD. The stop supplies most of the gap: removing it drops the strategy
  to 35.89% / 62.99%. It is **0.71-0.77 correlated** with the old 165-day base,
  fails its own pre-registered `< 0.60` diversity rule, and in 2024-2026 earns
  **36.19% vs TQQQ's 44.93%** (only DD is better).

Both 2024-2026 "holdouts" are contaminated at the parameter-selection level:
the ratio overlay was designed and tuned on 2017-2026/2021-2026, and the vol
`0.70` multiplier is the centre of a round-2 plateau on the same windows. The
vol's 36.2% vs 44.9% is therefore worse than a clean test would be, not better:
the parameter choice had seen the period and still lagged.

The genuinely independent rebuilds that passed the brief's diversity rule earn
4-22% CAGR on dev (6-40% on the holdout), not 51-62%. The two winners' returns
require TQQQ beta timing.

---

## 1. Exposure and beta

Weights are per-minute targets; "bar %" is the fraction of the 1,056,144 bars.
Average gross leverage counts TQQQ at 3x.

| | Ratio froth | Vol-scaled |
|---|---:|---:|
| average weight QQQ | 21.05% | 0.00% |
| average weight TQQQ | 53.72% | 71.95% |
| average weight BIL | 25.23% | 28.05% |
| average gross leverage (TQQQ=3x) | 1.82x | 2.16x |
| bars with TQQQ > 0 | 53.7% | 85.8% |
| bars with QQQ > 0 | 21.1% | 0.0% |
| bars 100% cash | 25.2% | 14.2% |
| bars 100% TQQQ | 53.7% | 40.2% |
| average TQQQ size when in TQQQ | 100% (binary) | 83.8% |
| fills (full window) | 919 | 3,950 |
| fills per session | 0.34 | 1.45 |
| turnover, × start equity | 41,019x | 51,802x |
| turnover, × mean equity per year | 103x | 186x |
| **beta to TQQQ** | **0.378** | **0.468** |
| correlation to TQQQ | 0.636 | 0.800 |
| **beta to QQQ** | **1.122** | **1.387** |
| correlation to QQQ | 0.633 | 0.795 |
| up-capture of TQQQ days | 54.2% | 62.5% |
| down-capture of TQQQ days | 46.3% | 58.0% |
| static blend at same average weights: CAGR / DD | 28.90% / 60.02% | 32.12% / 67.48% |
| static blend Sharpe | 0.84 | 0.83 |
| **actual CAGR / DD** | **62.21% / 36.65%** | **51.32% / 37.88%** |

**Answer to Q1: no, they are not simply high TQQQ exposure.** The ratio
strategy is in TQQQ only 54% of the time and has a TQQQ beta of 0.38; it looks
more like a 1.12-beta QQQ timing strategy. The vol strategy has a 72% average
TQQQ weight but a beta of only 0.47 because the weight is cut in high-vol
periods. Holding the *same average weights* statically earns 29-32% CAGR with
60-68% drawdown — 19-33 pp less CAGR and 24-30 pp more drawdown than the
winners. The timing, not the average exposure, is doing the work.

---

## 2. Ratio froth: the old base with a froth filter

### 2.1 The rule is still the old base

`research/agents2/ratio-pairs/strategy.py` keeps the round-1 winner unchanged:

1. **165-day QQQ SMA gate** (`SMA_N = 165`): risk-on when QQQ's prior close is
   above its prior 165-day SMA, else BIL.
2. **4% armed intraday stop** (`STOP = 0.04`, `MA_FAST = 20`,
   `ARM_BUF = 0.01`): armed when QQQ's first-minute price is below its prior
   20-day SMA × 1.01; if armed and TQQQ's 1-minute close falls 4% below the
   session open, move to BIL at the next minute's open for the rest of the
   session and the night.
3. **New ratio overlay** (`RATIO_MA = 200`, `THETA = 0.18`): if the prior
   close's `log(TQQQ/QQQ ratio / 200-day MA)` exceeds 0.18, hold QQQ instead of
   TQQQ for the next session (the stop still applies).

`winner_state()` is byte-for-byte the old base; the only new code is
`froth_flag()` and the day-weight branch. The full window is 2016-2026 with
`warmup_days=0`, so the 165-day SMA and 200-day ratio MA are cold until
~Sep/Oct 2016; 2016 is mostly BIL. That is causal but dilutes the headline
(10-year 2017-start result is 69.50%, not 62.21%).

### 2.2 Component attribution (same window, same engine)

| Variant | CAGR | max DD | Sharpe | avg TQQQ w | note |
|---|---:|---:|---:|---:|---|
| TQQQ buy & hold | 37.54% | 81.68% | 0.82 | 100% | |
| **Old base: gate + 4% stop** | **52.89%** | **41.62%** | **1.17** | 74.8% | 85.0% of headline CAGR |
| Gate only (no stop, no overlay) | 42.20% | 57.82% | 0.98 | 78.2% | |
| Stop only (no gate, no overlay) | 51.82% | 60.32% | 1.01 | 93.6% | strong CAGR, 60% DD |
| Gate + overlay, no stop | 54.05% | 52.41% | 1.23 | 56.7% | |
| Overlay only, QQQ defensive | 49.01% | 81.13% | 0.96 | 78.5% | no DD control |
| Overlay only, BIL defensive | 53.41% | 81.14% | 1.01 | 78.5% | no DD control |
| **Full (QQQ defensive)** | **62.21%** | **36.65%** | **1.43** | 53.7% | published headline |
| Full, BIL defensive | 65.47% | 36.54% | 1.50 | 53.7% | diagnostic only |

Sequential decomposition:

| Step | Δ CAGR | Δ max DD |
|---|---:|---:|
| TQQQ → stop only | +14.28 pp | −21.36 pp |
| stop only → gate + stop | +1.07 pp | −18.70 pp |
| TQQQ → gate only | +4.66 pp | −23.86 pp |
| gate only → gate + stop | +10.69 pp | −16.20 pp |
| gate + stop → gate + stop + overlay | +9.32 pp | −4.97 pp |
| gate only → gate + overlay (no stop) | +11.85 pp | −5.41 pp |
| gate + overlay → full (add stop) | +8.16 pp | −15.76 pp |

The old base supplies **85.0% of the headline CAGR** (52.89 / 62.21; 87.1% on
the fair-stop variant, 52.89 / 60.72) and **89.0% of the drawdown reduction**
versus TQQQ (40.06 of 45.03 pp). On the old strategy's own 10-year window the
same split is **58.68 / 41.62** for the base versus **69.38 / 36.65** for the
overlay (daily marks) — 84.6% of CAGR from the base. (The old report's
58.80 / 44.56 and 69.50 / 39.11 are the same runs on minute marks.)

Within the base, the **stop is the larger return contributor** (stop-only
51.82% vs gate-only 42.20%), while the **gate is the larger drawdown
contributor** when added to the stop (+1.07 pp CAGR but −18.70 pp DD). The
headline needs both; neither is investable alone.

Adding the overlay without the stop (54.05% / 52.41%) to the old base adds
only +1.16 pp CAGR and **increases** drawdown by 10.79 pp; the overlay only
becomes a risk improvement when the stop is present. The rules are
complementary, not independent.

One rule asymmetry: on froth days the book holds QQQ but the stop still
watches TQQQ. A 4% TQQQ move is only ~1.33% QQQ, so the QQQ leg is effectively
stopped at ~1.3%. The published variant fires 26 froth-day stops out of 160;
a fair 4%-on-QQQ stop fires 1, and disabling the stop on QQQ days gives
**60.72% / 36.54%** versus the published **62.21% / 36.65%**. The asymmetry is
worth about +1.5 pp CAGR, not the headline, but it is an economic asymmetry:
the QQQ leg is stopped three times tighter than its own 4% rule would imply.
On the fair variant the overlay's incremental contribution is +7.8 pp CAGR /
−5.1 pp DD over the old base, rather than +9.3 / −5.0.

### 2.3 What the ratio overlay actually does

* 584 froth sessions (21.5% of 2,718), in **67 episodes**; median 3 sessions,
  longest 71 (2020-11 to 2021-02).
* Froth days are genuinely bad for TQQQ: next-session open-to-open TQQQ mean
  **−0.155%/day** vs **+0.311%/day** otherwise; QQQ −0.044%/day vs
  +0.114%/day. Cumulative TQQQ return on froth days **−70.9%**, versus
  **+10,414%** on non-froth days.
* But both assets fall on froth days. Holding **BIL** instead of QQQ is better
  on this sample: 65.47% / 36.54% vs 62.21% / 36.65%. Minute-level sleeve P&L:
  TQQQ +58.0%/yr, QQQ **−1.35%/yr**, BIL +0.47%/yr. The QQQ leg is a drag; the
  signal is really a **risk-off / cash-timing signal**, not a QQQ-vs-TQQQ
  pairs trade. The report's own reason for QQQ (hedge against a 1999-style
  melt-up) is reasonable, but it is not where the return comes from.
* The overlay's yearly contribution is episodic: +42.7 pp in 2020, +19.8 pp in
  2021, +22.5 pp in 2024, +32.6 pp in 2025, but −2.9 pp in 2017 and 0.0 in
  2022 (no froth days). It is a crash hedge that paid in specific years, not a
  steady alpha.

### 2.4 Holdout contamination

This is the critical selection problem. The old strategy's `report.md` chooses
`MA=200, theta=0.18` from a 35-point surface evaluated on **10y 2017-2026 and
5y 2021-2026**. Both windows contain 2024-2026. The 5-year window is
2021-10-25 .. 2026-10-23. So **2024-2026 is not a holdout for ratio froth**:
every year from 2017 through 2026 was used in design or selection. The only
period not used is 2016, which is a cold-start BIL year and says nothing about
the rule.

That matters because the overlay's 2024-2026 contribution is large:

| 2024-2026 | CAGR | max DD | Sharpe |
|---|---:|---:|---:|
| Old base (gate + stop, no overlay) | 48.37% | 33.08% | 1.06 |
| Ratio froth (with overlay) | 65.40% | 26.50% | 1.40 |
| TQQQ | 44.93% | 58.00% | 0.91 |

The old base alone is already a modest beat over TQQQ in 2024-2026; the
overlay adds +17.0 pp CAGR and −6.6 pp DD, but that increment is exactly the
part that was selected on the holdout years. It cannot be counted as
out-of-sample evidence.

The vol strategy has a subtler version of the same problem. Its `report.md`
says the `0.70` ATR multiplier is the centre of the round-2 plateau
(0.55-0.85), and the round-2 test windows are 10y 2017-2026 and 5y 2021-2026
(`research/agents2/vol-scaled-crash-stop/report.md`, lines 24-25 and 206-217).
Both include 2024-2026. The revisit code never loaded a holdout bar and the
weights are causal, but the parameter values were selected on data that
includes the holdout. So 2024-2026 is a clean test of the *implementation*, not
of the *parameter choice*. The fact that the strategy still lags TQQQ on CAGR
in that period is evidence against a persistent edge, not for it.

**Verdict on Q2:** the headline is a trend/timing artifact built on the banned
old base. The gate and stop are unchanged and supply 85% of the CAGR. The
ratio overlay is a real but secondary crash/risk-off filter (+9.3 pp CAGR,
−5.0 pp DD over the full window) and its apparent 2024-2026 strength is
in-sample.

---

## 3. Vol-scaled crash system: a TQQQ crash-avoidance overlay

### 3.1 The actual rule

From `research/revisit/vol-scaled-crash-stop/strategy.py` (frozen parameters):

```
ATR14[k]  = mean true range of TQQQ daily bars over the prior 14 sessions / prior close
size[k]   = clip(0.040 / ATR14[k], 0.40, 1.00)
dist[k]   = clip(0.70 * ATR14[k], 0.025, 0.040)

default:    TQQQ = size[k], BIL = 1 - size[k]
trigger:    first 1-minute close < session_open * (1 - dist[k])
on trigger: TQQQ sleeve -> BIL on that bar (fills next bar open);
            stay 100% BIL for the rest of the session and the night
re-entry:   next session's open at size[k+1]
```

There is no QQQ/TQQQ moving-average gate and no QQQ position. It is long TQQQ
by default, sized inversely to TQQQ ATR, with a one-sided volatility-scaled
stop. The `baseline_weights()` 165-day function exists only as a correlation
reference and is never used for positions (lines 117-139).

### 3.2 Component attribution (same window, same engine)

| Variant | CAGR | max DD | Sharpe | avg TQQQ w | stop events |
|---|---:|---:|---:|---:|---:|
| TQQQ buy & hold | 37.54% | 81.68% | 0.82 | 100% | 0 |
| Constant 72% TQQQ / 28% BIL (same avg exposure) | 32.12% | 67.48% | 0.83 | 72.0% | 0 |
| Vol sizing only, no stop | 35.89% | 62.99% | 0.91 | 82.9% | 0 |
| Fixed 4% stop + vol sizing | 45.24% | 39.01% | 1.13 | 76.4% | 441 |
| **Full: ATR stop + vol sizing** | **51.32%** | **37.88%** | **1.26** | 72.0% | 607 |
| Binary 100% TQQQ + ATR stop | 60.13% | 55.86% | 1.13 | 85.8% | 607 |
| 100% TQQQ + fixed 4% stop | 53.27% | 56.77% | 1.04 | 90.4% | 441 |
| Constant 72% + ATR stop | 45.60% | 41.34% | 1.15 | 61.8% | — |
| Constant 72% + fixed 4% stop | 40.75% | 42.21% | 1.05 | 64.9% | — |

Decomposition versus the same-average-exposure blend:

| Source | Δ CAGR | Δ max DD |
|---|---:|---:|
| Average exposure (72% TQQQ / 28% BIL static) | 32.12% baseline | 67.48% baseline |
| + vol sizing (no stop) | +3.77 pp | −4.49 pp |
| + ATR stop (full vs sizing-only) | **+15.43 pp** | **−25.11 pp** |
| ATR stop vs fixed 4% stop (both sized) | +6.08 pp | −1.13 pp |
| Sizing vs binary, both with ATR stop | −8.81 pp | −17.98 pp |
| 100% TQQQ + fixed 4% stop | 53.27% | 56.77% |

**Answer to Q3:** the stop is the dominant contributor; volatility sizing is
mostly a drawdown-reduction layer that costs CAGR; the ATR-scaled distance is
better than a fixed 4% stop by about 6 pp CAGR at similar DD. The ATR stop
fires 607 times versus 441 for the fixed 4% stop, mostly in calm years
(2017, 2019, 2021), because it tightens to 2.5-3% when ATR is low; that is
where the +6 pp comes from. The strategy is indeed "long TQQQ most of the time
with a volatility-scaled stop."

### 3.3 Is the edge in the signal or just crash avoidance?

* **Event study:** 607 stop events. Mean move from the exit fill to the next
  session's open is **−0.27%**; median +0.05%; 49% negative. Mean rest-of-
  session move after the trigger is **−0.21%**. The per-event edge is small and
  comes from the left tail, not from a directional forecast.
* **Matched-frequency placebo:** 40 random-exit sets with the same number of
  exits (from `result.json`, full-window because of the cache issue below):
  mean CAGR **26.1%**, median 24.6%, best 41.4%; mean DD 62.6%, best 51.4%.
  The actual 51.3% / 37.9% beats all 40. So the *timing* of the exits is
  informative — it is not random crash exposure.
* **But the economics are crash avoidance.** The stop does not predict up
  days; it truncates the left tail. The strategy gives up upside in some strong
  bulls: 2025 +26.6% vs TQQQ +34.3%, 2026 +5.8% vs +26.5% (2024 was an
  exception, +73.0% vs +58.2%). Its 2022 is much worse than the old base's
  because it lacks the slow gate: 2022 calendar-year **−33.2% vs −16.7%**, and
  its max drawdown episode (2021-12-27 to 2023-01-05) is **37.9%**, versus
  **20.1%** for the old base in calendar 2022.

### 3.4 The old-base comparison is the one that matters

| Full 2016-2026 | CAGR | max DD | Sharpe |
|---|---:|---:|---:|
| Old base (165d gate + 4% stop) | **52.89%** | 41.62% | 1.17 |
| Vol-scaled system | **51.32%** | 37.88% | 1.26 |

| 2024-2026 | CAGR | max DD | Sharpe |
|---|---:|---:|---:|
| Old base (165d gate + 4% stop), reference | **48.37%** | 33.08% | 1.06 |
| Vol-scaled system (code frozen before the run) | **36.19%** | 31.74% | 0.97 |
| TQQQ | 44.93% | 58.00% | 0.91 |

The old base is a benchmark, not an independent holdout strategy: its 165-day
and 4% rules predate the revisit but were selected on overlapping data. The
vol code was frozen before the 2024-2026 run, so the implementation is clean,
but the `0.70` multiplier is the centre of a round-2 plateau evaluated on
2017-2026/2021-2026 (see 2.4), and the 4.0% cap is the round-1 stop from the
same family. Even with that parameter-selection advantage, the vol strategy
**lags TQQQ on CAGR** (36.2% vs 44.9%) and gives up 12.2 pp CAGR to the
old-base reference for only 1.3 pp lower DD. It is a lateral re-implementation
of the same crash-avoidance bet.

Correlation evidence:

| Daily-return correlation | Vol-scaled |
|---|---:|
| vs old base (gate + stop) | **0.769** |
| vs causal 165-day gate only | **0.716** |
| vs ratio froth full | 0.738 |
| vs its own pre-registered 165-day baseline, clean dev | **0.713** |
| vs its own baseline as computed in `result.json` (stale after 2023) | 0.755 |

The strategy's own falsifier #1 says: retire as overlay-only if daily-return
correlation with the 165-day baseline is `>= 0.60`. It measures 0.71-0.77. By
its own pre-registered rule it is an overlay, not a standalone strategy.

**Verdict on Q3:** the edge is crash avoidance plus TQQQ beta, with a genuine
but secondary volatility-scaling signal in the stop distance. The clean
holdout shows no CAGR edge over TQQQ (36.2% vs 44.9%) and no edge over the old
base. It is a better-managed TQQQ exposure, not a new standalone edge.

---

## 4. Holdout behaviour: 2020 or 2024-2026?

### 4.1 Subperiods

Daily marks. `ex-2020` is the compounded return with 2020 removed; Sharpe is
not shown for that column because splicing the series makes it meaningless.

| Period | Ratio froth CAGR / DD | Vol-scaled CAGR / DD | TQQQ CAGR / DD | QQQ CAGR / DD |
|---|---:|---:|---:|---:|
| 2016-2019 | 37.51% / 36.65% | 51.03% / 30.60% | 48.60% / 57.97% | 19.16% / 22.72% |
| 2020 | 219.86% / 31.22% | 175.65% / 28.18% | 100.30% / 69.89% | 46.10% / 28.44% |
| 2021-2023 | 58.14% / 24.96% | 37.13% / 37.88% | 6.08% / 81.68% | 10.58% / 35.11% |
| 2024-2026 | 65.40% / 26.50% | 36.19% / 31.74% | 44.93% / 58.00% | 22.69% / 22.74% |
| **dev 2016-2023** | **61.56% / 36.65%** | **57.65% / 37.88%** | 35.98% / 81.68% | 18.86% / 35.11% |
| **holdout 2024-2026** | **65.40% / 26.50%** | **36.19% / 31.74%** | 44.93% / 58.00% | 22.69% / 22.74% |
| **ex-2020** | **51.42% / 36.65%** | **42.39% / 37.88%** | 32.40% / 81.68% | 17.24% / 35.11% |

### 4.2 Calendar-year returns

Close-to-close, 2026 through 2026-10-23.

| Year | Ratio froth | Old base (no overlay) | Vol-scaled | TQQQ | QQQ |
|---|---:|---:|---:|---:|---:|
| 2016 | 5.4% | 5.4% | 6.8% | 18.6% | 9.3% |
| 2017 | 115.9% | 118.8% | 128.1% | 118.3% | 32.6% |
| 2018 | 2.8% | 2.0% | 11.1% | −19.6% | −0.1% |
| 2019 | 52.4% | 48.0% | 91.3% | 133.1% | 38.9% |
| 2020 | 234.2% | 191.5% | 188.2% | 109.6% | 48.4% |
| 2021 | 82.1% | 62.3% | 44.9% | 83.0% | 27.4% |
| 2022 | −16.7% | −16.7% | −33.2% | −79.1% | −32.5% |
| 2023 | 155.0% | 149.1% | 162.1% | 198.4% | 54.8% |
| 2024 | 86.1% | 63.6% | 73.0% | 58.2% | 25.6% |
| 2025 | 78.4% | 45.7% | 26.6% | 34.3% | 20.8% |
| 2026 YTD | 21.6% | 20.5% | 5.8% | 26.5% | 15.1% |

**Answer to Q4:**

* **Ratio froth:** not just 2020. Ex-2020 it still earns 51.4% vs TQQQ's
  32.4%, and the 2024-2026 holdout is strong (65.4% vs 44.9%). But the holdout
  is **in-sample** (the overlay was designed and tuned on 2017-2026 and
  2021-2026), so the 2024-2026 strength cannot be counted as independent
  evidence. Note it lags TQQQ badly in the strong bulls 2019 (+52.4% vs
  +133.1%) and 2023 (+155.0% vs +198.4%); the edge is crash avoidance, not
  consistent outperformance. The overlay's biggest single-year contributions
  are 2020 (+42.7 pp over the old base), 2025 (+32.6 pp), 2024 (+22.5 pp) and
  2021 (+19.8 pp).
* **Vol-scaled:** the outperformance is concentrated in the **2017-2023 crash
  years**, especially 2020 (+188% vs +110%), 2022 (−33% vs −79%) and 2018
  (+11% vs −20%). The 2024-2026 result is **worse than TQQQ on CAGR** (36.2%
  vs 44.9%); it only wins on drawdown and Sharpe. Neither winner has a pristine
  2024-2026 holdout (ratio was tuned on it; the vol `0.70` multiplier came from
  a round-2 plateau that included it), but that makes the vol result worse, not
  better: the parameter choice had seen the period and still lagged.

### 4.3 Cost sensitivity

CAGR at 0/1/2/5/10 bp one-way on traded notional (daily marks):

| Cost | Ratio froth | Vol-scaled |
|---|---:|---:|
| 0 bp | 63.60% | 54.01% |
| 1 bp | 62.21% | 51.32% |
| 2 bp | 60.84% | 48.67% |
| 5 bp | 56.79% | 41.00% |
| 10 bp | 50.27% | 29.08% |

The ratio strategy keeps a 50%+ CAGR even at 10 bp. The vol strategy loses
22 pp of CAGR from 1 to 10 bp and falls below TQQQ at 10 bp. Its 3,950 fills
and 186x-mean-equity annual turnover make the 1 bp headline the optimistic end
of the plausible cost range. This is a second, independent reason not to treat
the vol headline as a durable edge.

---

## 5. Data and curve integrity

### 5.1 Curves match the current code

We rebuilt both strategies from current source on the full 2016-01-04 ..
2026-10-23 panel (2,718 sessions, 1,056,144 bars) and compared the daily
curves with `research/revisit/curves_full/*.json`:

| Curve | Published days | Fresh days | Max abs relative diff | Published CAGR / DD | Fresh CAGR / DD |
|---|---:|---:|---:|---:|---:|
| `ratio-froth.json` | 2,718 | 2,718 | **0.0** | 62.21% / 36.65% | 62.21% / 36.65% |
| `vol-scaled-crash-stop.json` | 2,718 | 2,718 | **0.0** | 51.32% / 37.88% | 51.32% / 37.88% |

No staleness in the curve values themselves. But there are three labeling /
provenance problems.

### 5.2 `ratio-froth` is the old agents2 strategy, not the standalone rebuild

`research/full_missing.py` lines 79-87 load
`research/agents2/ratio-pairs/strategy.py` and save it as `ratio-froth`. It is
**not** `research/revisit/ratio-pairs/` (the standalone rebuild). The latter
earns 18.96% / 34.59% on dev and 24.82% / 22.94% on the holdout — nowhere near
62%. Anyone reading the `ratio-froth` curve as "the ratio-pairs rebuild" is
reading the old base.

### 5.3 The vol strategy's `dev` block is contaminated by a full-window cache

`research/revisit/vol-scaled-crash-stop/dev_panel.npz` currently contains
**1,056,144 bars, 2016-01-04 .. 2026-10-23**, not the declared dev end
2023-12-29. `load_dev_panel()` returns any existing cache without checking the
requested dates. Consequently `main()` runs the full window and writes
full-window numbers into `windows.dev`:

* `result.json` `windows.dev.1bp`: CAGR 51.46%, DD 39.29%, events 607,
  fills 3,950 — exactly the **full 2016-2026** minute-mark result.
* A clean dev run on a physically truncated panel: CAGR **57.85%**, DD 39.29%,
  events **452**, fills **2,897** (minute marks; daily marks 57.65% / 37.88%).
* The `yearly` block in `result.json` stops at 2023 (hard-coded
  `range(2016, 2024)`), so the file mixes a full-window CAGR with dev-only
  yearly returns. It is internally inconsistent.

The curve is consistent with the full run, so the headline is not wrong — but
the "dev" label is. Any comparison of "dev 51.46%" against the audit table's
"dev 57.84%" is comparing different windows. The strategy file's dev window is
2016-2023, and the full-data weights are causal (we verified the first
781,880 bars are identical, max abs diff 0.0), so the 2024-2026 path is a valid
test of the implementation. Parameter provenance is a separate issue — see
5.6. The cache should be deleted before any clean dev run.

### 5.4 The vol correlation baseline freezes after 2023

`baseline_weights()` filters the daily Yahoo file to `date <= 2023-12-29`
(line 126). On the full run it forward-fills that baseline through 2026, so the
reported `corr_vs_165d_baseline = 0.755` is measured against a baseline that is
flat after 2023. A live causal 165-day gate gives **0.716** (our own rebuild)
and the old base with stop gives **0.769**. The conclusion (fails `< 0.60`) is
unchanged, but the exact 0.755 is not a clean full-window number.

### 5.5 Bar and print integrity

* 2,718 sessions, 1,056,144 bars; timestamps strictly increasing, no
  duplicates; no NaN or non-positive prices; OHLC high/low consistent on every
  bar (0 violations).
* 21 half-days have 211 bars (09:30-13:00 inclusive) and are handled by
  `bt.HALF_DAYS`; no after-hours prints leak in.
* 7 sessions have missing minutes: 2016-02-02 (9 bars, 11:18-11:26),
  2016-02-22 (50 bars, 10:26-11:17), 2020-03-09/12/16/18 (14 bars each,
  the market-wide circuit-breaker halts), and 2026-08-31 (2 bars,
  09:47-09:48). The 2020 gaps are real exchange halts; the 2016 and 2026 gaps
  are vendor outages. None can inflate a long-only strategy materially; if
  anything they can hide stop triggers.
* Intra-session 1-minute extremes: QQQ worst −1.74%, TQQQ worst **−4.96%**
  (2025-04-07). TQQQ's only four minutes beyond ±5% are positive rebound
  spikes on 2020-03-03/18 and 2025-04-07/09; each is confirmed by a ~3x QQQ
  move and continues in the same direction, so none is a spike-and-reverse bad
  print. The largest overnight gaps (2020-03-16, 2024-08-05, 2025-04-03/07)
  are real.
* Daily panel close vs Yahoo adjusted close: mean absolute difference 0.02%
  for QQQ, 0.05% for TQQQ; maximum 0.84% / 0.66% on volatile days, because the
  panel marks at 15:59 and Yahoo at 16:00. Mean daily-return difference
  0.03% / 0.07%, maximum 0.96% / 1.20% (2020-03-13/16). This is a marking
  difference, not a return inflation.
* BIL is forward-filled on the QQQ calendar and split-adjusted before
  2017-11-30; its daily return difference vs Yahoo is < 0.06%. No issue.

### 5.6 Parameter provenance (selection, not execution)

Both 2024-2026 "holdouts" are contaminated at the selection level:

* **Ratio froth:** `MA=200, theta=0.18` chosen from a 35-point surface on
  10y 2017-2026 and 5y 2021-2026; both include the 2024-2026 holdout. The
  strategy's `report.md` also notes the result is "a crash hedge, not alpha"
  and that the +10.7 pp of CAGR is "not something to underwrite."
* **Vol-scaled:** `0.70` is the centre of the round-2 plateau identified on
  10y 2017-2026 and 5y 2021-2026; the 4% cap is the round-1 stop from the same
  family of tests; `0.040` is TQQQ's full-sample median ATR. The revisit code is
  dev-only and causal, but the parameter values are not. The 2024-2026 return is
  therefore an out-of-sample test of the *implementation*, not of the
  *strategy design*.

This does not change the attribution: the full-window numbers are correct and
the weights are causal. It does change how the 2024-2026 evidence should be
read. Neither winner has a clean holdout; the vol's 2024-2026 underperformance
is the more informative result because its parameters had seen that period.

**Data verdict:** the curves are internally consistent and the prices are
clean enough for the attribution. The integrity problems are **selection and
labeling**, not bad prints: the ratio strategy has no clean holdout, the vol
strategy's `result.json` dev block is the full window, and both winners'
2024-2026 results are contaminated by parameter selection.

---

## 6. Could a standalone rebuild replicate it?

The genuinely independent rebuilds that passed the brief's dev gates and the
`< 0.60` correlation rule:

| Strategy | Dev CAGR / DD | Holdout CAGR / DD | Corr vs 165d |
|---|---:|---:|---:|
| `intraday-seasonality` | 21.84% / 43.75% | 40.48% / 31.75% | 0.26 |
| `ratio-pairs` (standalone rebuild) | 18.96% / 34.59% | 24.82% / 22.94% | 0.53 |
| `intraday-mean-reversion` | 11.31% / 31.47% | 15.62% / 27.66% | 0.13 |
| `gap-capitulation-reversal` | 4.18% / 12.49% | 5.99% / 2.29% | 0.03 |

(From `SUMMARY.md`; these are 1-minute-mark numbers, the convention used for
the rebuild gates. Daily marks differ by ~1-2 pp of drawdown.)

None is near 51-62%. The best independent holdout is `intraday-seasonality`
at 40.5% / 31.8%, and its dev CAGR is 21.8%.

The two winners are not comparable to these:

* **Ratio froth** is the old 165-day base plus a ratio overlay. The base alone
  is 52.9% / 41.6%. The overlay is a secondary crash filter, and its 2024-2026
  gain is in-sample. The ratio signal by itself (standalone rebuild) earns
  20.5% over 10 years.
* **Vol-scaled** is a standalone *implementation* but not a standalone *edge*:
  72% average TQQQ, beta 0.47, stop-driven, 0.71-0.77 correlated with the old
  base, and no CAGR edge over TQQQ in the 2024-2026 holdout. It fails its own
  pre-registered diversity rule.

### Final verdict

| Winner | Category | Why |
|---|---|---|
| **Ratio froth** | **(b) the banned old base in disguise** | Contains the unchanged 165-day QQQ SMA gate and 4% armed stop; those supply 85% of CAGR and 89% of DD reduction; 0.942 daily correlation with the old base; overlay adds 9.3 pp CAGR / 5.0 pp DD (7.8 / 5.1 on a fair 4%-QQQ stop); no clean holdout (overlay designed and tuned on 2017-2026 and 2021-2026); BIL defensive beats the published QQQ defensive, so the "pairs" leg is not the source. |
| **Vol-scaled crash system** | **(c) crash-avoidance / beta timing, behaviourally close to (b)** | No 165-day gate in code, but 72% average TQQQ, beta 0.47, stop supplies +15.4 pp CAGR / −25.1 pp DD over sizing-only; constant same-exposure blend earns 32.1% / 67.5%; 0.71-0.77 correlation with the old base and 0.769 with the old base+stop; fails its own `< 0.60` rule; 2024-2026 36.2% vs TQQQ 44.9% (the `0.70` parameter had seen that period); 5 bp costs cut CAGR to 41.0%, 10 bp to 29.1%. It is a better-managed TQQQ exposure, not a new standalone edge. |

**Could a standalone rebuild replicate it? No.** The 51-62% headline returns
require TQQQ beta timing (a trend gate, a crash stop, or both). The independent
signals that survive the brief's diversity rule earn 4-22% CAGR on dev (6-40%
on the holdout). The two winners are the old base and a crash-avoidance overlay
on TQQQ, not standalone alpha.

---

## Appendix: reproduction

All scripts are in `research/revisit/audit/` and write JSON next to themselves.
They are read-only with respect to strategy code and curves.

| Script | Output | Purpose |
|---|---|---|
| `winners_prep.py` | `cache/full_panel_ohlc.npz` | 2016-2026 1-minute OHLC panel |
| `winners_rebuild.py` | `winners_rebuild.json` | Fresh runs, curve match, exposure, beta |
| `winners_attrib.py` | `winners_attrib.json` | Gate/stop/overlay and vol component runs |
| `winners_extra.py` | `winners_extra.json` | Bar-level exposure, matched-exposure stops, froth episodes |
| `winners_subperiod.py` | `winners_subperiod.json` | Subperiods, ex-2020, costs, drawdowns, crash days |
| `winners_integrity.py` | `winners_integrity.json` | Bars, OHLC, prints, Yahoo comparison, stop events |
| `winners_staleness.py` | `winners_staleness.json` | Cache provenance, clean dev, 10y/5y cross-checks |
| `winners_vol_baseline_corr.py` | `winners_vol_baseline_corr.json` | Correlation vs the 165-day baseline |
| `winners_corr.py` | `winners_corr.json` | Daily-return / exposure correlation matrix |
| `winners_ratio_defensive.py` | `winners_ratio_defensive.json` | QQQ vs BIL defensive leg |
| `winners_ratio_stop_asym.py` | `winners_ratio_stop_asym.json` | TQQQ-based stop on QQQ days vs fair QQQ stop |
| `winners_ratio_stop_only_corrected.py` | `winners_ratio_stop_only_corrected.json` | Corrected stop-only control (TQQQ default) |
| `winners_ratio_subperiod.py` | `winners_ratio_subperiod.json` | Old base vs full, dev/holdout |
| `winners_ratio_2022.py` | `winners_ratio_2022.json` | 2021/2022/2023 comparison |
| `winners_static_blend.py` | `winners_static_blend.json` | Same-average-weight static blends |
| `winners_return_attrib.py` | `winners_return_attrib.json` | Minute-level sleeve P&L |
| `winners_froth_years.py` | console | Froth days and overlay delta by year |
| `winners_intrabar.py` / `winners_missing.py` | console | Bad-print and missing-minute checks |

Reproduce with:

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
python research\revisit\audit\winners_prep.py
python research\revisit\audit\winners_rebuild.py
python research\revisit\audit\winners_attrib.py
```

No strategy file, result file, website asset, or git state was changed by this
audit.
