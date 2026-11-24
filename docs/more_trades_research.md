# Expanding to more trades: research and tests

**Question.** The core Nasdaq strategy makes ~11 round trips and ~172 fills a
year. Can we add more trading opportunities without destroying the edge?

**Answer.** More trades is easy. More trades *with a net edge* is not. Ten
families were researched and tested. Only one passed: a **25% multi-asset trend
sleeve** alongside the Nasdaq core. It roughly doubles the round trips, cuts
the drawdown by 6–9 points, and slightly improves Sharpe — at the cost of
4–7pp of CAGR. Every intraday family is breakeven or negative at 5bp costs.

**Scope note.** This document is the research trail, not the shipped strategy.
The combo engine and the sleeve presets used for the expansion tests were
exploratory and have been removed. What remains in the repo is the core; the
tables here record what else was tried and why it was not promoted.

---

Numbers are from a 2026-11-23 run with `end_date = "2026-11-20"`. Yahoo
revises adjusted history, so re-runs can differ by ~0.1pp and a few trades
(drawdowns by a few tenths); that is data revision, not a strategy change.

## 1. Test matrix (all measured in this repo)

| Family | Period | Round trips | Return vs benchmark | Verdict |
|---|---|---:|---:|---|
| **Nasdaq core (baseline)** | 5y | 54 | **+16.9pp vs QQQ** | Best raw return |
| **95/2.5/2.5 max-trades** | 10y | **376** | **+17.4pp vs QQQ** | **Most trades, core edge** |
| **80/10/10 balanced** | 10y | **310** | **+13.6pp vs QQQ** | Lower DD, meaningful sleeves |
| **75/25 Nasdaq + multi-asset** | 5y | **98** | **+13.1pp vs QQQ** | Best 2-sleeve |
| 75/25 Nasdaq + multi-asset | 10y | **182** | **+12.0pp vs QQQ** | Lower DD |
| Trend on 100 stocks | 5y | **906** | −0.45pp vs SPY | Dilutes; biased universe |
| Sector trend (29 ETFs) | 5y | **421** | −5.63pp vs SPY | Dilutes |
| Multi-asset TSMOM (17 ETFs) | 5y | **306** | −8.11pp vs SPY | Trend drought |
| Momentum rotation (40 stocks) | 5y | **207** | +0.98pp vs SPY | Market-like |
| SPY/UPRO 3x trend | 5y | 31 | +0.25pp vs SPY, 48.5% DD | Worse risk |
| ORB QQQ/SPY (5m) | 28d | 40 | +1.54% at 1bp | −0.04% at 5bp |
| VWAP QQQ/SPY (5m) | 28d | **295** | +2.15% at 1bp | **−9.19% at 5bp** |
| ORB stocks in play (5m) | 28d | **377** | −0.82% at 1bp | Negative |
| Noise area SPY (5m) | 55d | 45 | +3.59% at 1bp | −0.07% at 5bp; −4.44% at 10bp |
| QQQ RSI-2 (1d) | 5y | 21 | +2.66%/yr vs 9.49% | Too little exposure |

Cost sensitivity of the intraday families (same trades, only slippage changes):

| Strategy | 1bp | 5bp | 10bp |
|---|---:|---:|---:|
| ORB QQQ/SPY (28d) | +1.54% | −0.04% | −2.03% |
| VWAP QQQ/SPY (28d) | +2.15% | −9.19% | −21.57% |
| Noise area SPY (55d) | +3.59% | −0.07% | −4.44% |

## 2. The expansion that works

The measured 75/25 allocation (exploratory combo build, since removed):

- **75%** Nasdaq core: QQQ/TQQQ/BIL, 165-day SMA, 40% vol target.
- **25%** multi-asset trend sleeve: TLT, GLD, DBC, UUP, EFA; 20/40-day
  channel breakout, volatility-sized, long-only.

| | 5 years | 10 years |
|---|---:|---:|
| Return | **22.61%/yr** | **30.67%/yr** |
| QQQ | 9.49% | 18.58% |
| Excess | **+13.12pp** | **+12.10pp** |
| Max drawdown | **23.13%** | **29.35%** |
| Sharpe | **0.86** | **1.08** |
| Round trips | **98** (19.6/yr) | **182** (18.2/yr) |
| Fills | 1,050 | 1,953 |

