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

## Results

All periods end 20 November 2026. Returns are per year, after 1bp slippage.

| Period | Strategy | QQQ | vs QQQ | Worst drawdown |
|---|---:|---:|---:|---:|
| 5 years | **26.4%** | 9.5% | **+16.9pp** | 29% (QQQ 35%) |
| 10 years | **37.4%** | 18.6% | **+18.8pp** | 38% (QQQ 35%) |
| 20 years (synthetic) | **27.0%** | 15.0% | **+12.0pp** | 42% (QQQ 53%) |
| 26 years (synthetic) | **20.4%** | 9.4% | **+11.0pp** | 42% (QQQ 73%) |

TQQQ started in 2010. Before that the test uses a synthetic 3x QQQ series,
checked against real TQQQ over 2010-2026: 30.5% vs 29.9% a year.

The long-run edge is thinner after realistic costs: **+9.4pp** with 5bp
slippage and 50bp financing.

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
```

## Research

The rule comes from three ideas in the literature:

- **Trend filter:** Faber (2007); Gayed & Bilello (2016),
  [Leverage for the Long Run](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2741701).
- **Volatility scaling:** Moreira & Muir (2017); Zarattini & Antonacci (2024),
  [A Century of Profitable Industry Trends](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4857230).
- **Closest Nasdaq replication:** Nygard & Liukko (2026),
  [thesis](https://diva-portal.org/smash/get/diva2:2077998/FULLTEXT01.pdf).

The case is not one-sided: Cederburg et al. (2020) and Massaad et al. (2024)
find that trend and volatility results weaken under robust testing.

Full details:

- [The study](docs/nasdaq_leveraged_trend.md) - why 165 days, why 40%, yearly
  returns, cost tests, caveats.
- [Live-readiness audit](docs/live_readiness_audit.md) - look-ahead checks,
  execution lag, tracking error, corporate actions.
- [More-trades research](docs/more_trades_research.md) - what else was tried
  and rejected.

## Keep in mind

- **This uses leverage.** A 30% Nasdaq drop can become a 40%+ account drop.
- **The five-year window was kind.** The full-cycle result is the better guide.
- **Costs matter.** The edge is about 9pp after realistic costs, not 17pp.
- **Paper only.** Not investment advice.

## Files

```
src/       backtester, live loop, paper broker, data feeds, strategy
configs/   live/5-year preset and 20-year research preset
docs/      full study, audit, expansion research
config.toml  default config (same as the live preset)
```
