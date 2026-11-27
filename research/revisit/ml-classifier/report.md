> **Post-test note (2026-11-27):** this file is the pre-registration, not
> the result. The frozen development result is in `../SUMMARY.md`; the
> full 2016-2026 audit, the post-tune variants and the research-validity
> verdicts are in `../WHY_UNDERPERFORM.md`. The published website curve is
> the freeze named in `../SUMMARY.md`.

# ml-classifier — standalone regime-cluster allocator

**Status:** `draft_pending_test` — hypothesis, specification, code and provenance
are written; **backtests are paused by the user/lead**, so this report contains
no new performance numbers for the regime strategy and `result.json` has not
been generated. §9 contains pre-pause exploratory numbers for the rejected
stripped-base prototype, not for this strategy.

**Original strategy:** `research/agents/ml-classifier` — a supervised
walk-forward logistic risk-off overlay on the 165-day QQQ SMA base. The original
`result.json` reports 74.95%/40.48% (10y) and 51.29%/33.20% (5y) at 1 bp, but
those numbers include the shared base and overlap the holdout. They are **not**
the result of the strategy described here.

---

## 1. The idea being kept, and what changes

The one genuinely new idea in the original is the **walk-forward machine-learning
risk model**: estimate market risk from causal features, retrain only on past
data, and let the model decide when to be defensive. The original wrapped that
model around a 165-day trend gate and used it only as an exit filter. That is an
overlay, not a standalone strategy.

This rebuild keeps the ML-risk-model idea but changes the problem it solves:

| Dimension | Original | Rebuild |
|---|---|---|
| Learning | Supervised logistic P(TQQQ > BIL) | **Unsupervised k-means market regimes** |
| Universe | TQQQ / BIL | **TQQQ / QQQ / BIL** |
| Signal | Probability rank vs trailing year | **Current regime + regimes' historical forward returns** |
| Base | QQQ 165-day SMA gate | **No 165-day gate; the regime itself decides** |
| Holding | Daily probability threshold | **Regime persistence (weeks)** |
| Sizing | Binary TQQQ/BIL | **100% in the regime's best asset; BIL otherwise** |
| Risk | Overlay on a trend base | **Self-contained long/defensive allocation** |

The old base weights and the old `build_weights` are not used.

---

## 2. Hypothesis

> Daily U.S. equity market states cluster into a small number of persistent
> regimes. A causal k-means fit on a rolling window of short-horizon returns,
> volatility, RSI, drawdown, EMA-distance and overnight/intraday features can
> identify the current regime in real time. The historical forward returns of
> each cluster — estimated only from past data — rank the regimes. Holding TQQQ
> in the historically strongest regime, QQQ in the second, and BIL in the rest
> should capture most of TQQQ's bull-market drift while cutting crisis exposure,
> without a 165-day moving-average gate.

The economic claim is **regime persistence and cross-regime asset sorting**, not
trend-following. If regimes are real, their forward-return ordering should be
stable enough out of sample to support a three-asset allocation. If they are
just volatility buckets with no forward-return content, the strategy should
collapse to QQQ-like performance or worse.

### Why this is not just the old overlay with a different hat

- No QQQ/TQQQ/SPY/NDX 100–250-day moving average is used in the signal.
- The signal is an unsupervised state, not a supervised direction probability.
- The portfolio can hold QQQ, a third asset the old strategy never held.
- The model is refit monthly, not annually, and the holding period is the life
  of a regime, not a daily threshold crossing.
- The regime map is learned from the clusters' own forward returns, not from a
  hand-set 0.20 rank cutoff.
- It is not a volatility-target or vol-ladder rule: volatility is one feature
  among many, and the asset choice comes from the cluster's forward-return rank.

---

## 3. Universe and data

- **QQQ** — middle-risk equity asset.
- **TQQQ** — 3× QQQ, aggressive asset; daily-reset leveraged ETF.
- **BIL** — T-bill defensive asset.
- Long-only, no leverage beyond 100% TQQQ, no shorts, no margin.
- Local adjusted 1-minute/daily QQQ/TQQQ/BIL data only. SPY exists in the local
  Dukascopy cache for 2026 only, which is insufficient for the 2016–2023
  development period, so it is not used. No new downloads.
- Development data: **2016-01-04 → 2023-12-29**. The first year is used only to
  train the first model; trading starts **2017-01-03**. The holdout
  (2024-01-02 → 2026-10-23) is not inspected.

---

## 4. Signal specification

### 4.1 State features (23, all causal, all ≤60-day lookbacks)

