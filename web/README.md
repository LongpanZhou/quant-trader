# quant-trader web

A local Next.js portal for systematic strategies. The landing page is a
catalog; each strategy opens its own performance page at
`/strategies/<slug>/`.

The catalog and each strategy portal read static JSON from
`public/data/<slug>/<window>.json` and a catalog manifest at
`public/data/strategies.json`. No database is required for the portals.

The Backtest Lab is different: it is a local Next.js server route that builds a
TOML config, runs the repository's Rust binary and returns the report JSON. The
site is therefore no longer a static export; run it with `bun run start` after a
build.

## Run

```powershell
bun install
bun run dev      # http://localhost:3000
```

## Build

```powershell
bun run build
bun run start    # local production server, required by /api/backtest
```

The Rust binary at `../target/release/quant-trader.exe` must exist for
`/api/backtest`. Build it from the repository root with:

```powershell
cargo build --release
```

## Backtest lab

- `/lab` — edit an adjustable strategy's parameters, costs and benchmark, then run the Rust
  engine through `POST /api/backtest`.
- `/lab/custom` — write a `decide(ctx)` function. The code is compiled and run
  in a browser Web Worker with a 30-second timeout; it never reaches the server.
  `GET /api/prices` downloads Yahoo Finance bars on a daily or intraday interval
  (`1m`, `5m`, `15m`, `1h`, `1d`) and caches them locally for six hours.

The custom engine uses only data through bar `i`, fills at bar `i+1`'s open,
charges slippage on traded notional, and keeps the remainder in cash. See the
Data & limits section on the page for the exact execution model.

Intraday windows are capped by Yahoo Finance:

| Interval | Maximum history |
|---|---|
| 1 minute | 7 calendar days |
| 5 minutes | 59 calendar days |
| 15 minutes | 59 calendar days |
| 1 hour | 2 years |

The adjustable-strategy lab stays daily: 165/200-day trend filters need several years of
history. Intraday results are shown as window returns rather than annualised
CAGR, because annualising a two-day sample is not meaningful.

## Local data limits

- Yahoo adjusted prices embed splits and dividends. For daily bars, adjusted
  open/high/low are reconstructed by scaling raw OHLC by adjusted close ÷ close;
  this is a consistent approximation, not an official adjusted OHLC feed.
  Intraday bars use Yahoo's raw OHLC when an adjusted close is not published.
- Delisting is not modeled. The custom engine aligns on the intersection of
  available bars and ends at the last common bar. A point-in-time delisting feed
  would be needed for a survivorship-free stock universe.
- SEC/EDGAR financial statements are not in the local dataset. The engines are
  price-only and do not claim fundamental inputs.
- The intraday feed is short and limited by Yahoo (see above). Minute tests are
  for rule prototyping, not multi-year validation. Intraday timestamps are stored
  in UTC and displayed in New York time; intraday CSV exports use a `date_et`
  column.
- For a longer 1-minute study, `scripts/intraday_1m_backtest.py` uses a free
  2016-2026 third-party dataset stored under `data/intraday-hf/`. See the root
  README. It is separate from the website's Yahoo-only custom lab.
- Custom runs are long-only, with no taxes, commissions, borrow costs, margin
  interest or cash yield. They are research tools, not a broker.

## Refresh the data

From the repository root:

```powershell
.\scripts\export-web-data.ps1
```

This rebuilds the Rust binary and rewrites the strategy JSON files.

## What is on the page

- Strategy catalog with a sparkline and headline stats for each strategy
- Per-strategy portal with its own metadata, horizon set and benchmark
- Headline metrics and horizon switcher (5 / 10 / 20 / 26 years)
- Equity curve vs the strategy's benchmark, with a linear/log toggle
- Drawdown chart and worst drawdown episodes
- Yearly returns and monthly-return heatmap
- Trade count, win rate, profit factor and turnover
- The exact sizing rule
- The paper trail and counter-evidence
- A local backtest lab and a browser-only custom-strategy workspace

The 20- and 26-year windows for the Nasdaq strategies use the synthetic 3x QQQ
series from the Rust backtester; the 5- and 10-year windows use real TQQQ
prices. The S&P 500 variant uses real SSO prices.

## Add a strategy

1. Add `research/strategies/<slug>/bot.toml` (the Rust bot config).
2. Add its windows to `scripts/export-web-data.ps1` and run it.
3. Add an entry to `public/data/strategies.json` with its slug, tags, windows
   and paper ids.
4. Run `bun run dev`; the catalog and the new portal are generated from that
   manifest.
