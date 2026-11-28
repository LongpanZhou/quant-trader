# Weekly close-location / participation state model - development report

**Strategy:** `family-ml-microstructure` / frozen primary `ridge5_ms_clv5_vol5_f25`
**Window:** 2016-01-04 -> 2023-12-29 (development only; 2024-2026 never loaded)
**Marks:** 1-minute, next-open fills, 2% band
**Bar:** TQQQ dev 36.72% CAGR / 82.29% max DD / 0.82 Sharpe

## Verdict

**Pass on the development window at 1, 5 and 10 bp, with a 45.9-46.1% max
drawdown.** The frozen cell is a walk-forward ridge model on two
session-shape features - 5-day close location and 5-day volume participation -
that predicts the next 5-session TQQQ return and holds TQQQ when the forecast
is above a quarter of the training mean, sized to a 45% volatility budget.

The honest qualification is that **the ML is not clearly additive over a
simple rule.** A fixed weekly `clv5<=0.25` gate gets 44.11% / 40.20% / 1.16 at
1 bp, and a fixed daily `volr<=0.25` gate gets 51.19% / 37.05% / 1.34. The ML
primary has a higher CAGR than the weekly rule but a higher drawdown; the
simple daily participation rule beats it on all three headline statistics at
1 bp. The family's edge is fast close-location / participation timing, not a
new ML alpha. The pass is real but it is a risk-managed TQQQ beta, not
independent alpha.

## Frozen-cell confirmation

The pre-freeze scratch log reported **51.67% CAGR / 45.93% DD / 1.20 Sharpe /
70.8% average TQQQ weight / 849 fills** for this cell. That number is
reproduced exactly when the refit calendar is stopped at 2023-10-01, which
leaves November-December 2023 at the 1.0 warm-up weight:

| run | CAGR | max DD | Sharpe | avg TQQQ | fills |
|---|---:|---:|---:|---:|---:|
| pre-freeze calendar (`refit_end=2023-10-01`) | 51.67% | 45.93% | 1.20 | 70.8% | 849 |
| clean full calendar (all of 2023 predicted) | **49.81%** | **45.93%** | **1.18** | **70.2%** | **859** |

The 1.86 pp difference is entirely the two months the old scratch left on the
warm-up weight; the model, features, hurdle, refit frequency and execution are
unchanged. The clean, holdout-ready run is the headline below. Both versions
pass the bar at 1/5/10 bp.

## 1. Headline

### Development window, 1-minute marks

| Cost | CAGR | Max DD | Sharpe | Sortino | Vol | Avg TQQQ wt | Fills | Turnover |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **1 bp** | **49.81%** | **45.93%** | **1.18** | 1.65 | 42.0% | 70.2% | 859 | 1,594x |
| 5 bp | 48.46% | 46.00% | 1.16 | 1.62 | 42.0% | 70.2% | 859 | 1,594x |
| 10 bp | 46.79% | 46.07% | 1.13 | 1.59 | 42.0% | 70.2% | 859 | 1,594x |

$100k at 1 bp ends at **$2,521,565** over 7.98 years. The 1 bp headline beats
the 36.72% bar by **13.1 pp** with a drawdown **36.4 pp below** the 82.29%
bar and 14.1 pp below the 60% target.

### Benchmarks, same window and marks

| Asset / control | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| TQQQ buy-and-hold | 36.15% | 82.29% | 0.80 |
| TQQQ official bar | 36.72% | 82.29% | 0.82 |
| QQQ buy-and-hold | 18.91% | 37.30% | 0.90 |
| BIL | 1.39% | 0.24% | 0.92 |
| Vol-target only (45%, same sizing) | 38.77% | 59.97% | 0.97 |
| **Frozen ML primary (1 bp)** | **49.81%** | **45.93%** | **1.18** |

The volatility-target-only control already clears the CAGR bar, so the ML
signal must be judged on what it adds on top of it: **+11.0 pp CAGR and
-14.0 pp drawdown**, at a similar vol budget. That is the real contribution;
it is not a claim that the raw signal beats TQQQ without sizing.

