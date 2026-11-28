# S&P 500 2x Trend

Hold the 2x S&P 500 fund (SSO) while SPY is above its 200-day average;
hold short-term Treasuries (SHY) below it. No volatility target.

`bot.toml` is the Rust bot config. The Python port is still to do: the shared
research panel only has QQQ/TQQQ/BIL minute data, so this strategy needs a
daily-only run on `data/external/SPY.parquet`, `SSO.parquet` and `SHY.parquet`.
