# Verification: code, causality and research logic

Two separate tests are recorded here. **Code validity** is mechanical:
the pre-cut weight test, holdout freshness, dev reproduction and weight
integrity. **Research logic** asks whether the stated mechanism is what the
code actually trades, whether the evidence supports it, and how fragile the
pass is. A strategy can be code-clean and still be a weak idea; the verdict
column says which.

**Website visibility:** four of the ten are currently shown — the best
full-window CAGR in each family. The other six are hidden but retained in
`META.json` with `visible=false`.

## Code audit
All ten pass the 2020-03-12 11:07 truncation test with **0.0 pre-cut weight
difference**, rebuild their 2024-2026 weights (1 to 277 changes), stay
long-only with row sums <= 1, and reproduce the development slice. The two
non-zero dev differences are `ml-regime-v2` at -0.29 pp and
`tqqq-52week-high` at +0.09 pp, both from the final daily-to-minute mapping,
not from stale weights.

## Research-logic audit

| Strategy | What the code actually trades | Evidence for the pass | Main fragility | Logic verdict |
|---|---|---|---|---|
| `fast-trend-vol` | 20/50 EMA QQQ trend, 85% TQQQ vol target, 2.5% intraday stop, 5-session crash cooldown | +14.8 pp dev CAGR, 8/8 grid cells, all costs pass | 2019 whipsaw: +54.9% vs TQQQ +148.2%, worse DD; pass carried by 2020/2023 and avoiding 2022 | Plausible risk-managed TQQQ beta |
| `vol-of-vol-timing` | Parkinson range vol + vol-of-vol risk state + 20-day vol ladder, with a V-recovery add | 45.35% dev, 1.20 Sharpe, event study on vov spikes | 2022 contributes ~200% of net log excess; de-risk cuts only 0.65 pp DD; 2022 loses 46.2% | Risk-state timing, 2022-dependent |
| `crash-early-warning` | Vol/drawdown/gap early-warning composite, cash defence, 10-day-high re-entry | 40.38% dev, 54.86% DD, all costs pass | Ex-2020 24.7% vs TQQQ 27.8%; 2018 false alarms; 2016 -21.6% | Crash hedge, not broad alpha |
| `ml-regime-v2` | Momentum gate + quarterly logistic P(20-day TQQQ drawdown > 15%) | 59.61% dev, 42.89% DD, walk-forward model | `rv5 < 0.60` matches 91% of decisions; AUC inflated across years; 2016 in cash; holdout nearly constant risk-off | Trend/vol timing; the ML is not additive |
| `relative-value-tqqq` | TQQQ/QQQ ratio momentum + QQQ vol scale, QQQ fallback | 43.60% dev, 54.65% DD, plateau | Ratio momentum is 99.7% explained by QQQ trend and variance; 2022 worse than QQQ; always invested | Variance-adjusted beta timing |
| `ema-ribbon-trend` | 20/50/100 EMA ribbon, 0.5% hysteresis, QQQ tier, 85% vol target | 46.77% dev, 44.13% DD, 8/8 grid cells | Raw ribbon is 36.40% (below bar); 2/30 shuffled placebos beat CAGR; 2022-23 17.33% CAGR | Trend/vol timing dependent on the whipsaw buffer |
| `drawdown-recovery-v2` | 8%/12% drawdown circuit breaker, two-speed recovery re-entry, cash between episodes | 57.63% dev, 43.39% DD, placebo p=0.0125 | Only 3 macro episodes; 8/12 is a local peak; 2018 whipsaw -43.39% | Event-driven crash recovery |
| `vol-term-structure` | 50% QQQ>165d trend + 50% RV20/RV60<0.95 sleeve + RV5/RV60 spike kill | 51.57% dev, 37.90% DD, 8/8 grid cells | Term structure adds DD/Sharpe, not raw CAGR; 3-session delay 33.6%; 10/60 variant 37.8%; 2020-concentrated | Crash-avoidance timing |
| `qqq-spy-relative` | QQQ/SPY 126d relative momentum x QQQ 150d SMA, 4-state leverage ladder, vol cap | 44.36% dev, 55.03% DD, 7/8 cells, placebo p=0.045 | Relative gate adds only +0.019 Sharpe and costs 2.3 pp CAGR; replacing 2022 with TQQQ gives 22.8%; 2020 DD 55% | Fragile 2022 crash-avoidance beta |
| `tqqq-52week-high` | QQQ within 8% of its 252-day high + above SMA20, 20-day low / -10% exits, 85% vol target | 43.30% dev, 37.42% DD, 6/8 cells, prefix exact | Entry band is a ridge (5% fails, 8-11% works); base is highest-CAGR cell; 2023 +63.8% vs TQQQ +204.9%; removing the 52-week gate gives 32.41% | 52-week-high trend with a narrow entry plateau |

## Common finding

None of the ten is independent alpha. Nine are TQQQ trend, volatility or
crash-state timing; `drawdown-recovery-v2` is event-driven recovery timing.
Their full-window CAGR edge over TQQQ comes from avoiding a large part of the
2022 bear market (and, for several, the 2020 crash), while giving up return in
strong bull years. That is a legitimate, repeatable risk-management result,
but it is not a market-neutral or all-weather edge, and the website copy should
not claim one.
