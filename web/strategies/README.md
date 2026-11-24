# Web strategy configs

These configs exist only to populate the local dashboard. They are research
variants, not live presets; the live preset remains
`configs/nasdaq_leveraged_trend.toml`.

- `sp500_2x_trend.toml` — SSO above SPY's 200-day average, SHY below it.
- `nasdaq_3x_simple.toml` — TQQQ above QQQ's 200-day average, BIL below it.
- `nasdaq_3x_simple_synth.toml` — the same rule with a synthetic TQQQ series
  for the 20/26-year windows.

To add a variant:

1. Add the TOML here.
2. Add an `Export-Window` call in `scripts/export-web-data.ps1`.
3. Add its metadata to `web/public/data/strategies.json`.
4. Run `scripts/export-web-data.ps1` from the repository root.
