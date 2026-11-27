# Revisit: `dual-speed-regime` — intraday-only 60-minute trend

**Status: design / pre-registration.** Backtests were paused by the user on 2026-11-26.
This report contains no new results, no `result.json`, and no holdout inspection. The
numbers under "Prior evidence" are exploratory development runs made *before* the pause and
belong to the old stripped design, not to the new strategy.

## 1. Extracted idea

The original round-2 strategy was the shared 165-day QQQ regime plus a 60-minute QQQ EMA(40)
crossover and a 4% minute stop, with the fast filter armed by QQQ's prior 20-day SMA. The
only genuinely new component was the **60-minute EMA crossover**: a fast trend signal that
exits earlier than a daily gate and re-enters on a reclaim.

## 2. Why simply removing the 165-day gate is not enough

Before the pause I tested the obvious strip: 60-minute QQQ EMA crossover, TQQQ when the fast
EMA is above the slow EMA, BIL otherwise, still held overnight. Development period
2016-01-04..2023-12-29, 1 bp:

| Variant (old strip) | Dev CAGR | Dev max DD | Dev Sharpe | Corr vs 165-day base |
|---|---:|---:|---:|---:|
| 10/30 EMA, TQQQ/BIL, overnight | 36.07% | 51.19% | 0.98 | 0.546 |
| 15/45 EMA, TQQQ/BIL, overnight | 40.53% | 49.35% | 1.05 | 0.553 |
| 10/60 EMA, TQQQ/BIL, overnight | 42.01% | 54.65% | 1.08 | 0.561 |

These are *not* the new strategy; they are the evidence that the naive strip is still a
cousin of the base. It is under the 0.60 correlation line only because it spends time in BIL,
and most of its return is still earned overnight, where TQQQ's drift lives (round-1
decomposition: +1,355% overnight vs +81% intraday over 2017-2026). The clarification asks
for a different return driver, not a base removal.

## 3. Standalone design

**One-sentence idea.** QQQ's 60-minute EMA cross measures intraday trend persistence; hold
TQQQ only while that trend is up, size by trend strength, and be flat every night.

**Universe and roles** (local 1-minute data only):

- **QQQ** — signal source. Not held.
- **TQQQ** — the long asset. Held only intraday, 10:30-15:30.
- **BIL** — cash / risk-off leg.
- No SPY, sector, bond, gold or volatility sleeve: the local SPY 1-minute cache starts in
  2026 and is unusable for 2016-2023. Rather than force an unvalidated download while tests
  are paused, the rebuild stays with the assets the archive supports and changes their roles
  and holding period. This is a documented data limitation.

**Signal.** Session-aligned 60-minute QQQ bars (09:30-10:29, 10:30-11:29, ..., 14:30-15:29,
15:30-15:59; half days use the actual last bar). `EMA_fast = EMA(10)`, `EMA_slow = EMA(30)`
on 60-minute closes; `spread = EMA_fast / EMA_slow - 1`.

**Position.**

- Long TQQQ only when `spread > 0`, from the 10:29 bar close (fill 10:30) through the 14:29
  bar close as the last entry.
- Size 100% TQQQ when `spread > +0.30%`; 50% TQQQ when `0 < spread <= +0.30%`; BIL for the
  remainder and whenever `spread <= 0`.
- Exit on `spread < 0`, on the ATR stop, or at the 15:29 bar close (flat 15:30).
- Flat 09:30-10:29, flat 15:30-16:00, and flat overnight.
- No re-entry on a day after an ATR stop; a normal trend flip can re-enter later the same
  day if the spread crosses back above zero inside the entry window.

**Holding period.** 1-5 hours intraday; typically 1-4 60-minute bars; zero overnight.

**Risk rules (own, not inherited).**

1. **ATR trailing stop on the position:** while long, exit if TQQQ's 60-minute close falls
   more than 2.5 x ATR(14) below the highest TQQQ 60-minute close since entry. The signal is
   QQQ-based; the stop is measured on TQQQ, the asset actually held.
2. **Hard time exit:** flat at the 15:29 bar close (15:30 fill); no closing-auction or
   overnight exposure.
3. **Trend-tiered size:** 50% in mild uptrends, 100% only when the EMA spread is above
   +0.30%; the cash leg is BIL.
4. **No entries after 14:29** and none in the first 60 minutes.

**Execution.** Weights set at bar i's close fill at bar i+1's open; 2% band; long-only;
weights sum <= 1; 1 bp headline, 5 bp and 10 bp reported; 1-minute equity marks.

## 4. Expected correlation vs the old base

**Expected: 0.15-0.45, hard limit 0.60.** Rationale: the 165-day base is long TQQQ on
roughly 80% of sessions including every night, and its daily return is dominated by the
overnight TQQQ window. The new strategy earns only the 10:30-15:30 return on selected days
and is flat overnight. The common component is the intraday part of the base's TQQQ
exposure, which is smaller and partly offset by the documented overnight/intraday
"tug of war". If the measured development correlation is above 0.55, the design should be
reworked (for example hold QQQ instead of TQQQ in the mild-trend tier, or use a different
asset) before it is presented as independent.

## 5. Expected performance (hypothesis, not a result)

At 1 bp on development data: **CAGR 6-14%, max DD 18-30%, Sharpe 0.5-0.8**. The strategy is
not expected to beat the 165-day base on CAGR; it is expected to be a lower-vol, different
return stream. At 5 bp the costs should be roughly 1-2%/yr; at 10 bp 2-4%/yr. If the 5 bp
Sharpe is below 0.40 or CAGR below 5%, the idea is not investable as a standalone.

