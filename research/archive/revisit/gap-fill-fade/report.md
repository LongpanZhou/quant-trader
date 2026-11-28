> **Post-test note (2026-11-27):** this file is the pre-registration, not
> the result. The frozen development result is in `../SUMMARY.md`; the
> full 2016-2026 audit, the post-tune variants and the research-validity
> verdicts are in `../WHY_UNDERPERFORM.md`. The published website curve is
> the freeze named in `../SUMMARY.md`.

# Gap-fill-fade — round-3 rebuild report (design skeleton)

**Status: design only. Backtests are paused by the 2026-11-26 clarification.**
No `result.json` has been generated. The dev metrics, correlations and
holdout are `TBD` until the lead authorizes the test and an independent audit.

## 1. Starting point, and what is actually new

The original `agents2/gap-fill-fade` was the round-1 winner plus a gap-up
filter: long TQQQ in a 165-day QQQ bull regime, sell TQQQ to BIL at 09:31 on
armed days with a +0.15% to +0.50% gap, re-enter at 15:59. Its 65.17%/39.02%
headline came mostly from the TQQQ overnight drift and crash avoidance, not
from the fade. The fade's own per-event edge was +0.41% with t = 1.60 over
10 years, +0.39% with t = 0.92 over 5 years, and the 5-year result was fragile
to the arm-gate buffer. That is the honest starting point.

The genuinely new idea is:

> **A small opening gap-up in a weak, stressed short-term tape tends to fill;
> if the first 30 minutes confirm the failure, the gap fill can be traded as a
> standalone short.**

The rebuild is not the old overlay with the 165-day gate removed. It changes
the position (outright short QQQ, not TQQQ→BIL), the holding period (10:01 to
at most 11:30, not all day plus overnight), the signal (10:00 confirmation, not
just a gap filter), the sizing (10% vol target, not 100%), and the risk
(OR-high stop + time stop, not the 4% TQQQ stop). It never holds TQQQ, never
holds overnight, and cannot earn the overnight drift.

## 2. Hypothesis

> On the development period 2016-01-04 → 2023-12-29, the confirmed
> gap-failure short has positive net expectancy after 1 bp, a Sharpe above 0.5,
> a win rate above 55%, and a daily-return correlation below 0.20 with the
> 165-day baseline. The edge is not explained by short QQQ beta, by a random
> entry at 10:01 on the same days, or by the gap label alone.

The mechanism is liquidity provision against an overnight order imbalance. A
small gap-up on no major news, in a tape that is already weak and volatile, is
more likely to be a temporary imbalance than a repricing. The first 30 minutes
are where the imbalance is absorbed; if price is below the open at 10:00, the
prior close is the natural magnet. The short is paid for the risk of a genuine
continuation.

## 3. Universe and data

- **Short instrument:** QQQ.
- **Cash:** BIL.
- **Data:** local adjusted 1-minute QQQ/TQQQ/BIL under `data/intraday-hf/`.
- **Development:** 2016-01-04 → 2023-12-29.
- **Holdout:** 2024-01-02 → 2026-10-23; not inspected by this agent.
- **SPY daily:** benchmark only, per `data/round3/yahoo/SOURCE.md`; it is not a
  tradable asset here.

No 100–250-day moving-average gate is used. The weak-tape definition is a
10-day SMA plus a 5-day return; the stress filter is 20-day realised volatility
versus its trailing 1-year median. Both are short-term and causal.

## 4. Rules (summary; exact version in `spec.md`)

1. **Gap:** `QQQ open / prior close − 1` must be between **+0.10% and +0.75%**.
2. **Weak tape:** prior QQQ close below its 10-day SMA **and** prior 5-day
   return negative.
3. **Stress:** prior 20-day realised volatility above its trailing 1-year
   median.
4. **Confirmation:** by the 10:00 close, QQQ's first-30-minute return is
   negative, price is below the 09:30 open, and price is still above the prior
   close (the gap is still open). If the gap has already filled by 10:00, skip
   the session.
