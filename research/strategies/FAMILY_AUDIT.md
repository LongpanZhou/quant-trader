# Family audit of the 20 additions

Existing entry gates: trend-vol (price trend/MA), vol-crash (realised vol/term
structure/ML path risk), relative (QQQ/SPY or TQQQ/QQQ ratio), event-recovery
(drawdown/capitulation), calendar (FOMC/OpEx/month/pre-holiday dates),
session-timing (overnight/first-hour/close block), short-reversal (1-5 day
price overreaction), rebalance-flow (mechanical LETF/closing flow),
intraday-microstructure (opening range/order flow/volume), ml-microstructure
(fitted ML on intraday features).

| New family | Primary gate | Existing overlap | Decision |
|---|---|---|---|
| tail-hedge-overlay | fast crash + synthetic inverse hedge | vol-crash (corr 0.85) | keep, distinct tail instrument |
| close-location | QQQ close-at-low / 5-day hold | short-reversal (corr 0.79) | keep, ratio-froth beater; CLV gate |
| policy-liquidity | BIL short-rate path | none | keep |
| volume-skew | up/down volume asymmetry | none | keep |
| vol-of-volume | volume dispersion/entropy | none | keep |
| change-point | online structural break | none | keep |
| hurst-persistence | Hurst/variance-ratio regime | trend-vol (borderline) | keep, statistical object |
| tqqq-decay | realised variance drag | relative/vol (borderline) | keep |
| realized-skew | intraday skew | vol-crash (borderline) | keep, skew object |
| beta-rotation | QQQ/SPY beta | relative (borderline) | keep, beta object |
| weekday-seasonality | weekday clock | calendar | **replace** |
| monthly-seasonality | month clock | calendar | **replace** |
| cpi-nfp-release | release calendar | calendar | **replace** |
| quarter-end-flow | quarter boundary | calendar/rebalance | **replace** |
| kelly-sizing | risk sizing | other/risk parity | **replace** |
| dynamic-risk-parity | risk contribution | other/risk parity | **replace** |
| volume-clock | midday volume state | session/intraday | **replace** |
| range-compression | intraday range | intraday-microstructure | **replace** |
| gap-continuation | opening gap | session/short-reversal | **replace** |
| lead-lag (removed earlier) | SPY residual | short-reversal | already removed |

## Replacement plan

Ten external-data families, each with a primary object not present in the
existing ten:

1. `vix-term-structure` — implied-vol curve (VIX/VIX3M).
2. `credit-spread` — HYG/IEF credit risk appetite.
3. `yield-curve` — 10y-3m Treasury slope.
4. `dollar-regime` — UUP dollar impulse.
5. `gold-safe-haven` — GLD/QQQ safe-haven demand.
6. `oil-shock` — USO energy shock.
7. `bond-equity-correlation` — TLT/QQQ rolling correlation.
8. `sector-rotation` — XLK/XLU growth-vs-defensive.
9. `breadth` — RSP/SPY equal-weight breadth.
10. `crypto-risk-appetite` — BTC risk appetite.

Data are cached under `data/external/` from Yahoo daily adjusted series. The
TQQQ execution panel remains the local 1-minute QQQ/TQQQ/BIL panel; signals use
the prior external close and fill at the next QQQ open.


## Final replacement results

The ten overlaps were replaced by these external-data families. Metrics are
full 2016-2026 daily-close; the one-shot 2024-2026 holdout is included.

| Replacement | Full CAGR | Full DD | Sharpe | Fills | Bar |
|---|---:|---:|---:|---:|:--:|
| ix-term-structure | 38.68% | 65.45% | 0.94 | 241 | above |
| credit-spread | 33.17% | 77.46% | 0.85 | 183 | below |
| sector-rotation | 29.86% | 48.79% | 0.94 | 719 | below |
| readth | 34.21% | 64.66% | 0.94 | 743 | below |
| crypto-risk-appetite | 46.50% | 52.33% | 1.19 | 293 | above |
| small-cap-relative | 47.02% | 78.08% | 1.01 | 511 | above |
| international-relative | 48.44% | 60.93% | 1.06 | 359 | above |
| 
ates-volatility | 38.80% | 43.01% | 1.05 | 355 | above |
| copper-gold | 28.60% | 73.53% | 0.76 | 347 | below |
| energy-rotation | 36.48% | 72.74% | 0.90 | 447 | below |

Kept from the original additions: tail-hedge, close-location,
policy-liquidity, volume-skew, vol-of-volume, change-point, Hurst,
TQQQ-decay, realized-skew and beta-rotation.

**Residual caveat:** close-location still correlates 0.79 with
amily-short-reversal, and tail-hedge 0.85 with ol-scaled-crash-stop.
They are retained because they are the only two candidates that beat

atio-froth on full CAGR; removing them would remove the ratio-froth result.


## 2026-11-28 low-correlation replacement

The four highest raw-correlation additions were replaced with gates from
unused data dimensions:

| Removed | Corr | Added | Corr | Jaccard | Full CAGR | Holdout CAGR |
|---|---:|---|---:|---:|---:|---:|
| ol-of-volume | 0.84 | skew-change | 0.60 | 0.48 | 32.19% | 4.00% |
| oil-shock | 0.80 | efa-spy | 0.60 | 0.44 | 35.59% | 37.16% |
| lowvol-rotation | 0.79 | qual-spy | 0.61 | 0.49 | 35.03% | 10.85% |
| eta-rotation | 0.77 | hyg-spy | 0.63 | 0.54 | 19.37% | 12.79% |

Primary objects: CBOE SKEW tail-risk pricing, EFA/SPY developed-market
relative, QUAL/SPY quality-factor leadership, HYG/SPY credit-equity risk
appetite. Pairwise correlations 0.38-0.61; pairwise Jaccard 0.27-0.40.


## 2026-11-28 strict pass: remaining non-beater names

The audit still showed three non-beater winners above 0.70 raw correlation.
They were replaced with low-overlap gates:

| Removed | Corr | Added | Corr | Jaccard | Full CAGR | Holdout CAGR |
|---|---:|---|---:|---:|---:|---:|
| 
ealized-skew | 0.74 | mtum-spy | 0.67 | 0.57 | 34.06% | 22.99% |
| 	qqq-decay | 0.73 | reakeven | 0.60 | 0.48 | 19.67% | -7.88% |
| style-rotation | 0.71 | sector-dispersion | 0.64 | 0.55 | 16.76% | 1.15% |

Result: every non-beater addition is now at or below 0.69 raw correlation.
close-location (0.77) is the only exception, and it is the only ratio-froth
beater. Winner count is 14; the site remains 43 strategies / 45 curves.


## Final pass: close-location out of the 20

Close-location (0.77 raw correlation with short-reversal) was removed from
the 20 independent families and retained as the aggressive sleeve of the
regime-switch overlay. Gold-miner stress replaced it:

| Removed | Corr | Added | Corr | Jaccard | Full CAGR | Holdout CAGR |
|---|---:|---|---:|---:|---:|---:|
| close-location | 0.77 | gold-miner-stress | 0.693 | 0.537 | 24.04% | 25.90% |

Result: all 20 independent additions are at or below 0.70 raw correlation and
0.66 Jaccard. The beater is the separate regime-switch overlay.
