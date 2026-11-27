# Spec — quiet oversold capitulation reversal (revisit)

**Slug:** `gap-capitulation-reversal`
**Engine:** `research/bt.py` (`bt.run`, `bt.run_many`, `simcore`)
**Universe:** QQQ, TQQQ, BIL (1-minute, regular session). SPY daily is
benchmark-only; the local source file says it must not be traded in a rebuild
(`data/round3/yahoo/SOURCE.md`).
**Development window:** 2016-01-04 → 2023-12-29.
**Holdout:** 2024-01-02 → 2026-10-23 — **never inspected by this agent**.
**Status:** pre-registered; not yet run.

## 1. Data and timing

- 1-minute QQQ/TQQQ/BIL from `data/intraday-hf/`, regular session only
  (09:30–15:59 ET), via `bt.panel(("QQQ","TQQQ","BIL"), start, end, "1min")`.
- Session boundaries come from the panel's dates, not from wall-clock time;
  half-days end at their last bar (13:00 on the 18 early closes).
- QQQ daily low and volume are aggregated from `bt.load_1m("QQQ")` and
  reindexed to the panel's session dates.
- A signal is set at bar `i`'s close and fills at bar `i+1`'s open. A daily
  decision made at the event day's close therefore fills at the next session's
  first bar open (09:30). This is the only entry used.
- The event-low stop and the hard stop use the current minute's close and fill
  at the next minute's open. The time exit sells at the 15:59 open of the last
  held session by setting the weight to 0 at the 15:58 bar (the harness'
  next-open convention).
- 2% band on rebalancing. Costs 1 bp headline, 5 bp and 10 bp reported.
- Equity is marked on every 1-minute bar.

## 2. Daily indicators (all through the event day's close)

For session `d`:

- `qret[d] = QQQ_close[d] / QQQ_close[d-1] - 1`
- `qdd[d]  = QQQ_low[d]  / QQQ_close[d-1] - 1`
- `q20[d]  = QQQ_close[d] / QQQ_close[d-20] - 1`
- `rvol[d] = QQQ_volume[d] / mean(QQQ_volume[d-20..d-1])`
- `vol20[d] = annualised stdev(QQQ daily returns d-19..d) * sqrt(252)`
  (the event day is included; it is known at the close)

All indicators are `NaN` for the first 20 sessions; a `NaN` event is false.
No 100–250-day moving average is used anywhere in the strategy.

## 3. Event definition

A **quiet oversold capitulation** occurs at the close of session `d` when all
three are true:

1. **Capitulation:** `qret[d] <= -0.020` **or** `qdd[d] <= -0.030`.
2. **Quiet:** `rvol[d] <= 1.20`.
3. **Oversold:** `q20[d] <= -0.030`.

The `or` in (1) is inclusive: a day that both closes down 2% and trades 3%
below the prior close is one event, not two.

## 4. Entry

- At the open of session `d+1`, buy the offensive asset at 100% of equity.
- **Offensive asset:** TQQQ if `vol20[d] <= 0.30`, otherwise QQQ.
  (QQQ is the de-risked version of the same Nasdaq-100 exposure; the switch is
  a volatility rule, not a trend gate.)
- If a new event occurs while a position is open, the holding window is
  extended to 3 sessions from the new event, and the asset, entry price and
  event-low stop are reset to the new event. There is one position at a time.

## 5. Holding period and exits

- **Time exit:** hold the entry session and the next two sessions (3 sessions
  total). Sell at the 15:59 open of the third session (weight set to 0 on the
  15:58 bar). If a new event extends the window, the 3-session clock restarts.
- **Event-low stop:** while holding, if QQQ's minute close is below the
  event-day low, sell the asset at the next minute's open and stay in BIL until
  a new event. This is the "thesis broken" stop: a new low after the
  capitulation means absorption failed.
- **Hard stop:** if the held asset's minute close is 8% below the entry fill,
  sell at the next minute's open and stay in BIL until a new event. This is a
  backstop for a gap through the event low.
