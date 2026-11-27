# Research-validity audit — batch B

**Scope.** Seven rebuilds: `event-risk-overlay`, `gap-capitulation-reversal`,
`gap-fill-fade`, `intraday-mean-reversion`, `intraday-momentum`,
`intraday-seasonality`, `letf-rebalance-flow`.

**Method.** Read `report.md`, `HYPOTHESIS.md`/`hypothesis.md`,
`SPEC.md`/`spec.md`, `PROVENANCE.md`/`provenance.md`, the original reports where
the rebuild's characterisation mattered, `strategy.py` only far enough to check
the stated rule, and `result.json` plus the diagnostic/tuning JSONs as context.
No backtest was run, no code was edited, nothing was tuned. `report.md` status
lines are treated as stale where they contradict `result.json`; the hypothesis
as written is what is judged.

**Headline.** None of the seven is `sound`. Two are only weak-but-testable
(`gap-capitulation-reversal`, `intraday-mean-reversion`), one is a real effect
with the wrong mechanism attributed (`intraday-seasonality`), one is a
calendar-beta overlay (`event-risk-overlay`), and three fail their own
pre-registered tests (`gap-fill-fade`, `intraday-momentum`,
`letf-rebalance-flow`).

## Summary table

| Strategy | Verdict | Mechanism (as claimed) | Key evidence problem | Standalone / overlay |
|---|---|---|---|---|
| `event-risk-overlay` | **overlay-only** | Negative open→close drift on the monthly expiry session from dealer gamma roll/covered-call hedging; own the cycle, skip the expiry session. | The strategy monetises the *complement* (long TQQQ 4 days before + 2 after), so 28.6% TQQQ beta supplies almost all the return; the event premium is ~1%/yr and the all-session permutation p=0.245. | Calendar de-risking overlay on TQQQ in disguise; 28.6% TQQQ / 71.4% BIL. |
| `gap-capitulation-reversal` | **plausible-but-weak** | A quiet, 20-day-oversold QQQ capitulation is a liquidity event that reverses over 3 sessions; buy TQQQ (QQQ in high vol) at the next open. | Strong raw event study (n=30, +6.03%, t=2.89) but the 1.2x volume cap is a knife-edge (1.0→2.80% CAGR, 1.5→1.25%), the actual trades average +2.37% because 20/24 are QQQ, and the event-low stop was removed after the holdout (4.18%→8.30%). | Standalone, very low exposure (3.9% in QQQ/TQQQ, 96% BIL). |
| `gap-fill-fade` | **unsupported** | A small gap-up in a weak, stressed tape is a temporary imbalance; if the first 30 minutes fail, short QQQ at 10:01 to the prior close. | n=25, +5.6 bp/event, t=1.01, bootstrap p=0.15, 95% CI includes zero; the no-confirmation variant is *better* (1.52% vs 1.43%); 10 bp CAGR 0.79%, below BIL. | Standalone intraday short, flat overnight; 25 events in 8 years. |
| `intraday-mean-reversion` | **plausible-but-weak** | A ≥3% intraday QQQ capitulation is a liquidity shock; the next session's open→close carries a liquidity-provision premium; buy TQQQ next open, sell before the close. | 88 events, +0.99%/event, p=0.068, 95% CI [−0.26%, +2.09%]; 2020-21 +2.61% vs 2022-23 −0.49%; the 3.0% threshold is a peak, not a plateau. | Standalone, 4.35% TQQQ / 95.6% BIL, never overnight. |
| `intraday-momentum` | **unsupported** | Weeks with a strong overnight-minus-intraday spread and a strong first hour have persistent time-of-day drift; a weekly 3-state TQQQ/QQQ/BIL ladder exploits it. | The code's own diagnostics show the first-hour signal is *inverted* (forward 5-day −1.2 bp when true vs +68.8 bp when false) and the TQQQ state has the lowest forward return (+5.0 bp vs +36.5 bp for QQQ); correlation 0.616 fails the <0.60 gate; DD 64% and CAGR 13.5% are dominated by QQQ. | Standalone in name only: 85% equity (66% QQQ, 16% TQQQ), 18% BIL; a QQQ-beta/leverage overlay. |
| `intraday-seasonality` | **plausible-but-weak** | A >1% intraday decline makes the close temporarily too cheap because LETF rebalancing sells into it; buy the close, hold one session. | 275 events, +70 bp, t=2.39, p=0.009, but the overnight leg earns nothing (`exit=next_open` −0.38% CAGR, +5.6 bp/event) while the full 23-hour hold earns 21.8%; the edge is next-day intraday dip-buying, not close flow. The −1.0% threshold is the peak of the grid, and 10 bp CAGR is 7.6%. | Standalone low-exposure (11.7% TQQQ, 88% BIL) but a 23-hour TQQQ beta timing book. |
| `letf-rebalance-flow` | **unsupported** | A large QQQ-underperformance-vs-SPY day is temporary Nasdaq-specific LETF/options flow pressure; buy TQQQ next open and hold 3 sessions. | The base 13.2% CAGR sits at the 72nd percentile of the random-entry placebo distribution (median 6.5%, z=0.53); hold=3 is a knife-edge (h1 −0.3%, h2 +0.3%, h3 13.2%); the QQQ-beta version has a similar Sharpe (0.56 vs 0.52); the absolute QQQ signal is *better* (15.7% vs 13.2%). | Standalone high-beta event book; ~22% TQQQ exposure, 41.8% DD, 99x/yr turnover. |

---

## 1. `event-risk-overlay`

### 1.1 Claimed mechanism and return driver
The monthly option-expiry session (third Friday, holiday-rolled) carries a
negative open→close drift because dealer gamma rolls off and covered-call
writers roll exposure into the same print. The rebuild owns TQQQ in the six
sessions around expiry (`expiry−4 … expiry−1` and `expiry+1 … expiry+2`) and
sits in BIL on the expiry session. The return driver is therefore TQQQ beta on
28.6% of sessions plus the avoided expiry-day drift.

### 1.2 Cited evidence
- The primary source is a **practitioner blog** (QuantifiedStrategies) claiming
  SPY expiry-day returns of −0.77% average, 51.4% win rate, 1993–2024. That is
  a blog backtest, not a peer-reviewed study.
