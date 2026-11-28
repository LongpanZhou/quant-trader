# Why the rebuilds underperform TQQQ — final audit

**Status:** complete, 2026-11-27. Data and pipeline fixes applied; website rebuilt.
No strategy was tuned in this audit, and no new strategy was added.
The earlier partial handoff is preserved as `WHY_UNDERPERFORM_partial.md`.

**Scope:** 27 published strategies (26 standalone rebuilds + the original
Ratio froth), uniform window 2016-01-04 → 2026-10-23, next-open fills, 2% band,
1 bp costs, daily-close marks on the website.

---

## 0. Bottom line

| | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| TQQQ buy & hold | **37.54%** | 81.68% | 0.82 |
| QQQ buy & hold | 19.64% | 35.11% | 0.92 |
| Ratio froth | **62.21%** | 36.65% | 1.43 |
| Vol-scaled crash system | **51.32%** | 37.88% | 1.26 |

Only two of 27 beat TQQQ on CAGR, and **neither is a standalone edge**:

- **Ratio froth** is the old banned 165-day QQQ/TQQQ base + 4% armed stop +
  the ratio overlay. The old base alone is 52.89% / 41.62%; it supplies
  **85.0% of the headline CAGR and 89.0% of the drawdown reduction** vs TQQQ,
  and its daily returns are 0.942 correlated with the full strategy. The
  overlay adds +9.3 pp CAGR / −5.0 pp DD; a fair 4%-on-QQQ stop reduces that
  to +7.8 / −5.1. The 0.18 / 200-day threshold came from a 35-point grid and
  was not pre-registered; its 584 froth days are only ~67 clustered episodes.
- **Vol-scaled crash system** is always-long TQQQ (72% of minutes) with
  inverse-vol sizing and a one-sided ATR stop. The stop is the dominant
  contributor: +15.4 pp CAGR / −25.1 pp DD over sizing-only. Its correlation
  to the old base is 0.755 (live 0.716), above the rebuild's own 0.60 gate. In
  the clean 2024-2026 implementation test it earns 36.19% vs TQQQ 44.93%; at
  10 bp the full-window CAGR falls to 29.1%, below TQQQ.

A static blend at each winner's average weights earns 28.90% / 60.02% (ratio)
and 32.12% / 67.48% (vol), so the timing and stops are doing real work. But the
work is **crash avoidance on TQQQ beta**, not a new return premium: both are
overlays, and their 2024-2026 segments were designed or tuned on overlapping
windows, so they are not clean holdouts.

Most rebuilds are 5–30% exposure, event-driven, or defensive by design. A
10–30% exposure book cannot beat 100% TQQQ on CAGR; it can beat it on Sharpe,
drawdown, or diversification. The fair risk-adjusted comparisons are:

- Full-window Sharpe: ratio-pairs 1.13, intraday-seasonality 0.96,
  event-risk 0.96, time-of-day 0.89, vs TQQQ 0.82.
- Calmar (CAGR/DD): ratio-froth 1.70, vol-scaled 1.35,
  intraday-seasonality 0.67, event-risk 0.60, ratio-pairs 0.60,
  time-of-day 0.54, vs TQQQ 0.46.

The research itself is mostly **not** sound: after the four deep reads,
**0 are sound, 8 plausible-but-weak, 12 unsupported, 7 overlay-only**.
The specific signs, thresholds, horizons, and universes are usually own tests,
not what the cited papers show.

There was also a real **data/versioning bug**: 8 published curves were captured
before the post-freeze tune, while their `result.json` files were rewritten by
the tune. The website uses the pre-tune curves; that freeze is now explicit and
validated. The post-tune variants are documented in §3, not adopted.

---

## 1. What was actually broken — and fixed

### 1.1 Website data

