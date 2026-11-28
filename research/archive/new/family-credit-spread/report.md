# Credit spread — development report

**Family:** `credit-spread`  
**Directory:** `research/new/family-credit-spread/`  
**Window:** 2016-01-04 .. 2023-12-29 (development only). No 2024-2026 data
enters any signal, result or robustness calculation; the external series are
truncated at the development end before the features are computed.  
**Headline marks:** 1-minute panel, next-session 09:30 open, 2% band, 1 bp
headline cost; 5 bp and 10 bp reported.  
**Pre-registration:** `HYPOTHESIS.md`.

## Verdict (short)

**Falsified.** At 1 bp the strategy earns **29.07% CAGR, 77.46% max drawdown and
0.777 Sharpe** versus the TQQQ bar of **36.72% / 82.29% / 0.82**. It is active
(147 fills, 73 state changes), but it fails the return and Sharpe bars, 0 of 8
plateau cells clear the bar, the circular-shift placebo is not significant
(p = 0.345), and — most importantly — the **direction of the hypothesis is
wrong**: the credit-improving state earned +0.053% average next-session TQQQ
return while the credit-deteriorating state earned +0.222% (difference -0.170%,
t = -0.88). Credit deterioration was a better time to own TQQQ than credit
improvement in this window.

This is a clean negative result, not a dead strategy. The mechanism is
rejected.

## 1. What was tested

The HYG/IEF total-return ratio is the price of high-yield credit relative to
duration. The strategy trades a long-only TQQQ/BIL book on a two-level
hysteresis:

| Condition | Target |
|---|---|
| `cr20 >= +0.005` | 100% TQQQ |
| `cr20 <= -0.010` | 100% BIL |
| otherwise | hold previous state |

where, for adjusted closes:

```
cr_t   = ln(HYG_t / IEF_t)
cr20_t = cr_t - cr_{t-20}
```

The 0.5%-1.0% band is the deadband. The decision is taken from the session's
official external close, written at the session's 15:59 bar and filled at the
next session's 09:30 open. Bars inside a session carry the target written at
the previous close. Idle capital is BIL.

The centre is a round-number cell (`+0.005 / -0.010`, 20 sessions). The 3 x 3
neighbourhood and a 60-session ablation are reported in section 6.

## 2. Data and execution

- Signal series: Yahoo daily `HYG` and `IEF` adjusted closes, 2015-01-02
  onward. Both adjusted closes include distributions, so the ratio is a
  relative total-return index. The ratio and its changes are computed on the
  external calendar and reindexed to the QQQ session calendar with a forward
  fill.
- Execution: local 1-minute QQQ/TQQQ/BIL panel, next-session 09:30 open, 2%
  rebalance band, 1 bp headline cost, 5/10 bp sensitivity. The benchmark is
  100% TQQQ on the same panel and cost.
- No 2024+ row is loaded: `credit_features(DEV_END)` truncates both series
  before the ratio is formed. The panel itself ends 2023-12-29.

## 3. Headline development metrics

1-minute panel, next-session open, 2% band. "TQQQ exposure" is the mean TQQQ
weight; the harness "exposure" is 100% because idle capital is BIL.

| Cost | CAGR | Max DD | Sharpe | Sortino | Vol | TQQQ exp. | Fills | Turnover | Ending equity |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 bp | **29.07%** | **77.46%** | **0.777** | 1.109 | 47.40% | 71.80% | **147** | 527.9x | $767,186 |
| 5 bp | 28.12% | 77.76% | 0.762 | 1.086 | 47.39% | 71.80% | 147 | 508.8x | $723,376 |
| 10 bp | 26.95% | 78.14% | 0.742 | 1.058 | 47.39% | 71.80% | 147 | 486.0x | $672,115 |
| TQQQ B&H | 36.15% | 82.29% | 0.801 | 1.122 | 66.55% | 100% | 1 | 1.0x | $1,175,165 |
| QQQ B&H | 18.91% | 37.30% | 0.900 | — | 22.02% | 0% | 1 | 1.0x | $398,628 |
| **TQQQ dev bar** | **36.72%** | **82.29%** | **0.82** | — | — | — | — | — | — |

