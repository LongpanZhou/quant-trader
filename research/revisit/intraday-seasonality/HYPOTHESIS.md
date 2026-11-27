# Hypothesis — `intraday-seasonality` (revisit)

**Status: design frozen, backtest paused. No result.json yet.**

## 1. What the original actually contained

The round-2 agent `agents2/intraday-seasonality` was the round-1 winner plus one
30-minute overlay:

> On a risk-on session where QQQ is more than 1% below its 09:30 open at 15:00,
> sell TQQQ at the 15:01 open and buy it back at the 15:30 open, then hold
> overnight as usual.

The shared base supplied everything that made it an investable book: the 165-day
QQQ SMA decided when to own TQQQ at all, the 4% armed stop supplied the crash
protection, and the overlay only removed 30 minutes from an otherwise continuous
long. Nothing in the signal says anything about the other 23.5 hours.

**The genuinely new content is therefore a claim about the close, not about the
trend:**

> When QQQ is already down more than 1% by 15:00, the last part of the session is
> sold by something other than information — the daily-reset leveraged-ETF
> complex must reduce exposure in the direction of the day's move — so the close
> is temporarily too cheap and the pressure is transitory.

That is the idea this rebuild tests.

## 2. Standalone hypothesis

If the close is temporarily depressed by forced flow, then the correct standalone
trade is not "hold everything and step aside for 30 minutes". It is:

> **Own TQQQ only for the reversal window**: buy the close on an orderly,
> intraday-led down day, hold one session, and sit in BIL the rest of the time.

This is a complete strategy because the signal decides **when to be long at all**
(about 11% of sessions), not merely when to trim an existing position. Holding
period, entry time, sizing and risk are all set by the idea rather than by the
old base.

The old overlay and the rebuild are economically the same insight expressed at
different points on the same flow: the overlay sells *into* the pressure at
15:01 and buys back at 15:30; the rebuild waits until the pressure has been paid
(the close) and owns the reversal.

### What would make this wrong

- If the next-day return after an intraday decline is no better than after an
  up day or a random day, the signal carries no information and the book is just
  "sometimes long TQQQ".
