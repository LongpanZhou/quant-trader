# quant-trader

An automatic quantitative trading system in Rust. It watches **real, live US
stock prices**, runs a rule-based strategy on them, and trades **paper money
only** — it has no code path that can place a real-money order.

## Quick start

```powershell
cd $env:USERPROFILE\Desktop\quant-trader
cargo build --release

.\target\release\quant-trader.exe backtest   # test the strategy on recent real history
.\target\release\quant-trader.exe run        # start trading (leave it running)
.\target\release\quant-trader.exe replay     # rehearse: live code over the latest session's real prices
.\target\release\quant-trader.exe status     # account, positions, P&L (any time)
.\target\release\quant-trader.exe reset      # wipe the sim account and start over
```

It works immediately with no account or API key. The loop only trades during
the US regular session (9:30–16:00 Eastern, Mon–Fri); outside it, it waits.

Each strategy has a ready-made preset in `configs/`. Pick one with `--config`:

```powershell
.\target\release\quant-trader.exe backtest --config configs\connors_rsi2.toml
.\target\release\quant-trader.exe run      --config configs\connors_rsi2.toml
```

Every config file gets its own paper account and logs under `data\<config name>\`,
so several strategies can run side by side in separate terminals.

## Two backends

Set `broker` in `config.toml`:

| `broker`  | Market data                  | Paper account                         | Setup            |
|-----------|------------------------------|---------------------------------------|------------------|
| `"sim"`   | Yahoo Finance (live, keyless) | Built-in ledger in `data/sim_ledger.json` | none            |
| `"alpaca"`| Alpaca real-time IEX feed    | Alpaca paper account (realistic order simulator, web dashboard) | free API keys |

**Alpaca** is the better option once you want more realism: an official,
documented API, real-time data, and fills simulated against the live quote.
To use it:

1. Sign up at <https://alpaca.markets> (free, paper-only accounts are available).
2. In the dashboard switch to **Paper Trading** and generate API keys.
3. Set the keys, then set `broker = "alpaca"`:

```powershell
$env:APCA_API_KEY_ID = "PK..."
$env:APCA_API_SECRET_KEY = "..."
```

The Yahoo endpoint used by `sim` is unofficial: fine for paper trading, but it
can rate-limit or change without notice.

## How it trades

Every `poll_seconds` the loop, for each symbol:

1. Pulls the latest bars and marks open positions to the live price.
2. **Risk exits** – sells if the position hit its stop-loss or take-profit.
3. **Strategy** – once per newly completed bar, asks the strategy for
   buy / sell / hold.
4. **Sizing** – a buy uses `position_pct` of account equity (whole shares),
   capped by cash and by `max_positions`. Long-only, market orders.

Stale data (halts, holidays, feed gaps) is never traded on.

## Strategies

| Preset (`configs/`) | Bars | Source | Rule in one line |
|---|---|---|---|
| `sma_cross` | 5m | textbook | Buy when the fast average crosses above the slow one; sell when it drops below |
| `rsi_reversion` | 5m | textbook | Buy RSI(14) oversold; sell when it recovers |
| `breakout` | 5m | textbook (Donchian) | Buy a new 40-bar high; sell a new 20-bar low |
| `intraday_momentum` | 5m | Zarattini, Aziz & Barbon (2024) | Buy SPY/QQQ when price leaves its normal intraday range; trail a stop at max(range edge, VWAP); flat before the close |
| `connors_rsi2` | 1d | Connors & Alvarez (2008) | Buy a 2-day RSI < 5 pullback in a stock above its 200-day average; sell above the 5-day average |
| `bollinger` | 1d | Chan (2013) | Buy 2 standard deviations below the 20-day average; sell back at the average |
| `monthly_trend` | 1d | Faber (2007) | Hold each of 5 asset-class ETFs only while above its 10-month average |
| `momentum_rotation` | 1d | Clenow (2015) | Weekly, hold the 8 stocks with the strongest volatility-adjusted 90-day momentum |
| `trend_stocks` (also the default `config.toml`) | 1d | Zarattini & Antonacci (2024); Zarattini, Pagani & Wilcox (2025) | Buy 20-day channel breakouts, trail a stop at the 40-day lower band, size positions by inverse volatility, park unused capital in SPY while SPY is above its 200-day average |
| `trend_sectors` | 1d | Zarattini & Antonacci (2024) | The same trend rules on 29 sector and industry ETFs, unused capital in cash |

| `vwap_1m` | 1m | Zarattini & Aziz (2023) | Every minute: long QQQ/SPY above the session VWAP, short below it, flat before the close |
| `orb_1m` | 1m | Zarattini & Aziz (2023) | Opening range breakout: one trade per symbol per day in the direction of the first 5 minutes, tight stop, 10x target, flat before the close |
| `orb_tqqq_1m` | 1m | Zarattini & Aziz (2023) | The same opening range breakout on the 3x Nasdaq fund (TQQQ) |
| `leverage_2x` | 1d | Gayed & Bilello (2016) | Hold the 2x S&P 500 fund (SSO) while SPY is above its 200-day average, otherwise short-term Treasuries |
| `leverage_3x`, `leverage_nasdaq_3x` | 1d | Gayed & Bilello (2016) | The same rule with the 3x S&P 500 fund (UPRO) or the 3x Nasdaq fund (TQQQ) |
| `leverage_3x_voltarget` | 1d | Gayed & Bilello (2016); Moreira & Muir (2017) | In an uptrend, blend SPY and UPRO to aim for 20% volatility |
| `trend_multi_asset`, `trend_multi_asset_long` | 1d | Moskowitz, Ooi & Pedersen (2012); Hurst, Ooi & Pedersen (2017) | Trend following across 17 ETFs (stocks, bonds, commodities, currencies): long what has been rising, short or flat what has been falling, sized by volatility |
| `value_momentum`, `value_momentum_long` | 1d | Asness, Moskowitz & Pedersen (2013) | Rank S&P 500 stocks on one-year momentum and five-year cheapness; hold the best 10% (and optionally short the worst 10%) |
| `profitability`, `profitability_long` | 1d | Novy-Marx (2013) | Hold the 20% of S&P 500 companies with the highest return on assets, from SEC filings |
| `core` | 1d | combination | 50% leverage rotation (2x S&P 500) + 50% multi-asset trend following |
| `orb_stocks_5m` | 5m | Zarattini, Barbon & Aziz (2024) | Opening range breakout on "stocks in play": of about 100 S&P 500 stocks, trade the 20 with the most unusual opening volume |
| `intraday_momentum_10`, `vwap_10_1m` | 5m / 1m | as above | Intraday momentum and VWAP trend across ten symbols (four index ETFs, six large stocks) |
| `trend_sp500` | 1d | same as `trend_stocks` | The trend rules across the whole S&P 500, holding up to 40 of the strongest trends |
| `ls_momentum` | 1d | Jegadeesh & Titman (1993) | Monthly: long the strongest 10% of the S&P 500, short the weakest 10% |
| `earnings` | 1d | Ball & Brown (1968); Bernard & Thomas (1989) | Reads each company's quarterly report from SEC EDGAR; the next day goes long a strongly positive profit surprise and short a strongly negative one, 20% of the account each |
| `combo` | 1d | — | 50% trend + 30% long/short momentum + 20% RSI(2) pullbacks on one account |

**Short selling.** Portfolio strategies can return negative weights. A short
adds its proceeds to cash and is marked to market as a liability; total short
exposure may not exceed account equity. Backtests charge a borrow fee
(`risk.short_borrow_pct`).

**Large universes.** `symbols_file` adds symbols from a file
(`universes/sp500.csv`, one `SYMBOL,CIK` per line). Prices download in
parallel, and in live trading daily bars for stocks that are not held are
re-fetched at most hourly.

**Combining strategies.** `kind = "combo"` runs several strategies as parts
of one account; see `configs/combo.toml`. Each part gets an `allocation`, and
the parts' target weights are added per symbol.

**Financial reports.** The earnings strategy pulls quarterly net income from
the SEC's free EDGAR API (cached in `data/cache/edgar`) and scores each report
by how far profit departed from the company's own year-over-year pattern.
It works from the numbers in the filing, not the text, and from the filing
date, which is often days after the company's press release.

**Flat before the close.** `risk.flatten_before_close_minutes` makes the live loop close every position and stop trading that many minutes before the exchange's real closing time (half-days included), whatever the strategy says. The 1-minute presets set it.

**Long intraday history.** The live price source keeps only about 60 days of
5-minute candles. Adding `--source dukascopy` to a backtest reads years of
1-minute history from Dukascopy's public datafeed instead (no key). It has
SPY, QQQ and large US stocks, regular session only. The first run is slow,
because the feed throttles downloads (five years of one symbol takes over an
hour); everything is kept in `data/cache/dukascopy`, so later runs are quick.
Prices are quotes for Dukascopy's contract on the stock, not exchange trades,
the volume is Dukascopy's own, and prices are not adjusted for stock splits,
so use it for SPY and QQQ and be wary of single stocks.

```powershell
.\target\release\quant-trader.exe backtest --config configs\orb_5m.toml --source dukascopy --days 1825
```

**Replay.** `replay` feeds the latest session's recorded bars, one at a time,
through the same code that trades live, using a throwaway account in
`data/<config name>-replay/`. Use it to rehearse a strategy before the open.

The trend strategy is a portfolio strategy: it outputs a target weight for
every symbol and the engine moves the account towards those weights, only
resizing a position when it drifts outside a tolerance band (to limit trading
costs). It is a combination of published rules, not a replication of one paper.

Departures from the sources: nothing uses leverage on the long side, the
per-symbol strategies and the intraday momentum strategy are long-only (the
paper also shorts and uses leverage), pairs trading from Chan's book is not
included, and momentum rotation uses equal position sizes instead of the
book's volatility-based sizing.

Daily-bar strategies decide on the previous day's close and trade shortly
after the next open. Leave them running through the open, or start them any
time during the session.

## Output files (`data/<config name>/`)

- `sim_ledger.json` – cash and positions of the sim account (survives restarts)
- `trades.csv` – every fill: time, symbol, side, qty, price, reason
- `equity.csv` – account equity at every poll while the market is open

## Code map

| File | Purpose |
|------|---------|
| `src/main.rs` | CLI |
| `src/config.rs` | `config.toml` schema and validation |
| `src/engine.rs` | live trading loop, logging, `status` |
| `src/strategy.rs` | `Strategy` trait + all strategies, the combiner |
| `src/dukascopy.rs` | Multi-year 1-minute history for backtests |
| `src/edgar.rs` | SEC EDGAR financial reports and the earnings-surprise score |
| `src/indicators.rs` | SMA, standard deviation, RSI, linear regression |
| `src/backtest.rs` | historical simulation and statistics |
| `src/backend.rs` | common interface over the two backends |
| `src/sim.rs` / `src/yahoo.rs` | local ledger / Yahoo data |
| `src/alpaca.rs` | Alpaca paper trading + data |

To add a strategy: implement `Strategy` in `strategy.rs`, add a variant to
`StrategyConfig` in `config.rs`, and wire it up in `strategy::build`.

Run the tests with `cargo test`.

## Caveats

- This is an educational paper-trading system, not financial advice. The
  bundled strategies are textbook examples and are not expected to be profitable.
- Backtest fills are idealised (bar close + slippage, no commissions, no
  liquidity limits); real results would be worse.
- The 40-stock presets use today's large companies, i.e. stocks already known
  to have done well. That flatters both the strategy and the buy-and-hold
  numbers in multi-year backtests (survivorship bias).
- The S&P 500 file lists today's members only, so every S&P 500 backtest
  picks from companies already known to have survived and grown. Results on
  it are optimistic, most of all for strategies that buy past winners.
- Yahoo keeps about 29 days of 1-minute history, so 1-minute backtests cover
  roughly a month. Very active strategies are dominated by trading costs:
  check how the result changes with `risk.slippage_bps`.
- The value + momentum result is the one most inflated by the S&P 500 list:
  a stock that fell for five years and is still in the index today is, by
  construction, one that recovered. Stocks that kept falling were removed
  from the index and are missing from the test.
- Daily bars are dividend-adjusted (total return), so dividends count for
  both the strategy and buy-and-hold. Intraday bars are not adjusted.
- The leverage presets get their leverage from leveraged ETFs. Those funds
  can lose most of their value in a crash; the 3x funds did not exist in
  2008, so their backtests have never seen one.
- Yahoo only serves about 59 days of 5-minute history, so intraday backtests
  cover a very short window. Alpaca provides years of intraday history.
