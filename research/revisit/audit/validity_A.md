# Research-validity audit — batch A (7 strategies)

**Scope.** `daily-regime-minute-entry`, `donchian-breakout`, `drawdown-regime`,
`drawdown-stop-overlay`, `dual-speed-regime`, `dynamic-leverage-throttle`,
`ensemble-signals`.

**Method.** Read `report.md`, `HYPOTHESIS.md`/`hypothesis.md` and the
provenance tables, the original report under `research/agents*/` wherever the
rebuild relies on it, and `strategy.py` only far enough to check whether the
stated rule is the rule that was run. `result.json` is used as context, not as
proof. Nothing was re-run, tuned or edited. The independent audit
(`research/revisit/audit/report.md`) reports every one of these as clean on
look-ahead, so the issues below are about *inference and evidence*, not
leakage.

**Caveat on the paper trail (applies to the whole batch).** All seven reports
are frozen at the "paused / no result yet" stage. All seven `strategy.py` files
were then tuned on 2026-11-27, and four of them changed the *mechanism*, not a
parameter:

| strategy | pre-registered in the report | what the shipped code does |
|---|---|---|
| donchian-breakout | 5-minute bars, ~100 min / 4.6 h / 5 day horizons | 1-hour bars (`RULE="1h"`), ~3 day / 8 day / 8 week horizons |
| dual-speed-regime | intraday-only, flat 09:30–10:29 and 15:30–16:00, flat overnight, BIL residual | `OVERNIGHT=True`, no time-of-day entry window, `IDLE="cash"` |
| drawdown-regime | arm on current `dd(t) ≤ −20%` | arm on the *trough* drawdown since the last 52-week high (entry seen at dd = −12.6%) |
| daily-regime-minute-entry | constant-notional −1× TQQQ NAV rebalanced each minute | constant-share short re-anchored at each entry (`short_nav`) |

Consequently the pre-registered pass/fail bars in the reports do not govern
the numbers now sitting in `result.json`. Several reports also still show the
*pre-tune* result in `SUMMARY.md` (donchian −3.4% vs 13.4%; dual-speed
"rejected" vs "passed"). This is the largest process problem in the batch: the
research question was answered after the goalposts moved.

---

## Summary table

| Strategy | Verdict | Claimed mechanism | Key evidence problem | Standalone / overlay |
|---|---|---|---|---|
| `daily-regime-minute-entry` | **unsupported** | A 4% break below the TQQQ session open predicts continuation into the close; short it | The 276-event study is **165-day-gated**, not "ungated"; it includes 2024 holdout crash days; the ungated dev event mean is +8 bp (t = 0.45), not −27 bp | Standalone short; the original role was an exit filter |
| `donchian-breakout` | **plausible-but-weak** | Three Donchian horizons agree → trend breadth → BIL/QQQ/TQQQ ladder | The pre-registered 5-min version lost 3.4%/yr at 1 bp; the shipped 1-hour version was chosen after that and earns only +0.8 pp CAGR over a leverage-matched static TQQQ/BIL mix | Standalone trend ladder, but return ≈ beta + trend filter |
| `drawdown-regime` | **plausible-but-weak** | After a ≥20% QQQ drawdown, a confirmed 20-day high opens a 60-session TQQQ recovery window | 8 episodes total; 3 of the 5 2022–23 episodes lost 12–14%; 49% DD vs 35% gate; Sharpe 0.78 vs 0.92 for a constant 14% TQQQ mix | Standalone, but concentrated recovery beta |
| `drawdown-stop-overlay` | **unsupported** | A failed breakdown (undercut 20-day low, close back above it) is a liquidity sweep; buy TQQQ for 5 days | Primary is −9.3%/yr at 1 bp and every one of the 10 variants is negative; "buy any −1% day" control earns +15.8%/yr | Standalone event trade (failed) |
| `dual-speed-regime` | **overlay-only** | 60-minute QQQ EMA cross measures intraday trend persistence; hold TQQQ only while up, flat overnight | The pre-registered intraday-only version made 5.4%/yr at 1 bp and **−16.7%/yr at 5 bp**; the shipped version switched to overnight holding, i.e. it earns the TQQQ overnight drift | Trend overlay on TQQQ beta |
| `dynamic-leverage-throttle` | **plausible-but-weak** | A decaying vol shock inside a drawdown marks the end of forced deleveraging; buy inverse-vol-sized TQQQ | 6 entries (pre-registered gate: ≥12); 5.2%/yr (gate: ≥8%); the six entries cluster on 2016-02, 2018-11, 2019-05, 2020-03, 2020-09, 2022-05 | Standalone, but effectively cash-plus |
| `ensemble-signals` | **unsupported** | Vol percentile + slope state machine: QQQ normal, TQQQ recovery, BIL panic/complacency | Dev −6.3%/yr with 76% DD; 97.5% of placebo state machines beat it; neighbourhood flips to +10.2% at `stress_pct=0.9` | Standalone (failed) |

---

## 1. `daily-regime-minute-entry`

**1. Claimed mechanism and return driver.** A 4% intraday break below the TQQQ
session open is a crash-continuation signal; short TQQQ from the break to the
close (with a reclaim cover) and hold BIL otherwise. Return driver: a
short-horizon downside-momentum/liquidity-cascade effect in the 3× ETF.

