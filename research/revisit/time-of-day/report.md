> **Post-test note (2026-11-27):** this file is the pre-registration, not
> the result. The frozen development result is in `../SUMMARY.md`; the
> full 2016-2026 audit, the post-tune variants and the research-validity
> verdicts are in `../WHY_UNDERPERFORM.md`. The published website curve is
> the freeze named in `../SUMMARY.md`.

# `time-of-day` — rebuild (closing-pressure overnight carry)

**Status: SPEC FROZEN, NOT YET TESTED.** Backtests are paused by the lead. No
number in this report has been produced. Every result cell below is `PENDING`
and will be filled by a single authorised run of `strategy.py`, which writes
`result.json`.

---

## 1. The idea, and why it is not the old overlay

The original strategy held **TQQQ every night** (15:59 → 10:01) and used a
165-day QQQ trend gate to decide whether to hold at all. Its report itself says
the gate does most of the risk work and that the unconditional overnight block
is the return engine.

Removing that gate leaves "buy TQQQ every night", which is exactly the residue
the 2026-11-26 clarification prohibits. So this rebuild keeps the *clock* — the
one thing that is genuinely this strategy's own — and replaces the *reason to
hold* with a mechanism that comes from the closing auction rather than from a
slow trend:

> The last 30 minutes of the session are the only reliably negative block of the
> day. That selling is price pressure, not information, and it is reversed when
> liquidity returns the next morning. Therefore the overnight block should pay
> **more after a sold close than after a bought close**, and the strategy should
> hold only the nights that follow genuine closing pressure.

The old strategy could not express this: it was unconditional (modulo the trend
gate) and binary. This one is conditional, continuous in size, and its gate is a
statistic of the strategy's *own* block returns rather than of the index level.

## 2. Hypothesis

- **H1.** The overnight+first-30m block return is a decreasing function of the
  QQQ return over the last 30 minutes of the preceding session. Holding only
  after negative closing blocks beats holding every night.
- **H2.** The conditional edge dies in high-volatility states, so the sleeve must
  also require the block's own realised volatility to be within 1.5× its
  60-session median.
- **H0.** Closing-block information is worthless and the conditional strategy is
  a random subset of nights.

The direction is genuinely contested in the literature: the cross-sectional
open literature (Berkman et al. 2012) says the open is temporarily inflated and
then reverses, which supports H1; the market-level intraday-momentum literature
(Gao et al. 2018) says the close continues the morning, which would support the
opposite sign. Variant **V4** runs the opposite sign explicitly, so the sign is
measured, not assumed.

## 3. Specification (frozen)

| element | value |
|---|---|
| Universe | TQQQ long (3× QQQ); cash. BIL only in variant V5. |
| Timeframe | 1-minute bars, regular session only |
| Decision | once per session, at 15:58 ET, using data through bar `last-1` |
| Entry | open of the session's **last** 1-minute bar (~15:59; 12:59 on half days) |
| Exit | open of the next session's **32nd** bar (~10:01) |
| Holding period | ≈ 17 hours per active night |
| Closing signal | `c30` = QQQ log return, 15:29 close → 15:58 close (bar offsets, so half days work) |
| Signal normaliser | `|c30| >= 0.5 × median(|c30|, previous 20 sessions)` |
| Risk state | `v` = annualised stdev of the previous 10 *completed* block log returns |
| Risk reference | `m` = median of `v` over the previous 60 sessions |
| Gate | `sign(c30) == -1` **and** `|c30| >= 0.5·median` **and** `v <= 1.5 m` |
| Size | `min(1, 0.40 / v)` when the gate is on, else 0 |
| Leverage | none beyond TQQQ's own 3× daily reset; weights ∈ {0} ∪ (0, 1] |
| Shorts | none |
| Costs tested | 1 bp (headline), 5 bp, 10 bp |

**Causality.** A block entered on session *k* ends at ~10:01 of session *k+1*, so
at 15:58 of session *k* the newest completed block is *k−1*. The `c30` of
session *k* uses closes up to bar `last−1`, and the entry fills at the open of
bar `last`, so the signal never sees the fill price. The magnitude reference uses
only the previous 20 sessions.

**No shared base.** No 100–250-day moving average of QQQ, TQQQ, SPY or NDX
appears in the strategy path. `baseline_weights()` in `strategy.py` is a
separable function used *only* to measure the correlation requirement; it is
never called by `build_weights()` and never touches the weights.

## 4. Pre-registered variants (6)

