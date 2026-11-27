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
| `fast-trend-vol` | 44.61% | 40.26% | +0.00 pp | 0.00e+00 | 74 | PASS |
| `ml-regime-v2` | 41.74% | 35.98% | -0.29 pp | 0.00e+00 | 1 | PASS |
| `qqq-spy-relative` | 38.98% | 53.64% | +0.00 pp | 0.00e+00 | 134 | PASS |
| `relative-value-tqqq` | 40.50% | 51.54% | +0.00 pp | 0.00e+00 | 35 | PASS |
| `tqqq-52week-high` | 38.64% | 39.43% | +0.09 pp | 0.00e+00 | 47 | PASS |
| `vol-of-vol-timing` | 42.17% | 51.64% | +0.00 pp | 0.00e+00 | 277 | PASS |
| `vol-term-structure` | 42.48% | 35.80% | +0.00 pp | 0.00e+00 | 66 | PASS |

## Research notes

- **`crash-early-warning`** — Vol/drawdown/gap early-warning composite; 2020 crash hedge; 50% defensive spells were false alarms. Plausible crash avoidance, not broad alpha.
- **`drawdown-recovery-v2`** — Deep-drawdown recovery entries after a capitulation low, with cash between episodes. Read report: cash-episode conditioning and the 2020/2022 concentration decide the pass.
- **`ema-ribbon-trend`** — 20/50/100 EMA ribbon + 0.5% hysteresis + 85% vol target. All 8 grid cells pass; without hysteresis 36.40% (below bar); 2/30 shuffled placebos beat CAGR but the base DD is the best of 30; 2022-23 weak. Plausible but whipsaw-premium-dependent trend.
- **`fast-trend-vol`** — 20/50 EMA trend + 85% vol target + 2.5% intraday stop + 5-session crash cooldown. Trend/vol timing; 2019 whipsaw; 2016-2019 weak. Plausible risk-managed TQQQ beta.
- **`ml-regime-v2`** — Momentum + quarterly logistic P(20-day TQQQ drawdown >15%); ML adds nothing over rv5<0.60 (91% same decisions). Trend/vol timing.
- **`qqq-spy-relative`** — QQQ/SPY 126d relative momentum x QQQ 150d SMA 4-state leverage ladder; 7/8 grid cells pass, placebo p=0.045. But the relative gate adds only +0.019 Sharpe and costs 2.3 pp CAGR vs the absolute-only ladder; replacing 2022 with TQQQ drops CAGR to 22.8%. Fragile crash-avoidance beta.
- **`relative-value-tqqq`** — Ratio momentum + vol scale; ratio momentum is 99.7% explained by QQQ trend and variance. Variance-adjusted TQQQ beta timing.
- **`tqqq-52week-high`** — QQQ within 8% of its 252d high and above SMA20 -> TQQQ; exit on the 20d closing low or -10% from the high; 85% vol target. 6/8 grid cells; the 8-11% entry band is a ridge and the base is the highest-CAGR cell; removing the 52-week gate drops dev CAGR to 32.41%; 2023 +63.8% vs TQQQ +204.9%. v2 fixed v1's intraday lookahead.
- **`vol-of-vol-timing`** — Parkinson range vol + vol-of-vol risk state; 2022-dependent; de-risk cuts weak; vov-spike rule has event evidence. Plausible risk-state timing.
- **`vol-term-structure`** — 50% QQQ>165d SMA trend + 50% RV20/RV60<0.95 term-structure sleeve + RV5/RV60 acute-spike kill. All 8 grid cells pass; 3-session delay drops to 33.6%; term structure buys 10.4 pp DD and +0.17 Sharpe over trend+spike, not raw CAGR; 2020 crash-avoidance concentrated.