## 2. What the strategy does

### Features (session shape, intraday only)

For each session `d`, using adjusted 1-minute bars and the **15:58** signal
bar (the second-to-last regular bar):

```
CLV_d  = 2*(C_d - L_d)/(H_d - L_d) - 1     # close location in the day's range
VOLR_d = log(V_d / mean(V_{d-20..d-1}))    # participation vs its own trailing mean
clv5_d  = mean(CLV_{d-4..d})
volr5_d = mean(VOLR_{d-4..d})
```

The signal bar is strictly before the 15:59 fill. The high, low, close and
volume all use data through 15:58; the 15:59 bar is only the execution price.

### Label and model

```
y5_d = entry(d+5) / entry(d) - 1           # next 5-session holding return
model = ridge, L2=30, expanding window, monthly refit
train = every 5th session (block starts), labels realised >= 9 days before test
scale = training mean/std only, clip +/-5
hurdle = 0.25 * training mean of y5
```

### Allocation and execution

```
sigma20 = annualised stdev of last 20 entry-to-entry TQQQ returns through d-1
base_vt = clip(0.45 / sigma20, 0, 1)
w       = base_vt * 1{predicted y5 >= 0.25 * training_mean}
remainder = BIL
decision  = every 5 sessions, at the 15:58 signal bar
fill      = next bar open (15:59)
hold      = 5 sessions
```

The 5-session horizon is deliberate. A daily gate on the same signal turned
over too much to survive 5-10 bp costs; the weekly state is persistent and
cost-robust. It is still a short-horizon microstructure state, not a slow
trend or volatility regime.

### Warm-up disclosure

The first model prediction is **2017-04-04**; the minimum training window is
60 five-session blocks. From 2016-01-04 to 2017-04-03 the strategy holds the
1.0 warm-up weight (100% TQQQ). The 2016 return is therefore exactly TQQQ's
+18.6%. This is disclosed and is not part of the claimed edge. On the
model-only period (2017-04-04 -> 2023-12-29) the strategy still makes
**49.68% CAGR / 44.51% max DD**, versus TQQQ **33.64% / 81.68%**. The pass is
not a warm-up artifact.

## 3. Pre-registered grid and plateau

The grid was fixed around the frozen cell before the final run. The primary
was not changed after seeing the results.

| # | id | features | refit | hurdle | CAGR | max DD | Sharpe | avg TQQQ | pass 1 bp |
|---:|---|---|---|---:|---:|---:|---:|---:|---|
| 1 | **clv5_vol5_m_f25 (frozen)** | clv5, volr5 | monthly | 0.25 | **49.81%** | **45.93%** | **1.18** | 70.2% | yes |
| 2 | clv5_vol5_m_f50 | clv5, volr5 | monthly | 0.50 | 41.01% | 45.93% | 1.05 | 64.5% | yes |
| 3 | clv5_vol5_m_f75 | clv5, volr5 | monthly | 0.75 | 34.29% | 45.93% | 0.96 | 58.0% | no |
| 4 | clv5_vol5_q_f25 | clv5, volr5 | quarterly | 0.25 | 49.36% | 45.93% | 1.18 | 69.9% | yes |
| 5 | clv5_m_f25 | clv5 | monthly | 0.25 | 38.63% | 60.56% | 0.97 | 77.1% | yes |
| 6 | clv5_m_f50 | clv5 | monthly | 0.50 | 41.34% | 55.96% | 1.03 | 70.5% | yes |
| 7 | volr5_m_f25 | volr5 | monthly | 0.25 | 40.57% | 62.82% | 1.00 | 77.0% | yes |
| 8 | clv5_vol5_last5_m_f25 | clv5, volr5, last30_5 | monthly | 0.25 | 36.64% | 45.50% | 0.99 | 64.8% | no |

**6 of 8 cells pass the formal bar at 1 bp.** The plateau is broad in the
feature direction: the two-feature cell, the quarterly cell, both one-feature
cells and the 50% hurdle all clear 36.72%. It is not flat in the hurdle
direction: 0.75 is too conservative and falls to 34.29%. The 3-feature cell
misses by 0.08 pp (36.64%), i.e. it is at the bar, not safely above it.

