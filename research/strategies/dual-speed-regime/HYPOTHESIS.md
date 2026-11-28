# Hypothesis and pre-registration — `dual-speed-regime` revisit

**Status:** design stage. Backtests paused by the user on 2026-11-26. Nothing below is a
result; it is the pre-registered hypothesis, spec and falsification plan for the new test.

## 1. What the original actually added

The round-2 strategy was a 165-day QQQ regime holding TQQQ, plus a 60-minute QQQ EMA(40)
crossover and a 4% minute stop, both armed only when QQQ's first minute was below its prior
20-day SMA. The genuinely new component was the **60-minute EMA crossover**; everything else
was the shared base.

## 2. Why the naive strip is not enough

Removing the 165-day gate but keeping the 60-minute crossover and overnight TQQQ (exploratory
development run, 2016-01-04..2023-12-29, 1 bp, before the pause) gave roughly:

- 10/60 EMA: ~42% CAGR, ~55% max DD, ~0.56 daily-return correlation to the 165-day base;
- 15/45 EMA: ~41% CAGR, ~49% max DD, ~0.55 correlation.

That is still a cousin of the base: most of its return is earned overnight, where TQQQ's
drift lives (round-1 decomposition: +1,355% overnight vs +81% intraday). The clarification
asks for a different return driver, not a base removal. The rebuild therefore changes the
holding period: **the fast signal owns an intraday-only position and the strategy is flat
every night.**

## 3. Standalone hypothesis

**Idea.** QQQ's 60-minute EMA cross measures intraday trend persistence. A long-TQQQ
position held only while that trend is up, sized by trend strength, and closed before the
overnight, earns a return stream that is structurally different from the overnight-dominated
165-day base.

**Hypothesis.** On 2016-2023 development data, the intraday-only 60-minute trend strategy
will have daily-return correlation below 0.60 with the 165-day baseline, a positive Sharpe
after 5 bp costs, and a drawdown profile that is not explained by the base's overnight beta.
It is not expected to beat the base on CAGR; it is expected to be an independent, lower-vol
return stream.

**What would falsify it.**

1. Development correlation with the 165-day baseline is **0.60 or higher**.
2. Development CAGR is below 5%, or Sharpe is below 0.40 at 5 bp.
3. The timing overlay does not beat the placebo "long TQQQ every intraday session
   10:30-15:30" on Sharpe or drawdown — i.e. the 60-minute EMA adds nothing over intraday
   buy-and-hold.
4. The edge is concentrated in 2020 or one sub-period; 2016-19 or 2022-23 is negative.
5. A random or lagged-EMA placebo with the same exposure and turnover performs as well.
6. The 10 bp result is negative, or the 5 bp Sharpe is below 0.30.
7. The signal's next-bar hit rate after an up-cross is 50% or less, or the average trade
   net of 1 bp is zero or negative.
8. The strategy is long TQQQ on more than 80% of intraday bars — that would mean it is
   intraday TQQQ beta, not a timing strategy.

## 4. Universe and data

- **Signal:** QQQ 1-minute bars, resampled to session-aligned 60-minute bars.
- **Long asset:** TQQQ (3x QQQ).
- **Cash / risk-off:** BIL.
- **Data:** local adjusted 1-minute QQQ/TQQQ/BIL in `data/intraday-hf/`, via
  `research/bt.py`. Development 2016-01-04..2023-12-29. No holdout inspection.
- **Data limitation:** SPY 1-minute history is not available locally (the Dukascopy cache
  contains only 2026), so no SPY/sector/bond/gold/vol sleeve is used. This is documented
  rather than papered over. No new downloads while tests are paused.

## 5. Signal and position

Session-aligned 60-minute bars: 09:30-10:29, 10:30-11:29, ..., 14:30-15:29,
15:30-15:59. Half days use their actual last bar.