| Issue | Before | Fix | After |
|---|---|---|---|
| `ml-classifier` 2024-2026 | reused the Dec-2023 model | extend the monthly-refit literal `"2023-12-01"`; regenerate | 10y 21.05% → **17.93%**; full 2016-2026 **16.15%** (flat 2016 BIL) |
| `time-of-day` | ended 2026-10-22 | include the whole final session in `slice_idx`; regenerate | 2718 days, ends **2026-10-23**, 19.70% dev |
| `vol-scaled` dev block | 51.46% was the **full** 2016-2026 run, not dev | delete the date-agnostic `dev_panel.npz`; rerun | true dev **57.84%**; curve unchanged 51.32% full |
| 8 pre-tune curves | published curves did not match post-tune `result.json` | keep the pre-registered curves; record the freeze; fix the verifier | 27/27 curves validated, **0 stale** |
| Library text | Ratio froth said “2017-2023” | corrected | “2016-2026” |

### 1.2 Pipeline

- `capture_full.py` now rewrites all three dev-end literals
  (`2023-12-29`, `2023-12-30`, `2023-12-01`), includes the whole final dev
  session, normalizes mixed `\r`/`\n` line endings, deletes stale panel
  caches, refuses to overwrite a curve whose dev freeze differs by >2 pp
  unless `--force`/`--freeze-pre` is passed, and records `source_sha256`,
  `result_sha256`, `generated_at`, and `dev_result` in every curve.
- `export_compare_full.py` backfills a strategy that starts later
  (`ml-classifier`, 2017-01-03) with a flat cash segment, forward-fills a
  one-session-short curve, and warns on any coverage gap.
- `run_all.py --export` now calls the uniform 2016-2026 exporter, the library,
  and the catalog — not the old 2017-2023 exporter.
- `verify_full_curves.py` compares each curve to the freeze that actually
  reproduces it (`pre_tune` vs `current`) instead of calling a pre-registered
  curve stale against a post-tune result.
- `final_check.py` now checks 27 full curves, 2718 days, no nulls, and
  recomputes every metric from its own series. It passes.

**Not fixed, by design:** the post-tune mechanism changes and the research
validity failures. Those are findings, not data bugs, and adopting the tuned
variants now would be adding new strategies. See §3.

---

## 2. Research validity — final ranking

The first-pass handoff ranked 0 sound / 11 plausible / 14 unsupported /
2 overlay-only. The four deep reads changed several classifications —
five strategies moved to overlay-only — so the final table below supersedes it.