| Group | Features |
|---|---|
| Short-horizon returns | QQQ 1d, 5d, 20d, 60d log returns |
| Realized volatility | QQQ 5d, 20d, 60d daily-return vol; 20/60 vol ratio; 20d minus 60d vol |
| Stretch / trend | RSI(14); drawdown from 20d and 60d highs; distance from EMA(10), EMA(20), EMA(50) |
| Overnight / intraday | 20d average overnight gap; 20d average intraday return; 20d average 5-minute realized vol |
| Leverage / defensive | TQQQ−3×QQQ 20d return (leverage decay); BIL 20d return |
| Distribution / momentum | 20d return skew; QQQ 5d minus 20d return; day-of-week |

No 100–250-day price moving average is used. The 60-day features are the longest
price lookback. The 750-day window is a **training window**, not a price gate.

### 4.2 Clustering

- Standardize features on the training window.
- Fit **k-means** (`k = 3`) with deterministic k-means++ initialization
  (fixed seed, 8 restarts, 60 iterations).
- Refit on the **first trading day of each month** using only data through the
  prior trading day.
- Training window: last up to **750** rows, minimum **150** rows. Any row whose
  20-day forward label would end after the prior trading day is removed, so the
  regime map cannot peek into the month in which it is used.
- Assign each day's feature vector to the nearest centroid.

### 4.3 Regime-to-asset mapping

For each cluster, compute the average forward **20-trading-day open-to-open**
return of TQQQ, QQQ and BIL among its training members (labels purged as above).

- **Best cluster** (highest forward TQQQ return): TQQQ if that return is
  positive, otherwise BIL.
- **Second cluster** (only when `k ≥ 3`): QQQ if its forward QQQ return is
  positive, otherwise BIL.
- **All other clusters:** BIL.
- A cluster with fewer than 20 training members is treated as unavailable (BIL).

This is a causal, data-driven mapping. It does not use a hand-set probability
threshold.

---

## 5. Position, holding period, sizing and risk

- **Decision:** at the close of day `i`, compute features, assign the regime,
  and set the target asset.
- **Fill:** at the open of day `i+1`; 2% no-trade band.
- **Holding period:** until the cluster assignment changes; typically weeks,
  not minutes. The 20-day forward return is a ranking device, not a fixed
  holding period.
- **Persistence filter:** a new asset must be the mapped asset for **2
  consecutive sessions** before the book switches. This is a regime-persistence
  requirement, not a price stop; variant: 1 or 3 sessions.
- **Sizing:** 100% of equity in the mapped asset (TQQQ, QQQ or BIL). No partial
  positions in the primary; a continuous cluster-distance sizing is a planned
  variant.
- **Risk controls:** long-only; max 100% TQQQ; no stop-loss overlay; no shorts;
  no margin. The regime map itself is the risk control.
- **Confidence filter (variant, off in primary):** if the distance to the
  nearest centroid exceeds the 95th percentile of training distances, hold BIL.
  This is a robustness variant, not part of the primary.

---

## 6. Why this should have low correlation with the old base

The old baseline is TQQQ when QQQ is above its 165-day SMA, else BIL. The
rebuild:

- holds **QQQ** in the second-best regime, a return stream the old base never
  owns;
- can hold BIL while the old base is still long TQQQ (early regime change);
- can hold TQQQ in a volatile but historically strong regime where the old SMA
  might be whipsawed;
- uses a monthly-refit unsupervised state, not a slow price average.

**Expected dev daily-return correlation with the 165-day baseline: 0.35–0.60.**
This is an expectation, not a measurement. The hard limit is **< 0.60**; if the
measured correlation is higher, the design must shift more weight to QQQ/BIL
(e.g., force the second cluster to QQQ, add the confidence filter, or use a
longer regime holding period).

Cross-rebuild correlation (< 0.70) is pending the lead's
`research/revisit/correlations.json`. The closest rebuilds are likely the
volatility-sizing and crash-filter strategies; the unsupervised three-asset
regime map is intended to be distinct from both.

---

## 7. What would falsify the idea

The strategy should be **retired** if any of the following holds on the
development period:

1. **No regime ordering:** out-of-sample, the best cluster's forward TQQQ return
   is not higher than the worst cluster's, or the ordering flips across refits.
2. **No risk-adjusted improvement:** dev Sharpe is below QQQ buy-and-hold
   (0.90 on 2017–2023), or dev CAGR is below QQQ (20.1%) with no drawdown
   benefit.
3. **No drawdown benefit:** max drawdown is not below TQQQ (81.7%) or the old
   baseline (58.7%).
