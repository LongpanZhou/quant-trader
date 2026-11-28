# Cross-Asset Multi-Horizon Dual Momentum — development report

**Window:** 2016-01-04 → 2023-12-29 (1-minute marks).
**Holdout 2024-2026:** not loaded, not inspected.
**Costs:** 1 bp headline; 5 bp and 10 bp reported.
**Execution:** next-open fills, 2% band, long-only, weights ≥ 0, sum ≤ 1.

## Verdict first

| | Strategy A | TQQQ buy-and-hold | Task bar |
|---|---:|---:|---:|
| CAGR | **40.00%** | 36.15% (local 1m close-to-close) | 36.72% |
| Max drawdown | **42.89%** | 82.29% | < 82.29%, ideally < 60% |
| Sharpe (1m) | **1.08** | 0.80 | 0.82 |
| Calmar | **0.93** | 0.44 | 0.45 |
| Risky exposure | 68.1% | 100% | — |
| Daily corr to TQQQ | 0.59 | 1.00 | — |
| CAGR at 10 bp | **38.31%** | — | — |

**Headline: pass.** A beats the 36.72% bar by 3.28 pp at 1 bp and by 1.59 pp at
10 bp, with a 39.4 pp lower max drawdown.

**But this is not a validated strategy.** It is an exploratory Revision 2,
designed after the pre-registered Revision 1 failed on the same development
window. Three pre-registered robustness checks fail: the placebo p-value is
0.10 (10% of random circular shifts beat the CAGR), the short gate depends on
the 42-day leg (21-only and 63-only both fail), and replacing either 2018 or
2022 with TQQQ's return drops CAGR below 36.72%. The edge is a two-year
crash-avoidance bet, not a steady premium. The full evidence is below; the
verdict is "headline pass, fragile, needs a true holdout."

## 1. What was tested, and why there are two revisions

The mandate asked for a cross-asset dual-momentum rotation across QQQ, SPY and
BIL, with TQQQ as the leveraged Nasdaq sleeve when relative and absolute
momentum agree, weekly or monthly rebalance, and a vol-targeted risky sleeve.

**Revision 1** was the clean pre-registration: one absolute lookback (126 or
252 sessions), one relative lookback of the same length, a 50% or 65% vol
target, weekly or monthly, eight combinations. It was run first.

**Revision 1 failed.** Primary A (126/65/weekly) returned 31.04% CAGR / 54.86%
DD / 0.86 Sharpe. No grid point passed. The diagnosis is in §2.

**Revision 2** is the final design. It replaces the single absolute lookback
with a multi-horizon ensemble: a short 21/42 OR gate and a medium 84/105/126
majority gate. It keeps the relative QQQ/SPY gate and the vol target. The
eight-point grid is target {80,90,100}% × relative {126,252} × weekly, plus
two monthly controls. It passes the headline bar.

Revision 2 was designed after Revision 1 failed and after diagnostics on the
same window. The short-horizon set was informed by those diagnostics. This is
stated in `HYPOTHESIS.md` §11 and in `result.json` (`exploratory: true`). It is
why the result is a candidate, not a clean out-of-sample pass.

**Variants tried.** The formal grids contain 8 (Revision 1) + 8 (Revision 2) =
16 combinations. In addition, the diagnostic search that produced Revision 2
ran roughly 200 backtests across single lookbacks (21-252 sessions), vol
targets (35-100%), stop overlays, state rules and relative horizons.
`result.json` reports `variants_tried: 26` for the formal grid + neighbours +
placebo; that is not the full diagnostic count. The final design was selected
from the broader search, which is exactly why it is labelled exploratory. The
report does not claim that 26 trials were the whole search.

## 2. Revision 1: the pre-registered design and why it failed

### Rules

- Absolute: `M_L(QQQ,t) > M_L(BIL,t)`.
- Relative: `M_L(QQQ,t-1) > M_L(SPY,t-1)`.
- Both → TQQQ; absolute only → QQQ; neither → BIL.
- Vol target 50% or 65% on the asset held.
- Weekly or monthly, next-open fills, 1/5/10 bp.

### Results (1 bp, 1-minute marks)

