# Hypothesis — gap-capitulation-reversal (revisit)

**Status:** pre-registered, not yet tested on the rebuild. Backtests are paused.
**Original:** `research/agents2/gap-capitulation-reversal` — a 165-day QQQ regime
plus a 1-day TQQQ buy after a QQQ gap-down. Its standalone version made
7.74%/21.22% (10y) and 7.95%/8.20% (5y) at 1 bp and was dominated by the base.
**This rebuild is not that overlay minus the 165-day gate.** It is a different
signal, holding period, asset choice and risk rule.

## 1. What is genuinely new

The original idea was: *a large QQQ gap-down is followed by a next-session
bounce, so buy TQQQ at the next open in a bull regime.* The rebuild keeps only
the broad area — **capitulation reversals** — and changes the causal claim:

> **A large decline that happens while the market is already short-term
> oversold and on *below-average* volume is a liquidity/positioning event, not
> an information event. It reverses over the following 3 sessions. A large
> decline on heavy volume is more likely to be information-driven and is not
> traded.**

The old strategy bought *any* gap-down; this strategy buys a **quiet, oversold
capitulation** and holds for **three sessions**, not one. The old strategy's
position was decided by a 165-day trend gate; this strategy's position is
decided entirely by the event, its volume condition, and its own exit rules.

## 2. Why this might be real

1. **Short-term reversal after large declines.** Cox & Peterson (1994) find
   short-horizon reversals after large one-day declines (though they attribute
   much of it to bid-ask bounce), and the S&P 500 dip statistics show a small
   positive next-session median after -2%/-3% days (jorgai; Finabase). The
   effect is weak unconditionally, which is why the old 1-day gap version was
   not investable on its own.
2. **The 3-5 day horizon.** The pre-pause dev event study (2016-01-03 to
   2023-12-29, QQQ/TQQQ, next-open entry) found the next-session bounce to be
   weak, but the 3-5 day TQQQ return after a large decline to be positive:
   - QQQ close <= -2%: 3-day +1.16% (t=1.66), 5-day +1.57% (t=1.62).
   - QQQ intraday low <= -3%: 3-day +1.11% (t=1.24), 5-day +2.16% (t=1.81).
   - QQQ 20-day drawdown <= -8%: 3-day +0.68% (t=1.02), 5-day +1.21% (t=1.32).
   The effect is stronger when the event is also short-term oversold (20-day
   return <= -3%): 3-day +1.55% (t=1.48) for close <= -2%, +2.13% (t=1.84) for
   low <= -3%. This is why the rebuild holds 3 sessions rather than 1.
3. **The quiet-volume condition.** In the same dev event study, the 3-day
   TQQQ return was much stronger when the event-day volume was at most 1.2x
   its 20-day average:
   - QQQ close <= -2% and rvol <= 1.2: 3-day +3.97% (t=2.97, n=43); 5-day
     +4.36% (t=2.28).
   - QQQ low <= -3% and rvol <= 1.2: 3-day +4.32% (t=2.95, n=28); 5-day
     +6.06% (t=2.64).
   - QQQ 20-day drawdown <= -8% and rvol <= 1.2: 3-day +2.19% (t=2.62,
     n=109); 5-day +2.90% (t=2.41).
   This is the empirical core of the rebuild, and it is the part most likely to
   be a regime proxy or a sample artifact. It is therefore the first falsifier.
4. **Why low volume could matter for an index.** Campbell, Grossman & Wang
   (1993) argue the opposite for individual stocks: high-volume declines are
   more likely to be liquidity-driven and reverse. If the index behaves like a
   single large stock, the sign should be the other way. The rebuild treats the
   low-volume sign as a **hypothesis to be tested**, not an established fact;
   the high-volume version is an explicit ablation. A finding that the high-
   volume subset is at least as good kills the volume condition.