- The FMA 2025 paper is cited for "expiry-cycle flow … rollover on the third
  Friday and the following Monday." The report itself says it was "read as
  excerpt only." The paper's subject is **option returns on the expiration
  rollover day**, not the equity index's expiry-Friday open→close drift. The
  instrument and the day do not match the rule.
- Quantpedia's expiry-week page is cited as "partial: opposite sign to the
  day-level claim." The report is honest that the external evidence is mixed,
  but that means the negative expiry-session drift rests almost entirely on the
  author's own dev measurement (96 events).
- The own dev measurement is strong in isolation: −83.9 bp on expiry vs
  +14.6 bp on other days; expiry vs other Fridays −106.2 bp, t = −2.72; same
  sign in all three dev sub-periods. That is a real in-sample fact.

**Assessment:** the *fact* is supported by the author's own data, but the
*causal story* is practitioner-level and the cited paper supports a different
event. The strategy does not trade the fact anyway (see 1.3).

### 1.3 Falsifiable and pre-registered?
Yes. F1–F5 are explicit, with 13 variants, structural placebos, a permutation
test and a month bootstrap. The result reports all five: F1 true, F2 **false**
(dev max DD 39.0% > 30%), F3 true (corr 0.342), F4 true, F5 true. Status
`rejected`. The report's "backtest paused / no result" header is stale.

### 1.4 Does the rule follow from the mechanism?
No. The mechanism is a **negative** expiry-session drift, which is a short-side
effect. `bt.py` is long-only, so the rebuild monetises the complement: long the
cycle, flat the expiry session. That is not the same trade. The report admits
this in §2 and §11: "the rebuild is a proxy, and that is the single biggest
reason it might not clear F1." The rule is a calendar filter on TQQQ exposure,
not a test of the expiry-day flow.

### 1.5 Effect size after 1 bp costs and realistic turnover
The report's own attribution is the key number: "the avoided expiry day
(≈ −84 bp × 12 = +1.0%/yr of relative edge)" (§9). The rest of the 26.9% dev
CAGR is TQQQ beta on 576 of 2,012 sessions. The result's reported turnover is
2,101x over eight years (~263x/yr), a 1 bp cost base of ~2.6 pp/yr. That is
several times the ~1%/yr the report attributes to the event itself, so the
event is not paying for its own trading; the beta is. At 5 bp the CAGR is
22.7%, at 10 bp 17.7%, and the max DD rises to 42.7%. The strategy survives
costs only because the gross return is high-beta, not because the event premium
is large.

### 1.6 Standalone or overlay?
**Overlay-only.** 28.6% TQQQ / 71.4% BIL; 26.9% dev CAGR vs TQQQ's 36.2%;
the month bootstrap's 5th-percentile CAGR is 12.1%, i.e. even the bad case is a
positive TQQQ-beta outcome. The permutation test is the decisive diagnostic:
in-window mean 0.312%/session vs random 0.207%, p = 0.245. The calendar
selection is not statistically distinguishable from a random 576-session
TQQQ book. The strategy is a calendar de-risking overlay on an existing TQQQ
long, not a standalone flow strategy.

### 1.7 Known factors
TQQQ beta, the OpEx calendar anomaly, month-of-year, and the 2020/2022 regime.
The 2022 dev year is −28.2% while the 2016/2019/2020 years are +49.5/+48.5/
+60.1%, exactly the profile of a levered beta book.

### 1.8 Report vs code
The code matches the stated window and vol cap. The only material divergence is
the stale report status ("SPEC FROZEN, BACKTEST PAUSED") against a
`result.json` with a full dev run and `status: rejected`. The report's §9
prediction of 8–20% CAGR is below the actual 26.9%; the report attributes the
gap to beta, which is correct.

---

## 2. `gap-capitulation-reversal`

### 2.1 Claimed mechanism and return driver
A large QQQ decline (close ≤ −2% or low ≤ −3% vs prior close) that occurs while
QQQ is already 20-day oversold (≤ −3%) and on below-average volume (≤ 1.2x the
prior 20-day average) is a liquidity/positioning event, not an information
event. It reverses over three sessions. The rule buys TQQQ at the next open
(QQQ if 20-day vol > 30%) and holds three sessions, with an event-low stop and
an 8% hard stop.

### 2.2 Cited evidence
- **Cox & Peterson (1994)** supports short-term reversals after large one-day
  declines and warns that part of the effect is bid–ask bounce. That is a
  reasonable citation for the 3-session horizon, but the paper is about
  individual stocks, not an index or a 3x ETF; the application is an
  extrapolation.
- **Campbell–Grossman–Wang (1993)** and **Conrad–Hameed–Niden (1994)** predict
  the **opposite** volume sign: high-volume declines are the liquidity-driven
  ones that reverse; low-volume declines are more likely information-driven.
  The rebuild's core condition is low volume. The report explicitly flags this
  as counter-evidence and treats the sign as a hypothesis. That is honest, but
  it means the load-bearing rule contradicts the cited theory.
- **Llorente et al. (2002)** says the volume–return sign is conditional on
  whether volume is informed or liquidity-driven; it does not establish a
  low-volume reversal for the index. It is used correctly as a "sign unknown"
  caveat, not as positive support.
- **Moreira–Muir (2017)** is used for the TQQQ/QQQ vol switch; the paper is
  about inverse-variance scaling, not a 30% threshold switch. Loose mapping.
- **Kaminski–Lo (2014)** is general support for stops; it does not justify the
  specific event-low stop or the 8% hard stop.
- The **own dev event study** is the real evidence: quiet-oversold events
  n=30, 3-session TQQQ mean +6.03%, t=2.89, bootstrap p=0.001; heavy-volume
  events n=58, mean −0.47%, t=−0.34. The volume split is strong in this sample.

**Assessment:** the citation set is honestly assembled, but the central
volume sign is counter to the two classic papers and rests on 30 in-sample
events. That is a legitimate exploratory finding, not a validated effect.

### 2.3 Falsifiable and pre-registered?
Nominally yes: 23 variants, 8 falsifiers, pre-registered base parameters. But
the final `strategy.py` is **not** the pre-registered rule: `PARAMS` has
`event_low_stop=False`, changed on 2026-11-27 after the holdout, with the
comment "POST-HOLDOUT, dev-only evidence." The pre-registered rule (stop on)
made 4.18% CAGR / 12.49% DD / 0.576 Sharpe; the tuned rule makes 8.30% /
10.26% / 0.877. The pre-registered falsifier 6 said removing the event-low stop
must not improve CAGR by more than 2 pp; it improved by 4.1 pp. The
pre-registration did not authorize flipping the stop off after seeing the
holdout and re-running it; it called for re-specification or rejection. The
final `result.json` presents the post-hoc rule as the passed strategy.
The result also omits the pre-registered sub-period table (2016-19, 2020-21,
2022-23), so falsifier 3 is not adjudicated in `result.json` (the tuning file
does show 2.6/12.6/16.1 for the tuned rule).

