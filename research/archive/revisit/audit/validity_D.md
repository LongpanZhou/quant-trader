# Validity audit — batch D: five rebuilds + the original Ratio froth

**Scope:** `time-of-day`, `vol-kelly-overlay`, `vol-scaled-crash-stop`,
`volume-orderflow`, `winner-ensemble-blend` (rebuilds), plus the original
`research/agents2/ratio-pairs/` — displayed as **“Ratio froth”**.

**Method:** read each `report.md`, `HYPOTHESIS.md`, `SPEC.md`, `PROVENANCE.md`,
`hypothesis.md`, `spec.md`, `provenance.md` and `strategy.py`; used
`result.json` only as context, never as proof. No backtest was run. The many
“backtests paused / no result yet” status lines are stale and were ignored; the
hypothesis and rule were judged as written. Where a `result.json` exists, its
numbers are quoted to show what the frozen test actually produced.

**Evidence standard used below.** “Supports” means the cited source's own
title/abstract claim is the same direction, sign, horizon, universe and sizing
as the rule. “Component only” means the source supports one input (e.g.
volatility clustering) but not the specific entry/exit rule. “Different effect”
means the source is about a different phenomenon, even if it sounds related.

---

## Summary

| Strategy | Verdict | Claimed mechanism | Key evidence problem | Standalone / overlay |
|---|---|---|---|---|
| `time-of-day` | **overlay-only** | A sold last-30m close reverses in the overnight+first-30m block; hold TQQQ only then, vol-scaled | F1 t=1.35; V1 (conditioning only) 25.4% vs V0 (every night) 35.0%; the unconditional overnight premium is the driver; the sign is explicitly contested | Filter on overnight beta; ~30% of nights, 2.3% of intraday bars |
| `vol-kelly-overlay` | **unsupported** | Post-vol-spike reflation: 1–3 session TQQQ rebound after a 1-minute RV spike + 10-day −5% + first up-close | 11 events (own minimum 15); mean event 0.015%, bootstrap p=0.49; 2020–21 −4.3%; the exact event has no external source | Standalone event sleeve; effectively cash |
| `vol-scaled-crash-stop` | **overlay-only** | Always-long TQQQ, inverse-vol size, a 0.7-ATR one-sided barrier that exits to BIL for the session and night | Correlation 0.755 > 0.60; 72% of minutes in TQQQ; event mean −0.27% (p=0.073), median positive; 4% cap inherited from the old stop | Risk overlay on TQQQ beta |
| `volume-orderflow` | **unsupported** | A heavy-volume intraday decline that closes in the upper half of its range = absorbed supply; buy TQQQ for 5 sessions | 3 events in 2,012 sessions; the cited literature is cross-sectional/monthly; the CLV filter is untested; below its own ~40-event gate | Standalone event sleeve; effectively empty |
| `winner-ensemble-blend` | **unsupported** | Inverse-vol blend of a calm QQQ carry stream and a panic TQQQ reversal stream | Stream A 1.68%, Stream B −6.19%, blend 0.30%; placebo p=0.79; event p=0.37; fails 5 bp | Standalone two-stream blend; allocation adds nothing |
| `ratio-pairs` (“Ratio froth”) | **overlay-only** | High TQQQ/QQQ ratio extension = low-vol melt-up / crash risk; hold QQQ instead of TQQQ on those sessions | Still uses the old 165-day QQQ gate and 4% armed stop; overlay alone adds 1.35 pp but DD 53.3%; 69.5% headline is 2017–2026; threshold/sign post-hoc; 584 days are ~67 clustered episodes | Overlay on the old base; not a standalone rebuild |

---

## 1. `time-of-day` — verdict: `overlay-only`

### 1.1 Claimed mechanism and return driver

The overnight + first-30-minute block (15:59 → 10:01) is treated as the
settlement window for the prior session's closing imbalance. The last 30
minutes are said to be sold for price-pressure/liquidity reasons, and that
selling is reversed when liquidity returns next morning. The rule therefore
holds TQQQ only after a **negative** QQQ last-30-minute return, with a
magnitude threshold and a self-referential block-vol gate, and sizes inversely
to the block's own realised vol.

The stated return driver is *when* the overnight block is held, not the
unconditional overnight drift. That is the claim under test.

### 1.2 Cited evidence vs the specific rule

| Source | What the source actually supports | Mismatch with the rule |
|---|---|---|
| Berkman, Koch, Tuttle & Zhang (2012), *Paying Attention: Overnight Returns and the Hidden Cost of Buying at the Open* | Positive overnight returns followed by intraday reversal; the opening price is temporarily inflated by attention-driven buying at the open. Cross-sectional US stocks. | The paper does **not** say a negative last-30-minute return predicts a *larger* overnight return. It supports the unconditional overnight premium and the open being expensive, not the close→overnight sign. Universe is stocks, not a 3× index ETF; no sizing rule. |
| Heston, Korajczyk & Sadka (2010), *Intraday Patterns in the Cross-Section of Stock Returns* | Return continuation at half-hour intervals that are exact multiples of a trading day; intraday periodicity is persistent. Cross-sectional. | Supports “clock windows are repeatable”, not the direction from the last 30 minutes to the overnight. No sizing. |
| Lou, Polk & Skouras (2019), *A Tug of War: Overnight versus Intraday Expected Returns* | Overnight and intraday returns are driven by separate clienteles; institutional trading clusters at the close, retail at the open. | Supports the close→open mechanism and the 15:59 entry, but not the conditional sign. The paper does not say a sold close predicts a stronger overnight. |
| Cliff, Cooper & Gulen (2008), *Return Differences between Trading and Non-Trading Hours* | The unconditional overnight premium exists. | This is the benchmark V0, not the conditioning. It supports the old residue, not the new rule. |
| Gao, Han, Li & Zhou (2018), *Market Intraday Momentum* | The first half-hour predicts the last half-hour; intraday momentum is continuation. | This is the **opposite** sign at the daily horizon: it says the close continues the morning, not that a sold close reverses overnight. The report acknowledges this and tests V4; V4 earns 1.0% CAGR on dev, so the momentum branch is also dead. |

**Assessment.** The citations support three components — the overnight premium,
the specialness of the open/close, and the repeatability of clock blocks — but
none of them supports the specific “sold close → higher next overnight” rule.
The rule is an original synthesis, not a replication. The report is honest
about this (“the closing-pressure direction is the part I am least sure
about”), which is good scientific practice, but honesty about a weak
foundation does not make the foundation stronger. The cross-sectional stock
evidence is extrapolated to a single 3× index ETF without a bridging test.

### 1.3 Falsifiable and pre-registered?

**Yes, on paper, and better than most of the batch.** `HYPOTHESIS.md` was
written before the code, states H1/H2/H0, lists six pre-registered variants
(V0–V5), and gives explicit falsifiers F1–F7 with numeric thresholds. The
neighbourhood and freeze protocol are declared. `strategy.py::decide()` maps
F1–F7 to a status mechanically rather than typing the status by hand.

Two qualifications matter:

- **F2 is not the hypothesis.** H1 is about return *per night* and Sharpe;
  F2 demands that V1 (conditioning only, size 1) beat V0 (every night, size 1)
  on **CAGR**. A conditional strategy can have a higher per-night mean and
  Sharpe but a lower CAGR because it is invested less often. F2 therefore
  tests exposure, not the mechanism, and its failure is not by itself proof
  that the conditioning is worthless. Conversely, passing F2 would not prove
  the per-night story.
- **The V4 sign flip is a pre-registered second chance.** Allowing one
  re-specification to the opposite sign after seeing F1 doubles the effective
  test count. It is disclosed and counted, so it is not hidden p-hacking, but
  it weakens the “one pre-registered test” claim.

### 1.4 Does the rule follow from the mechanism?

Partly, but the weakest link is the sign. If the mechanism is “closing selling
is price pressure that reverses overnight”, then a more negative close should
predict a more positive overnight — that is the rule's direction. But the
cited literature does not establish that link, and the market-level
intraday-momentum literature points the other way. The 17-hour horizon is
reasonable for an overnight reversal; the TQQQ universe is a high-beta
extrapolation; the inverse-vol sizing is a risk overlay, not part of the
mechanism. The magnitude threshold (`|c30| ≥ 0.5 × median`) is a noise filter.