5. **Sizing and risk.** The event is rare and the holding period is short, so
   the strategy is in BIL most of the time. To avoid taking 3x leverage into a
   high-volatility crash, the offensive asset is TQQQ only when QQQ's 20-day
   realised volatility is at most 30% annualised; otherwise the position is
   QQQ. This is a volatility-scaled asset choice in the spirit of Moreira &
   Muir (2017), not a trend gate.

## 3. Hypothesis (one sentence)

In a QQQ/TQQQ/BIL account, a large QQQ decline (close <= -2% or intraday low
<= -3%) that occurs while QQQ is short-term oversold (20-day return <= -3%) and
on below-average volume (<= 1.2x the 20-day average) is followed by a positive
3-session TQQQ return, large enough to beat BIL after 1/5/10 bp costs, with a
daily-return correlation below 0.60 to the old 165-day baseline.

## 4. What would falsify it

The rebuild is rejected, or the volume condition is dropped, if any of these
hold on the development period (2016-01-04 to 2023-12-29):

1. **The core event is not positive.** The mean 3-session TQQQ return after the
   quiet-oversold event is <= 0, or its bootstrap p-value is > 0.10.
2. **The volume condition is a regime proxy.** The quiet subset does not beat
   the heavy-volume subset (rvol > 1.2) within the same oversold bucket, or the
   quiet edge disappears after controlling for the 20-day trend/volatility
   bucket. In that case the volume filter is dropped and the strategy is
   re-specified as a plain oversold-capitulation hold, or retired.
3. **The edge is one episode.** The 2016-2019, 2020-2021 and 2022-2023
   sub-periods do not all have a positive mean 3-session return, or the 2020
   episode accounts for more than half of the total P&L.
4. **The strategy is not investable.** Dev CAGR < 3%, or Sharpe < 0.30, or max
   drawdown > 25% on 1-minute marks, after 1 bp costs.
5. **The correlations fail.** Daily-return correlation with the 165-day
   baseline >= 0.60, or with any other rebuild >= 0.70.
6. **The exits are the edge.** Removing the event-low stop or the hard stop
   improves CAGR by more than 2 pp, i.e. the risk rules are destroying the
   signal rather than protecting it.
7. **The placebo matches.** Randomly chosen event days with the same count and
   holding period produce a CAGR within the 90% confidence band of the real
   strategy.
8. **Costs dominate.** The 10 bp CAGR is below 2%, or the 5 bp/10 bp drawdown
   is worse than the 1 bp drawdown by more than 5 pp.

## 5. Pre-registered choices (no fitting after the fact)

- Event: QQQ close-to-close <= -2.0% **or** QQQ intraday low <= -3.0% from the
  prior close.
- Volume: event-day volume <= 1.2x the mean of the prior 20 sessions.
- Oversold: QQQ 20-day return <= -3.0%.
- Entry: next session's open, 100% of the chosen asset.
- Hold: 3 sessions, exit at the close of the third session.
- Asset: TQQQ if QQQ 20-day realised vol <= 30% annualised, else QQQ.
- Risk: exit at the next open if QQQ closes below the event-day low; hard stop
  at -8% of the chosen asset from the entry; time exit.
- No 165-day (or any 100-250-day) moving-average gate. No old base weights.

The one-at-a-time neighbourhood and the ablations are listed in `SPEC.md` and
were fixed before the rebuild run. Any change to the core event after seeing
the result is a new hypothesis, not a parameter tweak.

## 6. Honest prior

The most likely outcome is a **low-CAGR diversifier**: roughly 30-50 events
over 8 years, 3 sessions each, so exposure is about 5-7% of bars. A 4% mean
3-session return on that exposure is a mid-single-digit CAGR before BIL carry,
with a drawdown in the low-to-mid teens. That will not beat TQQQ as a
standalone and may be retired by the lead. The value of the rebuild is to test
whether the quiet-oversold effect is real and independent of the old base, not
to produce another 60% CAGR strategy.