| ID | L | Target | Rebalance | CAGR | Max DD | Sharpe | Pass |
|---|---:|---:|---|---:|---:|---:|---|
| A | 126 | 65% | W | 31.04% | 54.86% | 0.86 | no |
| B | 126 | 65% | M | 27.81% | 63.86% | 0.77 | no |
| C | 126 | 50% | W | 27.20% | 49.18% | 0.83 | no |
| D | 126 | 50% | M | 25.84% | 57.41% | 0.76 | no |
| E | 252 | 65% | W | 20.10% | 58.78% | 0.64 | no |
| F | 252 | 65% | M | 27.61% | 67.85% | 0.76 | no |
| G | 252 | 50% | W | 18.90% | 50.86% | 0.64 | no |
| H | 252 | 50% | M | 25.56% | 58.97% | 0.76 | no |

No point passes. A is the best CAGR, C the best drawdown; neither reaches
36.72%.

### Why it failed

The 126-day absolute signal is slow in both directions:

- **2019 re-entry.** The 126-day absolute signal did not turn positive until
  April 2019. The strategy sat in BIL/QQQ through the January-March rally. The
  Revision 1 primary returned 25.97% that year versus TQQQ's 133.11%.
- **2023 re-entry.** The signal did not turn positive until March 2023, missing
  the January rally. The Revision 1 primary still returned 112.19% that year,
  far below TQQQ's 198.37%.
- **2020 exit.** It exited after a large part of the COVID crash, then the
  50–65% vol target cut exposure exactly when the rebound started. The max
  drawdown was 54.86%.
- **Relative drag.** The QQQ state (relative off, absolute on) occurs about 12%
  of sessions and returns much less than TQQQ. In this sample it is a pure drag.

The lesson is not "use a tighter single lookback." A 42-day signal alone
reaches 38.28% CAGR / 42.89% DD, but its neighbours collapse: 21-day 22.80%,
63-day 21.37%. A single short lookback is a peak, not a plateau. Revision 2
therefore uses an ensemble, not a tighter single window.

## 3. Revision 2: exact rules

### Universe and data

- **QQQ:** signal and 1x middle sleeve.
- **SPY:** relative-momentum signal only. There is no SPY 1-minute history for
  2016-2023; SPY is never held and never marked. Its daily close is lagged one
  session in the relative signal, because the official close is 16:00 and the
  decision bar is 15:59.
- **TQQQ:** 3x Nasdaq sleeve, held only when both absolute gates and the
  relative gate agree.
- **BIL:** cash/defensive sleeve.
- Daily signal closes for QQQ/TQQQ/BIL are the 15:59 panel closes, spliced to
  Yahoo adjusted daily closes before 2016-01-04 so every lookback has warm-up
  from 2015-01-02.

### Absolute momentum (two gates)

For lookback `L`, `M_L(asset,t) = P(asset,t) / P(asset,t-L) - 1`.

- **Short gate (OR):** at least one of
  `M21(QQQ) > M21(BIL)` and `M42(QQQ) > M42(BIL)`.
- **Medium gate (majority):** at least two of
  `M84(QQQ) > M84(BIL)`, `M105(QQQ) > M105(BIL)`,
  `M126(QQQ) > M126(BIL)`.
- **Absolute on = short AND medium.**

The short gate is the fast exit/re-entry leg. The medium majority is the regime
filter: it stops a one- or two-month bounce from re-levering while the
four-to-six-month trend is still down, and it stops a short-term dip from
de-levering while the medium trend is still up. The majority-of-three structure
is deliberate: the medium result is a plateau, not a single-horizon peak.

### Relative momentum

`M126(QQQ, t-1) > M126(SPY, t-1)` for the primary. The grid also tests 252
sessions. SPY is lagged one session for causality.

### State and sizing

| State | Condition | Risky sleeve |
|---|---|---|
| 2 | absolute on and relative on | TQQQ |
| 1 | absolute on, relative off | QQQ |
| 0 | absolute off | BIL |

`w_risky = min(1, target_vol / sigma_20d)`, where `sigma_20d` is the
annualized 20-session realized vol of the asset held. The remainder is BIL.
Primary target is 100%; the grid tests 80%, 90%, 100%. A 100% target means the
vol rule only cuts in extreme volatility; the multi-horizon gate is the crash
control.