The rule is a coherent *test* of the hypothesis, but it is not a logical
consequence of the cited evidence. The report itself treats the sign as an
open question and lets the data settle it; that is legitimate research, but it
means the prior probability of success was not high.

### 1.5 Is the expected effect size plausible after 1 bp costs?

**No, not as a standalone edge.** The frozen dev result:

| Variant | 1 bp CAGR | 1 bp DD | 5 bp CAGR | 10 bp CAGR |
|---|---:|---:|---:|---:|
| V0 unconditional, every night | 35.00% | — | — | — |
| V1 close only, size 1 | 25.41% | — | — | — |
| V4 opposite sign | 1.00% | — | — | — |
| **V3 full** | **19.68%** | **31.81%** | **13.09%** | **5.37%** |

F1: mean block return after a sold close 22.27 bp vs 5.47 bp after a bought
close, difference 16.80 bp, **t = 1.35** — below the pre-registered 1.5. F2:
V1 25.41% < V0 35.00%, so conditioning loses on CAGR. F4 sub-period sign
stability fails. F7 at 5 bp fails (13.09% vs TQQQ's 36.39% dev). The strategy
has 1,221 fills and turnover of 2,544×; the 1 bp headline is not robust.

The unconditional overnight hold (V0) earns 35.0% with almost no intraday
exposure — that is the known overnight drift, not the closing-pressure signal.
The conditional version earns less. A 16.8 bp/night difference with t = 1.35
over ~2,000 nights is not enough to justify the complexity, and it disappears
against the unconditional benchmark.

### 1.6 Standalone strategy or risk overlay/filter in disguise?

It is a **standalone long/cash timing strategy** in legal form, but economically
it is a **filter on the unconditional overnight beta**. V0 is the old residue;
V3 is V0 with a condition that reduces return and a vol gate that reduces
exposure further. It is not an overlay on another strategy's positions, but it
is a timing filter in disguise: the return driver is the overnight drift, and
the new signal is a selection rule on top of it. Exposure is ~30% of nights
(2.3% of intraday bars; 17 hours per active night), so the book is flat most of
the session and earns a risk premium only overnight.

### 1.7 Is the claimed edge explained by known factors?

**Yes.** The dominant factor is the overnight drift (Cliff et al.; Lou et al.),
which is a well-documented calendar/time-of-day effect. The second factor is
TQQQ beta: the strategy is long a 3× Nasdaq ETF for 17 hours at a time. The
inverse-vol sizing is a volatility-scaling overlay. The conditional signal is
a short-horizon reversal/momentum hybrid whose sign is contested. There is no
factor-model attribution (FF5 + momentum, or an overnight/intraday
decomposition) to show that the conditional part earns anything beyond the
overnight premium.

### 1.8 Report vs code

- The HYPOTHESIS §2 says the strategy “sizes with the magnitude of the closing
  move”; the frozen spec uses the magnitude only as an entry threshold
  (`|c30| ≥ 0.5 × median`) and sizes by `0.40 / v`. This is an internal
  inconsistency between the hypothesis and the final rule, though the spec is
  explicit about it.
- The code's `weights_from_size()` writes the entry at `ends[k] - 1` (15:58)
  and the exit at `j - 1` where `j = starts[k+1] + 31`, so the fills are the
  15:59 open and the 10:01 open. This matches the report.
- The `exposure` field is bar-weighted: 2.3% of intraday bars, not 30% of
  capital-time. The original report warns about this; the rebuild report does
  not. A reader can easily misread the strategy as a tiny sleeve when it is a
  concentrated overnight bet.
- The report says “not yet tested” while `result.json` exists with status
  `retired_overlay_only`. The status is stale, not the result.

### 1.9 Strongest reason for the verdict

**The pre-registered conditioning test fails its own falsifiers.** F1 is
t = 1.35, F2 shows V1 (conditioning) at 25.4% vs V0 (every night) at 35.0%,
and the opposite-sign branch earns 1.0%. The return that remains is the
unconditional overnight premium — the old residue — not the closing-pressure
mechanism. That makes it an overlay/filter, not a new standalone edge.

---

## 2. `vol-kelly-overlay` — verdict: `unsupported`

### 2.1 Claimed mechanism and return driver

After a sharp QQQ selloff accompanied by a fast 1-minute realised-volatility
spike, volatility mean-reverts and TQQQ's daily-reset convexity produces a
positive 1–3 session rebound. The strategy waits in BIL, buys a
volatility-scaled TQQQ position after the first stabilisation (QQQ close above
the prior close), and exits on volatility normalisation, a 3-session time stop,
or a 4% QQQ price stop. The return driver is the post-spike reflation event.

This is **not** the original strategy's idea. The original `vol-kelly-overlay`
was a 20-day realised-vol ladder from TQQQ toward QQQ plus a crash throttle,
sitting on the 165-day QQQ base. The rebuild explicitly changes the economic
bet to a new event strategy. That is allowed by the brief, but it means the
original's evidence does not transfer; this is a new hypothesis.

### 2.2 Cited evidence vs the specific rule

| Source | What the source actually supports | Mismatch with the rule |
|---|---|---|
| Moreira & Muir (2017), *Volatility-Managed Portfolios* | Scaling exposure inversely to volatility improves Sharpe because volatility changes are not matched by proportional expected-return changes. Monthly factor portfolios. | Supports the `0.35 / v20` sizing and the use of vol as a state variable. Does **not** support a 1-minute RV spike + 10-day −5% + first-up-close entry, nor a 1–3 day TQQQ rebound. |
| Harvey et al. (2018), *The Impact of Volatility Targeting* | Volatility targeting reduces tail events and max drawdowns. Risk-management result. | Supports the risk-control assumption, not the alpha. It is not an entry signal. |
| Cheng & Madhavan (2009), *The Dynamics of Leveraged and Inverse ETFs* | Daily rebalancing makes LETF returns path-dependent; a de-levered fund has convexity. | Supports the *possibility* of a convex rebound, not its predictability. A lower NAV after a selloff does not imply a higher expected return; the expected return is still 3× the index minus drag. |
| ProShares TQQQ prospectus | Higher volatility and longer holding periods can make returns worse than the daily 3× target. | Supports the short 3-session hold, not the entry rule. |
| Own hypothesis | The exact event — RV spike, 10-day −5%, first up-close, 3-session hold — has **no external source**. | The report says this explicitly. The citations support components, not the rule. |

**Assessment.** The report is honest: the exact event is an own hypothesis. The
academic citations are about volatility scaling and LETF path dependence, not
about a 1-minute RV spike event. There is no paper that says “after a fast RV
spike and a 5% 10-day drawdown, the first up-close predicts a 1–3 day TQQQ
rebound”. The mechanism is plausible in the loose sense that post-selloff
reversal and LETF convexity exist, but the specific rule is unsupported.

### 2.3 Falsifiable and pre-registered?

**Yes on paper, but the run does not satisfy the pre-registration.** The report
lists nine falsifiers, including “fewer than 15 valid entries → underpowered;
report the count and do not claim an edge”, a bootstrap p-value, single-event
dependence, correlation, placebo, sub-period failure, and “stabilisation adds
nothing”. It also declares a ±1-step neighbourhood and a 10,000-resample
bootstrap.

The actual `result.json` has `variants_tried: 0`, no neighbourhood table, no
placebo, and only 11 events. The first falsifier is triggered: 11 < 15. The
mean event return is 0.0146% (0.15 bp), bootstrap p = 0.4879, so the second and
third falsifiers also trigger. The 2020–21 sub-period is −4.27%. The test is
underpowered and fails its own gates.

This is not a case of a good test that happened to fail; it is a case of a
design that was known to be underpowered before the run. `hypothesis.md` §7 says
“if a minute-marked event study of this shape cannot reach ~40 non-overlapping
events on dev, the sample is too thin… retired without running.” The actual
event count is 11. The hypothesis should have been retired before the run, not
reported as a pending result.

### 2.4 Does the rule follow from the mechanism?

The sign is plausible: after a selloff, a rebound is a known short-term
reversal/liquidity-provision effect. The 1–3 session horizon is plausible. The
TQQQ universe is a high-beta expression of the QQQ rebound; the 25–75% sizing
is a vol budget. But the “first up-close” condition is a momentum filter that
can delay entry and reduce the rebound capture, and the 4% QQQ stop is a risk
overlay. The mechanism does not pin the 10-day −5% threshold, the `v5/v20 ≥
1.5` spike, the 3-session hold, or the 4% stop; these are own design choices.
The rule is coherent but under-specified, and the sample is too small to
distinguish it from noise.

### 2.5 Is the expected effect size plausible after 1 bp costs?

**No.** The dev result:

| Metric | Value |
|---|---:|
| 1 bp CAGR / DD / Sharpe | 1.81% / 19.22% / 0.25 |
| 5 bp CAGR / DD | 1.70% / 19.30% |
| 10 bp CAGR / DD | 1.52% / 19.62% |
| Fills / turnover | 79 / 28.7× |
| Events | 11 |
| Mean event return | 0.0146% |
| Median event return | 3.86% |
| Hit rate | 63.6% |
| Bootstrap p | 0.4879 |
| Best / worst event | +6.41% / −10.80% |
| 2016–19 / 2020–21 / 2022–23 CAGR | +2.89% / −4.27% / +6.14% |

The mean is essentially zero; the median is positive because a few large
losses dominate the mean. The bootstrap p-value says the mean is
indistinguishable from zero. Costs are small (79 fills), so the problem is not
costs; it is that the event has no reliable positive expectancy. The 1.81%
CAGR is barely above BIL (1.39% in the same sample) and the Sharpe is 0.25. A
strategy that is in cash most of the time and earns less than cash-plus-noise
is not a standalone edge.

### 2.6 Standalone strategy or risk overlay/filter in disguise?

It is a **standalone event sleeve** in form: BIL by default, TQQQ only on the
event. It is not an overlay on another strategy's positions. But economically
it is a rare, cash-heavy long-beta event. The original was an overlay on the
165-day base; the rebuild is a new standalone event, not a test of the original
overlay. It is not a risk overlay in disguise, but it is also not a viable
strategy: it is an underpowered event study.

### 2.7 Is the claimed edge explained by known factors?

**Yes, mostly.** The post-selloff rebound is the short-term reversal /
liquidity-provision premium (Nagel 2012, Da et al. 2014, though the report does
not cite them for this rebuild). The TQQQ convexity is mechanical. The
volatility spike is a volatility-clustering state. The 2020–21 failure and the
zero mean suggest the event is not a stable premium; it is a rare crash
rebound that happened a few times. There is no factor attribution.

### 2.8 Report vs code

- The report's entry/exit rules match the code: signal at day `i` close, fill
  at `i+1` open; `v5/v20 ≥ 1.5`; 10-day high drawdown ≤ −5%; QQQ close > prior
  close; `w = clip(0.35 / v20, 0.25, 0.75)`; exit on `days >= 2`, `v5/v20 <
  1.00`, or `QQQ ≤ entry_px × 0.96`; exit at next open.
- The event study in `result.json` uses the **strategy's daily returns** over
  each event window, not the raw TQQQ event return. That is a legitimate
  measure of strategy event P&L, but it is not the same as “mean TQQQ rebound”
  and should not be compared directly to the TQQQ unconditional mean.
- The report says “no result / pending”; `result.json` exists with 11 events
  and status `pending_test`. The status is stale, and the report's own
  “underpowered → do not claim an edge” rule is not reflected in the status.

### 2.9 Strongest reason for the verdict

**Eleven events, a mean event return of 0.015%, and a bootstrap p of 0.49.**
The design's own first falsifier (fewer than 15 entries → underpowered) is
triggered, and the 2020–21 sub-period is negative. There is no statistically
or economically meaningful standalone edge to support.

---

## 3. `vol-scaled-crash-stop` — verdict: `overlay-only`

### 3.1 Claimed mechanism and return driver

Hold TQQQ by default, size it inversely to ATR, and when TQQQ breaks a
one-sided ATR barrier (`0.7 × ATR14`, capped at 4%), move the TQQQ sleeve to
BIL for the rest of the session and the night. The claimed edge is a
**conditional continuation** after the break: the break is not an average-day
signal but a tail signal, and the stop avoids the worst continuation days. The
rebuild claims this can replace the 165-day trend gate, producing a
lower-drawdown strategy with correlation below 0.60 to the old base.

The return driver is always-long TQQQ beta plus the stop's crash avoidance; the
ATR barrier is a risk overlay, not a new return source.

### 3.2 Cited evidence vs the specific rule

| Source | What the source actually supports | Mismatch with the rule |
|---|---|---|
| Kaminski & Lo (2014), *When Do Stop-Loss Rules Stop Losses?* | Stops add value under momentum / negative conditional skew. | Supports the general idea of a stop in a momentum asset. Does not support a 0.7×ATR one-sided barrier on TQQQ, the 4% cap, or the rest-of-session-and-night exit. |
| Moreira & Muir (2017), *Volatility-Managed Portfolios* | Inverse-vol scaling improves risk-adjusted returns. | Supports the `0.040 / ATR` sizing, not the stop or the event. Monthly factor portfolios, not a daily 3× ETF. |
| Cheng & Madhavan (2009); Avellaneda & Zhang (2010) | LETF daily rebalancing and path dependence; flows can amplify moves. | Supports the existence of LETF flow effects, not the sign/horizon of the trigger→next-open rule. |
| Mathis & Moerke (2022) | LETF/option rebalancing price effects are transitory and reverse the next day. | Supports a *reversal* boundary condition; the report uses it to justify exiting overnight. But the event study finds a negative mean from trigger fill to next open, i.e. continuation, not reversal. The citation is at best ambiguous for the rule's sign. |
| Quant Arenas Chandelier Exit; Cesar Alvarez stop study; FXNX 20,000-trade study | ATR-multiple exits; ATR stops are not automatically better; sub-1.0× ATR collapses under noise. | **Practitioner-only evidence.** Useful for calibration intuition, not for validating the edge. The 0.70 multiplier is from the author's own round-2 plateau, not from these sources. |
| Own test (round 2) | Trigger → next-open mean −0.46%, median −0.32%, 204 events. | The primary evidence for the rule is own, not external. The actual 2016–2023 event study is mean −0.27%, median +0.05%, p=0.073, so the effect is weaker than the round-2 number and not clearly negative. |

**Assessment.** The citations support the components — stops under momentum,
vol scaling, LETF path dependence, flow effects — but not the specific rule.
The core calibration (0.70×ATR, 2.5–4.0% band, 0.040 size target) is own or
practitioner-derived. The 4% cap is explicitly “inherited from the round-1
stop”, which is a subtle retention of the banned base: it is a parameter, not
the old armed stop, but it is still the old 4% level. The report is transparent
about this, but transparency does not make the rule independent.

### 3.3 Falsifiable and pre-registered?

**Yes, and the test was largely executed.** The report lists seven falsifiers:
correlation ≥ 0.60 (diversity), no drawdown improvement, CAGR below the
baseline without a 10 pp DD improvement, placebo match, event mean not
significantly below zero, cost fragility, and sub-period instability. It
declares 12 variants, 40 placebos, a 10,000-draw bootstrap, and a parameter
neighbourhood.

The result has 12 variants, 40 placebos, and a 607-event study. But the
`result.json` status is `pending_test`, `frozen_commit` is null, and the
report's “measured evidence” section is a pre-pause exploration with 100%
sizing, not the frozen primary. The primary run's correlation is 0.755, which
fails the first falsifier. The report's projection of 0.50–0.65 was wrong; the
sizing layer did not fix diversity.

### 3.4 Does the rule follow from the mechanism?

As a **risk rule**, yes: if a break can continue into the close/overnight, a
one-sided stop that exits for the rest of the session and night is coherent,
and inverse-vol sizing is coherent. As a **standalone return strategy**, no:
the mechanism is “own TQQQ beta and avoid some left-tail days”, not a new
return forecast. The sign of the event is weak (mean −0.27%, median +0.05%,
48.9% negative), so the “conditional continuation” claim is not strongly
supported. The 4% cap is a bound on the stop distance, not a prediction. The
rule is a risk overlay on beta, not a standalone alpha.

### 3.5 Is the expected effect size plausible after 1 bp costs?

**At 1 bp it looks strong; at realistic costs it is fragile.** The dev result:

| Metric | Primary | Binary core (100% sizing) | TQQQ | 165-day baseline |
|---|---:|---:|---:|---:|
| 1 bp CAGR | **51.46%** | 60.28% | 37.67% | 44.77% |
| 1 bp DD | **39.29%** | 59.43% | 82.29% | 62.21% |
| 1 bp Sharpe | 1.29 | 1.16 | 0.82 | 0.98 |
| 5 bp CAGR / DD | 41.13% / 43.14% | — | — | — |
| 10 bp CAGR / DD | 29.19% / 48.62% | — | — | — |
| Fills / turnover | 3,950 / 51,802× | 2,429 / 99,411× | — | — |
| TQQQ time | 71.95% | 85.85% | 100% | — |
| Corr vs 165d | **0.755** | 0.723 | — | 1.00 |

The 1 bp CAGR beats TQQQ and the baseline; the 5 bp still beats TQQQ (41.1% vs
37.7%) but the 10 bp does not (29.2% vs 37.7%). With 3,950 fills and turnover
of 51,802×, the 1 bp headline is not a realistic execution assumption. The
event study is 607 events, mean −0.2656%, median +0.0532%, 48.9% negative,
p(mean ≥ 0) = 0.0727. The mean is a fat left tail, not a reliable conditional
continuation; the median is positive. The strategy's return is mostly TQQQ beta
plus crash avoidance, and the 1 bp edge is the best case.

### 3.6 Standalone strategy or risk overlay/filter in disguise?

**Risk overlay in disguise.** It holds TQQQ 72% of minutes, has correlation
0.755 with the old base, and its return is TQQQ beta plus a stop. The ATR
barrier is a crash hedge, and the inverse-vol sizing is a risk budget. It is
not a new return driver. The report itself says the binary core “is a real
standalone return edge but it is not a risk strategy” and that the variants
which pass the correlation rule give up most of the return. The primary's
correlation 0.755 is above the pre-registered 0.60 ceiling, so it fails the
brief's diversity requirement. The repository's own summary calls it
“a better-managed TQQQ exposure rather than a new edge”. That is the right
description.

### 3.7 Is the claimed edge explained by known factors?

**Yes.** TQQQ beta, volatility scaling, and a stop-loss/momentum overlay. The
stop's event is a short-horizon continuation after a break, which is a known
stop-run/momentum effect. The inverse-vol sizing is the volatility-managed
portfolio effect. There is no factor attribution; the correlation with the old
base and the 72% TQQQ time are enough to explain the return.

### 3.8 Report vs code

- The report's measured binary core table (452 events, 65.10% CAGR, 59.43% DD,
  corr 0.64) is **not** the frozen primary (607 events, 51.46% CAGR, 39.29% DD,
  corr 0.755). The report labels the table “pre-pause, binary 100% core”; it is
  not directly comparable to the primary. The event count difference (452 vs
  607) is large enough that the two tables should not be read as the same test.
