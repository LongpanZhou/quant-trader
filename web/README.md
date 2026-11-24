# quant-trader web

A local Next.js portal for systematic strategies. The landing page is a
catalog; each strategy opens its own performance page at
`/strategies/<slug>/`.

The site reads static JSON from `public/data/<slug>/<window>.json` and a
catalog manifest at `public/data/strategies.json`. No database or API server is
required.

## Run

```powershell
bun install
bun run dev      # http://localhost:3000
```

## Build

```powershell
bun run build    # static site in out/
```

## Refresh the data

From the repository root:

```powershell
.\scripts\export-web-data.ps1
```

This rebuilds the Rust binary and rewrites the four JSON files.

## What is on the page

- Strategy catalog with a sparkline and headline stats for each strategy
- Per-strategy portal with its own metadata, horizon set and benchmark
- Headline metrics and horizon switcher (5 / 10 / 20 / 26 years)
- Equity curve vs the strategy's benchmark, with a linear/log toggle
- Drawdown chart and worst drawdown episodes
- Yearly returns and monthly-return heatmap
- Trade count, win rate, profit factor and turnover
- The exact sizing rule and a file-by-file code map
- The paper trail and counter-evidence

The 20- and 26-year windows for the Nasdaq strategies use the synthetic 3x QQQ
series from the Rust backtester; the 5- and 10-year windows use real TQQQ
prices. The S&P 500 variant uses real SSO prices.

## Add a strategy

1. Add a config in `web/strategies/` (or use an existing preset).
2. Add its windows to `scripts/export-web-data.ps1` and run it.
3. Add an entry to `public/data/strategies.json` with its slug, tags, windows
   and paper ids.
4. Run `bun run dev`; the catalog and the new portal are generated from that
   manifest.