### 2.4 Does the rule follow from the mechanism?
Partially. The 3-session hold follows from "the reversal takes several
sessions"; the next-open entry follows from the overnight/next-open literature;
the event-low stop is a coherent "absorption failed" thesis. But the 20-day
oversold condition is a regime/trend proxy, and the volume sign is the
opposite of the standard liquidity story. The rule is internally coherent with
the author's hypothesis; the hypothesis is the weak link.

### 2.5 Effect size after 1 bp costs and realistic turnover
The raw event study is large: +6.03% per 3-session TQQQ event. But the strategy
does not capture that: 20 of 24 trades are QQQ (because `vol20 > 30%` on most
events), and the actual trade mean is +2.37% (QQQ +2.63%, TQQQ +1.05%). The
8.3% dev CAGR on 3.9% exposure is plausible, and costs are small (turnover
133x total, ~16.6x/yr; 1 bp→10 bp costs 1.18 pp). The problem is not costs; it
is that the headline event study overstates the tradeable edge by ~2.5x and
the sample is 24 trades.

The neighborhood is a knife-edge, not a plateau:
- `rvol_max = 1.0` → 2.80% CAGR; **1.2** → 8.30%; `1.5` → 1.25%.
- `no_volume` ablation → 1.67% CAGR / 32.8% DD.
- `event_low_stop=True` (pre-registered) → 4.18% CAGR; `False` → 8.30%.
- `no_oversold` → 9.11% CAGR (better than the base), so the oversold filter is
  not adding return; it is changing the event set.
This is not a robust parameter region.

### 2.6 Standalone or overlay?
Standalone, very low exposure: 3.9% of sessions in QQQ/TQQQ, 96% BIL. It is not
a filter on another strategy. As an overlay it would add a small long after a
capitulation; as a standalone it is a low-CAGR diversifier, as the report
anticipates.

### 2.7 Known factors
Short-term reversal, volatility-managed exposure (the TQQQ/QQQ switch), the
2020/2022 bear-market rebound, and TQQQ beta. The quiet-volume condition is
plausibly a proxy for the volatility/regime state; the 20-day oversold is a
trend/mean-reversion factor. The 2022 cluster (15 of 30 events) is a
bear-market rebound, not a generic liquidity effect.

### 2.8 Report vs code
- `report.md` §4 says "event-low stop on"; `strategy.py` `PARAMS` has it off.
- `result.json` has no sub-period block despite the pre-registered falsifier.
- The report says "30–50 events over 8 years"; the result has 30 event dates,
  24 trade starts.
- The event study uses TQQQ for every event, while the strategy uses QQQ for
  20/24 trades. That is a material mismatch between the evidence and the rule.

---

## 3. `gap-fill-fade`

### 3.1 Claimed mechanism and return driver
A small opening gap-up (+0.10% to +0.75%) in a weak, stressed tape (prior close
below the 10-day SMA, 5-day return negative, 20-day vol above its 1-year
median) is a temporary overnight order imbalance. If the first 30 minutes
confirm failure (r30 < 0, price below the open, gap still open), short QQQ at
10:01, target the prior close, stop at the opening-range high (0.2–1.5%),
time-stop at 11:30. The return driver is the intraday gap fill, not TQQQ
overnight drift.

### 3.2 Cited evidence
- The size split (small gaps fill, large gaps continue) is supported by a mix of
  **2026 practitioner/data studies** (MPM Markets, Steady Turtle, Open Market
  Journal, thetrading.tools) and one low-tier journal (IOSR 2019). These are
  descriptive fill-rate studies, not net-P&L tests.
- The MPM study itself says "no reliable edge after costs"; the Loomi study
  cited in the rejected table says three of four gap-size buckets lose after
  1 point of costs and **small gaps are the worst**. That is direct
  counter-evidence to the rule, not support.
- **Grant–Wolf–Yu (2005)** finds intraday reversals after **large** opening gaps
  in S&P 500 futures 1987–2002, stronger after positive gaps, with profits
  reduced by a bid–ask proxy. The rebuild fades **small** gaps in QQQ; the
  paper's size bucket and universe do not match.
- **Aiche–Cohen–Griskin (2024)** finds positive gaps **drift** (continuation);
  the **Price Gap Anomaly (2020)** paper finds prices move in the gap direction
  on the gap day and no evidence gaps always fill. Both are cited as support,
  but both point to continuation, not fade.
- The 10:00 confirmation, OR-high stop, 11:30 time stop and 10% vol target are
  own-test choices; the report admits this.

**Assessment:** the peer-reviewed evidence mostly supports continuation or
fades of *large* gaps; the small-gap fade is supported by practitioner fill
statistics and contradicted by the practitioner P&L study the report itself
cites. This is a citation that supports a different effect.

### 3.3 Falsifiable and pre-registered?
Yes: 8 falsifiers, a 23-variant neighborhood, placebos and a bootstrap. But the
result fails the first falsifier: n=25, mean +5.56 bp after 1 bp, t=1.01,
bootstrap p=0.152, 95% CI [−5.2 bp, +16.0 bp]. The pre-registered rule says
"t < 1.5, or bootstrap 95% CI includes zero" → reject. The result also fails
falsifier 2: the no-confirmation variant makes 1.52% CAGR vs the primary 1.43%,
and the random-entry placebo makes 1.32% with lower DD. The status is still
"pending", not "rejected".

### 3.4 Does the rule follow from the mechanism?
Partially. The direction (short a failed gap-up) and the target (prior close)
follow from the "temporary imbalance" story. But the mechanism is about
*small gaps filling*, which is a high-probability/low-payoff event; the strategy
needs the payoff after costs to be positive, and the fill-rate evidence does not
establish that. The first-30-minute confirmation is a momentum filter
(short-term continuation), which is in tension with the reversal thesis: the
strategy is short after the price has already moved down for 30 minutes, not
short into the initial gap. The OR-high stop is a sensible invalidation level.