- The `atr_series` uses ATR through the prior close and divides by the prior
  close; the first 13–14 sessions have no ATR, so the stop is disabled and size
  is 1.0. This matches the report's disclosure.
- The trigger uses `closes[f:l+1, 1] < session_open × (1 − d)`, and the weight
  at the trigger bar is set to BIL, filled at the next bar's open. This matches
  “sell at the next bar's open”.
- The result's `status` is `pending_test` even though the run exists and the
  summary says rejected. The report's status is stale.
- The report's projection “correlation 0.50–0.65” is contradicted by the
  measured 0.755. The sizing layer did not reduce correlation versus the
  binary core; it slightly increased it (0.723 → 0.755). This is a substantive
  spec-vs-result miss, not a rounding issue.

### 3.9 Strongest reason for the verdict

**Correlation 0.755 with the old 165-day base, above the rebuild's own 0.60
ceiling.** The strategy is always-long TQQQ with a stop and inverse-vol size;
the 1 bp return is real but it is a better-managed TQQQ beta, not a new
independent edge. The event mean is only −0.27% with p=0.073, and the median is
positive, so the “conditional continuation” story is weak even before the
diversity failure.

---

## 4. `volume-orderflow` — verdict: `unsupported`

### 4.1 Claimed mechanism and return driver

