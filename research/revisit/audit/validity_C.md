# Research-validity audit — batch C

**Scope.** Seven rebuilds: `ml-classifier`, `ml-crash-overlay-winner`,
`opening-range-breakout`, `overnight-crash-filter`, `risk-parity-hrp`,
`ratio-pairs`, `stop-reentry-recovery`. This is a validity audit, not an
implementation audit. I did not edit strategy code, run a backtest, tune a
parameter, or commit anything.

**Method.** Read each rebuild's `report.md` plus `HYPOTHESIS.md` / `SPEC.md` /
`PROVENANCE.md` (and lower-case variants) where present, the relevant original
report under `research/agents*/`, and the parts of `strategy.py` needed to check
the stated rule. `result.json` and its diagnostics are used only as context and
as corroboration of the reports' own pre-registered tests, never as proof of a
mechanism. The reports are stale: all seven say “backtests paused / no result”
even where a `result.json` exists. I judged the hypothesis as written.

**Verdict key.** `sound` = mechanism, evidence, rule and economics all line up;
`plausible-but-weak` = mechanism is real but the specific rule is ad hoc and the
edge is small/unproven; `unsupported` = the cited evidence does not support the
rule, or the rule fails its own pre-registered test; `overlay-only` = the
“strategy” is economically a risk/vol/beta overlay or filter in disguise.

---

## Summary

| Strategy | Verdict | Mechanism | Key evidence problem | Standalone/overlay |
|---|---|---|---|---|
| `ml-classifier` | **plausible-but-weak** | K-means market regimes mapped to TQQQ/QQQ/BIL by each cluster's past 20-day forward return. | Regime literature supports regimes, not the 23-feature k-means → forward-return map; the result is QQQ-like (20.7% CAGR, Sharpe 0.81 vs QQQ 0.90), and the cluster-ordering test is not reported. | Standalone three-asset allocator; fully invested, QQQ/TQQQ beta. |
| `ml-crash-overlay-winner` | **overlay-only** | A walk-forward classifier of high 5-day TQQQ-vs-3×QQQ decay rotates TQQQ/QQQ/BIL. | The decay identity is real, but the TQQQ-state vs QQQ-state decay difference is only ~1–2 bp and insignificant (p=0.47); a simple 20-day vol rule earns Sharpe 1.13 vs 0.81. | Overlay: 13.5% TQQQ / 50.7% QQQ / 35.8% BIL; the ML is a volatility filter on QQQ beta. |
| `opening-range-breakout` | **unsupported** | Buy a failed breakdown of the 30-min opening range that reclaims ORL; target ORH, stop at sweep low, flat by the close. | The only rigorous cited ORB study finds the family fails costs; the reclaim is a practitioner pattern with no direct test; dev CAGR is −2.1% at 1 bp and −15.1% at 5 bp. | Standalone intraday QQQ event strategy; 0.5% risk/trade, low exposure. |
| `overnight-crash-filter` | **unsupported** | Long TQQQ overnight after up days; long QQQ intraday after negative gaps; size by a 3-sigma gap budget. | The cited “Day Destroys the Night” predictor is a ~7-year EWMA, not yesterday's sign; F1 t=0.23 and F2 t=−0.51, and the strategy is dominated by a static vol-matched TQQQ/cash mix. | Standalone in form, but a static overnight TQQQ beta harvest (31.5% calendar TQQQ at ~0.86 weight). |
| `risk-parity-hrp` | **overlay-only** | ERC QQQ/TQQQ sleeve with a contrarian vol-state budget and an own-equity drawdown brake. | QQQ/TQQQ correlation 0.999 makes ERC a 1.5× QQQ leverage choice, not risk parity; only 8 transient-spike events (<40), and corr 0.78 > 0.60. | Overlay: ~24% average budget on a 1.5× QQQ sleeve = ~0.36 QQQ beta; vol/DD overlay. |
| `ratio-pairs` | **plausible-but-weak** | TQQQ/QQQ ratio extension: froth→BIL, deep discount + turn→40% TQQQ, middle→90% QQQ. | Avellaneda–Zhang is an accounting identity; the ratio extension is 97.8% explained by QQQ extension + variance; dev CAGR 18.96% ≈ QQQ 18.91%, so the edge is a small cash/vol overlay. | Standalone in form, but ~90% QQQ core; QQQ beta + cash/vol overlay. |
| `stop-reentry-recovery` | **unsupported** | Buy TQQQ after a ≥3% intraday drop and ≥1 pp underperformance vs 3× QQQ, hold 3 sessions, 2% stop. | The excess condition conflates permanent decay/tracking error with temporary overshoot; 1 event in 8 years (2020-03-12 signal, entered and stopped on 2020-03-13), so the hypothesis is untestable. | Standalone event strategy in form; effectively empty (1 entry). |

No strategy in this batch is `sound`.

---

## 1. `ml-classifier` — plausible-but-weak

**1. Claimed mechanism and return driver.** Daily U.S. equity states cluster into
a few persistent regimes. A causal monthly-refit k-means on 23 short-horizon
features identifies the current regime; the best cluster by past 20-day forward
TQQQ return gets TQQQ, the second gets QQQ, the rest BIL. The claimed driver is
regime persistence plus cross-regime asset sorting, not a 165-day trend gate.

