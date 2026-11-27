# quant-trader

A paper-trading bot for one simple rule: **own leveraged Nasdaq exposure only
while the Nasdaq-100 is trending up, and size it to a fixed risk level.**

It never places real-money orders.

**Dashboard (local):** `cd web && bun install && bun run dev` →
http://localhost:3000 (see [Website](#website)).

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
| 2021 | +55.0% | +27.4% | +27.6 |
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

### Trade statistics

| Window | Closed trades | Wins | Losses | Win rate | Per year | Profit factor |
|---|---:|---:|---:|---:|---:|---:|
| 5 years | 54 | 29 | 25 | **53.7%** | 10.8 | 4.16 |
| 10 years | 97 | 51 | 46 | **52.6%** | 9.7 | 5.18 |
| 20 years | 261 | 123 | 138 | **47.1%** | 13.1 | 5.05 |
| 26 years | 319 | 138 | 181 | **43.3%** | 12.3 | 4.96 |

A **closed trade** is a round trip: an entry and its exit. A fill is one order,
including volatility-target resizes, so there are many more fills than trades.
**Profit factor** is gross wins divided by gross losses.

Over the full 26-year test that is **319 round trips and 3,493 fills**; the
10-year real-TQQQ record is **97 round trips and 1,502 fills**.

The edge is not a high hit rate. Over the full cycle only 43% of trades win, but
winners are much larger than losers (profit factor about 4-5 across the windows).
That is normal for trend following: many small losses, a few large trend years.

## How it is implemented

The exact rule, as the code runs it:

```
sma  = 165-day simple moving average of QQQ close
vol  = standard deviation of the last 20 QQQ daily returns * sqrt(252)
trend = QQQ close > sma

if not trend:
    weight(BIL) = 1
else:
    exposure = min(0.40 / vol, 3.0)     # 1.0 if vol is zero
    if exposure <= 1:
        weight(QQQ) = exposure
        weight(BIL) = 1 - exposure
    else:
        w_tqqq = (exposure - 1) / 2
        weight(TQQQ) = w_tqqq
        weight(QQQ)  = 1 - w_tqqq
```

The signal is computed on the previous close and the order is filled at the
next open (`lag_bars = 1`, `fill_open = true`). Positions are only resized when
they drift more than 2% of equity from target.

| File | What it does |
|---|---|
| `src/strategy.rs` | The rule. `LeveragedIndex` computes the SMA and volatility, then `blend_exposure` splits exposure between QQQ and TQQQ. `SmaCross` remains only as a test fixture. |
| `src/config.rs` | Parses `config.toml`, checks the parameters, and verifies that QQQ, TQQQ and BIL are in `symbols`. |
| `src/backtest.rs` | Loads adjusted daily bars, builds the synthetic 3x series when requested, runs the event loop, applies lag/open fills and costs, and reports returns, drawdown, win rate and yearly results. |
| `src/engine.rs` | The live paper loop. Once per completed daily bar it fetches data, asks the strategy for targets, applies the 2% band, and sends orders. It also handles retries, stale data and corporate actions. |
| `src/sim.rs` | The local paper broker: cash, positions, fills, splits and dividends. |
| `src/alpaca.rs` | Optional Alpaca paper broker. The endpoint is hard-wired to paper trading. |
| `src/preflight.rs` | Checks data freshness, corporate actions and the current target without placing orders. |
| `src/yahoo.rs` | Downloads daily adjusted closes and corporate-action events. |
| `src/indicators.rs` | The SMA and standard-deviation helpers. |

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

## Website

The `web/` folder is a local Next.js portal for systematic strategies. The
landing page lists every strategy in `web/public/data/strategies.json`; each
one opens its own performance page with equity, drawdowns, yearly and monthly
returns, trade statistics, the exact rule and its paper trail.

The portals read static JSON. The **Backtest Lab** (`/lab`) is different: it is
a local Next.js API route that builds a TOML config and runs the Rust binary, so
the site is a local server rather than a static export. The custom-strategy
workspace (`/lab/custom`) runs user code in the browser, not on the server.

The catalog ships with the promoted Nasdaq rule plus two research variants:
the original S&P 500 2x rotation and a Nasdaq 3x trend without the volatility
target. They are website research entries, not live presets.

