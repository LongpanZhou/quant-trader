# Autocorrelation-regime TQQQ — development report

**Family:** time-varying short-horizon serial dependence. The primary signal is
a rolling lag-1 autocorrelation of QQQ daily returns; the position switches
between TQQQ continuation, TQQQ reversal and BIL.

**Window:** 2016-01-04 → 2023-12-29, development only. The 2024-2026 holdout
was never loaded or inspected. Pre-2016 daily closes (2015) are used only to
warm up the autocorrelation estimate.

**Verdict: the primary clears the numerical development bar at 1/5/10 bp, but
the family claim is not supported. The edge is the negative-autocorrelation
reversal leg, which is a short-reversal variant; the positive-autocorrelation
continuation leg is weak; the parameter plateau is a narrow ridge at the
weakest reversal threshold; and daily-return correlation with
`family-short-reversal` is 0.765. Archive as a dev-only conditional pass, not a
new family.**

---

## 1. Headline

Execution: `research/bt.py`, 1-minute marks, next-open fills, 2% band,
long-only, weights ≥ 0, row sum ≤ 1. Flat is BIL. Headline 1 bp.

| | CAGR | Max DD | Sharpe | Sortino | Vol | TQQQ exp | Fills | Turnover | Ending equity |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Primary, 0 bp (gross)** | 51.23% | 67.59% | 1.02 | 1.43 | 57.0% | 62.2% | 629 | 4,540x | $2.718M |
| **Primary, 1 bp** | **50.04%** | **67.62%** | **1.00** | **1.41** | **57.0%** | **62.2%** | **629** | **4,329x** | **$2.552M** |
| Primary, 5 bp | 45.39% | 67.72% | 0.95 | 1.33 | 57.0% | 62.2% | 629 | 3,587x | $1.985M |
| Primary, 10 bp | 39.77% | 67.85% | 0.88 | 1.23 | 57.0% | 62.2% | 629 | 2,847x | $1.449M |
| TQQQ dev bar | 36.72% | 82.29% | 0.82 | — | — | 100% | — | — | — |
| TQQQ buy & hold (same panel) | 35.98% | 81.68% | 0.80 | — | 67.7% | 100% | — | — | $1.163M |

- At 1 bp the primary beats the CAGR bar by **13.32 pp**, cuts max drawdown by
  **14.67 pp**, and adds **0.18 Sharpe**. At 10 bp it still beats the CAGR bar
  by **3.05 pp** with **14.44 pp** less drawdown and **0.06** more Sharpe. The
  pass is not a 1 bp artifact.
- The max drawdown is still **67.62%** (2020-02-19 → 2020-03-23, recovered
  2020-06-23). No cell in the grid combines a CAGR above 36.72% with a
  drawdown below 60%; the "ideally below 60%" target is not met.
- The strategy is not a low-activity curiosity: **629 fills, 157 entries,
  157 exits, 8.0-session average hold** (median 6, max 35), **62.2% TQQQ
  exposure**, 4,329x turnover at 1 bp. It is well above the 100-fill floor.
- The 1-minute result is lower than a daily open-to-open approximation
  (56.8% gross). Part of the gap is the fill convention: the fill is at the
  next open, so the overnight gap on a switch day belongs to the old position,
  while the approximation attributed the whole open-to-open interval to the
  new position. The 1-minute simulator is the reported path.

---

## 2. Rules and decision clock

All inputs are known at the **15:59 ET close of session d**; the target is
written on that close and fills at the **09:30 ET open of d+1**.

```
qret[d] = QQQ close-to-close return
rho[d]  = lag-1 autocorrelation of qret over the last L sessions
cont[d] = rho[d] >= theta_cont
rev[d]  = rho[d] <= -theta_rev and qret[d] < 0
held[d] = rev[d] or rev[d-1] or ... or rev[d-hold+1]

target[d+1] = TQQQ 1.0 if cont[d] or held[d], else BIL 1.0
```

The `held` term is a rolling hold: a reversal signal keeps the sleeve in TQQQ
for `hold` sessions and a new signal extends it. There is no stop, no trend
gate, no volatility target, no drawdown state, no calendar rule, no intraday
feature and no fitted model.

**Primary:** L=120, lag=1, theta_cont=0.03, theta_rev=0.05, hold=3, daily
clock. It is the centre of the pre-registered grid (middle window, middle
positive threshold, middle hold). The 12-cell grid and the falsifiers are in
`HYPOTHESIS.md`.

---

## 3. What the autocorrelation actually looks like