## 6. Falsifiers (pre-registered)

1. Development correlation with the 165-day baseline >= 0.60.
2. Development CAGR < 5% or Sharpe < 0.40 at 5 bp.
3. The timing overlay fails to beat "long TQQQ every intraday session 10:30-15:30" on
   Sharpe or drawdown — i.e. the 60-minute EMA adds nothing over intraday buy-and-hold.
4. The edge is concentrated in 2020 or one sub-period; 2016-19 or 2022-23 is negative.
5. A random or lagged-EMA placebo with matched exposure/turnover performs as well.
6. The 10 bp result is negative, or the 5 bp Sharpe is below 0.30.
7. The signal's next-bar hit rate after an up-cross is <= 50%, or the average trade net of
   1 bp is <= 0.
8. The strategy is long TQQQ on > 80% of intraday bars — that would be intraday TQQQ beta,
   not a timing strategy.

## 7. Planned tests and overfitting controls

- **Primary:** fast 10, slow 30, entry band 0, strong +0.30%, ATR 2.5, last entry 14:29,
  hard exit 15:29.
- **±1-step neighbourhood:** fast 8/12, slow 24/36, strong 0.20%/0.40%, ATR k 2.0/3.0.
  Choose the plateau center, not the peak.
- **Alternatives/ablations:** entry band 5 bp; 0/100% size instead of 50/100%; QQQ as the
  mild-trend asset; stop measured on QQQ instead of TQQQ; hard exit 15:55 instead of 15:30.
- **Placebos:** random entries with matched exposure and turnover; EMA lagged by one bar;
  intraday TQQQ buy-and-hold 10:30-15:30; QQQ buy-and-hold.
- **Correlation diagnostics:** report the daily-return correlation on all days *and* on
  active days only (days with a nonzero strategy return), so a low headline number cannot
  come purely from zero-inflation; also report the active-day beta to the base.
- **Sub-periods:** 2016-19, 2020-21, 2022-23.
- **Event count:** report entries, exits, stops and trades; bootstrap p-value if entries
  < 100 (expected: several hundred).
- **Variants tried:** count every variant; the new design starts at 0. The prior strip
  exploration (~130 grid points) is disclosed separately and is not reused as evidence for
  the new design.
- **Costs:** 1/5/10 bp, all reported, including failures.

## 8. Results (pending authorization)

| Window | 1 bp | 5 bp | 10 bp |
|---|---:|---:|---:|
| Dev 2016-01-04..2023-12-29 CAGR / DD / Sharpe | TBD | TBD | TBD |
| Dev correlation vs 165-day base | TBD | — | — |
| Dev sub-period 2016-19 | TBD | — | — |
| Dev sub-period 2020-21 | TBD | — | — |
| Dev sub-period 2022-23 | TBD | — | — |
| Holdout 2024-01-02..2026-10-23 | not run (lead) | not run | not run |
| 10y 2017-01-03.. | not run (overlaps holdout) | not run | not run |
| 5y 2021-10-25.. | not run (overlaps holdout) | not run | not run |

No `result.json` has been generated. `strategy.py` is written and syntax-checked only; it has
not been executed.

## 9. Provenance

| Claim / rule | Source | Role | Confidence |
|---|---|---|---|
| 60-minute EMA crossover as the new idea | Own prior work: `research/agents2/dual-speed-regime/report.md` (round 2) | inspired the signal | high |
| Intraday return persistence is predictable | Gao, Han, Li & Zhou (2018), *Market Intraday Momentum*, Journal of Financial Economics 129(2), 394-414 | supports the intraday-trend premise | medium |
| Overnight and intraday are different return streams; isolating intraday is meaningful | Lou, Polk & Skouras (2019), *A Tug of War: Overnight versus Intraday Expected Returns* | supports the flat-overnight design | high |
| Faster trend models cut the left tail but cost Sharpe/turnover | Man Group / Man AHL (2023), *The Need for Speed in Trend-Following Strategies*; Graham Capital (2018), *The Speed of Trend-Following* | supports the speed/risk trade-off | high |
| MA crossovers whipsaw; bands and smoothing help | StockCharts SystemTrader (2016), *How to become a Smooth Operator*; BestFolio (2026), *The best trend filter depends on the year you start* | supports hysteresis/size tiers | medium |
| Stop-losses add value under momentum/regime shifts | Kaminski & Lo (2014), *When do stop-loss rules stop losses?* | supports the ATR stop | high |
| Data and harness | `research/bt.py`; local QQQ/TQQQ/BIL 1-minute parquet | data/method | high |

Own tests / no external source: the 10/30 EMA pair, the +0.30% size threshold, the 2.5 x ATR
stop, the 10:30-15:30 window, the 50/100% tiers, and the no-re-entry-after-stop rule. These
are design choices to be tested, not published rules.

## 10. Why this is not the old base in disguise

- The strategy never holds TQQQ, QQQ or any equity ETF overnight.
- The 165-day gate, the 20-day arming gate and the 4% round-1 stop are absent from the
  position logic. The 165-day series exists only in the correlation benchmark function.
- The holding period is hours, not weeks; the position is flat ~80% of calendar time and
  ~100% of nights.
- The return driver is intraday trend persistence, not overnight TQQQ beta.
- The risk rules are position-level (ATR on TQQQ) and time-level (hard flat), not inherited.
