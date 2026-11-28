# Quiet Capitulation Reversal v2 — hypothesis and repair plan

**Status:** repaired, development window only. 2016-01-04 .. 2023-12-29.
**Original:** `research/revisit/gap-capitulation-reversal` (30 events, 24
starts, 3.95% exposure, 8.30% CAGR / 10.26% DD / 0.88 Sharpe at 1 bp).
**Data:** QQQ (signal), TQQQ (risk), BIL (cash), adjusted 1-minute regular
session; QQQ daily low/volume only through 2023-12-29.  No 2024+ row is used.
**Harness:** `research/bt.py`, next-open fills, 2% band, 1/5/10 bp.

---

## 1. Diagnosis: why v1 traded only 30 times at 3.95% exposure

v1 required **all** of:

- a QQQ close <= -2.0% **or** an intraday low <= -3.0% vs the prior close;
- event-day volume <= 1.2x the prior 20-day average;
- QQQ 20-day return <= -3.0%.

Each condition is individually reasonable.  Together they select only 30 events
in eight years, clustered in 2016, 2018, 2020 and 2022.  Three further problems:

1. **The 3-session hold is very short.**  24 starts x 3 sessions = 102 invested
   days = 3.95% of 2,012 sessions.
2. **The 30% volatility cap binds at almost every event.**  QQQ 20-day
   realised vol is above 30% at most capitulations, so v1 held **QQQ** in 20 of
   24 trades and TQQQ in only 4.  The reversal was monetised at 1x.
3. **The event-low stop was already turned off** in the pre-run tuning; the
   remaining 8% hard stop fires rarely (1 of 24 trades).  The exits are not the
   cause of the low exposure.

The low exposure is therefore inherent to a 3-day event.  The repair targets
the **event count and the holding period**, and makes a modest risk-cap change
so the TQQQ vehicle is actually used at 30-35% volatility.  It does not try to
force 20% exposure out of a 5-day reversal: that would require holding through
the part of the window where the event study says the edge decays.

## 2. What is preserved

- The event remains a **quiet, short-term-oversold capitulation**: a large QQQ
  decline on below-average volume while QQQ is already 20-day oversold.
- The next-open entry, one-position-at-a-time clock, 8% hard stop, and
  `event_low_stop=False` are unchanged.
- The vehicle is still TQQQ below the volatility cap and QQQ above it.
- No 165-day (or any 100-250 day) moving average is used.  Long-only, weights
  >= 0 and sum <= 1.

## 3. What changed, and why

| Parameter | v1 | v2 | Reason |
|---|---:|---:|---|
| `drop` | 0.020 | **0.015** | The -2% close leg and the -3% intraday leg overlapped heavily.  A -1.5% close is still a large one-day decline for QQQ and lifts the sample from 30 to 39 events without dropping the quiet or oversold conditions. |
| `hold` | 3 | **5** | Pre-registered event study: the 5-session TQQQ mean is at least as strong as the 3-session mean, and the original hypothesis already reported a stronger 5-day than 3-day effect.  The 5-day hold roughly doubles invested days. |
| `vol_max` | 0.30 | **0.35** | 30% was binding at 31-34% vol events, forcing QQQ exactly when the reversal was strongest.  35% keeps the 2020 crash (79-92% vol) and the 2022 May/June cluster (36-45%) in QQQ, but lets TQQQ participate in the 30-35% events. |

Everything else is v1: `intraday=0.030`, `rvol_max=1.20`, `oversold=0.030`,
`hard_stop=0.08`, `event_low_stop=False`, `size=1.0`, `high_vol="QQQ"`.

## 4. Pre-registered plateau grid (8 variants)

Fixed before the final run.  One-at-a-time around the primary.

| # | Variant | Change |
|---|---|---|
| 1 | primary | `drop=0.015, hold=5, vol_max=0.35` |
| 2 | drop 1.25 | `drop=0.0125` |
| 3 | drop 1.75 | `drop=0.0175` |
| 4 | hold 3 | `hold=3` |
| 5 | hold 8 | `hold=8` |
| 6 | vol cap 30 | `vol_max=0.30` |
| 7 | vol cap 40 | `vol_max=0.40` |
| 8 | rvol 1.3 | `rvol_max=1.30` |

All eight are reported in `result.json` and `report.md`.  A result that only
works at the primary point, with a cliff on both sides, is treated as fitted.

## 5. Falsifiers for the repair

1. Fewer than 20 events, or fewer than 15 independent starts.
2. The event mean is <= 0, or its bootstrap p-value is > 0.10.
3. The heavy-volume subset is at least as good as the quiet subset (the volume
   condition is the core mechanism and must survive).
4. Any of 2016-19, 2020-21, 2022-23 has a negative mean event return, or 2020
   accounts for more than half of the total event P&L.
5. Removing the single best trade drops CAGR below 10% (one-trade dependence).
6. A circular-shift placebo with the same holding lengths and asset mix has a
   median CAGR within 5 pp of the strategy, or p(CAGR >= strategy) > 0.10.
7. Dev CAGR < 3%, Sharpe < 0.30, or max drawdown > 25% at 1 bp.
8. The 10 bp CAGR is below 2%, or the 10 bp drawdown is more than 5 pp worse
   than the 1 bp drawdown.

The 20% average-exposure target is **not** a falsifier for this family.  A
5-session event with 39 occurrences cannot reach 20% exposure without
overlapping positions or holding through the decay; the report states this
explicitly rather than forcing the number.

## 6. Timing

The event is known at the close of day d.  The target is written on day d's
last 1-minute bar and fills at day d+1's first bar open.  The time exit writes
0 on the last held session's penultimate bar, so it fills at the 15:59 open of
the fifth session.  The 1-minute panel is physically sliced at 2023-12-29, and
the QQQ daily low/volume file is read with a UTC timestamp filter and a
`date <= 2023-12-29` daily filter.

## 7. Files

- `strategy.py` — implementation and `--run`; writes `result.json`.
- `result.json` — cost ladder, event study, 26 trades, sub-periods, 8-row grid.
- `robustness.py` / `robustness.json` — leave-one-trade-out, circular-shift
  placebo, max-drawdown window.
- `diagnose.py` — exploratory event/definition sweeps that motivated the fix
  (not part of the pre-registered grid; writes `diagnose.json` when run).