### Rebalance

Weekly, last session of the ISO week. The first panel session (2016-01-04)
inherits the target decided at 2015-12-31; the first in-window rebalance is
the first week-end. Decision at the 15:59 close, fill at the next 09:30 open.
2% band. Monthly is the slow-rebalance control.

## 4. Revision 2 results

### 4.1 Headline (primary A: 100% vol target, relative 126, weekly)

| Cost | CAGR | Max DD | Sharpe | Sortino | Vol | Fills | Turnover/yr |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 bp | **40.00%** | **42.89%** | **1.08** | 1.52 | 37.86% | 129 | 68.9× |
| 5 bp | 39.25% | 42.94% | 1.07 | 1.50 | 37.86% | 129 | 66.9× |
| 10 bp | **38.31%** | 43.06% | 1.05 | 1.47 | 37.85% | 129 | 64.5× |

Ending equity at 1 bp: $1,467,956 from $100,000. Total turnover 550×; fills
129 over 8 years (about 16 per year, but large 0↔1 switches). The 10 bp CAGR
still clears 36.72% by 1.59 pp, so the edge is not a 1 bp artifact.

### 4.2 Grid (1 bp) — the plateau

| ID | Target | Relative | Rebalance | CAGR | Max DD | Sharpe | Corr TQQQ |
|---|---:|---:|---|---:|---:|---:|---:|
| **A** | **100%** | **126** | **W** | **40.00%** | **42.89%** | **1.08** | **0.59** |
| B | 90% | 126 | W | 39.33% | 43.68% | 1.07 | 0.59 |
| C | 80% | 126 | W | 38.38% | 43.06% | 1.06 | 0.59 |
| D | 100% | 252 | W | 39.80% | 42.89% | 1.07 | 0.59 |
| E | 90% | 252 | W | 39.06% | 43.68% | 1.07 | 0.59 |
| F | 80% | 252 | W | 37.94% | 43.06% | 1.05 | 0.59 |
| G | 90% | 126 | M | 25.09% | 53.47% | 0.77 | 0.61 |
| H | 100% | 126 | M | 25.19% | 53.47% | 0.77 | 0.61 |

**Plateau:** all six weekly points pass, spanning 37.94–40.00% CAGR and
42.89–43.68% DD. The target dimension is monotonic (80→90→100%: 38.38→39.33→
40.00%) and the relative horizon barely matters (126 vs 252: 40.00 vs 39.80).
This is a genuine weekly plateau, not a single grid point.

**Monthly fails.** G/H return 25.1–25.2% with 53.5% DD. The short gate is
useless at a monthly sampling; the strategy is weekly by construction.

### 4.3 Benchmarks (same window and marks)

| | CAGR | Max DD | Sharpe | Vol |
|---|---:|---:|---:|---:|
| TQQQ (local 1m close-to-close) | 36.15% | 82.29% | 0.80 | 66.55% |
| TQQQ (task bar) | 36.72% | 82.29% | 0.82 | — |
| QQQ (1m) | 18.91% | 37.30% | 0.90 | 22.02% |
| SPY (daily only) | 13.37% | 33.72% | 0.77 | 18.39% |

The local TQQQ CAGR is 0.57 pp below the task's 36.72% because the local
benchmark is close-to-close on the 1-minute panel, not the official daily
total-return series. The drawdown matches exactly. The strategy beats both
numbers at 1 bp and 10 bp.

### 4.4 Yearly returns

| Year | Strategy | TQQQ | QQQ |
|---|---:|---:|---:|
| 2016 | 9.76% | 18.63% | 9.34% |
| 2017 | 120.64% | 118.35% | 32.63% |
| 2018 | **41.32%** | **-19.58%** | -0.12% |
| 2019 | 12.25% | 133.11% | 38.94% |
| 2020 | 109.62% | 109.61% | 48.36% |
| 2021 | 21.07% | 82.97% | 27.39% |
| 2022 | **-15.49%** | **-79.07%** | -32.52% |
| 2023 | 78.14% | 198.37% | 54.81% |