Versus the core alone (5y: 26.4%, 29.4% DD, 0.82 Sharpe, 54 trips; 10y: 37.4%,
38.3% DD, 1.05 Sharpe, 97 trips): **~2x the round trips, 4–7pp lower CAGR,
6–9pp lower drawdown, slightly higher Sharpe.**

### 2b. Three sleeves: how far the trade count can go

Adding a sector sleeve (XLK, XLF, XLE, XLV, XLI) on top of the multi-asset
sleeve extends the frontier. Allocation is core / multi-asset / sectors:

| Allocation | 5y CAGR | 5y excess | 5y DD | 5y Sharpe | 5y trips | 10y CAGR | 10y excess | 10y DD | 10y trips |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 100/0/0 core | 26.4% | +16.9 | 29.4% | 0.82 | 54 | 37.4% | +18.8 | 38.3% | 97 |
| **95/2.5/2.5** | **25.5%** | **+16.0** | **28.2%** | **0.82** | **204** | **36.0%** | **+17.4** | **36.8%** | **376** |
| 90/5/5 | 24.9% | +15.4 | 26.9% | 0.83 | 163 | 34.8% | +16.3 | 35.0% | 310 |
| **80/10/10** | **23.4%** | **+13.9** | **24.4%** | **0.85** | **166** | **32.1%** | **+13.6** | **31.5%** | **310** |
| 75/25 (2 sleeves) | 22.6% | +13.1 | 23.1% | 0.86 | 98 | 30.7% | +12.1 | 29.4% | 182 |
| 60/20/20 | 19.4% | +10.0 | 19.4% | 0.87 | 166 | — | — | — | — |

The trade count is set by the sleeves, not their size: even a 2.5% sleeve
opens and closes its five ETFs. That is why 95/2.5/2.5 gives **4x the core's
round trips (38/yr over 10y)** while keeping almost all of the core's return.
The 60/20/20 allocation sits exactly at the +10pp bar (+9.95pp), so 80/10/10 is
the meaningful-diversification limit.

Two cautions on reading the table. **The 95/2.5/2.5 row has more return because
it is 95% core, not because the sleeves add alpha** — its Sharpe (0.82) is the
same as the core's. And **the sector sleeve does not pass the correlation
test** (ρ 0.7-0.9 vs the 0.42 threshold); it is included only as a
trade-count/breadth add-on, capped at 5-10%. The multi-asset sleeve is the
only research-supported diversifier.

The trade-off is cost: 95/2.5/2.5 turns over 1,548x starting equity over 10y
(~155x/yr); at 5bp that is ~0.8%/yr of average equity, at 1bp ~0.15%/yr.

The multi-asset sleeve is the only expansion that passes the correlation test:
`SR_sleeve > ρ × SR_core`. Multi-asset trend has ρ ≈ 0–0.2 to equities; sector
ETFs (ρ 0.7–0.9) and cross-sectional stock momentum (ρ 0.8–0.95) fail it. The
sector sleeve in the 3-sleeve table is therefore a breadth/trade-count add-on,
not an alpha source.

## 3. Why the other expansions fail

### Correlated universes (sectors, 100 stocks, multi-asset TSMOM)

