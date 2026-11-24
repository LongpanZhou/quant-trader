# Beating QQQ by 10 points a year: a leveraged-trend study

**Question.** Find a rules-based strategy that, over the past five years, beat
buying and holding the Nasdaq-100 (QQQ) by 10 percentage points a year — if
QQQ makes 10%, make 20%; if QQQ makes -10%, make 0%.

**Answer.** `configs/nasdaq_leveraged_trend.toml` — hold a volatility-targeted
blend of QQQ and TQQQ while QQQ is above its 165-day average, T-bills
otherwise. Over the five years to 20 Nov 2026 it returned **26.4% a year
against QQQ's 9.5% (+16.9 points a year)**, with a **29.4% maximum drawdown
versus QQQ's 35.1%**, and it beat QQQ in **every complete calendar year from
2022 to 2026, by 7.4 to 36.1 points**.

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

The closest independent test of this shape we found is **Nygård & Liukko (2026)**,
a Linköping thesis on the Nasdaq-100 from 2001 to 2026 with synthetic
leveraged funds ([PDF](https://diva-portal.org/smash/get/diva2:2077998/FULLTEXT01.pdf)):

| Nasdaq-100, 2001-2026 | CAGR | Max drawdown |
|---|---:|---:|
| 1x buy & hold | 12.0% | -53.9% |
| 1x + 200-day SMA | 8.6% | -31.4% |
| 3x buy & hold | 21.2% | -96.0% |
| 3x + 200-day SMA | 20.9% | -69.4% |
| **3x + 200-day SMA + implied-vol filter** | **22.0%** | **-64.8%** |

That is the honest full-cycle version of the claim: **+10pp over 1x, but with a
-65% drawdown**, not the -30% seen in the last five years. The thesis also
finds the combined rule cuts the 3x maximum drawdown from -96% to -65%.

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

At QQQ volatility of 20% the exposure is 2.0x: **50% TQQQ / 50% QQQ**. At 30%
it is 1.33x: **16.7% TQQQ / 83.3% QQQ**. At 40% it is 1.0x: **all QQQ**. So the
portfolio's *risk* is held roughly constant while the *instrument* gets more
aggressive as volatility falls — the Gayed & Bilello mechanism, expressed as a
continuous weight rather than an on/off switch. Positions are only resized when
they drift more than 2% of equity (`rebalance_band`).

The strategy trades `QQQ`, `TQQQ` and `BIL` only. There is no stock universe,
so there is **no survivorship bias** in the usual sense: the backtest holds the
actual funds that existed.

## 4. Result: five years, Nov 2021 - Nov 2026

```
Strategy return      : +221.83%  (+26.40% a year)
QQQ buy & hold       :  +57.21%  ( +9.49% a year)
Excess vs QQQ        : +16.91% a year
Max drawdown         : 29.35%  (QQQ: 35.12%)
Drawdown window      : 2024-07-10 to 2024-09-06
Sharpe (annualised)  : 0.82
Closed trades        : 54
Weight tracking      : avg 0.69% of equity off target, worst 5.48%
```

| Year | Strategy | QQQ | Excess | Days |
|---|---:|---:|---:|---:|
| 2021 (partial) | +0.2% | -0.1% | +0.3 | 26 |
| 2022 | -12.5% | -32.6% | **+20.0** | 251 |
| 2023 | +90.9% | +54.9% | **+36.1** | 250 |
| 2024 | +40.4% | +25.6% | **+14.8** | 252 |
| 2025 | +28.2% | +20.8% | **+7.4** | 250 |
| 2026 (to 20 Nov) | +6.9% | -0.6% | **+7.5** | 224 |

Yahoo revises its most recent bar between downloads, so re-running can move the final partial year by a few tenths of a point. The other years are stable.

Every complete calendar year beats QQQ, by **+7.4 to +36.1 points**. The
first partial month (26 days) is flat. On a calendar-year basis 2021 is also
positive: in the ten-year run the strategy made +55.3% against QQQ's +27.4%
(+27.8pp).

The worst drawdown was **29% in July-September 2024**, the yen-carry unwind —
a fast V-shaped selloff, which is the failure mode trend following handles
worst. It was not the 2022 bear market.

Reproduce it with `quant-trader backtest --config configs/nasdaq_leveraged_trend.toml`.

## 5. Robustness

### 5.1 Ten years (2016-2026), same rule, no re-tuning

```
Strategy return      : +2283.14%  (+37.38% a year)
QQQ buy & hold       :  +448.06%  (+18.58% a year)
Excess vs QQQ        : +18.80% a year
Max drawdown         : 38.32%  (QQQ: 35.12%)
Drawdown window      : 2018-08-29 to 2019-10-02
Sharpe (annualised)  : 1.05
Weight tracking      : avg 0.61% of equity off target, worst 6.24%
```

Yearly excess: 2017 +81.2, 2018 -1.8, 2019 -6.2, 2020 +22.6, 2021 +27.8,
2022 +20.0, 2023 +35.9, 2024 +14.8, 2025 +7.4, 2026 +7.5. The weak years are
the choppy ones (2018, 2019), which is the known cost of trend following.
Add `--days 3650` to the headline command to reproduce it.

### 5.2 Parameter plateau (5 years, 5% band sweep)

The plateau below was measured before the live audit. The audit's band sweep
shows that changing the band from 1% to 10% moves CAGR by less than 0.2pp, so
the plateau conclusion is unaffected; the preset now uses the 2% band for
tracking accuracy.

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
| **Live-parity: 2% band, lag 1, next open, 1bp** | **26.4%** | **+16.9** | **29.4%** | **0.82** |
| Same, 5bp slippage | 25.3% | +15.8 | 29.5% | 0.79 |
| Same, 10bp slippage | 24.0% | +14.5 | 29.7% | 0.77 |
| One extra day of delay (lag 2, open fill, 5% band) | 29.2% | +19.0 | 29.4% | 0.87 |
| Pessimistic: lag 2 + close fill (5% band) | 19.3% | +9.8 | 37.2% | 0.67 |

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
| 20 Nov 2026 (0d) | 26.4% | 9.5% | +16.9 |
| 21 Oct 2026 (-30d) | 30.5% | 14.0% | +16.6 |
| 6 Oct 2026 (-45d) | 38.5% | 16.6% | +21.6 |
| 21 Sep 2026 (-60d) | 34.9% | 15.6% | +19.1 |

The shifted rows were measured with the 5% band; the 2% band changes the
headline by +0.1pp and does not change the pattern.

The excess is *largest* at the October high, so the result is not produced by
the November drawdown; if anything the chosen end date is the least favourable.

### 5.5 How much is "avoided 2022"?

A natural objection is that the whole edge is one lucky exit. Substituting
QQQ's actual 2022 return for the strategy's in 2022, and keeping every other
year, gives about **2.48x** over five years versus QQQ's 1.57x — roughly
**+10.4pp a year** even with zero credit for 2022. So the crash filter is not
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

The full parameter sweep was run in the exploratory build; this repo keeps
only the chosen setting, which is the point of the study.

One more alternative was ruled out before coding. Cross-sectional momentum on
today's Nasdaq-100 members looks spectacular — a controlled test of the same
12-1 top-10 rule returns **47.9% a year** on today's 97 members and **9.2%** on
a point-in-time S&P 500 universe that keeps delisted stocks, over the same
Feb 2013 - Feb 2018 window (SPY: 14.6%). The 38.7pp gap is survivorship bias,
not alpha. Index-level trend following has no such failure mode: it holds
actual funds, not a hand-picked list of survivors.

## 7. Honest caveats

1. **Risk budget, not alpha.** It holds 1-3x Nasdaq exposure, averaging
   **2.4x when invested** (1.9x unconditional; 16.6% of invested days at the 3x
   cap). Realised volatility is 36%. Its Sharpe is **1.6x QQQ's five-year
   Sharpe** (0.82 vs 0.50) and 1.2x over ten years (1.05 vs 0.86), but at
   ~1.5x QQQ's volatility. 2022 lost **12.5%**, not 15%.
2. **Concentration.** Three ETFs is not diversification: QQQ holds ~104
   stocks, the top ten are **~46%** of assets, and technology plus
   communication services are ~69%. At 2.4x the effective top-ten exposure is
   **~110% of equity** and Apple alone ~22%; at the 3x cap the top ten is
   ~137%. This is a leveraged mega-cap/AI bet.
3. **The window is kind, but the endpoint is not the driver.** 2022 gave a
   clean downtrend and 2023-2026 an exceptional rally. The 2018-2019 stretch
   shows the cost: **-1.8pp and -6.2pp**. Shifting the end date earlier raises
   the excess, so November 2026 is the least favourable end date.
4. **The full cycle is +10.96pp at 1bp, and the margin is thin.** A 26-year
   synthetic run (2000-2026, current preset) gives **20.36%/yr vs QQQ's 9.40%,
   +10.96pp, max drawdown 42.3% (2000-2003), Sharpe 0.71**. At 5bp: +10.01pp.
   With a 50bp financing spread: +10.30pp. With both: **+9.36pp — below the
   bar.** The 2000s returned roughly +5%/yr. The old "13.1% / +5.1pp / -83%"
   figure came from a different, slower variant (200-day, 25% vol target) and
   has been removed to avoid confusion.
5. **TQQQ inception is 2010.** Pre-2010 is synthetic, validated to 0.64pp/yr on
   the real-fund overlap. The synthetic series floors at $0.01, so the 2000-02
   share-count accounting is unreliable (the 26-year weight-drift statistic is
   an artifact); the return path is still useful.
6. **Daily reset and gap risk.** TQQQ returned +1.3% over these five years
   while QQQ returned +57%. At ~70% TQQQ, a -20% overnight gap is **-14% of
   equity in a day**; a -30% gap is -21%. FINRA warns that daily-reset
   leveraged ETFs are unsuitable for holding longer than one session.
7. **Fills are modelled.** Live-parity 1bp; 5bp gives +15.8pp and 10bp +14.5pp
   over five years; a deliberately pessimistic two-day-delay/close-fill case
   gives +9.8pp. TQQQ moved 0.87% on average in the first ten minutes after the
   open.
8. **Taxes are not modelled.** About 54 round trips and 170 resize fills a year
   create short-term gains and wash-sale exposure in a taxable account; a
   several-pp/yr drag would push the full-cycle excess below 10pp.
9. **Fund and index selection.** TQQQ is a surviving 3x fund and QQQ is a
   hindsight choice; the rule is not tested on SPY, IWM or global indices. BIL
   did not exist before 2007, so pre-2007 down-states earn 0%.
10. **Adjusted-close signal.** Yahoo's total-return adjustment factor varies
    within the 165-day window as dividends are paid, a small (~0.3% of SMA)
    look-ahead. It did not flip any tested signal, but it is not exactly zero.
11. **Daily whipsaw.** The plain daily 200-day rule switches ~7 times a year
    and 77% reverse within a month; the 165-day + 2% band is smoother (~9-10
    closed round trips a year) but still reacts a day late to a V-shaped crash.
12. **Publication decay.** The 2016 rule has been public for a decade. A 2026
    replication of the Gayed-Bilello rule reports the 2x rotation at 14.0%/yr
    vs 11.45% since 1988 — a much smaller edge than the original table.

## 8. Reproduce

```powershell
cargo build --release

# headline, five years
.\target\release\quant-trader.exe backtest --config configs\nasdaq_leveraged_trend.toml

# ten-year robustness
.\target\release\quant-trader.exe backtest --config configs\nasdaq_leveraged_trend.toml --days 3650

# full cycle, synthetic 3x before TQQQ existed
.\target\release\quant-trader.exe backtest --config configs\nasdaq_synthetic_20y.toml
.\target\release\quant-trader.exe backtest --config configs\nasdaq_synthetic_20y.toml --days 9500
```

The study configs pin `end_date = "2026-11-20"` so the window does not move
with the run date. `days = 1824` is the five-year window
(Nov 24, 2021 - Nov 20, 2026); `days = 7299` is the twenty-year window.
`--days` overrides still respect the fixed end date.

Numbers are from the 2026-11-23 run. Yahoo revises adjusted history, so
re-running can move a result by ~0.1pp and a few trades (drawdowns by a few
tenths); that is data revision, not a strategy change.

The backtester downloads daily adjusted closes from Yahoo Finance at run time;
nothing is pre-baked.

## 9. Code changes that make this measurable

- `src/config.rs`: `[backtest] benchmark` (default `SPY`) so results can be
  measured against QQQ; `lag_bars` to hide recent bars from the strategy;
  `fill_open` to execute at the next session's open; `end_date` for a
  reproducible window; `end_days_ago` for endpoint sensitivity;
  `synthetic_symbol` for tests before a fund existed.
- `src/backtest.rs`: benchmark series is fetched independently of the traded
  universe and used for the buy-and-hold line, drawdown and the yearly table;
  open-fill execution; synthetic daily-reset funds; drawdown dates.
- `src/types.rs`: one completed-bar rule (`Bar::is_complete`) shared by the
  live loop and preflight.
- `src/preflight.rs`: live data, freshness, corporate-action and target check.
- `src/sim.rs`: splits and dividends applied to the paper ledger.
- `configs/nasdaq_leveraged_trend.toml`: the live/5-year preset.
- `configs/nasdaq_synthetic_20y.toml`: the long-run research preset.

## 10. Five-year verdict

The objective is met on the stated window: **+16.9pp a year over QQQ, in every
complete year from 2022 to 2026, with a smaller drawdown than QQQ**. The
yearly edge ranges from +7.4 to +36.1 points; the aggregate clears the bar.
It is met by leveraging a trend filter, not by finding an uncorrelated alpha
source, and it would not have met the bar with 2x instead of 3x (+9.8pp over
five years).

The wider evidence is thinner than the five-year headline. Over the full cycle
(2000-2026) the same preset returns **20.36%/yr vs QQQ's 9.40%, +10.96pp, with
a 42.3% drawdown** at 1bp — but **+9.36pp** once 5bp slippage and a 50bp
financing spread are included. The five-year result is therefore above the
full-cycle average and in the better part of the strategy's historical range,
not a forecast. Anyone running this should size it as a satellite, expect a
30-50% drawdown in normal use and 40%+ in a 2000-style unwind, and should not
expect the last five years to repeat.

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
| Synthetic 3x QQQ | 30.50% | 39.81% | 0.92 |
| Real TQQQ | 29.86% | 40.03% | 0.91 |

The synthetic model is **0.64pp/yr** from the real fund, so the 20-year
extension is a fair test rather than a different strategy.

### 11.3 Result

```
Strategy return      : +11727.06%  (+26.99% a year)
QQQ buy & hold       :  +1526.51%  (+14.98% a year)
Excess vs QQQ        : +12.00% a year
Max drawdown         : 41.54%  (QQQ: 53.40%)
Drawdown window      : 2007-10-31 to 2009-04-20
Sharpe (annualised)  : 0.84
Closed trades        : 261
Orders / turnover    : 2,869 fills, 9,006x starting equity
Weight tracking      : avg 0.59% of equity off target, worst 6.42%
```

Yearly excess (strategy minus QQQ, points):

| 2007 | 2008 | 2009 | 2010 | 2011 | 2012 | 2013 | 2014 | 2015 | 2016 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| +14.4 | +14.0 | +13.6 | **-5.1** | **-20.3** | **-10.7** | +72.4 | +14.5 | **-2.6** | **-10.8** |

| 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| +82.8 | **-1.5** | **-5.3** | +22.9 | +29.3 | +20.1 | +37.4 | +16.5 | +9.0 | +8.7 |

Thirteen of twenty years beat QQQ. The losing years cluster where trend
following is supposed to lose: choppy, mean-reverting markets (2010-12, 2015-16,
2018-19). The **worst drawdown was the global financial crisis**:
October 2007 to April 2009, a 41.5% peak-to-trough loss, while QQQ fell 53%
over the whole cycle.

For comparison, the real **2x QLD** version over the same 20 years returns
+7.3pp a year with a 40.1% drawdown. **3x is what clears the +10pp bar; 2x
does not.**

### 11.4 Full cycle (2000-2026)

The 26-year synthetic run covers the dot-com crash and the GFC:

| Assumption | CAGR | Excess vs QQQ | Max DD |
|---|---:|---:|---:|
| 1bp, T-bill financing | **20.36%** | **+10.96** | 42.27% |
| 5bp | 19.41% | +10.01 | 43.11% |
| 1bp, +50bp financing spread | 19.70% | +10.30 | 42.29% |
| **5bp + 50bp financing** | **18.76%** | **+9.36** | **43.13%** |

The worst drawdown ran from **2000-11-20 to 2003-03-31**. The 2000s returned
roughly +5%/yr, with 2001 -16.8%, 2002 -16.3%, 2003 +45.5%, 2005 -21.3% and
2008 -27.7%. The strategy clears the +10pp bar at 1bp but **not** once 5bp
slippage and a 50bp financing spread are both charged. BIL did not exist before
2007, so the pre-2007 down-state earns 0% cash (conservative). The synthetic
fund's $0.01 floor makes the 2000-02 share-count accounting unreliable, so the
weight-drift statistic from this run is not meaningful.

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

All **54 unit tests pass**.

### 12.2 Tested on live data

`preflight` runs the live data path without trading:

```
PREFLIGHT | Leverage rotation (TQQQ 3x while QQQ > 165-day average, 40% volatility target, else BIL) | 1d bars | 3 symbols
now: 2026-11-23 02:56 UTC | history window: 270 days | warmup: 166 bars
data: local paper ledger + Yahoo Finance live prices
market: closed

QQQ       187 bars | last 2026-11-20 14:30 | 1.5 days old | close 608.45 | fresh
         corporate actions: dividend $0.7510 on 2026-09-21; $0.8130 on 2026-06-22; $0.7330 on 2026-03-23
         quote: 3236.3 min old
TQQQ      187 bars | last 2026-11-20 14:30 | 1.5 days old | close 41.20 | fresh
         corporate actions: dividend $0.1560 on 2026-09-23; $0.1710 on 2026-06-24; $0.0720 on 2026-03-25
         quote: 3236.3 min old
BIL       187 bars | last 2026-11-20 14:30 | 1.5 days old | close 91.59 | fresh
         corporate actions: dividend $0.3080 on 2026-11-02; $0.2630 on 2026-10-01; $0.2800 on 2026-09-01
         quote: 3236.3 min old

current target: 100.0% gross
  BIL        100.0%
paper account: equity $100000.00 | cash $100000.00 | 0 position(s)
PREFLIGHT: PASS
```

The quote age is expected over a weekend; during the session preflight fails
if a quote is more than 15 minutes old or the exchange reports a delay.

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
Actions : applied 5 corporate action(s)
SYMBOL  QTY  ENTRY  LAST
TQQQ    200  40.00  41.20
AFTER:  qty 200, avg_price 40, cash 50097
```

The 5 actions are the 2:1 split plus four quarterly dividends. Equity is
unchanged by the split; the dividends add $97 of cash.

### 12.4 Operational guards

- **Tracking error is bounded.** The preset uses a 2% rebalance band; measured
  drift is 0.69% of equity on average and 5.5% at worst, versus 2.0%/12.4% at
  the old 5% band, with the same return and about 9% more notional turnover.
- **Failed orders are retried.** Up to 3 retries per bar on the following
  polls, after re-reading positions from the broker. The research and the
  residual duplicate risk are in `docs/live_readiness_audit.md`.
- **The open is not missed.** While the market is closed the loop wakes every
  60 seconds, so the first decision lands within a minute of the open.
  Unit-tested (`closed_market_polls_at_least_every_minute`).
- **Cash-starved buys are logged.** `WARN ...: buy limited by cash, wanted ...`
  fires when a buy cannot reach its target.
- **Quote freshness is checked.** Preflight reports the age and exchange delay
  of each quote and fails during the session if it is stale or delayed.
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
   - require `PREFLIGHT: PASS`.
3. `.\target\release\quant-trader.exe replay --config configs\nasdaq_leveraged_trend.toml`
   - confirm the orders match the target.
4. Start `run` before 9:25 ET; while the market is closed the loop wakes every
   minute, so the first decision lands at the open.
5. `status` shows the account; `data/nasdaq_leveraged_trend/trades.csv` is the
   audit trail. Watch for `buy limited by cash` and rebalance-retry warnings.

### 12.6 Known limitations

- Yahoo's endpoint is unofficial and can rate-limit or change; the client
  retries, but a multi-hour outage means a missed daily signal.
- The sim does not model taxes, bid/ask beyond 1bp slippage, or market impact.
  TQQQ moved 0.87% on average in the first ten minutes after the open over the
  last 35 sessions, so a delayed start is much more expensive than 1bp.
- Dividends are credited on the ex-date rather than the pay date.
- Corporate actions rely on Yahoo reporting them within the 400-day window.
- A restart re-evaluates the latest completed bar; the 2% band limits the extra
  turnover, but it is not zero.
- The 20-year result uses a synthetic 3x fund before 2010; its 0.64pp error
  versus the real fund is the best available estimate of that assumption's cost.
  The synthetic series floors at $0.01, so 2000-02 share-count accounting is
  unreliable.
- Alpaca paper does not credit dividends **and does not apply splits**; its
  free feed is IEX-only (~2-4% of consolidated volume). The loop halts on a
  detected split in a held symbol. The sim broker is the more faithful test for
  this strategy; see `docs/live_readiness_audit.md`.
- The SMA/vol signal uses Yahoo's total-return adjusted closes. The adjustment
  factor varies within the window as dividends are paid, a small (~0.3% of the
  SMA) look-ahead that did not flip any tested signal but is not exactly zero.
- There is no client-order-ID idempotency. The retry logic relies on
  re-reading positions from the broker before each attempt.
- A real **cash** account would face T+1 settlement and free-riding rules; the
  sim and Alpaca paper are margin-enabled. This preset sells and buys on the
  same day.


