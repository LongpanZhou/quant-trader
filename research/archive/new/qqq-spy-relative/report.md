# qqq-spy-relative — development report

**Window:** 2016-01-04 → 2023-12-29 (1-minute marks, next-open fills, 2% band,
$100k start).
**Holdout:** 2024-01-02 → 2026-10-23 was never loaded or inspected. SPY and the
daily Parquet reads are filtered at 2023-12-29; the 1-minute panel is hard-sliced
at that date.
**Costs:** 1 bp headline; 5 bp and 10 bp reported.
**Rules:** long-only, weights ≥ 0, sum ≤ 1.

---

## Verdict first

| | Strategy A | TQQQ buy-and-hold | Task bar |
|---|---:|---:|---:|
| CAGR | **44.36%** | 36.15% (local 1m close) / 36.72% (stated) | > 36.72% |
| Max drawdown | **55.03%** | 82.29% | < 82.29%, target < 60% |
| Sharpe (1m) | **1.06** | 0.80 | 0.82 |
| Calmar | **0.81** | 0.44 | — |
| Invested (incl. BIL) | 99.9% | 100% | — |
| Risky exposure (QQQ+TQQQ) | 82.2% | 100% | — |
| Daily corr to TQQQ | 0.78 | 1.00 | — |
| Daily beta to TQQQ | 0.51 | 1.00 | — |
| CAGR at 10 bp | **42.17%** | — | > 36.72% |

**Headline: pass.** A beats the CAGR bar by 7.64 pp and cuts max drawdown by
27.26 pp. It survives 10 bp costs (42.17%), exact cut tests, and a 200-draw
placebo (4.5% of shifts beat it).

**Attribution: fragile.** The absolute-trend-only ladder earns **46.64% /
55.03% / 1.044**, so the QQQ/SPY relative gate adds only **+0.019 Sharpe**
against a pre-registered +0.02 threshold, and it *costs* 2.3 pp of CAGR. The
CAGR pass is concentrated in 2022 avoidance: replacing 2022 with TQQQ's return
drops the 8-year CAGR to **22.84%**. This is a leveraged Nasdaq-beta timing
strategy whose relative signal is a de-risking overlay, not an independent
alpha source. It is reported as a candidate for the holdout, not as a
market-neutral edge.

---

## 1. What the strategy is

Four risk states from two binary gates, mapped to a leverage ladder:

| Relative gate R | Absolute gate A | Position at session k's close | Effective Nasdaq |
|---|---|---|---|
| + | + | TQQQ 1.00 | 3x |
| − | + | TQQQ 0.50 + QQQ 0.50 | 2x |
| + | − | QQQ 1.00 | 1x |
| − | − | BIL 1.00 | 0x |

- **R:** `M126(QQQ, k-1) > M126(SPY, k-1)`. Both legs are measured through
  session `k-1`, because SPY's official close is 16:00, one minute after the
  15:59 decision bar. Lagging both legs also keeps the two windows aligned; a
  stale-SPY/fresh-QQQ comparison is tested in §7 and is worse.
- **A:** `QQQ(k) > SMA150(QQQ, k)` using the 15:59 panel close at `k`.
- **Vol cap:** the TQQQ sleeve is multiplied by `min(1, 0.70 / rv20(TQQQ, k))`,
  where `rv20` is the annualized 20-session realized volatility of TQQQ daily
  total returns. Freed weight goes to QQQ when A is on, otherwise BIL.
- Targets are refreshed every session at the close and filled at the next
  session's open. 2% band. 452 fills over eight years.

The 2x rung is the compromise that matters: when tech is lagging but the market
is still in an uptrend, the book stays invested with half the leveraged sleeve
instead of jumping between 3x and 1x. The 1x rung is the rare "tech leading
while the broad market is below trend" state — 3.4% of sessions, mostly
V-bottoms — where the strategy stays in QQQ instead of going to cash.

---