QQQ daily returns are **negatively autocorrelated most of the time** on this
window. The positive state that the continuation hypothesis needs is the rare
state.

| L | median rho | P(rho>0) | P(rho>0.03) | P(rho<-0.05) | P(rho<-0.10) | P(rho<-0.15) |
|---:|---:|---:|---:|---:|---:|---:|
| 60 | -0.068 | 30.9% | 21.6% | 54.1% | 38.1% | 21.3% |
| 120 | -0.060 | 25.7% | 14.1% | 56.5% | 26.7% | 11.7% |
| 250 | -0.058 | 18.2% | 11.2% | 57.4% | 23.4% | 13.1% |

At L=120 the continuation state (rho ≥ 0.03) is on **14.1%** of sessions, the
reversal signal fires on **23.7%** of sessions, and the union holds TQQQ on
**62.2%** of sessions. QQQ's daily mean return over the window is +0.078% with
22.75% annualised volatility. The first empirical warning is therefore
structural: the positive-AC state is not common enough to carry a strategy on
its own, and the negative-AC state is the default.

---

## 4. Leg attribution: the reversal leg is the strategy

All four rows use the same 1 bp execution and the same 2016-2023 panel.

| Leg | CAGR | Max DD | Sharpe | TQQQ exp | Fills |
|---|---:|---:|---:|---:|---:|
| Continuation only (rho ≥ +0.03) | 7.42% | 46.03% | 0.40 | 14.1% | 189 |
| Reversal only (rho ≤ -0.05, down day, 3-session hold) | 42.31% | 68.03% | 0.96 | 48.3% | 457 |
| **Union (primary)** | **50.04%** | **67.62%** | **1.00** | **62.2%** | **629** |
| Reversal with no AC gate (every down day, 3-session hold) | 38.88% | 71.73% | 0.84 | 83.0% | 611 |

- **Continuation-only is economically negligible.** It is positive (7.42%
  CAGR) but at 14.1% exposure and 0.40 Sharpe. The "positive AC → continuation"
  half of the hypothesis is not supported as a standalone edge. Holding TQQQ
  in the positive-AC state without the up-day condition is essentially a slow
  long-beta sleeve.
- **Reversal-only already clears the bar by itself** (42.31% CAGR, 68.03% DD,
  0.96 Sharpe). The autocorrelation gate is not what makes the strategy pass.
- **The gate improves the reversal on a per-exposure basis**: reversal-only
  earns 42.31% on 48.3% average exposure (a 0.88 CAGR/exposure ratio), while
  the no-gate version earns 38.88% on 83.0% exposure (0.47). The gate cuts
  exposure and avoids the worst bear-market clusters. But the absolute gain
  over no-gate is only +3.4 pp CAGR; the union's extra +7.7 pp comes from
  adding the continuation leg's 14 pp exposure.
- The gate's real contribution is **regime protection in 2022-2023**: no-gate
  reversal is **-17.39%** in 2022-2023, the gated primary is **+27.15%**.
  In 2016-2019 the ordering reverses: no-gate **+46.11%**, gated **+30.58%**.
  The gate trades early-period CAGR for bear-market protection. That is a
  useful risk effect, but it is not the hypothesised continuation mechanism.

The honest reading: the strategy is a **short-reversal engine with an
autocorrelation regime overlay**, not an autocorrelation-continuation engine.

---

## 5. Parameter plateau

The 12 pre-registered cells plus the L=60/L=250 window checks, all at 1 bp.
`pass` means CAGR > 36.72% and max DD < 82.29%.

| L | theta_cont | theta_rev | hold | CAGR | Max DD | Sharpe | Fills | TQQQ exp | pass |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| 120 | 0.00 | 0.05 | 3 | 40.73% | 71.58% | 0.87 | 591 | 73.6% | yes |
| 120 | 0.00 | 0.10 | 3 | 23.11% | 73.81% | 0.67 | 395 | 47.7% | no |
| 120 | 0.00 | 0.15 | 3 | 26.65% | 63.42% | 0.74 | 295 | 35.5% | no |
| 120 | **0.03** | **0.05** | **3** | **50.04%** | **67.62%** | **1.00** | **629** | **62.2%** | **yes** |
| 120 | 0.03 | 0.10 | 3 | 30.61% | 67.62% | 0.81 | 409 | 36.1% | no |
| 120 | 0.03 | 0.15 | 3 | 35.94% | 48.29% | 0.94 | 309 | 23.9% | no (CAGR) |
| 120 | 0.05 | 0.05 | 3 | 37.11% | 67.62% | 0.86 | 593 | 55.4% | yes |
| 120 | 0.05 | 0.10 | 3 | 19.24% | 67.62% | 0.63 | 369 | 29.3% | no |
| 120 | 0.05 | 0.15 | 3 | 24.11% | 47.48% | 0.76 | 269 | 17.1% | no |
| 120 | 0.03 | 0.05 | 1 | 44.75% | 65.96% | 1.03 | 1,409 | 37.7% | yes |
| 120 | 0.03 | 0.05 | 2 | 48.45% | 67.35% | 1.01 | 925 | 53.0% | yes |
| 120 | 0.03 | 0.05 | 5 | 46.11% | 72.72% | 0.94 | 349 | 71.2% | yes |
| 60 | 0.03 | 0.05 | 3 | 29.19% | 69.51% | 0.74 | 599 | 68.2% | no |
| 250 | 0.03 | 0.05 | 3 | 35.95% | 68.02% | 0.85 | 457 | 59.2% | no (CAGR) |