4. **Too correlated:** daily-return correlation with the 165-day baseline is
   ≥ 0.60.
5. **One-episode dependence:** the result is driven by 2020 or 2022; the
   2017–19 or 2022–23 sub-period is negative or worse than BIL.
6. **Parameter fragility:** k = 2/3/4, training window 250/500/750, monthly
   vs quarterly refit, or forward-return horizon 10/20/60 flips the sign of the
   result; there is no plateau.
7. **Placebo equivalence:** random cluster labels or random asset mappings
   produce similar results, i.e. the clusters have no forward-return content.
8. **Cost fragility:** the edge disappears at 5 bp or 10 bp because regime
   switches are too frequent.
9. **Unstable assignment:** small feature perturbations change the current
   asset, or the cluster mapping changes every month.

If the idea fails, the honest conclusion is that the original ML edge was
overlay-only, and the strategy should be marked `retired_overlay_only`.

---

## 8. Evaluation plan (when backtests are authorized)

- Development window: 2016-01-04 → 2023-12-29; trading from 2017-01-03;
  2016 only for the first training fit.
- Costs: **1 bp headline, 5 bp and 10 bp sensitivity**.
- Marks: **1-minute bars** via `research/minute_marks.py:to_minutes`, with
  `bt.run`/`bt.simulate` and the 2% band.
- Benchmarks: TQQQ, QQQ, BIL buy-and-hold; the 165-day baseline for correlation;
  the original `ml-classifier` result for context (not a like-for-like dev
  comparison because it uses the shared base and overlaps the holdout).
- Sub-periods: 2017–19, 2020–21, 2022–23.
- Variants and neighbourhood:
  - k = 2, 3, 4;
  - training window 250, 500, 750;
  - forward-return horizon 10, 20, 60;
  - monthly vs quarterly refit;
  - persistence 1, 2, 3 sessions;
  - negative-return filter on/off;
  - confidence filter on/off;
  - discrete vs continuous cluster-distance sizing.
- Placebo: random cluster labels, random asset mapping, shuffled features.
- Event count: number of regime switches; if < 100, report a bootstrap p-value.
- Correlation: daily session-close returns vs the 165-day baseline on dev;
  cross-rebuild correlation from the lead's file.
- Holdout: **not run by this agent**; the lead runs it once after the strategy
  is frozen.

The planned `result.json` fields are the brief's schema. `windows.holdout`,
`windows.10y` and `windows.5y` will remain `null` until the lead authorizes the
holdout run; the strategy is not allowed to inspect 2024–2026.

---

## 9. Prior exploratory evidence (before the pause)

A direct stripped-base version — the old supervised TQQQ-vs-BIL direction model
with no 165-day gate — was tested on the development period before the pause.
It did **not** stand alone:

- binary TQQQ/BIL rank thresholds 0.2–0.8: ~19–31% CAGR, 64–74% max DD;
- continuous rank sizing: ~20–28% CAGR, 59–65% max DD;
- a three-asset TQQQ/QQQ/BIL version of the same supervised model: ~20–34%
  CAGR, 59–75% max DD.

All were below TQQQ buy-and-hold (38.2% CAGR / 81.7% DD) on CAGR and below QQQ
(20.1% CAGR / 35.1% DD) on risk-adjusted terms, and far below the old baseline
(49.9% CAGR / 58.7% DD). That is why this rebuild changes the learning problem
to unsupervised regime clustering and adds QQQ as a middle-risk asset, rather
than merely removing the SMA gate.

These are **development-only exploratory numbers**, not the result of the new
strategy. The new strategy has not been run.

---

## 10. Provenance

### Sources that inspired or support the design

1. **Hamilton (1989), “A New Approach to the Economic Analysis of Nonstationary
   Time Series and the Business Cycle,” Econometrica 57, 357–384.**
   <https://www.ssc.wisc.edu/~bhansen/718/Hamilton1989.pdf>
   *Role:* inspired rule. Persistent latent regimes are a credible description
   of economic and market time series; supports the regime-state premise.

2. **Guidolin & Timmermann (2007), “Asset allocation under multivariate regime
   switching,” Journal of Economic Dynamics and Control 31(11), 3503–3544.**
   <https://ideas.repec.org/a/eee/dyncon/v31y2007i11p3503-3544.html>
   *Role:* inspired rule / supports assumption. Asset allocation can improve
   when regime probabilities are modeled explicitly; supports mapping regimes to
   assets rather than forecasting one direction.