- **No regime exit.** There is no 165-day (or any 100–250-day) moving-average
  condition. The event and these exits own the position.
- If neither stop nor the time exit fires, the position is BIL between events.

## 6. Sizing

- 100% of the chosen asset while in a trade; 100% BIL otherwise.
- No leverage beyond TQQQ's own 3x; no shorts; weights sum to <= 1.
- The TQQQ/QQQ switch is the only sizing/risk knob. A 50% TQQQ + 50% BIL
  version for high-vol events is a neighbour, not the base.

## 7. Base parameters (pre-registered)

| Parameter | Value | Meaning |
|---|---:|---|
| `drop` | 0.020 | QQQ close-to-close trigger |
| `intraday` | 0.030 | QQQ low vs prior close trigger |
| `rvol_max` | 1.20 | quiet-volume cap |
| `oversold` | 0.030 | QQQ 20-day return cap |
| `hold` | 3 | sessions held |
| `vol_max` | 0.30 | TQQQ if 20-day vol <= this, else QQQ |
| `hard_stop` | 0.08 | hard stop from entry |
| `event_low_stop` | on | QQQ close below event low |

## 8. Neighbourhood and ablations (fixed before the run)

One-at-a-time ±1 step around the base; every row is reported, not only the
best:

- `drop`: 0.015 / **0.020** / 0.025
- `intraday`: 0.025 / **0.030** / 0.035
- `rvol_max`: 1.00 / **1.20** / 1.50
- `oversold`: 0.000 (off) / **0.030** / 0.050
- `hold`: 1 / **3** / 5
- `vol_max`: 0.25 / **0.30** / 0.35
- `hard_stop`: 0.06 / **0.08** / 0.10
- `event_low_stop`: **on** / off

Ablations: no volume filter; no oversold filter; always TQQQ; always QQQ;
no event-low stop; no hard stop; 50% TQQQ + 50% BIL in high vol.

`variants_tried` is the count of these rows plus the base (23). No other
grid is run before the freeze.

## 9. Evaluation

- Dev: CAGR, max DD (1-minute marks), Sharpe, Sortino, fills, turnover,
  exposure, ending equity, at 1/5/10 bp.
- 10y (2017-01-03 →) and 5y (2021-10-25 →): reported by the lead; they overlap
  the holdout and must be labelled as such.
- Holdout: the lead runs the frozen strategy once. This agent does not run it.
- Correlation: daily returns of the strategy vs the 165-day baseline on the dev
  window. The baseline is used **only** for this correlation and the benchmark
  table, never inside `build_weights`.
- Benchmarks: TQQQ, QQQ, SPY buy-and-hold; the original strategy's
  `result.json` numbers.
- Sub-periods: 2016–2019, 2020–2021, 2022–2023.
- Placebo: random event days, same count and hold, 1,000 draws; report the
  percentile of the real CAGR.
- Bootstrap: 10,000 resamples of the event 3-session returns; p-value for
  mean <= 0. Required because the event count is below 100.
- Sign conventions: `<=` is inclusive; a stop triggers on a strict `<` below
  the level.

## 10. Implementation contract

`strategy.py` must expose:

```python
def build_weights(ts, opens, closes, qlow, qvol, params=None) -> (weights, info)
```

- `weights` is `(n, 3)` for QQQ/TQQQ/BIL, non-negative, rows sum to <= 1.
- `info` contains event dates, trade count, stop counts, exposure and the
  effective parameters.
- `main()` loads the dev panel, builds the weights, runs 1/5/10 bp, computes
  the baseline correlation and benchmarks, and writes `result.json`.
- `main()` must not load data after `2023-12-29` unless the caller explicitly
  passes the overlap flag; the subagent run is dev-only.
- No call to, or copy of, the old `build_weights` or the round-1 winner's
  weights. The 165-day baseline is built only in `benchmark_weights()` for the
  correlation/benchmark, clearly separated from the strategy path.
