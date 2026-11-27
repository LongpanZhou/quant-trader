# Why the rebuilds underperform TQQQ

**Status: partial audit, stopped on request (2026-11-27).** This is a handoff
document, not a completed audit. It records what was inspected, what is
confirmed, and what is still unknown. No strategy code, result, curve, website
file, or data file was modified. No backtest was launched after the stop
instruction.

The audit covered:

- all 26 `research/revisit/<slug>/report.md` plus the original
  `research/agents2/ratio-pairs/report.md`;
- the available `HYPOTHESIS.md` / `hypothesis.md`, `SPEC.md` / `spec.md`,
  `PROVENANCE.md` / `provenance.md` (read directly where present, otherwise
  through the report's provenance table);
- all 27 `curves_full/<slug>.json` files, compared with the current
  `<slug>/result.json` development metrics;
- all 27 `web/public/data/compare/all.json` metrics;
- file mtimes for `strategy.py`, `result.json`, `curves_full/*.json`, and the
  `_before_tune` backups;
- `capture_full.py`, `full_missing.py`, `full_direct.py`,
  `export_compare_full.py`, `run_all.py`, `run_holdout.py`, and `bt.py`.

It did **not** finish the line-by-line spec-vs-code audit, the look-ahead cut
tests, or the same-exposure benchmark for every strategy. Those are marked
below.

---

## 1. Research validity (priority section)

### 1.1 How this ranking was made

For each strategy I asked:

1. What is the claimed mechanism and return driver?
2. Does the cited paper/evidence support that exact claim, or is it
   overgeneralised/misapplied (cross-sectional result used as a time-series
   rule, monthly result used intraday, theory paper used as proof of a
   tradable anomaly, different asset/universe)?
3. Is the hypothesis falsifiable, and was it written before the test?
4. Does the rule follow from the mechanism (sign, horizon, universe, sizing)?
5. Is the effect plausible after costs, or is it a tiny edge?
6. Is it standalone, or a risk overlay/filter in disguise?
7. Is the edge already explained by TQQQ beta, trend/momentum, volatility, or
   mean reversion?

The ranking is an analyst judgment from the documents, not a mechanical score.
It is deliberately independent of the backtest result; the result is used only
as corroboration.

**Bottom line: no strategy is ranked SOUND.** The best are
PLAUSIBLE-BUT-WEAK. Two are OVERLAY-ONLY in disguise. The rest are UNSUPPORTED
because the specific rule is own-test, the cited evidence does not support it,
the cited evidence supports the opposite sign, or the event is too thin to
test.

### 1.2 Ranking table

| # | Slug | Mechanism / claimed driver | Key citation(s) | Citation support | Falsifiable + pre-registered? | Rule follows mechanism? | Standalone? | After-cost plausibility | Known-factor redundancy | Rank |
|---:|---|---|---|---|---|---|---|---|---|---|
| 1 | `ratio-froth` (original) | TQQQ/QQQ ratio froth = low-vol melt-up, crash risk; switch TQQQ→QQQ | Avellaneda–Zhang 2010; Brunnermeier–Sannikov 2014; Adjusted Close | Identity yes; predictive/crash claim is own test | Yes; report has falsifiers and a look-ahead shift test | Mostly: ratio ext is a decay/variance proxy, but the strategy still needs the 165-day gate and stop | No: it is the old 165-day winner + ratio overlay | Not tested standalone; overlay contributes ~1.4 pp CAGR without the stop | TQQQ/QQQ beta + low-vol/momentum interaction | **OVERLAY-ONLY** |
| 2 | `vol-scaled-crash-stop` | ATR-scaled one-sided stop on always-long TQQQ; inverse-vol size | Kaminski–Lo 2014; Moreira–Muir 2017; Cheng–Madhavan 2009 | Stop-under-momentum and vol-scaling support the pieces; the specific one-sided break is own | Yes; explicit 7 falsifiers | Yes as a risk rule; not as a new return driver | No: always-long TQQQ with a stop; corr 0.755 to old base, fails its own <0.60 rule | High turnover (3,950 fills) and 5/10 bp sensitivity are real; 1 bp edge survives, 10 bp much weaker | TQQQ beta + crash timing | **OVERLAY-ONLY** |
| 3 | `ratio-pairs` | Ratio cycle: froth→BIL, capitulation→40% TQQQ, middle→90% QQQ | Avellaneda–Zhang 2010; Brunnermeier–Sannikov 2014; Moreira–Muir 2017; Cederburg et al. 2020 | Identity yes; the jump from identity to a tradable 200-day oscillator is own | Yes; explicit 7 falsifiers, dev-only expectation bands | Mostly; but the ratio is ~98% explained by QQQ extension + variance, so it is largely QQQ + vol | Yes, but ~90% QQQ in the middle state | 18.96% dev / 20.42% full ≈ QQQ's 18.9% / 19.6%; the timing adds ~1–2 pp, not a new premium | QQQ beta + low-vol/momentum; corr to TQQQ 0.84 | **PLAUSIBLE-BUT-WEAK** |
| 4 | `intraday-seasonality` | LETF/close-flow pressure makes a down close temporarily cheap; buy 15:59, hold one session | Cheng–Madhavan 2009; Mathis–Moerke 2022; Lenkey 2024 (sceptical); Gao et al. 2018 | Rebalancing exists; a predictable next-day reversal is contested (Ivanov–Lenkey 2018). The trade holds through the next day, not just the overnight reversal | Yes; explicit F1–F7 | Partly: the mechanism predicts an overnight reversal, but the preliminary evidence says the overnight leg alone earns ~1.0% while the next-day intraday leg earns ~19.4% | Yes: 11% of bars, TQQQ/BIL | Strong 1 bp result (26.4% full, 21.8% dev); 5/10 bp not checked here | Generic short-horizon reversal / dip-buying, not necessarily LETF flow | **PLAUSIBLE-BUT-WEAK** |
| 5 | `event-risk-overlay` | OpEx Friday is the weak session; own the 4-before/2-after window, skip expiry | QuantifiedStrategies OpEx; FMA 2025 expiration rollover; Quantpedia (opposite sign) | The expiry-day fact is measured in-sample (96 events, −83.9 bp o2c, t=−2.72); the long-only window is a proxy for a short effect | Yes; explicit F1–F5 | Partly: it avoids the negative day but earns mostly TQQQ beta on the other 29% of sessions | Yes in form, but 29% TQQQ exposure | 22.2% full / 26.9% dev on 29% exposure is high; the attributable calendar edge is only ~1%/yr; window selection is in-sample | TQQQ beta + calendar/carry | **PLAUSIBLE-BUT-WEAK** |
| 6 | `intraday-mean-reversion` | After a ≥3% intraday QQQ decline, next session open→close has a liquidity-provision rebound | Nagel 2012; Lou–Polk–Skouras 2019; Gao et al. 2018 | Nagel is cross-sectional reversal; LPS is overnight/intraday cross-prediction; neither directly proves a QQQ event-time next-open-to-close trade | Yes; explicit P0/V1–V12/falsifiers | Mostly; but the cited reversal is at the overnight boundary, while the trade is next-day intraday | Yes: ~4.35% of minutes, TQQQ/BIL | 88 events / 43 clusters, mean +0.99%, p=0.068, 95% CI includes zero; 2022–23 flat | Short-horizon reversal / dip-buying; TQQQ beta on event days | **PLAUSIBLE-BUT-WEAK** |
| 7 | `time-of-day` | Closing pressure reverses overnight; buy TQQQ after a sold last-30m, hold to 10:01 | Berkman et al. 2012; Lou–Polk–Skouras 2019; Cliff–Cooper–Gulen 2008; Gao et al. 2018 (opposite) | Overnight premium yes; the sign of the closing→overnight link is explicitly contested and tested as V4 | Yes; F1–F7 and 6 variants | Mostly; but 17.2% full ≈ a static ~45% TQQQ / 55% BIL mix, so the conditioning may add little | Yes: conditional overnight TQQQ | 17.2% full / 19.7% dev; 40–50% duty cycle, two fills per active night | Overnight TQQQ beta; known overnight drift | **PLAUSIBLE-BUT-WEAK** |
| 8 | `overnight-crash-filter` | Night continues an up day; day reverses a down night; gap-budget sizing | Lou–Polk–Skouras 2019; “Day Destroys the Night”; NY Fed SR917 | Block means are real; the conditional sign pattern is own and the day leg is weak | Yes; F1–F6, legs tested separately | Partly; the day leg fights a negative session mean in the 25–30% vol bucket | Yes: two-block rotation | 10.37% dev / 11.34% full; below a static ~50% TQQQ mix (~19.5%) | TQQQ overnight beta + vol timing | **PLAUSIBLE-BUT-WEAK** |
| 9 | `dual-speed-regime` | 60-minute QQQ EMA cross measures intraday trend; hold TQQQ intraday only | Gao et al. 2018; Lou–Polk–Skouras 2019; Man AHL speed; Kaminski–Lo 2014 | Gao supports intraday persistence; a 60-min EMA is a trend rule, not the first-half-hour predictor | Yes; explicit 8 falsifiers | Partly; the signal is a generic fast trend filter | Yes: intraday TQQQ/BIL | Current dev result 28.76% / 45.45% DD is strong; the published full curve (5.15%) is stale. **High-priority check** | Intraday momentum/trend; TQQQ beta | **PLAUSIBLE-BUT-WEAK** |
| 10 | `donchian-breakout` | Multi-horizon Donchian alignment as trend breadth; BIL→QQQ→TQQQ ladder | Original Turtle rules; practitioner Donchian sources | Turtle breakout is real; the 20/55/390 alignment ladder is an own synthesis with no external evidence | Yes; 9 falsifiers | Partly; breadth is plausible, but the slow sleeve is only 5 days, not a long trend | Yes: QQQ/TQQQ/BIL ladder | Current dev 13.40% / 35.77% DD; published full curve (−0.94%) is stale | Trend/momentum; TQQQ beta at 3/3 | **PLAUSIBLE-BUT-WEAK** |
| 11 | `ml-classifier` | K-means regimes; map clusters to TQQQ/QQQ/BIL by past forward returns | Hamilton 1989; Guidolin–Timmermann 2007; Nystrup et al. 2015; Horvath et al. 2021 | Regime persistence yes; the 23-feature k-means / 20-day mapping is own, and the “unsupervised” label is misleading because the asset map is supervised | Yes; explicit 9 falsifiers | Partly; cluster→asset mapping can work but is unstable and is essentially vol/trend sorting | Yes: three-asset allocation | 20.69% dev / 18.95% full; corr to TQQQ 0.64, QQQ-like; full curve vs dev mismatch −2.79 pp suggests a full-period refit issue | QQQ/TQQQ beta + vol regime | **PLAUSIBLE-BUT-WEAK** |
| 12 | `ml-crash-overlay-winner` | ML predicts next-5-session TQQQ-vs-3×QQQ decay; rotate TQQQ/QQQ/BIL | Avellaneda–Zhang 2010; Cheng–Madhavan 2009; Arnott et al. 2019; López de Prado | Decay identity yes; predictability is weak (original AUC ≈0.50, unstable) | Yes; explicit 8 falsifiers | Partly; the label is mostly a vol proxy; ML may add little over a vol rule | Yes: three-state rotation | 15.80% dev / 15.07% full; 22.4% dev DD; corr 0.52 | TQQQ/QQQ beta + vol/decay | **PLAUSIBLE-BUT-WEAK** |
| 13 | `letf-rebalance-flow` | QQQ underperformance vs SPY is temporary LETF/flow pressure; buy TQQQ 3 sessions | Barbon et al. 2022; Shum et al. 2016; Baltussen et al. 2025; Lenkey 2024; Ivanov–Lenkey 2018 | The end-of-day flow literature is real, but the strategy uses a **daily close-to-close QQQ–SPY** proxy because there is no 1-min SPY; it does not test the late-day mechanism | Yes; explicit 8 falsifiers | Weak: the proxy includes the whole day and market beta, not just the close flow | Yes: TQQQ/BIL event | 13.20% dev / 7.80% full; 41.8% dev DD; corr 0.48 | QQQ/TQQQ beta + relative-value reversal | **PLAUSIBLE-BUT-WEAK** |
| 14 | `drawdown-regime` | After a ≥20% QQQ drawdown, a confirmed 20-session high starts a 60-session TQQQ recovery window | AQR “Hold the Dip” 2025 (negative); Bonini et al. 2024 (negative); Moskowitz et al. 2012 | The cited evidence is **negative** on dip-buying; TSMOM is 1–12 months, not a 20-session turn | Yes; explicit F1–F7 | Weak: the confirmation filter is the only thing standing between this and a failed dip-buy | Yes: TQQQ/BIL event | 17.20% dev / 49% DD; 5–8 windows; low power; published full curve (−0.11%) is stale | TQQQ beta + short-term reversal | **UNSUPPORTED** |
| 15 | `drawdown-stop-overlay` | Failed breakdown / spring: QQQ undercuts 20-day low intraday, reclaims, closes strong; buy TQQQ 5 sessions | Wyckoff 1931; practitioner spring/liquidity-sweep sources; Nagel 2012; Campbell–Grossman–Wang 1993 | The pattern is practitioner lore; the academic reversal evidence is cross-sectional/volume-based, not this exact pattern; the original stop family was TQQQ beta | Yes; explicit 8 falsifiers | Weak: “spring” is a pattern, not a measured flow; the 8% stop is not tied to the event | Yes: TQQQ/BIL event | −9.25% dev / 63% DD (current result); published full curve (−2.37%) is stale and too kind | TQQQ beta + short-term reversal | **UNSUPPORTED** |
| 16 | `ensemble-signals` | Volatility contraction recovery / complacency warning state machine; QQQ/TQQQ/BIL | Engle 1982; Bollerslev 1986; Bollerslev–Tauchen–Zhou 2009; Moreira–Muir 2017; Cederburg et al. 2020 | Vol clustering/variance risk premium yes; the exact percentile/slope state machine is own | Yes; 10 falsifiers | Partly; the state machine is a vol-timing rule with no direct evidence | Yes: three-asset vol state | −5.21% dev / 76% DD; 1.34% full / 76% DD | Vol timing + QQQ/TQQQ beta | **UNSUPPORTED** |
| 17 | `dynamic-leverage-throttle` | Vol-shock recovery: buy TQQQ when v20≥1.25×v60, v5≤0.85×v20, and QQQ drawdown −35%..−8% | Moreira–Muir 2017; Harvey et al. 2018; Cederburg et al. 2020; Whaley 2000; Da–Engelberg–Gao 2015 | Vol clustering and fear rebounds support the pieces; the joint state is own | Yes; 7 falsifiers | Partly; the vol-decay state is plausible but the drawdown band is arbitrary | Yes: TQQQ/BIL episodic | 2.65% dev / 5.24% dev CAGR? (current result 5.24% 1 bp) with only ~5 entries; underpowered | Vol timing + TQQQ beta | **UNSUPPORTED** |
| 18 | `vol-kelly-overlay` | Vol-spike reflation: buy TQQQ after 1-min RV spike + 10-day oversold + first up close | Moreira–Muir 2017; Harvey et al. 2018; Cheng–Madhavan 2009; ProShares prospectus | Vol clustering yes; the exact event is own | Yes; 9 falsifiers | Partly; “first up close” is a reasonable stabilisation, but the event is rare | Yes: TQQQ/BIL event | 1.81% dev / 1.03% full; ~few entries; underpowered | Vol timing + TQQQ beta | **UNSUPPORTED** |
| 19 | `gap-fill-fade` | Small gap-up in weak/stressed tape fills; short QQQ after 10:00 confirmation | Practitioner gap sources; Grant–Wolf–Yu 2005; Aiche-Cohen-Griskin 2024; 2026 overnight-reversal paper | Small-gap fill is a known intraday pattern; the 10:00 confirmation and OR-high stop are own and likely data-mined | Yes; 7 falsifiers | Partly; the old overlay's per-event edge was t=1.60 (10y) and t=0.92 (5y), not significant | Yes: synthetic short QQQ | 1.43% dev / 2.21% full; 0.38% DD: effectively empty | Short QQQ beta + intraday reversal | **UNSUPPORTED** |
| 20 | `opening-range-breakout` | Failed breakdown of the 30-min opening range that reclaims ORL is a liquidity sweep; long QQQ to ORH/EOD | Build Alpha blog; Fetna 2026 (ORB fails costs); Pineda 2026 (retest); Zarattini–Aziz 2023 | The cited evidence rejects plain ORB; the failed-breakdown reclaim is a practitioner pattern with no direct evidence | Yes; 8 falsifiers | Weak: the “sweep” is inferred from one bar pattern, not order flow | Yes: intraday QQQ | −2.10% dev / 19.99% DD | Intraday reversal / QQQ beta | **UNSUPPORTED** |
| 21 | `stop-reentry-recovery` | TQQQ underperforms 3×QQQ by ≥1 pp on a ≥3% down session = LETF rebalancing overshoot; buy TQQQ 3 sessions | Strasmore; Shum et al. 2016; Avellaneda–Zhang 2010; “Preying on Leveraged ETFs” (Korea) | LETF rebalancing/tracking error is real; the specific relative-overshoot event is own; the Korean evidence is external-validity-limited | Yes; 8 falsifiers | Plausible sign/horizon, but the event is extremely rare | Yes: TQQQ/BIL event | **1 event in 2,012 sessions** (SUMMARY); effectively empty | TQQQ beta + short-term reversal | **UNSUPPORTED** |
| 22 | `volume-orderflow` | Heavy-volume intraday decline closing in the upper half = absorbed supply; buy TQQQ 5 sessions | Campbell–Grossman–Wang 1993; Conrad–Hameed–Niden 1994; Llorente et al. 2002 | These are cross-sectional/volume studies; the time-series QQQ event is own; the report itself says the sample may be 15–30 events | Yes; F1–F8 | Partly; “absorption” is inferred from CLV, not measured | Yes: TQQQ/BIL event | **3 events in 2,012 sessions** (SUMMARY); effectively empty | TQQQ beta + short-term reversal | **UNSUPPORTED** |
| 23 | `winner-ensemble-blend` | Inverse-vol blend of calm QQQ carry and panic TQQQ reversal | Nagel 2012; Da–Liu–Schaumburg 2014; Moreira–Muir 2017; Asness–Frazzini–Pedersen 2012; DeMiguel et al. 2009 | Components are known factors; the allocation is a risk-parity overlay; the citations do not establish a blend premium | Yes; 8 falsifiers | Partly; the two streams are anti-correlated in condition, but each is weak | Yes: multi-stream | 0.30% dev / 3.04% full; 30.5% DD | Equity carry + reversal beta | **UNSUPPORTED** |
| 24 | `risk-parity-hrp` | ERC QQQ/TQQQ plus a contrarian vol-state budget; raise risk after transient vol spikes | Asness–Frazzini–Pedersen 2012; ERC literature; Moreira–Muir 2017; Cederburg et al. 2020 | ERC yes; with QQQ/TQQQ correlation ≈0.999 it is just a leverage choice; the contrarian tilt is an own hypothesis with no direct evidence | Yes; 6 falsifiers | Weak: the central “conditional Sharpe rises after transient vol” claim is untested | Yes: allocation | 5.70% dev / 6.49% full; 17.9% DD; corr to TQQQ 0.88; Sharpe 0.69 < QQQ 0.92 | Low-beta QQQ/TQQQ equity mix | **UNSUPPORTED** |
| 25 | `intraday-momentum` | Weekly three-state leverage ladder on overnight-minus-intraday and first-hour returns | Boyarchenko–Larsen–Whelan 2023; Lou–Polk–Skouras 2019; Gao et al. 2018; Cheng–Madhavan 2009 | The overnight drift and intraday momentum are daily phenomena; aggregating to a 5-session weekly state is an own leap | Yes; 7 variants, 8 falsifiers | Weak: weekly aggregation may destroy the daily effect; the report itself flags this | Yes: TQQQ/QQQ/BIL | 13.51% dev / 14.65% full; **63.5% DD**, corr to TQQQ 0.81: TQQQ beta with a timing overlay | TQQQ beta + time-of-day drift | **UNSUPPORTED** |
| 26 | `gap-capitulation-reversal` | Quiet, short-term-oversold QQQ decline on low volume reverses over 3 sessions | Cox–Peterson 1994; Campbell–Grossman–Wang 1993; Conrad–Hameed–Niden 1994; Lou–Polk–Skouras 2019 | **The cited volume literature finds the opposite sign**: high-volume declines reverse, not low-volume ones. The report admits this. The quiet subset is an in-sample 43-event slice (t=2.97) | Yes; 8 falsifiers | Weak: the core empirical fact contradicts the cited mechanism | Yes: TQQQ/QQQ/BIL event | 8.30% dev / 4.64% full; 30 events / 24 trade starts; 10.3% DD | Short-term reversal / dip-buying | **UNSUPPORTED** |
| 27 | `daily-regime-minute-entry` | A 4% break below the TQQQ session open predicts continuation into the close; short TQQQ intraday | Gao et al. 2018; Baltussen et al. 2021; Cheng–Madhavan 2009 (contested); Ivanov–Lenkey 2018; Kaminski–Lo 2014 | Intraday momentum supports continuation, but the event study is fat-tail driven (mean −0.269%, median ~0) and the synthetic inverse is not investable | Yes; 6 falsifiers | Partly; the sign is plausible, but the edge is tiny and short-side tail risk is large | Yes in form: synthetic −1× TQQQ | 0.91% dev / 61.7% DD; 1.0% full / 62.8% DD | Short TQQQ tail / intraday momentum | **UNSUPPORTED** |

### 1.3 Cross-cutting research-validity problems

1. **The two winners are not standalone tests.** `ratio-froth` is the banned
   165-day QQQ/TQQQ base plus a 4% stop plus a ratio overlay. `vol-scaled` is
   always-long TQQQ with inverse-vol sizing and a stop; its correlation to the
   old base is 0.755, above the rebuild's own 0.60 limit. Their high CAGR is
   TQQQ beta/timing, not evidence of a new independent edge. Comparing them to
   the standalone rebuilds on CAGR is apples-to-oranges.
2. **Several citations are overgeneralised.** The most serious:
   - `ratio-pairs` / `ratio-froth`: Avellaneda–Zhang is an accounting identity,
     not a predictive signal. The ratio is ~98% explained by QQQ extension plus
     variance (the report's own regression, R²=0.978), so the “new” information
     is mostly QQQ trend + low vol.
   - `gap-capitulation-reversal`: the cited volume literature says high-volume
     declines reverse; the strategy trades the low-volume subset. That is
     counter-evidence, not support.
   - `intraday-mean-reversion` / `winner-ensemble` / `drawdown-stop-overlay`:
     Nagel (2012) and Campbell–Grossman–Wang (1993) are cross-sectional
     reversal/liquidity results, used here as time-series event rules.
   - `intraday-seasonality` / `letf-rebalance-flow` / `stop-reentry-recovery`:
     Cheng–Madhavan and the LETF-flow papers document rebalancing/tracking
     error, not a predictable next-day reversal. Ivanov–Lenkey (2018) is the
     explicit counter-evidence.
   - `ml-classifier`: “unsupervised” k-means is followed by a supervised
     cluster→asset map using forward returns; the regime literature does not
     validate that specific mapping.
   - `opening-range-breakout`: the cited ORB literature mostly says ORB fails
     after costs; the failed-breakdown reclaim is a practitioner pattern with
     no direct academic test.
3. **Many “standalone” strategies are low-exposure beta vehicles.** Event-risk
   is 29% TQQQ; intraday-seasonality ~11%; intraday-mean-reversion ~4.35% of
   minutes; gap-capitulation ~5–7%; stop-reentry has 1 event; volume-orderflow
   has 3 events. A 10–30% exposure strategy cannot compete with 100% TQQQ on
   CAGR. That is expected, not a bug.
4. **Thin samples and in-sample threshold selection.** gap-capitulation (30
   events), stop-reentry (1), volume-orderflow (3), dynamic-leverage (~5
   entries), vol-kelly (few), drawdown-regime (5–8 windows), opening-range
   (unknown but likely <100) cannot support a claim of a durable edge. Several
   thresholds were chosen from the same dev sample (gap-capitulation’s quiet
   subset, intraday-mean-reversion’s 3.0% at the edge of a 2.5–3.0 plateau,
   event-risk’s 4-before/2-after window).
5. **The reports are pre-registrations, not post-test reports.** All 26
   `report.md` files still say “not tested / PENDING / no result.json” while
   `result.json` exists and the SUMMARY quotes results. The pre-registration is
   a strength, but the lack of a post-test reconciliation is a reproducibility
   failure: the reader cannot see which rules changed and which numbers are
   from which code version.

---

## 2. Benchmarks and per-strategy performance

### 2.1 Benchmarks

| Window | TQQQ CAGR / DD / Sharpe | QQQ CAGR / DD / Sharpe | Source |
|---|---:|---:|---|
| Full 2016-01-04 → 2026-10-23 | **37.54% / 81.68% / 0.82** | **19.64% / 35.11% / 0.92** | `web/public/data/compare/all.json` (daily closes) |
| Dev 2016-01-04 → 2023-12-29 | **36.72% / 82.29% / 0.82** | **19.67% / 37.30% / 0.94** | `result.json` benchmarks (1-minute marks) |
| 10y 2017-01-03 → 2026-10-23 | 39.38% / 82.29% | 20.67% / 37.30% | `TUNE_BRIEF.md` |
| Holdout 2024-01-02 → 2026-10-23 | 43.59% / 62.21% | n/e | `SUMMARY.md` |

The full-window TQQQ number is slightly below the 10y number because 2016 was
a weak year and 2022 was a −79% TQQQ year. The QQQ benchmark is the fair
risk-adjusted comparison: 35% DD vs TQQQ's 82%.

### 2.2 Published full-window table (all 27, from `all.json`)

`Stale?` is the confirmed full-curve/current-code mismatch from §3. Full
metrics are daily-close; dev metrics are the current `result.json` 1 bp
1-minute numbers.

| Slug | Full CAGR | Full DD | Full Sharpe | Dev CAGR (1 bp, 1m) | Dev DD | Corr to TQQQ (daily) | Stale? |
|---|---:|---:|---:|---:|---:|---:|---|
| `ratio-froth` | 62.21% | 36.65% | 1.43 | n/a (old base) | n/a | 0.64 | no dev result |
| `vol-scaled-crash-stop` | 51.32% | 37.88% | 1.26 | 51.46% | 39.29% | 0.80 | **yes** (curve dev 57.65%) |
| `intraday-seasonality` | 26.41% | 39.24% | 0.96 | 21.84% | 43.75% | 0.47 | no |
| `event-risk-overlay` | 22.20% | 36.97% | 0.96 | 26.94% | 39.04% | 0.44 | no |
| `ratio-pairs` | 20.42% | 33.94% | 1.13 | 18.96% | 34.59% | 0.84 | no |
| `ml-classifier` | 18.95% | 35.29% | 0.73 | 20.69% | 36.04% | 0.64 | **yes** (curve dev 17.90%) |
| `time-of-day` | 17.20% | 31.78% | 0.89 | 19.68% | 31.81% | 0.38 | no (ends 10-22) |
| `ml-crash-overlay-winner` | 15.07% | 23.33% | 0.76 | 15.80% | 22.42% | 0.52 | no |
| `intraday-momentum` | 14.65% | 63.55% | 0.61 | 13.51% | 63.98% | 0.81 | no |
| `intraday-mean-reversion` | 12.41% | 21.48% | 0.71 | 11.31% | 31.47% | 0.28 | no |
| `overnight-crash-filter` | 11.34% | 26.98% | 0.81 | 10.37% | 27.62% | 0.42 | no |
| `letf-rebalance-flow` | 7.80% | 42.98% | 0.40 | 13.20% | 41.80% | 0.48 | no |
| `risk-parity-hrp` | 6.49% | 17.89% | 0.69 | 5.70% | 18.46% | 0.88 | no |
| `dual-speed-regime` | 5.15% | 36.93% | 0.35 | **28.76%** | 45.45% | 0.38 | **yes** (curve dev 5.89%) |
| `gap-capitulation-reversal` | 4.64% | 10.63% | 0.82 | 8.30% | 10.26% | 0.23 | **yes** (curve dev 4.18%) |
| `winner-ensemble-blend` | 3.04% | 30.53% | 0.33 | 0.30% | 32.67% | 0.42 | no |
| `volume-orderflow` | 2.49% | 13.11% | 0.36 | 0.87% | 16.66% | 0.12 | no |
| `dynamic-leverage-throttle` | 2.38% | 15.30% | 0.54 | 5.24% | 9.16% | 0.26 | no |
| `gap-fill-fade` | 2.21% | 0.38% | 6.53 | 1.43% | 0.48% | −0.06 | no |
| `stop-reentry-recovery` | 2.05% | 1.25% | 5.09 | 1.25% | 1.81% | −0.13 | no |
| `daily-regime-minute-entry` | 2.04% | 62.82% | 0.20 | 0.91% | 61.74% | −0.27 | **yes** (curve dev −0.05%) |
| `ensemble-signals` | 1.34% | 75.91% | 0.20 | −6.34% | 76.04% | 0.71 | **yes** (curve dev −5.21%) |
| `vol-kelly-overlay` | 1.03% | 16.50% | 0.17 | 1.81% | 19.22% | 0.21 | no |
| `drawdown-regime` | −0.11% | 47.55% | 0.07 | **17.20%** | 49.02% | 0.22 | **yes** (curve dev −1.64%) |
| `donchian-breakout` | −0.94% | 35.77% | 0.01 | **13.40%** | 15.02% | 0.54 | **yes** (curve dev −3.42%) |
| `opening-range-breakout` | −1.32% | 19.99% | −0.33 | −2.10% | 17.22% | 0.20 | no |
| `drawdown-stop-overlay` | −2.37% | 55.33% | 0.06 | **−9.25%** | 63.09% | 0.44 | **yes** (curve dev −1.75%) |

**How many beat TQQQ on the published full window?** Two: `ratio-froth`
(+24.7 pp CAGR) and `vol-scaled-crash-stop` (+13.8 pp). Both are the
overlay/high-beta cases above. On the current dev window, the same two beat
TQQQ, plus none of the standalone rebuilds. `dual-speed-regime` (28.76% dev)
and `drawdown-regime` (17.20%) may move up after their stale curves are
regenerated, but neither is close to TQQQ's dev 36.72%.

**Risk-adjusted, the picture is different.** Full Sharpe:
`ratio-pairs` 1.13, `intraday-seasonality` 0.96, `event-risk` 0.96,
`time-of-day` 0.89, `ratio-froth` 1.43, `vol-scaled` 1.26 vs TQQQ 0.82.
On Calmar (CAGR/DD), `ratio-froth` 1.70, `vol-scaled` 1.35,
`intraday-seasonality` 0.67, `event-risk` 0.60, `ratio-pairs` 0.60,
`time-of-day` 0.54 vs TQQQ 0.46. So the rebuilds are not uniformly “bad”;
they are lower-return, lower-risk or diversifying streams. The user's
question is a CAGR question, and on CAGR most cannot compete by design.

**Exposure and fills.** A complete exposure table was not finished before the
stop. What is known from the reports/result files:

- `ratio-froth`: ~78% risk-on; 21.5% of sessions hold QQQ instead of TQQQ;
  889 fills/10y (report).
- `vol-scaled`: `tqqq_time` 0.7195 (72% of dev minutes), 3,950 fills dev.
- `event-risk`: ~29% of sessions in TQQQ.
- `intraday-seasonality`: ~11% of bars.
- `intraday-mean-reversion`: 4.35% of minutes; 353 fills dev.
- `gap-capitulation`: ~5–7% bar exposure; 97 fills dev; 30 events.
- `risk-parity`: 15–25% equity (design).
- `drawdown-regime`: 15–25% exposure (design).
- `dual-speed`: intraday 10:30–15:30 only (design).
- `time-of-day`: 40–50% of nights (design).
- `overnight-crash-filter`: ~50% of calendar time (design).
- `intraday-momentum`: one of TQQQ/QQQ/BIL each week (design).
- `ml-classifier`: TQQQ ~15%, QQQ ~55%, BIL ~30% (design).
- `ml-crash`: TQQQ ~15%, QQQ ~55%, BIL ~30% (design).
- `ratio-pairs`: QQQ ~90% in the middle state; TQQQ 40% + QQQ 30% in
  capitulation; BIL in froth.
- `stop-reentry`: 1 event; `volume-orderflow`: 3 events; `gap-fill-fade`:
  near-empty (0.38% DD); `vol-kelly`: few events.

Every strategy uses next-open fills and the 2% band through `bt.run`; the
engine is long-only and enforces weights ≥0 and row sum ≤1. `fills` is
reported in `result.json`; the full table was not extracted.

---

## 3. Full-curve audit (confirmed data bug)

### 3.1 The stale-curve finding

For each `curves_full/<slug>.json`, I computed the 2016-01-04 → 2023-12-29
CAGR/DD from its daily values and compared it with the current
`result.json` dev 1 bp CAGR/DD. A match within normal daily-vs-1-minute
rounding is expected; a multi-point gap means the curve was generated from a
different code version.

**Confirmed stale (dev-slice CAGR difference > ~2 pp):**

| Slug | Curve dev CAGR | Current dev CAGR | Delta | Curve mtime | `strategy.py` mtime | Verdict |
|---|---:|---:|---:|---|---|---|
| `dual-speed-regime` | 5.89% | 28.76% | **−22.88 pp** | 12:21:57 | 12:38:08 | stale: curve predates code |
| `drawdown-regime` | −1.64% | 17.20% | **−18.84 pp** | 12:14:48 | 12:31:20 | stale |
| `donchian-breakout` | −3.42% | 13.40% | **−16.82 pp** | 12:23:55 | 12:31:50 | stale |
| `drawdown-stop-overlay` | −1.75% | −9.25% | **+7.50 pp** | 12:14:42 | 12:20:00 | stale; website is too kind |
| `vol-scaled-crash-stop` | 57.65% | 51.46% | **+6.18 pp** | 12:53:58 | 12:31:20 | mismatch despite newer mtime; full-panel generation bug suspected |
| `gap-capitulation-reversal` | 4.18% | 8.30% | **−4.12 pp** | 12:16:51 | 12:31:20 | stale |
| `ml-classifier` | 17.90% | 20.69% | **−2.79 pp** | 12:54:01 | 11/26 17:43 | mismatch; full-period refit/feature-window difference suspected |
| `daily-regime-minute-entry` | −0.05% | 0.91% | **−0.96 pp** | 12:14:19 | 12:40:02 | stale (smaller) |
| `ensemble-signals` | −5.21% | −6.34% | **+1.12 pp** | 12:21:58 | 12:31:33 | stale (smaller) |

**Matched (daily-vs-1m rounding only):** `event-risk-overlay`,
`gap-fill-fade`, `intraday-mean-reversion`, `intraday-momentum`,
`intraday-seasonality`, `letf-rebalance-flow`, `ml-crash-overlay-winner`,
`overnight-crash-filter`, `ratio-pairs`, `risk-parity-hrp`,
`stop-reentry-recovery`, `time-of-day`, `vol-kelly-overlay`,
`volume-orderflow`, `winner-ensemble-blend`, `opening-range-breakout`,
`dynamic-leverage-throttle`.

The mtime pattern is consistent with the stale set: 16 of 27 curves are older
than their `strategy.py`, and the largest gaps are exactly the strategies that
were edited after the first full-curve capture. The website is therefore
ranking a mix of code versions. This is a **confirmed export/data bug**, not a
research-hypothesis result.

**Impact on the ranking:** the stale curves understate `dual-speed-regime`,
`drawdown-regime`, `donchian-breakout`, `gap-capitulation-reversal`, and
`ml-classifier`; they overstate `vol-scaled-crash-stop` and
`drawdown-stop-overlay`. Regenerating them is the first fix. It will not make
any standalone rebuild beat TQQQ, but it will change the middle of the table
substantially.

### 3.2 Generator risks (not all confirmed)

`capture_full.py` extends a strategy by replacing the literal `"2023-12-29"`
with `"2026-10-23"` in the source, runs `main()`, captures every `bt.run` /
`bt.simulate` result, and selects the captured run whose 2016–2023 slice
matches the stored dev CAGR/DD within 5e-4. Risks:

1. **Literal-only rewrite.** If a strategy uses a different dev-end constant
   (e.g. `DEV_END = "2023-12-29"` is fine, but a computed date or a different
   string is not), the replacement fails silently and the full run stops at
   2023. The stale curves show this class of failure is real.
2. **Main() may tune.** If `main()` runs a grid and picks the best variant on
   the full panel, the captured full curve is selected on 2024–2026. The
   matching step only checks the dev slice, so a full-period-selected run can
   still pass if its dev slice happens to match. This is a look-ahead risk in
   the generator, not in `build_weights`.
3. **Variant capture ambiguity.** `captured` includes every run; the first
   match wins. If two variants have similar dev CAGR/DD, the wrong curve can
   be saved.
4. **Result.json backup/restore.** The script writes `result_dev_backup.json`
   and restores it in `finally`; an interrupted run can leave the backup or a
   modified result. Not observed, but fragile.

`full_missing.py` and `full_direct.py` avoid the literal rewrite but call
`build_weights` directly on the full panel. That is safe only if
`build_weights` is strictly causal and has no full-sample calibration. The
`ml-classifier` and `vol-scaled` mismatches are warnings that this assumption
does not hold for every strategy.

`export_compare_full.py` computes metrics from daily close equity and
normalises each series by its first non-null value. It does not check that a
curve reaches 2026-10-23. `time-of-day` ends 2026-10-22, one session short;
the stats use its own last date, so its CAGR is over a slightly shorter
window. That is a minor alignment bug, not a strategy bug.

### 3.3 Which curves are “current code”?

The only curves that match the current `result.json` dev slice are the 17
listed above. For the other 9, the website's full-window numbers are not the
current strategy. This alone can explain part of “why the website shows 27
strategies with poor results”: the website is not showing 27 current
strategies.

---

## 4. Implementation / spec audit (partial)

### 4.1 What was checked

- All strategies call `bt.run` / `bt.simulate` / `bt.run_many`; the engine
  enforces next-bar-open fills, long-only weights, row sum ≤1, 2% band, and
  1 bp headline. `bt.load_1m` truncates the 21 half-days at 13:00 and repairs
  the BIL 2017 reverse split. `bt.panel` uses QQQ's calendar and
  `ffill().bfill()`.
- `bt.stats` marks equity on 1-minute bars for the dev result; the website
  metrics are daily close. Both are internally consistent, but they are not
  the same measurement.
- The full-curve generators were read; the stale-curve comparison above is
  the main confirmed finding.
- The reports' rules were compared with the result summaries for the large
  underperformers and the near-empty signals. No line-by-line diff of every
  `strategy.py` was completed.

### 4.2 Confirmed implementation / reporting issues

1. **Stale full curves** for the 9 strategies in §3.1. Confirmed by
   dev-slice mismatch and mtimes. This is the single largest data bug found.
2. **Reports not updated after the run.** All 26 reports still say “not
   tested / PENDING”; `result.json` and `SUMMARY.md` contain results. This is
   a spec/report mismatch. It also means the reports' rule descriptions may
   not match the final tuned code. The `_before_tune` directories exist for
   21 strategies, but only `intraday-mean-reversion` has a `DIAGNOSIS.md`
   documenting the change. The other 20 tuned strategies have no public
   before/after record.
3. **SUMMARY numbers are stale relative to `result.json`.** Examples:
   `daily-regime-minute-entry` SUMMARY −0.04% vs current result 0.91%;
   `gap-capitulation-reversal` 4.18% vs 8.30%; `drawdown-stop-overlay`
   −1.74% vs −9.25%; `dual-speed-regime` 5.38% vs 28.76%. The SUMMARY was
   written before the final tuning/run and not regenerated.
4. **`time-of-day` full curve ends 2026-10-22**, one session before the
   uniform end. Minor.
5. **`vol-scaled-crash-stop` full curve (57.65% dev) does not match its own
   `result.json` (51.46%) even though the curve is newer.** Suspected
   full-panel generation difference (sizing/ATR warm-up/variant). This is a
   confirmed mismatch, not yet root-caused.
6. **`ml-classifier` full curve (17.90% dev) does not match `result.json`
   (20.69%).** Suspected full-period feature/refit difference. Confirmed
   mismatch, not root-caused.
7. **Near-empty signals are real, not just low exposure.** `stop-reentry` has
   1 event in 2,012 sessions; `volume-orderflow` has 3; `gap-fill-fade` has a
   0.38% max DD and 1.43% CAGR; `dynamic-leverage` has ~5 entries. These are
   threshold/spec failures (the event definition is too restrictive), not
   merely “the strategy is in BIL”. They should be retired or re-specified
   before being presented as strategies.
8. **The synthetic inverse implementation** in `daily-regime-minute-entry`
   and `gap-fill-fade` is not an investable instrument. It is a valid
   research device for measuring a short effect, but a website comparison to
   long-only TQQQ is unfair. The reports say this; the leaderboard does not.

### 4.3 Not yet checked (handoff)

- Line-by-line spec-vs-code for all 26 `strategy.py` files: thresholds,
  `<` vs `<=`, which bar a decision uses, weight index, half-day handling,
  warm-up, and weight sum. The independent `audit/report.md` claims all clean,
  but its scope and current-code coverage were not re-verified.
- Look-ahead cut tests at 2020-03-12 11:07 and 2022-09-13 10:41 for every
  current strategy.
- Whether any `build_weights` uses a 100–250-day moving average as a gate.
  Static grep was planned but not completed.
- Whether any full-curve generator uses 2024–2026 to select parameters.
- Same-exposure benchmark (static TQQQ/BIL or QQQ/BIL mix at each strategy's
  average exposure) for every strategy.
- Exact average exposure, fills, turnover, and cost drag for every strategy.
- The `2026-05-26` bad-print impact: `bt.load_1m` does not clean the repeated
  TQQQ 88.62 high or the QQQ high/low corruption. Close-to-close marks are
  unaffected, but any high/low-based rule (donchian, opening-range, ATR stop)
  could be distorted on that holdout day. Not yet checked per strategy.
- Whether the 2022-06-21 TQQQ low cluster triggers any stop in dev.

---

## 5. Root cause per strategy (provisional)

| Slug | Main root cause | Evidence |
|---|---|---|
| `ratio-froth` | Overlay-only on the banned 165-day base + stop; high TQQQ/QQQ exposure | Report §3 and §4.5; 62.2% full vs TQQQ 37.5%; corr 0.64 |
| `vol-scaled-crash-stop` | High TQQQ exposure (72%) + stop; not independent (corr 0.755); stale curve overstates | `result.json` corr 0.755, `tqqq_time` 0.7195; curve/dev mismatch |
| `intraday-seasonality` | Genuine event edge, but mechanism not identified; 11% exposure; possible generic reversal | 26.4% full / 21.8% dev; 11% bars; overnight leg only 1.0% in preliminary |
| `event-risk-overlay` | Calendar fact is real but small; 29% TQQQ beta; window chosen in-sample | 96 events, −83.9 bp o2c; 22.2% full on 29% exposure |
| `ratio-pairs` | Mostly QQQ beta; ratio timing adds ~1–2 pp; 90% QQQ | 18.96% dev ≈ QQQ 18.9%; 20.42% full vs QQQ 19.64%; corr to TQQQ 0.84 |
| `ml-classifier` | Regime model is QQQ-like; full-curve mismatch | 20.69% dev, corr 0.64; curve 17.90% |
| `time-of-day` | Conditional overnight beta; 17.2% ≈ static 45% TQQQ mix; sign contested | 40–50% duty cycle; 17.2% full; report V4 opposite sign |
| `ml-crash-overlay-winner` | Decay classifier weak; QQQ/BIL rotation; 15.8% dev / 22% DD | Original AUC ≈0.50; 15.8% dev |
| `intraday-momentum` | TQQQ beta with weekly timing; 63.5% DD; corr 0.81 | Report §12; full 14.65%/63.55% |
| `intraday-mean-reversion` | Low exposure (4.35%); event edge p=0.068, 2022–23 flat | 88 events/43 clusters; 11.31% dev |
| `overnight-crash-filter` | Two-leg timing underperforms a static 50% TQQQ mix; day leg weak | 10.37% dev; 50% exposure; session mean negative in 25–30% vol |
| `letf-rebalance-flow` | Daily QQQ–SPY proxy does not test the late-day flow; high DD | 13.2% dev / 41.8% DD; report §11 |
| `risk-parity-hrp` | Low-exposure QQQ/TQQQ mix; corr 0.88; Sharpe 0.69 < QQQ 0.92 | 5.70% dev / 18.46% DD |
| `dual-speed-regime` | **Unresolved**: current dev 28.76% vs stale full 5.15%; either stale curve or dev-only bug | mtime; dev-vs-curve delta −22.88 pp |
| `gap-capitulation-reversal` | Thin 30-event sample; low-volume sign contradicts literature; low exposure | 8.30% dev; 30 events; 10.3% DD; curve 4.18% |
| `winner-ensemble-blend` | Both streams weak; allocation adds nothing; 0.3% dev | 0.30% dev / 32.67% DD |
| `volume-orderflow` | Near-empty (3 events); cross-sectional evidence misapplied | SUMMARY; 0.87% dev |
| `dynamic-leverage-throttle` | Near-empty (~5 entries); underpowered | 5.24% dev / 9.16% DD |
| `gap-fill-fade` | Near-empty; old event t=1.60/0.92; synthetic short | 1.43% dev / 0.38% DD |
| `stop-reentry-recovery` | Near-empty (1 event); threshold too tight | SUMMARY; 1.25% dev |
| `daily-regime-minute-entry` | Short-side fat-tail event; synthetic inverse; 0.91% dev / 61.7% DD | 0.91% dev; corr −0.27 |
| `ensemble-signals` | Vol state machine failed; −6.34% dev / 76% DD | result.json |
| `vol-kelly-overlay` | Few events; 1.81% dev | result.json |
| `drawdown-regime` | Negative prior; 5–8 windows; 49% DD; curve stale | 17.20% dev; AQR/Bonini negative |
| `donchian-breakout` | Alignment ladder own; 13.4% dev; curve stale | 13.40% dev; Turtle-only provenance |
| `opening-range-breakout` | Pattern has no edge; −2.10% dev | result.json |
| `drawdown-stop-overlay` | Failed spring; −9.25% dev / 63% DD; curve stale and too kind | result.json |

---

## 6. Confirmed fixes and impact

**No fixes were applied.** The stop instruction arrived before the audit could
regenerate curves or edit code. The confirmed fix list, in priority order:

1. **Regenerate every stale full curve from the current `strategy.py`** using
   a generator that does not rewrite dates by string replacement and does not
   call `main()` variants. Use the exact `build_weights` path and assert the
   2016–2023 slice matches `result.json` before saving. Expected impact:
   `dual-speed-regime`, `drawdown-regime`, `donchian-breakout`,
   `gap-capitulation-reversal`, and `ml-classifier` move up;
   `vol-scaled-crash-stop` and `drawdown-stop-overlay` move down. The website
   ranking changes materially, but no standalone rebuild starts beating TQQQ.
2. **Fix `time-of-day`'s missing 2026-10-23 session** (or document the
   one-session-late end).
3. **Re-run or remove the `vol-scaled` and `ml-classifier` full curves** after
   root-causing their dev-slice mismatch.
4. **Update each `report.md` with the post-test results and the tuning
   before/after**, or add a single `RESULTS.md` per strategy. The current
   reports are pre-registrations and are misleading as “reports”.
5. **Regenerate `SUMMARY.md`** from current `result.json`; the current table
   is stale for at least 4 strategies.
6. **Retire or re-specify the near-empty signals** (`stop-reentry-recovery`,
   `volume-orderflow`, `gap-fill-fade`, `dynamic-leverage-throttle`,
   `vol-kelly-overlay`) rather than presenting them as strategies.
7. **Label the two winners as overlay/high-beta** in any comparison, or
   exclude them from the “standalone rebuild” leaderboard. `ratio-froth` uses
   the banned 165-day base; `vol-scaled` fails its own correlation rule.

Impact of these fixes was **not measured** because no backtest was run after
the stop.

---

## 7. Corrected / provisional ranking

The published full-window ranking is not trustworthy for the 9 stale curves.
The best available current ranking is the **dev 1 bp, 1-minute** result from
`result.json`:

| Rank | Slug | Dev CAGR | Dev DD | Note |
|---:|---|---:|---:|---|
| — | TQQQ | 36.72% | 82.29% | benchmark |
| 1 | `vol-scaled-crash-stop` | 51.46% | 39.29% | high TQQQ exposure, corr 0.755 |
| 2 | `dual-speed-regime` | 28.76% | 45.45% | full curve stale; high-priority check |
| 3 | `event-risk-overlay` | 26.94% | 39.04% | 29% exposure; calendar |
| 4 | `intraday-seasonality` | 21.84% | 43.75% | 11% exposure; event |
| 5 | `ml-classifier` | 20.69% | 36.04% | QQQ-like; full curve stale |
| 6 | `time-of-day` | 19.68% | 31.81% | overnight beta |
| 7 | `ratio-pairs` | 18.96% | 34.59% | QQQ beta |
| 8 | `drawdown-regime` | 17.20% | 49.02% | few windows; full curve stale |
| 9 | `ml-crash-overlay-winner` | 15.80% | 22.42% | decay classifier |
| 10 | `intraday-momentum` | 13.51% | 63.98% | TQQQ beta |
| 11 | `donchian-breakout` | 13.40% | 15.02% | full curve stale |
| 12 | `letf-rebalance-flow` | 13.20% | 41.80% | proxy signal |
| 13 | `intraday-mean-reversion` | 11.31% | 31.47% | 4.35% exposure |
| 14 | `overnight-crash-filter` | 10.37% | 27.62% | two-leg timing |
| 15 | `gap-capitulation-reversal` | 8.30% | 10.26% | 30 events |
| 16 | `risk-parity-hrp` | 5.70% | 18.46% | low-beta QQQ mix |
| 17 | `dynamic-leverage-throttle` | 5.24% | 9.16% | ~5 entries |
| 18 | `vol-kelly-overlay` | 1.81% | 19.22% | few events |
| 19 | `gap-fill-fade` | 1.43% | 0.48% | near-empty |
| 20 | `stop-reentry-recovery` | 1.25% | 1.81% | 1 event |
| 21 | `daily-regime-minute-entry` | 0.91% | 61.74% | short synthetic |
| 22 | `volume-orderflow` | 0.87% | 16.66% | 3 events |
| 23 | `winner-ensemble-blend` | 0.30% | 32.67% | weak streams |
| 24 | `opening-range-breakout` | −2.10% | 17.22% | no edge |
| 25 | `ensemble-signals` | −6.34% | 76.04% | vol state machine |
| 26 | `drawdown-stop-overlay` | −9.25% | 63.09% | failed spring |
| — | `ratio-froth` | 61.56% (curve) | 36.65% | old base + overlay, not standalone |

Only `vol-scaled-crash-stop` (and `ratio-froth`, the old base) beats TQQQ's
dev CAGR. `dual-speed-regime` is the only standalone rebuild that comes close
on dev, and its full curve is stale. On full-window Sharpe, `ratio-pairs`,
`intraday-seasonality`, `event-risk`, `time-of-day`, `ratio-froth`, and
`vol-scaled` beat TQQQ; on Calmar, the same set plus `gap-capitulation` and
`intraday-mean-reversion`. That is the fairer comparison.

---

## 8. Short answer

**Is the research wrong, the implementation wrong, or is this expected?**

Mostly **expected, with a real data/export bug and some weak research**.

- **Expected:** TQQQ returned 37.5% CAGR over 2016–2026 with an 82% drawdown.
  Most rebuilds were explicitly designed to be low-exposure, low-correlation,
  event-driven, or defensive. A 10–30% exposure strategy cannot beat 100% TQQQ
  on CAGR; it can beat it on Sharpe, drawdown, or diversification. Judging
  them only on CAGR is an unfair comparison. The two that “massively”
  outperform are not counterexamples: `ratio-froth` is the old 165-day
  TQQQ/BIL base plus a 4% stop plus a ratio overlay, and `vol-scaled` is
  always-long TQQQ with inverse-vol sizing and a stop (correlation 0.755 to
  the old base). Their returns are TQQQ beta/timing, not independent alpha.
- **Implementation/data bug:** the website's full curves are stale for at
  least 9 of 27 strategies. The worst gaps are `dual-speed-regime`
  (current dev 28.76% vs curve 5.89%), `drawdown-regime` (17.20% vs −1.64%),
  and `donchian-breakout` (13.40% vs −3.42%). The website is not ranking 27
  current strategies. `vol-scaled` and `ml-classifier` also have unexplained
  full-curve/dev mismatches. `time-of-day` is one session short. These are
  confirmed bugs to fix before drawing conclusions.
- **Research weakness:** several hypotheses are not supported by their cited
  evidence. The clearest are `gap-capitulation-reversal` (the cited
  volume literature says the opposite sign), `ratio-pairs`/`ratio-froth`
  (the Avellaneda–Zhang identity is not a predictive signal; the ratio is
  ~98% QQQ trend + variance), `intraday-mean-reversion`/`winner-ensemble`
  (cross-sectional reversal used as a time-series event), and
  `letf-rebalance-flow` (a daily QQQ–SPY proxy does not test late-day flow).
  Several signals are effectively empty (`stop-reentry`: 1 event;
  `volume-orderflow`: 3) and should be retired, not tuned.

**What would change the answer:** after regenerating the stale curves, if
`dual-speed-regime`'s 28.76% dev result is real and holds over 2024–2026, it
would be the one standalone rebuild with a genuinely competitive return at a
lower drawdown. That is the single highest-value check for the main session.
If its full curve stays near 5%, the 28.76% dev result is likely a code-version
or look-ahead artifact and should be treated as a bug, not an edge.

---

## 9. Files created / modified

- Created: `research/revisit/WHY_UNDERPERFORM.md` (this file).
- Modified: none. No strategy, result, curve, website, or data file was
  changed. No commit or push was made.