The primary is the highest-CAGR cell. That is a consequence of the freeze,
not a post-hoc promotion: the cell was fixed from the cost-robust weekly
screen before this run, and no other cell was substituted after the results.

## 4. Feature ablation

| Feature set | CAGR | max DD | Sharpe | avg TQQQ |
|---|---:|---:|---:|---:|
| clv5 + volr5 (primary) | 49.81% | 45.93% | 1.18 | 70.2% |
| clv5 only | 38.63% | 60.56% | 0.97 | 77.1% |
| volr5 only | 40.57% | 62.82% | 1.00 | 77.0% |
| last30_5 only | 32.96% | 49.66% | 0.90 | - |
| gap5 + first30_5 + mid5 | 25.61% | 66.07% | 0.75 | - |
| full shape (adds day5, rng5) | 30.73% | 49.31% | 0.89 | - |

Both single features clear the formal CAGR bar but with drawdowns above the
60% target. The combination is the only configuration that clears both the
CAGR bar and the 60% DD target, which is consistent with the mechanism:
close location says *which way* the week is likely to revert; participation
says *whether the session was significant*. Adding the other session-shape
features (gap, first 30m, midday, range) **hurts**: the model overfits noise
and the full-shape cell falls to 30.73%. This is a useful negative result and
the reason the grid is deliberately small.

## 5. Placebo

All placebos use the same model, hurdle, sizing and 1 bp cost. Labels or
training features are permuted within each monthly training window; the
timing placebo shifts the features by one 5-session block.

| Placebo | mean CAGR | p5 | p50 | p95 | real | real percentile |
|---|---:|---:|---:|---:|---:|---:|
| shuffled training labels (20) | 35.48% | 26.75% | 35.01% | 45.31% | 49.81% | 100% |
| shuffled training features (20) | 36.15% | 26.94% | 36.03% | 44.52% | 49.81% | 95% |
| features shifted 5 sessions (1) | 36.37% | - | - | - | 49.81% | - |

The real strategy is above all 20 label placebos and 19 of 20 feature
placebos, and shifting the features one block destroys the edge (36.37% CAGR,
60.08% DD, 0.95 Sharpe). But the separation is modest: the placebos are
structurally high because they inherit the long TQQQ / 45% vol-target
exposure, which alone makes 38.77%. The ML's incremental edge over the
placebo mean is about 14 pp; over the 95th percentile it is about 5 pp. This
is evidence that the timing is not random, but not overwhelming evidence of a
large, stable signal.

## 6. Cut tests and causality

Two pre-cut rebuilds were run on data truncated at a block-aligned date:

| Cut | Sessions compared | Max abs weight difference | Changed > 1e-12 |
|---|---:|---:|---:|
| 2020-06-30 | 1,130 | 0.0 | 0 |
| 2022-06-30 | 1,635 | 0.0 | 0 |

The pre-cut weights are bit-identical. Every feature is a trailing statistic
through the 15:58 signal bar; the label uses only past 5-session blocks; the
model standardisation uses training rows only; the volatility target uses
returns through the prior session; and the walk-forward refits only on labels
realised at least 9 calendar days before the test month. There is no
full-sample scaling and no holdout loading.

## 7. Yearly, subperiods and drawdown

### Yearly returns

| Year | Strategy | TQQQ | Difference |
|---:|---:|---:|---:|
| 2016 | 18.6% | 18.6% | 0.0 pp (warm-up) |
| 2017 | 131.6% | 113.0% | +18.6 pp |
| 2018 | 8.7% | -23.5% | +32.2 pp |
| 2019 | 61.7% | 130.5% | -68.8 pp |
| 2020 | 43.7% | 99.8% | -56.1 pp |
| 2021 | 103.1% | 90.9% | +12.2 pp |
| 2022 | -31.4% | -79.7% | +48.3 pp |
| 2023 | 134.8% | 204.9% | -70.1 pp |