**2. Cited evidence.** Hamilton (1989) is a Markov-switching model of the
business cycle (GNP), not daily equity regimes. Guidolin–Timmermann (2007) is a
monthly multivariate regime-switching asset-allocation model; Nystrup et al.
(2015) is regime-based allocation with HMMs; Horvath et al. (2021) is Wasserstein
clustering. Together they support the *premise* that persistent regimes exist and
that regime information can help allocation. None of them validates this
specific rule: a 23-feature k-means, `k=3`, a 750-day window, a 20-day
open-to-open forward-return map, a QQQ middle asset, and monthly refits. The
report itself marks the exact features/mapping “Own design / no external
source.” The word “unsupervised” is also misleading: the clustering is
unsupervised, but the cluster→asset map is supervised by forward returns. That is
a citation-to-rule gap, not a fatal misapplication, because the report is honest
about the own-design parts.

**3. Falsifiable and pre-registered?** Yes. The report lists nine explicit
falsifiers (regime ordering, Sharpe vs QQQ, drawdown, correlation, one-episode
dependence, parameter fragility, placebo, cost fragility, assignment stability)
and a development-only test plan. This is the strongest part of the document.
The gap is follow-through: the result file reports the final portfolio metrics
but not the per-refit cluster forward-return ordering that falsifier 1 requires,
so the core mechanism test is not shown.

**4. Does the rule follow from the mechanism?** Partly. If regimes persist and
their forward-return ordering is stable, mapping the best cluster to TQQQ and
the second to QQQ is logical. But the ordering is estimated in-sample from the
same 750-day window used to fit the clusters; it can flip across refits. The
100% single-asset switch is a crude implementation: it turns a regime-ranking
problem into a binary beta choice. The 20-day forward horizon and weeks-long
holding are broadly consistent, but the universe (QQQ/TQQQ/BIL) is a beta ladder,
not a set of genuinely different regime exposures.

**5. Expected effect size after costs.** Costs are not the problem: 253 fills and
turnover 474 are modest, and the 1 bp / 5 bp / 10 bp CAGRs (context: 20.7% /
18.9% / 16.8%) stay positive. The problem is the level: the report's stated aim
was to “capture most of TQQQ's bull-market drift while cutting crisis exposure,”
but 20.7% CAGR is QQQ-like, not TQQQ-like (TQQQ 38.2% on dev). The 36.0% max DD
is also slightly worse than QQQ's 35.1%. The effect is a modest risk-profile
change, not the claimed TQQQ-drift capture.

**6. Standalone or overlay?** Standalone in form: a fully invested three-asset
allocator, no old-base gate. Economically it is still QQQ/TQQQ beta with a
regime sort; the result's 0.58 correlation with the 165-day baseline is at the
top of the report's expected 0.35–0.60 range. The exposure implication is that
the strategy is a fully invested equity-beta vehicle, not a diversifying return
stream.

**7. Known factors.** QQQ/TQQQ beta, volatility regime, momentum, and a
low-vol/trend sort. The cluster features are mostly returns, realized vol,
drawdown, EMA distance and RSI; the “regime” is largely a volatility/trend
bucket. The report's own exploratory table shows the stripped supervised model
was 19–31% CAGR with 64–74% DD; the new k-means improves DD but not the return
driver. The result is consistent with a QQQ-like beta sort, not a new premium.

**Spec/code check.** No material rule divergence. The code's cluster→asset map
matches §4.3 (best→TQQQ/BIL, second→QQQ/BIL, rest BIL), the 2-session
confirmation matches the report, and the 750/20/2 parameters match. The
“unsupervised” label is conceptual, not a code bug.

---

## 2. `ml-crash-overlay-winner` — overlay-only

**1. Claimed mechanism and return driver.** TQQQ's 3× daily reset makes its
return path-dependent: `log(TQQQ_T/TQQQ_0) ≈ 3 log(QQQ_T/QQQ_0) − 3 Σ r²`.
A walk-forward classifier predicts when the next five sessions will have
unusually large TQQQ-vs-3×QQQ decay; hold TQQQ when predicted decay is lowest
(rank < 0.15), QQQ in the middle (0.15–0.70), BIL when highest (≥ 0.70). The
claimed driver is the timing of leverage, not crash avoidance on a TQQQ base.

**2. Cited evidence.** Avellaneda–Zhang (2010) derives and tests the decay
formula; Cheng–Madhavan (2009) documents path dependence and daily re-leveraging;
the walk-forward/purge protocol comes from Arnott–Harvey–Markowitz and López de
Prado. Those sources support the *existence* and *size* of decay. They do not
support the claim that a 37-feature classifier can predict the next five days'
relative decay, nor the 15/70 rank thresholds, the 5-session minimum hold, or
the 25th-percentile label. The report marks the exact three-state rule “Own
test / no external source.” The deeper problem is that the label is
approximately `−3 × realized variance`: the “decay classifier” is a volatility
forecaster, and volatility is persistent. The cited identity is being used as a
prediction signal when it is an accounting relation.

**3. Falsifiable and pre-registered?** Yes. Eight explicit falsifiers, including
OOS AUC ≤ 0.55, no decay separation, placebo, single-episode dependence, and
10 bp costs. The report is unusually honest about the risk that the ML has no
skill and that a simple vol rule may capture the effect. The follow-through is
the problem: the report's results section is stale, but the run diagnostics
(context) contain the tests, and several of the pre-registered falsifiers fire
(decay separation, 10 bp cost, placebo).

**4. Does the rule follow from the mechanism?** Partly. The sign is logical:
low expected decay → TQQQ; high expected decay → BIL; middle → QQQ. The 5-day
horizon matches the label and the 5-session minimum hold. But the mechanism is
*relative* (TQQQ vs 3× QQQ), while the implementation is *absolute* (100% in one
asset). A pure decay trade would be long TQQQ / short QQQ or a relative-value
position; the long-only, 100% switch cannot isolate the decay premium and
instead takes QQQ beta risk. The report admits “The QQQ default keeps equity
beta.” The 15/70 thresholds and the immediate BIL exit are hand-set risk rules,
not implications of the decay formula.

