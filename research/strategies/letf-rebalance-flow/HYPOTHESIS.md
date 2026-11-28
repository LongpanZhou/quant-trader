# Hypothesis: Relative Nasdaq flow dip (RN Flow)

**Status:** design / pre-registration only. Backtests are **paused** (2026-11-26).
No `result.json` has been generated. Nothing in this folder is a result.

**Slug:** `letf-rebalance-flow`
**Original:** `research/agents2/letf-rebalance-flow`

## 1. Extracted idea

The old strategy was an overlay on the 165-day QQQ/TQQQ winner: on a *risk-off*
session, if QQQ was up more than 1.5% by 14:59, it bought TQQQ for the last hour
and exited before the close, because the overnight after those rallies reversed.
The genuinely new part is not the TQQQ trend base; it is the claim that **the
end-of-day move contains temporary leveraged-ETF / options-hedging pressure that
partly reverses afterwards**.

## 2. Why the old implementation could not stand alone

The old overlay owned the position for only one hour on ~96 days in ten years.
Its standalone version (same signal, no winner underneath) returned about
7%/yr, far below TQQQ, and the default-long version that kept TQQQ most of the
time was 0.64-0.72 correlated with the old base. The idea was real only as a
small add-on to a long TQQQ book.

The redesign therefore changes the object being traded. Instead of an absolute
QQQ late-day move, it uses the **relative** QQQ-vs-SPY end-of-day move, which
isolates the Nasdaq-specific part of the flow from the broad market. Instead of
a one-hour trade, it holds the reversal for several sessions, which gives the
signal enough exposure to be a standalone strategy. It uses no 165-day (or any
100-250-day) moving-average gate and no old base weights.

## 3. Hypothesis

**H1 (signal):** when QQQ underperforms SPY by a large standardized amount on
day *t*, a meaningful part of that relative move is temporary Nasdaq-specific
flow pressure (LETF rebalancing, options delta-hedging, index arbitrage), not
information. The relative move should therefore partly reverse over the next
few sessions.

**H2 (tradable form):** buying TQQQ at the next open after such a relative dip,
holding for three sessions, and sitting in BIL otherwise produces a positive,
standalone return with daily-return correlation below 0.60 to the old 165-day
TQQQ/BIL baseline.

**H3 (not just beta):** the signal-day return exceeds the unconditional TQQQ
return over the same three-session windows, and a random-entry placebo with the
same holding period and exposure does not reproduce it.

The economic prior is that the Nasdaq-100 complex has the largest leveraged-ETF
and options complex, so its end-of-day flow shock is disproportionately
Nasdaq-specific. SPY is the hedge/benchmark that lets us measure "Nasdaq-specific"
without shorting.

## 4. Complete strategy specification (pre-registered base)

| Choice | Base rule | Why |
|---|---|---|
| Traded universe | TQQQ, BIL | TQQQ gives the Nasdaq reversal enough amplitude; BIL is the risk-off asset. Both are markable on the existing 1-minute panel. |
| Signal universe | QQQ daily close, SPY daily close | SPY is used only to compute the relative move, never held. The 1-minute SPY history needed for an intraday version is not available for the development period (only late 2026), so the daily close-to-close relative return is the flow proxy. |
| Signal | `rel_t = r_QQQ,t - r_SPY,t`; `sigma_t = std(rel, 20)` through *t-1*; `z_t = rel_t / sigma_t` | Standardized relative move; no absolute market-direction gate. |
| Entry | If `z_t < -1.25` and flat, set TQQQ at day *t*'s close; fill at day *t+1*'s open | The signal uses only the close of *t*; the fill is the next open. No look-ahead. |
| Holding | 3 sessions (fill at *t+1* open; sell at *t+4* open) | The overnight reversal is one part; the relative convergence may take several sessions. 1/2/5 sessions are pre-registered neighbours. |
| Sizing | 100% TQQQ on a signal, 100% BIL otherwise; no leverage, no shorts | Long-only; the engine is long-only. |
| Overlap | Ignore new signals while a position is open; one position at a time | Avoids pyramiding and makes the event count clean. |
| Risk | Base: no stop. Variant only: exit if TQQQ closes 10% below the entry open, fill next open | The stop is a disaster control, not the edge; it is tested as a variant, not mixed into the base. |
| Costs | 1 bp headline; 5 bp and 10 bp reported | Standard. |
| Marks | 1-minute QQQ/TQQQ/BIL panel | The daily target is broadcast to minutes with the same fill times as the daily run. |

