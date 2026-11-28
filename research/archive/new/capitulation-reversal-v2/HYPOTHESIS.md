# Multi-horizon quiet capitulation reversal — `capitulation-reversal-v2`

**Status:** pre-registered. Development window only, 2016-01-04 .. 2023-12-29.
The 2024-2026 holdout has not been loaded or inspected.
**Primary:** `q3 <= -3.0%` or `q10 <= -5.0%` or `q15 <= -8.0%`, volume <= 1.2x the
prior 20-day average, buy TQQQ at the event-day close, hold one session.

---

## 1. What is genuinely new

The existing `gap-capitulation-reversal` (v1) is a **one-day** event: QQQ closes
<= -2% or trades <= -3% intraday, with a 20-day oversold condition and a
quiet-volume filter; it holds TQQQ (or QQQ when vol > 30%) for **three**
sessions, and it enters at the **next open**. It produced 30 events, ~4%
exposure and 8.3% CAGR at 1 bp on the development window.

This v2 keeps the broad area — a quiet decline is a positioning event that
reverses — and changes every part of the implementation:

| | v1 `gap-capitulation-reversal` | v2 `capitulation-reversal-v2` |
|---|---|---|
| Event horizon | one session (close or intraday low) | **cumulative 3, 10 or 15 sessions** |
| Event thresholds | -2% close / -3% low / 20-day -3% | **-3% / -5% / -8% cumulative** |
| Volume | <= 1.2x 20-day | <= 1.2x 20-day (same prior, new horizon) |
| Entry | next session's open | **event-day close (15:59)** |
| Hold | 3 sessions | **1 session** |
| Vehicle | TQQQ only when QQQ vol <= 30%, else QQQ | **always TQQQ, vol-capped** |
| Size | 100% of the chosen asset | 100% TQQQ capped by `0.80 / vol20` |
| Exit | time + event-low + 8% stop | time only (one session) |
| Events / exposure | 30 / 3.9% | **119 / 5.9%** |

It is also distinct from the other named rebuilds:

- `intraday-mean-reversion`: that is a **one-day intraday** QQQ -3% trigger,
  next-open entry, same-session exit, and never holds overnight. v2 has no
  intraday trigger, uses multi-day cumulative declines, and holds
  close-to-close (including the overnight).
- `gap-fill-fade`: that is a **short QQQ** trade on failed small gap-ups inside
  a weak tape. v2 is long TQQQ, uses no gap, no opening range and no short.
- The old 165-day QQQ base and the old 4% stop are **not used**. The 165-day
  baseline is computed only for the correlation/benchmark table.

## 2. Mechanism

1. **A multi-day decline on below-average volume is an air pocket, not news.**
   If the decline were information-driven, volume would be high and the next
   session would continue to reprice. Quiet volume means the decline is a
   drift/positioning event: sellers are not urgent, buyers are absent, and the
   next session's opening flow reverses the drift. This is the same family as
   the v1 quiet-volume prior, but applied to a multi-session cumulative decline
   rather than a single close or intraday low.
2. **The reversal is realised in the next close-to-close return, including the
   overnight.** A next-open entry misses the overnight gap. On the v1 event,
   the close-entry version earns roughly 30% CAGR at 1 bp versus 18% for the
   next-open version; the overnight is a large part of the reversal. The v2
   implementation therefore computes the signal at 15:58 and fills at the 15:59
   open, and exits at the next session's 15:59 open.
3. **TQQQ gives 3x the reversal; the one-session hold avoids the fade.** The
   event study shows the first session carries the edge and sessions 2-5 give
   it back. A one-session hold is not a compromise; it is the measured optimum.
4. **Three horizons capture fast, medium and slow quiet declines.** The 3-day
   leg catches shallow pullbacks (often in bull markets), the 10-day leg the
   normal multi-day pullback, and the 15-day -8% leg the deeper capitulation.
   The three legs are highly overlapping but not identical; the union raises
   the event count from 85 to 119 without destroying the per-event mean.

## 3. Hypothesis (one sentence)

On 2016-01-04 .. 2023-12-29, a QQQ decline of at least 3% over 3 sessions, 5%
over 10 sessions, or 8% over 15 sessions, on volume at most 1.2x the prior
20-day average, is followed by a positive next-session TQQQ close-to-close
return large enough that a 100% TQQQ position held only on those event days
beats TQQQ's 36.72% development CAGR with a much lower maximum drawdown.

## 4. Exact rules

Data: QQQ (signal), TQQQ (vehicle), BIL (cash); adjusted 1-minute regular
session. All signals use only data through 15:58 ET; all fills are at the next
bar's open by `research/bt.py`.

At 15:58 ET on session `d`:

```
q3   = QQQ_close_1558[d] / QQQ_close_1558[d-3]  - 1
q10  = QQQ_close_1558[d] / QQQ_close_1558[d-10] - 1
q15  = QQQ_close_1558[d] / QQQ_close_1558[d-15] - 1
rvol = volume_1558[d] / mean(volume_1558[d-20 .. d-1])
vol20 = annualised stdev(QQQ daily returns, last 20 sessions)
```

Event:

```
(q3 <= -3.0% OR q10 <= -5.0% OR q15 <= -8.0%) AND rvol <= 1.2
```

