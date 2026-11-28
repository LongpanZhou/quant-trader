# Revisit audit: all strategies, 1-minute bars, 2016-2026

Generated 2026-11-26 by `research/revisit/audit/audit_all.py`. Panel 2016-01-04 .. 2026-10-23; 10y = 2017-01-03 ->, 5y = 2021-10-25 ->.
Every run: next-bar-open fills, 2% band, 1 bp slippage (5/10 bp in audit.json).

| strategy | status | bars | look-ahead | 10y CAGR | 10y DD | 5y CAGR | 5y DD | issues |
|---|---|---|---|---:|---:|---:|---:|---|
| vol-scaled-crash-stop | pending_test | 1m | clean | 56.78% | 39.3% | 38.26% | 39.3% | none |
| intraday-seasonality | passed | 1m | clean | 28.50% | 43.8% | 26.07% | 43.8% | none |
| ratio-pairs | passed | 1m | clean | 21.69% | 34.6% | 17.11% | 34.6% | none |
| event-risk-overlay | rejected | 1m | clean | 19.71% | 39.0% | 8.55% | 39.0% | none |
| ml-classifier | pending_test | 1m | clean | 17.93% | 36.9% | 13.56% | 36.9% | none |
| ml-crash-overlay-winner | pending | 1m | clean | 17.87% | 25.3% | 20.94% | 25.3% | none |
| time-of-day | retired_overlay_only | 1m | clean | 17.37% | 31.8% | 9.42% | 31.8% | none |
| intraday-mean-reversion | passed | 1m | clean | 14.19% | 31.5% | 6.19% | 27.7% | none |
| intraday-momentum | pending | 1m | clean | 13.94% | 64.0% | 1.97% | 64.0% | none |
| overnight-crash-filter | rejected | 1m | clean | 13.69% | 27.6% | 8.66% | 27.6% | none |
| letf-rebalance-flow | design_only | 1m | clean | 13.27% | 44.1% | 6.65% | 44.1% | none |
| risk-parity-hrp | pending_test | 1m | clean | 6.34% | 18.5% | 4.79% | 18.5% | none |
| gap-capitulation-reversal | passed | 1m | clean | 5.41% | 12.5% | 6.00% | 9.1% | none |
| dual-speed-regime | rejected | 1m | clean | 4.27% | 38.0% | 7.82% | 27.8% | none |
| daily-regime-minute-entry | rejected | 1m | clean | 3.55% | 64.2% | 15.85% | 24.3% | none |
| volume-orderflow | pending_audit | 1m | clean | 2.74% | 16.8% | 5.32% | 16.8% | none |
| winner-ensemble-blend | rejected | 1m | clean | 2.67% | 32.7% | 2.87% | 28.8% | none |
| dynamic-leverage-throttle | pending | 1m | clean | 2.61% | 16.3% | 2.97% | 16.3% | none |
| gap-fill-fade | pending | 1m | clean | 2.41% | 0.5% | 3.75% | 0.3% | none |
| stop-reentry-recovery | retired_overlay_only | 1m | clean | 2.25% | 1.8% | 3.72% | 0.1% | none |
| vol-kelly-overlay | pending_test | 1m | clean | 1.13% | 19.2% | 1.76% | 16.8% | none |
| drawdown-regime | pending_test | 1m | clean | -0.13% | 48.8% | -1.20% | 48.8% | none |
| donchian-breakout | pending_audit | 1m | clean | -0.14% | 34.8% | 0.16% | 31.0% | none |
| ensemble-signals | pending_holdout | 1m | clean | -0.27% | 76.0% | -8.72% | 76.0% | none |
| opening-range-breakout | pending_backtest | 1m | clean | -1.16% | 19.7% | -1.00% | 11.5% | none |
| drawdown-stop-overlay | pending | 1m | clean | -3.02% | 57.7% | 0.91% | 55.7% | none |

Benchmarks (1-minute marks):

- 10y QQQ buy & hold: CAGR 20.67%, DD 37.3%
- 10y TQQQ buy & hold: CAGR 39.38%, DD 82.3%
- 5y QQQ buy & hold: CAGR 14.10%, DD 37.3%
- 5y TQQQ buy & hold: CAGR 14.29%, DD 82.3%

Notes:

- daily-regime-minute-entry: synthetic short column(s) [1]; held overnight on 0 sessions
- drawdown-regime: cut-tested directly (cut_direct.py) at 2020-03-12 00:00, 2022-09-13 00:00: all weights before each cut identical
- drawdown-regime: no position changes after 2023 (constant weights [0.0, 0.0, 1.0])
- dual-speed-regime: cut2: only the last 1 bar(s) before the cut differ (end-of-data)
- event-risk-overlay: dev run ends 2023-12-29 09:30, before the 2023-12-29 session
- gap-fill-fade: synthetic short column(s) [3]; held overnight on 0 sessions
- intraday-mean-reversion: cut-tested directly (cut_direct.py) at 2020-03-12 11:07, 2022-09-13 10:41: all weights before each cut identical
- intraday-seasonality: cut1: only the last 1 bar(s) before the cut differ (end-of-data)
- opening-range-breakout: cut2: cut2 differences (10:18-10:31) come from entry_cutoff_bars=30 counted back from the last bar in the data: with data stopping at 10:41 the run thinks the session ends there. Live, the session end (15:59) is known from the clock, so this is not look-ahead.
- overnight-crash-filter: cut2: only the last 2 bar(s) before the cut differ (end-of-data)
- ratio-pairs: dev run ends 2023-12-28 15:59, before the 2023-12-29 session
- stop-reentry-recovery: no position changes after 2023 (constant weights [0.0, 0.0, 1.0])
- time-of-day: dev run ends 2023-12-28 15:59, before the 2023-12-29 session
- time-of-day: cut2: only the last 2 bar(s) before the cut differ (end-of-data)
- time-of-day: cut-tested directly (cut_direct.py) at 2020-03-12 11:07, 2022-09-13 10:41: all weights before each cut identical
- vol-scaled-crash-stop: engines agree on equity (maxrel 7.8e-16); fill count 2897 vs 2896 from a zero-size trade at a float tie
- winner-ensemble-blend: cut-tested directly (cut_direct.py) at 2020-03-12 00:00, 2022-09-13 00:00: all weights before each cut identical