| id | rule | role |
|---|---|---|
| V0 | unconditional: every night, size 1 | reference / the old residue |
| V1 | `c30 < 0` only, size 1 | isolates the conditioning (F2) |
| V2 | vol gate only, size 1 | isolates the risk state |
| **V3** | **full: closing gate + vol gate + `0.40/v` sizing** | **the strategy** |
| V4 | full but `c30 > 0` | the momentum branch, settles the sign |
| V5 | full but BIL instead of cash while flat | does bill carry pay for the round trips? |

Neighbourhood (±1 step around V3, reported in full including losing cells):
`vol_look` 5/10/20 · `ref_look` 40/60/90 · `vol_mult` 1.25/1.50/2.00 ·
`close_window` 20/30/45 · `close_min_z` 0.0/0.5/1.0 · `vol_target` 0.30/0.40/0.50.

Parameters are accepted only if V3 sits on a **plateau**, not a peak.

## 5. Falsifiers and decision rule

| id | test | fail action |
|---|---|---|
| F1 | mean block return after sold close exceeds after bought close by ≥5 bp/night, t ≥ 1.5 | if reversed, run V4 once; if V4 also fails → retire |
| F2 | V1 (conditioning) beats V0 (unconditional) on dev CAGR at 1 bp, both size 1 | retire as overlay-only |
| F3 | dev max DD ≤ 45% and Sharpe ≥ 0.70 at 1 bp | reject |
| F4 | conditional sign holds in ≥2 of 3 dev sub-periods | reject |
| F5 | 200-shuffle placebo: real dev CAGR above the placebo distribution, p < 0.10 | reject |
| F6 | dev daily-return correlation with the 165-day base < 0.60 | reject |
| F7 | at 5 bp still beats TQQQ buy-and-hold on dev | mark `fragile`, not `passed` |

If F2 fails the honest outcome is `retired_overlay_only`: the clock alone is the
old residue and the closing condition adds nothing.

`strategy.py::decide()` maps F1–F7 to the `status` field mechanically
(`passed` / `fragile` / `retired_overlay_only` / `rejected`); the status is never
typed into `result.json` by hand.

## 6. Results — PENDING

All cells below are placeholders. Nothing has been run.

### 6.1 Development, 2016-01-04 → 2023-12-29

| variant | 1 bp CAGR | 1 bp DD | 1 bp Sharpe | 5 bp CAGR | 5 bp DD | 10 bp CAGR | 10 bp DD | fills | corr vs 165d |
|---|---|---|---|---|---|---|---|---|---|
| V0 unconditional | PENDING | | | | | | | | |
| V1 close only | PENDING | | | | | | | | |
| V2 gate only | PENDING | | | | | | | | |
| **V3 full** | **PENDING** | | | | | | | | |
| V4 opposite sign | PENDING | | | | | | | | |
| V5 BIL idle | PENDING | | | | | | | | |

### 6.2 Correlation numbers (required by the brief)

- `corr_vs_165d_baseline` (dev, daily returns): **PENDING**, expected 0.35–0.55.
- `max_corr_vs_other_rebuilds`: **PENDING** — no other rebuild exists in
  `research/revisit/` at the time of writing, so this is left `null` for the lead
  to fill after the set is built.

### 6.3 Sub-periods (1 bp)

| variant | 2016–19 | 2020–21 | 2022–23 |
|---|---|---|---|
| V1 close only | PENDING | | |
| **V3 full** | **PENDING** | | |
| V0 unconditional | PENDING | | |

### 6.4 Overfitting controls

- variants tried: **6** (+ 1 full six-way neighbourhood grid).
- ±1-step neighbourhood: PENDING.
- placebo (200 shuffles of which nights are active, same count and sizes):
  PENDING.
- event count: the number of active nights and the number of gate switches is
  PENDING; if active nights < 100 the F1 bootstrap p-value is reported as well.

### 6.5 Overlapping windows (produced once, after the freeze)

| window | 1 bp CAGR | 1 bp DD | 5 bp CAGR | 5 bp DD |
|---|---|---|---|---|
| 10y 2017-01-03 → 2026-10-23 | PENDING | | | |
| 5y 2021-10-25 → 2026-10-23 | PENDING | | | |
| holdout 2024-01-02 → 2026-10-23 | left for the lead | | | |

The 10y and 5y windows overlap the holdout and are produced only after the
parameters are frozen; they are recorded for comparability with the original
(10y 49.23%/42.66%, 5y 28.89%/34.54% at 1 bp) and are not used for any decision.

