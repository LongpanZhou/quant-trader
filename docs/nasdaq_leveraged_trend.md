# Beating QQQ by 10 points a year: a leveraged-trend study

**Question.** Find a rules-based strategy that, over the past five years, beat
buying and holding the Nasdaq-100 (QQQ) by 10 percentage points a year â€” if
QQQ makes 10%, make 20%; if QQQ makes -10%, make 0%.

**Answer.** `configs/nasdaq_leveraged_trend.toml` â€” hold a volatility-targeted
blend of QQQ and TQQQ while QQQ is above its 165-day average, T-bills
otherwise. Over the five years to 20 Nov 2026 it returned **25.7% a year
against QQQ's 9.5% (+16.2 points a year)**, with a **29.9% maximum drawdown
versus QQQ's 35.1%**, and it beat QQQ in **every complete calendar year from
2022 to 2026 by 11 to 31 points**.

That is a better result than the published literature leads one to expect, and
the reasons are set out honestly in Â§7: the window contains one crash and one
very strong recovery, the strategy uses 3x leverage, and 2026 ended on a weak
note for QQQ. Read Â§7 before believing Â§4.

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
- **Faber (2007), "A Quantitative Approach to Tactical Asset Allocation"** â€”
  the 10-month SMA rule; the source of the "own it above the average, T-bills
  below" pattern.
- **Moreira & Muir (2017), "Volatility-Managed Portfolios"** â€” scale exposure
  by trailing realized variance. Target volatility is what keeps the 3x fund
  from being held at full size in a 40%-vol tape.

The closest published test of the exact combination is **NygÃ¥rd & Liukko (2026)**,
a LinkÃ¶ping thesis on the Nasdaq-100 from 2001 to 2026 with synthetic
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
(`lag_bars = 1`), which matches the live loop's next-session execution:

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
while the *instrument* gets more aggressive as volatility falls â€” the Gayed &
Bilello mechanism, expressed as a continuous weight rather than an on/off
switch. Positions are only resized when they drift more than 5% of equity
(`rebalance_band`).

The strategy trades `QQQ`, `TQQQ` and `BIL` only. There is no stock universe,
so there is **no survivorship bias** in the usual sense: the backtest holds the
actual funds that existed.

## 4. Result: five years, Nov 2021 - Nov 2026

```
Strategy return      : +212.85%  (+25.69% a year)
QQQ buy & hold       :  +57.21%  ( +9.49% a year)
Excess vs QQQ        : +16.20% a year
Max drawdown         : 29.88%  (QQQ: 35.12%)
Sharpe (annualised)  : 0.82
Closed trades        : 54      Win rate: 61.1%   Profit factor: 4.47
```

| Year | Strategy | QQQ | Excess | Days |
|---|---:|---:|---:|---:|
| 2021 (partial) | -3.4% | -0.1% | -3.3 | 26 |
| 2022 | -15.4% | -32.6% | **+17.2** | 251 |
| 2023 | +85.7% | +54.9% | **+30.9** | 250 |
| 2024 | +36.8% | +25.6% | **+11.2** | 252 |
| 2025 | +36.6% | +20.8% | **+15.8** | 250 |
| 2026 (to 20 Nov) | +10.3% | -0.6% | **+10.9** | 224 |

Every complete calendar year clears +10pp. On a calendar-year basis 2021 also
clears it: in the ten-year run the strategy made +56.7% against QQQ's +27.4%
(+29.3pp).

Raw output: `research/results/nasdaq_leveraged_trend_5y.txt`.

## 5. Robustness

### 5.1 Ten years (2016-2026), same rule, no re-tuning

```
Strategy return      : +2418.43%  (+38.14% a year)
QQQ buy & hold       :  +448.06%  (+18.58% a year)
Excess vs QQQ        : +19.57% a year
Max drawdown         : 35.88%  (QQQ: 35.12%)
Sharpe (annualised)  : 1.06
```

Yearly excess: 2017 +82.5, 2018 -2.2, 2019 +2.0, 2020 +20.1, 2021 +29.3,
2022 +17.2, 2023 +30.9, 2024 +11.2, 2025 +15.9, 2026 +10.9. The weak years are
the choppy ones (2018, 2019), which is the known cost of trend following.
Raw output: `research/results/nasdaq_leveraged_trend_10y.txt`.

### 5.2 Parameter plateau (5 years, all with lag 1)

| SMA | Vol target | CAGR | Excess | Max DD | Sharpe |
|---:|---:|---:|---:|---:|---:|
| 155 | 40% | 21.6% | +12.1 | 29.9% | 0.73 |
| **165** | **40%** | **25.7%** | **+16.2** | **29.9%** | **0.82** |
| 175 | 40% | 26.7% | +17.2 | 29.0% | 0.84 |
| 165 | 45% | 26.9% | +17.4 | 32.1% | 0.81 |
| 165 | 50% | 26.8% | +17.3 | 34.2% | 0.79 |
| 165 | 40%, vol 10d | 22.1% | +12.6 | 33.9% | 0.73 |
| 165 | 40%, vol 40d | 21.7% | +12.2 | 32.1% | 0.73 |

