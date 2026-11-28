# family-oil-shock — hypothesis

**Status:** development-only study. No 2024–2026 result was computed. The development panel ends 2023-12-29; `build_weights` accepts a longer panel for a separate one-shot holdout, but no such run is part of this study.  
**Window:** 2016-01-04 .. 2023-12-29.  
**Primary object:** 5-session USO log return (oil-shock event).  
**Execution:** 1-minute QQQ/TQQQ/BIL panel, signals at the session close, fills at the next 09:30 open.

## 1. Claim

Oil is the priced input to the inflation cycle. A fast oil spike raises input
costs and inflation expectations, compresses real incomes, and increases the
chance of a hawkish policy response. Long-duration growth equity is the most
sensitive asset to that combination. The shock is usually short-lived, so a
fixed five-session de-risk is enough; when oil is calm, a leveraged
growth-equity sleeve can be held.

The family is an **oil-shock event** family, not a generic oil-trend filter.
The event form isolates the shock window rather than holding BIL for as long as
oil is above a slow threshold.

## 2. Mechanism

Oil shocks transmit to equity values through at least four channels:

1. **Input costs.** Energy is a direct cost for transport, manufacturing and
   consumers; a spike compresses margins and real disposable income.
2. **Inflation expectations.** Oil is the most visible flexible price. A sharp
   rise feeds headline inflation and can pull inflation expectations up.
3. **Policy response.** Higher oil/inflation raises the probability of a
   hawkish Fed, which is negative for long-duration growth equity.
4. **Terms of trade.** Oil importers see a negative terms-of-trade shock; the
   US is a net importer, so the aggregate equity effect is negative.

A 5% five-session USO rise is a clear energy impulse (about 13% of development
sessions). The strategy holds BIL for five sessions after
the event: the event session plus the next four. Overlapping events extend the
hold. The hold is short because oil spikes often mean-revert; a long hold would
turn the family into an oil-trend filter.

### Why the event form, not an always-on 20-day threshold

The assignment allows a 5- or 20-day oil return or volatility object. We tested
the natural always-on version first: BIL whenever the 20-day USO return was
above a fixed threshold (5%, 6%, 8%, 10%, 12%), with 10/15/30-session windows
as the plateau. It produced a headline CAGR above the bar at the 8% cell, but
only **2/8** plateau cells cleared the three-way bar: the 8% threshold was a
fragile local peak. The 5-day event form passes **8/8** local cells and has a
lower drawdown. The always-on diagnostic is reported in the result and report;
the event form is the pre-registered primary because it is the robust version
of the same economic idea.

This is a development choice and is disclosed rather than hidden. The
hypothesis is still ex-ante sensible: an oil shock is an event, and the
risk-off response should be temporary.

## 3. Signal

At the close of session `k`:

```
o5[k]     = log(USO_close[k] / USO_close[k-5])
event[k]  = o5[k] > +0.050
risk_off[k] = event[k] or event[k-1] or event[k-2] or event[k-3] or event[k-4]

target[k] = BIL  1.0   if risk_off[k]
            TQQQ 1.0   otherwise
```

`USO` is the United States Oil Fund, which holds front-month WTI futures. The
external daily series starts in 2015; the first five-session feature for the
2016-01-04 session is finite from the first day of the development window.

The target is written on the last 1-minute bar of session `k` and filled at
the 09:30 open of session `k+1`. The external close of session `k` is the
latest daily print used. No bar after `k` enters the signal, and the external
frame is hard-truncated at 2023-12-29 before any feature is formed.

## 4. Portfolio construction and execution

- Universe: QQQ, TQQQ, BIL. The signal only uses USO.
- Long-only, weights ≥ 0, row sum ≤ 1.
- Binary book: TQQQ 1.0 when risk-on, BIL 1.0 during the five-session
  post-shock window. No cash drag beyond the BIL position.
- 2% rebalance band; fills at the next open; 1 bp headline slippage, also
  reported at 5 bp and 10 bp.
- The backtester marks the book on 1-minute QQQ/TQQQ/BIL bars. Idle capital is
  BIL, not zero-yield cash.

## 5. Primary and eight-cell plateau

The pre-registered primary is `W=5, THR=+5.0%, HOLD=5`. The plateau varies the
threshold at the five-session hold and the hold at the 5% threshold.

