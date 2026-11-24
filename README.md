# quant-trader

A paper-trading bot for one simple rule: **own leveraged Nasdaq exposure only
while the Nasdaq-100 is trending up, and size it to a fixed risk level.**

It never places real-money orders.

## The idea

- **Trend:** if QQQ is above its 165-day average, be invested. If not, hold
  T-bills (BIL).
- **Size:** aim for 40% yearly volatility.
  - Calm market: up to 3x exposure through TQQQ.
  - Normal market: a mix of QQQ and TQQQ.
  - Rough market: less than 1x, with the rest in BIL.
- **Timing:** check once a day after the close, trade at the next open.
- **Churn control:** only rebalance when 2% off target.

QQQ is the Nasdaq-100 ETF. TQQQ is a 3x daily Nasdaq-100 ETF. BIL is T-bills.

## Performance

All periods end 20 November 2026. Headline and cost-table returns are
annualised; the yearly tables are calendar-year returns. Figures use 1bp
slippage unless stated, and the benchmark is QQQ total return.

### Headline

| Period | Strategy | QQQ | Excess | Max drawdown | Sharpe | Round trips |
|---|---:|---:|---:|---:|---:|---:|
| 5 years | **26.4%** | 9.5% | **+16.9pp** | 29.4% (QQQ 35.1%) | 0.82 | 54 |
| 10 years | **37.4%** | 18.6% | **+18.8pp** | 38.3% (QQQ 35.1%) | 1.05 | 97 |
| 20 years (synthetic) | **27.0%** | 15.0% | **+12.0pp** | 41.5% (QQQ 53.4%) | 0.84 | 261 |
| 26 years (synthetic) | **20.4%** | 9.4% | **+11.0pp** | 42.3% (QQQ 73.0%) | 0.71 | 319 |

TQQQ started in 2010. The 20- and 26-year tests use a synthetic 3x QQQ series
for the whole window, including after 2010, to keep one consistent price path.
The model was checked against real TQQQ over 2010-2026: 30.5% vs 29.9% a year.

### Versus Nasdaq indexes, annualised

| Period | Strategy | QQQ (total return) | Nasdaq-100 price | Nasdaq Composite price |
|---|---:|---:|---:|---:|
| 5 years | **26.4%** | 9.5% | 8.9% | 7.4% |
| 10 years | **37.4%** | 18.6% | 17.8% | 15.4% |
| 20 years | **27.0%** | 15.0% | 14.0% | 11.7% |
| 26 years | **20.4%** | 9.4% | 8.4% | 7.9% |

QQQ is the fair benchmark because it includes dividends. The two Nasdaq
indexes are price-only, so the gap there is overstated by roughly the dividend
yield.

### Year by year: real TQQQ

| Year | Strategy | QQQ | Difference |
|---|---:|---:|---:|
| 2016 | +0.5% | +0.0% | +0.4 |
| 2017 | +113.9% | +32.7% | +81.2 |
| 2018 | -2.0% | -0.1% | -1.8 |
| 2019 | +32.8% | +39.0% | -6.2 |
| 2020 | +71.0% | +48.4% | +22.6 |
| 2021 | +55.3% | +27.4% | +27.8 |
| 2022 | -12.5% | -32.6% | +20.0 |
| 2023 | +90.8% | +54.9% | +35.9 |
| 2024 | +40.3% | +25.6% | +14.8 |
| 2025 | +28.1% | +20.8% | +7.4 |
| 2026 | +6.9% | -0.6% | +7.5 |

2016 is a 25-day stub; 2026 ends 20 November.

### Year by year: full cycle, synthetic 3x

| Year | Strategy | QQQ | Difference |
|---|---:|---:|---:|
| 2000 | +0.0% | -16.4% | +16.4 |
| 2001 | -16.8% | -33.3% | +16.6 |
| 2002 | -16.3% | -37.4% | +21.0 |
| 2003 | +45.5% | +49.7% | -4.2 |
| 2004 | +10.3% | +10.5% | -0.3 |
| 2005 | -21.3% | +1.6% | -22.9 |
| 2006 | +16.1% | +7.1% | +9.0 |
| 2007 | +33.3% | +19.0% | +14.3 |
| 2008 | -27.7% | -41.7% | +14.0 |
| 2009 | +68.3% | +54.7% | +13.6 |
| 2010 | +15.0% | +20.1% | -5.1 |
| 2011 | -16.8% | +3.5% | -20.3 |
| 2012 | +7.4% | +18.1% | -10.7 |
| 2013 | +109.1% | +36.6% | +72.4 |
| 2014 | +33.7% | +19.2% | +14.6 |
| 2015 | +6.8% | +9.4% | -2.6 |
| 2016 | -3.7% | +7.1% | -10.8 |
| 2017 | +115.5% | +32.7% | +82.9 |
| 2018 | -1.7% | -0.1% | -1.6 |
| 2019 | +33.7% | +39.0% | -5.2 |
| 2020 | +70.6% | +48.4% | +22.2 |
| 2021 | +56.4% | +27.4% | +28.9 |
| 2022 | -12.5% | -32.6% | +20.1 |
| 2023 | +92.3% | +54.9% | +37.5 |
| 2024 | +42.0% | +25.6% | +16.5 |
| 2025 | +29.8% | +20.8% | +9.0 |
| 2026 | +8.1% | -0.6% | +8.7 |