## 2. Headline results

| cost | CAGR | max DD | Sharpe | Sortino | vol | invested | avg TQQQ | fills | turnover* |
|------:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **1 bp** | **44.36%** | **55.03%** | **1.06** | 1.48 | 43.7% | 99.9% | 0.688 | 452 | 558x |
| 5 bp | 43.38% | 55.10% | 1.05 | 1.46 | 43.7% | 99.9% | 0.688 | 452 | 537x |
| 10 bp | 42.17% | 55.19% | 1.03 | 1.43 | 43.7% | 99.9% | 0.688 | 454 | 511x |

\* cumulative traded notional / $100k starting equity; the book grows 18.8x
(mean equity 5.47x), so this is about 102x average equity over eight years
(~13x/year). The low fill count is why 10 bp costs only 2.2 pp of CAGR.

Benchmarks on the same 1-minute panel:

| | CAGR | max DD | Sharpe |
|---|---:|---:|---:|
| TQQQ (computed) | 36.15% | 82.29% | 0.80 |
| TQQQ (stated bar) | 36.72% | 82.29% | 0.82 |
| QQQ | 18.91% | 37.30% | 0.90 |
| SPY (daily marks) | 13.37% | 33.72% | 0.78 |
| **Strategy, 1 bp** | **44.36%** | **55.03%** | **1.06** |

Average target weights: **TQQQ 68.8% / QQQ 13.4% / BIL 17.8%**. Effective
Nasdaq exposure is about **2.20x** (QQQ 1x + TQQQ 3x). The strategy is almost
always fully allocated; "risk off" means BIL, not cash.

State shares over 2,012 sessions:

| state | share | 21-day forward TQQQ mean | median |
|---|---:|---:|---:|
| both + (3x) | 63.0% | +4.28% | +5.51% |
| absolute only (2x) | 15.8% | +6.32% | +9.34% |
| relative only (1x) | 3.4% | **+15.72%** | +10.84% |
| neither (0x) | 17.8% | +0.67% | +1.30% |

This table is the first warning about the relative gate. The 2x rung has a
*higher* forward TQQQ return than the 3x rung, and the 1x rung has the highest
forward return of all. The relative gate de-risks into states that subsequently
rebound. That is good for drawdown control and bad for CAGR — exactly what the
ablations show.

---

## 3. Yearly returns

| year | strategy | TQQQ | QQQ | avg TQQQ weight | dominant state |
|---:|---:|---:|---:|---:|---|
| 2016 | **-5.1%** | 18.6% | 9.3% | 0.58 | both+ 44%, abs+ 28%, BIL 19% |
| 2017 | 117.6% | 118.3% | 32.6% | 0.99 | both+ 98% |
| 2018 | **11.8%** | -19.6% | -0.1% | 0.77 | both+ 79%, BIL 14% |
| 2019 | 47.0% | 133.1% | 38.9% | 0.75 | both+ 64%, 2x 23%, BIL 13% |
| 2020 | 110.8% | 109.6% | 48.4% | 0.80 | both+ 91%, 1x 9% |
| 2021 | 57.4% | 83.0% | 27.4% | 0.74 | both+ 50%, 2x 50% |
| 2022 | **-24.8%** | -79.1% | -32.5% | 0.04 | BIL 92% |
| 2023 | 119.0% | 198.4% | 54.8% | 0.85 | both+ 78%, 2x 15% |

The shape is what the mechanism predicts. The strategy roughly matches TQQQ in
2017 and 2020, lags in the strong-bull years where the 2x rung and BIL periods
bind (2019, 2021, 2023), and avoids most of 2022. The full-window CAGR edge is
created by **2022**, not by out-earning TQQQ every year.

2022 month by month:

| month | strategy | TQQQ | QQQ |
|---:|---:|---:|---:|
| Jan | -16.0% | -25.5% | -8.6% |
| Feb | 0.0% | -15.1% | -4.4% |
| Mar | -1.0% | +10.5% | +4.4% |
| Apr | 0.0% | -37.3% | -13.5% |
| May | 0.0% | -9.2% | -1.6% |
| Jun | +0.1% | -27.6% | -8.9% |
| Jul | 0.0% | +39.4% | +12.6% |
| Aug | -7.4% | -16.6% | -5.1% |
| Sep | +0.2% | -30.5% | -10.6% |
| Oct | +0.2% | +8.3% | +4.0% |
| Nov | +0.3% | +12.9% | +5.6% |
| Dec | -3.1% | -26.5% | -9.0% |

The January loss is the cost of a slow trend filter: the book entered 2022 with
a full TQQQ position and only moved to the 2x rung on 2022-01-05 and to BIL on
2022-01-18. The August and December losses are whipsaw re-entries. Everything
else is BIL.

### 3.1 Subperiods

| window | strategy CAGR / DD / Sharpe | TQQQ CAGR / DD / Sharpe |
|---|---|---:|
| 2016-2019 | 36.22% / 39.04% / 1.01 | 48.98% / 58.62% / 1.05 |
| 2020-2021 | 82.08% / 55.03% / 1.30 | 93.48% / 72.74% / 1.21 |
| 2022-2023 | **28.44% / 32.29% / 0.91** | **-21.72% / 81.10% / 0.05** |

In the first four years the strategy lags TQQQ's CAGR by 12.8 pp, with a lower
drawdown. The full-window CAGR edge is created in 2022-2023, where TQQQ's
compounding is destroyed and the strategy is mostly in BIL. This is the same
shape as the leave-one-year-out and replace-one-year results: the edge is crash
avoidance, not a steady premium.

---

## 4. Pre-registered grid and plateau

Eight cells, fixed before the run; A is the primary. 1 bp.

| ID | rel | SMA | vol cap | CAGR | max DD | Sharpe | pass |
|---|---:|---:|---:|---:|---:|---:|---|
| **A** | **126** | **150** | **0.70** | **44.36%** | **55.03%** | **1.06** | **yes** |
| B | 126 | 150 | 0.60 | 43.83% | 52.86% | 1.07 | yes |
| C | 126 | 150 | 0.80 | 45.33% | 55.79% | 1.06 | yes |
| D | 105 | 150 | 0.70 | 44.44% | 55.03% | 1.06 | yes |
| E | 147 | 150 | 0.70 | 42.22% | 55.03% | 1.03 | yes |
| F | 126 | 180 | 0.70 | 43.46% | 55.03% | 1.05 | yes |
| G | 126 | 200 | 0.70 | 37.02% | 55.03% | 0.94 | yes (thin) |
| H | 126 | 150 | none | 43.71% | 61.26% | 1.02 | **no (DD)** |

Seven of eight cells pass. The CAGR range is 37.0-45.3% and the drawdown range
is 52.9-61.3%; there is no knife-edge cell. The one failure is the no-vol-cap
cell, which breaches the 60% internal DD target at 61.26%. At 10 bp, G falls to
34.70% (below the bar); every other cell stays above.

The pre-registered plateau is genuine but not perfectly smooth in the trend
dimension: SMA 140-180 spans 42.8-44.4%, while SMA 120 is 35.6% and SMA 200 is
37.0%. The 150-day centre is a ridge between a fast-SMA whipsaw zone and a
slow-SMA late-exit zone. The vol-cap dimension is smooth and monotone in DD:
0.55 → 51.7%, 0.60 → 52.9%, 0.70 → 55.0%, 0.80 → 55.8%, none → 61.3%.

---

## 5. Neighbour probe (descriptive, not candidates)