- **6 of the 12 pre-registered cells pass** (6 of 14 including the L=60/L=250
  window checks). Among the 9 core cells (L=120, hold=3), only **3** pass, and
  **all three are at theta_rev=0.05**. The 30-cell full grid in
  `robustness.json` has 7 passes out of 30, again all at theta_rev=0.05.
- The passing region is a **ridge**, not a plateau: it runs along the weakest
  reversal threshold and through hold = 1/2/3/5. Raising the reversal
  confidence threshold to 0.10 or 0.15 — the natural way to stop the strategy
  from flipping every day — collapses CAGR to 19-36%.
- The L=60 and L=250 checks both fail the CAGR bar (29.19% and 35.95%). The
  pass is specific to L=120.
- **Falsifier 4 fails** (at least 8 of 12 cells and not all at one parameter
  value). This is not a parameter plateau in the sense the programme requires;
  it is a corner of the grid that happens to work.

---

## 6. Subperiods and yearly

Each subperiod is a fresh $100k run, not a chain; the ending equities are not
additive.

| Subperiod | CAGR | Max DD | Sharpe | Sortino | Fills | TQQQ exp |
|---|---:|---:|---:|---:|---:|---:|
| 2016-2019 | 30.58% | 50.72% | 0.84 | 1.20 | 311 | 61.0% |
| 2020-2021 | 130.97% | 67.62% | 1.46 | 2.01 | 167 | 75.9% |
| 2022-2023 | 27.15% | 61.05% | 0.71 | 1.02 | 153 | 50.9% |

The sum of subperiod log returns is 1.064 + 1.675 + 0.479 = 3.219; the
2020-2021 share is **52.0%**. That is below the 70% single-subperiod
falsifier, but it is still the majority of the edge. Two of the three
subperiods (2016-2019 and 2022-2023) are below the full-window CAGR bar; the
strategy is positive in all three, with a much better 2022-2023 than TQQQ.

| Year | Strategy | TQQQ | Note |
|---:|---:|---:|---|
| 2016 | -4.52% | +9.34% | strategy underperforms |
| 2017 | +45.12% | +32.63% | |
| 2018 | -8.60% | -0.12% | strategy underperforms |
| 2019 | +128.96% | +38.94% | reversal harvest |
| 2020 | +204.51% | +48.36% | COVID crash and recovery |
| 2021 | +79.41% | +27.39% | |
| 2022 | -17.96% | -32.52% | better than TQQQ, still a loss |
| 2023 | +96.40% | +54.81% | |

The strategy is a **crash/recovery harvester**, not a smooth compounder. It
loses less than TQQQ in 2022 but loses in 2016 and 2018 when TQQQ is roughly
flat. The maximum drawdown is the COVID crash: peak 2020-02-19 14:44, trough
2020-03-23 11:45, 67.62%, recovered 2020-06-23 10:40. The reversal leg was
buying down days all the way into that hole; that is the family's known
falling-knife risk and it is not fixed by the AC gate.

---

## 7. Placebo / circular shift

The test preserves the holding pattern or the AC marginal distribution and
destroys the alignment with returns. 300 draws each, 1 bp.

| Null | mean CAGR | median | p5 | p95 | true | percentile | one-sided p |
|---|---:|---:|---:|---:|---:|---:|---:|
| Circular-shift target | 21.15% | 19.90% | 4.17% | 42.87% | 50.04% | 99.3% | **0.010** |
| Circular-shift AC | 26.48% | 25.41% | 8.47% | 45.42% | 50.04% | 98.0% | **0.023** |
| Random gate (shuffled AC values) | 31.09% | 30.88% | 11.47% | 52.22% | 50.04% | 94.3% | **0.060** |

