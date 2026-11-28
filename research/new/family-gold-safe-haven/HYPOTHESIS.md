# family-gold-safe-haven — hypothesis

**Status:** development-only study. No 2024–2026 result was computed. The development panel ends 2023-12-29; `build_weights` accepts a longer panel for a separate one-shot holdout, but no such run is part of this study.  
**Window:** 2016-01-04 .. 2023-12-29.  
**Primary object:** 5-session GLD log return (gold shock).  
**Execution:** 1-minute QQQ/TQQQ/BIL panel, signals at the session close, fills at the next 09:30 open.

## 1. Claim

Gold is the oldest safe-haven asset. A fast, large gold rally is a market
signal that demand for safety or a real-rate hedge has risen. If that demand is
genuine, equity risk should be reduced for a short window. When gold is quiet,
the fear premium is low and a leveraged growth-equity sleeve can be held.

The family is deliberately a **gold-shock** family, not a gold-trend family. A
five-session impulse is an event; a twenty-session gold return is a different
object (a gold bull/bear trend) and is not the primary.

## 2. Mechanism

Gold has no cash flow, so its price is especially sensitive to real rates, the
dollar and tail-risk demand. In a flight to safety:

1. Real yields fall, which lowers the opportunity cost of holding gold.
2. Investors buy gold as a hedge against equity/geopolitical tail risk.
3. The dollar may also rally, but gold's own impulse is the cleanest
   cross-asset fear signal.

A 3.5% five-session rise is a large move (about 4% of development sessions,
roughly the top 5% of the distribution). The event triggers a three-session BIL hold: the
event session plus the next two. The hold is short because safe-haven spikes
often mean-revert quickly; a long hold would become a gold-trend filter and
would also overlap with the existing trend families.

The signal is **absolute GLD momentum**, not GLD/QQQ relative strength. This is
intentional: the assignment bans a generic relative-strength ratio gate, and a
GLD/QQQ 20-day relative-strength variant was tested in development and was
materially weaker (about 18–26% CAGR in the same 1-minute harness, depending
on threshold, versus 42.9% for the absolute shock). The absolute gold shock is
the cleaner expression of safe-haven demand.

## 3. Signal

At the close of session `k`:

```
g5[k]    = log(GLD_close[k] / GLD_close[k-5])
event[k] = g5[k] > +0.035
risk_off[k] = event[k] or event[k-1] or event[k-2]

target[k] = BIL  1.0   if risk_off[k]
            TQQQ 1.0   otherwise
```

`GLD` is the SPDR Gold Shares ETF. The external daily series starts in 2015;
the first five-session feature for the 2016-01-04 session is finite from the
first day of the development window.

The target is written on the last 1-minute bar of session `k` and filled at
the 09:30 open of session `k+1`. The external close of session `k` is the
latest daily print used. No bar after `k` enters the signal, and the external
frame is hard-truncated at 2023-12-29 before any feature is formed.

## 4. Portfolio construction and execution

- Universe: QQQ, TQQQ, BIL. The signal only uses GLD.
- Long-only, weights ≥ 0, row sum ≤ 1.
- Binary book: TQQQ 1.0 when risk-on, BIL 1.0 during the three-session
  post-shock window. No cash drag beyond the BIL position.
- 2% rebalance band; fills at the next open; 1 bp headline slippage, also
  reported at 5 bp and 10 bp.
- The backtester marks the book on 1-minute QQQ/TQQQ/BIL bars. Idle capital is
  BIL, not zero-yield cash.

## 5. Primary and eight-cell plateau

The pre-registered primary is `W=5, THR=+3.5%, HOLD=3`. The plateau varies the
two parameters that define the shock: threshold and hold. The lookback is
fixed at the hypothesised five sessions.

