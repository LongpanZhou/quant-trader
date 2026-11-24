# Strategy research map

Only one strategy is shipped: the **Nasdaq leveraged trend** rule. Everything
else on this page was tested and removed. This page keeps the paper trail: what
each strategy followed, how it traded, and why it is not the current rule.

The full performance record is in
[the study](nasdaq_leveraged_trend.md). The expansion tests and cost results are
in [more-trades research](more_trades_research.md).

## Current strategy

| Strategy | Bars | Research | Rule |
|---|---|---|---|
| `nasdaq_leveraged_trend` | 1d | Gayed & Bilello (2016); Moreira & Muir (2017) | QQQ above its 165-day average: hold a QQQ/TQQQ blend sized to 40% volatility. Below it: hold BIL. |

This is the only preset in `configs/`. `config.toml` is the same rule.

## Trend plus leverage

The direct ancestors of the current rule.

| Strategy | Bars | Research | Rule |
|---|---|---|---|
| `leverage_2x` | 1d | Gayed & Bilello (2016) | Hold SSO while SPY is above its 200-day average; otherwise T-bills. |
| `leverage_3x` | 1d | Gayed & Bilello (2016) | The same rule with UPRO. |
| `leverage_nasdaq_3x` | 1d | Gayed & Bilello (2016) | The same rule on QQQ with TQQQ. |
| `leverage_3x_voltarget` | 1d | Gayed & Bilello (2016); Moreira & Muir (2017) | In an uptrend, blend SPY and UPRO to aim for 20% volatility. |
| `core` | 1d | Combination | 50% 2x S&P rotation plus 50% multi-asset trend. |

**Why not current:** 2x was not enough (QLD added +9.8pp over five years,
just below the +10pp bar), and the S&P versions were weaker than Nasdaq.
The 3x Nasdaq version with volatility sizing became the current rule.

## Intraday

| Strategy | Bars | Research | Rule |
|---|---|---|---|
| `vwap_1m` | 1m | Zarattini & Aziz (2023) | Long QQQ/SPY above the session VWAP, short below it, flat before the close. |
| `vwap_10_1m` | 1m | Zarattini & Aziz (2023) | The same rule across ten symbols. |
| `orb_1m` | 1m | Zarattini & Aziz (2023) | Opening-range breakout: first 5 minutes set the range, tight stop, 10x target, flat before the close. |
| `orb_tqqq_1m` | 1m | Zarattini & Aziz (2023) | The same opening-range breakout on TQQQ. |
| `orb_stocks_5m` | 5m | Zarattini, Barbon & Aziz (2024) | Opening-range breakout on the 20 "stocks in play" with the most unusual opening volume. |
| `intraday_momentum` | 5m | Zarattini, Aziz & Barbon (2024) | Buy when price leaves its normal intraday range; trail a stop at the range edge or VWAP; flat before the close. |
| `intraday_momentum_10` | 5m | Zarattini, Aziz & Barbon (2024) | The same rule across ten symbols. |

**Why not current:** at 1bp the signals are marginal; at 5bp they are negative.
VWAP lost 9.19% over 28 days at 5bp, and opening-range breakout was roughly
flat. The edge does not survive realistic costs.

## Cross-sectional stock selection

| Strategy | Bars | Research | Rule |
|---|---|---|---|
| `ls_momentum` | 1d | Jegadeesh & Titman (1993) | Monthly: long the strongest 10% of the S&P 500, short the weakest 10%. |
| `value_momentum`, `value_momentum_long` | 1d | Asness, Moskowitz & Pedersen (2013) | Rank on one-year momentum and five-year cheapness; long the best 10%, optionally short the worst 10%. |
| `profitability`, `profitability_long` | 1d | Novy-Marx (2013) | Long the top 20% of S&P 500 companies by return on assets, from SEC filings. |
| `earnings` | 1d | Ball & Brown (1968); Bernard & Thomas (1989) | Read quarterly reports from SEC EDGAR; go long positive profit surprises and short negative ones. |
| `momentum_rotation` | 1d | Clenow (2015) | Weekly: hold the 8 stocks with the strongest volatility-adjusted 90-day momentum. |