- The specific timing is significant against both circular-shift nulls
  (p = 0.010 and 0.023). The true CAGR is above the 95th percentile of both
  distributions.
- The **random-gate** null is borderline (p = 0.060): a random AC series with
  the same marginal distribution gets within the true result often enough that
  the "level" of autocorrelation alone is not a clean explanation. The serial
  ordering / persistence of the gate matters more than its cross-sectional
  level. Do not overstate the placebo as proof of an AC edge.
- The placebo mean is 21-31% CAGR, well below the true 50.04%, so the exposure
  pattern alone is not the explanation. But the random-gate result is the
  weakest of the three tests and is reported as such.

---

## 8. Correlation with the current family winners

Daily-return Pearson correlation over 2016-2023 (2,010 overlapping days). The
archived curves also contain 2024-2026 values; they were truncated to
2023-12-29 before any return was computed, and no 2024+ value was inspected.

| Winner | Correlation |
|---|---:|
| ratio-froth | 0.473 |
| vol-scaled-crash-stop | 0.624 |
| relative-value-tqqq | 0.733 |
| fomc-opex-window | 0.568 |
| family-session-timing | 0.616 |
| **family-short-reversal** | **0.765** |
| family-rebalance-flow | 0.712 |
| family-intraday-microstructure-day | 0.481 |
| family-ml-microstructure | 0.706 |
| **range** | **0.473 – 0.765** (mean 0.631) |

- The highest correlation is with `family-short-reversal` at **0.765**. The
  family falsifier required < 0.70; it fails. The strategy is largely the same
  risk as the existing short-reversal family, with an autocorrelation overlay.
- Correlation with TQQQ daily returns is **0.846**, beta **2.12**. The
  62.2% average exposure is concentrated in high-volatility days, so the
  realised beta is above the exposure fraction. This is a TQQQ beta product,
  not market-neutral alpha.
- The low correlations (ratio-froth 0.473, intraday-microstructure 0.481) show
  that it is not identical to every winner, but the one family it most needs
  to be distinct from is the one it is closest to.

---

## 9. Weekly decision clock

The required weekly exploration uses a Friday 15:59 decision, next Monday open
fill and a one-week hold. Two versions: autocorrelation of weekly returns
(Lw = 20/26/39/52) and the daily autocorrelation sampled at Friday close,
crossed with theta_cont ∈ {0, 0.03, 0.05} and theta_rev ∈ {0.05, 0.10, 0.15}.

- **72 cells, 1 pass.** The best is weekly AC, Lw=20, theta_cont=0,
  theta_rev=0.10: **37.26% CAGR, 67.48% DD, 0.893 Sharpe, 275 fills, 43.3%
  exposure**. That is a single cell barely above the CAGR bar, with a worse
  Sharpe than the daily primary.
- The weekly clock is not a robust alternative. The daily clock is the only
  one that produces a coherent ridge. This is a negative result for the
  weekly part of the mandate.

---

## 10. Costs and BIL vs cash

| Cost | BIL flat (primary) CAGR | Cash flat CAGR | BIL fills | Cash fills |
|---:|---:|---:|---:|---:|
| 0 bp | 51.23% | 50.29% | 629 | 314 |
| 1 bp | 50.04% | 49.70% | 629 | 314 |
| 5 bp | 45.39% | 47.36% | 629 | 314 |
| 10 bp | 39.77% | 44.49% | 629 | 314 |

- BIL is better at 0-1 bp because the idle sleeve earns the T-bill return.
  Cash is better at 5-10 bp because it halves the fill count: the BIL leg pays
  two extra fills on every switch.
- The primary keeps BIL because the hypothesis specifies a BIL neutral state
  and because it still clears the bar at 10 bp (39.77% vs 36.72%). A
  cost-sensitive implementation would use cash and would clear more
  comfortably at 10 bp (44.49%).
- Turnover is 4,329x initial equity at 1 bp; the 1 bp cost drag is 1.19 pp of
  CAGR, the 10 bp drag is 11.46 pp. The strategy is not cost-fragile at 1-5 bp,
  but it is not cheap.

---

## 11. Kill criteria