If the event is true:

- **Entry:** set the TQQQ target on the 15:58 bar, so it fills at the 15:59
  open. Size = `clip(0.80 / vol20, 0.25, 1.0)`.
- **Hold:** through the next session.
- **Exit:** set the target to 0 on the next session's 15:58 bar, so it fills at
  the 15:59 open.
- **Chain:** if the exit day is itself an event, the new event's entry
  overwrites the exit and the position stays on for another session.
- Otherwise 100% BIL. Long-only, weights >= 0, sum <= 1. No leverage beyond
  TQQQ's embedded 3x.

## 5. Why it should beat TQQQ

TQQQ's 36.72% CAGR comes with an 82.29% drawdown. v2 is in TQQQ only ~6% of
sessions and in BIL otherwise, so its drawdown should be far lower. The
measured event mean is +2.6% per event with a t-stat near 4; 119 events at 5.9%
exposure can compound to roughly 40% CAGR at 1 bp. The risk-adjusted case is
stronger than the absolute-CAGR case: the target is a Sharpe around 1.4 and a
Calmar around 1.5-2.0, versus 0.82 and 0.45 for TQQQ.

## 6. What would falsify it

1. **No event edge.** Mean next-session TQQQ return <= 0, or bootstrap
   `p(mean <= 0) > 0.05`.
2. **Placebo matches.** Random sessions with the same count, entry, hold and
   size produce a CAGR within the 90% band of the real strategy.
3. **One episode.** Excluding 2020 or 2022 drops CAGR below 10%, or the
   per-year event mean is negative in more than one year with n >= 3.
4. **Knife-edge grid.** The q3 -2.5%/-3.5% and q15 -7%/-8% neighbours all
   collapse below 20% CAGR.
5. **Costs dominate.** 10 bp CAGR < 15%, or 10 bp max drawdown > 40%.
6. **Look-ahead.** Truncating the panel at 2022-01-03 changes any prior weight.
7. **The volume cap is a cliff.** rvol 1.15 and 1.25 both collapse relative to
   1.20. This is the known fragility of the design; it must be reported, not
   hidden.

## 7. Pre-registered grid (8 combinations)

All at 1 bp, 1-minute marks, next-open fills, 2% band. The primary is row 4.
Rows 1-3 are the core without the short-horizon leg; rows 5-6 vary the q3
threshold; rows 7-8 vary the volume cap.

| # | q3 | q10 | q15 | rvol | hold | expected |
|---|---|---|---|---|---|---|
| 1 | off | -5% | off | 1.2 | 1 | core, ~29% CAGR / ~17% DD |
| 2 | off | off | -8% | 1.2 | 1 | core, ~23% CAGR / ~15% DD |
| 3 | off | -5% | -8% | 1.2 | 1 | core, ~34% CAGR / ~17% DD |
| 4 | -3% | -5% | -8% | 1.2 | 1 | **primary, ~40% CAGR / ~26% DD** |
| 5 | -2.5% | -5% | -8% | 1.2 | 1 | more events, ~41% CAGR / ~26% DD |
| 6 | -3.5% | -5% | -8% | 1.2 | 1 | fewer events, ~39% CAGR / ~21% DD |
| 7 | -3% | -5% | -8% | 1.15 | 1 | tighter volume, ~31% CAGR / ~26% DD |
| 8 | -3% | -5% | -8% | 1.25 | 1 | looser volume, ~28% CAGR / ~38% DD |

The expected plateau is rows 3-6: 34-41% CAGR with 17-26% DD. Rows 7-8 are
expected to be worse; the 1.2 volume cap is the fragile parameter, not the q3
threshold (rows 4-6 should be a plateau).

**Disclosure:** the expectations above are priors from a development-only event
study that motivated the design, not an independent sample. The final run uses
the same 2016-2023 window, so the agreement between the prior and the observed
values is not out-of-sample validation. The grid is pre-registered in the sense
that the primary and all eight rows were fixed before the final 1-minute run,
and no row was dropped or added after it.

## 8. Honest prior

The most likely outcome is a **marginal 1 bp pass**: the primary is expected to
land around 39-40% CAGR with a 26% drawdown, while the 5 bp result will be
around 34-35%, just below the TQQQ bar. The robust core (rows 1-3) is expected
to be 29-35% CAGR with a 15-17% drawdown — a clear risk-adjusted improvement,
not an absolute pass. The q3 leg is statistically weaker than the q10/q15 core
(mean +1.48%, t≈1.4 versus +3.05%, t=4.23), so part of the primary's pass is a
diversifying short-horizon sleeve, not a stronger capitulation edge. 2020 and
2022 supply most of the events (20 and 67 of 119); the per-year event mean is
positive in every year with n >= 4, but the sample is regime-tilted. Treat the
result as a candidate that needs the holdout, not as a validated standalone.

## 9. Sample adequacy

119 events over 8 years, ~15/year, 5.9% of sessions, 1 session each. The event
mean is +2.62% with t = 4.35 and a bootstrap 95% CI of +1.45% to +3.79%. That
is large enough to reject a zero mean, but not large enough to rule out regime
dependence: 73% of the events are in 2020-2022, and the 2021 sample is two
events. The report states this explicitly.
