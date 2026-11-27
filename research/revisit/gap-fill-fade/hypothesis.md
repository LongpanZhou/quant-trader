# Hypothesis — gap-fill-fade (round-3 rebuild)

Status: **design only. Backtests are paused by the 2026-11-26 clarification.**
No result.json yet. Nothing in this folder is a working strategy until the lead
authorizes a dev run and an independent audit.

## 1. What the original strategy actually was

The original `agents2/gap-fill-fade` was an **overlay on the round-1 winner**:
hold 100% TQQQ while QQQ's prior close is above its 165-day SMA, sit in BIL
otherwise, and on armed days with a QQQ gap of +0.15% to +0.50% sell TQQQ at
09:31, hold BIL to the close, and re-enter at 15:59 unless TQQQ closed 4%
below the session open.

The genuinely new idea inside it was:

> **A small opening gap-up in a weak short-term tape tends to fill.**
> The rest — the 165-day gate, the 4% stop, the overnight TQQQ hold — was the
> shared base, not the idea.

The overlay's headline (65.17%/39.02% at 1 bp) came mostly from the TQQQ
overnight drift on all non-overlay days plus crash avoidance, not from the fade
itself. The per-event fade edge was +0.41% with t = 1.60 over 10 years and
+0.39% with t = 0.92 over 5 years: real enough to study, too weak to claim as
alpha. It also failed the 5-year arm-gate robustness test. So the old result is
a **starting point, not a template**.

## 2. The standalone idea

**Short QQQ on confirmed failed small gap-ups in a weak, stressed tape.**

The position is an outright intraday short, not a temporary move from TQQQ to
BIL. The strategy is flat (100% BIL) by default. It only takes risk on a small
number of sessions where four things line up:

1. **The gap is small.** QQQ opens +0.10% to +0.75% above the prior close.
   Small gaps are the part of the gap distribution that fills; large gaps are
   news and continue (MPM Markets, Steady Turtle, Open Market Journal,
   thetrading.tools, IOSR).
2. **The tape is weak and stressed.** QQQ's prior close is below its 10-day
   SMA and its prior 5-day return is negative; 20-day realised volatility is
   above its trailing 1-year median. Short-term weakness plus stress is when
   overnight strength is most likely to reverse in the first half hour
   (Grant-Wolf-Yu 2005; the 2026 overnight-return reversal paper).
3. **The gap is already failing.** By the 10:00 close, QQQ's first-30-minute
   return is negative, the price is below the 09:30 open, and the price is
   still above the prior close (the gap has not already filled). This is the
   confirmation that separates a fading gap from a gap-and-go. It is an
   own-test idea, not a published rule.
4. **The gap is still open.** If the 10:00 close is at or below the prior
   close, or the 10:01 entry is at or below the prior close, skip the session;
   there is no gap left to fade.

Entry is the 10:01 open. Target is the prior close (the full gap fill). Stop
is the **opening-range high** (the max QQQ high from 09:30 to 09:59), floored
at +0.2% and capped at +1.5% above the entry; a fixed 1% stop is a control.
The OR high is the level that would invalidate the fade thesis, and it keeps
the reward/risk near 1:1 instead of risking 1% to make a 0.1% gap. Time stop
is 11:30. Size is volatility-targeted at 10% annualised, capped at 100% short,
so the position is smaller when QQQ is volatile. The strategy is flat
overnight; there is no TQQQ long, no 165-day gate, no 4% stop, no 15:59
re-entry.

## 3. Hypothesis

> On the development period 2016-01-04 → 2023-12-29, the confirmed
> gap-failure short has a positive net expectancy after 1 bp costs, a Sharpe
> above 0.5, a win rate above 55%, and a daily-return correlation below 0.20
> with the 165-day baseline. The edge is not explained by short QQQ beta or by
> a random entry between 10:01 and 11:00 on the same days.

The economic mechanism is liquidity provision against an overnight order
imbalance. A small gap-up on no major news, in a tape that is already weak and
volatile, is more likely to be a temporary imbalance than a repricing. The
first 30 minutes are where the imbalance is absorbed; if price is already below
the open at 10:00, the absorption is failing and the prior close is the natural
magnet. The short is paid for the risk of being run over by a genuine
continuation.