**2. Does the cited evidence support this rule?** Only partially, and the
report misstates its own source. The provenance table calls the 276-event
study "ungated". It is not: `research/agents/daily-regime-minute-entry/stop_events.py`
line 18 skips every session where `not reg[f]` — i.e. every session where QQQ
is *below* its 165-day SMA. So the −0.269% "break → close" mean was measured
**inside a 165-day uptrend**, while the rebuild's primary rule is explicitly
ungated (`arm_ma20=False`). That is a conditional effect applied
unconditionally. In the ungated dev sample the sign/magnitude does not
replicate: 327 events, mean short return **+0.081%** (the price fell only 8 bp),
median +0.098%, std 3.23%, t = 0.455, p(mean ≤ 0) = 0.334. The claimed 27 bp
is roughly 3× the realised 8 bp. The cited Gao–Han–Li–Zhou (2018) and
Baltussen et al. (2021) papers support *intraday momentum from the first
half-hour to the last half-hour*; they do not establish that a −4% level
break at an arbitrary time continues. The LETF-rebalancing leg is contested by
Ivanov & Lenkey (2018), which the report itself cites. The original report is
also explicit that the stop's value is "almost entirely a handful of gap
nights", several of which are **2024 events (2024-08-01, 2024-08-02)** — i.e.
holdout data used to motivate the rule.

**3. Falsifiable and pre-registered?** Yes, unusually well: H1–H3, six
falsifiers, a placebo, and explicit numeric gates (CAGR > BIL, Sharpe ≥ 0.30,
DD ≤ 25%, event t ≥ 1.65, correlation < 0.60). The gates are stated before the
run. The problem is not the design; it is that the evidence base was
misdescribed.

**4. Does the rule follow from the mechanism?** Directionally yes (a sharp
down-move continuing is momentum), but the horizon does not. The original's
mean "saving" is `stop → next open`, and the largest events are overnight
gaps; the rebuild deliberately holds only intraday and exits at 15:59. If the
effect is a gap-night effect, an intraday-only short cannot harvest it. The
report's claim that "the night is flat" is true in its own dev event table but
contradicts the original report's attribution of the edge to gap nights. The
sizing (1× short, 100% of equity) is far too large for a 3.2% per-event
standard deviation: the realised 1-minute equity curve has 120 days with
|return| > 3% and a 61.7% drawdown.

**5. Effect size after costs.** Gross +8 bp/event × 327 events ≈ +26% over
eight years before costs. Four fills/event at 1 bp ≈ 4 bp/event, leaving
~4 bp/event, ~1.5%/yr. The result is +0.91% CAGR at 1 bp, −5.49% at 5 bp and
−12.93% at 10 bp. This is a tiny edge whose sign is not statistically
distinguishable from zero, and the 1 bp assumption is optimistic for a
marketable 1-minute order in TQQQ immediately after a −4% break.

**6. Standalone or overlay?** The rebuild is a genuine standalone short (BIL
otherwise; no old base), but the *idea* was only ever measured as an exit
filter on a long TQQQ book. The honest characterisation of the original area
is `overlay-only`; the rebuild's attempt to make it standalone failed.

**7. Already explained by known factors?** Yes, mostly short-horizon
continuation/reversal and crash-day convexity. The placebo test is informative:
random intraday shorts of the same count earn −1.9%/yr on average, so the
−4% trigger does add something over random timing (real CAGR at the 72nd
percentile), but the real 0.91% is below the placebo p95 of +5.0%. In other
words the trigger is not nothing, but it is not a harvestable standalone
premium.

**Spec vs code.** `strategy.py` implements the reported rule (trigger at first
1-min close < open × 0.96, next-bar fill, reclaim/stop2/close cover, 15:45
cut-off, 15:59 forced exit). Two material divergences: (a) §4's synthetic
−1× NAV is not what was run; `short_nav` is a constant-share short re-anchored
at entry, with a docstring saying the inverse NAV "charges a volatility drag
that a real short does not pay"; (b) the report's provenance row labels the
event study "ungated" when the script gates on the 165-day regime.

**Verdict: `unsupported`.** Strongest reason: the only sample that produced
the −27 bp effect is 165-day-gated and includes 2024 holdout crash days; the
ungated dev sample produces +8 bp with t = 0.45, so the rule as rebuilt is not
supported by the evidence cited for it.

---

## 2. `donchian-breakout`

**1. Claimed mechanism and return driver.** Trend persistence is more reliable
when fast (20), medium (55) and slow (390) Donchian channels agree; the
alignment count (0–3) selects BIL, QQQ or volatility-targeted TQQQ. Return
driver: multi-horizon time-series momentum, with the alignment acting as a
trend-breadth filter.

**2. Does the cited evidence support this rule?** The provenance is
practitioner-only: the Original Turtle Rules (2003), a Donchian blog and a
Titan FX explainer. There is no academic citation for the *alignment ladder*
(and the report admits it is "own synthesis"). The Turtle rules are daily
futures rules (20/10, 55/20, 2N stop); the rebuild applies the same bar counts
to 1-hour QQQ bars, so "20 bars" is ~3 days, not 20 days. That is a horizon
transposition, not a test of the Turtle effect. The academic trend literature
that would actually support it (Moskowitz–Ooi–Pedersen 2012; Hurst–Ooi–Pedersen
2017) works at 1–12 month horizons; the 20/55-bar sleeves are much faster and
the report does not cite them. The report's pre-registered ±1 neighbours
are all *bar counts*, so the horizon change from 5 min to 1 h is outside the
stated neighbourhood.

