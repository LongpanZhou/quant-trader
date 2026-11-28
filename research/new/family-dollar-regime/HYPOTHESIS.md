# family-dollar-regime — hypothesis

**Status:** development-only study. No 2024–2026 result was computed. The development panel ends 2023-12-29; `build_weights` accepts a longer panel for a separate one-shot holdout, but no such run is part of this study.  
**Window:** 2016-01-04 .. 2023-12-29.  
**Primary object:** 60-session UUP log return (dollar impulse).  
**Execution:** 1-minute QQQ/TQQQ/BIL panel, signals at the session close, fills at the next 09:30 open.

## 1. Claim

A broad, persistent appreciation of the US dollar is a global tightening
shock. It raises the dollar value of foreign borrowers' liabilities, squeezes
cross-border credit, and is disproportionately negative for long-duration US
growth equity. When the dollar is flat or weakening, global liquidity is stable
or expanding and a leveraged growth-equity sleeve is supported.

The claim is directional but not symmetric. The strategy is **not** long TQQQ
because the dollar is falling; it is long TQQQ unless the dollar has just
appreciated enough to signal stress. The risk-off state is the exception, not
the base case.

## 2. Mechanism

The dollar is the funding currency of the global financial system. A large
trade-weighted appreciation tightens conditions through at least four channels:

1. **Foreign-currency debt service.** Non-US borrowers with dollar liabilities
   see their real burden rise. Credit spreads widen and dollar funding demand
   spikes.
2. **Global reserve / safe-haven demand.** Stress episodes produce a flight
   into dollars, which is itself a risk-off signal.
3. **Import prices and inflation.** A stronger dollar lowers US import prices,
   but the immediate effect on global risk assets is tighter conditions, not
   lower inflation.
4. **Earnings translation.** Large US multinationals earn abroad; a stronger
   dollar reduces translated earnings, with growth/technology names more
   sensitive to duration.

The 60-session window is long enough to distinguish a dollar *impulse* from
daily noise, but short enough to react within a quarter. The +3% threshold is a
large move: in the 2015–2023 development data, the 60-session UUP return is
above +3% in about 20% of sessions (top quintile). The strategy does not use a
QQQ 100–250 day trend, a volatility target, a drawdown event, or a calendar
clock. The only state variable is the dollar impulse.

## 3. Signal

At the close of session `k`:

```
u60[k] = log(UUP_close[k] / UUP_close[k-60])

target[k] = TQQQ 1.0   if u60[k] <= +0.030
            BIL  1.0   otherwise
```

`UUP` is the Invesco DB US Dollar Index Bullish Fund, which tracks the ICE US
Dollar Index (EUR, JPY, GBP, CAD, SEK, CHF). The external daily series starts
in 2015; the first 60-session feature for the 2016-01-04 session is therefore
finite from the first day of the development window.

The target is written on the last 1-minute bar of session `k` and filled at
the 09:30 open of session `k+1`. The external close of session `k` is the
latest daily print used. No bar after `k` enters the signal, and the external
frame is hard-truncated at 2023-12-29 before any feature is formed.

## 4. Portfolio construction and execution

- Universe: QQQ, TQQQ, BIL. The signal only uses UUP.
- Long-only, weights ≥ 0, row sum ≤ 1.
- Binary book: TQQQ 1.0 when risk-on, BIL 1.0 when risk-off. No cash drag
  beyond the BIL position.
- 2% rebalance band; fills at the next open; 1 bp headline slippage, also
  reported at 5 bp and 10 bp.
- The backtester marks the book on 1-minute QQQ/TQQQ/BIL bars. Idle capital is
  BIL, not zero-yield cash.

## 5. Primary and eight-cell plateau

The pre-registered primary is `W=60, THR=+3.0%`. The plateau is a local cross:
five thresholds at the primary window plus three nearby windows at the primary
threshold.

| Cell | W | THR | Role |
|---|---:|---:|---|
| 1 | 60 | +2.0% | tighter risk-off |
| 2 | 60 | +2.5% | tighter risk-off |
| 3 | 60 | +3.0% | **primary** |
| 4 | 60 | +3.5% | looser risk-off |
| 5 | 60 | +4.0% | looser risk-off |
| 6 | 20 | +3.0% | faster impulse |
| 7 | 40 | +3.0% | intermediate |
| 8 | 80 | +3.0% | slower impulse |

A genuine plateau should clear the three-way development bar in at least five
of the eight cells. The cells are not a search grid; they are the local
neighbourhood that a robust dollar-impulse rule should survive.

## 6. Activity floor

A publishable family must have either:

- at least 100 full fills over the development window, or
- at least 30 independent state-change events.

The dollar rule is expected to produce roughly 60–70 state changes and 120–140
fills. If it produces fewer, it is a low-activity macro overlay, not a
tradeable family, and the activity kill criterion triggers.

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

- **Growth-driven dollar strength.** A stronger dollar can reflect US growth
  exceptionalism and be equity-positive, not a funding shock. The 60-session
  return cannot distinguish the two.
- **Late signal.** The dollar often peaks *after* the equity drawdown has
  started. The strategy can be long TQQQ into the first leg of a crash (2020)
  and only de-risk after the dollar has already moved.
- **UUP basket composition.** UUP is heavily EUR/JPY; a broad trade-weighted
  dollar index would be a better object. The result is conditional on the UUP
  basket.
- **One dollar cycle.** The development window contains one major dollar cycle
  (2016–2023). The +3% threshold is not estimated on a long sample.
- **Overlap with risk-on winners.** The book is long TQQQ ~80% of the time, so
  its return stream correlates with existing risk-on families even if the gate
  is distinct.

## 9. Why this is a distinct family

The primary object is a cross-asset currency impulse. None of the nine
existing winners uses UUP or any FX series as its gate:

- `ratio-froth` uses a QQQ/TQQQ ratio.
- `vol-scaled-crash-stop` uses realised volatility and a crash stop.
- `relative-value-tqqq` uses QQQ/SPY relative value.
- `fomc-opex-window` uses a calendar event window.
- `family-session-timing` uses intraday session blocks.
- `family-short-reversal` uses 1–5 day price overreaction.
- `family-rebalance-flow` uses mechanical LETF/closing flow.
- `family-intraday-microstructure-day` uses opening range/order flow.
- `family-ml-microstructure` uses a fitted ML model on intraday features.

The dollar impulse is an external macro state. It is not a QQQ trend, a
volatility target, a drawdown event, a calendar clock, an opening-range rule, a
relative-strength ratio gate, or an ML model.

## 10. Data and reproducibility

- External: `data/external/UUP.parquet` (Yahoo adjusted close, 2015–2026;
  only rows ≤ 2023-12-29 are used).
- Execution: local `data/intraday-hf/QQQ-1m.parquet`, `TQQQ-1m.parquet`,
  `BIL-1m.parquet`.
- Warmup: external 2015 rows are used only to make the first 60-session
  feature finite on 2016-01-04.
- Run: `python research/new/family-dollar-regime/strategy.py`.
- The script writes `result.json` and `report.md` from the development window
  only.

## 11. Decision rule

If the primary clears the three-way bar, the activity floor, at least 5/8
plateau cells, and at least one placebo null at p ≤ 0.20, and no subperiod is
negative, it is a **dev candidate** eligible for a frozen one-shot holdout. It
is not a verified winner until that holdout and the causality/freshness audit
are complete.

If the primary fails the bar or the plateau, it remains a negative research
record. A high headline CAGR with a fragile plateau is not a winner.
