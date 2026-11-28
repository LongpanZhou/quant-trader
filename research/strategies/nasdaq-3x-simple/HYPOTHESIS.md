# Nasdaq 3x Simple Trend

Python version of the rule the Rust bot trades from `bot.toml` in this folder, so the research runner can test it
next to the other strategies on the same 2016-2026 panel and rules.

QQQ above its 200-day average -> 100% TQQQ; below it -> 100% BIL. No volatility target.

Parameters are copied from the TOML. The logic is `LeveragedIndex` in
`src/strategy.rs`, ported to `research/strategies/leveraged_index.py`.
