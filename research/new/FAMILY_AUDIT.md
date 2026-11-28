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
