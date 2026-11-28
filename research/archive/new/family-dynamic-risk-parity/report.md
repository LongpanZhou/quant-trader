# Dynamic risk parity — development report

**Verdict: fail as an above-TQQQ family (honest negative).** The rolling
risk-contribution allocator earns **25.39% CAGR / 52.45% max DD / 0.86 Sharpe**
at 1 bp over 2016-2023. It cuts the TQQQ drawdown from 82.3% to 52.5%, but it
is 11.3 percentage points below the published TQQQ CAGR bar and does not beat
QQQ's 0.90 Sharpe. The structural reason is visible in the weights: the
covariance matrix of QQQ and TQQQ is nearly singular (correlation 0.99,
volatility ratio 3), so equal risk contributions collapse to a slow 75/25
QQQ/TQQQ mix. The "dynamic" part adds essentially nothing.

## Development metrics

| Cost | CAGR | Max DD | Sharpe | Sortino | Vol | Exposure | Fills | Turnover |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 bp | 25.39% | 52.45% | 0.86 | 1.20 | 32.7% | 99.9% | 251 | 18x |
| 5 bp | 25.35% | 52.48% | 0.86 | 1.20 | 32.7% | 99.9% | 251 | 18x |
| 10 bp | 25.29% | 52.51% | 0.86 | 1.20 | 32.7% | 99.9% | 251 | 18x |

There are **251 fills across 126 independent fill days**, so the activity floor
is met. Average weights are 75.8% QQQ, 24.2% TQQQ, 0.0% BIL. Turnover is only
18x over eight years: the allocator is almost static.

## Subperiods and years

| Window | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| 2016-2019 | 27.6% | 32.8% | 1.12 |
| 2020-2021 | 52.1% | 41.1% | 1.20 |
| 2022-2023 | -2.1% | 50.0% | 0.14 |

| Year | Return |
|---|---:|
| 2016 | +12.8% |
| 2017 | +49.2% |
| 2018 | -5.2% |
| 2019 | +58.4% |
| 2020 | +64.6% |
| 2021 | +43.3% |
| 2022 | -48.2% |
| 2023 | +87.0% |

The 2022-2023 subperiod is negative and the 2022 calendar year is -48.2%: a
1.5x QQQ exposure has no defence against a correlated equity bear market.

## Plateau (pre-registered 8 cells)

| window | risk budget TQQQ | CAGR | Max DD | Sharpe | Fills |
|---:|---:|---:|---:|---:|---:|
| 21 | 0.50 | 25.94% | 52.4% | 0.87 | 247 |
| 42 | 0.50 | 25.61% | 52.4% | 0.86 | 245 |
| **63** | **0.50** | **25.39%** | **52.5%** | **0.86** | **251** |
| 126 | 0.50 | 25.39% | 52.5% | 0.86 | 235 |
| 252 | 0.50 | 24.60% | 52.5% | 0.84 | 239 |
| 63 | 0.40 | 23.89% | 48.4% | 0.87 | 177 |
| 63 | 0.60 | 27.41% | 57.1% | 0.85 | 359 |
| 63 | 0.70 | 29.62% | 62.2% | 0.84 | 441 |

This is a clean risk-return ladder, not a plateau around a passing cell: every
extra turn of the risk budget buys CAGR one-for-one with drawdown and slightly
**lowers** Sharpe. No window or budget reaches the 36.72% bar.

## Placebo and static attribution

* **Circular-shift placebo (100 shifts):** median CAGR 24.8%, 5th-95th range
  24.0-26.5%; the real 25.39% is at the 72nd percentile. Timing is
  indistinguishable from a random rotation of the same allocation path.
* **Static book at the average weights (75.8/24.2/0.0):** 24.96% CAGR / 52.0%
  DD / 0.85 Sharpe. The dynamic allocator adds 0.4 pp of CAGR, well inside the
  1 pp "static matches" kill band.

## Correlation to the nine current winners

Range **0.60 to 0.90**. Highest: `family-short-reversal` 0.90,
`relative-value-tqqq` 0.89, `family-rebalance-flow` 0.87. The book is a
levered QQQ beta, so it is unsurprisingly correlated with the long-biased
winners. It is below the 0.95 duplicate threshold but at the high end.

## Kill criteria

| Criterion | Result | Pass? |
|---|---|---|
| 1 bp CAGR > 36.72% | 25.39% | **no** |
| 1 bp DD < 82.29% | 52.45% | yes |
| 10 bp CAGR > 36.72% | 25.29% | **no** |
| Placebo percentile >= 90% | 72% | **no** |
| Max winner correlation <= 0.95 | 0.90 | yes |
| >= 100 fills / >= 30 events | 251 / 126 | yes |
| No negative subperiod | 2022-2023 is -2.1% | **no** |
| Static blend not within 1 pp | 24.96% vs 25.39% | **no** (static matches) |

## What this negative result teaches

1. **Risk parity needs a non-degenerate covariance matrix.** With a constant-
   leverage ETF, TQQQ is almost exactly 3x QQQ. Equalising risk contributions
   across the two is algebraically inverse-volatility weighting, which is a
   constant 75/25 mix. There is no state variable left to time.
2. **Cash cannot be an equal-risk asset in a long-only book.** BIL's volatility
   is ~0.2% versus QQQ's ~22%; an unconstrained ERC puts ~99% in BIL. Excluding
   cash is the only sensible implementation, and that removes the asset that
   could have provided crisis diversification.
3. **The long-only constraint caps effective exposure at 1.5x** (75% QQQ + 25%
   TQQQ = 0.75 + 0.75). To reach TQQQ's return the book would need materially
   more TQQQ, which is exactly what the risk budget ladder does — at the cost
   of TQQQ-like drawdowns and no Sharpe improvement.

This is a structural result, not a parameter-search failure. The family is
retained as a research record and as a risk-control reference, not as an
above-TQQQ winner.

## Reproduce

```bash
cd research/new/family-dynamic-risk-parity
python strategy.py        # rewrites result.json
```

`build_weights(ts, opens, closes)` accepts the shared minute panel or a daily
panel; the lead's `run_holdout.py` can call it directly.
