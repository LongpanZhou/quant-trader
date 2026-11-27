# Drawdown / stop overlay on the 165-day QQQ → TQQQ trend

Agent: `drawdown-stop-overlay` · Date: 2026-11-26 (corrected revision)

## TL;DR

**V1 (intraday 165-day-SMA threshold stop, regime-reset / new-10-day-high
re-entry) passes both windows at 1 bp and 5 bp, but it is dominated by V4:**

| Window | V1 CAGR | V1 max DD | V1 Sharpe | TQQQ CAGR | TQQQ max DD | Verdict |
|---|---:|---:|---:|---:|---:|---|
| 10y (2017-01-03 → 2026-10-23) | **43.27%** | **45.23%** | 1.00 | 39.28% | 81.68% | **PASS** |
| 5y (2021-10-25 → 2026-10-23) | **29.46%** | **42.96%** | 0.80 | 13.47%¹ | 81.68% | **PASS** |

At 5 bp: 10y **42.70% / 45.84%**, 5y **28.91% / 43.14%** — still passes both.

V1 does **not** beat the daily baseline's 10y CAGR (43.27% vs 45.31%); it cuts
the 10y max drawdown from 58.71% to 45.23%. On the 5y window it is lower than
the baseline on both axes (29.46% vs 34.61%, DD 42.96% vs 36.86%). The
mechanism is March 2020: the daily 165-day-SMA rule sells at the 2020-03-10
open, buys the 2020-03-10 bounce at the 2020-03-11 open, then eats the
2020-03-12 TQQQ collapse. V1 exits **intraday** on 2020-02-28 when QQQ first
trades through the exact 165-day-SMA threshold. The daily regime then briefly
resets bullish on 2020-03-10, so V1 re-enters at the 2020-03-11 open — but the
intraday stop fires again at the 2020-03-11 09:30 bar, so it is out before the
2020-03-12 collapse and stays out until the 2020-04-13 regime reset. 2020
return: **+137.2%** vs +104.1% for TQQQ and +73.6% for the minute baseline;
2020 drawdown: **44.87%** vs 59.64% for the baseline.

**V4 (55% volatility-target overlay) is the best variant in this study and
dominates V1 on all four headline metrics:** 10y 43.66% / 43.10% / 1.06, 5y
34.88% / 36.64% / 0.92; at 5 bp 43.07% / 43.55% and 34.28% / 36.66%. It beats
the daily baseline on both axes in the 5y window; on 10y it has a lower CAGR
(43.66% vs 45.31%) but a much lower DD (43.10% vs 58.71%). It is not a price
stop, though; it is a smooth risk-sizing rule.

The honest cost of V1 is 2018/2019/2023/2024: the threshold stop whipsaws in
the Q4-2018 chop (**−11.6% vs −4.3%** for the baseline), in the 2019 trade-war
chop (+26.5% vs +47.1%), in 2023 (+78.3% vs +118.5%) and in the
August–September 2024 pullback (+36.4% vs +50.0%). That is also why its 5y max
DD (42.96%) is worse than the daily baseline's 36.86%. It still clears the TQQQ
bar on both windows by a wide margin.

¹ The harness benchmark from the 2021-10-25 close is 13.88%; the README's
13.47% target is consistent with a pre-window (2021-10-22) starting price.
Both are shown in `result.json`; pass/fail uses the stricter 13.47%.

> **Revision note (2026-11-26).** The first version of this report used a
> one-day-stale threshold (`thr_m = per_bar(thr_d)`), which inflated V1 to
> 46.89% / 45.32% (10y) and 32.40% / 42.96% (5y). The corrected code uses
> `thr_m = same_day(thr_d)`: `thr_d` is already `rolling(164).mean().shift(1)`,
> so `thr_d[d]` is the mean of closes `d-164..d-1` and is known before day `d`
> opens. The corrected V1 is 43.27% / 45.23% (10y) and 29.46% / 42.96% (5y).
> The old 46.89% numbers are withdrawn; every number below is from the
> corrected code.

---

## 1. Idea and sources