| # | Strategy | Verdict | Why |
|---:|---|---|---|
| 1 | `ratio-froth` (original) | **overlay-only** | Old 165-day base + 4% stop + overlay. Overlay alone 60.15% / 53.31%; the base does the work. Threshold post-hoc; 584 days ≈ 67 episodes. |
| 2 | `vol-scaled-crash-stop` | **overlay-only** | Always-long TQQQ, 72% of time; corr 0.755 > 0.60; event mean −0.27% (p=0.073); 3,950 dev fills. |
| 3 | `event-risk-overlay` | **overlay-only** | 28.6% TQQQ beta supplies almost all 26.9% CAGR; event premium ~1%/yr; permutation p=0.245. |
| 4 | `time-of-day` | **overlay-only** | F1 t=1.35; unconditional every-night 35.0% vs conditional 19.7%. The filter destroys the overnight premium it claims to time. |
| 5 | `risk-parity-hrp` | **overlay-only** | QQQ/TQQQ correlation 0.999 makes ERC a leverage choice; only 8 spike events; corr 0.78; Sharpe 0.69 < QQQ 0.92. |
| 6 | `ml-crash-overlay-winner` | **overlay-only** | Decay difference between TQQQ and QQQ states is 1–2 bp, p=0.47; a simple 20-day vol rule earns Sharpe 1.13 vs 0.81. |
| 7 | `dual-speed-regime` | **overlay-only** | Pre-registered intraday-only: 5.4%/1 bp, **−16.7%/5 bp**. Shipped variant adds `OVERNIGHT=True` and makes 28.8%; 90% of the gap is TQQQ overnight drift. |
| 8 | `ratio-pairs` | plausible-but-weak | Avellaneda–Zhang is an accounting identity; 97.8% of ratio extension is QQQ extension + variance; 18.96% dev ≈ QQQ 18.91%; ~90% QQQ. |
| 9 | `intraday-seasonality` | plausible-but-weak | 275 events, +70 bp, t=2.39; but the overnight leg earns −0.38%; the edge is next-day intraday dip-buying; −1.0% is the grid peak; 10 bp CAGR 7.6%. |
| 10 | `intraday-mean-reversion` | plausible-but-weak | 88 events, +0.99%, p=0.068, CI includes zero; 2020-21 +2.61% vs 2022-23 −0.49%; 3.0% threshold is a peak. |
| 11 | `overnight-crash-filter` | unsupported | “Day Destroys the Night” predictor is a ~7-year EWMA, not yesterday’s sign; F1 t=0.23, F2 t=−0.51; static vol-matched mix dominates. |
| 12 | `drawdown-regime` | plausible-but-weak | 8 episodes; 3 of 5 2022-23 episodes lost 12–14%; 49% DD; Sharpe 0.78 vs 0.92 for a constant 14% TQQQ mix. |
| 13 | `donchian-breakout` | plausible-but-weak | Pre-registered 5-min version lost 3.4%/yr; the shipped 1-hour version was chosen after; only +0.8 pp over a leverage-matched static mix. |
| 14 | `ml-classifier` | plausible-but-weak | QQQ-like: 20.7% dev vs QQQ 18.9%, Sharpe 0.81 vs 0.90; 23-feature k-means → forward-return map is own and the “unsupervised” label is misleading. |
| 15 | `letf-rebalance-flow` | unsupported | 13.2% CAGR is the 72nd percentile of a random-entry placebo (z=0.53); hold=3 is a cliff (h2 +0.3%, h3 13.2%); QQQ-beta version similar. |
| 16 | `gap-capitulation-reversal` | plausible-but-weak | 30 events, +6.03%, t=2.89; but 1.2× volume cap is knife-edge (1.0→2.80%, 1.5→1.25%); 20/24 trades are QQQ; stop removed post-holdout. |
| 17 | `dynamic-leverage-throttle` | plausible-but-weak | 6 entries (own gate ≥12); 5.2%/yr; all six cluster on known stress dates; effectively cash-plus. |
| 18 | `ensemble-signals` | unsupported | −6.3%/yr, 76% DD; 97.5% of placebo state machines beat it; neighbourhood flips to +10.2% at `stress_pct=0.9`. |
| 19 | `daily-regime-minute-entry` | unsupported | Event study is 165-day-gated, not ungated; largest motivating events are 2024 holdout; ungated dev +8 bp/event (t=0.45); synthetic short is not investable. |
| 20 | `drawdown-stop-overlay` | unsupported | −9.3%/yr; every one of 10 variants negative; “buy any −1% day” control +15.8%; failed spring pattern. |
| 21 | `gap-fill-fade` | unsupported | 25 events, +5.6 bp, t=1.01, p=0.15; CI includes zero; no-confirmation variant is better; 10 bp CAGR 0.79% below BIL. |
| 22 | `intraday-momentum` | unsupported | First-hour signal is inverted in its own diagnostics: True −1.19 bp vs False +68.79 bp (p=0.991); TQQQ state +5.0 bp vs QQQ +36.5 bp; corr 0.616 fails. |
| 23 | `opening-range-breakout` | unsupported | The only rigorous cited ORB study finds the family fails costs; dev −2.1%/1 bp, **−15.1%/5 bp**; reclaim is practitioner-only. |
| 24 | `stop-reentry-recovery` | unsupported | 1 event in 8 years; the “excess ≤ −1 pp” condition mostly captures permanent daily-reset drag, not temporary overshoot; untestable. |
| 25 | `vol-kelly-overlay` | unsupported | 11 events (own minimum 15); mean +0.015%, p=0.49; 2020-21 −4.3%. |
| 26 | `volume-orderflow` | unsupported | 3 events in 2,012 sessions; cross-sectional/monthly literature; CLV filter untested; below its own ~40-event gate. |
| 27 | `winner-ensemble-blend` | unsupported | Stream A +1.68%, Stream B −6.19%, blend +0.30%; placebo p=0.79; fails 5 bp. |

