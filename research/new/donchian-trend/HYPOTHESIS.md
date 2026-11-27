# Donchian two-sleeve TQQQ trend — hypothesis and frozen specification

**Slug:** `donchian-trend`
**Window:** 2016-01-04 → 2023-12-29 (development only). The 2024-01-02 →
2026-10-23 holdout is never read, inspected or used for selection.
**Bar:** TQQQ buy-and-hold 2016-2023 = **36.72% CAGR / 82.29% max DD / 0.82
Sharpe** (1-minute marks). Pass = CAGR > 36.72% and max DD < 82.29%, with a
design target of <60% DD.

## 1. Why this is not the failed Donchian rebuild

The revisit `donchian-breakout` used a 5-minute **QQQ** alignment ladder
(20/55/390-bar sleeves), a QQQ middle state, and ATR sizing. Its calibration
showed the single-sleeve TQQQ version at 6.8-9.7% CAGR. It was a fast intraday
breakout system and it lost.

This strategy is different in every load-bearing dimension:

| | old rebuild | this strategy |
|---|---|---|
| Bar | 5-minute | daily (overnight holds) |
| Signal asset | QQQ only | TQQQ fast sleeve + QQQ slow regime |
| Horizons | 20/55/390 five-minute bars | 20-session and 100-session daily channels |
| Exit | 10/20-bar low or 2.5×ATR | 10-session low (fast) / 50-session low (slow) |
| Sizing | 30% vol target, 20% floor, resized on alignment change | 85% vol target on TQQQ, continuous |
| Position | BIL/QQQ/TQQQ ladder | TQQQ / BIL only |
| Holding period | ~100 minutes to ~5 days | weeks to months |

The old rebuild was a fast mean-reversion-prone intraday system. This is a slow,
high-exposure daily trend system. The only shared vocabulary is "Donchian".

## 2. Hypothesis

> A 3x Nasdaq ETF compounds violently in sustained uptrends and loses 80% in
> regime breaks. A channel breakout that is *slow enough* to stay invested
> through ordinary pullbacks, but *fast enough* to leave before a bear market
> fully develops, can keep most of the bull-market compounding while cutting
> the left tail. Two sleeves at different horizons do different jobs: the fast
> 20/10 sleeve re-enters quickly after a shakeout, and the slow QQQ regime
> sleeve keeps the book invested through multi-month trends. Sizing the TQQQ
> position by an 85% volatility target trims the position only in genuine
> high-volatility regimes, where the trend signal is least reliable.

The failure mode of the earlier fast Donchian was measured directly: a 10-day
low exit on TQQQ is inside the normal pullback noise of a 3x ETF. In 2017 the
20/10 system sold at 3.30, bought back at 3.62, sold at 3.76, bought back at
4.17 — it paid the uptrend away in whipsaw. The fast sleeve alone is therefore
not the strategy; the slow regime sleeve is what carries the exposure.

## 3. Exact rules

### Data and timing

- **Signal:** official adjusted daily OHLC for QQQ and TQQQ from
  `data/intraday-hf/{QQQ,TQQQ}-1d-yahoo.parquet`, filtered to dates
  ≤ 2023-12-29. The 2015 rows are used only to warm the channels and the
  volatility estimate before 2016-01-04.
- **Execution and marks:** `bt.panel(("QQQ","TQQQ","BIL"), "2016-01-04",
  "2023-12-29", "1D")`, next-open fills, 2% band. The 1-minute archive is the
  source of the daily panel, so the marks are 1-minute-derived daily closes.
- A weight set at the close of session `t` is filled at the open of `t+1`.
  Every channel uses highs/lows of sessions `t-N .. t-1`; the current session
  is never inside its own channel.

### Fast sleeve (TQQQ, 20/10)

- Enter TQQQ when `TQQQ_close_t > max(TQQQ_high_{t-20..t-1})`.
- Exit when `TQQQ_close_t < min(TQQQ_low_{t-10..t-1})`.
- State machine; no re-entry without a new 20-session high.

### Slow regime sleeve (QQQ, 100/50)