### 3.5 Effect size after 1 bp costs and realistic turnover
The edge is tiny: +5.6 bp per event, 25 events over 8 years (~3/yr, not the
20–40/yr the report expects). The dev CAGR is 1.43% at 1 bp, 1.15% at 5 bp,
0.79% at 10 bp; BIL alone made 1.39% over the dev window. At 10 bp the strategy
is below cash. Turnover is 57x total (~7.1x/yr), so costs are not the main
problem; the gross edge is simply too small and too imprecisely estimated.

### 3.6 Standalone or overlay?
Standalone intraday short, flat overnight, 25 events. It is not a filter on
another base, but it is also not a viable standalone return stream at this
event count. The original report's conclusion was that "every standalone gap
strategy fails" and "the only way to use the gap signal is as an overlay on an
overnight TQQQ position" — the rebuild tries the standalone short and confirms
the original's negative result.

### 3.7 Known factors
Short QQQ beta, the opening-gap anomaly, intraday reversal, and short-vol
negative skew. The 76% win rate with a small average win is the classic
short-vol profile: many small gap fills, occasional stop-outs. The
first-30-minute confirmation is a short-term momentum filter, and the edge may
be a microstructure mean-reversion effect rather than a flow effect.

### 3.8 Report vs code
- The report says "expect roughly 20–40 shorts a year"; the result has 25 over
  eight years.
- The report says "Sharpe above 0.5, win rate above 55%"; both pass (0.94,
  76%), which shows why those gates are too weak: the t-stat and CI are the
  binding tests and they fail.
- The report's `main()` is gated by `REVISIT_RUN=1`, but `result.json` exists,
  so the run happened despite the "design only" status.
- The code's entry skip uses the 10:00 close (`closes[e-1]`) rather than the
  10:01 fill; that is a causality fix, but it means the actual fill can be
  below the prior close even when the signal passes.

---

## 4. `intraday-mean-reversion`

### 4.1 Claimed mechanism and return driver
A ≥3% intraday QQQ drawdown (minute close vs prior session close) is a
liquidity shock. The forced selling is not finished by the close, but the
**next session's open→close** carries a positive liquidity-provision premium.
Buy TQQQ at the next open, sell before the close, hold BIL otherwise; never
overnight.

### 4.2 Cited evidence
- **Nagel (2012), "Evaporating Liquidity"** is a good citation: short-term
  reversal returns are compensation for liquidity provision and spike in
  turmoil. The event is a turmoil event, so the mechanism is plausible.
- **Lou–Polk–Skouras (2019)** is a **cross-sectional** overnight/intraday
  "tug of war" paper; it documents that different strategies earn their premia
  overnight vs intraday. It does not establish an event-time next-session
  reversal after a drawdown. The report uses it for "the reversal is
  concentrated across the overnight/intraday boundary" — a scope stretch.
- **Gao–Han–Li–Zhou (2018)** is same-day intraday momentum (first half-hour →
  last half-hour). The report uses it to justify "intraday moves continue
  within the session, so do not buy the dip intraday." That is a reasonable
  use, but the paper's effect is continuation, not the next-session reversal
  the strategy trades.
- The next-session open→close rule is own-test. The original report's own
  evidence is the source: after a ≥3% drawdown in a **165-day bull regime**,
  the rest of the day is weak (+0.13%), the overnight gap is negative
  (−0.69%), and the next session's open→close is +1.17% TQQQ. The rebuild drops
  the regime gate.

**Assessment:** the liquidity-provision interpretation is well cited, but the
specific timing (next open → next close) is an untested extrapolation, and the
original evidence was conditional on a bull regime that the rebuild removes.

### 4.3 Falsifiable and pre-registered?
Yes: P0–V12 and 7 falsifiers, with explicit status rules (CAGR > 0, corr < 0.60,
cluster-bootstrap p < 0.10). But the preliminary evidence used a 5-minute event
definition (84 events, +1.346%), while the strategy uses 1-minute closes (88
events, +0.99%); the `result.json` is a mix of corrected event study and stale
`info` (109 event dates including 2024–26). `DIAGNOSIS.md` is candid that the
reporting bug produced a degenerate p=0.0 and that the corrected p is 0.068.

### 4.4 Does the rule follow from the mechanism?
Partially. If the liquidity premium is realised in the next session's
open→close, the rule is exactly right. But the mechanism citations are about
cross-sectional reversal and overnight/intraday decomposition, not about a
one-session event-time bounce. The original's effect was conditional on the
165-day bull regime; the rebuild's own 2022-23 mean is −0.49%, which suggests
the regime condition mattered. The rule is a reasonable expression of the
hypothesis; the hypothesis is not strongly identified.

### 4.5 Effect size after 1 bp costs and realistic turnover
88 events, mean +0.99% per event, vs an unconditional next-session mean
of +0.085%. 11.31% dev CAGR / 31.47% DD / 0.576 Sharpe at 1 bp; 9.36% at 5 bp;
6.97% at 10 bp. Turnover ~82x/yr, so costs take ~0.5 pp per bp. The effect size
is plausible but the statistical power is low: p=0.068, 95% CI [−0.26%,
+2.09%], and the 2020-21 sub-period is +2.61% while 2022-23 is −0.49%. Drop the
spring-2020 cluster and the mean falls to +0.37%. This is a real but fragile
event premium, not a tiny edge.

### 4.6 Standalone or overlay?
Standalone, 4.35% of minutes in TQQQ, 95.6% BIL, never overnight. It is a
complete long/flat event strategy, not a filter on another base. The low
exposure is structural: it holds TQQQ only on 88 of 2,011 sessions.

### 4.7 Known factors
Short-term reversal/liquidity provision (Nagel), volatility/turmoil (the 2020
cluster is a VIX spike), and TQQQ beta. The 2022-23 negative is a grinding bear
market; the strategy has no trend exposure to lose, but it also has no edge.
The 3.0% threshold is a tail event; the 2.5% neighbor has more events but worse
DD, and the 3.5% neighbor is much weaker.

### 4.8 Report vs code
- The report says "PENDING / result.json not generated"; `result.json` exists
  and `DIAGNOSIS.md` documents a post-holdout tune pass that left weights
  unchanged.
- The 3.0% threshold is a **peak, not a plateau**: 2.5% → 11.08%, 3.0% →
  11.31%, 3.5% → 8.18%, 4.0% → 4.41% (DIAGNOSIS table). The report's own
  language ("upper edge of a two-point plateau") is not supported by the
  3.5% drop.