The lab can rerun any preset with different parameters, costs and benchmarks.
The custom workspace lets you write a `decide(ctx)` function and run it on
daily or intraday Yahoo bars in a browser worker. Intraday history is short
because of Yahoo's limits: 1-minute bars cover at most 7 days, 5/15-minute bars
59 days, and hourly bars 2 years. The preset strategies stay daily because their
165–200-day averages need more history than the intraday feed provides.

```powershell
cd web
bun install
bun run dev      # http://localhost:3000

# local production server (the lab needs /api/backtest)
bun run build
bun run start
```

The Backtest Lab also needs the Rust binary:

```powershell
cargo build --release
```

Regenerate the JSON after changing the strategy or refreshing the data:

```powershell
.\scripts\export-web-data.ps1
```

The site is not deployed anywhere. Run it locally; if you later want to publish
it, choose the host and URL first.

## Intraday 1-minute research

The repo can also run the main rule on 1-minute bars from a free third-party
dataset. It is kept in `data/intraday-hf/`, which is gitignored; the raw data is
not redistributed here.

Source: [Syncster Historical Market Data](https://huggingface.co/datasets/syncster-data/historical-market-data)
on Hugging Face. The dataset is free research data with license "other", not an
official exchange feed. It covers 2016-2026. QQQ/TQQQ minute prices are adjusted
to total return with Yahoo Finance daily `adjclose / close` factors; BIL's 2017
reverse split is repaired before adjustment.

The free archive starts in 2016, so it can support a 5- or 10-year study. A
26-year 1-minute archive is not available from Yahoo or this free dataset; that
needs a paid historical minute feed.

QQQ itself launched on **1999-03-10**. The earliest 1-minute coverage from the
main vendors is:

| Vendor | 1-minute start | Access |
|---|---|---|
| Kibot | 1999-03-10 | paid |
| EODData | 1999-03-10 | paid |
| Portara | 1999-03-11 | paid |
| FirstRateData | 2000-01-03 | paid |
| MarketParquet | 2000-01-03 | paid |

A 26-year window ending 2026-11-25 starts **2000-11-25**, so the paid archives
cover it. The free feeds do not.

Kibot's live quote for the exact three-symbol order (1-minute, regular session,
split+dividend adjusted, full history) is **$145** for QQQ + TQQQ + BIL
(439 MB, 27.74 years). QQQ alone is **$99** (232 MB). TQQQ did not exist before
2010-02-11 and BIL before 2007-05-30, so the earlier years still need the same
synthetic 3x/T-bill treatment used by the 26-year daily study.

```powershell
pip install -r scripts/requirements-intraday.txt
python scripts/intraday_1m_backtest.py --download
# defaults: 2021-10-25 .. 2026-10-23, 2% band, 1 bp slippage
# add --sensitivity for band and slippage tables
```

The same rule, same 5-year window, 1 bp slippage:

| Decisions | Bars | CAGR | vs QQQ | Max DD | Sharpe | Fills | Turnover |
|---|---:|---:|---:|---:|---:|---:|---:|
| Every 1 minute | 487,658 | **20.20%** | +6.10pp | 39.19% | 0.70 | 2,352 | 1,187x |
| Once per day | 1,255 | **31.56%** | +17.60pp | 29.29% | 0.96 | 808 | 212x |
| Rust daily engine (same window) | 1,253 | **29.92%** | +16.07pp | 29.35% | 0.91 | 855 | 224x |

The Python daily run is within about 1.6pp of the Rust engine, which validates
the simulator. The 1-minute version is clearly worse: the slow 165-day filter
whipsaws when it is evaluated every minute, and 1,187x turnover makes costs
matter. At 0 bp slippage the 1-minute CAGR is 22.20%; at 5 bp it falls to
12.56%. The daily rule remains the right frequency.

The same free archive also supports a longer **9.8-year** test
(2017-01-03 to 2026-10-23, 958,945 bars): 1-minute decisions returned
**31.41% CAGR** with a **40.17% drawdown** and **8,161x turnover**, versus
**32.38% / 38.56% / 1,010x** for daily decisions. The 1-minute version gets
closer over the longer window, but it still has the deeper drawdown and eight
times the turnover, so the cost and risk conclusions do not change.

A 26-year 1-minute test cannot be built from this free archive: it starts in
2016. The exact QQQ 1-minute history back to 1999/2000 is a paid dataset
(MarketParquet about $79 one-time, Portara, FirstRateData, Kibot or EODData).

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
web/       Next.js dashboard and exported JSON
scripts/   web-data export and 1-minute research
config.toml  default config (same as the live preset)
```
