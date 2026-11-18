# Live paper test

Live market data, paper money. Nothing here can place a real order.

## Start

The US market opens at **9:30 AM Eastern**. Start a few minutes **before**
the open: the opening range strategy decides at 9:35 and trades badly if it
starts late. Open PowerShell and run:

```powershell
cd $env:USERPROFILE\Desktop\quant-trader
powershell -ExecutionPolicy Bypass -File docs\run-monday.ps1
```

Seven windows open, one per strategy. Each has its own $100,000 paper account.

| Window | Symbols | What to expect |
|---|---|---|
| `orb_stocks_5m` | about 100 S&P 500 stocks | At 9:35 it picks up to 20 stocks with unusual opening volume and trades each one; exits on stops, targets, or at 15:55 |
| `intraday_momentum_10` | 4 index ETFs + 6 large stocks | Buys when a symbol leaves its normal intraday range (checked every half hour); flat before the close |
| `vwap_10_1m` | the same 10 | Trades every minute, long above VWAP and short below; hundreds of orders a day |
| `core` | 19 ETFs | Rebalances about once a month; otherwise holds |
| `value_momentum_long` | S&P 500 | Holds about 50 stocks; rebalances about once a month |
| `intraday_ls_momentum_live_active` | about 100 S&P 500 stocks | Your momentum strategy, re-ranked every 30 minutes: a handful of trades through the day |
| `leverage_2x` | SSO or SHY | One position; changes only when SPY crosses its 200-day average |

Before the open each window shows `market is CLOSED - waiting`. At 9:30 it
prints `market is OPEN - trading`. Leave the windows open all day and keep
the computer awake.

## How to tell a window is alive

Every window prints a status line once a minute (every five minutes for
the monthly strategies), even when it has nothing to trade:

```
[10:14:02] running | equity $100,212.40 (+0.21% today) | 9 long, 6 short | 15 orders today | prices for 101/101 symbols
```

A strategy that holds its positions all day, or has finished its trades,
keeps printing this line. If the line stops appearing, the window really
has stopped: check for an error message at the bottom, and restart it with
the script (accounts are saved, so it carries on where it left off).

## Options

```powershell
# Rehearse first: replay the last session through the live code, no live trading
powershell -ExecutionPolicy Bypass -File docs\run-monday.ps1 -Rehearse

# Start every account again from a clean $100,000
powershell -ExecutionPolicy Bypass -File docs\run-monday.ps1 -Fresh

# Choose which strategies to run (names of files in configs\)
powershell -ExecutionPolicy Bypass -File docs\run-monday.ps1 -Strategies orb_stocks_5m,core
```

## Other strategies

Any preset in `configs\` can be added to `-Strategies`.

| Name | Trades | What it does |
|---|---|---|
| `orb_1m`, `orb_tqqq_1m` | Once a day at 9:35 | Opening range breakout on QQQ + SPY, or on TQQQ only |
| `vwap_1m` | Every minute | VWAP trend on QQQ + SPY only |
| `leverage_3x` | Rarely | Leverage rotation with the 3x S&P 500 fund |
| `trend_multi_asset_long` | Monthly | Trend following across 17 ETFs, no shorting |
| `profitability_long` | Monthly | The 20% of S&P 500 companies with the highest return on assets |
| `trend_sp500` | Daily, shortly after the open | Trend following across the S&P 500 |

## Check on it

In another PowerShell window:

```powershell
cd $env:USERPROFILE\Desktop\quant-trader
.\target\release\quant-trader.exe status --config configs\orb_stocks_5m.toml
```

Files written while it runs (replace `orb_stocks_5m` with the strategy name):

| File | Contents |
|---|---|
| `data\orb_stocks_5m\live.log` | Everything the window printed |
| `data\orb_stocks_5m\trades.csv` | Every fill: time, symbol, side, quantity, price, reason |
| `data\orb_stocks_5m\equity.csv` | Account value at every poll while the market is open |

## Stop

Press `Ctrl+C` in a strategy's window, or close the window. Positions and
cash are saved, so starting it again continues the same account.

The three intraday strategies close all their positions a few minutes before
16:00. When the market closes each window prints a `SESSION SUMMARY` line
with the day's profit or loss and the number of orders. The monthly
strategies only check every ten minutes, so their summary can appear up to
ten minutes after the close.

## What to look for

1. **Timing.** Do the opening-range orders appear at 9:35? Delays of more
   than a minute or two mean the free price feed is lagging.
2. **Warnings.** Lines starting with `WARN` mean a price request failed. An
   occasional one is harmless; a steady stream means Yahoo is rate-limiting.
3. **Flat at the close.** `status` after 16:00 should show `Positions: none`
   for the three intraday strategies.

## If something goes wrong

| Symptom | What to do |
|---|---|
| `running scripts is disabled on this system` | Use the full command above, including `-ExecutionPolicy Bypass` |
| `'core' is already running` | That strategy already has a window open. Close it first |
| Window stays on `market is CLOSED` after 9:30 | Check the computer's clock and internet connection; market holidays also show as closed |
| No status line for several minutes | The window has stopped. Note any error at the bottom, then start it again with the script |
| No orders from `orb_stocks_5m` by 9:40 | Look for `WARN` lines; if there are none, send the contents of `data\orb_stocks_5m\live.log` |
| Want to start over | Close the windows, then run the script with `-Fresh` |