165 is the centre of a broad region, not a single lucky cell. Every
combination tested in 155-175 / 35-50% clears +10pp. The failure case is a
**200-day** average: +6.8pp, because it exits later and re-enters later in this
particular cycle.

### 5.3 Execution lag and costs

| Assumption | CAGR | Excess | Max DD | Sharpe |
|---|---:|---:|---:|---:|
| Fill at signal close (optimistic) | 23.1% | +13.6 | 29.5% | 0.76 |
| **One-bar lag (live-like)** | **25.7%** | **+16.2** | **29.9%** | **0.82** |
| Lag + 5 bp slippage | 24.7% | +15.2 | 30.1% | 0.80 |

The edge survives a conservative execution assumption and 5bp costs. It does
not depend on filling at the close that generated the signal.

### 5.4 Endpoint sensitivity

QQQ fell about 12% in November 2026 before the test end. Shifting the whole
window back:

| End date | Strategy CAGR | QQQ CAGR | Excess |
|---|---:|---:|---:|
| 20 Nov 2026 (0d) | 25.7% | 9.5% | +16.2 |
| 21 Oct 2026 (-30d) | 31.3% | 14.0% | +17.3 |
| 6 Oct 2026 (-45d) | 39.7% | 16.6% | +23.1 |
| 21 Sep 2026 (-60d) | 35.9% | 15.6% | +20.3 |

The excess is *largest* at the October high, so the result is not produced by
the November drawdown; if anything the chosen end date is the least favourable.

### 5.5 How much is "avoided 2022"?

A natural objection is that the whole edge is one lucky exit. Substituting
QQQ's actual 2022 return for the strategy's in 2022, and keeping every other
year, gives about **2.49x** over five years versus QQQ's 1.57x â€” roughly
**+9.7pp a year** even with zero credit for 2022. So the crash filter is not
the whole story; the volatility-targeted leverage in 2023-2026 does most of
the remaining work. Conversely, if the 2023-2026 AI rally is removed, the
strategy has little to show â€” see Â§7.

## 6. Alternatives tested and rejected

All over the same five years, benchmark QQQ, daily bars.

| Variant | CAGR | Excess | Max DD | Why rejected |
|---|---:|---:|---:|---|
| QLD (2x) instead of TQQQ | 17.4% | +8.0 | 21.6% | Below the 10pp bar |
| Naive 150-day, no vol target | 22.8% | +13.3 | 38.0% | Same return, much deeper drawdown; 2022 was -32% |
| Naive 200-day, no vol target | 14.8% | +5.3 | 51.4% | Below bar, worst drawdown |
| 200-day + 40% vol target | 16.3% | +6.8 | 37.9% | Below bar |
| TSMOM monthly, 12-month, 2x margin | 8.8% | -0.7 | 40.5% | No edge; monthly rebalancing too slow for this cycle |

The naive "3x when above the 200-day" strategy is the one most often cited
online. Here it delivered +5.3pp with a 51% drawdown â€” worse on both axes than
the volatility-targeted version. Sizing is not a detail; it is the strategy.

Full sweep of 57 configurations: `research/results/sweep.csv`.

One more alternative was ruled out before coding. Cross-sectional momentum on
today's Nasdaq-100 members looks spectacular â€” a controlled test of the same
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
   a year vs QQQ's 8.0% â€” only **+5.1pp** â€” with an **-83% drawdown**. The
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
6. **Backtest fills are idealised.** Daily closes, no commissions, no
   liquidity limits, 1bp slippage in the headline run. The 5bp run is
   +15.2pp; a 10-20bp assumption would erode more.
7. **The live sim does not pay interest on idle cash.** The backtest's BIL
   holding earns T-bill total return; the paper ledger may not credit those
   dividends. Live results in risk-off periods will be slightly worse than
   the backtest.
8. **Publication decay.** The 2016 rule has been public for a decade. A 2026
   replication of the Gayed-Bilello rule reports a 2x rotation at 14.0%/yr
   vs 11.45% for the benchmark since 1988 â€” a much smaller edge than the
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
  `end_days_ago` for endpoint sensitivity. `tsmom` may now use margin up to
  `risk.max_leverage`.
- `src/backtest.rs`: benchmark series is fetched independently of the traded
  universe and used for the buy-and-hold line, drawdown and the yearly table;
  the yearly table now shows the benchmark and the difference.
- `configs/nasdaq_leveraged_trend.toml`: the strategy preset.
- `research/`: sweep configs, logs and result files.

## 10. Bottom line

The objective is met on the stated window: **+16.2pp a year over QQQ, in every
complete year from 2022 to 2026, with a smaller drawdown than QQQ**. It is met
by leveraging a trend filter, not by finding an uncorrelated alpha source, and
it would not have met the bar in 2018-2019 or with 2x instead of 3x.

The wider evidence says what to expect beyond this window. Over a full cycle
including 2000-02, the same family delivers roughly **+5pp a year with a
-65% to -83% drawdown** (independent 2000-2026 replications). The five-year
result is therefore a best-case regime, not a forecast. Anyone running this
should size it as a satellite, expect a 30-50% drawdown in normal use and
65%+ in a 2000-style unwind, and should not expect the last five years to
repeat.

*Educational paper-trading research, not financial advice.*