**5. Expected effect size after costs.** The 1 bp result (context: 15.8% CAGR /
22.4% DD / 0.81 Sharpe) is a low-beta QQQ-like profile, not a leverage-timing
premium. At 10 bp it falls to 9.9% CAGR / 25.3% DD / 0.56 Sharpe. The 461 fills
and 795 turnover make the 5–10 bp sensitivity real. More importantly, the
diagnostics show the ML is dominated by a simple vol rule: `rv20` vol-only is
25.6% CAGR / 31.1% DD / 1.13 Sharpe, and `range20` is 29.0% / 36.3% / 1.20. The
“edge” is a volatility filter with extra steps.

**6. Standalone or overlay?** Overlay-only. The state shares are 13.5% TQQQ,
50.7% QQQ and 35.8% BIL; average gross leverage is 0.91. The return is mostly
QQQ beta, with a BIL/vol filter. The report's own risk section says a simple
realized-vol threshold may capture much of the effect; the diagnostics confirm
that it does, and better.

**7. Known factors.** TQQQ/QQQ beta, volatility/decay, vol timing. The
state-conditional decay test is the decisive one: the TQQQ-state vs QQQ-state
difference in realized 5-day decay is economically negligible (on the order of
1–2 bp, with the exact sign depending on whether 2016 is included) and
statistically insignificant (one-sided p=0.47). The classifier does *not*
separate favorable from unfavorable leverage; it separates high-vol from
low-vol. The random-state placebo 95th-percentile Sharpe is 1.09 vs the
strategy's 0.81, so the timing is not statistically distinguishable from random
states with the same frequencies.

**Spec/code check.** No material divergence. The code's `state_weights` is
0=QQQ, 1=TQQQ, 2=BIL; the state shares match the report's ~15/55/30. The
`decay_separation` diagnostic is the report's falsifier 4 and it fails.

---

## 3. `opening-range-breakout` — unsupported

**1. Claimed mechanism and return driver.** A brief break below the 30-minute
opening-range low that is reclaimed is a liquidity sweep: stop-loss sellers and
breakout shorts are filled, the trapped sellers cover, and price reverses toward
ORH before the close. The strategy buys QQQ at the reclaim, stops at the sweep
low, targets ORH, risks 0.5% of equity, and is flat overnight.

**2. Cited evidence.** The rule is the long-side mirror of a Build Alpha blog
post (“fade the false breakout”), a practitioner guide. The rigorous cited
paper, Fetna (2026, SSRN 7428398), is a pre-registered 225-cell study on sixteen
years of futures data that finds the ORB family does *not* survive realistic
costs (median gross edge −0.01 ticks; 155/225 cells within two ticks of zero;
the largest surviving cell fails a random-anchor control). That is evidence
*against* the ORB family, not for the reclaim variant. Pineda (2026) is cited
“abstract only; full text 403” and supports studying the retest, not this rule.
Zarattini–Aziz (2023) supports a different ORB (5-minute first candle, 10R
target) that the rebuild explicitly rejects. Holmberg et al. (2012) supports
conditioning ORB on volatility, not the failed-breakdown reclaim. The specific
rule has no direct academic test; the strongest support is practitioner lore.
This is a clear practitioner-only evidence problem, with the one high-quality
citation pointing the other way.

**3. Falsifiable and pre-registered?** Yes. Eight explicit falsifiers: mean R
≤ 0 at 1 bp, profit factor < 1.1, both sub-periods ≤ 0, random-entry placebo,
<100 events and bootstrap p > 0.10, correlation ≥ 0.60, neighbourhood sign flip,
and dependence on the 5 bp buffers/ORH target. The report is pre-registered and
honest that a negative result is acceptable. The result (context) fires
falsifier 1: dev CAGR is −2.1% at 1 bp, with 716 entries, 485 stops, 182 targets
and 49 EOD exits. At 5 bp it is −15.1% CAGR / 73.0% DD; at 10 bp −29.0% / 93.5%.

**4. Does the rule follow from the mechanism?** Partly. The reversal sign and
intraday horizon follow the liquidity-sweep story, and the 0.5% fixed-fractional
risk is a sensible implementation. But the “sweep” is inferred from a bar
pattern, not measured order flow; the 5 bp break/reclaim buffers, 30-bar window,
1R reward filter and ORH target are all own choices. The report's own
pre-pause table shows the first-30-minute direction had a much stronger
overnight edge (+0.235%, t=3.10) but was rejected for correlation; the chosen
residual rule is the weaker, untested variant. The rule is logically coherent
but not supported by the evidence.

**5. Expected effect size after costs.** The 716 entries and 2,865 fills create a
large cost burden. The 1 bp result is already negative, so the gross edge is
below zero before realistic spread/slippage; the 5 bp and 10 bp results are
catastrophic. A 0.5%-risk, 1R-target intraday rule needs a mean R well above the
cost per round trip; the observed mean R is not. This is a tiny-edge/high-
turnover idea, not a plausible standalone strategy.

**6. Standalone or overlay?** Standalone in form: intraday QQQ only, no old
base, flat overnight, 0.5% risk per trade. The exposure is low and the return
stream is structurally separate from the overnight TQQQ base (correlation
0.15 in the result). But “standalone” does not make it viable; it is a
standalone negative-edge event strategy.

