# New-strategy verification

Causality test: truncate the panel at 2020-03-12 11:07, rebuild every
weight, and compare all pre-cut weights. Holdout freshness: count weight
changes in 2024-2026. Dev reproduction: holdout-run dev slice vs the
agent's frozen `result.json`. Weights: shape, long-only, sum ≤1.

| Strategy | Full CAGR | Full DD | Dev diff | Pre-cut max | 2024-26 changes | Status |
|---|---:|---:|---:|---:|---:|---|
| `crash-early-warning` | 42.06% | 52.96% | +0.00 pp | 0.00e+00 | 15 | PASS |
| `drawdown-recovery-v2` | 49.99% | 41.11% | +0.00 pp | 0.00e+00 | 8 | PASS |
| `ema-ribbon-trend` | 40.09% | 46.58% | +0.00 pp | 0.00e+00 | 37 | PASS |
| `family-intraday-microstructure` | 45.29% | 47.15% | — | 1.00e+00 | 963 | FAIL causality |
| `family-intraday-microstructure-day` | 40.97% | 47.42% | +0.00 pp | 0.00e+00 | 612 | PASS |
| `family-ml-microstructure` | 41.03% | 44.51% | +0.00 pp | 0.00e+00 | 110 | PASS |
| `family-rebalance-flow` | 45.55% | 50.92% | +0.00 pp | 0.00e+00 | 416 | PASS |
| `family-session-timing` | 46.26% | 41.42% | +0.00 pp | 0.00e+00 | 1412 | PASS |
| `family-short-reversal` | 49.54% | 66.46% | +0.00 pp | 0.00e+00 | 86 | PASS |
| `fast-trend-vol` | 44.61% | 40.26% | +0.00 pp | 0.00e+00 | 74 | PASS |
| `fomc-opex-window` | 52.77% | 40.64% | +0.00 pp | 0.00e+00 | 78 | PASS |
| `ml-regime-v2` | 41.74% | 35.98% | -0.29 pp | 0.00e+00 | 1 | PASS |
| `qqq-spy-relative` | 38.98% | 53.64% | +0.00 pp | 0.00e+00 | 134 | PASS |
| `ratio-froth` | 62.21% | 36.65% | -0.00 pp | 0.00e+00 | 150 | PASS |
| `relative-value-tqqq` | 40.50% | 51.54% | +0.00 pp | 0.00e+00 | 35 | PASS |
| `tqqq-52week-high` | 38.64% | 39.43% | +0.09 pp | 0.00e+00 | 47 | PASS |
| `vol-of-vol-timing` | 42.17% | 51.64% | +0.00 pp | 0.00e+00 | 277 | PASS |
| `vol-scaled-crash-stop` | 51.32% | 37.88% | +0.19 pp | 0.00e+00 | 618 | PASS |
| `vol-term-structure` | 42.48% | 35.80% | +0.00 pp | 0.00e+00 | 66 | PASS |

## Research notes

