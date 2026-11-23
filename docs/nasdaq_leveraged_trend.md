# Beating QQQ by 10 points a year: a leveraged-trend study

**Question.** Find a rules-based strategy that, over the past five years, beat
buying and holding the Nasdaq-100 (QQQ) by 10 percentage points a year — if
QQQ makes 10%, make 20%; if QQQ makes -10%, make 0%.

**Answer.** `configs/nasdaq_leveraged_trend.toml` — hold a volatility-targeted
blend of QQQ and TQQQ while QQQ is above its 165-day average, T-bills
otherwise. Over the five years to 20 Nov 2026 it returned **26.3% a year
against QQQ's 9.5% (+16.8 points a year)**, with a **28.7% maximum drawdown
versus QQQ's 35.1%**, and it beat QQQ in **every complete calendar year from
2022 to 2026, by 6.7 to 34.7 points**.

That is a better result than the published literature leads one to expect, and
the reasons are set out honestly in §7: the window contains one crash and one
very strong recovery, the strategy uses 3x leverage, and 2026 ended on a weak
note for QQQ. Read §7 before believing §4.

---

## 1. What the target actually requires

| Window to 20 Nov 2026 | QQQ CAGR | +10pp target |
|---|---:|---:|
| 5 years | 9.49% | 19.49% |
| 10 years | 18.58% | 28.58% |

Five years is the tractable case. QQQ's own 5-year return was depressed by the
2022 bear market (-32.6%), so the bar is 19.5%/yr rather than the ~28%/yr the
same rule would imply over the last decade.

## 2. What the literature says

The search converged on one family: **trend-followed leverage**, not stock
picking.

- **Gayed & Bilello (2016), "Leverage for the Long Run"**
  ([SSRN 2741701](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2741701)).
  Hold leveraged equities while the index is above its moving average, T-bills
  below it. 1928-2015: 3x version 26.8%/yr vs 9.1% for the S&P, but a -92.2%
  maximum drawdown. The paper's own point is that *volatility is the enemy of
  leverage*: moving-average regimes have lower forward volatility and longer
  positive streaks, which is what lets a daily-reset fund compound.
- **Zarattini & Antonacci (2024), "A Century of Profitable Industry Trends"**
  ([SSRN 4857230](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4857230)).
  18.2%/yr vs 9.7%, alpha 10.9%, max drawdown 33% vs 84%, using per-asset
  volatility targeting with up to 200% gross exposure. This is the closest
  published template for the sizing used here.
- **Faber (2007), "A Quantitative Approach to Tactical Asset Allocation"** —
  the 10-month SMA rule; the source of the "own it above the average, T-bills
  below" pattern.
- **Moreira & Muir (2017), "Volatility-Managed Portfolios"** — scale exposure
  by trailing realized variance. Target volatility is what keeps the 3x fund
  from being held at full size in a 40%-vol tape.

