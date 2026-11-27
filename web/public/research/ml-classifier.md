# Agent 7 — Walk-forward ML classifier: TQQQ / BIL

**Slug:** `ml-classifier`
**Question:** can a walk-forward machine-learning classifier beat TQQQ buy-and-hold
(CAGR > TQQQ, max DD < TQQQ) on **both** the 10-year and 5-year windows?

**Answer:** the *30-minute* classifier does **not** pass. The *60-minute*
classifier has only a marginal 1 bp pass (41.87% vs 39.28% on 10y) and fails
at 5 bp. A **longer-horizon version of the same walk-forward pipeline**
(5/10/20-day labels, minute-derived features, QQQ 165-day SMA regime base)
**does pass both windows with margin**, including at 5 bp costs. The passing
strategy is a daily-decision strategy, not a 30/60-minute trading strategy.
Both sets of results are reported below.

---

## 0. Headline results

Primary strategy: **walk-forward logistic ensemble risk-off overlay on the
documented QQQ > 165-day SMA regime**.

| Window | Costs | CAGR | Max DD | Sharpe | Sortino | Fills | Turnover | Pass vs TQQQ |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 10y (2017-01-03 → 2026-10-23) | 1 bp | **74.95%** | **40.48%** | 1.53 | 2.19 | 353 | 22,023x | **PASS** |
| 10y | 5 bp | **72.44%** | **41.09%** | 1.50 | 2.14 | 353 | 19,639x | **PASS** |
| 5y (2021-10-25 → 2026-10-23) | 1 bp | **51.29%** | **33.20%** | 1.28 | 1.89 | 193 | 693x | **PASS** |
| 5y | 5 bp | **48.97%** | **33.41%** | 1.24 | 1.82 | 193 | 657x | **PASS** |

TQQQ buy-and-hold targets from `research/README.md`:

| Window | TQQQ CAGR | TQQQ max DD | TQQQ Sharpe |
|---|---:|---:|---:|
| 10y | 39.28% | 81.68% | 0.83 |
| 5y | 13.47% | 81.68% | 0.53 |

The daily baseline that already passes (`QQQ > 165-day SMA → TQQQ`, else BIL)
is reproduced exactly by the harness: **45.31% / 58.71% / 1.00** on 10y and
**34.61% / 36.86% / 0.88** on 5y. The ML overlay improves on it on both windows.

> **Read this before believing the headline CAGR.** The 10y number is boosted
> by an extraordinary 2020 (+403.8% for the strategy vs +99.8% for TQQQ).
> Removing 2020 entirely still leaves **54.30% CAGR / 40.48% DD** on the
> remaining 9 years. The 5y window (which excludes 2020) is **51.29% / 33.20%**.
> The 48-configuration stability grid has a median of **57.8% CAGR / 47.1% DD**
> on 10y and **40.5% / 35.6%** on 5y; all 48 configurations pass. The headline
> is above the grid median but is not the single best grid point. See §4.

---

## 1. Data, harness and execution assumptions

- Local adjusted 1-minute QQQ / TQQQ / BIL bars under `data/intraday-hf/`,
  regular session only. No new downloads.
- Features are 5-minute and daily aggregates; decisions are made at the daily
  close (or at the 15:50 bar for the minute experiments). Weights fill at the
  **next bar's open**. The harness charges slippage on traded notional.
- Long-only, non-negative weights, rows sum to ≤ 1. The only risky asset is
  TQQQ; the defensive asset is BIL.
- Primary cost **1 bp**; sensitivity **5 bp**.
- The simulator's 2% no-trade band is used throughout (`band=0.02`).
- Test windows: **2017-01-03 → 2026-10-23** (10y) and **2021-10-25 →
  2026-10-23** (5y). Daily bars annualise with 252; 5-minute bars with
  `252 × 78`.
- The 5y TQQQ benchmark is 13.47% in the README and 13.88% on the harness
  daily bars (small close-timing difference). The pass test uses the stricter
  **13.47%**.

Harness: `research/bt.py` (`bt.panel`, `bt.run`, `bt.stats`,
`bt.benchmark`, `bt.yearly`). No core files were modified.

---

## 2. Mandated experiment: 30/60-minute classifier (30-min fail; 60-min marginal)

### 2.1 Set-up