- **`crash-early-warning`** — Vol/drawdown/gap early-warning composite; 2020 crash hedge; 50% defensive spells were false alarms. Plausible crash avoidance, not broad alpha.
- **`drawdown-recovery-v2`** — Deep-drawdown recovery entries after a capitulation low, with cash between episodes. Read report: cash-episode conditioning and the 2020/2022 concentration decide the pass.
- **`ema-ribbon-trend`** — 20/50/100 EMA ribbon + 0.5% hysteresis + 85% vol target. All 8 grid cells pass; without hysteresis 36.40% (below bar); 2/30 shuffled placebos beat CAGR but the base DD is the best of 30; 2022-23 weak. Plausible but whipsaw-premium-dependent trend.
- **`family-intraday-microstructure-day`** — Day-only opening-drive + trailing stop, flat overnight. Dev 44.12% / 46.72% DD / 1.13 Sharpe; 5 bp 19.5%, 10 bp negative; 1 bp only. Family-pure intraday version of the combined opening-drive + overnight strategy.
- **`family-ml-microstructure`** — Walk-forward weekly ridge on session-shape features (clv5, volr5); monthly refit, 0.25x mean hurdle. Dev 49.81% / 45.93% DD / 1.18 Sharpe; 5 bp 48.46%, 10 bp 46.79% — genuinely cost-robust. No daily vol/drawdown/trend features in the primary.
- **`family-rebalance-flow`** — Mechanical leveraged-ETF/closing-flow strategy. Dev 50.55% / 53.87% DD / 1.16 Sharpe; 5 bp 47.13%, 10 bp 42.88%; full 45.55% / 50.92% DD / 1.07 Sharpe; holdout 34.89%. Cost-robust but still a 3x flow beta.
- **`family-session-timing`** — Pure intraday session timing (no daily trend gate). Dev 56.23% / 37.86% DD / 1.34 Sharpe on only 19.1% exposure, but turnover is enormous: 56.3% at 1 bp, 49.1% at 2 bp, 42.2% at 3 bp, already below the bar at 4 bp. Full 46.26% / 44.86% DD / 1.15 Sharpe; cost-fragile.
- **`family-short-reversal`** — QQQ 2-session down streak or 3-session return <= -1.5% -> TQQQ for 5 sessions, no trend/stop/vol in the primary. Full 49.54% / 66.46% DD / 0.99 Sharpe; holdout 62.12%; the high DD is the cost of catching falling knives, and the edge is concentrated in rebound episodes.
- **`fast-trend-vol`** — 20/50 EMA trend + 85% vol target + 2.5% intraday stop + 5-session crash cooldown. Trend/vol timing; 2019 whipsaw; 2016-2019 weak. Plausible risk-managed TQQQ beta.
- **`fomc-opex-window`** — Pure FOMC + post-OpEx calendar, ex-ante dates through 2026. Dev 58.26% / 42.60% DD / 1.36 Sharpe; full 52.77% / 42.60% DD / 1.29 Sharpe; holdout 40.99%. Calendar windows are the primary edge; a vol throttle is only an overlay. Return edge is concentrated in 2020-2023, and it lags calm bulls.
- **`ml-regime-v2`** — Momentum + quarterly logistic P(20-day TQQQ drawdown >15%); ML adds nothing over rv5<0.60 (91% same decisions). Trend/vol timing.
- **`qqq-spy-relative`** — QQQ/SPY 126d relative momentum x QQQ 150d SMA 4-state leverage ladder; 7/8 grid cells pass, placebo p=0.045. But the relative gate adds only +0.019 Sharpe and costs 2.3 pp CAGR vs the absolute-only ladder; replacing 2022 with TQQQ drops CAGR to 22.8%. Fragile crash-avoidance beta.
- **`relative-value-tqqq`** — Ratio momentum + vol scale; ratio momentum is 99.7% explained by QQQ trend and variance. Variance-adjusted TQQQ beta timing.
- **`tqqq-52week-high`** — QQQ within 8% of its 252d high and above SMA20 -> TQQQ; exit on the 20d closing low or -10% from the high; 85% vol target. 6/8 grid cells; the 8-11% entry band is a ridge and the base is the highest-CAGR cell; removing the 52-week gate drops dev CAGR to 32.41%; 2023 +63.8% vs TQQQ +204.9%. v2 fixed v1's intraday lookahead.
- **`vol-of-vol-timing`** — Parkinson range vol + vol-of-vol risk state; 2022-dependent; de-risk cuts weak; vov-spike rule has event evidence. Plausible risk-state timing.
- **`vol-scaled-crash-stop`** — Legacy always-long TQQQ with inverse-ATR sizing and a 0.70x ATR intraday stop. Shared-runner adapter: full 51.46% / 39.29% DD / 1.29 Sharpe, holdout 34.89%; audit pending. No 165-day trend gate; the stop is the strategy.
- **`vol-term-structure`** — 50% QQQ>165d SMA trend + 50% RV20/RV60<0.95 term-structure sleeve + RV5/RV60 acute-spike kill. All 8 grid cells pass; 3-session delay drops to 33.6%; term structure buys 10.4 pp DD and +0.17 Sharpe over trend+spike, not raw CAGR; 2020 crash-avoidance concentrated.