| # | Falsifier | Result | Status |
|---:|---|---|---|
| 1 | Continuation leg has positive standalone CAGR/Sharpe | 7.42% CAGR, 0.40 Sharpe, 14.1% exp | passes only in the weak sense; economically negligible |
| 2 | AC gate improves reversal per unit exposure | 0.88 vs 0.47 CAGR/exposure | passes |
| 3 | Bar at 1/5/10 bp | 50.04 / 45.39 / 39.77% CAGR; 67.6-67.9% DD | **passes** |
| 4 | ≥ 8/12 plateau cells, not all at one parameter value | 6/12 (6/14 incl. checks); 3/9 core; all at theta_rev=0.05 | **fails** |
| 5 | Placebo p < 0.05 | target 0.010; AC 0.023; random gate 0.060 | passes two, borderline third |
| 6 | Correlation with family-short-reversal < 0.70 | 0.765 | **fails** |
| 7 | ≥ 2/3 subperiods positive; no subperiod > 70% of log return | all three positive; 2020-21 = 52.0% | passes |

Two hard falsifiers fail (#4 plateau, #6 family distinctness). The numerical
bar pass is real but does not establish a new family.

---

## 12. Verdict and recommendation

**What passes:** the primary is a genuine above-TQQQ development result at
1/5/10 bp, with lower drawdown than TQQQ at every cost level, 629 fills and a
positive placebo result. It is not a dead or too-slow signal.

**What fails:** the mechanism is not the one in the hypothesis. The
positive-autocorrelation continuation leg is weak; the negative-autocorrelation
reversal leg is the engine and is a short-reversal variant. The plateau is a
ridge at the weakest reversal threshold; raising the confidence threshold
collapses the CAGR. The edge is concentrated in 2020-2021 (52% of log return),
the drawdown is still 67.6%, and correlation with `family-short-reversal` is
0.765.

**Recommendation:** archive this as a **dev-only conditional pass, not a new
family**. Do not promote it to the website or the verified-family set on the
strength of this result. If the lead wants a one-shot holdout, run it as a
short-reversal variant with an autocorrelation overlay, with the explicit
expectation that it is a variant of an existing family, not a new one.

A more AC-centric alternative exists but does not clear the bar:
theta_rev=0.15, L=120, theta_cont=0.03, hold=3 gives **35.95% CAGR / 48.29%
DD / 0.94 Sharpe** at 1 bp (35.95% is 0.77 pp below the CAGR bar). It is the
honest "risk-adjusted near-pass" if the priority is a lower drawdown and a
stronger regime gate rather than the headline CAGR. It is reported in the
plateau, not promoted as the primary.

**What would change the verdict:** a continuation leg with standalone CAGR
above ~15% and correlation with short-reversal below 0.70; or a holdout that
confirms the 2022-2023 protection without giving back the 2020-2021 edge. The
current evidence does not support either.

---

## 13. Limitations

- **Dev-only.** No 2024-2026 holdout. All numbers are in-sample on the
  development window; the grid was informed by dev diagnostics (disclosed in
  `HYPOTHESIS.md` §6). The placebo and the plateau are the only guards against
  selection.
- **2020-2021 dominance.** 52% of the log return comes from two years. The
  full-window CAGR is not a statement about a typical year.
- **Drawdown.** 67.6% is below the 82.29% bar but far above the "ideally below
  60%" target. The COVID episode is a falling-knife event: the reversal leg
  bought down days into the crash.
- **Noisy AC estimate.** The standard error of a 120-day autocorrelation is
  roughly 1/sqrt(120) ≈ 0.09. The primary threshold 0.05 is inside one
  standard error of zero; the theta_rev=0.10/0.15 collapse shows how little
  signal is left when the threshold is raised. The strategy is exploiting a
  weak, slow-moving regime, not a strong one.
- **Short-reversal overlap.** 0.765 correlation and the reversal-only leg's
  42.31% CAGR mean the result is largely the existing short-reversal family.
- **BIL fills.** The BIL neutral state doubles the fill count versus cash. At
  10 bp, cash is the better implementation (44.49% vs 39.77%).
- **1-minute data start.** The 1-minute archive starts 2016-01-04; the AC
  warmup uses 2015 daily closes from the local Yahoo file. The boundary return
  differs from the official daily close by about 7 bp (15:59 vs 16:00 mark),
  which is immaterial for a 120-day autocorrelation.
- **Archived curves.** The winner-correlation block reads the archived full
  curves and truncates at 2023-12-29 before computing anything. The 2024-2026
  values are not used or inspected. The dev slices reproduce the published dev
  CAGRs to within about 0.2 pp.
- **Multiple testing.** The primary is the best cell of the dev scan. The
  plateau and placebo reduce, but do not eliminate, the selection risk. A
  holdout is the only clean test; this study did not run one.
