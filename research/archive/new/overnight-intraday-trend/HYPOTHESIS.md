# HYPOTHESIS — overnight-intraday-trend

**Status:** pre-registration written before the final `strategy.py` run.
**Window:** development only, 2016-01-04 → 2023-12-29. No 2024+ data is loaded.
**Bar:** TQQQ dev 36.72% CAGR / 82.29% max DD / 0.82 Sharpe. Pass if CAGR >
36.72% and max DD < 82.29% (target < 60%).

## 1. Economic hypothesis

TQQQ's return is earned mostly overnight: on the dev window the 15:59-open to
next-09:30-open block contributes roughly 23% annualised log return versus 7.7%
for the 09:30→15:59 session. The session is where the left tail lives — a 3x
ETF can lose several percent between the open and the close on a day when QQQ
merely drifts down. The hypothesis is that a slow 20/50-session trend should
own the **overnight** position, while a fast intraday weakness rule should own
the **session**, and that the two are complementary:

- the 20/50 trend keeps the overnight drift in bull regimes and moves to BIL
  when the medium-term trend breaks;
- the intraday stop cuts the day-session left tail that the daily trend cannot
  see, and re-enters on a reclaim so the strategy is not permanently de-risked
  by one bad morning;
- if the session closes weak (stopped out and not reclaimed), the strategy
  skips that night, which is the one place where a fast signal can reduce
  overnight gap risk without giving up the trend's overnight drift on normal
  days.

This is deliberately **not** a fixed time-of-day schedule (the existing
`time-of-day` work) and **not** an overnight crash filter with vol targeting
(the existing `overnight-drift-filter`). The position is a 20/50 trend state;
the fast filter is a price-reclaim stop, not a volatility throttle.

## 2. Exact rules

Universe: QQQ (signal), TQQQ (position), BIL (defensive sleeve). Long-only,
weights ≥ 0, sum ≤ 1. Fills are next-minute opens; 2% rebalance band; 1 bp
headline, 5/10 bp reported.

Daily clock (all times ET):

```
session k has bars 09:30 .. 15:59.
q58[k]  = QQQ close of the 15:58 bar of session k
SMA20[k], SMA50[k] = means of QQQ daily closes through q58[k]
trend_up[k] = (SMA20[k] > SMA50[k]) OR (q58[k] > SMA50[k])
```

The second leg is the reclaim leg: after a break, price reclaiming the
50-session average re-arms the trend even before the 20/50 cross flips. The
trend is "broken" only when both legs are false (SMA20 < SMA50 and price <
SMA50).

Session rules for session k+1 (the trend state `trend_up[k]` is known at the
15:58 close of k):

```
start the session long TQQQ iff trend_up[k], else BIL for the whole session.
checks at 10:00, 10:30, 11:00, 11:30, 12:00, 12:30, 13:00, 13:30,
           14:00, 14:30, 15:00, 15:30 (close of each 30-minute bar):
    if long and QQQ_close <= QQQ_session_open * (1 - 0.006):
        exit to BIL at the next minute's open
    if in BIL and QQQ_close >= QQQ_session_open:
        re-enter TQQQ at the next minute's open
at 15:30 the session state is frozen for the night:
    if long at 15:30 and trend_up at 15:58: hold TQQQ overnight
    if BIL at 15:30 (stopped, not reclaimed): stay BIL overnight
    if the trend has just turned up at 15:58 from a down day: buy TQQQ at
        the 15:59 open for the overnight (fresh entry)
    if the trend is down at 15:58: BIL overnight
if the night was skipped after a weak close, re-enter at 09:31 the next
session when the trend is still up (the 09:30 bar's close sets the weight;
the fill is 09:31).
```

The 15:58 trend decision fills at the 15:59 open. Every other decision is made
at a bar close and fills at the next bar's open. No same-bar information is
used. The 15:30 night decision is deliberate: the last 30 minutes are excluded
from the fast filter so a late, unconfirmed bounce cannot pull the strategy
back into a weak overnight.

## 3. Why these parameters

- **0.6% QQQ stop.** A 0.6% QQQ move is about 1.8% on TQQQ. The explored
  plateau (0.5–0.7%) is broad; 0.6% is the middle, not the maximum. A 0.4%
  stop is too tight (whipsaw), 0.8% too slow (gives back the day-session
  left tail).
- **30-minute checks.** Standard session-aligned bars (09:30–10:00,
  10:00–10:30, …). 15- and 60-minute variants are in the grid.
- **15:30 night decision.** The session state after the 15:30 check owns the
  night. A true 15:55 close check is a neighbour; it is slightly weaker
  because late-day reclaims are poor overnight signals.
- **20/50 with the 50-session reclaim leg.** The pure 20/50 cross is a
  neighbour; it passes too but with a smaller margin (see the grid).

## 4. Pre-registered grid (8 cells, no other selection)

| # | stop | check step | night rule | trend gate |
|---:|---:|---:|---|---|
| 1 | 0.5% | 30m | skip weak close | 20/50 + reclaim |
| 2 | 0.6% | 30m | skip weak close | 20/50 + reclaim (centre) |
| 3 | 0.7% | 30m | skip weak close | 20/50 + reclaim |
| 4 | 0.6% | 15m | skip weak close | 20/50 + reclaim |
| 5 | 0.6% | 60m | skip weak close | 20/50 + reclaim |
| 6 | 0.6% | 30m | always re-enter at close | 20/50 + reclaim |
| 7 | 0.6% | 30m | skip weak close | pure 20>50 cross |
| 8 | none | — | skip weak close | 20/50 + reclaim |

The plateau is cells 1–5 and 7. The report will show all eight at 1/5/10 bp,
plus neighbours, controls, placebos and cut tests.

## 5. Predictions and falsification

- Dev CAGR > 36.72%, max DD < 60%, average TQQQ weight > 60%.
- Daily correlation to TQQQ 0.5–0.8 (the strategy is long much of the time,
  but the stop and the BIL sleeve decorrelate it).
- At 5 bp the CAGR should stay above the TQQQ bar; at 10 bp it may not — the
  stop is a high-turnover signal and that is a stated risk.
- Falsified if the stop overlay adds nothing (no-stop cell ≈ centre), if a
  stale/random stop signal matches the real one, if the result is concentrated
  in a single calendar year and disappears ex-2020, or if the weights change
  when the panel is truncated before 2022.

## 6. Known risks

- **Turnover.** ~1,600–2,000 fills over 8 years (~0.8–1.0 per session; about
  460 round trips, four fills each because both TQQQ and BIL are traded),
  dominated by the intraday stop. At 10 bp the drag is large.
- **Overnight gaps.** The stop is intraday only. A gap from a strong close is
  not protected; the skip-night rule only helps after a weak close. The worst
  nights are reported explicitly.
- **Choppy-market whipsaw.** The worst dev drawdown is expected to be a
  trendless choppy period (2019), not a crash. The strategy can lose 35% in a
  year that ends positive.
- **2020 concentration.** A crash + V-recovery is the ideal path for this
  design. Ex-2020 results are reported as a cut test.
- **BIL carry.** BIL is held only part-time and much of that is intraday; its
  carry is small (~1.4%/yr over the window). A cash-idle control is reported.
- **Clock choice.** The 30-minute grid and 15:30 night decision are design
  choices; 15/60-minute neighbours and a 15:00/15:45 night-decision sweep are
  reported so the reader can see the clock sensitivity.