- 5-minute bars, 27 causal features: QQQ/TQQQ returns over 5/15/30/60/120
  minutes, day return, overnight gap, realized vol (30/60 min and day),
  vol ratio, RSI(14), distance from session VWAP, EMA(20)/EMA(60), 165-day
  trend, 20-day drawdown/momentum, time-of-day sin/cos, day-of-week sin/cos.
- Label: TQQQ beats BIL over the next 6 bars (30 min) or 12 bars (60 min).
- L2 logistic regression, annual walk-forward, first model trained on 2016,
  purge of `horizon` bars at each train/test boundary, features standardised
  on the training set only.
- Trading rules tested: enter/exit probability thresholds with a minimum
  holding period. All fills next open, 1 bp.

### 2.2 Out-of-sample accuracy

| Year | 30-min accuracy | 30-min base rate | 60-min accuracy | 60-min base rate |
|---|---:|---:|---:|---:|
| 2017 | 51.0% | 54.5% | 51.5% | 56.7% |
| 2018 | 52.1% | 51.6% | 53.6% | 52.8% |
| 2019 | 52.5% | 53.0% | 52.5% | 54.1% |
| 2020 | 53.0% | 54.3% | 54.1% | 55.7% |
| 2021 | 52.9% | 53.7% | 54.5% | 55.0% |
| 2022 | 52.4% | 50.1% | 52.3% | 49.6% |
| 2023 | 54.0% | 54.1% | 54.7% | 54.8% |
| 2024 | 52.7% | 52.7% | 53.3% | 53.2% |
| 2025 | 52.3% | 52.3% | 53.5% | 53.8% |
| 2026 | 51.6% | 51.7% | 52.2% | 51.8% |

Accuracy is essentially the base rate. The annual IC (prediction vs next
30/60-minute TQQQ-minus-BIL return) oscillates around zero and is negative in
several years (e.g. 2017 −0.011, 2023 −0.026 for 30 min). Decile mean excess
returns are not monotonic: for 30 min, deciles 0→9 were
`0.03, 0.93, 0.29, 1.04, 2.21, 2.42, 1.22, 0.14, 1.00, 0.18` bp; the bottom
decile was not the worst and the top decile was not the best.

### 2.3 Trading results (1 bp)

| Strategy | 10y CAGR | 10y DD | 10y Sharpe | 5y CAGR | 5y DD | Fills (10y) |
|---|---:|---:|---:|---:|---:|---:|
| 30 min, enter 0.55 / exit 0.45 / min hold 12 bars | 27.14% | 73.0% | 0.71 | 14.15% | 73.0% | 1,141 |
| 30 min, enter 0.60 / exit 0.40 / min hold 12 bars | 28.94% | 77.4% | 0.74 | 18.27% | 77.4% | 225 |
| 60 min, enter 0.55 / exit 0.45 / min hold 12 bars | **41.87%** | 71.8% | 0.90 | **23.02%** | 71.8% | 977 |
| 60 min, enter 0.55 / exit 0.45 / min hold 78 bars | 36.44% | 61.7% | 0.83 | 27.47% | 61.7% | 653 |

The 60-minute rule at 1 bp is a **marginal** pass vs TQQQ (41.87% > 39.28%,
71.8% < 81.68%), but:

- at **5 bp** its 10y CAGR falls to **36.32%**, below TQQQ (and 36.44% → 32.86%
  for the 78-bar variant);
- its max DD (71.8%) is worse than the daily baseline's 58.7%;
- it needs ~977 fills (about 100/year) and 3,427x turnover;
- yearly returns are erratic (2022 −66.3%, 2023 +189.7%).