A session in which QQQ sells off **inside the day** (`open→close ≤ −0.8%`) on
well-above-normal volume (`rvol ≥ 1.5`) but closes in the upper half of its
range (`clv ≥ 0`) marks absorbed supply: the selling was non-informational and
the stock has been transferred to patient hands. Buy 100% TQQQ at the next
open, hold five sessions, otherwise BIL. The return driver is a
participation-conditioned supply-climax reversal.

### 4.2 Cited evidence vs the specific rule

| Source | What the source actually supports | Mismatch with the rule |
|---|---|---|
| Campbell, Grossman & Wang (1993), *Trading Volume and Serial Correlation in Stock Returns* | High-volume declines exhibit return reversal because the price pressure is non-informational/liquidity-related. Cross-sectional, daily/monthly. | Supports the **sign** (buy after a high-volume decline). Does not require a close in the upper half of the range, a 5-session hold, or a 3× ETF. The paper's reversal is about the decline itself, not about a decline that has already been bought back intraday. |
| Gervais, Kaniel & Mingelgrin (2001), *The High-Volume Return Premium* | Stocks with unusually high volume outperform over the following days/weeks. Cross-sectional, monthly; replicated across 41 countries. | Supports “abnormal participation is informative”, but the premium is positive after high volume regardless of direction. The rule uses volume as a condition for a **decline** event; the horizon and universe are different. |
| Lee & Swaminathan (2000), *Price Momentum and Trading Volume* | Momentum life cycle: high-volume winners reverse faster. Cross-sectional. | Supports the direction check (a high-volume advance is the late-stage case), not the specific decline event. |
| Conrad, Hameed & Niden (1994), *Volume and Autocovariances in Short-Horizon Individual Security Returns* | High-volume days are followed by negative short-horizon autocorrelation. Cross-sectional. | Supports reversal, not the CLV filter or the 5-session hold. |
| Gao, Han, Li & Zhou (2018), *Market Intraday Momentum* | Intraday predictability is stronger on higher-volume days. | Used only as a conditioning insight; their actual first-half-hour → last-half-hour rule was tested and rejected. It does not support the supply-climax story. |

**Assessment.** The citations support a generic high-volume decline/reversal
effect, but the specific event — intraday decline + CLV in the upper half +
5-session TQQQ hold + 100% size — is an own construction. The CLV filter is
the most questionable part: if the close is already in the upper half of the
range, the intraday decline has been substantially bought back, so the
remaining reversal may be smaller, not larger. The report's own F8 tests
whether the CLV filter is doing the work; with 3 events, it cannot.

### 4.3 Falsifiable and pre-registered?

**Yes on paper, but the design fails its own power gate.** `hypothesis.md`
lists F1–F8: event mean > unconditional, bootstrap p ≤ 0.10, net of costs,
sub-period sign, placebo, correlation, plateau, and the CLV ablation. `spec.md`
declares the parameter surface and the event thresholds. `hypothesis.md` §7 says:
“If a minute-marked event study of this shape cannot reach ~40 non-overlapping
events on dev, the sample is too thin to pass F2 and the design should be
retired without running.”

The actual result has **3 events** (2020-09-04, 2021-05-04, 2021-07-27), 15
sessions long out of 2,012 (0.75% of sessions), 13 fills, 0.87% CAGR, 16.66%
DD, 0.154 Sharpe. The design was known to be underpowered and was run anyway.
No neighbourhood or placebo table appears in the result. This is a
pre-registration that predicts its own failure; it is not evidence for the
hypothesis.

### 4.4 Does the rule follow from the mechanism?

The sign is plausible: high-volume declines reverse, so buying after one is
directionally consistent. But the CLV filter selects days where the decline
was already absorbed; that is a different claim from “the decline reverses”.
The 5-session horizon is arbitrary; the paper's reversal is shorter. The TQQQ
universe is a 3× expression, which amplifies both the reversal and the risk.
The 100% sizing is aggressive for a single-event strategy. The rule is a
plausible event study, but it is not tightly derived from the cited mechanism,
and the event definition is so restrictive that it is empty.

### 4.5 Is the expected effect size plausible after 1 bp costs?

**There is no measurable effect.** The dev result:

| Metric | Value |
|---|---:|
| 1 bp CAGR / DD / Sharpe | 0.87% / 16.66% / 0.15 |
| 5 bp CAGR / DD | 0.81% / 16.80% |
| 10 bp CAGR / DD | 0.73% / 17.10% |
| Events / sessions long | 3 / 15 |
| TQQQ exposure | 0.745% of sessions |
| Fills / turnover | 13 / 13.6× |
| BIL benchmark | 1.39% CAGR |
| 165-day baseline | 44.76% / 58.76% |
| Correlation vs 165d | 0.141 |