3. **Nystrup, Hansen, Madsen & Lindström (2015), “Regime-Based Versus Static
   Asset Allocation: Letting the Data Speak,” Journal of Portfolio Management
   42(1), 103–111.**
   <https://www.pm-research.com/content/iijpormgmt/42/1/103>
   *Role:* supports assumption. Regime-based allocation can reduce drawdowns
   relative to static weights; implementation delays and costs matter.

4. **Horvath, Issa & Muguruza (2021), “Clustering Market Regimes Using the
   Wasserstein Distance,” arXiv:2110.11848.**
   <https://arxiv.org/abs/2110.11848>
   *Role:* inspired rule. Unsupervised clustering of financial time series into
   temporal regimes is a valid, assumption-light detection method; supports the
   k-means-style approach.

5. **LSEG Developers, “Market regime detection using Statistical and ML based
   approaches.”**
   <https://developers.lseg.com/en/article-catalog/article/market-regime-detection>
   *Role:* supports assumption. Practical comparison of k-means, GMM and HMM
   regime detection, including out-of-sample testing; explicitly warns that
   transaction costs and slippage are often omitted.

6. **Kaufman & Rousseeuw (1990), *Finding Groups in Data: An Introduction to
   Cluster Analysis*.**
   *Role:* method. Standard k-means clustering; used for the unsupervised
   partition. URL: `null` (book; no stable open link used here).

7. **Bailey, Borwein, López de Prado & Zhu, “The Probability of Backtest
   Overfitting.”**
   <https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf>
   *Role:* supports assumption. Motivates the variant grid, placebo, and the
   explicit discount for multiple testing.

8. **Arnott, Harvey & Markowitz (2019), “A Backtesting Protocol in the Era of
   Machine Learning.”**
   <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3275654>
   *Role:* supports assumption. Report all trials, avoid data-mined backtests,
   and use economic priors.

9. **López de Prado (2018), “The 10 Reasons Most Machine Learning Funds Fail.”**
   <https://www.garp.org/hubfs/Whitepapers/a1Z1W0000054x6lUAA.pdf>
   *Role:* supports assumption. Non-IID samples, regime shifts and backtest
   overfitting are the main failure modes; motivates the causal refit and
   purge.

10. **SEC/FINRA, “Updated Investor Bulletin: Leveraged and Inverse ETFs.”**
    <https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-alerts/sec-finra>
    *Role:* supports assumption. TQQQ resets daily; long-horizon returns are
    path-dependent. The strategy is long-only and never uses margin.

11. **`research/README.md` and `research/bt.py`** — harness, benchmarks, costs,
    next-open fills and the 165-day baseline used **only** for correlation.
    *Role:* benchmark/data. URL: `null`.

12. **Own design / no external source** — the exact 23 features, `k = 3`, the
    750/150/21 training/purge choices, the 20-day forward-return mapping, the
    QQQ middle asset and the monthly refit.
    *Role:* inspired rule. These are pre-test design choices; no external paper
    prescribes them.

### Tested and rejected

- **Old 165-day QQQ SMA base** (`research/README.md`). Rejected as a base for
  this rebuild: it is the shared gate the brief requires us to remove. It is
  retained only as the correlation benchmark.
- **Old supervised TQQQ-vs-BIL direction classifier** (original
  `ml-classifier`). Rejected as a standalone signal: the stripped-base
  prototypes above were below QQQ on risk-adjusted terms and below TQQQ on
  CAGR. It remains the historical starting point, not the new strategy.
- **HRP paper and industry-trend paper** previously attributed to the old web
  page. Rejected: hierarchical risk parity and industry trends are not used by
  this strategy. The provenance in this report supersedes those attributions.

---

## 11. What is deliberately not claimed

- No performance number for the new strategy is claimed yet. The numbers in
  §9 are exploratory results for the rejected stripped-base approach.
- The expected 0.35–0.60 correlation with the old base is a design expectation,
  not a measurement.
- The regime clustering may fail. The falsifiers in §7 are the conditions under
  which it should be retired rather than forced.
- The holdout has not been inspected. The lead runs it once after the strategy
  is frozen.

---

## 12. Reproduction (when authorized)

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
python research/revisit/ml-classifier/strategy.py
```

`strategy.py` builds the features, fits the monthly causal k-means, produces
daily TQQQ/QQQ/BIL weights, maps them to 1-minute marks with
`minute_marks.to_minutes`, runs the dev window at 1/5/10 bp, computes the
correlation against the 165-day baseline, and writes `result.json`. It does not
load or evaluate the holdout.

**Do not run this until the user/lead authorizes the new test.**