This is the strategy's signature: it wins big in the two crash years (2018,
2022), roughly matches TQQQ in 2017 and 2020, and lags badly in the strong bull
years (2019, 2021, 2023). It is a crash-avoidance overlay, not a bull-market
compounder.

### 4.5 Sub-periods

| Period | Strategy CAGR / DD / Sharpe | TQQQ CAGR / DD / Sharpe |
|---|---|---|
| 2016-2019 | 40.12% / 33.22% / 1.20 | 48.98% / 58.62% / 1.05 |
| 2020-2021 | 59.26% / 42.89% / 1.14 | 93.48% / 72.74% / 1.21 |
| 2022-2023 | 22.79% / 34.20% / 0.89 | -21.72% / 81.10% / 0.05 |

The strategy wins risk-adjusted in all three sub-periods but only wins absolute
CAGR in 2022-2023. The 2020-2021 max drawdown is the COVID peak-to-trough; the
full-period max DD is the same 42.89%.

### 4.6 Exposure and state

| | Average |
|---|---:|
| TQQQ target weight | 55.95% |
| QQQ target weight | 12.18% |
| BIL target weight | 31.87% |
| Risky (QQQ + TQQQ) | 68.13% |
| Invested fraction (includes BIL) | 100.00% |

Session shares: TQQQ 56.9%, QQQ 11.7%, BIL 31.4%; 116 state switches.
Daily correlation to TQQQ is **0.593**; to QQQ **0.589**. The strategy is a
genuinely different return stream, not a closet TQQQ. The correlation is below
the 0.70–0.85 range expected in HYPOTHESIS §11.7, and risky exposure is below
the 75–90% range, because BIL is 31.4% of sessions. The lower correlation is a
positive surprise for diversification; the lower exposure is the cost of the
crash filter.

## 5. Robustness

### 5.1 Neighbour table (1 bp) — the short gate is the weak point

| Variant | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| Short 21 only | 22.80% | 51.18% | 0.77 |
| Short 42 only | 38.28% | 42.89% | 1.07 |
| Short 63 only | 21.37% | 67.89% | 0.67 |
| Short 21/42 AND | 21.29% | 44.62% | 0.75 |
| Short 21/42/63 majority | 34.76% | 42.89% | 1.00 |
| Medium 63/84/105 | 32.78% | 42.89% | 0.94 |
| Medium 105/126/147 | 37.83% | 42.89% | 1.04 |
| Medium 84/126/168 | 34.93% | 42.89% | 0.99 |
| Absolute only (no relative gate) | 48.67% | 42.89% | 1.18 |

The medium ensemble is robust: 105/126/147 gives 37.83% and 63/84/105 gives
32.78%, both with the same 42.89% DD. The short gate is not: 21-only and
63-only both fail, and the 42-day leg is doing the work. The 21/42 OR ensemble
is better than either alone, but it is still a short-horizon selection. This is
the main overfitting risk.

The **relative gate is a drag**: removing it raises CAGR from 40.00% to 48.67%
with the same 42.89% DD and a better Sharpe (1.18). The mandate requires the
relative leg; the strategy keeps it, but the report does not pretend it adds
return. Its economic role is to de-lever to QQQ when Nasdaq leadership fades;
in this sample that role costs 8.67 pp of CAGR and buys no drawdown reduction
because the max DD occurs while the relative gate is still on.

### 5.2 Placebo: circular shifts of the target sequence

200 random circular shifts of A's per-session target sequence, preserving the
exact state sequence, exposure, vol targeting and turnover but destroying
alignment with returns. 1 bp, 1-minute marks.

| | CAGR | Max DD |
|---|---:|---:|
| Strategy A | 40.00% | 42.89% |
| Placebo median | 21.01% | 72.74% |
| Placebo 5th percentile | 2.83% | 60.08% |
| Placebo 95th percentile | 46.15% | 84.33% |
| Share beating A's CAGR | **10.0%** | — |

The strategy is at the 90th percentile of the placebo CAGR distribution, not
the 95th. The pre-registered falsifier was "more than 5% of shifts beat A" —
10% does, so **this falsifier fails**. The drawdown result is much stronger:
42.89% versus a 72.74% placebo median and an 84.33% 95th percentile. The risk
control is real; the CAGR timing edge is not statistically strong.

