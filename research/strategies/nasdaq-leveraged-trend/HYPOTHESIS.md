# Nasdaq Leveraged Trend

Python version of the rule the Rust bot trades from `bot.toml` in this folder, so the research runner can test it
next to the other strategies on the same 2016-2026 panel and rules.

QQQ above its 165-day average -> a QQQ/TQQQ blend sized to a 40% annualised volatility target; below it -> BIL.

Parameters are copied from the TOML. The logic is `LeveragedIndex` in
`src/strategy.rs`, ported to `research/strategies/leveraged_index.py`.