**Signal timing / fill timing:** the daily close of *t* is known at 16:00 ET. The
target is set at the last 1-minute bar of *t* and fills at the next session's
09:30 open. The position is held through the last bar of the third session and
sold at the following open. This is identical to the daily engine's next-open
convention and introduces no look-ahead.

**Why this is not the old base:** no QQQ/TQQQ/SPY/NDX 100-250-day moving
average; no round-1 4% stop; no old `build_weights` or old weights; the position
is driven by a relative QQQ-SPY event, not by a slow trend; the risk asset is
TQQQ only on event days, not as a permanent base.

## 5. Expected correlation with the old base

**Expected: 0.25-0.45.** The old base is long TQQQ on roughly 80% of sessions;
this strategy is long TQQQ on roughly 10-15% of sessions and BIL otherwise.
Relative-dip days are more likely in risk-off or rotation periods, when the old
base is often in BIL, which lowers the overlap further. The TQQQ leg makes the
correlation higher than a QQQ-only version would be; a QQQ-risk-asset variant is
pre-registered as a lower-correlation, lower-return check.

**Expected correlation with other rebuilds:** unknown until the lead computes
the matrix. The closest neighbour is `gap-capitulation-reversal` (buying after a
gap-down); this strategy uses an intraday/close relative underperformance, not a
gap, and holds three sessions, but the lead should check the pair.

## 6. What would falsify it

1. **No predictive power:** the coefficient of the next 1/3-session TQQQ return
   on `z_t` is ≤ 0, or its HAC t-statistic is below 2.
2. **Too correlated:** development daily-return correlation with the 165-day
   baseline is ≥ 0.60.
3. **No excess return:** development CAGR is below BIL, or Sharpe < 0.3.
4. **Fragile event count:** fewer than 100 events and a bootstrap p-value above
   0.10; or the result is driven by a single sub-period (2020) or a single side
   (only up-market dips or only down-market dips).
5. **Costs kill it:** the edge disappears at 5 bp or 10 bp.
6. **Placebo:** random entries with the same number of events, holding period
   and exposure produce a similar CAGR/Sharpe.
7. **Just beta:** the strategy's signal-day return is no better than
   unconditional TQQQ over the same three-session windows.
8. **Leverage artefact:** the QQQ-risk-asset version has no edge (i.e. the
   result is only the 3x beta of TQQQ, not a relative-value reversal).

## 7. Data and evidence status

- Traded prices: `data/intraday-hf/QQQ-1m.parquet`, `TQQQ-1m.parquet`,
  `BIL-1m.parquet` (adjusted, regular session).
- Signal prices: `data/intraday-hf/QQQ-1d-yahoo.parquet`,
  `data/round3/yahoo/SPY-1d-yahoo.parquet` (daily adjusted closes, 2015-2026).
- There is **no** 1-minute SPY history for 2016-2023; `data/cache/dukascopy/SPY`
  contains only 2026-08-31 onward. That is why the signal uses the daily
  close-to-close relative move rather than a last-hour QQQ-vs-SPY move.
- Preliminary evidence only (from the old overlay's event study, not a test of
  this strategy): the old 96 risk-off late-rally events had TQQQ last-hour
  +64 bp and next-overnight -90 bp; the overnight reversal regression on the
  absolute last-hour move had a coefficient of -2,886 bp per unit (HAC t =
  -2.27) controlling for the day's move. The old pure standalone last-hour
  strategy returned ~7.7%/yr, and the default-long exit version was 0.64-0.72
  correlated with the old base. Those two failures are the reason for the
  relative-value, multi-session redesign.

## 8. Pre-registered evaluation plan (not run)

- Development only: 2016-01-04 → 2023-12-29. Holdout 2024-2026 is not inspected.
- 1 bp headline; 5 bp and 10 bp.
- Neighbourhood: z threshold {-1.00, -1.25, -1.50}; hold {1, 2, 3, 5} sessions;
  pick from a plateau, not the peak.
- Sub-periods: 2016-19, 2020-21, 2022-23.
- Placebo: random entry days matched on count and holding period; 1,000 draws.
- Event count and bootstrap p-value if <100 events.
- Benchmarks: TQQQ, QQQ, SPY buy-and-hold; original strategy's result.json.
- Correlations: 165-day baseline, plus the lead's cross-rebuild matrix.
- Report the QQQ-risk-asset variant (no leverage) as the "is it just beta?" test.