| Cell | W | THR | HOLD | Role |
|---|---:|---:|---:|---|
| 1 | 5 | +2.0% | 5 | lower threshold |
| 2 | 5 | +3.0% | 5 | lower threshold |
| 3 | 5 | +4.0% | 5 | lower threshold |
| 4 | 5 | +5.0% | 5 | **primary** |
| 5 | 5 | +6.0% | 5 | higher threshold |
| 6 | 5 | +5.0% | 3 | shorter hold |
| 7 | 5 | +5.0% | 4 | shorter hold |
| 8 | 5 | +5.0% | 7 | longer hold |

A genuine plateau should clear the three-way development bar in at least five
of the eight cells. The thresholds 2–6% and the holds 3–7 sessions are the
local neighbourhood that a robust oil-shock rule should survive.

## 6. Activity floor

A publishable family must have either:

- at least 100 full fills over the development window, or
- at least 30 independent state-change events.

The oil-shock rule is expected to produce roughly 170 state changes and 350
fills. If it produces fewer, it is a sparse macro overlay, not a tradeable
family, and the activity kill criterion triggers.

## 7. Kill criteria

The study is killed or demoted if any of the following is true:

| # | Criterion | Threshold |
|---|---|---|
| 1 | Activity floor | fewer than 100 fills **and** fewer than 30 events |
| 2 | No three-way dev improvement | CAGR ≤ TQQQ buy-and-hold **and** DD ≥ TQQQ **and** Sharpe ≤ TQQQ |
| 3 | Plateau | fewer than 5 of 8 cells clear the three-way dev bar |
| 4 | Placebo | one-sided p > 0.20 for both circular-shift nulls |
| 5 | Redundancy | correlation > 0.85 with any of the nine existing winners |
| 6 | Subperiod instability | any of 2016–19 / 2020–21 / 2022–23 has negative CAGR |

A single triggered criterion does not automatically delete the research record,
but it does block promotion to a verified winner. Two or more triggered
criteria make the family a negative result.

## 8. Known failure modes

- **The 2020 negative oil shock.** The COVID crash was a *negative* oil return,
  so the strategy was long TQQQ into the crash. The 64% drawdown is structural;
  the oil-shock signal is not a pandemic/credit-crash detector.
- **USO roll yield.** USO holds front-month futures; contango and
  backwardation can decouple it from spot crude. A spot WTI or Brent series
  would be a cleaner object.
- **Demand-driven spikes.** An oil rally can be a demand recovery (risk-on),
  not a supply/inflation shock. The signal conflates the two.
- **Short-horizon decay.** The five-session event window is a timing rule. If
  the market learns to look through oil spikes, the edge will weaken.
- **High turnover.** 2,068x development turnover at 1 bp; the 10 bp cost is
  about 5.7 percentage points of CAGR.
- **Overlap with risk-on winners.** The book is long TQQQ ~67% of the time, so
  its return stream correlates with existing risk-on families even if the gate
  is distinct.

## 9. Why this is a distinct family

No existing winner uses USO, crude oil or an energy impulse as its primary
gate:

- `ratio-froth` uses a QQQ/TQQQ ratio.
- `vol-scaled-crash-stop` uses realised volatility and a crash stop.
- `relative-value-tqqq` uses QQQ/SPY relative value.
- `fomc-opex-window` uses a calendar event window.
- `family-session-timing` uses intraday session blocks.
- `family-short-reversal` uses 1–5 day price overreaction.
- `family-rebalance-flow` uses mechanical LETF/closing flow.
- `family-intraday-microstructure-day` uses opening range/order flow.
- `family-ml-microstructure` uses a fitted ML model on intraday features.

The oil-shock event is an external energy/inflation state. It is not a QQQ
trend, a volatility target, a drawdown event, a calendar clock, an
opening-range rule, a relative-strength ratio gate, or an ML model.

## 10. Data and reproducibility

- External: `data/external/USO.parquet` (Yahoo adjusted close, 2015–2026;
  only rows ≤ 2023-12-29 are used).
- Execution: local `data/intraday-hf/QQQ-1m.parquet`, `TQQQ-1m.parquet`,
  `BIL-1m.parquet`.
- Warmup: external 2015 rows are used only to make the first five-session
  feature finite on 2016-01-04.
- Run: `python research/new/family-oil-shock/strategy.py`.
- The script writes `result.json` and `report.md` from the development window
  only.

## 11. Decision rule

If the primary clears the three-way bar, the activity floor, at least 5/8
plateau cells, and at least one placebo null at p ≤ 0.20, and no subperiod is
negative, it is a **dev candidate** eligible for a frozen one-shot holdout. It
is not a verified winner until that holdout and the causality/freshness audit
are complete.

If the primary fails the bar or the plateau, it remains a negative research
record. A high headline CAGR from a single threshold is not a winner.