Costs are negligible (13 fills), but the return is below BIL and the strategy is
in TQQQ only 0.75% of the time. The result is not an edge; it is an empty
strategy. The report's own risk table predicted 15–30 events; the actual 3 is
worse. A single 2020 event can dominate the P&L; the 2021 events are small.

### 4.6 Standalone strategy or risk overlay/filter in disguise?

It is a **standalone event sleeve** in form, but it is effectively empty. It is
not an overlay on another strategy, but the original was a volume-armed stop
overlay; the rebuild tried to turn the stop-arming condition into a return
forecast, and the forecast is too rare to test. The honest label is
“unsupported/empty”, not “standalone strategy”.

### 4.7 Is the claimed edge explained by known factors?

**Yes, if there is any edge at all.** The event is a short-term reversal after
a high-volume decline — a known liquidity-provision/reversal effect (Campbell
et al., Conrad et al.). The TQQQ leg is 3× QQQ beta, and the 5-session hold
captures beta as much as reversal. The 2020 event is a crash rebound. There is
no factor attribution and no evidence that the CLV filter adds anything.

### 4.8 Report vs code

- The event rule matches the spec: `rvol = q_vol / mean(prior 20 sessions)`,
  `intraday = close/open − 1 ≤ −0.008`, `clv ≥ 0.0`, `hold = 5`.
- `holding_flags()` sets the position for sessions `d+1..d+5` and exits at the
  open of `d+6`; this matches “5 complete sessions”.
- The result's `windows.dev.1bp.exposure` is **0.9999987** because the book is
  always 100% invested in either TQQQ or BIL. The meaningful TQQQ exposure is
  `info.exposure = 0.007455` (0.75% of sessions). The report's table would be
  misleading if it quoted the 100% field as “exposure”; the report itself says
  expected 25–40%, so the actual 0.75% is a major miss.
- The report says “not run”; `result.json` exists with 3 events and status
  `pending_audit`. The status is stale.
- The `hypothesis.md` preliminary evidence (n=142 sessions with rvol > 1.5 and
  a down close, +0.70% next session) is a **different event** from the frozen
  rule (which also requires an intraday decline and CLV ≥ 0). It cannot be used
  as evidence for the frozen rule. The report says this, but the reader should
  not conflate the two.

### 4.9 Strongest reason for the verdict

**Three events in 2,012 sessions.** The design's own rule says to retire
without running if it cannot reach ~40 events; it reached 3. The cross-sectional
and monthly volume literature cannot validate a single-asset, 5-session event
with a CLV filter, and the result (0.87% CAGR, below BIL) is an empty strategy,
not a weak edge.

---

## 5. `winner-ensemble-blend` — verdict: `unsupported`

### 5.1 Claimed mechanism and return driver

Allocate capital across two “independent” return streams by inverse trailing
volatility: Stream A is a calm-regime QQQ carry (70% QQQ / 30% BIL when
short-term vol is in the bottom 40% of its 60-day range and QQQ's 5-day return
is positive); Stream B is a panic-reversal TQQQ trade (buy after a 3-day ≤ −5%
or a 1-day ≤ −3% with 10d/60d vol ≥ 1.5, hold 1–3 sessions, exit on a close
above the 10-day mean, an 8% close stop, or time). The claim is that the blend's
risk comes from the combination, with lower drawdown than either stream and
correlation below 0.60 to the old base.

The original strategy was a 75/25 blend of two sleeves that both sat on the
same 165-day QQQ base; its own report says it was a “textbook risk-reduction
blend, not a new alpha source”. The rebuild tries to test the allocation idea
on genuinely different streams.

### 5.2 Cited evidence vs the specific rule

| Source | What the source actually supports | Mismatch with the rule |
|---|---|---|
| Nagel (2012), *Evaporating Liquidity* | Short-horizon reversal is a liquidity-provision premium; reversal profits rise with volatility/VIX. Cross-sectional stocks. | Supports Stream B's direction and vol conditioning. Does not support a 3-day QQQ decline + TQQQ + 3-session hold; the universe and sizing are extrapolations. |
| Da, Liu & Schaumburg (2014), *A Closer Look at the Short-Term Return Reversal* | Reversal profits are concentrated in high-volatility, high-turnover stocks and are consistent with liquidity provision. | Supports the vol-ratio condition, but cross-sectional; not a single index ETF. |
| Connors & Alvarez (2008), *Short Term Trading Strategies That Work* | RSI(2)-style oversold dip buying **inside an uptrend**, with a fast exit on the bounce. Practitioner book. | The rebuild removes the 200-day trend filter and uses a naked panic-reversal. That is a **different effect** from the book's rule. The report admits “low” confidence and says the exact rule is not reproduced. |
| Moreira & Muir (2017), *Volatility-Managed Portfolios* | Volatility timing as a state/leverage rule; monthly factor portfolios. | Supports Stream A's state filter in spirit, but not a 60-day vol quantile on QQQ. The report admits the paper “does not validate the exact threshold”. |
| Cederburg et al. (2020), *On the Performance of Volatility-Managed Portfolios* | Volatility scaling is fragile across portfolios/specifications. | Used correctly as a caution/falsifier, not as support. |
| Asness, Frazzini & Pedersen (2012), *Leverage Aversion and Risk Parity* | Risk parity / inverse-vol allocation across asset classes with leverage. | Supports the weighting principle, not an unlevered, single-factor, two-stream blend. The report admits. |
| DeMiguel, Garlappi & Uppal (2009), *Optimal Versus Naive Diversification* | Simple 1/N and risk-based weights are hard to beat out of sample. | Supports the simple clip, but the paper is about many-asset portfolios, not two correlated streams of the same factor. |
| Newfound (2020), *Ensembles and Rebalancing* | A rebalanced blend of strategies can have a higher geometric return; the optimal mix can beat either component. | Practitioner blog; motivates testing a blend, not the existence of a premium. |

**Assessment.** The citations support the components and the risk-parity
principle, but not the specific claim that these two streams are independent
premia or that the blend has an edge. The report is honest about the gaps. The
strongest citation, Nagel (2012), is about cross-sectional stock reversal, not
a 3-day QQQ/TQQQ event. Connors & Alvarez is a practitioner source for a
different rule (RSI(2) within an uptrend); removing the 200-day filter removes
the part that made the practitioner rule robust.

### 5.3 Falsifiable and pre-registered?

**Yes, and the test was run.** `HYPOTHESIS.md` and `SPEC.md` list eight
falsifiers, 13 parameters with ±1-step neighbours, a 200-draw placebo, a
10,000-resample event bootstrap, and sub-periods. The result has 29 variants,
a placebo, an event study, and a rejection status with five reasons:
`blend_adds_nothing`, `fails_5bp`, `carry_stream_not_a_premium`,
`reversal_event_study_weak`, `placebo_beats_real`.

The pre-registration is strong. The only issue is that the report is stale
(“SPEC ONLY — BACKTESTS PAUSED”) while the result is a clean rejection. The
result should be believed over the report's status.

### 5.4 Does the rule follow from the mechanism?

The allocation logic follows risk parity: inverse-vol weights, a 20/80 clip,
and a residual BIL. The two streams are deliberately opposite conditional
exposures (calm-up vs panic-down), and their daily correlation is −0.001, so
the “combination” idea is at least internally coherent. But both streams are
still QQQ/TQQQ equity beta; the “independence” is conditional, not structural.
Stream A is a low-vol QQQ carry, Stream B is a high-beta crash rebound. The
70% QQQ / 30% BIL sizing and the 20/80 clip are risk choices, not fitted
values, but they are arbitrary. The rule follows the risk-parity principle;
it does not follow that the resulting blend has a positive expected return,
because the components do not.

### 5.5 Is the expected effect size plausible after 1 bp costs?

**No.** The dev result:

| Metric | Blend | Stream A | Stream B |
|---|---:|---:|---:|
| 1 bp CAGR | **0.30%** | 1.68% | −6.19% |
| 1 bp DD | **32.67%** | 15.22% | 68.78% |
| 1 bp Sharpe | **0.084** | 0.310 | −0.054 |
| 5 bp CAGR / DD | −0.61% / 34.91% | — | — |
| 10 bp CAGR / DD | −1.79% / 37.83% | — | — |
| Fills / turnover | 773 / 204.6× | 503 / 369.5× | 133 / 122.7× |
| Correlation A/B | −0.001 | — | — |
| Correlation vs 165d | 0.238 | 0.373 | 0.157 |