- If the edge lives entirely in the *opening gap* component of the decline
  rather than the intraday component, the idea is gap-capitulation (another
  agent's mandate) and this rebuild is not distinct.
- If the effect does not survive the 5 bp cost line, it is a microstructure
  curiosity, not a strategy.

## 3. Why the previous attempt failed

Before the pause I ran one development-only exploration of the naive standalone
(`explore_dev.py`, 2016-01-04 → 2023-12-29, 1 bp, 2% band):

| variant | CAGR | max DD | Sharpe | exposure | corr vs 165d base |
|---|---:|---:|---:|---:|---:|
| long TQQQ always | 36.4% | 82.3% | 0.80 | 100% | **0.71** |
| long TQQQ + carve 15:00-15:30 on weak days | 41.0% | 79.8% | 0.85 | 99% | **0.71** |
| buy 15:30 after QQQ < −1%, hold to next 15:00 | 19.4% | 43.4% | 0.69 | 10.9% | **0.25** |
| buy 15:30, hold only to next open | 1.0% | 44.5% | 0.17 | 0.9% | 0.19 |

The first two fail the brief's correlation rule (> 0.60) — they are still the old
base with a rounding error. The third is the only low-correlation expression and
it is positive in all three dev sub-periods (13.7% / 44.3% / 8.7% CAGR for
2016-19, 2020-21, 2022-23). The overnight-only leg earns nothing, which says the
reversal is not an overnight gap effect; it is realised during the next session.

This is **preliminary, pre-pause evidence**, not a verified result: it used a
15:31 entry (not the close), no crash filter, no stop, and one fixed threshold.
It is the reason the hypothesis below is worth a proper test, not proof of it.

## 4. What changed in the new design

1. **Entry moved to the close (15:59), not 15:30.** The 15:30-15:59 block is the
   part of the day that is *most* negative on weak days (about −10 bp per event
   in the pre-pause sample), so entering at 15:30 pays for the privilege of
   holding the worst 30 minutes. Buying the closing print is both closer to the
   documented forced-flow point and mechanically cheaper.
2. **Signal moved to 15:58.** It is evaluated on the price one minute before the
   entry fill, so a late rally cancels the trade instead of being bought.
3. **Crash and gap filters are pre-registered variants.** The base spec is the
   plain −1% rule; the filters exist to test whether the edge is specifically
   intraday flow (orderly decline, small gap) rather than generic dip buying.
4. **The book is flat by default.** No 165-day gate, no stop-derived base, no
   continuous long.

## 5. Provenance

| claim | source | role | confidence |
|---|---|---|---|
| Daily-reset leveraged funds must trade `L(L−1)·r·NAV` (6% of NAV per 1% index move for a 3x fund) at the close | Cheng & Madhavan (2009), *The Dynamics of Leveraged and Inverse Exchange-Traded Funds* | supports mechanism | high |
| Leveraged-ETF rebalancing creates end-of-day price pressure and the effect is transitory, reversing during the next trading day | Mathis & Moerke (2022), *Liquidity Provision to Leveraged ETFs and Equity Options Rebalancing Flows*, <https://wp.lancs.ac.uk/fofi2022/files/2022/08/FoFI-2022-027-Mathis-Moerke.pdf> | supports mechanism | medium |
| The late-day LETF effect is statistically visible but its economic magnitude is disputed | Lenkey (2024), *The market impact of leveraged ETFs: a survey*, QFE 8(4), <https://doi.org/10.3934/QFE.2024031> | caveat / benchmark | high |
| A real TQQQ/SQQQ rebalance can be billions of dollars of selling into one close | ETF.com, *One Bad Day: A levered-QQQ ETF Case Study*, <https://www.etf.com/sections/equity/one-bad-day-levered-qqq-etf-case-study> | supports mechanism | medium |
| The reset flow is executed in the closing auction | Strasmore, *Leveraged ETF Rebalancing Into the Close*, <https://www.strasmore.com/blog/leveraged-etf-rebalancing-and-the-close> | supports mechanism | medium |
| Intraday momentum / late-informed trading near the close | Gao, Han, Li & Zhou (2018), *Market Intraday Momentum*, JFE 129(2), <https://doi.org/10.1016/j.jfineco.2018.05.009> | related literature; tested and only partly replicated | high |
| The exact signal (QQQ −1% at 15:00) and the 15:01-15:30 block | Own test / no external source — 1-minute QQQ/TQQQ panel, 2017-2026; 195 risk-on signal days, mean carve gain +20.0 bp, t = 3.0 | inspired rule | high |
| The standalone "buy the flush, hold one session" book | Own test, pre-pause dev 2016-2023: 19.4% CAGR, 43.4% DD, Sharpe 0.69, corr 0.25 | preliminary support | medium |

## 6. Expected correlation vs the old base

**~0.20-0.30** on development daily returns. The book is invested about 11% of
bars, only in one-session bursts after down days, and the old base is a
continuous TQQQ/BIL trend book. The measured pre-pause value for the 15:30-entry
version was **0.25**.

## 7. Collision risk

- **`gap-capitulation-reversal`**: both end up long TQQQ after declines. Mine
  triggers on the *intraday* move (open → 15:58) and enters at the close; theirs
  triggers on the opening gap and enters at the open. Expected correlation
  0.4-0.6, must be measured. If it exceeds 0.70, this strategy should yield (the
  gap version is the more direct expression of that mandate).
- **`letf-rebalance-flow`**: owns the flow signal itself. Mine is a long-only
  reversal book, not a flow-timed de-risk; expected correlation low, but the
  lead should check.
- **`time-of-day`**: overnight book. Mine holds no overnight-only exposure as a
  systematic position (the hold spans one night, but entry and exit are
  intraday); expected correlation low (~0.3).

## 8. Falsifiers (pre-registered)

- **F1** Dev 2016-2023, 1 bp: CAGR < 6.0% or Sharpe < 0.50 → retire as weak.
- **F2** Daily-return correlation vs the 165-day baseline > 0.60 → fails the brief.
- **F3** Mean net return per event at 5 bp ≤ 0 → the edge is a cost artefact.
- **F4** Any dev sub-period (2016-19, 2020-21, 2022-23) has negative CAGR → not robust.
- **F5** The up-day placebo (same trade after QQQ > +1%) matches or beats the
  down-day selection on Sharpe → the signal has no information.
- **F6** Fewer than 150 dev events → require a bootstrap p-value < 0.05 on the
  per-event mean, otherwise retire.
- **F7** With the gap filter on, the edge vanishes and the base is dominated by
  gap-down days → the strategy is gap-capitulation and must be retired as
  non-distinct.