| variant | CAGR | max DD | Sharpe |
|---|---:|---:|---:|
| vol cap 0.80 | 45.33% | 55.79% | 1.065 |
| p = 0.60 | 44.98% | 55.03% | 1.066 |
| rel 105 | 44.44% | 55.03% | 1.063 |
| rel 252 | 44.33% | 55.03% | 1.056 |
| SMA 160 | 43.88% | 55.03% | 1.054 |
| vol cap 0.60 | 43.83% | 52.86% | 1.075 |
| p = 0.40 | 43.79% | 55.03% | 1.060 |
| vol cap none | 43.71% | 61.26% | 1.019 |
| SMA 180 | 43.46% | 55.03% | 1.047 |
| vol cap 0.55 | 42.83% | 51.71% | 1.071 |
| SMA 140 | 42.75% | 50.92% | 1.041 |
| rel 147 | 42.22% | 55.03% | 1.026 |
| rel 189 | 41.94% | 55.03% | 1.019 |
| rel 63 | 40.46% | 55.03% | 1.003 |
| rel 84 | 39.43% | 55.03% | 0.985 |
| SMA 200 | 37.02% | 55.03% | 0.937 |
| SMA 120 | **35.61%** | 54.69% | 0.928 |

The neighbourhood is a plateau on the vol-cap and relative-lookback dimensions
(39.4-45.3% CAGR), with one soft spot at rel 84 and a cliff at SMA 120. The
drawdown reduction (50.9-55.8% for every capped variant) survives all probes.
The `p` dimension is nearly flat: 43.79 / 44.36 / 44.98% for 0.4 / 0.5 / 0.6, so
the 2x rung is not a tuned knife-edge.

---

## 6. Is the edge just Nasdaq beta?

### 6.1 Correlation, beta and capture

| diagnostic | value |
|---|---:|
| daily corr to TQQQ | 0.78 |
| daily beta to TQQQ | 0.51 |
| daily corr to QQQ | 0.78 |
| daily beta to QQQ | 1.51 |
| up-capture of TQQQ days | 0.63 |
| down-capture of TQQQ days | 0.59 |
| effective Nasdaq exposure (avg weights) | 2.20x |

The beta is 0.51 and the correlation 0.78. This is unambiguously a
Nasdaq-beta-timing strategy: it owns less beta than TQQQ and changes that beta
over time. It is not a market-neutral spread.

### 6.2 Static blend at the strategy's own average weights

A constant **68.8% TQQQ / 13.4% QQQ / 17.8% BIL** book, rebalanced by the same
2% band:

| | CAGR | max DD | Sharpe |
|---|---:|---:|---:|
| static blend, same average weights | 31.56% | 68.92% | 0.81 |
| timed strategy | **44.36%** | **55.03%** | **1.06** |

The timing adds **+12.8 pp CAGR** and removes **13.9 pp of drawdown** versus the
same average exposure. So it is not constant beta — but it is still beta
timing, not a market-neutral premium.

### 6.3 Ablations: which gate does the work?

1 bp, same panel.

| variant | CAGR | max DD | Sharpe | beta |
|---|---:|---:|---:|---:|
| **primary (R + A + vol cap, p=0.5)** | **44.36%** | **55.03%** | **1.063** | 0.51 |
| absolute only (R always true) | **46.64%** | 55.03% | 1.044 | 0.64 |
| relative only (A always true) | 40.91% | 64.47% | 0.930 | 0.75 |
| p = 1.0 (ignore R when A+) | **47.02%** | 55.03% | 1.069 | 0.54 |
| p = 0.0 (full QQQ when R−/A+) | 41.11% | 55.03% | 1.033 | 0.48 |
| drop 1x rung (all A− → BIL) | 42.50% | 52.04% | 1.048 | — |
| no vol cap | 43.71% | 61.26% | 1.019 | 0.54 |
| weekly rebalance | 37.55% | 61.60% | 0.932 | 0.54 |
| ratio vs its own SMA (instead of M126) | 42.01% | 55.03% | 1.023 | 0.50 |
| absolute momentum 126 vs BIL (instead of SMA) | 40.39% | 54.90% | 0.990 | 0.52 |
| absolute trend on SPY 150 (instead of QQQ) | 42.25% | 51.78% | 1.036 | 0.51 |