- The `result.json` `info.event_dates` still includes 2024–26 holdout sessions;
  the `event_study` block is the corrected dev-only 88/43 version. The file is
  internally inconsistent.

---

## 5. `intraday-momentum`

### 5.1 Claimed mechanism and return driver
Weeks in which QQQ's overnight return has beaten its intraday return (a 5-day
sum of overnight-minus-intraday) and in which the first hour has been strong
(a 5-day sum of first-hour returns) have a stronger time-of-day drift. A weekly
three-state ladder holds TQQQ when both signals are above their 26-week
medians, QQQ when exactly one is, and BIL when neither is; a 20-session
overnight-vol cap cuts TQQQ to QQQ above 60% vol and to BIL above 80%.

### 5.2 Cited evidence
- **Boyarchenko–Larsen–Whelan (2023), "The Overnight Drift"** documents a
  static overnight risk premium and a tug-of-war between overnight and intraday
  returns. It does **not** establish that a high trailing 5-day
  overnight-minus-intraday spread predicts a high future spread. The rule is a
  time-series conditional strategy; the paper is a decomposition of average
  returns. This is a misapplication of the paper's mechanism to a timing rule.
- **Gao–Han–Li–Zhou (2018)** is same-day first-half-hour → last-half-hour
  momentum, especially on high-volatility/high-volume days. The rebuild
  aggregates a 60-minute first-hour return over five sessions and uses it to
  predict the next five sessions. That is a different horizon and a different
  object; the paper does not support it.
- **Lou–Polk–Skouras (2019)** is cross-sectional, not a weekly timing signal.
- The 26-week median, 5-session holding, 3-state ladder and vol caps are
  own-test. The median includes the current week, which mechanically makes the
  signals roughly 50/50.

**Assessment:** the papers support static overnight exposure and same-day
intraday momentum. They do not support a weekly conditional ladder built on
trailing sums. The rule is an untested extrapolation.

### 5.3 Falsifiable and pre-registered?
Yes, with 7 falsifiers and a clear parameter neighborhood. The result fails
almost all of them:
1. Correlation 0.616 ≥ 0.60 → fail.
2. TQQQ state forward 5-day QQQ return +5.0 bp, **lower** than the QQQ state's
   +36.5 bp and the BIL state's +49.0 bp → fail.
3. 2022-23 sub-period CAGR −21.0% → wrong sign → fail.
4. Static same-average-weights mix: 20.4% CAGR / 41.6% DD / 0.878 Sharpe, better
   than the strategy's 13.5% / 64.0% / 0.571 → fail.
5. The parameter neighborhood is not a plateau (state counts 64 TQQQ / 267 QQQ
   / 58 BIL; the first-hour signal is inverted).
6. At 5/10 bp the CAGR is 11.3%/8.5%, below QQQ's 18.9%; the drawdown is worse
   than QQQ's 37.3% → fail.
7. Dev CAGR 13.5% below QQQ 18.9% with no drawdown improvement → fail.
The result status is still "pending"; the report says "not run". This is an
adjudication failure as much as a research failure.

### 5.4 Does the rule follow from the mechanism?
No. The mechanism is a static overnight premium / same-day intraday momentum.
The rule is a weekly time-series timing ladder using trailing 5-day sums vs
26-week medians. The paper does not establish the predictive sign at a weekly
horizon, and the first-hour signal is actually **inverted** in the diagnostics:
`fwd_by_fh_signal` True = −1.19 bp, False = +68.79 bp; `perm_fh` p=0.991. The
TQQQ state is the worst of the three states. The ladder is selecting the wrong
weeks.

### 5.5 Effect size after 1 bp costs and realistic turnover
13.5% dev CAGR / 64.0% DD / 0.571 Sharpe at 1 bp; 11.3% at 5 bp; 8.5% at
10 bp. Turnover 897x total (~112x/yr), so costs are ~0.5 pp/bp. The problem is
not costs: the strategy is dominated by QQQ buy-and-hold (18.9% CAGR / 37.3%
DD) at every cost level, and by a static same-average-weights mix (20.4% /
41.6% / 0.878). The time-of-day signals add negative value.

### 5.6 Standalone or overlay?
Standalone in name, but the exposure is 66.3% QQQ, 15.8% TQQQ, 17.9% BIL
(average gross leverage 1.14x). It is a QQQ-beta book with a leverage/vol
overlay, not a distinct time-of-day return stream. The low correlation to the
165-day base is not achieved by being in cash; it is achieved by holding QQQ
instead of TQQQ.

### 5.7 Known factors
QQQ beta, the overnight drift, momentum, and volatility. The 85% equity
exposure explains most of the return; the first-hour signal is negatively
related to forward returns; the TQQQ state underperforms the QQQ state. The
2022-23 −21% is a bear-market beta drawdown, not a timing failure in isolation.

### 5.8 Report vs code
- The report says "designed; backtests paused; no result"; `result.json` exists
  with a full dev run and `status: pending`.
- The code's `state_counts` are 64 TQQQ / 267 QQQ / 58 BIL, not a balanced
  three-state ladder. The report's expected "3x/1x/0x" balance is wrong.
- `strategy.py` has a "tuning fix" comment on the rebalance bar indexing; the
  result was produced after the fix. The report's "not run" status hides this.
- The `_tune/diag.json` is the most informative file in the folder, and it is
  not referenced by the report.

---

## 6. `intraday-seasonality`

### 6.1 Claimed mechanism and return driver
On a session where QQQ is down more than 1% by the close, part of the late
selling is mechanical: daily-reset leveraged ETFs must reduce exposure in the
direction of the day's move, and they do it in the closing auction. The close
is temporarily too cheap, so buy TQQQ at the 15:59 open, hold one session, and
sell at the next 15:00 open. BIL otherwise.

### 6.2 Cited evidence
- **Cheng & Madhavan (2009)** supports the daily-reset arithmetic
  (`L(L−1)·r·NAV`, 6% of NAV per 1% index move for a 3x fund). It supports the
  *magnitude* of the flow, not the direction or the reversal horizon.
- **Mathis & Moerke (2022)** documents end-of-day LETF/options rebalancing
  pressure and a transitory reversal during the next trading day. That is the
  closest support, but the paper's effect is at the close/next open, not a
  23-hour hold to the next 15:00.