## 7. Known weaknesses, stated in advance

1. **The sign of the closing→overnight link is the least certain part.** If it
   runs the other way the strategy is V4, and if neither works the idea is dead.
2. **Duty cycle.** Expect roughly 40–50 % of nights active. That is deliberate:
   it is the main reason the strategy can decorrelate from the old base, and it
   also means the strategy will lag badly in a bull market where the overnight
   drift is unconditional.
3. **Cost.** Two fills per active night. At a 45 % duty cycle that is ~0.9 round
   trips/day, so the 1 bp result is the only one likely to clear TQQQ; 5 bp and
   10 bp are reported as the honest stress.
4. **Half days.** Entry uses the last bar and the exit uses bar 32 of the next
   session, so a half-day entry happens at 12:59 — the position then misses the
   half-day's final move and holds a longer overnight. This is a real, if small,
   modelling choice and is flagged rather than smoothed over.
5. **BIL.** If V5 loses to cash, the reason is the extra round trip; that is a
   finding, not a bug.

## 8. Provenance

| claim / rule | source | role | confidence |
|---|---|---|---|
| Positive overnight returns followed by intraday reversal, driven by a temporarily inflated opening price | Berkman, Koch, Tuttle & Zhang (2012), *Paying Attention*, JFQA 47(4) — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1625495 | inspired the closing-pressure conditioning (H1) | high for the existence of the open/overnight reversal; medium for the market-index sign |
| Return continuation at half-hour intervals that are exact multiples of a trading day; intraday periodicity is a real, persistent structure | Heston, Korajczyk & Sadka (2010), *Intraday Patterns in the Cross-Section of Stock Returns*, JF 65(4) — https://arxiv.org/abs/1005.3535 | supports treating clock windows as separate, repeatable blocks | high |
| Overnight and intraday returns are driven by separate clienteles; institutional trading clusters at the close, retail at the open | Lou, Polk & Skouras (2019), *A Tug of War*, JFE — https://ifr.hkust.edu.hk/uploads/upload/files/20250212/445bce5ab83ffca69c4fe4b56c8055e1.pdf | supports the close→open mechanism and the 15:59 entry | high |
| The unconditional overnight premium exists at all (V0 / the old idea) | Cliff, Cooper & Gulen (2008), *Like Night and Day* — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1004081 | benchmark for F2; the thing that must be beaten | high |
| The first half hour is the strong intraday block, hence exit at 10:01 not 09:31 | Gao, Han, Li & Zhou (2018), *Market Intraday Momentum*, JFE 129(2) — https://doi.org/10.1016/j.jfineco.2018.05.009 | inspired the exit time | high |
| The last 30 minutes are the negative block for TQQQ (−5.74 % CAGR, −1.48 bp/day over ~2,700 sessions) | Own measurement on the local 1-minute panel (original report §2) | inspired the conditioning variable and the 15:59 entry | medium — sample-specific |
| The block's own realised volatility is the right risk state | Own measurement (2022 overnight block −58 % vs +33 % in 2025) | inspired H2 | medium |
| Turn-of-the-month, day-of-week and month-of-year overlays | McConnell & Xu (2008); Lakonishok & Smidt (1988); own tests in the original report §7 | **tested and rejected** — unstable across years, monotone in window width | — |

Rejected on the way to this design: the 165-day QQQ gate (prohibited and, at
2016–2023, it is what made the original a trend strategy rather than a
time-of-day one); the turn-of-month 24 h overlay (the width sweep rises
monotonically to 68 % CAGR, so the gain is extra beta, not calendar); the
day-of-week and September filters (sign flips across eras).

## 9. How this gets run (when authorised)

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
python research\revisit\time-of-day\strategy.py
```

`main()` loads the dev panel only, evaluates V0–V5 at 1/5/10 bp, runs F1 and the
placebo, prints the six-way neighbourhood, then freezes (sha256 of this file +
the parameter dict) and only afterwards loads the full panel once for the
overlapping 10y/5y windows. It writes `result.json` with the schema from the
brief; `windows.holdout` is left empty for the lead.

## 10. Files

| file | contents |
|---|---|
| `HYPOTHESIS.md` | pre-registration: idea, hypotheses, falsifiers, variants |
| `strategy.py` | frozen implementation; `build_weights(...) -> (weights, info)`; not yet run |
| `report.md` | this file |
| `result.json` | written by the authorised run — does not exist yet |