Four conclusions:

1. **The absolute trend is the return engine.** Removing the relative gate
   entirely raises CAGR to 46.64% but also raises beta to 0.64; Sharpe falls
   from 1.063 to 1.044.
2. **The relative gate is a modest risk shaper, not a return source.** It adds
   +0.019 Sharpe — just below the pre-registered +0.02 — and costs 2.3 pp of
   CAGR. The p=1.0 ablation (ignore R when the trend is up) earns 47.02% and
   1.069 Sharpe. That would have been the better dev configuration, but it was
   not pre-registered; adopting it now would be post-hoc selection. The primary
   keeps the 2x rung as a risk control.
3. **The 1x rung is worth keeping.** Removing it (all A− → BIL) costs 1.9 pp
   CAGR and 0.015 Sharpe, and only saves 3.0 pp of DD. The 3.4% of sessions in
   the R+/A− state are mostly V-bottoms with strong forward returns.
4. **The vol cap is the best risk-adjusted component.** It adds 0.65 pp CAGR
   and cuts DD by 6.2 pp; without it the strategy fails the 60% DD target.
   Daily refresh is also load-bearing: weekly rebalancing drops CAGR to 37.55%
   and raises DD to 61.60%.

The honest one-line summary: **this is an absolute-trend TQQQ timer with a
QQQ/SPY relative-strength de-risking overlay.** The relative signal is real and
economically interpretable (tech leadership during a broad-market drawdown is a
V-bottom tell), but it is not an independent alpha source. The mandate asked
for exactly this test, and the answer is no.

---

## 7. Robustness

### 7.1 Placebo: circular shift of the target path

The per-session target sequence was circularly shifted by a random offset
(200 draws, seed 20261127), preserving the exact state sequence, exposure
distribution, vol cap and turnover but destroying alignment with returns.

| | median | p05 | p95 |
|---|---:|---:|---:|
| CAGR | 26.03% | 15.98% | 44.31% |
| max DD | 75.23% | 66.67% | 82.41% |
| Sharpe | 0.70 | — | — |

The primary (44.36% / 55.03% / 1.06) is just above the placebo CAGR p95
(44.31%) and **4.5%** of draws match or beat it. The placebo drawdown p05 is
66.67% and the median is 75.23%, both far worse than the strategy. The
alignment matters; the return edge is at the edge of statistical significance,
the drawdown edge is clear.

### 7.2 Cut tests (causality)

| cut | bars checked | max weight difference | pass |
|---|---:|---:|---|
| 2020-03-12 11:07 | 409,460 | 0.0 | yes |
| 2022-09-13 10:41 | 654,959 | 0.0 | yes |

Rebuilding the weights on a truncated panel reproduces the full-run weights
exactly. There is no full-sample normalisation and no future data in the signal.

### 7.3 Signal alignment

| alignment | CAGR | max DD | Sharpe |
|---|---:|---:|---:|
| **both legs through k−1 (primary)** | **44.36%** | **55.03%** | **1.06** |
| QQQ fresh at k, SPY through k−1 (causal) | 42.89% | 51.81% | 1.05 |
| both through k (SPY 16:00, 1-minute look-ahead) | 46.06% | 55.03% | 1.09 |
| one-session look-ahead (QQQ at k+1, diagnostic) | 63.47% | 57.00% | 1.36 |

The primary is fully causal. The fresh-QQQ causal variant (42.89%) is worse
than the aligned k−1 comparison, because mixing a fresh QQQ leg with a stale
SPY leg creates a one-day endpoint mismatch. Using SPY's same-day 16:00 close
as well (46.06%) adds 3.2 pp over that causal variant; the 16:00 print is one
minute after the decision bar, so this is a genuine look-ahead and is not used.
The one-session look-ahead (63.47%) shows the signal has strong next-day
predictive power, which is why the causal lag matters; it is reported only as a
diagnostic.