The blend's 1 bp CAGR is 0.30%, below BIL (1.39%); at 5 bp it is negative. Its
Sharpe (0.084) is below Stream A's (0.310), and its drawdown (32.67%) is worse
than Stream A's (15.22%). The allocation fails the “adds something” test: it
combines a weak positive-Sharpe stream with a negative-Sharpe stream and ends
up worse than the better stream. The event study is 33 events, mean 3-day
forward 0.713% vs unconditional 0.615%, bootstrap p=0.369 — not significant.
The placebo is decisive: the real Sharpe 0.084 vs random mean 0.331, and 79% of
random entries beat the real signal. The blend is not a premium; it is a
low-beta book that under-earns cash.

### 5.6 Standalone strategy or risk overlay/filter in disguise?

It is a **standalone two-stream allocation** in form, not an overlay on the old
base. But the allocation is a risk overlay on two weak signals: the only thing
it reliably does is lower volatility and correlation by holding less equity.
The result is a low-beta, low-return book (11.7% vol), not a new return stream.
The original was a risk-reduction blend on the old base; the rebuild is a
risk-reduction blend on two weak standalone streams. It is “standalone” in
construction but not in economic content.

### 5.7 Is the claimed edge explained by known factors?

**Yes.** Stream A is the equity risk premium in calm markets plus volatility
timing; Stream B is short-term reversal/liquidity provision plus TQQQ beta;
the allocation is inverse-vol risk parity. All three are known effects. The
blend's low correlation with the old base is achieved by being mostly low-beta
or cash, not by a new driver. There is no factor attribution. The 0.30% CAGR is
below BIL, so the “premium” is not even cash-plus.

### 5.8 Report vs code

- The rules match the code: `on_a = (vol10 < q40) & (r5 > 0)`, 70% QQQ;
  `entry_b = (r3 ≤ −5%) | (r1 ≤ −3% & vol10/vol60 ≥ 1.5)`; exit on `qqq >
  sma10`, `tqqq < entry_ref × 0.92`, or `held ≥ 3`; 2-session cooldown;
  `aA = clip((1/σA)/(1/σA + 1/σB), 0.20, 0.80)`, σ shifted one day.
- The report says “SPEC ONLY / no numbers”; `result.json` exists with status
  `rejected` and 29 variants. The report is stale.
- The report's “expected correlation 0.30–0.55” is met (0.238), but that is the
  only thing that works. The report's “low absolute return is acceptable” is
  not met: the return is below BIL, and the 5 bp result is negative.

### 5.9 Strongest reason for the verdict

**The blend adds nothing and fails its own placebo.** Stream A earns 1.68%,
Stream B loses 6.19%, and the blend earns 0.30% — below BIL — with a Sharpe
(0.084) below Stream A's. The event study p=0.37 and 79% of random entries beat
the real Sharpe. The allocation idea is not supported by these streams.

---

## 6. `ratio-pairs` — “Ratio froth” — verdict: `overlay-only`

### 6.1 Claimed mechanism and return driver

The TQQQ/QQQ ratio is a leverage-cycle meter. Because
`log(TQQQ/QQQ) = 2 log(QQQ) − 3 × realised variance` (plus financing), a ratio
far above its own 200-day mean is a low-volatility, strongly trending melt-up
in which leveraged exposure has compounded without paying drag. Such froth is
said to predict poor forward TQQQ returns and elevated crash risk. The rule
holds **QQQ instead of TQQQ** on the next session when the prior close's log
ratio extension exceeds 0.18, and otherwise runs the round-1 winner unchanged.

This is explicitly **the old base plus an overlay**: the base is
“QQQ above its 165-day SMA → 100% TQQQ, else BIL”, and the 4% armed minute stop
is unchanged. The ratio overlay only changes the asset held on 21.5% of
sessions. The return driver is therefore the old base + stop + a beta-reduction
filter, not a standalone ratio edge.

### 6.2 Cited evidence vs the specific rule

| Source | What the source actually supports | Mismatch with the rule |
|---|---|---|
| Avellaneda & Zhang (2010), *Path-Dependence of Leveraged ETF Returns* | An exact accounting identity: for a daily-rebalanced LETF, `log(L/L0) = b log(S/S0) + (b−b²)/2 V + financing`; for b=3, `log(L/S) = 2 log(S/S0) − 3V`. | The identity describes how the ratio is **constructed**, not how it predicts returns. A high ratio means QQQ is far above its starting level and/or variance is low; it does not imply a lower forward return. The report uses the identity correctly but then makes a predictive leap it does not support. |
| Brunnermeier & Sannikov (2014), *A Macroeconomic Model with a Financial Sector* | The “volatility paradox”: low exogenous risk → intermediaries choose higher leverage → the system is more fragile to a shock. A macro model. | A metaphor for why low-vol melt-ups can be fragile, not a 200-day ratio threshold, a 1-month horizon, or a QQQ/TQQQ pair rule. It does not test the trading signal. |
| NY Fed Liberty Street Economics (2017), *The Low Volatility Puzzle* | A plain-English commentary: low volatility can be a catalyst for high future volatility. | Practitioner/commentary, not a test of the ratio rule. It supports the *state* interpretation, not the threshold. |
| Adjusted Close, *Leveraged ETF “Decay” Is Not What You Think It Is* | LETF drag ≈ 3σ²; volatility break-even near 14% realised vol; TQQQ financing/fee gap ~7.2%/yr. A blog. | Supports the drag arithmetic, not the froth signal. Practitioner source. |
| Trainor (2025), *Beyond Volatility Decay* | LETF expected returns are state-dependent; the standard decay formula is not constant. | Supports the idea that variance matters, not the 0.18 threshold or the sign of the forward return. |
| Cheng & Madhavan (2009) | Daily re-leveraging creates path dependence; value can be destroyed for buy-and-hold investors. | Supports the ratio construction, not the predictive rule. |
| Hessel, Nam, Wang, Cunyu & Zhang (2017) | LETF pair spreads mean-revert; profits are a bet on index mean reversion and die in trends. | Supports a **different** effect (pair mean reversion), and the report tested/rejected it. |
| FinLab (2026); Exent (2026) | Practitioner backtests of the 200-day TQQQ rule: ~45–46% CAGR, ~55–61% DD, 2017–2026. | Benchmark context for the base, not evidence for the ratio froth. |

**Assessment.** The identity is correct and the report uses it well as a
description of what the ratio contains. But the identity is not a forecast. The
report's own regression makes this explicit:

```
ext200 = −0.106 + 2.067 × qqq_ext200 + 1.342 × (−(200d RV − 400d mean))
R² = 0.978
```

The ratio is ~97.8% explained by QQQ's own extension plus a variance term. It
is not a new object; it is a re-parameterisation of “QQQ is far above trend and
volatility is low”. The report says the slope on QQQ extension is “exactly the
theoretical 2.0” and the residual is variance — that is an admission that the
ratio is mostly QQQ trend + low vol, not a new signal. The “froth” label is an
interpretation of a known low-vol melt-up state, supported by a macro metaphor,
not by a paper that tests the trading rule.

### 6.3 Falsifiable and pre-registered?

**No, not the original.** The original `ratio-pairs` report is post-hoc. It
says the “natural guess” (ratio in an uptrend → hold TQQQ) “turns out to be the
wrong sign”; Section 5 documents the negative results; the 0.18/200-day point
came from a **35-point grid (5 MAs × 7 thresholds)**. The folder's
`web_audit.json` says: “The 0.18/200-day point came from a 35-point grid … and
is **not pre-registered**.” There is no pre-test pass/fail rule; the report was
written after the tests, with the sign and threshold chosen in-sample. The
robustness checks (rolling 3-year windows, episode jackknife, permutation,
look-ahead shift) are all in-sample over 2017–2026. The 28 rolling 3-year
windows overlap heavily; they are not independent evidence.

This is the single biggest validity problem in the batch: the rule's sign and
threshold are the product of the same data used to evaluate them.

### 6.4 Does the rule follow from the mechanism?