Counts: **0 sound · 8 plausible-but-weak · 12 unsupported · 7 overlay-only.**

### Cross-cutting validity problems

1. **The two winners are not standalone tests.** One is the banned old base;
   the other is high-beta TQQQ with a stop. Their returns are beta/timing, not
   a new premium.
2. **Citations support components, not the rules.** The clearest
   misapplications: `gap-capitulation` cites volume literature that says the
   opposite sign; `ratio-pairs` treats an accounting identity as a predictive
   signal; `intraday-mean-reversion` / `winner-ensemble` use cross-sectional
   reversal as a time-series event; `letf-rebalance-flow` uses a daily
   QQQ–SPY proxy that never tests late-day flow; `opening-range-breakout`
   cites ORB evidence that rejects the family.
3. **Thin samples and in-sample thresholds.** `stop-reentry` 1 event,
   `volume-orderflow` 3, `vol-kelly` 11, `dynamic-leverage` 6,
   `gap-capitulation` 30, `drawdown-regime` 5–8 windows. Several thresholds
   were chosen from the same dev sample (gap-capitulation’s volume cap,
   intraday-mean-reversion’s 3.0%, event-risk’s 4-before/2-after window).
4. **Reports are pre-registrations, not post-test reports.** All 26 still say
   “PENDING / not tested” in their body while `result.json` exists. Each now
   carries a dated pointer to this audit and `SUMMARY.md`, but the body is
   still the pre-registration; the tuning changes are documented only here.
   The pre-registration is a strength; the missing per-strategy change log is
   still a reproducibility gap.

---

## 3. Pre-registered vs post-tune (the versioning finding)

The 2026-11-27 tune edited 24 `strategy.py` files and rewrote every
`result.json`. The published curves were captured before most of that tune.
The website therefore shows the **pre-registered** freeze for the 8 curves
below; the current `result.json` is the post-tune variant. Both are preserved.

| Strategy | Pre-tune dev | Post-tune dev | What changed |
|---|---:|---:|---|
| `dual-speed-regime` | 5.38% | **28.76%** | `OVERNIGHT=True`, `IDLE="cash"`; 90% of the gap is the overnight flag |
| `drawdown-regime` | −1.64% | **17.20%** | drawdown-trough arming, daily-close breakout, fill moved to prior last bar |
| `donchian-breakout` | −3.38% | **13.40%** | signal bars 5-minute → 1-hour; ATR annualization |
| `drawdown-stop-overlay` | −1.74% | **−9.25%** | stop measured on TQQQ (was QQQ); state machine factored/fixed |
| `gap-capitulation-reversal` | 4.18% | **8.30%** | event-low stop **removed after the holdout**; entry target moved to the event day’s last bar |
| `daily-regime-minute-entry` | −0.05% | **0.91%** | synthetic short rebalanced −1× → constant-share NAV |
| `dynamic-leverage-throttle` | 2.65% | **5.24%** | pre-2016 Yahoo daily history; re-acceleration exit disabled |
| `ensemble-signals` | −5.21% | **−6.34%** | pre-2016 Yahoo daily history for the 252-day percentile |

### Protocol problems

- **`gap-capitulation-reversal` is the serious one.** Its event-low stop was
  removed after the holdout had been seen, moving dev CAGR 4.18% → 8.30%. That
  is exactly the selection the project rules forbid. The website keeps the
  pre-holdout curve (4.64% full); the post-holdout result is not published.
- **21 strategies were tuned after the reports were frozen.** Only
  `intraday-mean-reversion` has a `DIAGNOSIS.md`; the other 20 have no public
  before/after record.
- **The 2024-2026 segments of tuned strategies are not a clean holdout.** The
  2026-11-26 audit predates the tune, so its “look-ahead clean” verdicts cover
  the pre-tune code only. Any regenerated tuned curve is post-tune.