- Enter when `QQQ_close_t > max(QQQ_high_{t-100..t-1})`.
- Exit when `QQQ_close_t < min(QQQ_low_{t-50..t-1})`.
- State machine. This sleeve expresses TQQQ, not QQQ: it is a regime gate.

### Position

```
trend_t  = 1 if fast_t == 1 or slow_t == 1 else 0
vol20_t  = annualised stdev of TQQQ daily log returns over t-19..t
w_tqqq_t = trend_t * min(1, 0.85 / vol20_t)
w_bil_t  = 1 - w_tqqq_t
```

Long-only, non-negative, sum ≤ 1. No QQQ holding in the book; QQQ is a signal
asset only. No leverage above 100% TQQQ.

### Why the slow horizon is 100, not 55

The mandate suggested 20/55 channels. The 55-session slow sleeve with a
20-session exit was tested and **fails**: `OR(20/10, QQQ 55/20)` gives 30.2%
CAGR / 43.0% DD with the 85% vol target. The 55-day channel is still inside the
pullback noise of a 3x ETF; its 20-day exit re-enters too late. The slow
horizon has to be long enough to be a *regime*, not a second fast signal. The
horizon map in the report shows the transition: 55/40 = 35.8%, 55/50 = 43.0%,
80/60 = 59.0%, 100/50 = 52.5%, 120/60 = 56.3%. The frozen base uses 100/50
because it is the middle of the passing region and its 50-session exit is
faster (more defensive) than the 60-session neighbours.

## 4. Frozen 8-cell grid

The base is the centre of the design, not the best cell. Each non-base cell
moves one parameter by one step. All cells are complete strategies with the
same execution and costs.

| Cell | Fast entry/exit | Slow entry/exit | Vol target |
|---|---|---|---|
| **base** | 20 / 10 | 100 / 50 | 0.85 |
| `slow_entry_80` | 20 / 10 | 80 / 50 | 0.85 |
| `slow_entry_120` | 20 / 10 | 120 / 50 | 0.85 |
| `slow_exit_40` | 20 / 10 | 100 / 40 | 0.85 |
| `slow_exit_60` | 20 / 10 | 100 / 60 | 0.85 |
| `fast_entry_15` | 15 / 10 | 100 / 50 | 0.85 |
| `fast_entry_25` | 25 / 10 | 100 / 50 | 0.85 |
| `fast_exit_15` | 20 / 15 | 100 / 50 | 0.85 |

Volatility-target sensitivity (0.55/0.65/0.75/0.95) is reported as a
neighbourhood, not as part of the pre-registered 8.

## 5. Falsifiers

The hypothesis is rejected on the development window if any of these hold:

1. CAGR ≤ 36.72% at 1 bp, or max DD ≥ 82.29%.
2. Fewer than 7 of the 8 grid cells pass, or the base is an isolated peak
   (CAGR spread outside the grid > 30% of the base).
3. The 10 bp CAGR falls below 36.72% (turnover too high).
4. A lag of 1-5 sessions destroys the result (timing is not real), or the base
   is below the 95th percentile of 200 circular-shift placebos.
5. The edge is only the slow sleeve with no contribution from the fast
   sleeve, or only the fast sleeve with no slow regime.
6. One year contributes more than 80% of the log P&L, or two of the three
   fixed sub-periods are negative.
7. Correlation with TQQQ > 0.85 (it is just TQQQ beta) or with the 165-day
   QQQ SMA base > 0.90 (it is the old base in disguise). This is a
   distinctness check, not a pass/fail on returns.
8. A truncation test changes any weight before the truncation date.

## 6. Probe disclosure

Development exploration (this agent, dev window only) tested: plain 20/10,
55/20, 10/5, 5/5; QQQ vs TQQQ signal asset; trailing ATR stops (2-5N);
single-day crash exits; 5-day-vol spike exits; conditional exits gated on
QQQ's 50/100/150-day SMA; fast re-entries; a permanent TQQQ core (10-80%);
and slow-gate horizons 40-200. The strict 20/55 + 10/20 mandate was tested and
does not pass (30.2% CAGR). The frozen base was chosen as the centre of the
slow-horizon plateau, not as the maximum-CAGR cell (100/60 and 80/60 are
higher). No 2024+ data was loaded at any point.