- Zarattini & Antonacci's own 31-ETF version: **7.7%/yr vs SPY 10.0%**,
  2005–2024; **5.85%** after realistic retail costs, 2,270%/yr turnover
  ([paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4857230),
  [independent replication](https://www.pastperformancelab.com/p/industry-trend-following-100-year-backtest)).
- More sector names exhaust the diversification benefit at **6–9 ETFs**;
  the other 20 add trades, not risk reduction.
- Multi-asset trend is a **diversifier**: AQR's 2010–2016 net result was
  **3.3%/yr, Sharpe 0.41** — not the century average — with ρ ≈ 0
  ([AQR](https://www.aqr.com/-/media/AQR/Documents/Insights/Journal-Article/AQR-JPM-Fall-2017.pdf)).
  Our 17-ETF test returned +1.37%/yr over the last 5 years.

### Cross-sectional stock momentum

Survivorship bias is the whole result: NDX top-10 momentum goes from
**~46% to 16.4%** with delistings and the drawdown from −41% to **−83%**
([Price Action Lab](https://www.priceactionlab.com/Blog/2020/06/survivorship-bias-cross-sectional-momentum)).
Our own controlled test: **47.9% vs 9.2%** on the same rule. Reject.

### Intraday (ORB, VWAP, noise area, stocks in play)

The edge per trade is smaller than the spread:

- ORB QQQ gross edge is **~$0.07/share**; independent replication puts
  breakeven at **~2.2¢/share** of entry slippage, with 2022 producing 38% of
  PnL ([replication](https://github.com/giovannibrusco/zarattini-2023-orb-qqq)).
- VWAP is **~0.9bp of equity per trade**; at 2bp/side an independent rebuild
  turns +671% into **−71%**
  ([rebuild](https://guanalyser.com/test-bench/vwap-trading-strategy)).
- Noise area is the best family, but pooled post-publication Sharpe is
  **~0.35**, not the in-sample 1.33
  ([audit](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7323419)).
- Stocks in play needs a full-universe 1-minute feed with consolidated volume;
  a liquid mega-cap proxy lost **73%**
  ([proxy test](https://quant4free.com/analysis/stocks-in-play-relvol-orb)).

### Event-driven and pairs

- Large-cap PEAD is **non-existent since 2006**; costs consume 70–100% of the
  small-cap version ([Martineau](https://www.emerald.com/cfr/article/11/3-4/613/1324916/Rest-in-Peace-Post-Earnings-Announcement-Drift),
  [Chordia et al.](https://www.tandfonline.com/doi/abs/10.2469/faj.v65.n4.3)).
- Pairs trading was ~11%/yr before 2002 and **largely unprofitable after**
  ([Do & Faff](https://onlinelibrary.wiley.com/doi/10.1111/j.1475-6803.2012.01317.x)).

### More frequent rebalancing

Direct test on the same rule: daily **5.92%** → weekly **5.04%** → monthly
**2.50%**; turnover falls 22.6x → 14.5x → 7.4x. Return falls faster than the
cost it saves. Faster signals are not the lever either: a 100-day SMA returned
**+4.8pp** vs the 165-day **+16.9pp**.

## 4. Recommendation

1. **The core is the only shipped preset.** An earlier exploratory build could
   raise the trade count with a second sleeve: 95/2.5/2.5 measured **37-38 round
   trips a year, +17.4pp over 10y, 36.8% max DD**; 80/10/10 measured **31 round
   trips, +13.6pp, 31.5% max DD**. That engine is not part of the repo. It is a
   trade-count tweak, not a new source of edge.
2. **Do not add** sector/stock momentum as a standalone, multi-asset TSMOM as
   a standalone, intraday ORB/VWAP, PEAD, pairs, or RSI-2.
3. **If you want the core's fills lower:** a 5% band cuts fills from 861 to
   516 over 5 years with the same return, at the cost of more tracking error
   (2.0% vs 0.69%).
4. **If you want more return:** the 50–60% vol-target variants (22–23%/yr
   full-cycle, 50–57% DD). That is leverage, not trade count.
5. **If you ever test intraday seriously:** require an all-in cost ≤2bp,
   a consolidated-volume feed, a pre-registered kill rule, and a 6-month
   forward record before sizing up. Expect ~0–5%/yr, not 20%.

## 5. Reproduce

The shipped core is what can be reproduced in this repo:

```powershell
.\target\release\quant-trader.exe backtest --config configs\nasdaq_leveraged_trend.toml
.\target\release\quant-trader.exe backtest --config configs\nasdaq_leveraged_trend.toml --days 3650
```

The expansion and intraday sweep configs were removed with their exploratory
engines. The tables above are the record of those tests; they are not claims
that the current code can rerun them.

## 6. Caveats

- The 28/55-day intraday tests are short samples; they show the cost boundary,
  not a definitive edge estimate.
- The 100-stock trend test uses today's S&P names (survivorship-biased); its
  return is an upper bound.
- The 75/25 combo's sleeve assets (TLT, GLD, DBC, UUP, EFA) start in 2002–2007,
  so the combo is tested over 10 years, not 20.
- All tests use 1bp slippage unless a 5/10bp variant is named; commissions and
  taxes are excluded.
