# FOMC + OpEx calendar TQQQ — pre-registered hypothesis

**Agent:** calendar/event family, independent implementation
**Dev window:** 2016-01-04 → 2023-12-29 (1-minute marks, next-open fills)
**Bar:** TQQQ dev 36.72% CAGR / 82.29% max DD / 0.82 Sharpe.
Pass = CAGR > 36.72% **and** max DD < 82.29% (ideally < 60%).
**Status of this file:** written before the first backtest. The grid, the
primary cell, the calendar rule and the risk overlay are fixed here. No cell
is selected on its evaluation-window result.

---

## 1. Mechanism

Two scheduled-flow effects, both knowable years in advance:

1. **FOMC cycle.** Cieslak, Morse & Vissing-Jorgensen (2019) document that a
   disproportionate share of the US equity premium is earned in the two weeks
   *after* scheduled FOMC decisions ("even weeks" of the FOMC cycle), while the
   odd weeks are close to flat. The mechanism is a policy-information and
   risk-premium cycle, not a directional forecast. If it survives in 2016-2023,
   a 3x Nasdaq fund held only in the post-decision window should capture most of
   the index's compounded return while sitting in T-bills for the rest of the
   month.
2. **OpEx flow week.** Monthly equity-options expiration concentrates dealer
   gamma, index rebalancing and roll flows around the third Friday. The
   pre-expiry session and the days immediately after expiry have a documented
   positive drift in broad indices. A 3x fund amplifies the drift.

The calendar is the primary signal. No trend SMA, no drawdown circuit breaker,
no relative-strength signal is used. The only permitted overlay is a causal
TQQQ realised-volatility risk gate, tested separately and not used by the
primary.

An important arithmetic caveat is stated up front: a calendar strategy that is
invested only part of the time must earn a *higher* per-session return than
buy-and-hold TQQQ to clear the CAGR bar. The report tests whether the windows
actually deliver that, and reports the required-vs-observed arithmetic rather
than hiding the shortfall in a Sharpe claim.

## 2. Calendar construction (ex-ante, holdout-ready)

Hardcoded, no external data at runtime:

* **FOMC decision dates.** The second day of every *scheduled* FOMC meeting,
  2015-12 through 2026-10-23. Scheduled dates are published by the Federal
  Reserve years ahead, so they are not look-ahead. Unscheduled/emergency
  decisions (2020-03-03 and 2020-03-15) are excluded because their dates were
  not knowable in advance. The March 2020 scheduled meeting (2020-03-17/18) is
  also excluded: the actual decision was the 2020-03-15 emergency action, so
  anchoring a window to 2020-03-18 would attach the rule to an event that did
  not happen on that date.
* **Monthly OpEx dates.** The third Friday of every month, 2015-12 through
  2026-10-23, moved to the preceding Thursday when the third Friday is Good
  Friday (2019-04-18, 2022-04-14, 2025-04-17). Hardcoded.
* **2024-2026 dates are included** in the same lists. They are never used by
  the development run because the development panel is truncated at
  2023-12-29. They make the file holdout-ready: a 2024-2026 run can call
  `build_weights` on its own bars without editing the calendar. Calendar dates
  are not price data and are not look-ahead.
* The December 2015 and December 2023 events are included because their
  post-decision windows straddle the development boundaries. The December 2023
  FOMC +20 window extends into January 2024; the holdout panel must therefore
  include pre-2024 warm-up bars, which is the standard `bt.panel` pattern.

A date is mapped to the **first trading session on or after** the date. For a
normal Wednesday FOMC decision that is the same session; for a weekend or
holiday it is the next session. Offsets are counted in trading sessions from
that anchor.

## 3. Trading rule

For each anchor session `a`:

```
FOMC window:  sessions a + f_start .. a + f_end   (inclusive)
OpEx window:  sessions a + o_start .. a + o_end   (inclusive)
held(k) = 1 if k is in the union of any window, else 0
target(k) = held(k) * gate(k)
```

`target(k)` is the TQQQ fraction held during session `k`, decided at the close
of session `k-1`. The rest is BIL. TQQQ and BIL are the only assets; QQQ is the
panel calendar but is never held. Weights are long-only and sum to exactly 1.

Fills use `research/bt.py` unchanged: the weight set on the last bar of the
prior session is filled at the next session's 09:30 open, with the 2% band and
slippage charged on traded notional. The headline cost is 1 bp; 5 bp and 10 bp
are reported.

## 4. Pre-registered grid (6 calendar cells + 2 risk variants)