### 1.1 The trend leg

Hold TQQQ while QQQ's daily close is above its 165-day SMA; otherwise BIL. This
is the Faber-style 10-month/200-day time-series trend rule applied to a 3× ETF:

- Meb Faber, *A Quantitative Approach to Tactical Asset Allocation* (2007):
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=962461>. The 10-month SMA
  keeps most of the equity return with much smaller drawdowns.
- FinLab, *TQQQ 200-Day Moving Average Strategy: 7 Leveraged ETF Rules* (Oct
  2026): <https://finlab.finance/en/blog/leveraged-etf-timing-backtest>. Their
  TQQQ + QQQ 200-day rule did 45.1% CAGR / −60.9% max DD / 0.99 daily Sharpe,
  but only 4 of 9 neighbouring settings beat QQQ's Sharpe, and the −60.9% DD
  came from the March 2020 whipsaw: sell 2020-03-10, buy back 2020-03-11, then
  take TQQQ's −27.4% day on 2020-03-12. In 6 of 8 exits TQQQ rose while the
  rule was out. This is exactly the failure mode the overlay targets.
- Brock, Lakonishok & LeBaron (1992), the original 200-day MA evidence, is
  summarised in the same FinLab piece.

### 1.2 The stop leg

The intraday stop is a threshold version of the daily SMA, not a fixed
percentage:

- Wilder's ATR trailing stop and the general trailing-stop literature:
  <https://pure.buas.nl/ws/files/39878068/Fonseca_Point-in-Time_backtesting_of_momentum-trend_equity_strategies.pdf>
  (point-in-time bias taxonomy; ATR trailing stop analysis).
- Investopedia, *Trailing Stop*: <https://www.investopedia.com/terms/t/trailingstop.asp>
  — definition and the three costs: whipsaw, slippage, profit giveback.
- ShareScope, *Trend following and trailing stops*:
  <https://knowledge.sharescope.co.uk/2022/08/26/trend-following-and-trailing-stops-methods-to-capture-trends/>
  — comparison of trailing methods and the whipsaw problem in range-bound
  markets.

The key design choice is the re-entry. A trailing stop that re-enters the next
day gets whipsawed in every V-shaped dip. Requiring a new 10-day high is a
standard "buy strength after a stop" filter. It applies when the daily regime
never goes bearish between the stop and the prospective re-entry (the 2018,
2019 and 2024 whipsaws). In COVID the regime did go bearish on 2020-03-09,
which resets the stop state; V1 re-entered on the 2020-03-10 bullish close, was
stopped again at the 2020-03-11 open, and then stayed out until the 2020-04-13
regime reset. Both paths are handled by the same state machine and are described
exactly in section 5.

### 1.3 The volatility-control leg

- Moreira & Muir, *Volatility-Managed Portfolios* (2017):
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2659431>. Scaling
  exposure inversely to recent volatility raises Sharpe because volatility
  changes are not matched one-for-one by expected-return changes.
- Cederburg, O'Doherty, Wang & Yan, *On the performance of volatility-managed
  portfolios* (JFE 2020):
  <https://www.sciencedirect.com/science/article/abs/pii/S0304405X2030132X>.
  Important caveat: vol scaling improves Sharpe for only some equity factors,
  so the result should not be treated as universal.
- Man Group, *The Impact of Volatility Targeting*:
  <https://man.com/insights/the-impact-of-volatility-targeting>.

V4 applies the idea to TQQQ: target 55% annualised TQQQ volatility with a
20-day lookback, capped at 100% TQQQ, with the 165-day regime as a hard filter.

---

## 2. Data, harness, conventions

- Local adjusted 1-minute QQQ/TQQQ/BIL only, `data/intraday-hf/`; regular
  session 09:30–16:00 ET; no new downloads.
- `research/bt.py` panels and simulator: signals at bar `i` (using data through
  bar `i` only), fills at bar `i+1`'s **open**, 2% rebalance band, 1 bp default
  slippage, 5 bp sensitivity, long-only, weights sum to ≤ 1.