5. **Entry:** short QQQ at the **10:01 open**, sized at
   `clip(10% / 20-day annualised vol, 10%, 100%)`; the rest is BIL. If the
   10:01 entry is at or below the prior close, skip; there is no gap left.
6. **Exit:** stop at the **opening-range high** (max QQQ high 09:30–09:59),
   floored at +0.2% and capped at +1.5% above the entry; target at the
   **prior close** (full gap fill); time stop at **11:30**. The fixed 1% stop is
   a control, not the primary. Stop wins if both stop and target are touched
   in the same bar. Exit fills at the next bar's open.
7. **Flat overnight.** No TQQQ, no long QQQ, no leverage beyond 1× short.
8. **Borrow:** 0.5%/yr on the short notional.

The short is implemented as a synthetic, session-reset inverse-QQQ asset held
long in the long-only `bt.py` engine. Its linear return from entry to exit is
exactly the negative of QQQ's return over the same interval; the borrow cost is
a small decay. This is an implementation device, not a tradable ETF.

## 5. Why this is different from the old overlay

| | Old overlay | Rebuild |
|---|---|---|
| Base | 100% TQQQ in a 165-day bull regime | 100% BIL by default |
| Trade | TQQQ→BIL at 09:31, rebuy 15:59 | Short QQQ at 10:01 |
| Signal | QQQ gap + winner's armed gate | Gap + 10-day weak tape + stress + first-30-minute failure |
| Hold | All day + overnight TQQQ | ≤ 90 minutes, flat overnight |
| Size | 100% | 10% vol target, max 100% short |
| Risk | 4% TQQQ stop, day+night BIL | OR-high stop (0.2–1.5%) + prior-close target + 11:30 time stop |
| Driver | Overnight TQQQ drift + crash avoidance | Intraday gap-fill reversal |
| Correlation to old base | 1.00 | Expected 0.0–0.2 (to be measured) |

## 6. Evidence and provenance

The size split — small gaps fill, large gaps continue — is the load-bearing
external evidence: MPM Markets (2026), Steady Turtle (2026), Open Market
Journal (2026), thetrading.tools (2026), IOSR (2019), Aiche-Cohen-Griskin
(2024), and the *Price gap anomaly* paper (2020). The intraday reversal after
opening gaps is supported by Grant-Wolf-Yu (2005) and the 2026 overnight-return
reversal paper. The opening-auction papers (RFS 2000, Gross 2003, JFM 2004)
explain why the opening price is informative. The stress/reversal link is
supported by the 2026 paper and Grant et al. The 10:00 confirmation, the
OR-high stop floor/cap, the 11:30 time stop and the vol target are **own-test**
choices; they are not taken from a paper.

The failed-opening-range-breakout literature is a **rejected** basis. The
TradingEdge Journal (2026) tested a "failed breakout → other side" family and
found nothing survived; Fetna (2026) finds ORB fails after realistic costs.
This design does not fade the ORB break; it uses the first 30 minutes only as a
time confirmation of the gap. The naive "fade every gap" rule is also rejected:
Loomi's NQ test (2026) shows most gap-size buckets lose after costs.

Full provenance: `provenance.md`.

## 7. Evaluation plan (when authorized)

- **Dev only** at 1/5/10 bp; minute marks; 2% band; next-open fills.
- **Event study:** n, mean, median, win rate, t, bootstrap p, holding minutes,
  exit reasons (per unit short, before vol sizing).
- **Sub-periods:** 2016–19, 2020–21, 2022–23.
- **±1-step neighbourhood:** gap band, weak-tape SMA (5/10/20), stress filter
  (none/1.25× median), confirmation (r30 < 0 / < −0.1% / none), OR-high stop
  floor/cap (0.1/0.2/0.3%, 1.0/1.5/2.0%; fixed 1% control), time stop
  (11:00/11:30/12:00), vol target (8/10/12%).