**3. Falsifiable and pre-registered?** Yes on paper: nine falsifiers including
correlation ≥0.60, CAGR/Sharpe floors, "alignment not better than the best
single sleeve", 5/10 bp cost retention, parameter cliff, sub-periods, placebo,
and "alpha vs QQQ ≤ 0". But the pre-registration is for the **5-minute**
version. That version was run and lost 3.38%/yr at 1 bp (DD 37.1%, Sharpe
−0.16). The 1-hour version was then chosen and produced 13.40%/yr at 1 bp. A
17 pp swing from a signal-timeframe change is not a parameter step; it is a
new strategy, and the report was never updated.

**4. Does the rule follow from the mechanism?** Directionally yes, but the
mechanism does not need three horizons. A 390-bar slow channel already
identifies the trend; the "alignment breadth" claim is that the *count* adds
information. The final sweep never compares the ladder with the slow sleeve
alone (falsifier 3 is not reported), so the central claim is untested. The
sizing is also odd: at alignment 3 the TQQQ weight is
`clip(0.30 / annATR, 0.20, 1.0)`; the result's last weight is 0.818 and the
average gross leverage is 0.684, so the strategy is 45% "risk-on" and 68%
gross on average, i.e. it is a levered beta position most of the time.

**5. Effect size after costs.** 1 bp 13.40% / 15.0% DD / Sharpe 1.00; 5 bp
8.16% / 19.8% / 0.65; 10 bp 1.95% / 25.5% / 0.21. The 10 bp result loses 85% of
the 1 bp CAGR and fails the report's own "lose no more than half" test. At
1 bp the strategy is almost exactly a leverage-matched static mix: 68.4%
average gross leverage → 22.8% TQQQ / 77.2% BIL static gives **12.64% CAGR /
28.2% DD / Sharpe 0.86**, versus the strategy's 13.40% / 15.0% / 1.00. So the
timing buys a lower drawdown but only ~0.8 pp of CAGR; there is no return edge
over beta. Turnover is 1,511× and 1,187 fills over eight years.

**6. Standalone or overlay?** Standalone in construction (it owns the position
and can be in BIL), but economically a **trend filter on QQQ/TQQQ beta**. The
honest description is "a risk-managed beta allocation"; the report's
"distinct return stream" language is too strong.

**7. Already explained by known factors?** Yes: time-series momentum/trend
following and TQQQ beta. The 0.468 correlation with the old base is within the
report's expected 0.35–0.60 range, and the static-mix comparison shows the
return is beta. The strategy does cut DD (15% vs 28% for the static mix), which
is a real risk-timing effect, but it is not a new return driver.

**Spec vs code.** `RULE = "1h"` (line 55) with `BARS_PER_DAY["1h"] = 6.5`;
the report's §4, §2 calibration table and the pre-registered slow sleeve
(390 bars = 5 days) all assume 5-minute bars. With 1 h bars, 390 bars is ~60
sessions, so the "slow" sleeve is a 60-day channel — much closer to the banned
100–250-day gate in spirit, even though it is not a moving average. The
docstring still says "on QQQ 5-minute bars" in its descriptive section.
`strategy.py` also hard-codes `VARIANTS_TRIED = 31` (5-min build + tune), so
the report's "variants tried" is a tune-time count, not the pre-registered
design.

**Verdict: `plausible-but-weak`.** Strongest reason: after the post-hoc
5 min → 1 h change, the ladder earns only 0.8 pp more CAGR than a static
TQQQ/BIL mix at the same average leverage (12.64% vs 13.40%), and 10 bp costs
remove 85% of the edge; the "alignment" adds risk reduction, not return.

---

## 3. `drawdown-regime`

**1. Claimed mechanism and return driver.** A ≥20% QQQ drawdown followed by a
confirmed 20-session high is a distinct, time-limited recovery state; hold
100% TQQQ for 60 sessions, exit on a 20-session low, then stand aside until the
drawdown heals by 5 pp. Return driver: post-capitulation recovery beta in TQQQ.

**2. Does the cited evidence support this rule?** The report is honest that the
prior is negative: AQR's *Hold the Dip* (2025) and Bonini–Shohfi–Simaan (2024)
find dip-buying at weeks-to-months horizons does not earn reliable alpha, and
Strahle (2025)/van Hemert et al. (2020) say drawdown rules trade return for
risk. The only supportive evidence is the report's own unconditional forward
TQQQ return table by drawdown bucket. That table does **not** condition on a
20-session-high confirmation, so it cannot support the confirmation rule; and
the deep bucket (≤−20%) has a 53% 20-day hit rate, the *lowest* of any bucket.
The one paper that could support a breakout entry
(Moskowitz–Ooi–Pedersen) is a 1–12 month time-series momentum result, not a
20-day high after a bear market. So the specific rule is a synthesis with a
negative prior and no direct evidence.

**3. Falsifiable and pre-registered?** Yes: F1–F7 with numeric gates
(CAGR ≥ 8%, DD ≤ 35%, corr < 0.60, ≥5 windows, bootstrap p ≤ 0.10, no
single-window dependence, 2022–23 DD ≤ 25%, breakout_only control). But the
`breakout_only`, `deep_only`, `fixed_hold` and matched-static controls are
**not in `result.json`** and not in the report's results; they exist only in
`tune_results.json`. The report still says "Controls to run with the test
(after authorisation)". F5 (the control that would show the drawdown condition
adds nothing) was therefore never formally evaluated in the report.

