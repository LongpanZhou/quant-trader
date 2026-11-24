# quant-trader

A small Rust backtester and **paper-trading** loop for one strategy: a
volatility-targeted, leveraged Nasdaq-100 trend follower. It has no code path
that can place a real-money order.

The strategy holds a blend of **QQQ** and **TQQQ** while QQQ is above its
165-day average, sized to a 40% annualised volatility target, and parks in
**BIL** (T-bills) otherwise.

## The rule

Evaluated once per completed daily bar, using the previous close, with orders
filled at the next session's open:

```
sma  = 165-day simple moving average of QQQ close
vol  = annualised standard deviation of QQQ daily returns, 20 days

if QQQ close <= sma:
    weight(BIL) = 1
else:
    exposure = min(0.40 / vol, 3.0)
    if exposure <= 1:
        weight(QQQ) = exposure, weight(BIL) = 1 - exposure
    else:
        weight(TQQQ) = (exposure - 1) / 2
        weight(QQQ)  = 1 - weight(TQQQ)
```

Positions are only resized when they drift more than **2% of equity** from
target. Backtests use a one-bar decision lag and next-open fills, matching the
live loop.

## Results

All windows end **20 November 2026** and use 1bp slippage. Benchmark is QQQ
total return.

| Window | Strategy | QQQ | Excess | Max drawdown | Sharpe | Round trips |
|---|---:|---:|---:|---:|---:|---:|
| 5 years | **26.4%** | 9.5% | **+16.9pp** | 29.4% (QQQ 35.1%) | 0.82 | 54 |
| 10 years | **37.4%** | 18.6% | **+18.8pp** | 38.3% (QQQ 35.1%) | 1.05 | 97 |
| 20 years* | **27.0%** | 15.0% | **+12.0pp** | 41.5% (QQQ 53.4%) | 0.84 | 261 |
| 26 years* | **20.4%** | 9.4% | **+11.0pp** | 42.3% (QQQ 73.0%) | 0.71 | 319 |

\* TQQQ only exists from 2010. Before that the backtest uses a synthetic
daily-reset 3x QQQ series. It was validated against real TQQQ over 2010-2026:
**30.50%/yr synthetic vs 29.86%/yr real**, a 0.64pp difference.

The full-cycle edge is cost-sensitive: **+10.96pp** at 1bp, **+10.01pp** at
5bp, **+10.30pp** with a 50bp financing spread, and **+9.36pp** with both.
That is the honest margin, not the five-year number.

## Run it

```powershell
cargo build --release
cargo test                 # offline unit tests

# five-year backtest (config.toml is the same preset)
.\target\release\quant-trader.exe backtest

# ten-year robustness
.\target\release\quant-trader.exe backtest --days 3650

# full cycle, synthetic 3x before 2010
.\target\release\quant-trader.exe backtest --config configs\nasdaq_synthetic_20y.toml
.\target\release\quant-trader.exe backtest --config configs\nasdaq_synthetic_20y.toml --days 9500

# live paper loop (Yahoo prices, local ledger, no account or key)
.\target\release\quant-trader.exe preflight   # check data + current target
.\target\release\quant-trader.exe run         # trade the paper account
.\target\release\quant-trader.exe status
.\target\release\quant-trader.exe replay      # rehearse the live code on the last session
.\target\release\quant-trader.exe reset       # wipe the paper account
```

`broker = "sim"` is the default and needs no setup. Alpaca paper trading is
optional: set `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY`, then change
`broker` in the config.

## Why this design

The rule is not stock picking; it is **trend-followed leverage with a risk
budget**:

- **Trend filter:** Faber (2007) and Gayed & Bilello (2016) show that a
  long moving-average filter puts leverage on only in regimes where forward
  volatility is lower and positive streaks are longer. That is exactly when a
  daily-reset leveraged fund compounds instead of decays.
- **Volatility target:** Moreira & Muir (2017) scale exposure by trailing
  realised variance. Zarattini & Antonacci (2024) apply the same idea with
  per-asset volatility targeting and up to 200% gross exposure.
- **Why 165 days and 40%:** the parameter sweep is in the study. The 200-day
  no-vol-target version returned +6.3pp with a 52% drawdown; 2x QQQ (QLD)
  returned +9.8pp, just below the target. Sizing, not the signal, is what
  makes the result.

Primary sources:

- Gayed & Bilello (2016), *Leverage for the Long Run* —
  [SSRN 2741701](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2741701)
- Faber (2007), *A Quantitative Approach to Tactical Asset Allocation*
- Moreira & Muir (2017), *Volatility-Managed Portfolios*
- Zarattini & Antonacci (2024), *A Century of Profitable Industry Trends* —
  [SSRN 4857230](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4857230)
- Nygård & Liukko (2026), Nasdaq-100 2001-2026 replication —
  [thesis PDF](https://diva-portal.org/smash/get/diva2:2077998/FULLTEXT01.pdf)

Counter-evidence is part of the design record too: Cederburg, O'Doherty, Wang
& Yan (2020) find volatility management does not systematically beat unmanaged
portfolios out of sample, and Massaad et al. (2024) find published trend
results degrade under robust testing. This implementation uses only trailing
information and no fitted constants, but the caveats remain.

## Read more

- [`docs/nasdaq_leveraged_trend.md`](docs/nasdaq_leveraged_trend.md) — full
  study: literature, parameter sweep, yearly returns, drawdowns, caveats.
- [`docs/live_readiness_audit.md`](docs/live_readiness_audit.md) — look-ahead
  audit, tracking error, execution lag, corporate actions, cost matrix.
- [`docs/more_trades_research.md`](docs/more_trades_research.md) — attempts to
  add trades (multi-asset trend, sectors, intraday, PEAD, pairs) and why they
  were rejected.

## Caveats

- **This is leverage.** It holds 1-3x Nasdaq exposure (about 2.4x when
  invested), so a 30% index drawdown can be a 40%+ account drawdown. The
  2022 loss was -12.5%, not -30%, but that is the trend filter working, not a
  guarantee.
- **The five-year window is kind.** It contains the 2022 crash and a strong
  2023-2026 recovery. The 20- and 26-year numbers are the better guide.
- **The edge is thin at realistic costs.** The full cycle is +9.36pp after 5bp
  slippage and 50bp financing. Do not assume the five-year +16.9pp persists.
- **Yahoo data is revised.** Re-runs can differ by about 0.1pp and a few
  trades. The configs pin `end_date = "2026-11-20"` so the window does not
  move with the run date.
- **Paper only.** Nothing here is investment advice, and the live loop trades
  a simulator.

## Layout

```
src/        engine, backtester, sim broker, Yahoo/Alpaca data, strategy
configs/    nasdaq_leveraged_trend.toml (live/5y), nasdaq_synthetic_20y.toml
docs/       study, live-readiness audit, expansion research
config.toml default config, same as the Nasdaq preset
```