| Cell | W | THR | HOLD | Role |
|---|---:|---:|---:|---|
| 1 | 5 | +3.0% | 3 | lower threshold |
| 2 | 5 | +3.5% | 3 | **primary** |
| 3 | 5 | +4.0% | 3 | higher threshold |
| 4 | 5 | +4.5% | 3 | higher threshold |
| 5 | 5 | +3.0% | 4 | longer hold |
| 6 | 5 | +3.5% | 4 | longer hold |
| 7 | 5 | +4.0% | 4 | longer hold |
| 8 | 5 | +4.5% | 4 | longer hold |

A separate horizon diagnostic varies the lookback to 3, 10 and 20 sessions at
the primary threshold and hold. It is not part of the primary plateau; it is a
fragility check. A gold-shock rule that only works at one lookback is a
short-horizon event rule, not a general safe-haven regime.

## 6. Activity floor

A publishable family must have either:

- at least 100 full fills over the development window, or
- at least 30 independent state-change events.

The gold rule is expected to produce roughly 60 state changes and 120 fills. If
it produces fewer, it is a sparse event overlay, not a tradeable family, and
the activity kill criterion triggers.

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
criteria make the family a negative result. The horizon diagnostic is a
fragility flag: if a 10- or 20-session lookback collapses below half the
primary CAGR, the family is not a general safe-haven rule even if the 5-day
cell passes.

## 8. Known failure modes

- **2022 inflation shock.** Gold and equities can fall together when the shock
  is an inflation/real-rate shock rather than a growth scare. A gold rally is
  not always a flight to safety; it can be a commodity-supply signal.
- **Lagging fear indicator.** A five-day gold rally may occur after the equity
  drawdown has started, so the BIL hold arrives late.
- **Short-horizon fragility.** The 10- and 20-session gold windows are much
  weaker than the 5-session shock. The family is an event overlay, not a
  regime model.
- **Near-redundancy.** The book is long TQQQ ~93% of the time, so its return
  stream is close to the existing risk-on winners even though the gate is
  distinct.
- **No flow/real-rate data.** The signal uses only price; it cannot tell a
  genuine safe-haven bid from a commodity supply shock.

## 9. Why this is a distinct family

No existing winner uses gold, a safe-haven commodity, as its primary gate:

- `ratio-froth` uses a QQQ/TQQQ ratio.
- `vol-scaled-crash-stop` uses realised volatility and a crash stop.
- `relative-value-tqqq` uses QQQ/SPY relative value.
- `fomc-opex-window` uses a calendar event window.
- `family-session-timing` uses intraday session blocks.
- `family-short-reversal` uses 1–5 day price overreaction.
- `family-rebalance-flow` uses mechanical LETF/closing flow.
- `family-intraday-microstructure-day` uses opening range/order flow.
- `family-ml-microstructure` uses a fitted ML model on intraday features.

A fast GLD impulse is a distinct cross-asset fear state. It is not a QQQ trend,
a volatility target, a drawdown event, a calendar clock, an opening-range rule,
a relative-strength ratio gate, or an ML model.

## 10. Data and reproducibility

- External: `data/external/GLD.parquet` (Yahoo adjusted close, 2015–2026;
  only rows ≤ 2023-12-29 are used).
- Execution: local `data/intraday-hf/QQQ-1m.parquet`, `TQQQ-1m.parquet`,
  `BIL-1m.parquet`.
- Warmup: external 2015 rows are used only to make the first five-session
  feature finite on 2016-01-04.
- Run: `python research/new/family-gold-safe-haven/strategy.py`.
- The script writes `result.json` and `report.md` from the development window
  only.

## 11. Decision rule

If the primary clears the three-way bar, the activity floor, at least 5/8
plateau cells, and at least one placebo null at p ≤ 0.20, and no subperiod is
negative, it is a **dev candidate** eligible for a frozen one-shot holdout. It
is not a verified winner until that holdout and the causality/freshness audit
are complete.

If the primary fails the bar or the subperiod stability test, it remains a
negative research record. A safe-haven signal that fails in the one
inflationary bear market in the sample is not a reliable hedge.