The sign is counterintuitive and was inverted after the natural guess failed.
The horizon is inconsistent: the signal is a slow level (200-day MA), but the
claimed effect is a 1-month forward return; the signal can persist for months.
The 2020-11-12 → 2021-02-25 episode is 71 sessions and +25.8% of missed TQQQ;
the report acknowledges that a melt-up can continue. The universe is QQQ/TQQQ;
holding QQQ instead of TQQQ is a beta reduction, not a short. If the mechanism
is “froth → crash”, the logical position is cash or a hedge, not 1× QQQ. The
report chooses QQQ because it is “defensible” and still dominates the winner,
but the BIL variant is actually better in-sample (73.26% vs 69.50% CAGR, same
39.11% DD). That is a narrative choice, not a mechanism implication.

The rule is a **de-risking overlay**: on froth days, cut beta from 3× to 1×.
It does not express a negative expected return; it expresses “own less beta
after a big run-up”. That is a known crash-hedge/trend-exhaustion idea, not a
new ratio edge.

### 6.5 Is the expected effect size plausible after 1 bp costs?

The headline is strong, but it is the old base + stop, and costs are high:

| Metric | Full | No stop | Winner (no overlay) | Defensive BIL |
|---|---:|---:|---:|---:|
| 10y 1 bp CAGR / DD | **69.50% / 39.11%** | 60.15% / 53.31% | 58.80% / 44.56% | 73.26% / 39.11% |
| 5y 1 bp CAGR / DD | **63.74% / 26.85%** | 52.01% / 35.55% | 49.88% / 33.49% | 69.72% / 26.00% |
| 10y 5 bp CAGR / DD | 63.46% / 41.75% | — | 54.60% / 47.08% | — |
| 10y 10 bp CAGR / DD | 56.22% / 45.03% | — | ~49.50% / 50.06% | — |
| Fills / turnover | 889 / 38,895× | 349 | 657 | 821 |
| Correlation vs TQQQ | 0.64 | — | — | — |
| Full 2016–2026 CAGR / DD / Sharpe | 62.21% / 36.65% / 1.43 | — | — | — |

The 10y headline is 2017-01-03 → 2026-10-23, not the uniform 2016-01-04 →
2026-10-23 window; on the full window it is 62.21% / 36.65%. The overlay fires
on 21.5% of sessions (67 episodes), costs about 1.5 pp of CAGR per 1 bp of
slippage, and has 889 fills / 38,895× turnover. At 10 bp the strategy's 10y
result is 56.22% / 45.03%; the winner's 10 bp result is 49.50% / 50.06%, so the
strategy still dominates at 10 bp too. The report's text says the 10 bp DD is
“0.47 pp worse than the winner (45.03% vs 44.56%)”, but 44.56% is the winner at
**1 bp**; comparing the strategy at 10 bp to the winner at 1 bp is an
apples-to-oranges cost comparison. The real cost issue is the 38,895× turnover
and the ~1.5 pp of CAGR lost per 1 bp, not a loss of dominance at 10 bp. (The
folder's `web_audit.json` repeats the same 1 bp/10 bp mix and should be
corrected.)

The ablation is the key:

- **Overlay alone, no stop:** 60.15% / 53.31% vs winner 58.80% / 44.56% — the
  overlay adds 1.35 pp of CAGR but **8.75 pp more drawdown**. It is not a
  risk-improving overlay on its own.
- **Full with stop:** 69.50% / 39.11%. The stop adds 9.35 pp CAGR and cuts DD
  by 14.2 pp. The stop, not the ratio, is the dominant risk control.
- **Defensive BIL instead of QQQ:** 73.26% / 39.11% — better than the headline.
  The report does not headline it because it is a bet that melt-ups reverse;
  that is a defensible narrative choice, but it shows the “QQQ” leg is not the
  unique expression of the signal.

The report itself says: “It is a crash hedge, not alpha… The mean advantage is
concentrated in the left tail (hit rates 53.6% vs 56.4%). A sample without a
Feb-2018, a Mar-2020, a Nov-2025 and a Jul-2026 would show the overlay costing
money. The drawdown control is the part I would expect to persist; the +10.7 pp
of CAGR is not something to underwrite.” That is the right conclusion, and it
is inconsistent with the website's “Leader” status on a like-for-like CAGR
table.

### 6.6 Standalone strategy or risk overlay/filter in disguise?

**Overlay/filter in disguise — in fact, not even in disguise.** It literally
uses the old 165-day QQQ gate and the 4% armed minute stop. The ratio is a
daily overlay that switches TQQQ → QQQ on 21.5% of sessions. The report says
“Base (round-1 winner, unchanged)” at the top of its rules. The strategy cannot
be compared to a standalone rebuild because it is the old base plus a filter.
The old base and stop are doing most of the work; the overlay is a crash hedge
that happens to have paid in this sample.

### 6.7 Is the claimed edge explained by known factors?

**Yes.** The 165-day QQQ gate is a trend/momentum factor. The 4% stop is a
crash-risk overlay. The ratio is ~97.8% QQQ extension + variance, so the
“froth” is a low-vol melt-up state — a combination of trend, low-volatility,
and crash-risk factors. The report's IC table shows the ratio trend is
contrarian at 5–60 days, which is a mean-reversion/timing effect. The gains are
concentrated in a handful of crash episodes (2018-01, 2020-07/09, 2021-11,
2023-08, 2025-11, 2026-06); a sample without those episodes would show the
overlay costing money. There is no factor-model attribution (FF5 + momentum +
vol), and the 2×2 sort controls for QQQ extension but not for volatility, so
the “ratio” split may simply be a volatility split. The report itself notes
that froth days have 1.9%/day realised vol vs 2.7%/day otherwise. That is a
known low-vol state, not a new ratio premium.

### 6.8 Report vs code

- **The old base and stop are present.** `strategy.py` has `SMA_N = 165`,
  `STOP = 0.04`, `MA_FAST = 20`, `ARM_BUF = 0.01`, and `winner_state()`
  implements “QQQ prior close > 165d SMA” plus the armed 4% stop. This directly
  contradicts any claim that Ratio froth is a standalone rebuild.
- **The 4% stop is applied to a QQQ position on froth days.** The stop trigger
  is `tqqq_close[i] < tqqq_open × (1 − 0.04)`, but on froth days the book holds
  QQQ. A 4% TQQQ drop is roughly a 1.33% QQQ drop, so the stop is effectively a
  ~1.3% QQQ stop — three times tighter on the actual position than the nominal
  4%. The report acknowledges “the 4% stop still applies while in QQQ, so a
  3x-sized intraday collapse takes the book to BIL”, but the ablation then
  attributes the full-vs-no-stop gain to “the stop” without adjusting for the
  fact that it is a different, much tighter risk rule on the QQQ leg. This is
  a real economic mismatch and likely inflates the full strategy's result
  relative to a fair “QQQ with a 4% QQQ stop” comparison.
- **The headline window is 2017–2026, not 2016–2026.** `START10 = 2017-01-03`;
  the full-window 2016–2026 result is 62.21% / 36.65%, not 69.50% / 39.11%.
  The website's “69.50%” is the 10y window, which excludes the weak 2016 year.
- **The 10 bp “not dominant” claim is a cost-mismatch error.** The report says
  at 10 bp the 10y DD is 45.03% vs the winner's 44.56% (0.47 pp worse). But
  44.56% is the winner at **1 bp**; the winner's 10 bp result is 50.06% DD and
  49.50% CAGR. The ratio strategy at 10 bp is 56.22% / 45.03%, so it still
  dominates at 10 bp on both metrics. The real 10 bp issue is the 38,895×
  turnover and the ~1.5 pp CAGR lost per 1 bp, not a loss of dominance. The
  folder's `web_audit.json` repeats the same 1 bp/10 bp mix and should be
  corrected.
- **The threshold and sign are post-hoc.** The folder's `web_audit.json` says
  “not pre-registered”; the report's Section 5 documents the negative natural-sign
  result; the 0.18/200 point came from a 35-point grid. The surface is
  `surface.json`; 200/0.20 is 72.2% / 40.5% and 150/0.18 is 71.2% / 43.0%, so
  the chosen point is not a unique peak, but it is still an in-sample choice.
- **The 584 froth days are clustered.** The report says 67 de-risking episodes;
  584/67 ≈ 8.7 days per episode; the effective number of independent melt-ups
  is 8–10, not 584. The t = −2.87 on daily means overstates significance. The
  20-day forward mean −1.51% vs +5.86% is overlapping and dominated by the
  same few crashes. The report acknowledges this, but the headline still leans
  on the t-stat and the 584-day sample.