**4. Does the rule follow from the mechanism?** Partly. A confirmed turn after
a deep drawdown is a reasonable trend-entry, but the code's arming is on the
**trough** drawdown since the last 52-week high, not the current drawdown. That
means the entry can occur when the current drawdown is only −12.6%
(2019-01-16) or −15.2% (2020-04-09), i.e. after the recovery is well underway.
The strategy is then "buy the first 20-day high after a bear market", which is
a momentum entry, not a "deep drawdown" state. The 60-session fixed hold and
the 20-session-low exit are reasonable, but the report's §5 rule 1
(`dd(t) ≤ −20%`) is not the shipped arming rule.

**5. Effect size after costs.** 33 fills over eight years: 1 bp 17.20% CAGR /
49.0% DD / Sharpe 0.776; 5 bp 17.00%; 10 bp 16.76%. Costs are irrelevant; the
problem is the risk. Average exposure is 14.29%, and a constant 14.26% TQQQ /
85.74% BIL mix earns 8.76% / 17.4% DD / Sharpe 0.921. The DDR roughly doubles
the return at the same average exposure but triples the drawdown and has a
*worse* Sharpe. Eight episodes, and the 2022–23 episodes are −12.1%, +2.4%,
−14.4%, −12.1%, +2.1% — the "bear-rally failure mode" the report itself
identified. The three big winners (2019 +45.5%, 2020 +97.7%, 2023 +65.0%) drive
essentially all of the result.

**6. Standalone or overlay?** Standalone by construction, but the return is
concentrated TQQQ beta in three recoveries. It is not a new driver; it is a
timing rule for the equity risk premium. The original idea (a tighter stop
while in drawdown) was genuinely an overlay, and the rebuild's attempt to make
the drawdown state standalone produces a concentrated beta bet.

**7. Already explained by known factors?** Yes: post-recession recovery beta,
time-series momentum (the 20-day high), and TQQQ's embedded 3× leverage. The
report's own pre-pause table shows every de-risking variant with a correlation
of 0.65–0.90; the only low-correlation variant (contrarian) had a 75%
drawdown. That is the same trade-off seen here.

**Spec vs code.** `trough[k] <= -deep_dd` (line 184) vs the report's
`dd(t) ≤ −20%` (line 82). The docstring says "armed until a new 52-week high"
(line 31), which contradicts the report's disarm/re-arm rule; the code does
disarm after an exit. `main()` runs only the primary, not the pre-registered
controls. The result note is candid: "Fails pre-registered F1 (dev DD > 35%)
and F6 (2022-23 DD > 25%)".

**Verdict: `plausible-but-weak`.** Strongest reason: only 8 episodes, with the
2022 bear-rally failure already visible (4 of 5 episodes lost 12–14%), a 49%
DD that violates the 35% gate, and a Sharpe below a constant 14% TQQQ mix; the
"deep drawdown" condition is not even binding at entry (entries at −12.6% and
−15.2%).

---

## 4. `drawdown-stop-overlay`

**1. Claimed mechanism and return driver.** When QQQ undercuts its prior
20-session low intraday but closes back above it, with the close in the upper
half of the day's range, the breakdown was a stop run / liquidity sweep;
forced sellers are exhausted and the next few days rebound. Buy TQQQ at the
next open, hold up to 5 sessions, exit on a 10-day high, an 8% stop, or time.
Driver: short-horizon reversal/liquidity provision.

**2. Does the cited evidence support this rule?** The pattern source is
Wyckoff (1931) and three practitioner blogs — low-confidence, as the report
admits. The academic citations are Nagel (2012, *Evaporating Liquidity*),
Campbell–Grossman–Wang (1993) and Brunnermeier–Pedersen (2009). These support
*short-term reversal after non-informational selling*, but the measured
reversal in those papers is the rebound of the initial price move, typically
over days/weeks at the stock level, and it accrues to the liquidity provider
who buys *during* the pressure. This rule waits for the close, requires the
close to be in the upper half of the range (so much of the intraday reversal
has already happened), and then holds a 3× ETF for up to five days. That is a
different sign/horizon/universe: the cited effect is a cross-sectional
stock-level reversal, not a 5-day TQQQ drift after a single-day V-close.

**3. Falsifiable and pre-registered?** Yes: too-few-events, no event edge vs
unconditional, no standalone performance, correlation, concentration,
placebo-match, parameter stability, costs. But the event study (mean forward
1/3/5/10-day TQQQ vs unconditional) was never run in `main()`; only the dip
control was. The report's §5 says it is "planned". So the pre-registered event
test and the random-entry placebo are missing.

**4. Does the rule follow from the mechanism?** Not really. If the close is in
the upper half of the day's range, the reversal has already been captured by
the intraday buyer; the residual 5-day drift is a much weaker claim. The 8%
stop and 5-day cap are sensible risk controls but they do not create the
effect. The universe (TQQQ, 3×) amplifies both the intended reversal and the
noise; sizing 100% of equity in TQQQ for a single event is very aggressive for
a pattern with a 41-signal sample.

**5. Effect size after costs.** 41 signal days, 153 fills: 1 bp −9.25% CAGR /
63.1% DD / Sharpe −0.27; 5 bp −9.94%; 10 bp −10.80%. The sign is negative
before costs matter. Every one of the 10 variants is negative: lookback10
−2.51%, lookback30 −2.34%, hold3 −2.41%, hold10 −10.52%, stop6 −9.97%,
stop10 −4.25%, range04 −7.29%, range06 −3.62%, size50 −3.38%. The primary is
one of the three worst cells. The dip control (buy after any QQQ ≤ −1% day,
same holding/stop rules) earns **+15.83%** CAGR, 76.7% DD, Sharpe 0.55. So the
failed-breakdown condition is not just weak; it selects worse days than a
generic down day.