- **`intraday-momentum` is not a sign bug to fix.** The code implements the
  stated rule; the data rejects it (first-hour True −1.19 bp vs False
  +68.79 bp). The correct action is to mark it rejected, not flip the sign
  post-hoc.
- **`ratio-froth`’s QQQ stop is intentional.** Its report says “the 4% stop
  still applies while in QQQ,” which is effectively a ~1.3% QQQ stop. That is
  a different, tighter rule than the ablation implies — a research critique,
  not an implementation bug.

---

## 4. Near-empty signals

A dedicated audit found **no coding bug** in the six near-empty strategies.
Every event count matches an independent raw count from the 1-minute panel.
They are rare by design; do not loosen thresholds.

| Strategy | Raw events | Entries | Cause |
|---|---:|---:|---|
| `stop-reentry-recovery` | 1 day | 1 | 1 pp excess condition is mostly permanent decay; 3% drop alone has 282 days |
| `volume-orderflow` | 3 days | 3 | `CLV ≥ 0` on a down close occurs 6 times in 8 years |
| `gap-fill-fade` | 25 days | 25 | real sample, but 0.043% short exposure; low CAGR is BIL carry |
| `dynamic-leverage-throttle` | 32 days | 6 | 32 days cluster into 6 episodes |
| `vol-kelly-overlay` | 15 days | 11 | 4 signals arrive while a position is open |
| `gap-capitulation-reversal` | 30 days | 24 | 6 events extend an open hold; inside its 30–50 bar |

`result.json` “exposure” near 100% is BIL, not risk exposure. Actual mean
risk-asset weights: stop 0.0004%, volume 0.75%, gap-fill 0.043%, dynamic
1.17%, vol-kelly 0.91%, gap-cap 3.95%.

---

## 5. Corrected uniform table (website freeze)

2016-01-04 → 2026-10-23, daily-close marks, 1 bp costs. Source:
`web/public/data/compare/all.json`.

| Strategy | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| Ratio froth | 62.21% | 36.65% | 1.43 |
| Vol-scaled crash system | 51.32% | 37.88% | 1.26 |
| Intraday-seasonality (close-flow exhaustion) | 26.41% | 39.24% | 0.96 |
| OpEx cycle | 22.20% | 36.97% | 0.96 |
| Ratio-cycle standalone | 20.42% | 33.94% | 1.13 |
| Closing-pressure overnight carry | 17.21% | 31.78% | 0.89 |
| Unsupervised regime allocator | 16.15% | 36.60% | 0.67 |
| Leverage-decay timing | 15.07% | 23.33% | 0.76 |
| Time-of-day leverage ladder | 14.65% | 63.55% | 0.61 |
| Post-capitulation reversal | 12.41% | 21.48% | 0.71 |
| Night continuation / day reversal | 11.34% | 26.98% | 0.81 |
| Relative Nasdaq flow dip | 7.80% | 42.98% | 0.40 |
| Volatility-state risk parity | 6.49% | 17.89% | 0.69 |
| Intraday 60-minute trend | 5.15% | 36.93% | 0.35 |
| Quiet capitulation | 4.64% | 10.63% | 0.82 |
| Two-stream risk parity | 3.04% | 30.53% | 0.33 |
| Participation exhaustion | 2.49% | 13.11% | 0.36 |
| Volatility-shock recovery | 2.38% | 15.30% | 0.54 |
| Failed gap-up fade | 2.21% | 0.38% | 6.53 |
| LETF overshoot recovery | 2.05% | 1.25% | 5.09 |
| Crash-continuation short | 2.04% | 62.82% | 0.20 |
| Volatility contraction recovery | 1.34% | 75.91% | 0.20 |
| Vol-spike reflation | 1.03% | 16.50% | 0.17 |
| Deep drawdown recovery | −0.11% | 47.55% | 0.07 |
| Donchian alignment ladder | −0.94% | 35.77% | 0.01 |
| Opening-range failed-breakdown reclaim | −1.32% | 19.99% | −0.33 |
| Failed-breakdown spring | −2.37% | 55.33% | 0.06 |
| **TQQQ buy & hold** | **37.54%** | **81.68%** | **0.82** |
| **QQQ buy & hold** | **19.64%** | **35.11%** | **0.92** |

