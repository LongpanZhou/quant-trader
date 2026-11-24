# quant-trader web

A static Next.js dashboard for the Nasdaq leveraged-trend strategy.

It reads four JSON files from `public/data/` (`5y`, `10y`, `20y`, `26y`) that
are produced by the Rust backtester. No database or API server is required.

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

- Headline metrics and horizon switcher (5 / 10 / 20 / 26 years)
- Equity curve vs QQQ, with a linear/log toggle
- Drawdown chart and worst drawdown episodes
- Yearly returns and monthly-return heatmap
- Trade count, win rate, profit factor and turnover
- The exact sizing rule and a file-by-file code map
- The paper trail and counter-evidence

The 20- and 26-year windows use the synthetic 3x QQQ series from the Rust
backtester; the 5- and 10-year windows use real TQQQ prices.