**Verdict:** the mandated 30/60-minute formulation does not clear the bar
robustly. The 60-minute rule does meet the letter of the **1 bp** TQQQ test on
both windows, but it fails at **5 bp**, has a **71.8% max DD** (worse than the
daily baseline's 58.7%), and is not stable across holding periods. It is
reported for completeness; the recommended strategy is §3. The economic reason
is simple: a 30/60-minute TQQQ trade has an expected drift of roughly 1 bp,
while a 2 bp round trip (1 bp per side) already consumes it. A 52–54% hit rate
is not enough to overcome that plus spread and adverse selection.

---

## 3. Passing strategy: walk-forward multi-horizon risk-off overlay

### 3.1 Idea

The documented 165-day SMA regime is a robust bear-market filter, but it is
slow: it gives back a lot at turns and whipsaws. The ML layer is not asked to
pick the next 30 minutes. Instead, three classifiers estimate whether TQQQ will
beat BIL over the next **5, 10 and 20 trading days**. Their probabilities are
ranked against their own trailing year. When their **average rank is in the
bottom 20%** of the past year, the strategy moves an otherwise-long
TQQQ position to BIL for the next session. This is a tactical de-risking
overlay, not a standalone market-timing model.

Decomposition (1 bp, 10y / 5y):

| Component | 10y CAGR | 10y DD | 5y CAGR | 5y DD |
|---|---:|---:|---:|---:|
| QQQ > 165d SMA base only | 45.31% | 58.71% | 34.61% | 36.86% |
| ML ensemble standalone (long TQQQ unless bottom-quintile) | 62.13% | 75.59% | 23.77% | 75.59% |
| **Base + ML overlay** | **74.95%** | **40.48%** | **51.29%** | **33.20%** |

The base supplies the drawdown backbone; the ML layer supplies the tactical
exits. Neither alone is as good as the combination.

### 3.2 Features (38, all causal through the decision close)

Groups:

- **Returns / momentum:** QQQ 1, 2, 5, 10, 20, 60, 120, 250-day returns;
  TQQQ 20/60-day returns; 60-day leverage decay (`TQQQ r60 − 3 × QQQ r60`);
  20-day fraction of up days.
- **Realized volatility:** 10/20/60-day QQQ vol, 10/60 vol ratio, 252-day vol
  percentile, 20-day average intraday 5-minute vol.
- **RSI / stretch:** RSI(14), distance from VWAP, EMA(20), EMA(50),
  SMA(20/50/100/165/200), 252-day and 20-day drawdown.
- **Overnight / intraday structure:** overnight gap, intraday return,
  first-30-minute and last-30-minute returns, close location in the day's
  range, 20-day average overnight and intraday returns.
- **Rates / calendar:** BIL 20-day return, day-of-week.

The full list is in `result.json → diagnostics.features` and in `strategy.py`.

### 3.3 Model and walk-forward protocol

- Three **L2 logistic regressions** (one per horizon 5/10/20 days), lambda = 10,
  IRLS/Newton, 30 iterations maximum.
- Rolling **750-trading-day** training window, retrained once per calendar year
  (2017 … 2026). For 2017 the model necessarily trains on 2016 only.
- **Purge:** the last `horizon + 1` training rows are dropped so no training
  label overlaps the test year.
- **Coverage filter:** features with less than 50% finite coverage in the
  training window are dropped for that year (this mainly removes the 250-day
  feature in the 2017 model). Remaining NaNs are median-imputed on the
  training set; standardized using training mean/std; winsorized at ±6 sd.
- **Probability rank:** each model's probability is converted to a trailing
  252-day percentile (`min_periods=60`). The three ranks are averaged.
- **Signal:** `base = QQQ close > 165-day SMA`; `bear = average rank < 0.20`;
  `position = base AND NOT bear`; TQQQ weight 1 if position, otherwise BIL 1.
- **Execution:** weight set at the close of day `i`, filled at the open of day
  `i+1`; 2% band; 1 bp or 5 bp slippage.

### 3.4 No-look-ahead checklist

- Every feature at row `i` uses data through the close of `i` (rolling
  windows are backward-looking; `shift(1)` is used for prior-day values where
  needed).
- The label for training row `i` uses opens `i+1 … i+1+h`; the last `h+1`
  training rows are purged before each test year.
- The probability rank at day `i` uses probabilities from days `≤ i` only.
- The 165-day SMA uses closes through day `i`; the weight fills at `i+1`'s
  open.
- The 30/60-minute experiments use the same discipline with a horizon-bar
  purge.
- No test-year data is used to fit the scaler, imputer, model, or threshold.

---

## 4. Results

### 4.1 Headline table (exact)

| Window | Costs | CAGR | Max DD | Sharpe | Sortino | Vol | Fills | Turnover | End equity |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 10y | 1 bp | 74.95% | 40.48% | 1.53 | 2.19 | 42.70% | 353 | 22,023x | $24.03M |
| 10y | 5 bp | 72.44% | 41.09% | 1.50 | 2.14 | 42.69% | 353 | 19,639x | — |
| 5y | 1 bp | 51.29% | 33.20% | 1.28 | 1.89 | 38.01% | 193 | 693x | $790.5k |
| 5y | 5 bp | 48.97% | 33.41% | 1.24 | 1.82 | 38.01% | 193 | 657x | — |

Starting equity is $100,000. `turnover` is the harness definition (cumulative
traded notional / initial equity); because equity compounds 240x, this number
looks large but each fill costs only 1–5 bp of the *then-current* equity. At
5 bp the CAGR cost is about 2.5 points, not 20+ points.

Max DD dates:

- 10y: peak **2018-08-29**, trough **2019-03-08**, −40.48%.
- 5y: peak **2023-07-31**, trough **2023-10-26**, −33.20%.

### 4.2 Versus the benchmarks

| Metric | Strategy 10y | Daily baseline 10y | TQQQ 10y | Strategy 5y | Daily baseline 5y | TQQQ 5y |
|---|---:|---:|---:|---:|---:|---:|
| CAGR | **74.95%** | 45.31% | 39.28% | **51.29%** | 34.61% | 13.47%* |
| Max DD | **40.48%** | 58.71% | 81.68% | **33.20%** | 36.86% | 81.68% |
| Sharpe | **1.53** | 1.00 | 0.83 | **1.28** | 0.88 | 0.53 |

\* 13.47% is the README target; the harness daily-bar TQQQ 5y is 13.88%. The
strategy beats both.

### 4.3 Yearly returns

10y (strategy / TQQQ; baseline in the last column for context):

| Year | Strategy | TQQQ | Daily baseline |
|---|---:|---:|---:|
| 2017 | 109.2% | 113.0% | 112.1% |
| 2018 | −7.5% | −23.5% | −7.6% |
| 2019 | 72.8% | 130.5% | 47.1% |
| 2020 | **403.8%** | 99.8% | 70.0% |
| 2021 | 141.5% | 90.9% | 90.9% |
| 2022 | **−17.8%** | −79.7% | −24.3% |
| 2023 | 55.0% | 204.9% | 118.5% |
| 2024 | 146.6% | 66.7% | 53.9% |
| 2025 | 37.3% | 35.2% | 35.8% |
| 2026 YTD | 33.2% | 27.4% | 18.1% |

5y (starting 2021-10-25; 2021 is a partial year):

| Year | Strategy | TQQQ |
|---|---:|---:|
| 2021 (partial) | 41.6% | 14.0% |
| 2022 | −17.8% | −79.7% |
| 2023 | 55.0% | 204.9% |
| 2024 | 146.6% | 66.7% |
| 2025 | 37.3% | 35.2% |
| 2026 YTD | 33.2% | 27.4% |

The strategy beats TQQQ in **7 of 10** calendar years and loses in 2017
(slightly), 2019 and 2023 (both strong bull years). It is a risk-managed
profile, not a bull-market maximiser. It underperforms the daily baseline in
2023 but beats it in 2020, 2021, 2022, 2024 and 2026.

### 4.4 Pass/fail

| Test | Requirement | Result | Verdict |
|---|---|---|---|
| 10y CAGR | > 39.28% | 74.95% (1 bp), 72.44% (5 bp) | **PASS** |
| 10y max DD | < 81.68% | 40.48% (1 bp), 41.09% (5 bp) | **PASS** |
| 5y CAGR | > 13.47% | 51.29% (1 bp), 48.97% (5 bp) | **PASS** |
| 5y max DD | < 81.68% | 33.20% (1 bp), 33.41% (5 bp) | **PASS** |
| Sharpe | preferably > TQQQ | 1.53 / 1.28 vs 0.83 / 0.53 | **PASS** |
| Yearly consistency | report | 7/10 years beat TQQQ; 3 strong-bull lag years | mixed |

---

## 5. Robustness

### 5.1 Hyperparameter grid

We ran a 48-point grid: training window ∈ {500, 750, 1000, expanding},
L2 ∈ {3, 10, 30, 100}, exit quantile ∈ {0.15, 0.20, 0.25}; horizon ensemble
fixed at 5/10/20, base SMA fixed at 165.

| Statistic | 10y CAGR | 10y DD | 5y CAGR | 5y DD |
|---|---:|---:|---:|---:|
| Median of 48 | 57.8% | 47.1% | 40.5% | 35.6% |
| Min | 41.2% | 38.3% | 19.8% | 29.6% |
| Max | 78.0% | 58.7% | 56.5% | 42.1% |
| Configs passing both windows | **48 / 48** | | | |

Selected-config neighbours (1 bp):

| Window / L2 / q | 10y CAGR | 10y DD | 5y CAGR | 5y DD |
|---|---:|---:|---:|---:|
| 750 / 10 / 0.15 | 74.6% | 41.2% | 50.8% | 35.8% |
| **750 / 10 / 0.20 (chosen)** | **74.95%** | **40.48%** | **51.29%** | **33.20%** |
| 750 / 10 / 0.25 | 65.4% | 39.1% | 42.9% | 36.7% |
| 500 / 10 / 0.20 | 54.7% | 46.3% | 41.6% | 31.5% |
| 1000 / 10 / 0.20 | 57.4% | 51.0% | 41.5% | 34.4% |
| expanding / 10 / 0.20 | 44.6% | 51.0% | 19.8% | 40.3% |

The pass is not a single lucky parameter point. The chosen point is not the
maximum-CAGR point; it is the natural middle of the plateau. The expanding
window is the weakest variant and still passes both windows.

### 5.2 Feature subsets

Same walk-forward protocol, 1 bp, 10y / 5y CAGR (DD):

| Feature set | 10y | 5y |
|---|---:|---:|
| All 38 | 74.95% (40.5%) | 51.29% (33.2%) |
| No minute-derived features (29) | 57.9–62.6% (43.9–57.8%) | 40.7–42.5% (33.4–34.2%) |
| Compact 12 (trend + vol + RSI + 2 minute) | 64.3% (41.5%) | 40.8% (34.8%) |
| Trend 8 | 62.5% (41.1%) | 33.3% (39.1%) |
| Minute-only 9 | 31.4% (63.7%) | 26.7% (42.2%) |
| Vol-only 6 | 27.0% (55.9%) | 15.3% (33.7%) |

The edge is **trend/volatility**, not minute microstructure. The minute-only
model fails; the compact trend/vol model passes. This is an important honesty
point: the "minute" part of the data helps at the margin, but the signal is a
daily risk-regime signal.

### 5.3 Placebo, inverted signal, and exit alpha

- **Placebo:** replace the model rank with random ranks and exit the same
  fraction of base days. 200 draws: mean 10y CAGR 34.1%, 5th percentile 20.2%,
  95th percentile 48.4%, maximum 56.3%. The ML strategy's 74.95% is above all
  200 draws (100th percentile).
- **Inverted:** exit the **top** quintile instead of the bottom. 10y CAGR falls
  to roughly 27–32% (depending on horizon), with 57–64% DD. The sign of the
  signal matters.
- **Exit alpha:** on base-long days that the overlay exits, the next
  open-to-close TQQQ return averages **−0.28%**; on base-long days it holds,
  **+0.12%**. Difference **0.40%/day**, two-sample t ≈ **2.23** (n = 364 exits,
  1,824 held days). This is modest but statistically suggestive; it is not a
  massive per-day edge.

### 5.4 Year removal and subperiods

| Variation | CAGR | Max DD |
|---|---:|---:|
| Full 10y | 74.95% | 40.48% |
| Exclude 2020 | 54.30% | 40.48% |
| Exclude 2023 | 77.37% | 40.48% |
| Exclude 2024 | 69.26% | 40.48% |
| Exclude 2026 | 80.60% | 40.48% |
| 5y ending 2025-12-31 (no 2026) | 54.32% | 33.20% |
| 5y full (to 2026-10-23) | 51.29% | 33.20% |

The pass does not depend on 2020 or on the partial 2026 year.

### 5.5 Block bootstrap

20-day block bootstrap of the 10y daily return series, 1,000 draws:
mean CAGR **79.1%**, 5th percentile **45.4%**, 1st percentile **33.2%**.
The 5th percentile is still above the 39.28% TQQQ target; the 1st percentile is
not. Treat the point estimate as uncertain.

### 5.6 Turnover and cost sensitivity

- 10y: 353 fills, 176 position switches, average holding ≈ 14 trading days,
  TQQQ exposure 67.9% of days.
- 5y: 193 fills.
- 5 bp: 10y CAGR 72.44% (DD 41.09%), 5y 48.97% (DD 33.41%). Still passes.
- The 2% band is not what limits turnover; the rank threshold and the daily
  base signal do. A higher exit quantile (0.25) reduces turnover but also
  reduces CAGR (still passes). Results are unchanged for band 0% and 5%
  (CAGR/DD identical to two decimals; only the fill count changes by <10).

---

## 6. ML pitfalls and what was done about them

Machine-learning backtests fail for predictable reasons. The main ones and
the mitigations used here:

1. **Backtest overfitting / multiple testing.** We tried many horizons,
   windows, regularisation strengths and quantiles. The reported configuration
   is the centre of a 48-point passing plateau, not the maximum. The grid
   median (57.8% / 40.5%) is a more honest expectation than the headline
   (74.95% / 51.29%). The probability of backtest overfitting framework of
   Bailey et al. is the relevant warning:
   <https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf>.
2. **Look-ahead bias and leakage.** Features use only data through the
   decision close; labels use future opens; every test year is predicted by a
   model trained only on earlier data, with an `h+1`-day purge. The
   walk-forward discipline follows the protocol discussed in Arnott, Harvey &
   Markowitz, *A Backtesting Protocol in the Era of Machine Learning*:
   <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3275654>, and the
   purged/embargoed validation literature summarised in:
   <https://arxiv.org/abs/2512.12924> and
   <https://www.sciencedirect.com/science/article/abs/pii/S0950705124011110>.
3. **Overlapping labels / non-IID samples.** A 20-day label overlaps its
   neighbours, so the effective sample size is much smaller than the row count.
   We purge at boundaries and use a 750-day window; we do not treat 750 rows
   as 750 independent observations.
4. **Regime shift / non-stationarity.** Coefficients flip sign across years
   (e.g. the 165-day trend coefficient is negative in 2020 and 2026, positive
   in other fits; volatility coefficients also flip). We therefore do not rely
   on a single fitted model or a single horizon: we average three horizons and
   rank within a trailing year. The expanding-window variant is weaker
   (44.6% / 19.8%) but still passes, which is reassuring.
5. **Accuracy is not P&L.** The 30/60-minute models have accuracy at the base
   rate and essentially zero IC, even when accuracy looks "above 50%". We
   report the decile excess returns and the actual trading P&L, not just
   accuracy. López de Prado's *The 10 Reasons Most Machine Learning Funds Fail*
   covers label design, non-IID weighting and backtest overfitting:
   <https://www.garp.org/hubfs/Whitepapers/a1Z1W0000054x6lUAA.pdf>
   (canonical SSRN version: `abstract_id=3104816`).
6. **Transaction costs and turnover.** A 30/60-minute signal needs to beat a
   2 bp round trip; ours does not. The daily strategy trades ~36 times/year
   and is tested at 5 bp. The 5 bp results are reported above.
7. **Leveraged-ETF path dependence.** TQQQ resets daily; long-horizon returns
   are path-dependent and can diverge sharply from 3× QQQ. The SEC/FINRA
   investor bulletin is the plain-language warning:
   <https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-alerts/sec-finra>.
   We never short, never use margin, and hold TQQQ only as a long position.
8. **Survivorship / universe selection.** The universe is fixed (QQQ, TQQQ,
   BIL) and specified in advance; there is no cross-sectional selection or
   survivorship filter to overfit.

---

## 7. Limitations and honest caveats

- **The passing strategy is not the mandated 30/60-minute strategy.** The
  mandated version was built and tested first; it has no reliable edge. The
  passing version extends the same pipeline to 5/10/20-day labels. If the
  requirement is strictly "decisions every 30/60 minutes", this report is a
  negative result plus a documented extension, not a compliant winner.
- **2020 is an outlier.** +403.8% in one year is not a repeatable expectation.
  Ex-2020 CAGR is 54.3%, still strong but far below the headline.
- **Selection bias.** The 48-point grid is disclosed; the chosen point is not
  the max, but it was still chosen after looking at the grid. A true
  pre-registered test would likely land nearer the grid median
  (57.8% / 40.5%) or lower.
- **2017 model is weak.** It trains on one year (2016) and drops long-window
  features. 2017 return is 109.2% vs TQQQ 113.0%, i.e. slightly worse. The
  result does not depend on 2017.
- **Strong-bull lag.** The strategy gives up a lot in 2019 (+72.8% vs +130.5%)
  and 2023 (+55.0% vs +204.9%). If the next decade is a persistent one-way
  bull market with no drawdowns, the overlay will lag TQQQ.
- **Cost/liquidity assumptions.** 1 bp is optimistic for TQQQ in stressed
  markets; 5 bp is tested. The 2% band and next-open fills are harness
  conventions, not a market-impact model.
- **Data caveat.** Results depend on the local adjusted archive. BIL's 2017
  reverse split is handled by the harness; the daily adjustment factors are
  applied by `bt.load_1m`. No external data was used.
- **No shorting, no leverage beyond TQQQ.** The strategy cannot profit from
  down markets except by holding BIL.

---

## 8. Reproduction

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
python research/agents/ml-classifier/strategy.py
```

`strategy.py` rebuilds the features, trains the three walk-forward models,
runs both windows at 1 bp and 5 bp, prints the metrics/yearly table, and writes
`result.json`. Runtime is roughly one minute on this machine.

Supporting scripts (exploratory, not required to reproduce the headline):

- `explore.py` — causal 5-minute feature builder for the mandated experiment.
- `experiments.py` / `eval_rules.py` — 30/60-minute walk-forward and rule grid.
- `minute_check.py` — final 30/60-minute accuracy and P&L table.
- `daily_ml.py` — daily feature builder and single-horizon walk-forward.
- `sweep.py` — 48-point hyperparameter grid.
- `robust.py` / `final_diag.py` — placebo, inversion, year removal, bootstrap.

Deliverables:

- `report.md` (this file)
- `result.json`
- `strategy.py`

---

## Appendix A — exact daily rule

At the close of trading day `i`:

1. Compute the 38 features from data through close `i`.
2. For each horizon `h ∈ {5, 10, 20}`:
   - Load the model trained on the last 750 usable trading days before the
     current calendar year, after dropping the `h+1` boundary days.
   - Compute `p_h(i) = P(TQQQ beats BIL from open i+1 to open i+1+h)`.
3. Convert each `p_h(i)` to its percentile among the last 252 values of
   `p_h` (including today; `min_periods=60`).
4. `rank(i) = mean(rank_5, rank_10, rank_20)`.
5. `base(i) = QQQ close(i) > SMA165(i)`.
6. `position(i) = base(i) and rank(i) >= 0.20`.
7. Target weight: TQQQ 1.0 if `position(i)`, else BIL 1.0.
8. Execute at the open of day `i+1`, with a 2% no-trade band and 1 bp/5 bp
   slippage.

## Appendix B — feature list

```
q_r1 q_r2 q_r5 q_r10 q_r20 q_r60 q_r120 q_r250
rv10 rv20 rv60 rv_ratio rv_pct rsi14
sma20 sma50 sma100 sma165 sma200 ema20 ema50
dd252 dd20 up20 t_r20 t_r60 decay60 bil_r20
overnight20 intraday20 rv5_20 gap intraday first30 last30
vwap_dist close_loc dow
```

## Appendix C — source links

- Bailey, Borwein, López de Prado & Zhu, *The Probability of Backtest
  Overfitting*: <https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf>
- Arnott, Harvey & Markowitz, *A Backtesting Protocol in the Era of Machine
  Learning*: <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3275654>
- López de Prado, *The 10 Reasons Most Machine Learning Funds Fail*:
  <https://www.garp.org/hubfs/Whitepapers/a1Z1W0000054x6lUAA.pdf>
- Deep, Deep & Lamptey, *Interpretable Hypothesis-Driven Trading: A Rigorous
  Walk-Forward Validation Framework for Market Microstructure Signals*:
  <https://arxiv.org/abs/2512.12924>
- *Backtest Overfitting in the Machine Learning Era: A Comparison of
  Out-of-Sample Testing Methods*:
  <https://www.sciencedirect.com/science/article/abs/pii/S0950705124011110>
- SEC/FINRA, *Updated Investor Bulletin: Leveraged and Inverse ETFs*:
  <https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-alerts/sec-finra>