## 4. Why this is not the old overlay with the base removed

| | Original overlay | This rebuild |
|---|---|---|
| Base position | 100% TQQQ overnight in a 165-day bull regime | 100% BIL by default |
| Trade | Sell TQQQ to BIL at 09:31, rebuy at 15:59 | Short QQQ at 10:01 |
| Signal | QQQ gap +0.15–0.50% and the winner's armed gate | Gap +0.10–0.75%, weak 10-day tape, stressed vol, negative first 30 minutes |
| Holding period | All day, then overnight TQQQ | Up to 90 minutes (10:01–11:30), flat overnight |
| Sizing | 100% of equity | Vol-targeted 10% annualised, max 100% short |
| Risk | 4% TQQQ stop from the open, day+night BIL | OR-high stop (0.2–1.5%), prior-close target, 11:30 time stop |
| Return driver | Overnight TQQQ drift + crash avoidance | Intraday gap-fill reversal |
| Correlation with old base | 1.00 (it is the base plus a filter) | Expected 0.0–0.2 |

The new strategy cannot make money from the overnight drift, because it is
never long TQQQ and never holds overnight. It has to earn its return from the
gap fill itself. That is the point of the rebuild.

## 5. What would falsify it

The design is rejected or retired if any of these is true on the development
period:

1. **No net edge.** Confirmed-event mean ≤ 0 after 1 bp, or t < 1.5, or a
   bootstrap 95% confidence interval that includes zero.
2. **The confirmation adds nothing.** A placebo that enters at 10:01 on all
   weak-tape small-gap days (no first-30-minute confirmation), or at a random
   minute on the same days, has the same or better net PnL.
3. **It is just short beta.** The strategy's PnL is matched by a constant short
   QQQ position over the same sessions, or by shorting every weak-tape day
   regardless of the gap.
4. **It is a 2020 artifact.** The edge is positive only in 2020 and vanishes in
   2016–19 and 2021–23.
5. **Costs kill it.** The net expectancy is positive at 1 bp but negative at
   5 bp, or the stop is hit so often that the average loss exceeds the average
   gain.
6. **It is a knife-edge.** The ±1-step neighbourhood (gap band, weak-tape MA,
   stress filter, confirmation threshold, stop, time stop, vol target) has no
   plateau.
7. **It is not independent.** Daily-return correlation with the 165-day
   baseline is ≥ 0.60, or correlation with another rebuilt strategy is ≥ 0.70.
8. **It fails audit.** Look-ahead at the 2020-03-12 11:07 and 2022-09-13 10:41
   cuts, next-open fills, session boundaries, or minute marks fail.

If the raw fade is real but the confirmed short is not, the honest status is
`retired_overlay_only`: the idea only ever worked as a filter on the old base,
and the standalone expression does not earn its costs.

## 6. Expected correlation with the old base

Expected **0.0–0.2** on daily returns. The strategy is in BIL on most sessions
and short QQQ on perhaps 20–40 sessions a year. The old base is long TQQQ in
bull regimes and BIL in bear regimes. The short days are weak, stressed days,
which often fall in the old base's BIL periods, so the correlation could be
slightly negative. It must be measured, not assumed; the design fails the
brief if the measured correlation is ≥ 0.60.

## 7. What is deliberately excluded

- The 165-day QQQ/TQQQ/SPY/NDX gate, and any 100–250-day moving average gate.
- The round-1 armed 4% TQQQ stop and the old `build_weights`.
- The 09:31 entry / 15:59 re-entry structure. The new entry is 10:01 and the
  exit is by 11:30.
- Long TQQQ, long QQQ, or any overnight equity exposure.
- The naive "fade every gap" rule. The confirmation, stress filter, stop and
  target are the parts that have to earn the edge.
- The failed-opening-range-breakout trade. The literature on fading the ORB
  break is negative after costs; this design uses the first 30 minutes only as
  a **time confirmation of the gap**, not as a break of the opening range.