### 7.4 Leave-one-year-out and replace-one-year

| removed year | 7-year CAGR | | replaced year | 8-year CAGR |
|---:|---:|---|---:|---:|
| 2016 | 52.92% | | 2016 | 48.26% |
| 2017 | **35.83%** | | 2017 | 44.24% |
| 2018 | 49.38% | | 2018 | 38.34% |
| 2019 | 43.65% | | 2019 | 52.74% |
| 2020 | 36.44% | | 2020 | 44.07% |
| 2021 | 42.27% | | 2021 | 46.92% |
| 2022 | 58.10% | | 2022 | **22.84%** |
| 2023 | **35.70%** | | 2023 | 49.87% |

Five of seven leave-one-year-out CAGRs exceed 36.72%. Removing 2017 or 2023
pushes the CAGR just below the bar (35.8% / 35.7%). Replacing 2022 with TQQQ's
return destroys the pass (22.84%); replacing any other year still passes. The
edge is a **2022 crash-avoidance bet**, with 2017 and 2023 providing the bull
margin.

### 7.5 Sampling uncertainty

A 20-day block bootstrap of the daily strategy returns (500 draws) gives:

| | p05 | median | p95 |
|---|---:|---:|---:|
| CAGR | 13.8% | 45.2% | 81.8% |
| max DD | 34.6% | 54.8% | 79.5% |

Eight years of a 44% vol strategy cannot pin the CAGR down tightly. The median
is close to the point estimate, but the p05 is 13.8%; a future eight-year path
could easily produce a much lower CAGR even if the mechanism is unchanged. The
drawdown distribution's p95 is 79.5%, so 55% is not a worst case.

### 7.6 Worst drawdown episode

| | |
|---|---|
| peak | 2020-02-19 14:44 ET |
| trough | 2020-03-23 11:45 ET |
| depth | -55.03% |
| peak-to-trough | 32.8 days |
| recovered | 2020-07-09 15:00 ET |

This is the COVID crash, not 2022. The book was 100% TQQQ into the 2020-02-19
peak. The vol cap started scaling it down on 2020-02-26 (TQQQ 0.97 → 0.80 by
2020-02-28 → 0.62 by 2020-03-05), the absolute gate turned off on 2020-03-09,
and the relative gate kept the book in QQQ (1x) rather than BIL from 2020-03-11
to 2020-04-09. It re-entered TQQQ on 2020-04-13. The exit was late — after most
of the drop — which is why the DD is 55% rather than 30%. The vol cap is what
keeps it below 60%; without it the same path draws down 61.26%.

The 2022 bear is the opposite case: the book was 92% BIL for the year and lost
only 24.8%, versus QQQ -32.5% and TQQQ -79.1%. The damage is January (still in
TQQQ), August and December (whipsaw re-entries).

---

## 8. Falsifier checklist

Fixed in `HYPOTHESIS.md` before the run.

| # | falsifier | outcome |
|---:|---|---|
| 1 | CAGR ≤ 36.72% or DD ≥ 60% | **not triggered**: 44.36% / 55.03% |
| 2 | fewer than 5 of 8 grid cells pass | **not triggered**: 7 of 8 (H fails DD, G is thin) |
| 3 | 10 bp CAGR ≤ 36.72% | **not triggered**: 42.17% |
| 4 | ≥ 10% of placebo draws beat the CAGR | **not triggered**: 4.5% |
| 5 | any cut test differs by > 1e-12 | **not triggered**: both exact |
| 6 | relative gate adds < 0.02 Sharpe vs absolute-only | **TRIGGERED**: +0.019 (1.063 vs 1.044) |
| 7 | fewer than 5 of 7 leave-one-year-out CAGRs beat 36.72% | **not triggered**: 5 of 7 |