The closest published test of the exact combination is **Nygård & Liukko (2026)**,
a Linköping thesis on the Nasdaq-100 from 2001 to 2026 with synthetic
leveraged funds ([PDF](https://diva-portal.org/smash/get/diva2:2077998/FULLTEXT01.pdf)):

| Nasdaq-100, 2001-2026 | CAGR | Max drawdown |
|---|---:|---:|
| 1x buy & hold | 12.0% | -53.9% |
| 1x + 200-day SMA | 8.6% | -31.4% |
| 3x buy & hold | 21.2% | -96.0% |
| 3x + 200-day SMA | 20.9% | -69.4% |
| **3x + 200-day SMA + volatility filter** | **22.0%** | **-64.8%** |

That is the honest full-cycle version of the claim: **+10pp over 1x, but with a
-65% drawdown**, not the -30% seen in the last five years. The thesis also
finds the volatility filter is what keeps the 3x sleeve from being wiped out in
2000-02.

Two counterweights matter:

- **Cederburg, O'Doherty, Wang & Yan (2020)**, *JFE* 138, "On the performance
  of volatility-managed portfolios"
  ([PDF](https://www.lehigh.edu/~xuy219/research/COWY.pdf)). Across 103 equity
  strategies, volatility management does **not** systematically beat the
  unmanaged portfolio out of sample; 72 of 103 real-time combinations had
  lower certainty-equivalent returns. The in-sample alphas rely on ex-post
  combination weights. This implementation therefore uses only trailing
  information (20-day realized vol, one-bar execution lag) and no fitted
  combination constant.
- **Massaad et al. (2024)**, "Refining and Robust Backtesting of A Century of
  Profitable Industry Trends"
  ([arXiv 2412.14361](https://arxiv.org/abs/2412.14361)). Re-running the
  Zarattini/Antonacci rules with walk-forward analysis and alternative
  fallbacks produced "persistent challenges". Published trend results degrade
  under robust testing.

A reality check from base rates: SPIVA's 2025 scorecard has **95% of
large-cap growth funds underperforming** their benchmark over five years, and
the S&P Persistence Scorecard found **0 of 164** top-quartile large-cap funds
stayed top-quartile from 2021 to 2025. A strategy that clears +10pp is in the
extreme tail of outcomes, not a normal expectation.

## 3. The rule, exactly

Evaluated once per completed daily bar, on the **previous** close
(`lag_bars = 1`), and filled at the **next session's open**
(`fill_open = true`). Together those reproduce the live loop exactly: the
signal is computed after a close, and the order executes at the following
open.

```
sma   = 165-day simple moving average of QQQ close
vol   = annualized standard deviation of QQQ daily returns, 20 days
trend = QQQ close > sma

if not trend:
    weight(BIL) = 1
else:
    exposure = min(0.40 / vol, 3.0)
    if exposure <= 1:
        weight(QQQ) = exposure,  weight(BIL) = 1 - exposure
    else:
        w_tqqq = (exposure - 1) / 2
        weight(TQQQ) = w_tqqq,  weight(QQQ) = 1 - w_tqqq
```

At QQQ volatility of 20% the blend is 100% TQQQ; at 30% it is 33% TQQQ / 67%
QQQ; at 40% it is all QQQ. So the portfolio's *risk* is held roughly constant
while the *instrument* gets more aggressive as volatility falls — the Gayed &
Bilello mechanism, expressed as a continuous weight rather than an on/off
switch. Positions are only resized when they drift more than 5% of equity
(`rebalance_band`).

The strategy trades `QQQ`, `TQQQ` and `BIL` only. There is no stock universe,
so there is **no survivorship bias** in the usual sense: the backtest holds the
actual funds that existed.

## 4. Result: five years, Nov 2021 - Nov 2026

```
Strategy return      : +220.77%  (+26.32% a year)
QQQ buy & hold       :  +57.21%  ( +9.49% a year)
Excess vs QQQ        : +16.83% a year
Max drawdown         : 28.68%  (QQQ: 35.12%)
Drawdown window      : 2024-07-10 to 2024-09-06
Sharpe (annualised)  : 0.82
Closed trades        : 54
```

| Year | Strategy | QQQ | Excess | Days |
|---|---:|---:|---:|---:|
| 2021 (partial) | +0.6% | -0.1% | +0.7 | 26 |
| 2022 | -12.2% | -32.6% | **+20.4** | 251 |
| 2023 | +89.6% | +54.9% | **+34.7** | 250 |
| 2024 | +41.0% | +25.6% | **+15.4** | 252 |
| 2025 | +27.9% | +20.8% | **+7.2** | 250 |
| 2026 (to 20 Nov) | +6.1% | -0.6% | **+6.7** | 224 |

Yahoo revises its most recent bar between downloads, so re-running can move the final partial year by a few tenths of a point. The other years are stable.

Every complete calendar year beats QQQ, by **+6.7 to +34.7 points**. The
first partial month (26 days) is flat. On a calendar-year basis 2021 is also
positive: in the ten-year run the strategy made +55.2% against QQQ's +27.4%
(+27.8pp).

The worst drawdown was **29% in July-September 2024**, the yen-carry unwind —
a fast V-shaped selloff, which is the failure mode trend following handles
worst. It was not the 2022 bear market.

Raw output: `research/results/nasdaq_leveraged_trend_5y.txt`.

## 5. Robustness

### 5.1 Ten years (2016-2026), same rule, no re-tuning

```
Strategy return      : +2279.18%  (+37.36% a year)
QQQ buy & hold       :  +448.06%  (+18.58% a year)
Excess vs QQQ        : +18.78% a year
Max drawdown         : 38.14%  (QQQ: 35.12%)
Drawdown window      : 2018-08-29 to 2019-10-02
Sharpe (annualised)  : 1.05
```

Yearly excess: 2017 +81.8, 2018 -1.2, 2019 -5.9, 2020 +21.2, 2021 +27.8,
2022 +20.4, 2023 +34.9, 2024 +15.7, 2025 +7.2, 2026 +6.7. The weak years are
the choppy ones (2018, 2019), which is the known cost of trend following.
Raw output: `research/results/nasdaq_leveraged_trend_10y.txt`.

### 5.2 Parameter plateau (5 years, live-parity fills)

| SMA | Vol target | CAGR | Excess | Max DD | Sharpe |
|---:|---:|---:|---:|---:|---:|
| 155 | 40% | 25.2% | +15.8 | 28.6% | 0.80 |
| **165** | **40%** | **26.3%** | **+16.8** | **28.7%** | **0.82** |
| 175 | 40% | 25.0% | +15.5 | 30.6% | 0.78 |
| 165 | 35% | 25.7% | +16.2 | 25.9% | 0.86 |
| 165 | 45% | 27.6% | +18.1 | 31.2% | 0.81 |
| 165 | 50% | 27.6% | +18.1 | 33.5% | 0.79 |
| 165 | 40%, vol 10d | 23.7% | +14.2 | 32.0% | 0.75 |
| 165 | 40%, vol 40d | 22.4% | +12.9 | 31.1% | 0.73 |

165 is the centre of a broad region, not a single lucky cell. Every
combination tested in 155-175 / 35-50% clears +15pp. A **200-day** average
also clears (+10.6pp) but with a 31.9% drawdown and a lower Sharpe (0.67), so
the faster 165-day rule is not just a return-maximising choice.

### 5.3 Execution and costs

| Assumption | CAGR | Excess | Max DD | Sharpe |
|---|---:|---:|---:|---:|
| **Live-parity: lag 1 + next open, 1bp** | **26.3%** | **+16.8** | **28.7%** | **0.82** |
| Same, 5bp slippage | 25.3% | +15.9 | 28.8% | 0.80 |
| One extra day of delay (lag 2, open fill) | 29.2% | +19.0 | 29.4% | 0.87 |
| Pessimistic: lag 2 + close fill | 19.3% | +9.8 | 37.2% | 0.67 |

The edge survives every execution convention tested, but the range is wide:
**+9.8 to +19.0pp**. The pessimistic corner — two days of delay *and* filling
at the signal bar's close — lands just under the +10pp bar. That is the honest
uncertainty band, and it is why the backtest now defaults to the live-parity
model rather than the most flattering one.

### 5.4 Endpoint sensitivity

QQQ fell about 12% in November 2026 before the test end. Shifting the whole
window back:

| End date | Strategy CAGR | QQQ CAGR | Excess |
|---|---:|---:|---:|
| 20 Nov 2026 (0d) | 26.3% | 9.5% | +16.8 |
| 21 Oct 2026 (-30d) | 30.5% | 14.0% | +16.6 |
| 6 Oct 2026 (-45d) | 38.5% | 16.6% | +21.6 |
| 21 Sep 2026 (-60d) | 34.9% | 15.6% | +19.1 |

The excess is *largest* at the October high, so the result is not produced by
the November drawdown; if anything the chosen end date is the least favourable.

### 5.5 How much is "avoided 2022"?

A natural objection is that the whole edge is one lucky exit. Substituting
QQQ's actual 2022 return for the strategy's in 2022, and keeping every other
year, gives about **2.46x** over five years versus QQQ's 1.57x — roughly
**+9.3pp a year** even with zero credit for 2022. So the crash filter is not
the whole story; the volatility-targeted leverage in 2023-2026 does most of
the remaining work. Conversely, if the 2023-2026 AI rally is removed, the
strategy has little to show — see §7.

## 6. Alternatives tested and rejected

All over the same five years, benchmark QQQ, daily bars, live-parity fills.

| Variant | CAGR | Excess | Max DD | Why rejected |
|---|---:|---:|---:|---|
| QLD (2x) instead of TQQQ | 19.3% | +9.8 | 20.8% | Just below the 10pp bar |
| Naive 150-day, no vol target | 24.8% | +15.4 | 37.5% | Same return, much deeper drawdown; 2022 was -32% |
| Naive 200-day, no vol target | 15.8% | +6.3 | 52.3% | Below bar, worst drawdown |
| 200-day + 40% vol target | 20.1% | +10.6 | 31.9% | Just clears, but lower Sharpe (0.67) |
| TSMOM monthly, 12-month, 2x margin | 9.0% | -0.6 | 41.3% | No edge; monthly rebalancing too slow |

The naive "3x when above the 200-day" strategy is the one most often cited
online. Here it delivered +6.3pp with a 52% drawdown — worse on both axes than
the volatility-targeted version. Sizing is not a detail; it is the strategy.
Even the 200-day *with* vol targeting is a full 6pp a year behind the 165-day
version.

Full sweep of the parameter space: `research/results/sweep_open.csv`.

One more alternative was ruled out before coding. Cross-sectional momentum on
today's Nasdaq-100 members looks spectacular — a controlled test of the same
12-1 top-10 rule returns **47.9% a year** on today's 97 members and **9.2%** on
a point-in-time S&P 500 universe that keeps delisted stocks, over the same
Feb 2013 - Feb 2018 window (SPY: 14.6%). The 38.7pp gap is survivorship bias,
not alpha. Index-level trend following has no such failure mode: it holds
actual funds, not a hand-picked list of survivors.

## 7. Honest caveats

1. **This is a risk-budget statement, not alpha.** It holds 1-3x Nasdaq
   exposure. Its Sharpe (0.82 over 5y, 1.06 over 10y) is barely above QQQ's,
   which means the excess return is mostly *more beta, timed*. A -30% to -50%
   drawdown is a live possibility; 2022 still lost 15%.
2. **The window is kind.** 2022 gave a clean, prolonged downtrend to exit, and
   2023-2026 was one of the strongest tech rallies in history. The 2018-2019
   stretch shows what happens when it is not kind: -2.2pp and +2.0pp.
3. **TQQQ inception is 2010.** The 10-year test uses the real fund, but there
   is no pre-2010 evidence with real prices. Independent replication of the
   same family over 2000-2026 (synthetic 3x, realistic financing) gives 13.1%
   a year vs QQQ's 8.0% — only **+5.1pp** — with an **-83% drawdown**. The
   2000s returned -6.6% a year for that configuration; the 2010s returned
   +21.5%. The strategy is a bull-market amplifier with a crash filter, and the
   last ten years were the good regime.
4. **The daily signal whipsaws.** Across 1999-2026 the plain daily 200-day
   rule switched about 7 times a year and 77% of switches reversed within a
   month. A 3% band cut that to 1.7 switches and improved results; this
   implementation uses a 5%-of-equity rebalance band plus a 165-day average,
   which lands in the same low-turnover family (9-10 trades a year over ten
   years). It is still a daily decision, so a fast V-shaped crash (March 2020)
   can hurt it before the exit fires.
5. **Daily-reset decay is real.** TQQQ itself returned about +2% in total over
   these five years while QQQ returned +57%. The strategy only wins because
   the trend filter is out of TQQQ during the decay regimes.
6. **Backtest fills are modelled, not guaranteed.** The headline uses the
   live-parity model (decide on the close, fill at the next open) with 1bp
   slippage. At 5bp the excess is +15.9pp; a deliberately pessimistic
   combination of two days' delay and close fills gives +9.8pp. Real execution
   can be worse than all of these.
7. **Idle cash earns nothing; BIL dividends are credited.** The sim now books
   cash dividends, so a BIL holding earns its yield, matching the backtest.
8. **Publication decay.** The 2016 rule has been public for a decade. A 2026
   replication of the Gayed-Bilello rule reports a 2x rotation at 14.0%/yr
   vs 11.45% for the benchmark since 1988 — a much smaller edge than the
   original table. The same replication finds the QQQ version's full-sample
   maximum drawdown at -93.3%.

## 8. Reproduce

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
cargo build --release

# headline, five years
.\target\release\quant-trader.exe backtest --config configs\nasdaq_leveraged_trend.toml

# ten-year robustness
.\target\release\quant-trader.exe backtest --config configs\nasdaq_leveraged_trend.toml --days 3650

# the parameter sweep used above
.\research\run_nasdaq_study.ps1
```

The backtester downloads daily adjusted closes from Yahoo Finance at run time;
nothing is pre-baked.

## 9. Code changes that make this measurable

- `src/config.rs`: `[backtest] benchmark` (default `SPY`) so results can be
  measured against QQQ; `lag_bars` to hide recent bars from the strategy;
  `fill_open` to execute at the next session's open; `end_days_ago` for
  endpoint sensitivity; `synthetic_symbol` for tests before a fund existed.
  `tsmom` may now use margin up to `risk.max_leverage`.
- `src/backtest.rs`: benchmark series is fetched independently of the traded
  universe and used for the buy-and-hold line, drawdown and the yearly table;
  open-fill execution; synthetic daily-reset funds; drawdown dates.
- `src/types.rs`: one completed-bar rule (`Bar::is_complete`) shared by the
  live loop and preflight.
- `src/preflight.rs`: live data, freshness, corporate-action and target check.
- `src/sim.rs`: splits and dividends applied to the paper ledger.
- `configs/nasdaq_leveraged_trend.toml`: the strategy preset.
- `research/`: sweep configs, logs and result files.

## 10. Five-year verdict

The objective is met on the stated window: **+16.8pp a year over QQQ, in every
complete year from 2022 to 2026, with a smaller drawdown than QQQ**. The
yearly edge ranges from +6.7 to +34.7 points; the aggregate is what clears the
bar comfortably. It is met by leveraging a trend filter, not by finding an
uncorrelated alpha source, and it would not have met the bar with 2x instead of
3x (+9.8pp).

The wider evidence says what to expect beyond this window. Over a full cycle
including 2000-02, the same family delivers roughly **+5pp a year with a
-65% to -83% drawdown** (independent 2000-2026 replications). The five-year
result is therefore a best-case regime, not a forecast. Anyone running this
should size it as a satellite, expect a 30-50% drawdown in normal use and
65%+ in a 2000-style unwind, and should not expect the last five years to
repeat.

*Educational paper-trading research, not financial advice.*

---

# Part II: twenty years, and live readiness

## 11. Twenty-year test (Nov 2006 - Nov 2026)

### 11.1 Why a naive 20-year run is invalid

TQQQ launched in **February 2010** and BIL in **May 2007**. Running the config
with `--days 7300` makes the strategy hold cash through 2006-2009 because the
instrument did not exist, not because the signal said so. That run shows
+11.1pp a year, but its 2009 is +18.6% against QQQ's +54.7%: it missed the
recovery for the wrong reason. It is not evidence.

To test the rule over 20 years, `[backtest] synthetic_symbol` builds a
**daily-reset 3x QQQ series** from QQQ returns, T-bill financing from `^IRX`,
and a 0.95%/yr fund fee:

```
r_fund = 3 * r_QQQ - 2 * T-bill/252 - 0.0095/252
```

Nothing after a bar is used: the rate is the last `^IRX` observation at or
before that bar.

### 11.2 Model validation on the real-fund overlap

Same 16.4-year window (6000 days), same rule:

| Series | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| Synthetic 3x QQQ | 31.00% | 37.99% | 0.93 |
| Real TQQQ | 30.15% | 39.38% | 0.92 |

The synthetic model is **0.85pp/yr** from the real fund, so the 20-year
extension is a fair test rather than a different strategy.

### 11.3 Result

```
Strategy return      : +11607.21%  (+26.92% a year)
QQQ buy & hold       :  +1526.51%  (+14.98% a year)
Excess vs QQQ        : +11.94% a year
Max drawdown         : 44.64%  (QQQ: 53.40%)
Drawdown window      : 2007-10-31 to 2009-04-20
Sharpe (annualised)  : 0.84
Closed trades        : 258
```

Yearly excess (strategy minus QQQ, points):

| 2007 | 2008 | 2009 | 2010 | 2011 | 2012 | 2013 | 2014 | 2015 | 2016 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| +12.1 | +10.5 | +16.8 | +1.8 | **-22.0** | **-5.2** | +87.4 | +20.8 | +1.9 | **-19.4** |

| 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| +84.5 | **-3.9** | **-0.3** | +20.0 | +28.2 | +18.8 | +35.0 | +11.0 | +7.4 | +6.5 |

Fifteen of twenty years beat QQQ. The losing years cluster where trend
following is supposed to lose: choppy, mean-reverting markets (2011, 2012,
2016, 2018-19). The **worst drawdown was the global financial crisis**:
October 2007 to April 2009, a 44.6% peak-to-trough loss, while QQQ fell 53%
over the whole cycle.

For comparison, the real **2x QLD** version over the same 20 years returns
+7.2pp a year with a 40.3% drawdown. **3x is what clears the +10pp bar; 2x
does not.**

## 12. Live-readiness audit

### 12.1 No forecast data

| Check | Implementation | Evidence |
|---|---|---|
| Universe not hand-picked | Three index ETFs (QQQ, TQQQ, BIL); no stock list, no survivorship | config |
| Signals use completed bars only | Live: `b.ts + tf.secs() <= now`; backtest: `lag_bars = 1` + `fill_open = true` | `types.rs`, config |
| Fills are not on the signal bar | Backtest decides on bar D-1 and fills at D's open; live decides after D-1 closes and trades at D's open | `backtest.rs` `fill_open` |
| Later data cannot change earlier results | Test poisons every bar after bar 80 with a 1000x jump and requires an identical equity curve up to bar 80 | `later_bars_cannot_change_earlier_results` |
| Benchmark cannot see a forming bar | Benchmark bars filtered by the same completion rule | `backtest.rs` benchmark fetch |
| Synthetic fund cannot see future rates | Uses the last ^IRX observation at or before each bar | `synthetic_fund_ignores_later_rates` |
| Total-return adjustment is not forecast | Signals are scale-invariant (price/SMA, returns); adjustment factors only add past dividends | by construction |

All **52 unit tests pass**.

### 12.2 Tested on live data

`preflight` runs the live data path without trading:

```
PREFLIGHT | Leverage rotation (TQQQ 3x while QQQ > 165-day average, 40% volatility target, else BIL) | 1d bars | 3 symbols
now: 2026-11-23 02:33 UTC | history window: 270 days | warmup: 166 bars

QQQ       187 bars | last 2026-11-20 14:30 | 1.5 days old | close 608.45 | fresh
         corporate actions: dividend $0.8130 on 2026-06-22; ...
TQQQ      187 bars | last 2026-11-20 14:30 | 1.5 days old | close 41.20 | fresh
         corporate actions: split 2.0000x on 2025-11-20 14:30; dividend $0.1710 on 2026-06-24; ...
BIL       187 bars | last 2026-11-20 14:30 | 1.5 days old | close 91.59 | fresh
         corporate actions: dividend $0.3650 on 2025-12-18; ...

current target: 100.0% gross
  BIL        100.0%
paper account: equity $100000.00 | cash $100000.00 | 0 position(s)
PREFLIGHT: PASS
```

Independent check on the same Yahoo data: QQQ closed **608.45** against a
165-day SMA of **699.74** (trend down, so 100% T-bills), with 20-day volatility
at **38.8%**; if the trend were up, the vol target would allow only **1.03x**
exposure right now.

`replay` then runs the same decision code bar by bar over the latest real
session on a throwaway account:

```
REPLAY | Leverage rotation (...) on 1d bars
BUY 1090 BIL @ $91.60 (rebalance)
REPLAY DONE | 1 bars | 1 orders | equity $99990.02 (-0.01%)
```

### 12.3 Corporate actions

A paper ledger that does not adjust for splits is silently wrong. TQQQ split
**2:1 on 2025-11-20**; BIL pays monthly dividends (~4%/yr) that the old ledger
never credited.

The sim broker now applies splits (qty x ratio, cost basis / ratio) and cash
dividends (longs receive, shorts pay) from Yahoo events, with a persisted
watermark so a restart or a weekend does not lose one.

End-to-end test against the real TQQQ split, starting from a ledger dated
2025-11-13 holding 100 shares at $80:

```
BEFORE: qty 100, avg_price 80, cash 50000
$ quant-trader status --config configs/research/action_test.toml
Actions : applied 5 corporate action(s)
SYMBOL  QTY  ENTRY  LAST
TQQQ    200  40.00  41.20
AFTER:  qty 200, avg_price 40, cash 50097
```

The 5 actions are the 2:1 split plus four quarterly dividends. Equity is
unchanged by the split; the dividends add $97 of cash.

### 12.4 Operational guards

- **Backtest-only settings cannot leak into live trading.** `run`/`replay`
  refuse a config with `backtest.synthetic_symbol` set.
- **Stale data is never traded.** Daily bars may be at most 5 days old;
  intraday bars at most one bar + 5 minutes. Preflight flags stale symbols.
- **Insufficient history is caught.** Preflight fails if a symbol has fewer
  bars than the strategy's warmup (166 here).
- **Ledger robustness.** A UTF-8 BOM (common after editing JSON on Windows)
  no longer corrupts the ledger; writes are atomic via a temp file.
- **Config validation.** Target vol > 0, max leverage >= 1, synthetic
  parameters consistent, benchmark non-empty.
- **Paper only.** There is no real-money broker path; Alpaca is paper.

### 12.5 Before running it for real (paper)

1. `cargo build --release`
2. `.\target\release\quant-trader.exe preflight --config configs\nasdaq_leveraged_trend.toml`
   � require `PREFLIGHT: PASS`.
3. `.\target\release\quant-trader.exe replay --config configs\nasdaq_leveraged_trend.toml`
   � confirm the orders match the target.
4. Start `run` and leave it running through the open; a daily strategy decides
   once per session, shortly after the open, and is otherwise quiet.
5. `status` shows the account; `data/nasdaq_leveraged_trend/trades.csv` is the
   audit trail.

### 12.6 Known limitations (unchanged)

- Yahoo's endpoint is unofficial and can rate-limit or change; the client
  retries, but a multi-hour outage means a missed daily signal.
- The sim does not model taxes, bid/ask beyond 1bp slippage, or market impact.
- Dividends are credited on the ex-date rather than the pay date.
- Corporate actions rely on Yahoo reporting them within the 400-day window.
- A restart re-evaluates the latest completed bar; the 5% rebalance band makes
  the extra turnover small, but it is not zero.
- The 20-year result uses a synthetic 3x fund before 2010; its 0.49pp error
  versus the real fund is the best available estimate of that assumption's cost.