The strategy fails the CAGR and Sharpe bars. It has a 4.8 pp lower drawdown than
TQQQ but a 9.1 pp lower CAGR and a slightly lower Sharpe. The daily-bar
cross-check is 29.07% CAGR / 76.44% DD / 0.772 Sharpe / 147 fills; the
1-minute and daily paths agree closely.

## 4. Activity and trade anatomy

| Item | Value |
|---|---:|
| Full-window fills | **147** |
| State changes | **73** (37 entries, 36 exits) |
| TQQQ buys / sells | 37 / 36 |
| Average on-run | 39.1 sessions |
| Median on-run | 28.0 sessions |
| On sessions / fraction | 1,445 / 71.8% |
| State changes by year | 10, 9, 12, 10, 11, 5, 19, 5 (2016-2023) |
| Final state | risk-on |

The activity floor is met. The 2022 state changes jump to 19: the credit ratio
was whipsawed by the bear-market rallies, and the strategy re-entered several
times before the next deterioration leg.

## 5. Subperiods and yearly returns

| Subperiod | Strategy CAGR | Strategy DD | Strategy Sharpe | TQQQ CAGR | TQQQ DD |
|---|---:|---:|---:|---:|---:|
| 2016-2019 | 26.47% | 40.65% | 0.868 | 48.60% | 58.0% |
| 2020-2021 | 108.86% | 37.19% | 1.639 | 91.47% | 69.9% |
| 2022-2023 | **-20.21%** | **75.94%** | -0.024 | -22.33% | 81.0% |

The 2020-2021 subperiod is genuinely strong: the credit-improving state was
long into the post-COVID recovery and beat TQQQ with half the drawdown. But
2016-2019 gives up 22 pp of CAGR, and 2022-2023 is essentially TQQQ beta with a
slightly lower return. The full-window result is a wash at best.

| Year | Strategy | TQQQ | QQQ |
|---:|---:|---:|---:|
| 2016 | +10.3% | +18.6% | +9.3% |
| 2017 | +87.9% | +113.0% | +31.5% |
| 2018 | -24.9% | -23.5% | -1.8% |
| 2019 | +52.2% | +130.5% | +38.4% |
| 2020 | +143.9% | +99.8% | +45.9% |
| 2021 | +86.0% | +90.9% | +29.2% |
| 2022 | **-69.0%** | -79.7% | -33.2% |
| 2023 | +110.6% | +204.9% | +55.9% |

2023 is the biggest opportunity cost: credit was improving for much of the year,
but the strategy was only 89% exposed and still gave up 94 pp to TQQQ. The
2022 loss is only 11 pp better than TQQQ. There is no year in which the credit
signal provides a decisive, repeatable edge.

## 6. 8-cell parameter plateau

The 3 x 3 neighbourhood around the centre `(+0.005, -0.010)`, eight neighbours:

| `on` | `off` | CAGR | Max DD | Sharpe | Fills | Clears bar |
|---:|---:|---:|---:|---:|---:|:--:|
| +0.000 | -0.015 | 15.09% | 82.52% | 0.532 | 127 | no |
| +0.000 | -0.010 | 19.30% | 82.52% | 0.607 | 179 | no |
| +0.000 | -0.005 | 20.75% | 81.97% | 0.639 | 271 | no |
| +0.005 | -0.015 | 21.15% | 82.97% | 0.637 | 119 | no |
| +0.005 | -0.005 | 19.99% | 79.12% | 0.632 | 221 | no |
| +0.010 | -0.015 | 21.65% | 83.65% | 0.649 | 115 | no |
| +0.010 | -0.010 | 28.76% | 79.22% | 0.785 | 139 | no |
| +0.010 | -0.005 | 16.74% | 82.37% | 0.579 | 173 | no |
| **centre +0.005 / -0.010** | | **29.07%** | **77.46%** | **0.777** | **147** | **no** |

Zero of eight neighbours clear the bar. The centre is the maximum of the 3 x 3
grid (29.07% vs 28.76% for the next cell), which is a knife-edge selection, not
a plateau. Every cell is below the TQQQ CAGR bar and every Sharpe is below 0.82.

**60-session ablation.** `cr60` with the same thresholds gives 4.85% CAGR /
90.47% DD / 0.350 Sharpe / 93 fills. Slower credit momentum is worse, not
better.