- **Lenkey (2024)** is a skeptical survey: the effect is statistically visible
  but economically disputed. The report cites it as a caveat, correctly.
- **ETF.com and Strasmore** are practitioner explanations of the mechanics.
- The original `agents2/intraday-seasonality` report describes the effect as
  **late-day momentum**, not reversal: it sold TQQQ at 15:01 and bought back at
  15:30 because the last 30 minutes were expected to continue down on weak
  days. The rebuild flips the sign at the close: it buys at 15:59 expecting a
  reversal. The original evidence does not establish the rebuild's sign.
- The own pre-pause evidence is the key: "buy 15:30, hold only to next open"
  made **1.0% CAGR / 44.5% DD**; "buy 15:30, hold to next 15:00" made **19.4%
  CAGR / 43.4% DD**. The difference is the next session's intraday, not the
  overnight/close reversal.

**Assessment:** the reset-flow mechanism is real, but the rule's horizon is
wrong. The strategy earns the next day's intraday drift, not the close-flow
reversal. The citation supports a different horizon.

### 6.3 Falsifiable and pre-registered?
Yes: F1–F7 and a 768-cell grid, with a base spec fixed before the test. But the
executed `result.json` has `variants_tried: 0` and no placebo block; the
`tune_diag.json` has 20 variants and the P1/P2/P3/P4 placebos, not 768. The
report's "parameters must be chosen from a plateau" is not satisfied: the
−1.0% threshold is the peak (see 6.5). The up-day placebo is strongly negative
(P1 −9.4% CAGR, −13.1 bp/event), which supports the signal; the gap-selected
placebo (P4) is +4.3% CAGR / +37.3 bp, about half the base, so roughly half the
edge is gap-related. The result status is "passed" but the central
"close-flow vs generic dip-buy" test is not adjudicated in the result file.

### 6.4 Does the rule follow from the mechanism?
No. The mechanism is an end-of-day flow reversal: the close is too cheap and
the pressure is transitory. The rule holds 23 hours, and the report's own
evidence says the overnight leg earns nothing (`exit=next_open` −0.38% CAGR,
+5.6 bp/event) while the full hold earns 21.8%. The edge is in the **next
session's intraday** (the 15:59→next 15:00 hold), which is a generic
post-decline dip-buy, not a close-flow reversal. The `exit=next_1558` variant
(hold to the next close) makes 30.2% CAGR, confirming that the edge continues
through the next session rather than being a one-print reversal.

### 6.5 Effect size after 1 bp costs and realistic turnover
275 events, +70.0 bp/event, t=2.39, bootstrap p=0.009; 21.8% dev CAGR / 43.8%
DD / 0.754 Sharpe at 1 bp; 15.3% at 5 bp; 7.6% at 10 bp. Turnover 2,116x total
(~264x/yr), so costs are ~1.6 pp/bp; the 1 bp headline is not robust. At 10 bp
the strategy is below QQQ (18.9%) and has a 52.7% DD. The threshold grid is a
peak, not a plateau: −0.75% → 20.6%, −1.0% → 21.8%, −1.25% → 16.4%, −1.5% →
7.9%. The `hold=2` variant makes 29.4% CAGR / 49.3% DD, so the one-session
choice is not the best either.

### 6.6 Standalone or overlay?
Standalone low-exposure event strategy: 11.7% TQQQ, 88.3% BIL, 275 events over
eight years. But the 23-hour hold includes a full overnight plus the next
session, so it is a TQQQ beta timing book, not a pure close-flow trade. As an
overlay, it would be a "buy the dip" entry on an existing long; as a standalone,
it is a lower-beta TQQQ substitute.

### 6.7 Known factors
Short-term reversal/dip-buying, TQQQ beta, the overnight drift, and
volatility. The 2020-21 sub-period is 60.6% CAGR vs 10.8% in 2016-19 and 11.7%
in 2022-23; the event is concentrated in the high-vol bull. The P1 up-day
placebo is negative, so the signal is not just "be long"; but the next-day
intraday edge is consistent with generic short-term reversal, not a
LETF-specific flow.

### 6.8 Report vs code
- The report says "design frozen, test pending; `result.json` deliberately
  absent"; `result.json` exists with `status: passed` and full dev/holdout/10y/
  5y windows.
- `result.json` `variants_tried: 0` contradicts the report's 768-cell grid and
  the `tune_diag.json` 20 variants.
- The `AUDIT.md` says "parameter neighbourhood, sub-periods, placebo and/or
  event bootstrap" are present; only the event bootstrap and sub-periods are in
  `result.json`. The placebo is in `tune_diag.json`, not the audited file.
- The code's signal is `q_day = QQQ(15:58)/QQQ(09:30 open) − 1`, which excludes
  the overnight gap; the trade's return includes the next overnight. That is
  the horizon mismatch in code form.

---

## 7. `letf-rebalance-flow`

### 7.1 Claimed mechanism and return driver
When QQQ underperforms SPY by a large standardized amount on day *t*
(`z_t = (r_QQQ − r_SPY)/σ_20 < −1.25`), part of the relative move is temporary
Nasdaq-specific LETF/options flow pressure, not information. Buy TQQQ at the
next open, hold three sessions, and sit in BIL otherwise. The return driver is
the relative reversal plus TQQQ beta.

### 7.2 Cited evidence
- **Barbon et al. (2022)** documents LETF/option rebalancing price pressure at
  the end of the day, concentrated in the underlying index. It supports the
  *existence* of end-of-day flow, not a daily close-to-close relative signal or
  a three-session hold.
- **Shum et al. (2016)** documents end-of-day rebalancing activity and
  end-of-day volatility; it is about volatility, not directional reversal. The
  provenance says so.
- **Baltussen–Da–Soebhag (2025); Vidovich & Zerjal (2026)** is a cross-sectional
  S&P 500 end-of-day reversal paper, explicitly weaker after 2019. The rebuild
  tests 2016–2023 and holdout 2024–26; if the effect weakened after 2019, the
  rule is trading a decaying effect. The report cites it as "inspired rule" but
  does not reconcile the post-2019 decay with the test period.
- **Gao et al. (2018)** is the competing intraday-momentum hypothesis.
- **Lenkey (2024)** and **Ivanov & Lenkey (2018)** are skeptical: the economic
  magnitude is disputed and LETFs may not amplify late-day returns. The report
  cites them as caveats, correctly.