### 5.3 Cut tests

| Cut | Bars checked | Max abs weight diff | Pass |
|---|---:|---:|---|
| 2020-03-12 11:07 | 409,460 | 0.0 | yes |
| 2022-09-13 10:41 | 654,959 | 0.0 | yes |

The weights before each cut are bit-identical when the panel is truncated.
No look-ahead in the weight construction.

### 5.4 Year concentration

Replace one year's strategy return with TQQQ's return and recompute CAGR:

| Year replaced with TQQQ | Resulting CAGR |
|---|---:|
| 2016 | 41.37% |
| 2017 | 39.81% |
| **2018** | **30.45%** |
| 2019 | 53.42% |
| 2020 | 40.00% |
| 2021 | 47.43% |
| **2022** | **17.55%** |
| 2023 | 49.34% |

The pass depends on 2018 and 2022. If the strategy had TQQQ's 2018 return, CAGR
would be 30.45%; with TQQQ's 2022 return, 17.55%. This is exactly the
crash-avoidance mechanism, but it is also a two-year bet. The pre-registered
falsifier "one year accounts for more than half of the excess" is effectively
triggered by both 2018 and 2022.

### 5.5 Falsifier checklist

| Falsifier | Result |
|---|---|
| CAGR > 36.72% at 1 bp | **pass** (40.00%) |
| Max DD < 60% | **pass** (42.89%) |
| At least three weekly grid points pass | **pass** (6/6) |
| Placebo ≤ 5% beat | **fail** (10%) |
| Cut test clean | **pass** (0.0) |
| 10 bp CAGR > 36.72% | **pass** (38.31%) |
| TQQQ target weight < 90% | **pass** (55.95%) |
| Short 21-only and 63-only both work | **fail** (22.80%, 21.37%) |
| Replacing any year with TQQQ still passes | **fail** (2018, 2022) |

**Overall robustness: fragile.** The headline passes; three robustness checks
do not.

## 6. Why it beats TQQQ

1. **Crash avoidance is worth more than bull-market participation.** In 2018
   the strategy returned +41.32% while TQQQ lost 19.58%; in 2022 it lost 15.49%
   while TQQQ lost 79.07%. Avoiding a 79% loss means the 2023 recovery starts
   from a much higher base, even though the strategy returns 78.14% versus
   TQQQ's 198.37% in 2023.
2. **The 2020 drawdown is short, not a long bear.** The max DD is 42.89% from
   2020-02-19 14:44 to 2020-02-28 10:04 — nine days. The strategy then
   re-enters and finishes 2020 at +109.62%, essentially matching TQQQ's
   +109.61% while taking a much smaller peak-to-trough loss.
3. **Multi-horizon agreement reduces whipsaw.** The medium majority keeps the
   strategy out of false one-month re-leverings, while the short OR gets it
   back in faster than a 126/252-day signal. Revision 1's single 126-day signal
   was too slow in 2019 and 2023; the ensemble fixes part of that.
4. **The high vol target keeps the bull-market compounding.** At a 100%
   target, the book is usually fully in TQQQ or QQQ in calm uptrends; the
   momentum gate, not a low vol target, does the risk control. The grid shows
   that lowering the target to 80% costs 1.62 pp of CAGR with almost no DD
   improvement.
5. **It is not a closet TQQQ.** Daily correlation is 0.593, average TQQQ weight
   is 55.95%, and 31.4% of sessions are in BIL. The return stream is different
   enough to be useful as a satellite.

## 7. Where it fails

- **Bull-market lag.** 2019 +12.25% vs +133.11%; 2021 +21.07% vs +82.97%;
  2023 +78.14% vs +198.37%. The medium gate is slow to confirm after a
  drawdown, so the strategy misses the first leg of V-shaped recoveries. This
  is the price of crash avoidance.
- **2019 is the worst case.** The medium gate did not confirm until April, so
  the strategy missed January-March. A faster medium confirmation would help
  2019 but would increase whipsaw in 2016/2018.
- **The short gate is 42-dependent.** 21-only and 63-only fail. The 21/42 OR is
  an ensemble, but the 42-day leg is essential. This is the main reason to
  call the result exploratory.