- `EMA_fast` = EMA(10) of QQQ 60-minute closes.
- `EMA_slow` = EMA(30) of QQQ 60-minute closes.
- `spread = EMA_fast / EMA_slow - 1`.
- Long TQQQ only when `spread > 0`, between the 10:29 and 14:29 bar closes.
- Size: 100% TQQQ if `spread > +0.30%`, otherwise 50% TQQQ; the remainder is BIL.
- Exit when `spread < 0`, on the ATR stop, or at the 15:29 bar close.
- Flat 09:30-10:29, flat 15:30-15:59, and flat overnight.
- No re-entry on a day after an ATR stop.

**Holding period:** 1-5 hours intraday, typically 1-4 60-minute bars; zero overnight.

## 6. Risk rules (own, not inherited)

1. **ATR trailing stop:** while long, exit if TQQQ's 60-minute close falls more than
   2.5 x ATR(14) below the highest TQQQ 60-minute close since entry. No re-entry that day.
   (The signal is QQQ-based; the stop is measured on the position, TQQQ.)
2. **Hard time exit:** flat at the 15:29 bar close (15:30 fill); no closing-auction or
   overnight exposure.
3. **Trend-tiered size:** 50% in mild uptrends, 100% only when the EMA spread is above
   +0.30%; the cash leg is BIL.
4. **No new entries after 14:29** and none in the first 60 minutes.

## 7. Execution and measurement

- Weights set at bar i's close fill at bar i+1's open; 2% band; long-only, weights sum <= 1.
- Headline 1 bp one-way; 5 bp and 10 bp reported.
- 1-minute equity marks; sessions indexed by bar, not clock time, so half days are handled.
- Development only. The 10-year (2017-01-03) and 5-year (2021-10-25) windows overlap the
  2024-2026 holdout and are deliberately **not** computed here; the lead runs them.
- Correlation is measured on daily returns of the strategy vs a 165-day baseline (TQQQ when
  QQQ's prior close is above its 165-day SMA, else BIL). The baseline is a measurement
  benchmark only and is never used to build the strategy's weights.

## 8. Planned overfitting controls

- Count and report every variant tried in the new design (starting at 0).
- ±1-step neighbourhood: fast EMA 8/10/12, slow 24/30/36, strong threshold 0.2/0.3/0.4%,
  ATR k 2.0/2.5/3.0. Choose the plateau center, not the peak.
- Sub-periods: 2016-19, 2020-21, 2022-23.
- Placebo: random signal with matched exposure/turnover; lagged EMA; intraday TQQQ
  buy-and-hold 10:30-15:30.
- Event/trade count and bootstrap p-value if entries < 100 (expected entries are in the
  hundreds, so this is a fallback).
- Report all results, including failures.

## 9. Provenance

| Claim / rule | Source | Role | Confidence |
|---|---|---|---|
| 60-minute EMA crossover as the new idea | Own prior work: `research/agents2/dual-speed-regime/report.md` (round 2) | inspired the signal | high |
| Intraday return persistence is predictable | Gao, Han, Li & Zhou (2018), *Market Intraday Momentum*, Journal of Financial Economics 129(2), 394-414 | supports the intraday-trend premise | medium |
| Overnight and intraday returns are different return streams; isolating intraday is meaningful | Lou, Polk & Skouras (2019), *A Tug of War: Overnight versus Intraday Expected Returns* | supports the flat-overnight design | high |
| Faster trend models cut the left tail but cost Sharpe/turnover; the fast leg must be selective | Man Group / Man AHL (2023), *The Need for Speed in Trend-Following Strategies*; Graham Capital (2018), *The Speed of Trend-Following* | supports the speed/risk trade-off | high |
| MA crossovers whipsaw; bands and smoothing help | StockCharts SystemTrader (2016), *How to become a Smooth Operator*; BestFolio (2026), *The best trend filter depends on the year you start* | supports hysteresis/size tiers | medium |
| Stop-losses add value under momentum/regime shifts | Kaminski & Lo (2014), *When do stop-loss rules stop losses?* | supports the ATR stop | high |
| Data and harness | `research/bt.py`; local QQQ/TQQQ/BIL 1-minute parquet | data/method | high |

Own tests / no external source: the 10/30 EMA pair, the +0.30% size threshold, the 2.5 x ATR
stop, the 10:30-15:30 window, and the 50/100% tiers. These are design choices to be tested,
not published rules.