## 7. Placebo / randomized signal dates

Two circular-shift placebos on the daily panel, 500 draws each:

| Placebo | Observed daily CAGR | p-value | 5th pct | Median | 95th pct |
|---|---:|---:|---:|---:|---:|
| Shift the HYG/IEF ratio | 29.07% | **0.345** | 3.15% | 23.57% | 48.19% |
| Shift the state path (matched exposure/run lengths) | 29.07% | **0.363** | 6.65% | 24.01% | 49.14% |

The observed CAGR sits near the middle of the placebo distribution. The timing
adds almost nothing over a random path with the same exposure. This is
consistent with the strategy being long TQQQ 72% of the time in a bull market.

## 8. Correlation with the nine existing winners

Daily development returns, 2016-01-04 .. 2023-12-29:

| Winner | Correlation |
|---|---:|
| ratio-froth | 0.567 |
| vol-scaled-crash-stop | 0.667 |
| relative-value-tqqq | 0.724 |
| fomc-opex-window | 0.581 |
| family-session-timing | 0.585 |
| family-short-reversal | 0.602 |
| family-rebalance-flow | 0.749 |
| family-intraday-microstructure-day | 0.444 |
| family-ml-microstructure | 0.656 |

Range **0.444-0.749**, maximum 0.749 (rebalance-flow). This is below the 0.85
overlap threshold, so the family is not a duplicate of an existing winner. It
is simply not profitable enough.

## 9. Mechanism check: the sign is wrong

The directional test is the most important result in this report. For each
development session, the next session's TQQQ open-to-close return is grouped by
the state formed at the prior close:

| State | Mean next-session TQQQ return | Days |
|---|---:|---:|
| Credit improving (`cr20 >= +0.005`) | +0.053% | 1,444 |
| Credit deteriorating (`cr20 <= -0.010`) | **+0.222%** | 567 |
| Difference | **-0.170%** | |
| t-stat | **-0.88** | |

The credit-deteriorating state has a *higher* forward return than the
credit-improving state, and the difference is not statistically significant in
the hypothesised direction. The sign is negative, so the mechanism is
falsified. The positive 2020-2021 subperiod is a recovery-beta effect, not
evidence for the credit-momentum hypothesis.

A longer-horizon (60-session) or level z-score version of the same object does
not rescue the sign: the best 2-state variants cap out at 28-31% CAGR and still
fail the return and Sharpe bars.

## 10. Kill criteria

| Criterion | Result | Pass? |
|---|---|:--:|
| 1 bp CAGR > 36.72% | 29.07% | no |
| 1 bp Sharpe > 0.82 | 0.777 | no |
| 1 bp max DD < 82.29% | 77.46% | yes |
| >= 100 fills or >= 30 state changes | 147 / 73 | yes |
| >= 6 of 8 neighbours clear bar | 0 of 8 | no |
| Placebo p < 0.10 | 0.345 (signal) / 0.363 (state) | no |
| Direction positive | -0.170%, t = -0.88 | no |
| Max correlation < 0.85 | 0.749 | yes |
| 10 bp CAGR > 36.72% | 26.95% | no |

Seven of nine criteria fail. The family is rejected.

## 11. Honest verdict

**Reject.** The primary object — HYG/IEF credit momentum — has the wrong sign
in the development window. A credit-improving state was a worse time to own
TQQQ than a credit-deteriorating state, and the strategy's positive years are
explained by long-TQQQ beta and the 2020 recovery, not by credit timing. The
drawdown reduction is real but modest, and it comes at a larger cost in CAGR.
There is no plateau and no placebo significance.

This does not mean credit is irrelevant to equity risk. It means the simple
"credit improving -> long TQQQ" mapping is not supported at the 20-session
horizon in 2016-2023. A conditional model (credit stress interacted with
equity volatility, or credit level rather than momentum) would be a different
family and is not claimed here.

## 12. Reproduction

```
$env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
$env:BT_THREADS = "4"
python research/new/family-credit-spread/strategy.py
```

`strategy.py` exposes `build_weights(ts, opens, closes)` returning the `(n, 3)`
long-only weight matrix and regenerates `result.json` on the development panel.