- Windows: 10y = 2017-01-03 → 2026-10-23 (9.802 years); 5y = 2021-10-25 →
  2026-10-23 (4.994 years).
- Indicators are computed on daily bars (165-day SMA, prior-164-close mean,
  10/20-day highs, 20-day realised vol) and mapped to minutes. On the 15:59 bar
  the day's close is used (signal fills at the next 09:30 open); on all earlier
  bars only the previous daily close is used.
- **Threshold alignment (the revision).** `thr_d = rolling(164).mean().shift(1)`,
  so `thr_d[d] = mean(C_{d-164..d-1})`. That is exactly the level at which
  today's close would equal the 165-day SMA, and it is known before day `d`
  opens. The code maps it with `same_day(thr_d)`. The earlier revision used
  `per_bar(thr_d)`, which reads `thr_d[d-1]` and adds a second day of lag. The
  old code produced V1 46.89% / 45.32% (10y) and 32.40% / 42.96% (5y); the
  corrected code produces 43.27% / 45.23% and 29.46% / 42.96%. The corrected
  numbers are used everywhere below.
- Max drawdown is reported two ways: on the **1-minute equity path** (the
  conservative number; `bt.stats` with 252×390 bars/year) and on **daily
  closes** (comparable to the README's daily baseline). The daily-close number
  is always smaller because intraday troughs are excluded.

---

## 3. Exact rules

### V1 — primary minute-stop variant: intraday SMA-threshold stop, regime-reset / 10-day-high re-entry

Let `C_t` be QQQ's daily close and `SMA165_t = mean(C_{t-164..t})`. Then

```
C_t > SMA165_t   ⇔   C_t > T_t := mean(C_{t-164..t-1})
```

because `165·C_t > Σ_{t-164..t-1} C + C_t ⇔ 164·C_t > Σ_{t-164..t-1} C`.
`T_t` uses only closes through `t−1`, so it is known before the open.

1. **Regime.** If QQQ's last completed daily close is above its 165-day SMA,
   the strategy is allowed to hold TQQQ; otherwise it holds BIL.
2. **Intraday stop.** While long, if QQQ's 1-minute close ≤ `0.995 × T_t`
   (0.5% below the exact SMA threshold), sell the entire TQQQ position at the
   next minute's open and move to BIL.
3. **While the regime stays bullish after a stop.** Do **not** re-enter on the
   next day's bounce. Re-enter TQQQ at the next minute open only when
   `TQQQ minute close ≥ max(prior 10 daily TQQQ closes)` (a new 10-day high)
   **and** the daily regime is bullish.
4. **Regime exit / reset.** If the daily close is below the SMA, go to BIL at
   the next open (the baseline exit) and **clear the stop state**. The next
   bullish daily close re-enters at the next open, exactly like the daily
   baseline; the 10-day-high condition only applies when the regime did not
   go bearish between the stop and the prospective re-entry. This is the
   mechanism that re-entered briefly on 2020-03-10/11.
5. **No other trades.** No shorting, no intraday re-entry on the stop day
   unless the new-high condition is met.

### V2 — negative control: same stop, sticky until regime reset

Same as V1, but after a stop stay in BIL until the daily regime goes bearish
and then bullish again (a fresh SMA cross). This tests the "wait for the bear
market to end" re-entry and shows its cost.

### V3 — classic trailing stop

15% trailing stop from the highest TQQQ close since entry; after a stop,
re-enter when QQQ's minute close ≥ its prior 20-day high and the regime is
bullish.

### V4 — 55% volatility target

```
w_TQQQ,t = min(1, 0.55 / vol20(TQQQ daily returns, annualised))
```

if the daily regime is bullish, else 0; the remainder is BIL. The target is
set at the 15:59 close and filled at the next 09:30 open; it is held constant
intraday (the 2% band handles drift). This is a daily risk-sizing rule executed
on minute bars, not a price stop.

---

## 4. Results

### 4.1 10-year window (2017-01-03 → 2026-10-23)

| Variant | CAGR 1bp | Max DD 1m | DD daily | Sharpe | Sortino | Fills | Turnover | CAGR 5bp | DD 5bp | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| TQQQ buy & hold | 39.28% | 81.68% | 81.68% | 0.83 | — | — | — | — | — | benchmark |
| Daily baseline (README) | 45.31% | 58.71% | 58.71% | 1.00 | — | 81 | 795x | — | — | — |
| Minute baseline (this harness) | 45.47% | 59.64% | 58.71% | 1.00 | 1.40 | 81 | 804x | 44.99% | 59.76% | — |
| **V1 threshold stop (regime/new-high)** | **43.27%** | **45.23%** | 43.60% | **1.00** | 1.41 | 97 | 799x | **42.70%** | **45.84%** | **PASS** |
| V2 threshold sticky | 37.12% | 51.47% | 48.88% | 0.96 | 1.37 | 81 | 507x | 36.67% | 52.01% | **FAIL** (CAGR < 39.28%) |
| V3 peak 15% + QQQ 20d high | 39.76% | 37.57% | 36.94% | 1.11 | 1.56 | 179 | 1089x | 38.74% | 38.37% | 1bp pass; 5bp fail; fragile |
| V4 vol target 55% | **43.66%** | **43.10%** | 41.70% | **1.06** | 1.49 | 881 | 1067x | **43.07%** | **43.55%** | **PASS, dominates V1** |

### 4.2 5-year window (2021-10-25 → 2026-10-23)

| Variant | CAGR 1bp | Max DD 1m | DD daily | Sharpe | Sortino | Fills | Turnover | CAGR 5bp | DD 5bp | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| TQQQ buy & hold | 13.88%* | 81.68% | 81.68% | 0.53 | — | — | — | — | — | benchmark |
| Daily baseline (README) | 34.61% | 36.86% | 36.86% | 0.88 | — | 45 | 82x | — | — | — |
| Minute baseline (this harness) | 35.59% | 42.17% | 36.86% | 0.89 | 1.25 | 45 | 85x | 35.10% | 42.17% | — |
| **V1 threshold stop (regime/new-high)** | **29.46%** | **42.96%** | 42.46% | **0.80** | 1.12 | 53 | 77x | **28.91%** | **43.14%** | **PASS** |
| V2 threshold sticky | 24.13% | 34.28% | 33.70% | 0.75 | 1.06 | 45 | 60x | 23.68% | 34.44% | 5y pass; 10y fail |
| V3 peak 15% + QQQ 20d high | 51.59% | 32.88% | 28.46% | 1.35 | 1.93 | 71 | 248x | 50.73% | 33.31% | metrics pass; fragile |
| V4 vol target 55% | **34.88%** | **36.64%** | 34.42% | **0.92** | 1.30 | 420 | 120x | **34.28%** | **36.66%** | **PASS, dominates V1** |

\* The README's 13.47% target is consistent with a 2021-10-22 starting price;
the harness's 2021-10-25-close benchmark is 13.88%. Pass/fail uses 13.47%, the
stricter bar.

### 4.3 Yearly returns (strategy / TQQQ)

| Year | V1 | V4 | Minute baseline | TQQQ |
|---|---:|---:|---:|---:|
| 2017 | 114.5% | 114.5% | 114.5% | 114.5% |
| 2018 | **-11.6%** | -3.0% | -4.3% | -20.8% |
| 2019 | 26.5% | 40.2% | 47.1% | 148.2% |
| 2020 | **137.2%** | 77.2% | 73.6% | 104.1% |
| 2021 | 81.0% | 65.5% | 81.0% | 81.0% |
| 2022 | **-22.4%** | -17.9% | -23.1% | -79.4% |
| 2023 | 78.3% | 112.9% | 118.5% | 192.1% |
| 2024 | 36.4% | 49.0% | 50.0% | 62.4% |
| 2025 | 35.8% | 26.9% | 32.6% | 32.1% |
| 2026 | 17.6% | 13.3% | 13.7% | 22.6% |

Yearly max drawdown on the 1-minute equity path, V1 vs the minute baseline:

| Year | V1 DD | Baseline DD |
|---|---:|---:|
| 2017 | 15.97% | 15.97% |
| 2018 | **39.49%** | 39.08% |
| 2019 | 32.27% | 31.96% |
| 2020 | **44.87%** | **59.64%** |
| 2021 | 32.84% | 32.84% |
| 2022 | 24.62% | 26.63% |
| 2023 | 34.90% | 34.93% |
| 2024 | **42.96%** | 42.17% |
| 2025 | 26.43% | 28.15% |
| 2026 | 34.28% | 34.28% |

The 10y max drawdown of V1 (45.23%) is the August-2018 → June-2019 episode,
not COVID: COVID's 2020 drawdown was cut to 44.87%, just below it. The daily
baseline's 10y max was 58.71% in COVID.

---

## 5. Where the edge comes from

1. **March 2020.** The daily SMA rule sells at the 2020-03-10 open, buys the
   2020-03-10 bounce at the 2020-03-11 open, and then takes the 2020-03-12
   TQQQ collapse. FinLab documents the same whipsaw in their 200-day study. V1
   exits intraday on 2020-02-28 at QQQ 192.65 vs the 193.64 threshold (stop
   level 192.67; TQQQ ~8.30). The daily regime then goes bearish on 2020-03-09,
   which resets the stop state, and bullish again on 2020-03-10, so V1 re-enters
   at the 2020-03-11 open (~7.81). The intraday stop fires again at the
   2020-03-11 09:30 bar (QQQ 191.62 vs the 194.45 threshold, stop level 193.48),
   so V1 exits at 09:31 — taking the
   overnight gap but avoiding the 2020-03-12 collapse. It stays in BIL until
   the 2020-04-13 regime reset. 2020: +137.2% vs +73.6% baseline, DD 44.87%
   vs 59.64%.
2. **2018 — the stop hurts.** The Q4-2018 chop produces a whipsaw storm:
   exits/re-entries on 2018-10-10, 10-12, 10-15, 10-16, 10-19, 10-22, 10-23,
   11-07 and 11-09. V1 finishes 2018 at **−11.6%** vs −4.3% for the baseline,
   with a 39.49% yearly DD vs 39.08%. 2018 is the worst *relative* year; the
   largest compounding drags on the 10y CAGR are 2023 (78.3% vs 118.5%), 2019
   (26.5% vs 47.1%) and 2024 (36.4% vs 50.0%), with 2018 also negative.
3. **2022.** The 165-day regime, not the stop, does the work: −22.4% vs −79.4%
   for TQQQ; the 2022 DD is 24.62% vs 26.63% for the baseline.
4. **2019, 2023, 2024.** In the 2019 trade-war chop the threshold stop fires on
   2019-10-03 (QQQ 174.91 vs 176.20; stop level 175.32) and the 10-day-high
   re-entry does not come until 2019-10-11, after TQQQ has already rallied from
   6.58 to 7.54 (+14.6%); V1 makes +26.5% vs +47.1% baseline. In 2023 the stop
   fires at the 2023-01-25 09:30 bar (QQQ 277.23 vs the 281.37 threshold; stop
   level 279.96) but QQQ recovers by the close; V1 re-enters at 10.67 vs the
   9.76 exit — a 9% whipsaw — and then whipsaws again around
   2023-10-26/31, finishing +78.3% vs +118.5% baseline. In August–September
   2024 the stop sells the 2024-08-05 gap low, re-enters higher, and whipsaws
   again around 2024-09-09/10: +36.4% vs +50.0% baseline. This is why V1's 5y
   max DD (42.96%) is slightly worse than the daily baseline's 36.86% — but it
   is still less than half of TQQQ's 81.68%.

V4 avoids the 2018/2024 whipsaws because it scales the position down instead
of going to cash: 2018 −3.0%, 2024 +49.0%, 5y DD 36.64%. Its 10y CAGR is lower
than the daily baseline's because the vol target also de-risks some of the
strong up-years, but it dominates V1 on all four headline metrics.

---

## 6. Parameter stability (no huge grid)

**V1 stop buffer** (same regime-reset / 10-day-high re-entry rule):

| Buffer | 10y CAGR / DD | 5y CAGR / DD |
|---|---|---|
| 0.25% | 41.83% / 44.71% | 26.23% / 44.56% |
| **0.50%** | **43.27% / 45.23%** | **29.46% / 42.96%** |
| 0.75% | 45.95% / 45.76% | 31.04% / 42.96% |
| 1.00% | 47.07% / 45.76% | 29.67% / 42.96% |

All four pass both windows at 1 bp (the 5 bp checks also pass: 10y 41.20–46.56%,
5y 25.61–30.53%). The 10y CAGR ranges 41.8–47.1% and the 5y 26.2–31.0%, so the
result is not a knife-edge; 0.5% is a conservative mid-point, not the best
setting. The 1.0% buffer has the highest 10y CAGR but a slightly lower 5y CAGR
than 0.75%.

**V4 vol target:**

| Target | 10y CAGR / DD | 5y CAGR / DD |
|---|---|---|
| 50% | 42.09% / 41.27% | 33.62% / 35.31% |
| **55%** | **43.66% / 43.10%** | **34.88% / 36.64%** |
| 60% | 45.06% / 44.81% | 35.56% / 38.14% |

Monotone in the target: higher target → higher CAGR and higher DD. All three
pass both windows. This is the most robust surface in the study.

**V3 peak stop** (QQQ 20-day-high re-entry) is not robust. The 10y CAGR/DD
surface is 35.17%/32.25% at 8%, 36.75%/40.17% at 10%, 45.39%/45.71% at 12%,
39.76%/37.57% at 15%, 37.87%/43.28% at 18%, 36.59%/43.57% at 20%, and
38.32%/53.79% at 25%. Only 12% and 15% clear 39.28% at 1 bp; at 5 bp only 12%
does (44.12%/46.66%). The 5y returns are equally non-monotone: 26.0%, 35.3%,
49.4%, 51.6%, 37.2%, 28.2%, 34.6% for the same stops. The 15% row in the
results table is the pre-specified example; picking 12% after seeing the grid
would be cherry-picking, and neither is a stable rule. I do not recommend V3.

**V2 sticky re-entry fails the 10y CAGR bar** (37.12% < 39.28% at 1 bp, 36.67%
at 5 bp; 10y DD 51.47%) and sits out most of 2019 (−7.0% vs +148.2% for TQQQ)
because a stop can fire without the daily regime ever going bearish. It passes
only the 5y window (24.13% / 34.28%). It is reported as a negative control.

---

## 7. Costs and implementation notes

- **1 bp vs 5 bp.** V1: 10y 43.27% → 42.70% CAGR, 45.23% → 45.84% DD; 5y
  29.46% → 28.91%, 42.96% → 43.14%. V4: 43.66% → 43.07% CAGR, 43.10% →
  43.55% DD; 5y 34.88% → 34.28%, 36.64% → 36.66%. Both still pass.
- **Fills/turnover.** V1: 97 fills and 799x turnover over 10y (53/77x over
  5y); the stop is a rare event, so costs are small. V4: 881 fills and 1067x
  over 10y (420/120x over 5y) because the vol weight changes often; the 5 bp
  drag is still only ~0.6 pp/yr.
- **Execution.** The stop observes the 1-minute close and fills at the next
  minute open. On a fast crash day the fill can be worse than the threshold;
  the backtest includes that gap because it uses the actual next-minute open.
- **BIL.** BIL is the cash proxy; its minute prices are forward-filled from the
  sparse BIL tape, and its small daily drift is included. No risk-free rate is
  added separately.
- **Start convention.** The minute strategy can be invested from the first
  bar's next-minute open if the prior day's regime was bullish; the daily
  harness starts in cash and fills at the next day's open. This makes the
  minute baseline's 5y CAGR 35.59% vs the daily baseline's 34.61%. The
  comparison tables show both, so the difference is visible rather than hidden.

---

## 8. Limitations and honest assessment

- **One crash, one bear market.** The 10y sample contains the 2020 COVID crash
  and the 2022 bear market. V1's 10y DD improvement is largely the 2020 event;
  the 2018, 2019, 2023 and 2024 whipsaws show that the same rule can lag in
  ordinary chop. V1's 10y CAGR is below the daily baseline's; treat the 45.23%
  DD as a sample-specific result, not a guarantee.
- **2018 is the worst relative year.** −11.6% vs −4.3% for the baseline. The
  Q4-2018 chop produced nine round trips. An investor who cannot tolerate that
  should prefer V4 or the plain daily baseline.
- **V1's 5y DD is worse than the daily baseline** (42.96% vs 36.86%) because of
  the 2024 whipsaws. It still passes the TQQQ bar by a wide margin, but the
  "lower DD than the baseline" claim is only true on the 10y window.
- **V4 is not a stop, but it is the best variant here.** It dominates V1 on
  all four headline metrics (10y 43.66%/43.10% vs 43.27%/45.23%; 5y
  34.88%/36.64% vs 29.46%/42.96%). Its 10y CAGR (43.66%) is still below the
  daily baseline's 45.31%.
- **In-sample.** All parameters were chosen after looking at the full sample;
  the buffer/target stability tables are a robustness check, not out-of-sample
  validation. A true walk-forward would re-select the buffer each year.
- **Data.** Adjusted 1-minute data can have split/dividend artefacts; the TQQQ
  daily and minute series were cross-checked against Yahoo daily closes. The
  15:59 bar is treated as the daily close, matching `bt.panel(..., "1D")`.
- **No shorting, no extra leverage.** The strategy is long TQQQ/BIL only.
- **Revision history.** The 2026-11-25 report used `per_bar(thr_d)` for the
  threshold, a one-day-stale value. It reported V1 at 46.89%/45.32% (10y) and
  32.40%/42.96% (5y). The corrected `same_day(thr_d)` code produces
  43.27%/45.23% and 29.46%/42.96%. The old numbers are withdrawn; see the
  revision note at the top.

---

## 9. Files

- `strategy.py` — runnable implementation of all four variants; reproduces the
  metrics and writes `result.json`.
- `result.json` — machine-readable metrics: 1 bp/5 bp, both windows, yearly
  returns, yearly drawdowns, fills, turnover, exposure, benchmark.
- `report.md` — this document.

Run:

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
python research/agents/drawdown-stop-overlay/strategy.py
```

## 10. Source links

1. FinLab, *TQQQ 200-Day Moving Average Strategy: 7 Leveraged ETF Rules*,
   2026-10 — <https://finlab.finance/en/blog/leveraged-etf-timing-backtest>
2. Faber, *A Quantitative Approach to Tactical Asset Allocation*, 2007 —
   <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=962461>
3. Moreira & Muir, *Volatility-Managed Portfolios*, 2017 —
   <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2659431>
4. Cederburg, O'Doherty, Wang & Yan, *On the performance of volatility-managed
   portfolios*, JFE 2020 —
   <https://www.sciencedirect.com/science/article/abs/pii/S0304405X2030132X>
5. Man Group, *The Impact of Volatility Targeting* —
   <https://man.com/insights/the-impact-of-volatility-targeting>
6. Investopedia, *Trailing Stop* —
   <https://www.investopedia.com/terms/t/trailingstop.asp>
7. ShareScope, *Trend following and trailing stops* —
   <https://knowledge.sharescope.co.uk/2022/08/26/trend-following-and-trailing-stops-methods-to-capture-trends/>
8. Fonseca, *Point-in-Time Backtesting of Momentum-Trend Equity Strategies*
   (ATR trailing stop; bias taxonomy) —
   <https://pure.buas.nl/ws/files/39878068/Fonseca_Point-in-Time_backtesting_of_momentum-trend_equity_strategies.pdf>
9. Brock, Lakonishok & LeBaron, *Simple Technical Trading Rules and the
   Stochastic Properties of Stock Returns*, 1992 —
   <https://doi.org/10.1111/j.1540-6261.1992.tb04681.x>