**6. Standalone or overlay?** Standalone event trade, and it failed. The
original was an overlay (a stop on the 165-day base), and the pre-pause
evidence already showed the stop only works on the base. This rebuild's
attempt to invert the overlay into a standalone long is decisively rejected.

**7. Already explained by known factors?** The +15.8% dip control is just
TQQQ beta after down days, and its 76.7% DD shows it is not a safe edge. The
specific "spring" adds nothing; the known factor is short-term reversal, and
the rule captures the wrong part of it.

**Spec vs code.** The rule is implemented as stated (daily QQQ OHLC from the
1-min tape, 20-day low, reclaim, upper-half range, next-open entry, 10-day-high
/ 8% TQQQ-close stop / 5-session time exit). The tune changed the stop from
QQQ to TQQQ (documented as a fix). The report's status is stale ("SPEC /
PAUSED"), and the event study / placebo in §5 were not run.

**Verdict: `unsupported`.** Strongest reason: the primary is −9.3%/yr and every
one of its 10 variants is negative, while a "buy any −1% day" control earns
+15.8%/yr — the 20-day-low reclaim adds negative information, not a spring.

---

## 5. `dual-speed-regime`

**1. Claimed mechanism and return driver.** QQQ's 60-minute EMA(10/30) cross
measures intraday trend persistence; hold TQQQ only while the fast EMA is
above the slow EMA, size 50/100% by spread strength, exit on the cross, a
2.5×ATR trailing stop, or the 15:29 bar; flat every night. Return driver:
intraday trend persistence, explicitly *not* overnight TQQQ beta.

**2. Does the cited evidence support this rule?** The provenance is a mix of
one academic paper (Gao–Han–Li–Zhou 2018) and practitioner research (Man AHL,
Graham Capital, StockCharts). Gao et al. support *first-half-hour → last-half-
hour* intraday momentum, not a 10/30 EMA cross at 60-minute bars. Man AHL and
Graham support "faster trend models cut the left tail but cost Sharpe" — a
risk trade-off, not a return edge. The report itself says the 10/30 pair, the
+0.30% tier, the 2.5×ATR stop and the 10:30–15:30 window are "own design
choices, not published rules". So the specific rule is unsupported by the
citations; the citations support adjacent claims.

**3. Falsifiable and pre-registered?** On paper, very well: eight falsifiers
including the crucial #3 ("the timing overlay fails to beat long TQQQ every
intraday session 10:30–15:30 on Sharpe or drawdown — i.e. the EMA adds
nothing"), #5 placebo, #7 hit rate, #8 "long TQQQ on >80% of intraday bars".
But the shipped code is not the pre-registered strategy. The pre-registered
intraday-only version was tested: **5.38% CAGR / 38.0% DD / Sharpe 0.356 at
1 bp, and −16.69% CAGR / 83.7% DD at 5 bp** (`_before_tune/result.json`).
After that, `OVERNIGHT=True` and `IDLE="cash"` were set, and the result became
28.76% / 45.5% / 1.07 at 1 bp, "passed". The diagnostic (`diag.log`) shows the
reason: the TQQQ overnight window earned +21.6%/yr over dev, while
10:30–15:30 earned +7.9%/yr and 15:30–16:00 was −8.4%/yr. The tune did not
improve the intraday signal; it switched the strategy to the overnight return
stream the report said it would avoid.

**4. Does the rule follow from the mechanism?** For the intraday version, yes
in direction but not in magnitude: the per-trade gross mean was 7.9 bp, and
net of four 1 bp fills it was 3.9 bp, t = 1.60, with 172 trades/yr and a 53.7%
hit rate. That is a very thin edge. For the shipped overnight version, the mechanism no longer
matches the claim: it holds TQQQ across sessions, so the return is dominated by
the overnight drift, and the "intraday trend persistence" story is a filter on
beta, not the source of return.

**5. Effect size after costs.** The tuned version: 1 bp 28.76% / 45.5% / 1.07;
5 bp 15.59% / 47.7% / 0.67; 10 bp 1.01% / 56.5% / 0.17. Turnover 7,343×, 2,735
fills, 589 entries and 496 stops (84% of entries stop out). The 10 bp result
removes ~96% of the 1 bp CAGR; the whole edge is of the same order as
transaction costs. The report's expected 5 bp cost of "1–2%/yr" is far too low
for 172 trades/yr; the realised 1→5 bp drop is 13.2 pp over eight years
(~1.6%/yr), and 1→10 bp is 27.8 pp (~3.5%/yr).

**6. Standalone or overlay?** **Overlay-only.** The 60-minute EMA only adds
value as a timing filter on a long TQQQ book that already earns the overnight
drift. The pre-registered intraday-only version — the actual standalone test —
lost money at realistic costs. The shipped version is a trend overlay on TQQQ
beta, and its low headline correlation (0.400) is partly zero-inflation: the
active-day correlation is 0.498, and 65% of minutes are in cash.