- The original overlay's evidence is **absolute** QQQ/TQQQ last-hour and
  overnight returns, not the relative QQQ–SPY signal. The report admits this in
  §8 and §11: "These are motivations, not results. The relative QQQ–SPY signal
  has not been tested."

**Assessment:** the cited papers support an end-of-day, absolute, intraday
flow effect. The rule is a daily relative signal with a three-session hold.
That is a different object; the citation is a mechanism metaphor, not a test of
the rule.

### 7.3 Falsifiable and pre-registered?
Yes: 8 falsifiers, a 3 z-threshold × 4 hold neighborhood, placebos, a QQQ-risk-
asset variant and an execution-delay check. But the executed `result.json` has
`variants_tried: 0` and no event study, sub-periods, placebo or QQQ variant;
the `tune/step3_results.json` has 28 variants and a 200-draw placebo. The base
`z=−1.25, hold=3` is not the best: `z=−1.5, hold=5` makes 21.3% CAGR / 41.3%
DD / 0.690, and `win40` makes 24.2% / 39.2% / 0.774. The hold is a knife-edge:
`h1` −0.28%, `h2` +0.28%, `h3` 13.2%, `h5` 8.6%. That is a peak, not a
plateau. The falsifiers are explicit, but the final rule is a selected cell.

### 7.4 Does the rule follow from the mechanism?
No. The mechanism is an end-of-day relative flow shock; the rule measures a
**daily close-to-close** relative return and holds **three sessions**. A
QQQ–SPY relative down day is at least as likely to be Nasdaq-specific
information (rates, tech earnings, rotation) as a LETF flow. The paper's
horizon is the last part of the session, not three days. The `absolute QQQ z`
variant makes 15.7% CAGR / 40.0% DD / 0.568, better than the relative version
(13.2% / 41.8% / 0.524), which directly undercuts the "Nasdaq-specific"
premise. The QQQ-risk-asset version makes 6.25% / 16.1% / 0.563; the TQQQ
version's extra return is mostly 3x beta, not relative-value alpha.

### 7.5 Effect size after 1 bp costs and realistic turnover
13.2% dev CAGR / 41.8% DD / 0.524 Sharpe at 1 bp; 9.8% at 5 bp; 5.8% at 10 bp.
Turnover 790x total (~99x/yr), so costs are ~0.8 pp/bp. The decisive number is
the placebo: the 200 random-entry CAGR draws have mean 7.8%, median 6.5%, sd
10.1%; the base 13.2% is at the 72nd percentile, z=0.53. The base is well
inside the random-entry distribution. The strategy's return is not
distinguishable from random three-session TQQQ exposure. At 10 bp, 5.8% CAGR /
47.5% DD / 0.338 is not investable.

### 7.6 Standalone or overlay?
Standalone high-beta event book: ~22% TQQQ exposure in the tune file (the
report expected 10–15%), 41.8% DD, 99x/yr turnover. It is not a filter on
another base, but it is a levered beta book with a weak relative signal. The
`QQQ risk asset` variant is the cleaner expression and has a similar Sharpe;
the TQQQ version is not adding risk-adjusted value.

### 7.7 Known factors
Nasdaq-specific relative momentum/reversal, TQQQ beta, volatility, and the
post-2019 decay of the end-of-day reversal. The absolute QQQ signal works
better than the relative one; the QQQ-risk-asset version has a similar Sharpe;
the placebo does not reject. The "relative" innovation is not supported.

### 7.8 Report vs code
- The report says "backtests paused; no `result.json`"; `result.json` exists
  with `status: design_only` and a full dev run.
- `result.json` `variants_tried: 0` understates the 28 variants in
  `tune/step3_results.json`; the report's 3×4 neighborhood is not the executed
  grid.
- The report's expected 10–15% exposure is below the tune file's 22.4%; the
  strategy is more beta than advertised.
- `strategy.py` has a "tuning fix" in `to_minutes` (2026-11-27); the result was
  produced after the fix.

---

## Cross-cutting failure patterns

### 1. Mechanism–horizon/universe mismatch is the dominant error
Four of the seven cite papers about **end-of-day, intraday or individual-stock**
effects but trade **overnight, multi-session or index/3x-ETF** objects:
- `intraday-seasonality`: the paper's reversal is at the close/next open; the
  rule holds 23 hours, and the overnight leg earns nothing.
- `letf-rebalance-flow`: the paper's flow is last-half-hour; the rule uses a
  daily close-to-close signal and a 3-session hold.
- `intraday-mean-reversion`: LPS is cross-sectional; Gao is same-day; the rule
  is a next-session event trade.
- `gap-capitulation`: Cox–Peterson is individual-stock short-term reversal; the
  rule is an index/3x ETF 3-session hold.
The reports often admit the mismatch in a footnote, then treat the rule as if
the mechanism had been tested.

### 2. Long-only harness forces short-side effects into long proxies
`event-risk-overlay` is the clearest case: the expiry-session drift is a short-
side effect, but the engine is long-only, so the rebuild owns the surrounding
cycle and skips the expiry session. The result is 28.6% TQQQ beta, not a flow
premium. `gap-fill-fade` uses a synthetic inverse-QQQ asset to express a short;
that is legitimate, but the original report's own conclusion was that the gap
signal only works as an overlay on an overnight TQQQ long. The harness
constraint changes the economic content, not just the implementation.

### 3. Practitioner evidence is load-bearing, and the peer-reviewed evidence often points the other way
- `event-risk-overlay`: QuantifiedStrategies blog + Quantpedia; the FMA paper is
  about option rollover, not the equity expiry session.
- `gap-fill-fade`: MPM/Steady Turtle/Open Market Journal/thetrading.tools; the
  peer-reviewed Aiche et al. and Price Gap Anomaly papers find positive gaps
  **drift**, and Grant–Wolf–Yu find reversals after **large** gaps, not small.
  The report's own Loomi citation says small-gap fades lose after costs.
- `intraday-momentum`: Boyarchenko et al. and Gao et al. support static
  overnight exposure and same-day momentum, not a weekly conditional ladder.
The reports are often candid about source quality, but candour does not convert
a blog into a test of the rule.

### 4. Tiny event counts and clustering
- `gap-fill-fade`: 25 events in 8 years; +5.6 bp; t=1.01; p=0.15.
- `gap-capitulation`: 30 events, 15 of them in 2022; the event study's +6.03%
  is 2.5x the actual trade mean (+2.37%) because 20/24 trades are QQQ.
