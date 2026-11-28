# Hypothesis: participation exhaustion (supply-climax) long

**Slug:** `volume-orderflow` · **Written:** 2026-11-26 · **Status:** hypothesised, not tested
**Backtests paused.** This file is the pre-registration. Nothing below has been
run under the frozen spec; no `result.json` exists.

---

## 1. What the original strategy actually contained

The original (`research/agents2/volume-orderflow`) is the round-1 base
*(100% TQQQ while QQQ's prior close is above its 165-day SMA, else BIL)* plus a
4% minute stop whose **arming** is conditioned on relative volume:

```
armed(i) = ( QQQ@09:30 < MA20(prev)*1.01  OR  rvol(i) > 1.5 )  AND  rvol(i) > 1.0
```

Its own ablation is decisive about where the value sat: the volume floor with the
re-arm switched off produced 57.70/42.86 (10y) versus the winner's 58.80/44.56,
and the re-arm alone produced 67.06/44.21. Both were measured **on top of the
165-day regime**, and the 10-year gain was concentrated in February–March 2020
(2020: +267.9% versus +183.9%). The 5-year drawdown improvement was traced to a
single suppressed stop on 2026-06-24.

So the extracted idea is narrow and real:

> **Participation (relative volume) is the variable that decides whether a price
> move is information or noise.** A decline on ordinary volume is a liquidity
> air pocket; a decline on heavy volume is real supply being absorbed.

In the original this only ever *gated a stop*. That is a filter, and the
clarification of 2026-11-26 says not to strip the base and call the residue a
strategy. The hypothesis below turns the same claim into a statement about
**returns**, not about stop usefulness — and then builds a complete strategy
around it.

## 2. The generalised claim

If heavy-volume selling is a transfer of stock from impatient to patient hands,
then the sessions where a decline is *fully absorbed* — sold hard, on heavy
participation, but closed well off the low — should be followed by positive
abnormal returns over the next few sessions. This is the supply-climax /
liquidity-provision story of Campbell, Grossman & Wang (1993): returns after
high-volume declines exhibit reversal, because the price pressure was
non-informational.

Two things distinguish this from the original and from the rest of the repo:

1. It is a **return forecast**, not a stop-arming condition. The position is long
   *because* the event happened.
2. The event is defined **within the session** (open-to-close), not by a gap and
   not by a moving average. Overnight gaps are excluded deliberately: the round-1
   and round-2 work showed that TQQQ's drawdowns are made of overnight gaps, and
   gap behaviour is a different (already-assigned) effect.

## 3. Hypothesis

**H1.** After a session in which QQQ falls ≥ 0.8% *open-to-close*, on ≥ 1.5× its
20-day average volume, and closes in the upper half of its own range, TQQQ's
return over the following five sessions exceeds its unconditional five-session
return, by enough to survive 5 bp one-way costs.

**H1a (mechanism).** The effect should be stronger when the close-location filter
is present: a heavy-volume decline that closes *on* its low is unresolved
selling, and should not be bought.

**H1b (what it is not).** The effect must not be a 2020 artifact, must not be
driven only by the short leg of some other effect, and must not be reproducible
by randomly choosing the same number of sessions.

## 4. Falsifiers — pre-registered, all must be reported

The hypothesis is **falsified** and the strategy is retired or rejected if any of
the following holds on the development period:

| # | Test | Falsified if |
|---|---|---|
| F1 | Event vs unconditional 5-session TQQQ return | event mean ≤ unconditional mean |
| F2 | One-sided bootstrap on the event-minus-baseline difference | p > 0.10 |
| F3 | Net of costs (1 bp and 5 bp) | CAGR ≤ BIL, or Sharpe ≤ 0 |
| F4 | Sub-periods 2016–19 / 2020–21 / 2022–23 | sign is not positive in at least two of three |
| F5 | Placebo: same number of randomly chosen 5-session holds | real result inside the placebo 90% interval |
| F6 | Correlation vs the 165-day baseline | ≥ 0.60 |
| F7 | Robustness to the declared parameter neighbourhood | the primary is an isolated spike, not on a plateau |
| F8 | Close-location filter | without it the edge vanishes entirely (then the edge is the filter, not participation) |

**No sign flipping.** If the event mean is *negative* and significant, that is a
rejection of H1, not a signal to go short. Reporting a reversed sign after seeing
the data is exactly the overfitting this brief forbids.

## 5. Why this is a complete strategy, not an overlay

| Component | Original | This rebuild |
|---|---|---|
| Universe | QQQ regime / TQQQ / BIL | QQQ signal / TQQQ expression / BIL cash |
| What decides the position | a 165-day price trend, volume only gated a stop | the participation event itself |
| Holding period | continuously long while the trend is up | 5 sessions per event, BIL otherwise |
| Sizing | 100% TQQQ, 100% BIL | 100% TQQQ on event, BIL otherwise; 50% variant declared |
| Risk | 4% intraday stop, out overnight | time-based exit only; **no price stop** |
| Turnover | ~80 fills/yr | ~2 fills per event, ~10–20 events/yr |
| Time in market | ~78% | expected ~25–40% |

The risk control is deliberately *not* a stop. A stop would reintroduce the old
overlay and make the result unattributable.

## 6. Preliminary evidence (pre-pause, not results)

Two exploratory dev runs were completed on 2026-11-26 **before** the pause, and
are recorded here only to justify the hypothesis, not as evidence for it:

1. **Participation has no unconditional timing power.** A volume-expansion ladder
   (hold TQQQ while 5-day/60-day mean volume is below a threshold) gave
   32.42/65.97 at the 70th percentile and 37.72/71.30 at the 80th, against TQQQ
   buy-and-hold 36.15/82.29 and the 165-day baseline 44.76/58.76. The placebo
   test was not passed: with 29% of sessions randomly removed the median placebo
   CAGR was 27.27% and p(placebo ≥ real) = 0.35; at 19% off, p = 0.30. This is
   the evidence that killed the *timing* form of the idea and pushed the design
   toward an event study.
2. **The sign of the event effect is the one hypothesised.** On dev, sessions with
   rvol > 1.5 and a down close (n = 142) were followed by +0.70% TQQQ
   close-to-close over the next session versus +0.18% for all other sessions, and
   +1.43% versus +0.99% over five sessions. That is the direction H1 needs, and it
   is the *opposite* of the round-2 overnight-gate conclusion, which was itself
   shown to be a 2020 artifact.

Both numbers are exploratory, use a different event definition from the frozen
spec (they do not require an intraday decline or a close off the low), and must be
re-derived from `strategy.py` once the lead authorises the test.

## 7. What would make me abandon this before testing

- If the lead's data audit finds that intraday open-to-close returns on the
  adjusted 1-minute QQQ panel are contaminated by the dividend adjustment factor
  applied per session (they should not be: the factor is constant within a day).
- If a minute-marked event study of this shape cannot reach ~40 non-overlapping
  events on dev, the sample is too thin to pass F2 and the design should be
  retired without running.