**7. Already explained by known factors?** Yes: TQQQ overnight drift, plus
time-series momentum/trend. The `diag.log` decomposition is explicit:
overnight +1.562 log points (+21.6%/yr), 09:30–10:30 +0.991 (+13.2%/yr),
10:30–15:30 +0.604 (+7.9%/yr), 15:30–16:00 −0.698 (−8.4%/yr). A static 0.37
TQQQ / BIL mix earns 19.07% / 42.4% / 0.84 in the pre-tune test, versus the
pre-tune strategy's 5.89% / 39.4% / 0.38 — the intraday timing destroyed value
relative to beta. The overnight version beats the static mix (32.25% vs 19.94%
in the diagnostic), so the EMA does have timing information on the overnight
book, but that is a trend overlay on the equity premium, not an independent
intraday driver.

**Spec vs code.** The divergence is the whole story. `OVERNIGHT = True` (line
50) and `IDLE = "cash"` (line 51) are the tuned defaults; when `overnight` is
true, `can_enter = (b >= warmup_bars)` (line 155) and `hard_exit = False`, so
the code can enter on any bar and hold across sessions. The report and
`HYPOTHESIS.md` say "Long TQQQ only when spread > 0, from the 10:29 bar close
through the 14:29 bar close as the last entry", "flat 09:30–10:29, flat
15:30–16:00, and flat overnight", and "BIL for the remainder". None of that is
true of the shipped default. The report's falsifier #3 (beat intraday TQQQ
10:30–15:30) is not in `result.json`; it is only in `diag.log`, where the
intraday TQQQ benchmark is −3.16% / 72.4% / 0.08. The auto-status only checks
corr < 0.60, 5 bp CAGR > 5%, 5 bp Sharpe > 0.40; it ignores DD, the intraday
benchmark, the placebo, and the mechanism change.

**Verdict: `overlay-only`.** Strongest reason: the pre-registered intraday-only
strategy made 5.4%/yr at 1 bp and −16.7%/yr at 5 bp; the "passed" version was
produced by switching to overnight holding, i.e. it earns the same TQQQ
overnight drift as the old base, with the EMA acting as a trend filter.

---

## 6. `dynamic-leverage-throttle`

**1. Claimed mechanism and return driver.** After a volatility shock, the
decay of short-horizon realised vol marks the end of forced deleveraging; if
QQQ is also in a −8% to −35% drawdown, buy TQQQ sized `min(0.75, 0.30/v20)`
and hold 2–8 weeks until vol normalises, the market recovers, vol
re-accelerates, or 60 sessions pass. Driver: post-shock recovery/volatility
risk premium, with inverse-vol sizing.

**2. Does the cited evidence support this rule?** Partly. Moreira–Muir (2017)
support *scaling exposure inversely to variance* in an always-on portfolio;
they do not support an episodic entry after a vol shock, and Cederburg et al.
(2020) — cited as counter-evidence — find the always-on version often fails
out of sample. Harvey et al. (2018) support vol targeting as a risk tool, not
as an alpha signal. Da–Engelberg–Gao (2015) support "high fear → high
subsequent market returns" at a monthly horizon, which is directionally
relevant. Whaley (2000) is a definitional VIX paper; the claim "sharp rebounds
often follow" is not in it. The exact three-condition state machine is the
report's own and is admitted to be unsupported by any paper. So the citations
support the *sizing* and a general "buy after fear" prior, not the specific
`v20 ≥ 1.25 v60`, `v5 ≤ 0.85 v20`, `−35% ≤ dd ≤ −8%` rule.

**3. Falsifiable and pre-registered?** Yes, and the bars are strict: ≥12
entries, CAGR ≥ 8%, Calmar ≥ 0.50, DD ≤ 35%, 2020 ≤ 80% of P&L, ablation of
the decay condition, 3×3×3×3×3 neighbourhood with median Calmar ≥ 0.35, 5 bp
survival. The shipped result fails two of them outright: **6 entries** (<12)
and **5.24% CAGR** (<8%). The code also disables the pre-registered
re-acceleration exit (`use_reaccel=False`).

**4. Does the rule follow from the mechanism?** The direction is plausible
(buy after a vol spike when it starts to decay), but the sign of the
short-horizon condition is fragile. `v5 ≤ 0.85 v20` is essentially "the last
five days were calmer than the last 20"; that is a short-term reversal/oversold
signal as much as a "forced deleveraging is over" signal. The drawdown band
−35% to −8% excludes the deepest crashes, which is where the convexity is
largest, and includes ordinary pullbacks. The inverse-vol size
`min(0.75, 0.30/v20)` at v20 = 0.60 gives 50%, at v20 = 1.0 gives 30%; the cap
binds only in calm vol, which the entry mostly excludes, so the position is
usually 30–50% TQQQ, not 75%. The holding period (median 14.5 sessions) is
short relative to the "2–8 weeks" claim.

**5. Effect size after costs.** 65 fills, turnover 10.8×: 1 bp 5.24% CAGR /
9.16% DD / Sharpe 1.06 / Calmar 0.57; 5 bp 5.20%; 10 bp 5.14%. Costs are not
the issue; the issue is the sample and the return level. The strategy is in
BIL most of the time; its yearly returns are 3.9%, 0.7%, 4.8%, 13.0%, 9.8%,
−0.1%, 5.4%, 4.9%. That is a cash-plus profile, not a 3× equity strategy.
Six episodes, all positive (+2.9%, +0.8%, +10.5%, +5.5%, +3.6%, +4.2%),
bootstrap p = 0.0 — but with n = 6 and a 100% hit rate the bootstrap is
uninformative.