The pattern is the familiar one: the strategy gives up a lot of upside in
strong bull years (2019, 2020, 2023) and earns its compounding edge by losing
much less in 2018 and 2022. It is not a broad all-weather alpha. The 2021 and
2017 beats are real but smaller than the bull-year give-ups.

### Subperiods

| Period | Strategy CAGR | max DD | TQQQ CAGR | TQQQ max DD |
|---|---:|---:|---:|---:|
| 2016-2019 | 51.45% | 34.32% | 48.60% | 57.97% |
| 2020-2021 | 67.45% | 44.51% | 91.47% | 69.89% |
| 2022-2023 | 26.33% | 34.16% | -22.33% | 81.05% |

The strongest relative contribution is 2022-2023: +48.7 pp of CAGR and 47 pp
less drawdown. The 2020-2021 period lags TQQQ badly on CAGR, which is the
cost of the participation filter during the post-COVID melt-up.

### Drawdown

The maximum drawdown is **45.93%** on 1-minute marks; on the daily equity
series the drawdown window is **2020-02-19 to 2020-03-12 at 44.51%** - the
COVID crash, not 2022. The strategy did not avoid the initial COVID gap; it
avoided the 2022 grind (-31.4% vs -79.7%). The drawdown improvement over TQQQ
is therefore mostly a 2022 story, not a 2020 one.

## 8. Exposure, correlation and what this is

- Average TQQQ weight: **70.2%**; fully invested 42.3% of sessions, zero
  TQQQ 13.7%; 211 weekly weight changes; 859 fills over 8 years.
- Daily correlation to TQQQ: **0.861**; to QQQ: **0.858**.
- The remainder is BIL. The strategy is long-only, weights >= 0, row sums
  <= 1.

This is a high-beta TQQQ timing overlay. It is not market-neutral, not
diversifying, and not a hedge. Its value is a better compounding path than
TQQQ buy-and-hold, paid for by giving up upside in strong bull years.

## 9. Simple-rule comparison: does the ML add anything?

| Rule | Cost | CAGR | max DD | Sharpe |
|---|---:|---:|---:|---:|
| **Frozen ML primary** | 1 bp | **49.81%** | **45.93%** | **1.18** |
| | 5 bp | 48.46% | 46.00% | 1.16 |
| | 10 bp | 46.79% | 46.07% | 1.13 |
| Weekly `clv5<=0.25` x VT | 1 bp | 44.11% | 40.20% | 1.16 |
| | 5 bp | 41.90% | 40.20% | 1.12 |
| | 10 bp | 39.18% | 40.20% | 1.07 |
| Daily `volr<=0.25` x VT | 1 bp | 51.19% | 37.05% | 1.34 |
| | 5 bp | 46.12% | 38.08% | 1.24 |
| | 10 bp | 39.98% | 39.68% | 1.12 |
| Vol-target only | 1 bp | 38.77% | 59.97% | 0.97 |
| TQQQ buy-and-hold | 1 bp | 36.15% | 82.29% | 0.80 |

The ML primary is **not clearly additive**:

- Against the fixed weekly close-location rule it adds +5.7 pp CAGR at 1 bp,
  but also +5.7 pp drawdown; the Sharpe is essentially identical (1.18 vs
  1.16). At 10 bp the ML is +7.6 pp CAGR and +0.06 Sharpe, so the extra
  feature and continuous forecast do buy something at higher costs.
- Against the fixed **daily** participation rule, the ML loses at 1 bp on
  every metric (49.81/45.93/1.18 vs 51.19/37.05/1.34). At 5 bp the ML has a
  higher CAGR (48.46 vs 46.12) but a higher drawdown and lower Sharpe. At
  10 bp the two Sharpe ratios are effectively tied (1.13 vs 1.12).

The honest reading is that the edge is a **fast close-location /
participation filter**, and the ML is a convenient but not superior way to
implement it. The 5-day horizon and the volume feature are what make the ML
cell cost-robust, but a simple daily volume gate is already cost-robust at
10 bp and has a better drawdown. The ML should not be presented as a new
source of alpha.