`result.json` therefore reports `robustness_status = "fragile"` with one
failure. The failure is narrow but real: the relative gate does not clear the
pre-registered risk-adjusted contribution threshold. The headline pass is
robust to costs, cuts, placebo and the grid, and fragile to attribution and to
the removal of 2022.

---

## 9. Limitations

1. **The relative signal is not alpha.** It is a de-risking overlay on a
   Nasdaq-beta timer. The absolute-only version earns more CAGR (46.64%) with
   the same drawdown; the relative gate buys 0.019 Sharpe and costs 2.3 pp
   CAGR. Do not market this as a market-neutral relative-value strategy.
2. **The pass is a 2022 bet.** Replacing 2022 with TQQQ drops the CAGR to
   22.84%. The strategy's geometric edge comes from avoiding one -79% year, not
   from a steady premium. A future bear that does not break the 150-day trend
   (a slow grind lower with repeated false recoveries) would hurt.
3. **The 2020 drawdown is 55%.** The trend filter exits late; the vol cap and
   the 1x rung soften but do not prevent the crash. A faster crash brake was
   deliberately not added because it would be a different mandate
   (`crash-early-warning`) and another tuned parameter.
4. **The 150-day SMA is a ridge.** SMA 120 (35.6%) and SMA 200 (37.0%) are
   much weaker than SMA 150-180 (43-44%). The centre is a plateau, but the
   dimension has cliffs. Do not re-tune on the holdout.
5. **Strong-bull lag.** The strategy underperforms TQQQ in 2019, 2021 and 2023
   because the 2x rung and BIL periods bind. In a 2024-2026 regime of persistent
   tech leadership and low vol, it will likely lag TQQQ's full-period CAGR even
   if it passes the dev bar.
6. **Exploratory design.** The state family and grid centre were chosen after
   daily-bar diagnostics on the same development window. The grid is a plateau
   probe, not a clean out-of-sample design. The holdout must be run once,
   frozen, by the lead.
7. **Bootstrap uncertainty.** The 20-day block bootstrap CAGR p05 is 13.8%;
   the point estimate is not a promise.

---

## 10. Relationship to existing work

`research/new/cross-asset-momentum` is the closest sibling: it also uses a
QQQ/SPY relative gate, absolute gates, a TQQQ/QQQ/BIL book and a vol target. It
uses a multi-horizon absolute ensemble (21/42 OR, 84/105/126 majority), weekly
rebalance, a full QQQ fallback and a 100% vol target; it earned 40.00% / 42.89%
/ 1.08. This strategy uses a **single 150-day QQQ trend**, a **four-rung
leverage ladder including a 50% TQQQ rung**, **daily refresh** and a **70% TQQQ
vol cap**. It earns 44.36% / 55.03% / 1.06 — more CAGR, more drawdown, similar
Sharpe.

`research/new/relative-value-tqqq` uses TQQQ/QQQ ratio momentum, not QQQ/SPY
relative strength, and earned 43.65% / 54.65% / 1.01. The two are independent
signals on the same leveraged asset; this one is simpler and has a slightly
better CAGR and Sharpe, with a similar drawdown.

These are the same economic family (leveraged Nasdaq beta timing). The honest
claim is a simpler, more explicit ladder with a slightly better dev result, not
a new source of edge.

---

## 11. Reproduction

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
$env:BT_THREADS = "1"
python research\new\qqq-spy-relative\strategy.py
```

`strategy.py` loads the 1-minute QQQ/TQQQ/BIL panel through `research/bt.py`,
splices pre-2016 Yahoo adjusted daily closes for warm-up, reads SPY with a
Parquet filter at 2023-12-29, simulates at 1/5/10 bp with next-open fills and a
2% band, and writes `result.json` with the grid, neighbours, ablations, placebo,
cuts, yearly returns, correlation/beta, static-blend attribution, leave-one-year-
out and replace-one-year tables. The 2024-2026 holdout was never inspected.