2000 is a 28-day stub; 2026 ends 20 November. From 2010 onward this table still
uses the synthetic series, so a few years differ slightly from the real-TQQQ
table.

### Cost sensitivity, 26-year window

| Assumption | CAGR | Excess vs QQQ | Max drawdown |
|---|---:|---:|---:|
| 1bp slippage, T-bill financing | **20.4%** | **+11.0pp** | 42.3% |
| 5bp slippage | 19.4% | +10.0pp | 43.1% |
| 1bp + 50bp financing spread | 19.7% | +10.3pp | 42.3% |
| 5bp + 50bp financing spread | 18.8% | +9.4pp | 43.1% |

## Which research paper it follows

The strategy is closest to **Gayed & Bilello (2016), "Leverage for the Long
Run"**: hold leveraged equity exposure while the index is above a long moving
average, and hold T-bills below it. The volatility sizing comes from a separate
literature.

| Design choice | Source |
|---|---|
| Hold the index above a long moving average; T-bills below | [Faber (2007)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=962461); [Gayed & Bilello (2016)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2741701) |
| Use a daily-reset 3x fund as the risk asset | [Gayed & Bilello (2016)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2741701) |
| Scale exposure down when trailing volatility is high | [Moreira & Muir (2017)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2659431); [Zarattini & Antonacci (2024)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4857230) |
| 165-day SMA and 40% vol target | Calibrated in this repo; not a published parameter set. The 3x cap is TQQQ's own leverage. |
| 2% rebalance band | Measured here (tracking error vs turnover); not from a paper |
| Close-to-next-open execution | Implementation choice to match the live loop; not from a paper |

That distinction matters. The *family* of rules is published; the exact
parameters are local choices, selected on this data. The closest independent
Nasdaq test we found is [Nygård & Liukko (2026)](https://diva-portal.org/smash/get/diva2:2077998/FULLTEXT01.pdf),
a Linköping thesis covering 2001-2026. It finds the same shape: 3x plus a
200-day filter plus an implied-volatility filter, about 22% a year with a -65%
drawdown. That is roughly buy-and-hold's 21% return with a much smaller
drawdown, not a new source of alpha.

The case is not one-sided: [Cederburg et al. (2020)](https://www.lehigh.edu/~xuy219/research/COWY.pdf)
find that volatility management does not systematically beat unmanaged
portfolios out of sample, and [Massaad et al. (2024)](https://arxiv.org/abs/2412.14361)
find that published trend results weaken under robust testing.

### What else was tested

| Family | Examples | Research | Verdict |
|---|---|---|---|
| Trend + leverage | 2x/3x S&P, 3x Nasdaq, vol target | Faber; Gayed & Bilello; Moreira & Muir | The current rule evolved from this |
| Intraday | VWAP, opening range, stocks in play | Zarattini & Aziz; Zarattini et al. | Rejected: costs erase the edge |
| Cross-sectional | momentum, value, profitability, earnings | Jegadeesh & Titman; Asness et al.; Novy-Marx; Ball & Brown | Rejected: survivorship, correlation or decay |
| Diversified trend | multi-asset, sectors, S&P 500 | Moskowitz et al.; Hurst et al.; Zarattini & Antonacci; Faber | Rejected standalone: dilutes the Nasdaq edge |
| Textbook | SMA, RSI, Bollinger, breakout | Textbook | Removed; SMA kept for tests |
| Combinations | core, combo | None | Removed: complexity; mixed results |

The full table, with each strategy from the old preset list, its rule and its
paper, is in [the strategy research map](docs/strategy_research_map.md).

## Run it

```powershell
cargo build --release

.\target\release\quant-trader.exe backtest    # five-year test
.\target\release\quant-trader.exe preflight   # check data and today's target
.\target\release\quant-trader.exe run         # start the paper loop
```

`status`, `replay` and `reset` work the same way. No account or API key is
needed. Alpaca paper trading is optional.

Long-run tests:

```powershell
.\target\release\quant-trader.exe backtest --days 3650
.\target\release\quant-trader.exe backtest --config configs\nasdaq_synthetic_20y.toml
.\target\release\quant-trader.exe backtest --config configs\nasdaq_synthetic_20y.toml --days 9500
```

## Read more

- [The study](docs/nasdaq_leveraged_trend.md) - why 165 days, why 40%, the
  parameter sweep, drawdown dates, benchmark comparison and caveats.
- [Live-readiness audit](docs/live_readiness_audit.md) - look-ahead checks,
  execution lag, tracking error, corporate actions.
- [More-trades research](docs/more_trades_research.md) - what else was tried
  and rejected.
- [Strategy research map](docs/strategy_research_map.md) - the old preset
  list, grouped by family, with its rule and source paper.

## Keep in mind

- **This uses leverage.** A fast 30% Nasdaq drop can become a 40%+ account drop before the trend filter exits.
- **The five-year window was kind.** The full-cycle result is the better guide.
- **Costs matter.** The edge is about 9pp after realistic costs, not 17pp.
- **Paper only.** Not investment advice.

## Files

```
src/       backtester, live loop, paper broker, data feeds, strategy
configs/   live/5-year preset and 20-year research preset
docs/      full study, audit, research map, expansion research
config.toml  default config (same as the live preset)
```