- **The relative gate is a drag.** Absolute-only returns 48.67% with the same
  DD. The mandate's relative leg costs 8.67 pp of CAGR in this sample. The
  cross-asset rotation is not the source of the edge.
- **Monthly rebalancing fails.** 25.1% CAGR / 53.5% DD. The strategy is
  weekly-only; a weekly execution assumption is material.
- **Placebo p ≈ 0.10.** 10% of random circular shifts beat the CAGR. The
  drawdown is robust; the CAGR timing is not.
- **Two-year concentration.** 2018 and 2022 carry the result. A future
  bull-market decade with shallow crashes could underperform TQQQ badly.
- **Turnover.** 68.9× per year, 129 fills. At 10 bp the CAGR is still 38.31%,
  but a less liquid implementation or higher borrow/execution costs would
  erode the margin.

## 8. Relationship to existing research

| Existing strategy | Difference |
|---|---|
| Old 165-day QQQ SMA + 4% stop | Not used. This is a total-return multi-horizon momentum ensemble, not a price SMA; no 4% intraday stop. |
| `dual-speed-regime` | Intraday 60-minute EMA, flat every night. This is daily, holds overnight, and uses cross-asset relative momentum. |
| `risk-parity-hrp` | HRP/ERC risk budgeting with a vol-state tilt. This uses discrete momentum states and a single vol target, not a risk-parity model. |
| `dynamic-leverage-throttle` / `vol-kelly-overlay` | Vol-targeted leverage without a cross-asset relative switch. This requires QQQ to lead SPY as well as beat BIL for the TQQQ sleeve. |
| `ml-classifier` | Unsupervised regime clustering. This has explicit, interpretable momentum votes and no fitted model. |
| `ratio-pairs` | TQQQ/QQQ ratio froth. This compares QQQ to SPY and QQQ to BIL; no TQQQ/QQQ ratio. |
| `winner-ensemble-blend` | Inverse-vol blend of sleeves. This is a state switch, not a blend. |
| `donchian-breakout` | Price breakout. This uses total-return momentum over 21/42/84/105/126 sessions. |
| `stop-reentry-recovery` | Buys TQQQ after an intraday downside overshoot for three days. This is a weekly multi-horizon state machine with no intraday stop. |

The closest structural cousin is the old 165-day trend base, but the signal,
horizon set, relative gate and rebalance are different. The daily correlation
to TQQQ is 0.593, so it is not the old base with a new name.

## 9. Honest verdict

**Headline pass: yes.** 40.00% CAGR, 42.89% max DD, 1.08 Sharpe at 1 bp;
38.31% CAGR at 10 bp. It beats the 36.72% bar with a 39.4 pp lower drawdown and
a 0.26 higher Sharpe. On the stated pass criterion, it wins.

**Validated strategy: no.** It is a Revision 2 designed after Revision 1
failed on the same window. The placebo p-value is 0.10, the short gate is
42-dependent, and the result is concentrated in 2018 and 2022. A true holdout
was not run (and must not be run by this agent). The correct label is
**exploratory headline pass, fragile**.

**What I would do next, in order:**

1. Freeze this exact `strategy.py` and run the untouched 2024-2026 holdout
   once. Do not tune after seeing it.
2. If the holdout confirms the crash-avoidance years, paper-trade for 6–12
   months to measure the weekly execution and turnover.
3. If a cleaner pass is needed, test the absolute-only version (48.67% CAGR,
   42.89% DD, 1.18 Sharpe) as a separate hypothesis. It violates the
   relative-momentum mandate but is stronger in this sample.
4. Do not lower the vol target or switch to monthly: both reduce CAGR without
   improving the drawdown.

The strategy is a legitimate crash-avoidance overlay with a real 2018/2022
mechanism. It is not a broad, all-weather alpha, and the report should not be
read as one.

## 10. Reproduction

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
$env:BT_THREADS = "1"
python research\new\cross-asset-momentum\strategy.py
```

`strategy.py` writes `result.json`; every number above is read from that file.
The holdout is never loaded: the panel ends 2023-12-29 and the Yahoo daily
series is sliced at that date.