- **Placebos:** no-confirmation entry; random entry 10:01–11:00 on the same
  days; gap-label shuffle; constant short on all weak-tape days.
- **Correlation:** daily returns vs the 165-day baseline (benchmark only) and
  vs every other rebuild; target < 0.60 and < 0.70.
- **Holdout:** not run here; the lead runs it once after freeze.

## 8. Results

| Window | 1 bp CAGR / DD | 5 bp CAGR / DD | 10 bp CAGR / DD |
|---|---:|---:|---:|
| Dev 2016-01-04 → 2023-12-29 | TBD | TBD | TBD |
| 10y 2017-01-03 → 2026-10-23 (overlaps holdout) | TBD | TBD | TBD |
| 5y 2021-10-25 → 2026-10-23 (overlaps holdout) | TBD | TBD | TBD |
| Holdout 2024-01-02 → 2026-10-23 | TBD | TBD | TBD |

Event study: TBD. Correlation vs the 165-day baseline: TBD (expected 0.0–0.2).
Correlation vs other rebuilds: TBD. Status: **pending**.

**No performance claim is made in this skeleton.** The old overlay's numbers
(65.17%/39.02% at 1 bp, etc.) belong to the old base and are not evidence for
this rebuild.

## 9. Falsifiers (repeat of the decision rule)

The rebuild is retired or rejected if any of these holds on dev:

1. Confirmed-event mean ≤ 0 after 1 bp, or t < 1.5, or bootstrap 95% CI
   includes zero.
2. The no-confirmation/random-entry/constant-short placebos match or beat it.
3. The edge is positive only in 2020 and vanishes in 2016–19/2021–23.
4. Net expectancy is positive at 1 bp but negative at 5 bp.
5. The ±1-step neighbourhood has no plateau.
6. Correlation with the 165-day baseline is ≥ 0.60, or with another rebuild
   ≥ 0.70.
7. Look-ahead, fills, session boundary or minute-mark audit fails.

If the raw fade is real but the confirmed short is not, the status is
`retired_overlay_only`: the idea only ever worked as a filter on the old base.

## 10. Risks and caveats

- **Short-only, negative skew.** A gap-up that continues is a loss; the
  OR-high stop caps it, but a fast squeeze can fill through the stop.
- **Few events.** Expect roughly 20–40 shorts a year; the event count may be
  below 100 over dev, so the bootstrap and sub-periods matter more than the
  headline CAGR.
- **The 2020 stress filter may concentrate the sample.** The 2026 paper says
  reversals strengthen in stress; if the edge is only 2020, it is not a
  strategy.
- **The 10:00 confirmation is own-test.** It may be data-mined. The placebo and
  neighbourhood are the guard.
- **Short implementation.** The synthetic inverse asset is exact for a linear
  short but is not a real ETF; the audit must verify the construction and the
  borrow cost.
- **Data.** 1-minute data starts in 2016; no 2000/2008. The dev period includes
  2018 and 2020 but not a multi-year 2000-style bear.

## 11. Files

- `hypothesis.md` — idea, mechanism, falsifiers, expected correlation.
- `spec.md` — exact rules, sizing, exits, evaluation plan.
- `strategy.py` — complete code; `main()` is gated by `REVISIT_RUN=1`.
- `provenance.md` — source-by-source evidence and rejected sources.
- `report.md` — this skeleton.
- `result.json` — **not generated** (backtests paused).

## 12. Next step

Lead authorizes the dev run, then:
1. run `REVISIT_RUN=1 python research/revisit/gap-fill-fade/strategy.py`;
2. audit look-ahead, spec-vs-code, reproduction, harness, no-shared-base,
   data and overfitting;
3. freeze and run the holdout once;
4. fill the results table and the correlation numbers, or retire the idea
   honestly.