## 10. Family purity

- The primary predictors are **intraday session-shape price/volume
  features**: 5-day mean close location (CLV) and 5-day mean volume
  participation (VOLR). Both are built from 1-minute bars through 15:58.
- No daily realised volatility, drawdown, trend SMA or relative-strength
  feature is used as a predictor. The 45% volatility target is **risk
  control only**; it is not in the signal.
- `rng` (intraday range) was deliberately excluded from the primary and the
  grid. An exploratory screen showed that a range filter is a volatility
  proxy and carries most of the daily-gate result, which would violate the
  family mandate. The grid's full-shape ablation includes `rng5` and is
  worse (30.73%), so the frozen model does not depend on it.
- Caveat: `volr5` is correlated with the session range (about 0.48), so the
  participation leg is partly a fast volatility/participation proxy. The
  one-feature ablations show that neither leg alone clears both the CAGR bar
  and the 60% DD target; the combination is what works. This is disclosed
  rather than presented as pure directional alpha.

## 11. Honest verdict

What is supported:

- The frozen weekly ML cell clears the stated development bar at **1, 5 and
  10 bp**: 49.81% / 48.46% / 46.79% CAGR, 45.9-46.1% max DD, 1.18 / 1.16 /
  1.13 Sharpe. The pre-freeze 51.67% / 45.93% / 1.20 is reproduced exactly
  under its original calendar; the clean full-calendar run is 49.81%.
- The pass is not a warm-up artifact: the model-only period is 49.68% /
  44.51% versus TQQQ 33.64% / 81.68%.
- The pre-cut weights are bit-identical at two cut dates. There is no
  full-sample scaling or holdout loading.
- The signal is above all label-shuffle placebos and 19/20 feature-shuffle
  placebos, and shifting the features one block destroys the edge.
- The grid shows a broad feature plateau: 6/8 cells clear the bar, including
  both one-feature variants and the quarterly refit.

What is not supported:

- The ML is **not additive** over a simple rule. The fixed daily
  `volr<=0.25` gate is better on CAGR, drawdown and Sharpe at 1 bp, and has a
  comparable 10 bp profile. The weekly ML's advantage is mainly against the
  weekly close-location rule, not against the best simple participation rule.
- The edge is concentrated in crash avoidance: 2018 +32 pp and 2022 +48 pp
  versus TQQQ, with large give-ups in 2019, 2020 and 2023. The 2020-2021
  subperiod lags TQQQ by 24 pp of CAGR.
- The maximum drawdown is the 2020 COVID crash (45.93%), not a 2022
  drawdown. The strategy is not a crash hedge.
- The placebo separation over the 95th percentile is only about 5 pp. The
  placebos are structurally high because they inherit the vol-targeted TQQQ
  exposure.
- The 3-feature cell and the high-hurdle cell fail; the plateau is not flat
  in every direction.

Bottom line: this is a **verified, cost-robust TQQQ risk-management overlay**
that clears the development bar with a 46% drawdown, but it is not independent
alpha and the ML is not clearly better than a simple participation rule. It
should be presented as a close-location / participation timing strategy, not
as an ML discovery.

## 12. Reproduction

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
$env:BT_THREADS = "1"
python research/strategies/family-ml-microstructure/strategy.py
```

`strategy.py` builds the session features from adjusted 1-minute bars,
runs the 8-cell walk-forward grid, the 1/5/10 bp cost ladder, the placebo
and cut tests, and writes `result.json`. The public entry point is
`build_weights(ts, o, c)`: it accepts the daily panel and uses only data up to
`ts[-1]`, with `features` supplied or rebuilt from 1-minute bars. The refit
loop runs to the last month in `ts`, so extending the window extends the
walk-forward without retuning.

## 13. Files

- `HYPOTHESIS.md` - pre-registration and frozen grid.
- `strategy.py` - causal implementation, grid, placebo, cut tests.
- `result.json` - full numbers.
- `report.md` - this file.