Only Ratio froth and Vol-scaled beat TQQQ on CAGR. On Sharpe, Ratio froth,
Vol-scaled, Ratio-cycle standalone, Intraday-seasonality, OpEx cycle and
Closing-pressure overnight carry beat TQQQ. On Calmar, the same set plus
Quiet capitulation and Post-capitulation reversal.

---

## 6. Answer

**Is the research wrong, the implementation wrong, or is this expected?**

Mostly **expected, with a real data/versioning bug, weak research, and several
post-hoc mechanism changes**.

- **Expected:** TQQQ returned 37.5% CAGR with an 82% drawdown over 2016-2026.
  Most rebuilds were designed to be low-exposure, event-driven, or defensive.
  They cannot beat 100% TQQQ on CAGR by construction; several beat it on
  Sharpe or Calmar. The two that “massively” outperform are not counterexamples:
  one is the banned old base, the other is high-beta TQQQ with a stop.
- **Data bug:** 8 published curves were pre-tune while `result.json` was
  post-tune. The website now shows the pre-registered freeze; the current
  variants are documented and preserved. `ml-classifier`, `time-of-day` and
  `vol-scaled` had separate window/refit defects, now fixed.
- **Research weakness:** the specific rules are usually own tests, not what
  the cited papers show. The clearest are `gap-capitulation` (opposite volume
  sign), `ratio-pairs`/`ratio-froth` (accounting identity used as a signal),
  `intraday-mean-reversion`/`winner-ensemble` (cross-sectional reversal used
  as a time-series event), and `letf-rebalance-flow` (daily proxy for a
  late-day flow).
- **Protocol:** `gap-capitulation` was changed after the holdout; 21
  strategies were tuned after their reports were frozen; only one has a change
  log. Those tuned variants are new strategies and need a fresh registration
  and a clean holdout, not a retrofit.

**What would change the answer:** a standalone strategy that beats TQQQ on
CAGR *and* survives costs, with a pre-registered rule, a clean holdout, and a
mechanism test that is not just TQQQ beta. None of the current 27 does that.
The post-tune variants that come closest — `dual-speed` overnight (25.17%
full), `donchian` 1-hour (~13% dev), `drawdown-regime` (~17% dev) — are new
strategies, not the extracted hypotheses.

---

## 7. Files and reproduction

**Audit evidence**
- `research/revisit/audit/validity_A.md` … `validity_D.md` — research validity
- `research/revisit/audit/curve_integrity.md` — 27-curve freeze audit
- `research/revisit/audit/dual_speed.md` — dual-speed code/spec audit
- `research/revisit/audit/near_empty.md` — six near-empty signals
- `research/revisit/audit/freeze_2026-11-27/` — frozen `result.json` + `strategy.py`
- `research/revisit/curves_full/_stale_backup_2026-11-27/` — pre-fix curves
- `research/revisit/WHY_UNDERPERFORM_partial.md` — earlier partial handoff

**Fixed pipeline**
- `research/capture_full.py` — three date literals, final-session cut, cache
  cleanup, source/result hashes
- `research/export_compare_full.py` — bfill/ffill coverage + warnings
- `research/verify_full_curves.py` — freeze-aware validation (0 stale)
- `research/revisit/final_check.py` — 27 curves, 2718 days, metric recomputation
- `research/revisit/run_all.py` — correct 2016-2026 export path
- `research/revisit/time-of-day/strategy.py` — final-session slice
- `research/revisit/ml-classifier/` — regenerated with monthly refit
- `research/revisit/vol-scaled-crash-stop/result.json` — true dev window

**Website** — `web/public/data/compare/all.json` (27 strategies + 2 benchmarks,
2718 days) and the rebuilt Next.js bundle.

No commit or push was made. `web/` remains ignored/untracked.