- `intraday-mean-reversion`: 88 events, 43 clusters; 2020-21 +2.61% vs 2022-23
  −0.49%; drop spring 2020 → +0.37%.
- `event-risk`: 96 expiry events; the permutation p=0.245.
- `intraday-seasonality`: 275 events, but 2020-21 contributes 60.6% CAGR.
The small-n problem is not just wide confidence intervals; it is that the
selected events cluster in the two most favorable regimes for dip-buying
(2020 COVID crash, 2022 bear-market rebounds).

### 5. Knife-edge parameters presented as plateaus
- `gap-capitulation`: `rvol_max` 1.0 → 2.80%, 1.2 → 8.30%, 1.5 → 1.25%;
  `event_low_stop` on → 4.18%, off → 8.30%.
- `intraday-seasonality`: threshold −0.75% → 20.6%, −1.0% → 21.8%, −1.25% →
  16.4%, −1.5% → 7.9%; the chosen −1.0% is the peak.
- `letf-rebalance-flow`: hold 1 → −0.28%, 2 → +0.28%, 3 → 13.2%, 5 → 8.6%;
  the chosen 3 is a jump, not a plateau.
- `intraday-momentum`: the 26-week median includes the current week; the
  state counts are 64/267/58, so the "three-state ladder" is mostly a QQQ book.
- `gap-fill-fade`: the no-confirmation variant is better than the confirmation;
  the 10:01/10:00 entry is a one-bar choice.
The reports say "plateau, not peak" in the pre-registration, but the executed
grids do not show one.

### 6. Post-holdout tuning and stale/unadjudicated results
- `gap-capitulation`: `event_low_stop` flipped off on 2026-11-27, explicitly
  "POST-HOLDOUT, dev-only evidence"; the pre-registered 4.18% rule became the
  8.30% rule, and the holdout was re-run.
- `intraday-mean-reversion`: a post-holdout tune pass (weights unchanged) fixed
  a reporting bug and lowered the p-value from a degenerate 0.0 to 0.068.
- `intraday-momentum`: a "tuning fix" in the rebalance indexing; the result is
  `pending` despite failing the correlation gate.
- `intraday-seasonality`: `result.json` has `variants_tried: 0` while
  `tune_diag.json` has 20 variants; the `AUDIT.md` claims placebos that are not
  in the audited file.
- `letf-rebalance-flow`: `variants_tried: 0` while the tune file has 28; the
  base is not the best cell.
- Several `report.md` files still say "paused / no result" although a
  `result.json` exists. The stale status is not itself a research flaw, but it
  makes the audit trail unreliable: the reader cannot tell which rule was
  actually frozen before the holdout.

### 7. Beta masquerading as alpha, and a misleading `exposure` field
`bt.stats` computes `exposure = mean((equity − cash)/equity)`. Because BIL is a
position, every result shows ~0.99999 "exposure" even when the strategy is in
the risk asset only 4–29% of the time. The correct numbers are in
`info.exposure` / `spec.exposure_share`:
- `event-risk`: 28.6% TQQQ, 26.9% CAGR — the return is beta.
- `intraday-momentum`: 66.3% QQQ + 15.8% TQQQ, 64% DD — a QQQ beta book.
- `intraday-seasonality`: 11.7% TQQQ but a 23-hour hold — beta timing.
- `letf`: 22.4% TQQQ, 41.8% DD — a levered beta book.
The result tables' `exposure` column should not be read as time in the market.

### 8. The dev window is the wrong test for these mechanisms
The 2016-2023 dev window contains the 2020 COVID crash and the 2022 bear
market — the two best environments for dip-buying, volatility-managed exposure
and capitulation reversals. The 2024-2026 holdout is a predominantly strong bull market, so a
long-biased event strategy looks good there too (`intraday-seasonality` 40.5%
holdout, `intraday-mean-reversion` 15.6%, `gap-capitulation` 10.6%). The holdout
does not test the crash behavior that the mechanisms claim to exploit. A
mechanism that is only identifiable in 2020/2022 is a regime bet, not a
standalone premium.

### 9. The original reports often already contain the negative result
- `gap-fill-fade`: original says "every standalone gap strategy fails" and "the
  only way to use the gap signal is as an overlay."
- `intraday-momentum`: original says "pure intraday momentum does not work
  here"; only the hybrid with the 165-day regime works.
- `intraday-mean-reversion`: original says the pass comes from the **re-entry**,
  not the entry, and the re-entry was conditional on the 165-day bull regime.
- `intraday-seasonality`: original says the effect is "late-day momentum," not
  reversal; the overlay sold into the 15:00-15:30 block.
The rebuilds often take the one component that worked inside the old base,
remove the base, and call it a standalone strategy. That is exactly the
"overlay in disguise" failure mode the revisit was meant to catch.

---

## Bottom line by strategy

| Strategy | Verdict | Single strongest reason |
|---|---|---|
| `event-risk-overlay` | **overlay-only** | 28.6% TQQQ exposure, 26.9% CAGR; the calendar premium is ~1%/yr, the permutation p=0.245, and the rest is beta. |
| `gap-capitulation-reversal` | **plausible-but-weak** | Strong raw event (n=30, +6.03%, t=2.89) but the 1.2x volume cap is a knife-edge and the event-low stop was removed after the holdout. |
| `gap-fill-fade` | **unsupported** | n=25, +5.6 bp, t=1.01, p=0.15; the no-confirmation variant is better and 10 bp CAGR is below BIL. |
| `intraday-mean-reversion` | **plausible-but-weak** | 88 events, +0.99%, p=0.068, CI includes zero; 2020-21 +2.61% vs 2022-23 −0.49%; the 3.0% threshold is a peak. |
| `intraday-momentum` | **unsupported** | The first-hour signal is inverted (−1.2 bp when true vs +68.8 bp when false), the TQQQ state has the lowest forward return, and corr 0.616 fails. |
| `intraday-seasonality` | **plausible-but-weak** | The edge is real (+70 bp, t=2.39) but it is next-day intraday dip-buying, not close flow; the overnight leg earns nothing, and 10 bp CAGR is 7.6%. |
| `letf-rebalance-flow` | **unsupported** | The base is at the 72nd percentile of the random-entry placebo (z=0.53), hold=3 is a knife-edge, and the absolute QQQ signal is better than the relative one. |