**6. Standalone or overlay?** Standalone (BIL default, episodic TQQQ), but it
is essentially an overlay-sized TQQQ sleeve on a cash portfolio. The original
idea (vol-targeted leverage on top of the 165-day base) was an overlay; this
rebuild changes the state but keeps the "own a small TQQQ sleeve" character.

**7. Already explained by known factors?** Yes: post-drawdown equity recovery
beta and the volatility risk premium. The six entries cluster on known stress
dates (2016-02-04, 2018-11-02, 2019-05-31, 2020-03-23, 2020-09-16,
2022-05-25), i.e. the strategy is a "buy the dip after a vol spike" rule. The
report's own ablation shows the always-on vol target earns 32.5% CAGR but
correlates 0.809 with the old base — the independence is bought by being out
of the market, not by a different driver. `no_drawdown` earns 5.66% with a
10.8% DD (better than the primary on both), so the drawdown condition is not
adding return; `no_shock` earns 5.23% with 15.2% DD. The combination is a risk
smoother, not an alpha source.

**Spec vs code.** `use_reaccel=False` (line 58) removes the report's
`v5 ≥ 1.10 v20` exit. The report's §5 still lists it. This is not cosmetic:
the pre-tune diagnostic (`tune_diag_warmfix.json`) has the 2018-11-02 episode
at −3.82%, while the shipped result's six episodes are all positive — dropping
the pre-registered re-acceleration exit converted a loser into a winner after
the dev result was known. The tune also added `warmup_daily` (pre-2016 daily
history), which is a data fix, not a rule change. The report's status is
"DESIGN ONLY — not run"; `result.json` is the tuned run, so the report's §11
"expected shape" (CAGR low-to-high teens, 10–25 entries) is not what happened
(5.2%, 6 entries).

**Verdict: `plausible-but-weak`.** Strongest reason: six entries and 5.2%/yr
fail the pre-registered ≥12-event and ≥8%-CAGR gates; the result is
indistinguishable from "TQQQ rallied after six stress dates", and the drawdown
condition actually reduces return versus `no_drawdown`.

---

## 7. `ensemble-signals`

**1. Claimed mechanism and return driver.** Volatility spikes cluster and mean
revert; the high-vol *contraction* phase is a distinct TQQQ recovery window,
while rising vol from a low is a complacency warning. Daily state machine:
QQQ in normal times, TQQQ in recovery, BIL in panic/complacency, with
vol-scaled weights. Driver: post-spike recovery premium plus a vol-timing
overlay.

**2. Does the cited evidence support this rule?** The provenance is broad and
mostly supportive of the *pieces*: Engle (1982)/Bollerslev (1986) for vol
clustering, Christie (1982)/Campbell–Hentschel (1992) for asymmetry,
Bollerslev–Tauchen–Zhou (2009) for the variance risk premium,
Moreira–Muir (2017) for vol-managed exposure, Cederburg et al. (2020) as
counter-evidence, Daniel–Moskowitz (2016) for high-vol crash risk,
Folkinshteyn (2015) for post-crash reversals. None of them supports the exact
percentile/slope thresholds, and the report says so. The strongest academic
support (Bollerslev–Tauchen–Zhou) is about the *variance risk premium*
predicting market returns at a monthly horizon; using realised vol as a proxy
and a 5/20/252-day state machine is a leap. The "complacency" state (low vol,
rising) has no direct citation at all.

**3. Falsifiable and pre-registered?** Yes: ten falsifiers including
correlation, recovery premium > 0, CAGR vs QQQ, sub-period sign stability, a
parameter neighbourhood with the same sign, a placebo with matched state
durations, cost fragility, QQQ-beta, time-stop dependence, and leakage. The
problem is the result: the primary is −6.34% CAGR / 76.0% DD / Sharpe −0.05 at
1 bp; −7.98% at 5 bp; −9.99% at 10 bp. The 2022–23 sub-period is −43.9%/yr.
The placebo test in `tune/placebo_A1.txt` says the placebo CAGR mean is
+16.5% (sd 8.7%) and **97.5% of placebo state machines beat the real one**.
That is a direct hit on falsifier #6 ("if the placebo is indistinguishable, the
state labels add nothing") — the labels are worse than random.

**4. Does the rule follow from the mechanism?** The direction is plausible but
the state definitions are fragile. `rv_pct ≥ 0.80` and `slope ≤ +0.10` is a
very coarse "recovery" definition; the recovery state is 292 days (14.5%) and
44 episodes, average 6.6 days. A 20-day max recovery and a 5-day min hold mean
the strategy is often whipsawed. The "complacency" state (199 days) sells QQQ
when vol is low and rising, which is exactly the condition before many
melt-ups; the report itself notes that 2019, 2021 and 2025 underperform for
this reason. The TQQQ weight `min(1, 0.35/rv20)` at rv20 = 0.35 is 100%, so the
recovery state is a full 3× position in the most volatile regime — the
opposite of risk control.

**5. Effect size after costs.** 768 fills, turnover 375×: 1 bp −6.34%, 5 bp
−7.98%, 10 bp −9.99%. Negative before costs matter. The only question is why it
is so bad: the state machine buys TQQQ in high-vol recoveries that fail (2022)
and sits in BIL during low-vol melt-ups (2019/2021). The neighbourhood is not a
plateau: `stress_pct=0.9` gives +10.2%, `vol_fast=10` +6.0%, `vol_mid=15`
+5.5%, `vol_mid=30` +4.1%, while the center is −6.3%. A 16.5 pp swing from a
one-step change in the stress percentile is a knife-edge, not a plateau.