The calendar grid is a 3 x 2 design: three FOMC post-decision lengths and two
OpEx windows. FOMC always starts at +2 sessions after the decision, as in the
mandate's example. Offsets are in sessions; the end is inclusive.

| id | FOMC window | OpEx window | role |
|---|---|---|---|
| G1 | +2 .. +10 | -1 .. +3 | short FOMC |
| G2 | +2 .. +10 | +1 .. +4 | short FOMC, post-expiry OpEx |
| **G3** | **+2 .. +15** | **-1 .. +3** | **primary / centre** |
| G4 | +2 .. +15 | +1 .. +4 | centre FOMC, post-expiry OpEx |
| G5 | +2 .. +20 | -1 .. +3 | long FOMC |
| G6 | +2 .. +20 | +1 .. +4 | long FOMC, post-expiry OpEx |

**Primary G3 is the centre, not the best cell.** +15 is the median of the three
FOMC lengths. The `-1..+3` OpEx window is the one that contains the expiration
session itself and is centred on it; `+1..+4` is the post-expiry neighbour.
The primary is pure calendar (no vol gate), so the calendar's own return is
measured without an overlay confounding it.

Two risk variants are pre-registered but are **not** selection candidates:

| id | definition |
|---|---|
| G7 | G3 with a soft gate: TQQQ weight x 0.5 when 20-session realised TQQQ vol is above its trailing 252-session 75th percentile, else x 1.0 |
| G8 | G3 with a hard gate: TQQQ weight 0 when the same condition holds, else 1.0 |

The gate uses data through the prior session's close only (one-session shift),
never the current session's return, and never a full-sample quantile.

The grid is a plateau test: all six calendar cells are reported, not just the
best. If the centre is not supported by its neighbours, the result is a ridge,
not a calendar effect.

## 5. Evaluation protocol

* Development only: `bt.panel(..., start="2016-01-04", end="2023-12-29",
  "1min", warmup_days=500)`. The panel is physically truncated at 2023-12-29;
  no 2024+ bar enters the weights or the simulation. The 2024-2026 calendar
  dates are present but inert in the dev run.
* Benchmark recomputed on the same 1-minute marks, and the published
  36.72% / 82.29% / 0.82 bar used for the pass/fail test.
* Costs: 1 bp headline, 5 bp and 10 bp.
* Metrics: CAGR, max DD (1-minute and daily), Sharpe, Sortino, volatility,
  TQQQ weight, BIL weight, fills, turnover, correlation and beta to TQQQ.
* Yearly returns and subperiod cuts: 2016-2019, 2020-2021, 2022-2023.
* Leave-one-year-out CAGR.
* Drop the best 1, 3 and 5 event windows (by realised window return).
* FOMC-only, OpEx-only and union decomposition.
* Shift test: move every anchor by -10..+10 sessions with the same window
  lengths. A real calendar effect should peak at shift 0, not at a neighbour.
* Random-calendar placebo: 500 draws, each replacing the event anchors with
  random session indices while preserving the number and lengths of the FOMC
  and OpEx windows. Report the percentile of the primary CAGR, DD and Sharpe,
  and the fraction of draws that beat the primary on both CAGR and DD.
* Event study: per-window open-to-open TQQQ returns, t-stat, positive share,
  and a same-length random-window null.
* Exposure arithmetic: the per-window log return that would be required to
  match the TQQQ bar, versus the observed per-window return.

## 6. Pass/fail and honest verdict

Pass only if the primary G3 has dev CAGR > 36.72% and max DD < 82.29% at 1 bp.
A lower-CAGR but much better Sharpe/Calmar result is reported as risk-adjusted,
not as a pass. If the calendar family cannot clear the bar, the report says so
and does not switch to a trend/vol/crash/relative family. The result is not a
licence to inspect 2024-2026; no holdout run is performed here.

## 7. Known failure modes

* The FOMC cycle may have decayed after 2011; the sample is 2016-2023.
* The union of windows may cover too few sessions to compound to TQQQ's
  return, or may cover the wrong part of the month.
* Overlapping FOMC and OpEx windows create a concentrated exposure profile;
  the placebo and shift tests are designed to detect "it is just exposure".
* 2020 COVID policy responses may dominate; the subperiod and leave-one-year
  cuts expose that.
* The OpEx window may be a pre-expiry effect, while the pre-registered
  variants are centred on/after expiry. The FOMC-only and OpEx-only
  decompositions show which leg, if any, carries the result.