**Why not current:** the clean backtests either fail the correlation test
(`SR_sleeve > rho * SR_core`) or depend on today's index membership. The
point-in-time test of the momentum rule fell from 47.9% to 9.2% a year once
delisted stocks were kept. Large-cap earnings drift has been weak since 2006.

## Diversified trend

| Strategy | Bars | Research | Rule |
|---|---|---|---|
| `monthly_trend` | 1d | Faber (2007) | Hold five asset-class ETFs only while each is above its 10-month average. |
| `trend_stocks` | 1d | Zarattini & Antonacci (2024); Zarattini, Pagani & Wilcox (2025) | 20-day channel breakout, 40-day trailing stop, inverse-volatility sizing; hold up to 40 names. |
| `trend_sp500` | 1d | Same as `trend_stocks` | The same rules across the whole S&P 500. |
| `trend_sectors` | 1d | Zarattini & Antonacci (2024) | The same rules on 29 sector and industry ETFs, unused cash in cash. |
| `trend_multi_asset`, `trend_multi_asset_long` | 1d | Moskowitz, Ooi & Pedersen (2012); Hurst, Ooi & Pedersen (2017) | Trend across 17 ETFs: long what is rising, short or flat what is falling, sized by volatility. |

**Why not current:** standalone, these diluted the Nasdaq edge. Multi-asset
trend lost 8.11pp a year vs SPY over five years, sector trend lost 5.63pp, and
100-stock trend lost 0.45pp (with survivorship bias). A 25% multi-asset sleeve
did help, but that combination is not part of the shipped rule.

## Textbook and discretionary-style rules

| Strategy | Bars | Research | Rule |
|---|---|---|---|
| `sma_cross` | 5m | Textbook | Buy when the fast average crosses above the slow one; sell below. |
| `rsi_reversion` | 5m | Textbook | Buy RSI(14) oversold; sell when it recovers. |
| `breakout` | 5m | Textbook (Donchian) | Buy a new 40-bar high; sell a new 20-bar low. |
| `connors_rsi2` | 1d | Connors & Alvarez (2008) | Buy a 2-day RSI below 5 in a stock above its 200-day average; sell above the 5-day average. |
| `bollinger` | 1d | Chan (2013) | Buy two standard deviations below the 20-day average; sell at the average. |

**Why not current:** these were scaffolding and tests, not edges. `sma_cross`
is still used by the backtester's unit tests; the rest are removed.

## Combinations

| Strategy | Bars | Research | Rule |
|---|---|---|---|
| `combo` | 1d | None | 50% trend plus 30% long/short momentum plus 20% RSI(2) pullbacks. |

**Why not current:** combining weak sleeves did not create a stronger edge, and
the extra bookkeeping made the live path harder to audit.

## Sources

- [Gayed & Bilello (2016), *Leverage for the Long Run*](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2741701).
- [Faber (2007), *A Quantitative Approach to Tactical Asset Allocation*](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=962461).
- [Moreira & Muir (2017), *Volatility-Managed Portfolios*](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2659431).
- [Zarattini & Antonacci (2024), *A Century of Profitable Industry Trends*](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4857230).
- Zarattini & Aziz (2023), intraday VWAP and opening-range work.
- Zarattini, Barbon & Aziz (2024), *Beat the Market*.
- Moskowitz, Ooi & Pedersen (2012), *Time Series Momentum*.
- Hurst, Ooi & Pedersen (2017), *A Century of Evidence on Trend-Following Investing*.
- Asness, Moskowitz & Pedersen (2013), *Value and Momentum Everywhere*.
- Novy-Marx (2013), *The Other Side of Value*.
- Jegadeesh & Titman (1993), *Returns to Buying Winners and Selling Losers*.
- Ball & Brown (1968); Bernard & Thomas (1989), earnings drift.
- Connors & Alvarez (2008), *Short Term Trading Strategies That Work*.
- Chan (2013), *Algorithmic Trading*.
- Clenow (2015), *Stocks on the Move*.