**6. Standalone or overlay?** Standalone in construction (QQQ default, TQQQ
only in recovery). But it is economically a vol-timing overlay on QQQ/TQQQ
beta; the original ensemble was an overlay on the 165-day base, and removing
the base leaves a state machine that has no positive return.

**7. Already explained by known factors?** Yes: volatility timing and the
post-shock recovery beta. The report's own table shows the vol budget added
6.5 pp CAGR / 16 pp DD *on top of the 165-day gate*; that is the context in
which the idea worked. Without the gate, the same vol budget is a standalone
timing rule that loses money. The known result that vol-managed portfolios do
not reliably beat unmanaged ones out of sample (Cederburg et al. 2020) is
exactly what happened.

**Spec vs code.** The code matches the report's state machine (verified
`_raw_state`, `_state_path`, `_target`). The report is stale: it says
"design only, no result" while `result.json` has a full dev run. The
`result.json` does not store the state counts or the placebo; those are only
in `tune/`. The report's §8 falsifier #5 (neighbourhood plateau) is failed by
the tune file, not by the report.

**Verdict: `unsupported`.** Strongest reason: −6.3%/yr with a 76% DD, and 97.5%
of placebo state machines beat it — the state labels are worse than random, so
there is no recovery premium to harvest.

---

## Cross-cutting

**1. "No shared base" was mostly an exposure test, not a driver test.** Six of
the seven are long TQQQ or QQQ in some state; the only short is
`daily-regime-minute-entry`, and it is too small and too volatile. Low
correlation with the old base is easy to achieve by sitting in BIL/cash most
of the time (dynamic-leverage 0.108, drawdown-regime 0.298, dual-speed 0.400),
but that is a statement about *time out of the market*, not about a new return
driver. The brief's 0.60 correlation gate therefore rewards under-exposure.
The dual-speed report deserves credit for reporting active-day correlation
(0.498 vs 0.400 all days); the others should do the same, and should report
beta to TQQQ/QQQ on active days.

**2. Pre-registration is nominal because the code was changed after the test.**
The reports were written as if the tests were still paused; then the strategies
were tuned on dev and the reports were not updated. In four cases the tune
changed the mechanism (donchian 5 min→1 h, dual-speed intraday→overnight,
drawdown-regime current-dd→trough, daily-regime inverse-NAV→constant-share
short). The result is that the published pass/fail bars no longer apply to the
published numbers. A reader who trusts the report will evaluate a strategy that
was not run; a reader who trusts `result.json` will evaluate a strategy whose
hypothesis was never pre-registered. This is more damaging than any single
negative result.

**3. The evidence is repeatedly borrowed from a different horizon, sign or
universe.** Examples:
- Turtle rules are daily futures rules; the rebuild runs 20/55/390 *bars* on
  1-hour QQQ.
- Gao–Han–Li–Zhou is first-half-hour → last-half-hour momentum; the rebuild
  uses a −4% level break at an arbitrary time.
- Nagel/Campbell–Grossman–Wang are stock-level short-term reversal/liquidity
  provision; the rebuild holds a 3× ETF for five days after a V-close.
- Moreira–Muir is always-on inverse-variance sizing; the rebuild uses it as an
  episodic entry signal.
- Kaminski–Lo says stops add value only under momentum; it is cited to justify
  stops in strategies whose own results show the momentum is absent.

**4. The only large, unambiguous results in this batch are negative.** The
three strongest pieces of evidence are: `drawdown-stop-overlay`'s +15.8% dip
control beating its −9.3% primary; `ensemble-signals`' placebo at +16.5% vs
−6.3% real; and `dual-speed-regime`'s intraday-only version at −16.7% at 5 bp
versus its overnight re-brand at +28.8% at 1 bp. These are the reports that
actually teach something: the specific signal is not the source of return, and
the "fix" is usually beta re-exposure.

**5. Small samples and fat tails dominate the positive-looking results.**
`drawdown-regime` has 8 episodes and 3 winners; `dynamic-leverage-throttle` has
6 episodes, all positive; `daily-regime-minute-entry` has
327 events but a 3.2% per-event standard deviation and a 61.7% drawdown. None
of these is enough to distinguish a real state premium from "TQQQ went up after
the bottom". The reports say this in the risk sections, but the summary tables
and statuses still read as if the point estimates were informative.

**6. The pre-registered controls are often absent from `result.json`.** The
event study and random-entry placebo in `drawdown-stop-overlay`; the
`breakout_only`/`deep_only`/`fixed_hold`/matched-static controls in
`drawdown-regime` (they exist in `tune_results.json` but not in the report);
the single-sleeve and alpha-vs-QQQ tests in `donchian`; the intraday-TQQQ and
placebo tests in `dual-speed` (only in `diag.log`). A report that does not
show the falsifier that would kill it is not a full test, even if the numbers
are honest.

**7. What would make a rebuild in this batch credible.** (a) Freeze the report
and code together, then run once; do not tune after the dev result. (b) Report
the leverage-matched static mix and the active-day beta next to every CAGR.
(c) Report the event count and the bootstrap/placebo before the headline
number. (d) Treat a 5 min→1 h or intraday→overnight change as a new strategy
requiring a new pre-registration. (e) Use the 0.60 correlation gate together
with an exposure/beta gate, otherwise under-exposure passes for independence.
(f) For stop/overlay ideas, state up front that the standalone test is expected
to fail and make the overlay role the deliverable, rather than converting a
stop into a standalone trade and calling the negative result a strategy
failure.