- **The matched-frequency control is not a clean control.** `QQQ ext200 >
  0.12` on 649 days gets 55.48% / 39.11% vs the ratio rule's 69.50% / 39.11%.
  This is a useful check, but the threshold 0.12 is chosen to match frequency,
  not severity; it does not control for volatility, which is the other half of
  the ratio. A 2×2 sort on QQQ extension × volatility would be a cleaner test
  of whether the ratio adds anything beyond the low-vol state.
- **The status is stale.** The report is a post-hoc result; `result.json`
  exists. The “Leader” website status is a comparison against the old base,
  not against standalone rebuilds.

### 6.9 Strongest reason for the verdict

**Ratio froth is the old 165-day QQQ gate plus the 4% armed stop plus a ratio
filter.** The overlay alone (no stop) adds only 1.35 pp CAGR and *worsens*
drawdown from 44.56% to 53.31%; the full 69.50% / 39.11% is a joint product of
the old base, the old stop, and a crash-hedge filter. The standalone rebuild of
the ratio idea (`research/revisit/ratio-pairs`) gets 18.96% dev / 20.42% full —
about QQQ — which is the honest like-for-like number. The 69.50% headline is a
base/timing artifact, not a standalone edge.

---

## Cross-cutting

### Common failure patterns

1. **Base leakage in disguise.** The brief bans the 165-day QQQ gate and the
   old 4% stop, but several strategies keep the same economic exposure:
   `vol-scaled-crash-stop` is always-long TQQQ with a stop and inverse-vol size
   (72% TQQQ time, corr 0.755); `time-of-day`'s V0 unconditional overnight hold
   earns 35.0% vs the conditional 19.7%; `ratio-pairs` literally uses the old
   gate and stop. The “no 165-day MA” rule is satisfied, but the return driver
   is still TQQQ/QQQ beta. Correlation with the old base is not sufficient to
   prove independence: time-of-day passes at 0.34 but is overnight beta;
   vol-scaled fails at 0.755; ratio froth is the old base by construction.

2. **Empty or underpowered event studies.** `volume-orderflow` has 3 events in
   2,012 sessions; `vol-kelly-overlay` has 11 events (own minimum 15);
   `winner-ensemble-blend` Stream B has 33 events (event p=0.37). The reports
   often pre-register a minimum count and then run anyway. The result is a
   point estimate dominated by one or two episodes, with a bootstrap p-value
   that cannot support a claim.

3. **Post-hoc sign and threshold selection.** The ratio froth's natural sign
   was wrong, so the rule was inverted; the 0.18/200-day point came from a
   35-point grid and is explicitly “not pre-registered”. `time-of-day` allows
   one sign flip to V4 after F1. `vol-scaled` uses a 0.70 multiplier from a
   round-2 plateau and a 4% cap inherited from the old stop. The
   “pre-registration” documents are often written after exploratory runs (the
   reports say “pre-pause exploration”), so the effective multiple-testing
   burden is much larger than the stated variant count.

4. **Citation-to-rule gap.** The papers support components — the overnight
   premium, LETF path dependence, volatility clustering, high-volume reversal,
   risk parity — but not the specific sign, threshold, horizon, universe and
   sizing. Cross-sectional stock evidence is applied to a single 3× index ETF;
   practitioner blogs are used for stop calibration; own tests are the core
   evidence. The reports are often honest about this, but honesty about a weak
   citation is not the same as a supported rule.

5. **Cost and turnover fragility.** `time-of-day` has 1,221 fills and 2,544×
   turnover; `vol-scaled` has 3,950 fills and 51,802×; `ratio-pairs` has 889
   fills and 38,895×. The 1 bp headline is fragile in different ways: time-of-day
   falls from 19.7% to 13.1% at 5 bp; vol-scaled falls from 51.5% to 29.2% at
   10 bp, below TQQQ; ratio-froth loses about 1.5 pp of CAGR per 1 bp and its
   10 bp CAGR is 13.3 pp below its 1 bp result, even though it still beats the
   old winner at the same cost. Some reports compare a 10 bp strategy result to
   a 1 bp winner (the ratio-froth report does exactly this), or headline only
   the 1 bp row. Cost sensitivity is a first-order part of the research, not a
   robustness footnote.

6. **Known-factor repackaging.** The strategies are combinations of overnight
   drift, TQQQ beta, short-term reversal, volatility scaling, low-vol
   anomaly/volatility paradox, momentum/trend, and crash risk. There is no
   factor-model attribution (FF5 + momentum + vol) or alpha-vs-known-factors
   test; the main independence test is correlation with the old base. A
   strategy can pass that correlation test by being flat most of the time
   (time-of-day) or by being low-beta (winner-ensemble) without having a new
   return driver.

7. **Metric, window and status problems.** `exposure` is bar-weighted and
   misleading for overnight strategies: `time-of-day` shows 2.3% of intraday
   bars but is long ~30% of nights / ~54% of calendar time; `volume-orderflow`
   shows 100% “exposure” but only 0.75% of sessions in TQQQ. The originals use
   2017–2026 / 2021–2026 while the rebuilds use 2016–2023; the website compares
   different windows. Most `report.md` files say “paused / no result” while a
   `result.json` exists, and the status fields are stale (`pending_test`,
   `pending_audit`). This is a documentation-integrity problem: a reader cannot
   tell what was actually tested without opening `result.json`.

8. **No clean out-of-sample design choice.** The 26-strategy search itself is a
   multiple-testing exercise; the two strategies that beat TQQQ on the uniform
   window are the old base (Ratio froth) and a high-beta stop overlay
   (vol-scaled). The standalone rebuilds that pass their dev gates earn 4–22%,
   far below TQQQ. The batch's “winners” are selected on the same data used to
   design them; there is no clean holdout for the design choices, only for the
   frozen parameters.

### Does Ratio froth belong in a like-for-like comparison with standalone rebuilds?

**No.** It is not a standalone rebuild. It is the round-1 winner — 165-day QQQ
gate + 4% armed minute stop — plus a daily ratio filter. The report says “Base
(round-1 winner, unchanged)” at the top of its rules, and `strategy.py` has
`SMA_N = 165`, `STOP = 0.04`, `MA_FAST = 20`. The overlay only changes the
asset held on 21.5% of sessions. The base and stop do most of the work:

- base + stop, no overlay: 58.80% / 44.56% (10y);
- overlay alone, no stop: 60.15% / 53.31%;
- full: 69.50% / 39.11%;
- defensive BIL instead of QQQ: 73.26% / 39.11%.

The overlay alone adds 1.35 pp CAGR but worsens drawdown by 8.75 pp. The stop
adds 9.35 pp CAGR and cuts DD by 14.2 pp. The full headline is a joint
base+stop+overlay artifact, not a standalone ratio edge. The 69.50% is also a
2017–2026 10y number; on the uniform 2016–2026 window it is 62.21% / 36.65% /
1.43, still base-driven. The standalone ratio rebuild (`research/revisit/
ratio-pairs`) earns 18.96% dev / 20.42% full, about QQQ — that is the honest
like-for-like number for the ratio idea.

**Recommendation:** Ratio froth should be labeled “old base + overlay — not
comparable” and excluded from the standalone leaderboard, or shown in a
separate “legacy base” group with the old gate/stop disclosed. If it is
compared at all, compare it on risk-adjusted metrics at 1–10 bp with the
38,895× turnover and the ~1.5 pp-per-bp cost sensitivity disclosed, and use the
2016–2026 window, not the 2017–2026 10y window. Its “Leader” status is a
statement about the old base, not about the research idea.

### What would make the batch credible

- Re-run the two “winners” (Ratio froth, vol-scaled) with the old base and stop
  removed, and report the standalone number next to the legacy number.
- Treat the event studies with fewer than 40–50 events as underpowered and
  retire them without a headline CAGR.
- Pre-register the sign and threshold before the exploratory grid; report the
  full multiple-testing count, not just the selected variants.
- Add a factor attribution (FF5 + momentum + vol) or at least a 2×2
  extension × volatility control for the ratio froth, so the “froth” effect is
  not just low-vol/beta timing.
- Report exposure in capital-time as well as bar-weighted, and use the uniform
  2016–2026 window for every strategy in the comparison.
- Fix the stale status lines and state, for each strategy, whether the result
  is a frozen run or an exploratory pre-pause run.