**7. Known factors.** Intraday mean reversion / liquidity provision, QQQ beta,
and short-term reversal. A failed breakdown that reclaims is a classic
short-horizon reversal pattern; the report does not control for a random-entry
placebo in the result, and the negative 1 bp result is consistent with the
pattern being arbitraged or cost-dominated. The one strong signal in the
report's exploration was the overnight first-30-minute direction, which is a
known overnight-drift effect and was rejected for correlation, not because it
was weak.

**Spec/code check.** One divergence worth flagging: the code computes
`entry_px = cl[i]` (the reclaim bar's close) and uses that for the reward filter
and the 0.5% risk size, while the report says entry is the next bar's open and
risk is “entry − sweep low.” The actual fill can differ from the reclaim close,
so the risk budget and R multiple are measured from the wrong price. This is a
sizing/spec accuracy issue, not the reason the strategy loses (it loses at
1 bp too), but it should be fixed before any re-run.

---

## 4. `overnight-crash-filter` — unsupported

**1. Claimed mechanism and return driver.** The overnight and intraday blocks are
priced by different clienteles. The night continues an up day (long TQQQ
overnight when the QQQ session return is positive), and the day reverses a down
night (long QQQ intraday when the opening gap is negative). Positions are sized
so a 3-sigma gap costs a fixed fraction of equity; a 40% vol ceiling switches
off extreme regimes. The claimed driver is a block-conditional risk premium, not
the old 165-day trend exposure.

**2. Cited evidence.** Cliff–Cooper–Gulen (2008), Haghani et al. (2022), and
Lou–Polk–Skouras (2019) support the *unconditional* overnight premium and the
clientèle/block decomposition. Bondarenko–Muravyev (2021) and “Give me a break”
(2025) support the idea that the overnight premium is compensation for
overnight risk, which argues for *scaling* with overnight vol, not a 40% ceiling.
The core signal citation, “The Day Destroys the Night, Night Extends the Day”
(2023), is a Lou–Polk–Skouras working paper whose predictive variables are
*smoothed* (EWMA, roughly seven-year half-life) overnight and intraday
components: smoothed past overnight returns forecast intraday reversals, and
smoothed past intraday returns forecast overnight continuation. The strategy
uses the *sign of the previous session's* return/gap, a one-day conditioning the
paper does not test. That is a horizon/variable mismatch: a slow component
predictor is being used as a daily sign rule. The report's own provenance table
even says “smoothed past … returns,” which does not match the rule as written.

**3. Falsifiable and pre-registered?** Yes. F1–F6 are explicit: night mean after
up days > after down days with t ≥ 1.5; day mean after negative gaps positive
and greater than after positive gaps; correlation < 0.60; Sharpe/DD vs the old
base; vol-ceiling ablation; parameter plateau. The report says the legs are
tested separately before combining. The diagnostics (context) show both core
legs fail: F1 t=0.231 (up-day 13.68 bp vs down-day 11.04 bp, bootstrap
p=0.449); F2 t=−0.506 (negative-gap 0.98 bp vs positive-gap 3.48 bp, the
opposite sign). The report's results section is stale, but the pre-registered
tests are in the diagnostics.

**4. Does the rule follow from the mechanism?** Partly. The block decomposition
and the gap-budget sizing follow the literature. The daily sign conditioning does
not: the paper's predictor is slow, and the one-day sign effects are
insignificant or opposite in the data. The 40% vol ceiling is also in tension
with the risk-premium story (higher overnight vol should mean higher expected
overnight return, not a blanket switch-off at 40%). The night leg's conditional
edge is only ~1.2 bp/night over the unconditional mean, and the day leg's
negative-gap filter actually lowers the mean by ~0.8 bp/day. The rule does not
follow from the mechanism at the horizon it trades.

**5. Expected effect size after costs.** The report expected 25–40% CAGR,
Sharpe 0.9–1.3. The actual 1 bp result is 10.37% CAGR / 27.6% DD / 0.76 Sharpe;
5 bp is −0.9% and 10 bp is −13.4%. The 3,248 fills (406/year) and 3,336 turnover
make the edge smaller than realistic costs. The expected 25–40% is also
inconsistent with the sizing: the night leg is 785 days at ~0.86 weight, the day
leg 839 days at ~0.48 weight, and time in market is 39.7%; a ~0.28 average TQQQ
exposure times TQQQ's 36% dev CAGR gives roughly 10%, which is what the run
shows. The expected range was not derived from the rule.

**6. Standalone or overlay?** Standalone in form (two-block rotation, no old
base), but economically a static overnight TQQQ beta harvest. Calendar exposure
is 31.5% TQQQ at ~0.86 weight and 7.7% QQQ at ~0.48 weight. The diagnostics show
a static vol-matched TQQQ/cash mix earns 11.15% CAGR / 26.6% DD / 0.810 Sharpe,
which dominates the strategy's 10.37% / 27.6% / 0.762; a static 30% TQQQ mix
earns 14.82% / 35.9% / 0.795. The conditional filters add nothing.

**7. Known factors.** Overnight drift, TQQQ beta, volatility timing and
short-term reversal. The unconditional overnight premium is well documented and
is the main source of the return; the conditional up-day/down-gap signals are
not significant. The day leg is a short-term reversal bet, and the report itself
flags that the session mean is −26.9 bp/day in the 25–30% vol bucket. The
strategy is explained by static overnight beta plus a vol filter.

**Spec/code check.** No material rule divergence: the code's `night_cond`,
`vol_ceil=0.40`, `target_gap=0.04`, `day_scale=0.50` match the report. The
report's “~50% calendar time” is higher than the run's 39.7% time in market, and
the expected 25–40% CAGR is not implied by the sizing; those are modeling
inconsistencies, not code bugs.

---

## 5. `risk-parity-hrp` — overlay-only

**1. Claimed mechanism and return driver.** Standard risk parity sizes by 1/σ and
implicitly assumes a constant Sharpe ratio. This rebuild claims the conditional
Sharpe of the equity factor rises after a *transient* volatility spike and does
not rise in a *persistent* high-vol regime. It holds an ERC QQQ/TQQQ sleeve
(typically 75/25, ~34% vol), tilts the risk budget up when 20-day vol is high
relative to 120-day vol, damps the tilt when 120-day vol is high versus its
3-year median, and applies an own-equity drawdown brake.

**2. Cited evidence.** Asness–Frazzini–Pedersen (2012) and the ERC literature
support risk parity when assets have different Sharpe ratios and imperfect
correlation. Here QQQ/TQQQ correlation is 0.9995 (60-day average 0.99986), so
ERC is a pure leverage choice, and BIL is the only diversifier; the original's
HRP across QQQ/TQQQ/BIL put 99.99% in BIL. The central contrarian vol-state
budget is an *own hypothesis*: the report's own provenance says it is “supported
only indirectly by the volatility/return-timing literature — it is not a
published rule.” The cited French–Schwert–Stambaugh / Schwert / NBER evidence
for a positive short-horizon vol-return relation is weak and horizon-dependent,
while the vol-managed-portfolio literature (Moreira–Muir 2017) finds that
scaling *down* when vol is high improves Sharpe — the opposite sign. Cederburg
et al. (2020) is cited as counter-evidence. The report is honest about the
tension, but the rule's central sign is not supported by a robust published
result.

**3. Falsifiable and pre-registered?** Yes. Six explicit falsifiers: correlation
≥ 0.60, CAGR below BIL or Sharpe < 0.35, sign-flipped placebo/constant-budget
ablation equal or better, both sub-periods negative, forward 20-day return after
transient spikes not above unconditional (p > 0.10), and ±1-step sign flip. It
also says <40 transient-spike events means underpowered. The run (context)
reports 8 spike events, a 0.78 correlation with the old base, 5.70% CAGR, 18.5%
DD and 0.65 Sharpe. Falsifiers 1 and 6 fire; the status comment says the
placebo beats the tilt, so falsifier 3 fires too. The cited DIAGNOSIS.md is not
in the tree, so the controls are not fully auditable.

**4. Does the rule follow from the mechanism?** Weakly. ERC on two 0.999-
correlated assets is not risk parity; it is a 1.5× QQQ beta sleeve. The
contrarian tilt is a bet that short-horizon vol spikes mean-revert and are
followed by higher returns; that is a plausible but fragile empirical claim, and
the report's own exploratory table shows the pro-cyclical variants had 0.71–
0.83 correlation with the old base while the crude contrarian tilt reached 0.68.
The final signal reaches 0.78, worse than the crude tilt. The drawdown brake is
a generic path-dependent overlay, not a risk-parity mechanism. The rule does not
follow from a robust risk-parity or vol-timing result.

**5. Expected effect size after costs.** Costs are not the issue: 767 fills and
turnover 29.65 are low. The issue is the level: a 24.2% mean budget on a 1.5×
QQQ sleeve is ~0.36 QQQ beta, and 0.36 × QQQ's 18.9% dev CAGR is roughly 6.8%,
close to the observed 5.70%. The strategy is a low-beta QQQ vehicle with a
drawdown brake; there is no visible alpha from the contrarian tilt. The 8 spike
events are far too few to support the event-study claim (<40 is the report's own
underpowered threshold).

**6. Standalone or overlay?** Overlay-only. The “risk parity” label is
misleading: with QQQ/TQQQ correlation 0.999, the ERC sleeve is a leverage choice,
and the budget/brake is a volatility/drawdown overlay on QQQ beta. The exposure
implication is ~0.36 QQQ beta on average, with 660 days in the half-budget brake
state. It is not a diversifying risk-parity portfolio.

**7. Known factors.** QQQ beta, volatility timing, drawdown/trend. The 0.78
correlation with the old base is the highest in this batch and directly
contradicts the report's expected 0.30–0.55. The return is a low-beta QQQ mix;
the “contrarian” tilt is not the source (placebo beats it), and the drawdown
brake is a generic trend/DD rule. The economic content is leverage timing on one
equity factor, not risk parity across risk premia.

**Spec/code check.** Minor internal inconsistency: `HYPOTHESIS.md` says the
budget is in [0.15, 0.55], while `SPEC.md`/code clips to [0.03, 0.60]. The code's
tilt sign, persistence damper, ERC weights and brake thresholds match the
report. The larger issue is that the report's expected correlation and the
event-count power calculation are contradicted by the run.

---

## 6. `ratio-pairs` — plausible-but-weak

**1. Claimed mechanism and return driver.** `log(TQQQ/QQQ) = 2 log(QQQ) −
3 × realized variance + noise`, so the ratio's extension above its own 200-day
trend is a joint measure of how far QQQ has run and how little variance it took.
The strategy treats a high extension as “froth” (hold BIL), a deep discount with
the ratio turning up as “capitulation” (hold 40% TQQQ / 30% QQQ / 30% BIL), and
the middle as a QQQ core (90% QQQ / 10% BIL). A 20/60 variance-expansion ratio
(`stress > 1.75`) is a second kill switch.

**2. Cited evidence.** Avellaneda–Zhang (2010) is an accounting identity; it says
nothing about whether the ratio's extension predicts returns. Brunnermeier–
Sannikov (2014) is a theory of endogenous leverage and the volatility paradox; it
supports the *idea* that low measured risk can build fragility, but not a
200-day oscillator or the 0.20/−0.30 thresholds. Moreira–Muir (2017) supports
standing aside when variance expands; Cederburg et al. (2020) is the
counter-evidence. Cheng–Madhavan (2009), Adjusted Close and Trainor (2025)
support the drag arithmetic. The original `ratio-pairs` report's regression on
the 10-year daily sample reports R²=0.978 with a slope of 2.07 on QQQ's own
extension: the ratio extension is almost entirely QQQ extension plus variance.
The report itself says the 0.20/−0.30 thresholds are “anchored to the
exploratory dev buckets” — in-sample calibration. The specific timing rule is
own design, and the identity is being used as a predictive signal.

**3. Falsifiable and pre-registered?** Yes. Seven explicit falsifiers:
correlation ≥ 0.60, Sharpe ≤ QQQ, always-QQQ control beats it, placebo median
CAGR ≥ real, neighbourhood sign flip, 2022–23 DD > QQQ's 37%, and the
capitulation sleeve losing money or having <10 entries. The report says the
parameters were not fitted on the holdout, but they *were* anchored to dev
buckets, and the 7-parameter neighbourhood plus 22 variants is a large search.
The result passes the dev gates (18.96% CAGR / 34.59% DD / 1.11 Sharpe, corr
0.54), but the dev max DD is above the report's expected 26–33% band, and the
result file does not report the capitulation sleeve's aggregate P&L or entry
count, so falsifier 7 is not explicitly evaluated.

**4. Does the rule follow from the mechanism?** Weakly. The identity implies the
ratio is high when QQQ has risen a lot with low variance — i.e., a
momentum/low-vol state, not necessarily “froth.” Holding cash in that state is a
contrarian bet against QQQ momentum and low-vol, which is a known, often
losing, bet in 2016–2023. The 90% QQQ core means the rule is mostly a cash/vol
overlay on QQQ beta. The deep-discount 40% TQQQ sleeve is a bounded dip-buy; it
is not implied by the identity. The horizon (200-day detrend, weeks-long states)
is own; the universe (QQQ/TQQQ/BIL) is one factor; the sizing (90% QQQ core) is a
beta allocation, not a relative-value ratio trade.

**5. Expected effect size after costs.** The 1 bp result is 18.96% CAGR vs QQQ's
18.91% — a 0.04 pp CAGR difference — with a 2.7 pp lower DD and a 0.21 higher
Sharpe. Costs are manageable (288 fills, turnover 529; 10 bp still 16.06% CAGR).
The edge is a small risk-adjusted improvement from the froth/cash overlay, not a
new premium. The report's own expectation was 15–21% CAGR, 26–33% DD and 1.0–
1.15 Sharpe; the realized DD is outside the band. The “62% ratio froth” result
often cited is the *original* `ratio-froth` strategy (old 165-day base + 4% stop
+ ratio overlay), not this standalone rebuild; the standalone is QQQ-like.

**6. Standalone or overlay?** Standalone in form: it chooses QQQ/TQQQ/BIL and has
no old-base gate. Economically it is ~90% QQQ in the middle state, with cash in
froth/stress and a bounded TQQQ sleeve in capitulation. The exposure implication
is a QQQ beta vehicle with a cash/vol overlay; the result's 0.54 correlation
with the old base and 0.84 correlation with TQQQ (prior audit) are consistent
with that.

**7. Known factors.** QQQ beta, momentum/low-vol, variance/vol timing, and
short-term reversal (the capitulation sleeve). The ratio is 97.8% explained by
QQQ extension + variance, so the “leverage-cycle meter” is largely a repackaging
of QQQ trend and volatility. The ablations (context) show the stress rule is not
additive (no-stress 21.43% CAGR / 1.10 Sharpe vs 18.96% / 1.11), the TQQQ sleeve
adds about 1 pp CAGR (no-sleeve 17.94% / 1.10), and always-QQQ90/BIL10 is 17.32%
/ 0.91. The edge is a small cash/froth overlay, not a new leverage-cycle
premium.

**Spec/code check.** No material rule divergence: the `ext_ma=200`, `froth=0.20`,
`deep=−0.30`, `stress_hi=1.75`, 90/10 core and 40/30/30 capitulation weights
match the report. The process issue is more important: the result's
`tuning_note` says there were post-holdout bug fixes (“window end now includes the
last session; 2015 daily warm-up”) and the holdout “must be re-run by the lead.”
The 24.82% holdout in the file is therefore provisional, not a clean frozen-code
holdout.

---

## 7. `stop-reentry-recovery` — unsupported

**1. Claimed mechanism and return driver.** A 3× fund must reset its swap exposure
daily; after a large down day it sells into the close, and the mechanical selling
can push TQQQ below 3× QQQ. The temporary pressure reverses over the next 1–3
sessions. The strategy buys TQQQ after a session where TQQQ fell ≥3% and
underperformed 3× QQQ by ≥1 pp, 50% first and 100% after a recovery close, with
a 2% stop and a 3-session hold.

**2. Cited evidence.** Strasmore is a practitioner blog that explains the daily
rebalancing flow. Shum et al. (2016) documents larger tracking errors in volatile
periods; Avellaneda–Zhang (2010) documents path dependence; “Preying on
Leveraged ETFs” (arXiv 2608.03703) studies the Korean market and arbitrage around
the rebalance. These sources support the *existence* of rebalancing/tracking
error, not a predictable 3-session U.S. TQQQ reversal. The Korean paper has
limited external validity for U.S. TQQQ, and it studies arbitrage around the
flow, not a long-only next-open trade. The specific event is own design. The
report's own screen shows pure 4% dip-buying has correlation 0.09–0.30 but dev
CAGR −3% to +6.5%, i.e., no standalone edge; the new rule is a refined dip-buy.

**3. Falsifiable and pre-registered?** Yes. Eight explicit falsifiers: mean
3-session return ≤0, CAGR ≤ BIL or DD ≥ the old base, correlation ≥0.60, one-
episode dependence, no plateau, <100 events and bootstrap p > 0.10, the scale-in
is not additive, and the add-on is the whole edge. The report says the event
count should be actual entries, not raw signals. The run (context) has 1 event,
1 entry, 1 stop and 0 add-ons, all on 2020-03-12/13. Falsifier 6 (<100 events)
fires immediately; the hypothesis is untestable.

**4. Does the rule follow from the mechanism?** Weakly. The rebalancing-flow story
is plausible, but the signal `excess = r_TQQQ − 3 r_QQQ ≤ −1 pp` is mostly the
fund's permanent daily-reset drag/tracking error, not a temporary overshoot. The
drag is negative on high-vol days by construction (`≈ −3σ²`), so the condition
selects high-vol days where the decay is large, not necessarily days where the
price is temporarily depressed. The 2% stop is tighter than TQQQ's daily vol
(~3.5%), so the one trade stopped the same day. The 3-session hold and 50%→100%
scale-in are own rules, not implications of the flow mechanism.

**5. Expected effect size after costs.** There is no effect to size: 1 event in
2,012 sessions, and that event lost 2% (entry and stop on 2020-03-13). The 1.25%
CAGR is essentially BIL carry plus the one loss; costs are irrelevant. The
report expected ~100 events, which
is inconsistent with the signal's base rate. The strategy is effectively empty,
so the expected effect size is not plausible or measurable.

**6. Standalone or overlay?** Standalone event strategy in form (TQQQ/BIL, no old
base, 3-session hold). In practice it is an empty event study: 5 fills, 1 entry,
1 stop. It cannot be a standalone strategy until the event definition is fixed
to isolate the temporary component (e.g., a flow/timing proxy), and even then
the 2% stop/hold rules need rethinking.

**7. Known factors.** TQQQ beta, short-term reversal/dip-buying, volatility. The
one event is 2020-03-12, the most famous COVID crash/reversal; the result is a
single-episode artifact. The signal is a refined dip-buy, and the report's own
screen shows dip-buying has no standalone edge. The “overshoot” is not
distinguished from the permanent decay.

**Spec/code check.** No material rule divergence: `DROP=0.030`, `EXCESS=0.010`,
`HOLD=3`, `STOP=0.020`, `SIZE0=0.50`, `SIZE1=1.00` match the report. The failure
is the event definition, not the code.

---

## Cross-cutting

### 1. The citation-to-rule gap is the dominant failure

In all seven, the cited evidence is weaker than the rule it is asked to
support: the paper supports a *premise* — regimes exist, an overnight premium
exists, LETF decay exists, rebalancing flow exists, risk parity works across
asset classes — but not the specific daily sign, threshold, horizon or sizing
rule. The clearest cases:

- `ml-classifier`: Hamilton (business-cycle MS), Guidolin–Timmermann (monthly
  regime switching) and Nystrup (HMM allocation) support regimes, not a
  23-feature daily k-means with a 20-day forward-return map.
- `ml-crash-overlay-winner`: Avellaneda–Zhang is an identity, not a forecast;
  the “ML” is a volatility forecaster.
- `overnight-crash-filter`: “The Day Destroys the Night” uses a ~7-year EWMA
  component predictor, not yesterday's sign; the one-day conditioning fails
  F1/F2.
- `stop-reentry-recovery`: the rebalancing/tracking-error literature does not
  imply a 3-session reversal; the Korean evidence is external-validity-limited.

This is not just “the paper is old.” It is a mismatch of sign, horizon, variable
or universe. The reports are often honest about the own-design parts; the
problem is that the own-design part is doing the work, and the citation is
decoration.

### 2. Accounting identities are being used as predictive signals

`ml-crash-overlay-winner` and `ratio-pairs` both start from
`log(TQQQ/QQQ) = 2 log(QQQ) − 3V`. The identity is exact and useful for
understanding drag, but it does not say the ratio's extension predicts future
returns. In `ratio-pairs`, the original report's own regression gives R²=0.978
for QQQ extension + variance; the “leverage-cycle meter” is 97.8% a QQQ
trend/vol proxy. In `ml-crash`, the 5-day decay label is approximately
`−3 × realized variance`; a vol forecast is not a new leverage-timing premium.
The result is that both strategies are beta/vol allocations, not independent
return streams.

### 3. “Standalone” often means “a beta/vol overlay in disguise”

The exposure numbers tell the story:

- `ml-crash-overlay-winner`: 13.5% TQQQ / 50.7% QQQ / 35.8% BIL; average gross
  leverage 0.91. It is a QQQ beta vehicle with a vol filter.
- `risk-parity-hrp`: 24.2% mean budget on a 75/25 QQQ/TQQQ sleeve (1.5× QQQ
  beta) = ~0.36 QQQ beta, plus a drawdown brake. It is leverage/vol timing on
  one factor, not risk parity.
- `ratio-pairs`: 90% QQQ in the core state; the ratio states are a cash/vol
  overlay. The dev CAGR is 0.04 pp above QQQ.
- `overnight-crash-filter`: 31.5% calendar TQQQ at ~0.86 weight; the
  conditional filters are insignificant, so it is a static overnight beta
  harvest.
- `ml-classifier`: 100% invested in TQQQ/QQQ/BIL; a QQQ/TQQQ beta sort.

The reports' “no 165-day gate” framing is true but insufficient. Removing the old
gate does not create a new premium if the replacement is another beta/vol rule.

### 4. Thin or empty events and underpowered tests

- `stop-reentry-recovery`: 1 event in 2,012 sessions. The hypothesis cannot be
  tested; the one trade lost.
- `risk-parity-hrp`: 8 transient-spike events, below its own 40-event power
  threshold; the central event study is underpowered.
- `ml-crash-overlay-winner`: the decay separation is only ~1–2 bp and
  insignificant (p=0.47); the core mechanism test fails.
- `overnight-crash-filter`: F1 t=0.23 and F2 t=−0.51; both conditional legs
  fail.
- `opening-range-breakout`: 716 entries, but the mean R is negative at 1 bp; the
  sample is not thin, the edge is absent.
- `ml-classifier`: 253 fills, but the result is QQQ-like; the cluster-ordering
  test is not reported.

The reports deserve credit for pre-registering falsifiers. The problem is that
several falsifiers fire and the reports were not updated to say so.

### 5. Cost fragility is concentrated in the high-turnover ideas

`overnight-crash-filter` (3,248 fills; 5 bp −0.9%), `opening-range-breakout`
(2,865 fills; 5 bp −15.1%) and `ml-crash-overlay-winner` (461 fills; 10 bp 9.9%)
have edges that are small relative to realistic costs. The 1 bp headline is not
a realistic cost for hundreds to thousands of fills per year; the 5 bp results
are the more honest test. `ratio-pairs` and `ml-classifier` are less
cost-sensitive (288 and 253 fills), but their edges are small for a different
reason: they are beta/vol allocations.

### 6. Missing same-exposure/static benchmarks

The reports usually compare to TQQQ buy-and-hold, QQQ, BIL and the old 165-day
base. They rarely compare to a *static mix with the same exposure*:

- `overnight-crash-filter`: a static vol-matched TQQQ/cash mix earns 11.15% /
  26.6% / 0.810 vs the strategy's 10.37% / 27.6% / 0.762.
- `ml-crash-overlay-winner`: the state-share static mix earns 16.83% / 34.2% /
  0.880; QQQ 100% earns 18.80% / 37.3% / 0.896; the strategy's 15.80% / 22.4% /
  0.813 is a lower-beta profile, not a return premium.
- `risk-parity-hrp`: the 24% budget × 1.5 beta is consistent with the 5.7% CAGR;
  a static low-beta QQQ mix is the right comparator.
- `ratio-pairs`: the always-QQQ90/BIL10 ablation is 17.32% / 33.98% / 0.906;
  the ratio states add ~1.6 pp CAGR and ~0.2 Sharpe, not a new premium.

Without the same-exposure benchmark, a lower return is often just lower beta,
and a higher Sharpe is often just a cash buffer.

### 7. In-sample threshold selection and post-hoc changes

Most “primary” parameters are round numbers chosen with knowledge of the dev
sample: `ratio-pairs` 0.20/−0.30/1.75 from dev buckets; `opening-range` 30 min /
5 bp / 30 bars / 1R; `ml-crash` 15/70/5-day; `overnight` 40% ceiling / 4% gap
budget; `risk-parity` 0.35/0.20/0.70. The ±1-step neighbourhoods are reported in
some cases, but a plateau of similar signs is not the same as out-of-sample
validity. More seriously, `ratio-pairs` had post-holdout bug fixes (window end,
2015 warm-up) and its holdout “must be re-run by the lead”; the 24.82% holdout
in the file is provisional. Once a holdout has been inspected and the code
changes, it is no longer a clean single-shot test.

### 8. The two “winners” are not standalone evidence for the rebuild thesis

The two strategies that beat TQQQ on the uniform window are `ratio-froth`
(~62% CAGR) and `vol-scaled-crash-stop` (~51%). Neither is a standalone rebuild
in this batch:

- `ratio-froth` is the *original* old 165-day QQQ/TQQQ base plus the 4% armed
  stop plus a ratio overlay (original report: 10y 69.50% / 39.11%, 5y 63.74% /
  26.85%). Its high CAGR is the old base + TQQQ beta, not the ratio signal
  alone. The standalone rebuild is `ratio-pairs`, which earns 18.96% dev /
  24.82% holdout, essentially QQQ.
- `vol-scaled-crash-stop` is always-long TQQQ with ATR/inverse-vol sizing and a
  stop; the prior audit puts its correlation with the old base at 0.71, above
  the rebuild's own 0.60 limit. It is a better-managed TQQQ exposure, not a new
  independent edge.

So the apparent “the rebuilds underperform but two beat TQQQ” result is
consistent with the shared base still doing most of the work. The standalone
research question — is there a new, independent return driver? — is answered
“not in this batch.” The best standalone result (`ratio-pairs`) is a QQQ-like
cash/vol overlay; the best risk-adjusted overlay (`ml-crash`) is a vol filter;
the rest are unsupported or empty.

---

### Bottom line for this batch

- **Keep as research leads, not as validated strategies:** `ratio-pairs`
  (small cash/vol overlay on QQQ; needs a clean re-run of the holdout after the
  code fix) and `ml-classifier` (regime sort; QQQ-like, no return edge).
- **Treat as overlays, not standalone premia:** `ml-crash-overlay-winner`
  (vol filter; simple `rv20` dominates) and `risk-parity-hrp` (1.5× QQQ
  leverage choice with a DD brake).
- **Do not promote:** `opening-range-breakout` (negative at 1 bp, catastrophic
  at 5 bp), `overnight-crash-filter` (F1/F2 fail; static vol-matched mix
  dominates), `stop-reentry-recovery` (1 event; untestable).
