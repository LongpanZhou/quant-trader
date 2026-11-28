# Hypothesis: turn-of-month TQQQ

**Slug:** `turn-of-month`
**Window:** development only, 2016-01-04 .. 2023-12-29, 1-minute marks.
**Bar:** TQQQ dev 36.72% CAGR / 82.29% max DD / 0.82 Sharpe.
**Status:** pre-registered before the final run and before any 2024+ data is touched.

## 1. Claim

A disproportionate share of the equity risk premium is earned in the sessions
around the month boundary. Pension and 401(k) contributions, month-end
rebalancing and window dressing, and the resolution of month-end liquidity
needs all cluster in the last few sessions of a month and the first few of the
next. TQQQ is a 3x daily compound of QQQ, so the same calendar tilt should be
amplified roughly threefold, while the long BIL sleeve outside the window
removes most of the time-in-market risk.

The claim is **calendar**, not trend: the signal is the session's position
relative to the month boundary, which is known in advance from the exchange
calendar. There is no price trend, no moving average, no cross-sectional
signal, and no full-sample normalisation.

Secondary claim: the calendar edge is less reliable in high-volatility
regimes. A causal 20-day volatility throttle is tested as an optional overlay;
it is **not** part of the delivered centre because, on the warmup-corrected
data, it costs more CAGR than the drawdown it saves (section 4).

## 2. Exact rules (centre)

Universe: QQQ (volatility input only), TQQQ (position), BIL (idle).

For each session `k`, with `pe(k)` = number of sessions from the end of its
month (0 = last session) and `ps(k)` = number from the start (0 = first):

```
in_window(k) = (pe(k) <= 4) or (ps(k) <= 5)      # last 5 + first 6 sessions
w(k) = 1.0 if in_window(k) else 0.0
```

- The decision for session `k` is taken at the 15:59 close of session `k-1`;
  fill at the next open (09:30 for the first session of a block; the 15:59
  bar's weight fills at the next session's open). The harness's next-open rule
  is used unchanged.
- Idle weight is BIL. QQQ is never held.
- The 2% rebalance band is the harness default; headline cost 1 bp, with 5 bp
  and 10 bp reported.
- The optional throttle, when enabled, is
  `w(k) = min(1, VOL_TARGET / sigma(k-1))` with `sigma` the annualised stdev
  of the last 20 completed TQQQ daily log returns, known at the close of
  `k-1`. The delivered centre uses no throttle (`VOL_TARGET = None`).
- The 20-day vol (for the throttle variant) is warmed with TQQQ daily closes
  from 2015-01-02..2015-12-31 so the strategy is live on 2016-01-04. No bar on
  or after 2024-01-01 is loaded.

The window is 11 sessions out of a typical 19-23 session month (about 52% of
sessions). This is deliberately wider than the classic "last 2 + first 3"
window; the pilot scan below explains why.

## 3. Pre-registered grid (8 cells)

The delivered centre is **L=5, F=6, no throttle**. The grid is a window ladder
around it plus three explicit throttle variants:

| # | last L | first F | vol target | role |
|---:|---:|---:|---:|---|
| 1 | 3 | 5 | 0.75 | narrow window |
| 2 | 3 | 6 | 0.75 | narrow window |
| 3 | 4 | 6 | 0.75 | L neighbour |
| 4 | 5 | 5 | 0.75 | F neighbour (fails CAGR in pilot) |
| 5 | **5** | **6** | **none** | **centre** |
| 6 | 5 | 7 | 0.75 | F neighbour |
| 7 | 5 | 6 | 0.60 | conservative throttle |
| 8 | 5 | 6 | 0.75 | pre-registered throttle |

No cell is selected on the holdout. The grid is fixed here; the report shows
every cell, including the failures.

## 4. Why this centre, and what the pilot scan already showed

A coarse scan of the dev window (last 1-11 sessions x first 0-11 sessions) was
run before fixing the grid. It showed:

- The classic 5-day window (last 2 + first 3) compounds at only about 15%
  CAGR in this sample. The effect is not strong enough there to clear 36.72%.
- The passing region requires a wide window, roughly last 4-5 + first 6-7
  sessions, i.e. about half the month.
- The window boundary at `pe=5` (the sixth-to-last session) is unusually bad
  in this sample (mean open-to-open return about -117 bp, t ~ -2.8). The L=5
  window excludes it; L=6 includes it and collapses to about 18-21% CAGR.
  This is a known fragility, not a robust plateau, and the report must say so.
- A 20-day vol throttle looked smooth in the pilot, but the pilot's vol was
  not warmed with 2015 data, so it sat in cash for the first 20 sessions of
  2016. With the correct warmup (live on 2016-01-04), the 0.75 throttle gives
  37.75% at 1 bp and 35.18% at 5 bp, versus 41.41% / 38.69% for the
  calendar-only centre. The throttle is therefore reported as a rejected
  optional overlay, not used in the centre.

So the centre is the **smallest wide window that clears the bar without a
throttle**. It is not claimed to be a broad, smooth optimum.

## 5. Falsification criteria

The hypothesis is rejected if any of the following holds on the dev window:

1. Centre CAGR <= 36.72% or max DD >= 82.29% at 1 bp.
2. The random-window placebo beats the centre with p > 0.10.
3. The result is a single spike: every immediate neighbour (L +/- 1, F +/- 1)
   is below the bar *and* the leave-one-year-out CAGR falls below the bar for
   more than one year.
4. The edge disappears when the best month is removed, or when 2020 alone is
   removed.

Criterion 3 is the one this strategy is most at risk of failing. The report
will state the outcome explicitly rather than hiding it behind the headline.

## 6. What would make this a real holdout candidate

The strategy is defensive: about half the time in TQQQ and half in BIL. It
should beat TQQQ in a drawdown and lag in a steady bull. It is a candidate for
the one-shot holdout only if the lead wants a low-drawdown calendar tilt, not
if the lead wants a high-CAGR replacement for TQQQ. The report gives the
full-period arithmetic needed to judge that trade-off.
