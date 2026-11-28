# Vol-of-vol risk-state timing (VVT) — development report

**Verdict: PASS on the development bar.** 1-minute marks, 2016-01-04 →
2023-12-29, 1 bp costs, 2% band, next-open fills.

| | CAGR | Max DD | Sharpe | Sortino | TQQQ exposure |
|---|---:|---:|---:|---:|---:|
| **VVT primary (1 bp)** | **45.35%** | **53.55%** | **1.197** | **1.689** | **72.0%** |
| VVT primary (5 bp) | 44.01% | 54.11% | 1.172 | 1.653 | 72.0% |
| VVT primary (10 bp) | 42.34% | 54.80% | 1.140 | 1.608 | 72.0% |
| TQQQ buy & hold (our 1m run) | 36.15% | 82.29% | 0.801 | 1.122 | 100% |
| Task bar (TQQQ) | 36.72% | 82.29% | 0.82 | — | 100% |
| QQQ buy & hold | 18.91% | 37.30% | 0.900 | 1.260 | — |

The primary clears the bar by **+8.6 pp CAGR** with **28.7 pp less max drawdown**
and **+0.38 Sharpe**. It also clears it at 5 bp and 10 bp. Ending equity on
$100k is **$1.981M** at 1 bp, $1.839M at 5 bp and $1.676M at 10 bp. Calmar
(CAGR / max DD) is **0.85**, vs 0.44 for TQQQ and 0.51 for QQQ.

This is a **risk-managed TQQQ beta**, not a market-neutral alpha. It beats TQQQ
because TQQQ's own 82% drawdown is catastrophic and the vol state avoids part
of it. Once invested, it *underperforms* TQQQ in every strong up year,
including 2016; the 2016 calendar-year comparison is helped by the flat
warmup. The net CAGR edge is overwhelmingly from 2022 (200.6% of the net log
excess; excluding 2022 the cumulative relative wealth vs TQQQ is 0.618). That
is the honest description.

---

## 1. Mechanism: why vol-of-vol should predict leverage risk

TQQQ is a 3x daily-reset fund. Its compound return is approximately

```
log E[r_TQQQ] ≈ 3 μ_QQQ − 3 σ_QQQ²
```

so volatility is a direct tax on the product. Two different high-vol states
matter:

1. **Chronic high vol** (2022): the level is high and persistent. Vol-of-vol is
   actually *low* (2022 median 0.164 vs 0.219 overall), because the regime is
   steady. A vol-of-vol-only filter would miss this entirely; the level ladder
   is what protects.
2. **Acute unstable vol** (Feb 2018, Mar 2020, Sep 2020): the level spikes and
   vol-of-vol spikes with it. This is the state where vol-of-vol is
   informative: it tells us the regime is in transition, not merely high. The
   strategy de-risks on the spike and re-risks only when vol-of-vol has turned
   down from its 10-day peak and short vol is no longer accelerating.

The economic bet is that **the direction of vol-of-vol separates a continuing
shock from a V-recovery**. In a continuing shock, vov is still rising and
short vol is above the 20-day baseline; the strategy withholds the re-risk
boost. When vov rolls over while the level is still high, forced deleveraging
is exhausting and TQQQ's daily-reset convexity is at its best. The event study
supports this: the 78 vov-add days have a mean forward 10-day TQQQ return of
**+6.36%** vs **+1.87%** on other days (event-mean t = 3.55), and the 51
vov-spike cut days have a mean forward 5-day return of **−4.64%** vs **+1.16%**
(t = −2.19).

The failure mode is equally clear: vov can turn down in a bear-market rally.
The 2018-11 and 2022-02 add episodes lost 15–25% over the next 10 days. The
rule is a probabilistic V-recovery detector, not a bottom call.

---

## 2. Exact rules

All signals use completed daily bars through session *d*; the target is set at
*d*'s close and fills at *d+1*'s open. No intraday decisions, no shorting, no
leverage above 100%.

```
park_d   = sqrt( log(high_d / low_d)^2 / (4 ln 2) )       # Parkinson daily sigma
rv_k     = sqrt(252) * mean(park_d, k)                     # k = 5, 10, 20
sigma_s  = 0.25 * rv_10 + 0.75 * rv_20
vov      = std(rv_5, 20) / mean(rv_5, 20)
vov_peak = max(vov, last 10 sessions)
vov_10   = vov 10 sessions ago

base = clip( (0.65 - sigma_s) / (0.65 - 0.40), 0, 1 )

if rv_5 < 0.80 * rv_20:                                   # deceleration
    base = base + (1 - base) * 0.50

if rv_20 > 0.55 and vov > 0.25 and vov <= 0.95 * vov_peak and rv_5 <= rv_20:
    base = base + (1 - base) * 0.50                       # V-recovery

if rv_5 > 1.30 * rv_20:                                   # acceleration cut
    base = base * 0.70

if vov > 0.45 and vov > 1.20 * vov_10:                     # vov spike cut
    base = base * 0.70

TQQQ = clip(base, 0, 1); BIL = 1 - TQQQ
```

The daily high/low are the true TQQQ session high/low, read from the daily
parquet with a `date <= 2023-12-29` predicate. The 1-minute panel is truncated
at 2023-12-29 before any signal. The first 30 sessions are flat while the
windows warm up: the first target is set at the 2016-02-17 close and fills
2016-02-18.

---

## 3. Yearly and regime attribution

| Year | VVT | TQQQ | Avg TQQQ weight | VVT calendar DD |
|---|---:|---:|---:|---:|
| 2016 | **+43.79%** | +19.86% | 82.4% | 20.76% |
| 2017 | +96.34% | +114.54% | 95.8% | 18.23% |
| 2018 | **−13.13%** | −20.76% | 68.9% | 37.61% |
| 2019 | +116.57% | +148.23% | 89.6% | 27.89% |
| 2020 | +82.61% | +104.14% | 55.6% | 35.18% |
| 2021 | +64.69% | +81.05% | 85.8% | 23.43% |
| 2022 | **−46.21%** | −79.39% | 17.6% | 48.00% |
| 2023 | +111.26% | +192.05% | 80.9% | 33.65% |

Subperiods (1-minute marks):

| Period | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| 2016-2019 | 53.22% | 37.61% | 1.382 |
| 2020-2021 | 74.50% | 35.18% | 1.494 |
| 2022-2023 | 6.92% | 48.00% | 0.368 |

**2016.** The first 30 sessions are flat (the first target is set at the
2016-02-17 close and fills 2016-02-18). TQQQ fell 20.9% from 2016-01-04 to
2016-02-17, so the warmup mechanically helped the calendar-year comparison.
This is causal — no signal is available before the windows fill — but it is a
one-time start-date effect, not a persistent edge. After the first entry, from
2016-02-18 to 2016-12-30, the strategy returned **+46.7% vs TQQQ +55.1%**: it
lagged once it was invested. The calendar-year +43.8% vs +18.6% is mostly the
flat warmup avoiding the January–mid-February decline. Starting at the first
entry gives 46.20% CAGR only because the flat period is excluded from the
denominator; the final equity is essentially unchanged. Do not read 2016 as
evidence of superior timing.

**2017.** A low-vol melt-up. The strategy holds 95.8% average TQQQ and still
lags TQQQ by 18 pp because it occasionally de-risks around vol blips. This is
the cost of the state: in a near-zero-vol uptrend, any de-risking is expensive.

**2018.** The vov add fires 31 times in February, early March and November.
The February adds mostly worked (+2 to +17% forward 10 days); the early-March
and November adds failed (−8% to −25% forward 10 days). Net, 2018 is −13.1% vs
TQQQ −20.8%, with a 37.6% calendar drawdown. This is the clearest whipsaw
example.

**2019.** 89.6% average weight, only 2 vov-add days. The strategy captures most
of the +148% TQQQ year but gives up 32 pp by being out on some strong days.

**2020.** The level ladder cuts in late February, but the 20-day estimator is
slow: the calendar drawdown is 35.2%. The vov add then fires 29 times from
25 March to 23 April, with forward 10-day TQQQ returns of +18% to +64%. That is
the V-recovery the strategy is designed to capture. 2020 is +82.6% vs TQQQ
+104.1% — it still lags the full-year TQQQ because it was underweight in the
rebound, but it avoids the worst of March.

**2021.** 10 vov-add days in March, 85.8% average weight, +64.7% vs +81.1%.
A low-vol grind where the strategy gives up upside.

**2022.** The protection year. Average weight 17.6%, 137 flat sessions.
Vol-of-vol is *low* (2022 median 0.164), so the V-recovery block is mostly
silent (6 add days, all 6 lost at 10 days). The level ladder is the only
protection, and it is slow: −46.2% vs TQQQ −79.4%, with a 48.0% calendar
drawdown. The peak-to-trough max drawdown of 53.55% runs from 2021-11-22 to
2022-11-29.

**2023.** The recovery year the strategy misses part of: +111.3% vs +192.0%.
Average weight 80.9%, no vov adds. The level ladder re-risks slowly after the
2022 vol regime, so it is underweight during part of the January rally. This
is the largest opportunity cost in the sample.

---

## 4. Pre-registered grid and plateau

Only one parameter changes per row. All cells use the same architecture and
the same fixed parameters. 1 bp, 1-minute marks.

| # | cell | `vol_hi` | `dec_ratio` | `vov_th` | `w10` | `w20` | CAGR | Max DD | Sharpe |
|---|------|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | **primary** | 0.65 | 0.80 | 0.25 | 0.25 | 0.75 | **45.35%** | **53.55%** | **1.197** |
| 1 | vol_hi_lo | 0.62 | 0.80 | 0.25 | 0.25 | 0.75 | 45.14% | 49.67% | 1.209 |
| 2 | vol_hi_hi | 0.68 | 0.80 | 0.25 | 0.25 | 0.75 | 46.03% | 56.54% | 1.194 |
| 3 | dec_lo | 0.65 | 0.78 | 0.25 | 0.25 | 0.75 | 45.35% | 53.69% | 1.200 |
| 4 | dec_hi | 0.65 | 0.82 | 0.25 | 0.25 | 0.75 | **48.00%** | 52.94% | **1.238** |
| 5 | vov_hi | 0.65 | 0.80 | 0.30 | 0.25 | 0.75 | 43.30% | 53.22% | 1.168 |
| 6 | blend_lo | 0.65 | 0.80 | 0.25 | 0.20 | 0.80 | 45.11% | 53.57% | 1.192 |
| 7 | blend_hi | 0.65 | 0.80 | 0.25 | 0.30 | 0.70 | 45.62% | 53.51% | 1.202 |

The plateau is **43.3–48.0% CAGR, 49.7–56.5% DD, 1.17–1.24 Sharpe**. Every cell
clears the bar. The primary is the mechanism-chosen centre, **not the best
cell**: `dec_hi` is 2.65 pp better on CAGR and 0.04 better on Sharpe. I did not
switch to it post hoc. The spread is a fair estimate of parameter noise.

The weakest direction is `vov_th=0.30` (43.30%), which raises the bar for the
V-recovery add; it still clears 36.72% by 6.6 pp. The widest drawdown is
`vol_hi_hi` at 56.54%, still under 60% and far under the 82.29% bar.

---

## 5. Ablations: what is doing the work

1 bp, 1-minute marks. `L` = level ladder only; `D` = + deceleration boost;
`V` = level + vov V-recovery (no dec); `DV` = level + dec + vov; `DVC` = primary
(adds the acceleration and vov-spike cuts).

| Variant | CAGR | Max DD | Sharpe | Avg TQQQ |
|---|---:|---:|---:|---:|
| L: level only | 39.29% | 53.32% | 1.084 | 70.6% |
| D: + dec boost | 42.52% | 53.87% | 1.121 | 73.6% |
| V: level + vov | 44.14% | 54.85% | 1.158 | 72.4% |
| DV: level + dec + vov | **47.95%** | 54.20% | **1.199** | 74.8% |
| DVC: primary (with cuts) | 45.35% | **53.55%** | 1.197 | 72.0% |

- The **level ladder alone** is already a pass (39.29% / 53.32%), so the core
  result is not fragile to the vov machinery.
- The **dec boost** adds +3.2 pp CAGR for +0.55 pp DD (D vs L).
- The **vov V-recovery** adds +4.85 pp on top of the level ladder (V 44.14%
  vs L 39.29%) and +5.43 pp on top of D (DV 47.95% vs D 42.52%), for roughly
  the same drawdown. It is the largest single addition after the level ladder.
  V vs D is only +1.62 pp because the two re-risk rules overlap; the DV
  combination is the one that matters.
- The **two cuts** cost 2.6 pp CAGR (DV 47.95% → DVC 45.35%) and reduce max DD
  by 0.65 pp (54.20% → 53.55%). Sharpe is essentially unchanged (1.199 vs
  1.197). The cuts are a mandate-consistent risk control, not a return source.
  The vov-spike cut has strong event evidence (forward 5-day −4.64% vs +1.16%,
  t = −2.19); the acceleration cut does not (forward 10-day +0.33% vs +2.29%,
  t = 0.36). This is reported honestly: the acceleration cut is the weakest
  rule in the strategy and a candidate for removal in a future version.

### Event study (daily TQQQ, next open to open *h* days later)

| Signal | n | h=5 mean | non-signal | h=10 mean | non-signal | t(h=10, mean>0) |
|---|---:|---:|---:|---:|---:|---:|
| vov add | 78 | **+3.88%** | +0.90% | **+6.36%** | +1.87% | 3.55 |
| dec boost | 444 | +0.85% | +1.06% | +2.39% | +1.94% | 4.54 |
| acc cut | 258 | +0.67% | +1.06% | +0.33% | +2.29% | 0.36 |
| vov spike cut | 51 | **−4.64%** | +1.16% | −5.41% | +2.24% | −1.85 |

The vov add is a genuine forward-return signal at 5–10 days. The vov spike
cut is a genuine short-horizon de-risk signal. The acceleration cut is a
risk-control rule with weak forward-return evidence; it mainly reduces
exposure in fast up-moves, which is why it costs CAGR.

---

## 6. Robustness

### 6.1 Costs

| Cost | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| 1 bp | 45.35% | 53.55% | 1.197 |
| 5 bp | 44.01% | 54.11% | 1.172 |
| 10 bp | 42.34% | 54.80% | 1.140 |

Turnover is **1,347×** at 1 bp, **1,282×** at 5 bp and **1,204×** at 10 bp;
1,363 fills over 2,012 sessions (0.68/day). The 2% band is doing real work.
The strategy remains well above the bar at 10 bp. It is not a
microstructure-dependent edge.

### 6.2 Start-date sensitivity

| Start | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| 2016-01-04 | 45.35% | 53.55% | 1.197 |
| 2016-02-01 | 45.88% | 53.55% | 1.203 |
| 2016-02-18 (first entry) | 46.20% | 53.55% | 1.206 |
| 2016-07-01 | 47.05% | 53.55% | 1.227 |
| 2017-01-03 | 45.20% | 53.55% | 1.184 |
| 2018-01-02 | 37.70% | 53.55% | 1.022 |

Starting at 2016-02-18 gives 46.20% only because the flat warmup is excluded
from the denominator; the absolute growth is essentially unchanged. The
meaningful robustness check is the **2018-01-02 start**: the strategy still
earns **37.70% CAGR / 53.55% max DD / 1.022 Sharpe**, above the 36.72% bar.
So the full-period result is not dependent on the 2016 warmup, but the 2016
calendar-year *comparison* is.

### 6.3 Leave-one-year-out CAGR

| Dropped year | CAGR | Dropped year return |
|---|---:|---:|
| 2016 | 43.77% | +43.79% |
| 2017 | 37.47% | +96.34% |
| 2018 | 54.49% | −13.13% |
| 2019 | 35.58% | +116.57% |
| 2020 | 38.96% | +82.61% |
| 2021 | 41.00% | +64.69% |
| 2022 | 65.46% | −46.21% |
| 2023 | 36.02% | +111.26% |

The strategy is not a one-year wonder — every leave-one-out CAGR is in the
35.6–65.5% range — but dropping 2019 (35.58%) or 2023 (36.02%) leaves CAGR
slightly below the bar. The edge is broad but not enormous, and it depends on
the full sample's mix of bull and bear years.

### 6.4 Static exposure-matched mix

Constant 72.08% TQQQ / 27.92% BIL (the primary's average daily target):

| | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| Static 72.08% TQQQ | 31.21% | 68.72% | 0.809 |
| VVT primary | **45.35%** | **53.55%** | **1.197** |

The static mix has the same average exposure but is 14.1 pp lower CAGR and
15.2 pp higher DD. The state transitions are doing real work; the strategy is
not just "TQQQ at 72%."

### 6.5 Placebos

200 draws each, 1 bp, 1-minute marks.

| Placebo | Mean CAGR | 5th pct | 95th pct | Actual |
|---|---:|---:|---:|---:|
| Shuffle daily weights | 25.97% | 10.35% | 44.55% | **45.35%** |
| Circular block bootstrap, 20d | 26.65% | 11.48% | 41.70% | **45.35%** |
| Permute vov-add days within year | 39.73% | 36.07% | 43.32% | **45.35%** |

The actual is above the 95th percentile of all three placebos. The shuffle and
block bootstraps preserve the exposure distribution but destroy the timing;
the vov permutation preserves the rest of the strategy and randomises only the
V-recovery days. The vov permutation is the cleanest test of the V-recovery
mechanism: the actual beats its 95th percentile by 2.0 pp, so the specific
vov-selected days matter (p ≈ 0.02).

Caveat: the shuffle placebo is harsh because random weights cause more
turnover and costs. The block bootstrap is the fairer timing null; actual
45.35% vs p95 41.70% is a clearer margin.

### 6.6 Cut sensitivity (post-hoc, not used for selection)

| Variant | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| primary (acc 1.30, vov spike 0.45) | 45.35% | 53.55% | 1.197 |
| acc 1.20 | 42.29% | 53.64% | 1.157 |
| acc 1.40 | 46.74% | 54.50% | 1.206 |
| vov spike 0.40 | 44.58% | 53.55% | 1.187 |
| vov spike 0.50 | 45.64% | 53.55% | 1.201 |
| no cuts (DV) | 47.95% | 54.20% | 1.199 |

The cuts are a modest drag; the primary is not knife-edge. The acceleration
cut at 1.20 is too aggressive (42.29%); at 1.40 it is too loose (46.74% but
higher DD). 1.30 is a reasonable middle. The vov-spike cut is nearly free.

### 6.7 Look-ahead checks

Rebuilding the strategy on a 1-minute panel truncated at the cut date leaves
all weights before the cut unchanged:

| Cut | Prefix identical |
|---|---|
| 2020-03-12 | yes |
| 2022-09-13 | yes |

The daily high/low file is read with a parquet predicate `date <= 2023-12-29`;
the 1-minute panel is truncated at the same date before any signal. There is
no 2024-2026 data in any input. The signal at session *d* uses only that
session's completed OHLC and earlier bars; the fill is at *d+1*'s open.

### 6.8 Pre-registered falsifier audit

| # | Falsifier | Result | Status |
|---|---|---|---|
| 1 | CAGR <= 36.72% or DD >= 82.29% | 45.35% / 53.55% | pass |
| 2 | 10 bp CAGR < 36.72% | 42.34% | pass |
| 3 | vov ablation improves CAGR by < 1 pp | DV vs D: +5.43 pp | pass |
| 4 | removing the de-risk cuts reduces DD by < 1 pp | 54.20% → 53.55% = 0.65 pp | **partially triggered** |
| 5 | any grid cell < 36.72% CAGR or > 65% DD | min 43.30%, max DD 56.54% | pass |
| 6 | negative subperiod, or > half of excess from one year | subperiods positive; **2022 = 200.6% of net log excess**; ex-2022 relative wealth 0.618 | **triggered on concentration** |
| 7 | corr > 0.90 and static Sharpe higher | corr 0.717; static Sharpe 0.809 vs 1.197 | pass |
| 8 | no-trade same exposure better at 5 bp | static 31.21% vs 44.01% | pass |

Two pre-registered falsifiers do not cleanly pass:

- **#4 (de-risk cuts):** the two cuts reduce max drawdown by only 0.65 pp, less
  than the 1 pp threshold. They cost 2.6 pp CAGR. The vov-spike cut has event
  evidence; the acceleration cut does not. The "de-risk when vol accelerates"
  part of the mandate is therefore weaker than hypothesised.
- **#6 (concentration):** the net relative log return over TQQQ is **entirely
  from 2022**. In 2022 the strategy returns −46.2% vs TQQQ −79.4%, a 2.61×
  relative year; that single year contributes 200.6% of the net log excess.
  Excluding 2022, the strategy's cumulative relative wealth vs TQQQ is
  **0.618** — it underperforms. The 2022-2023 subperiod CAGR is still positive
  (+6.9%), so the literal subperiod condition passes, but the "single year"
  condition is triggered.

This is the most important caveat in the report: the literal bar is passed,
but the CAGR claim is a **2022 crash-avoidance bet**, not a broad all-weather
edge. The risk-adjusted result (Sharpe 1.197, DD 53.55%) is real, but it is
earned by being underweight in one specific bear market.

### 6.9 Daily-panel cross-check

The same signals on the daily panel (daily marks, 1 bp, 2% band) give
**45.42% CAGR / 51.04% max DD / 1.175 Sharpe**, 1,191 fills and 1,313×
turnover. The 1-minute result is 45.35% / 53.55% / 1.197. The signal is
identical; the small differences are minute marking and the finer fill path.
This confirms the result is not an artefact of minute marking.

---

## 7. Where the strategy fails

1. **2022-style persistent high vol.** Vol-of-vol is low in 2022, so the
   V-recovery block is silent; only the slow 20-day level ladder protects. The
   strategy still loses 46.2% in 2022 and has a 53.55% peak-to-trough
   drawdown. It is not a tail hedge.
2. **Whipsaw in the vov add.** 2018-11 and 2022-02 are losing clusters: the
   vov turn-down fired in a continuing bear. The add is +50% of the remaining
   weight, so a bad add is expensive. The event mean is positive but the
   5-day hit rate is only 59%.
3. **V-recovery timing is not a bottom call.** 2020-03/04 was the best case
   (+18% to +64% forward 10 days); 2022-02 was the worst (−6% to −16%). The
   10-day vov peak is a stabilisation filter, not a valuation signal.
4. **Acceleration cut is weak.** The event study shows no forward-return edge
   at 10 days (t = 0.36), and the cut costs ~1.5–2.6 pp CAGR depending on the
   comparison. It is included because the mandate asks for an acceleration
   de-risk rule, not because it is a strong predictor. The vov-spike cut is the
   part with real evidence.
5. **Strong bull years and 2022 concentration.** The strategy underperforms
   TQQQ in 2017 (−18 pp), 2019 (−32 pp), 2020 (−22 pp), 2021 (−16 pp) and
   2023 (−81 pp) once invested. The net CAGR edge is overwhelmingly from 2022
   (200.6% of the net log excess); excluding 2022 the cumulative relative
   wealth vs TQQQ is 0.618. If the next decade has no 2022-style bear, the
   strategy will lag TQQQ.
6. **Turnover.** 1,347× is high. At 10 bp the CAGR falls to 42.34%; the edge
   survives, but it is cost-sensitive. A capacity-constrained implementation
   should use a wider band or less frequent rebalancing.
7. **2016 warmup.** The first 30 sessions are flat. TQQQ fell 20.9% from
   2016-01-04 to 2016-02-17; the strategy enters on 2016-02-18 and then
   returns +46.7% vs TQQQ +55.1% through year-end. The calendar-year 2016
   comparison is flattered by the warmup. Starting at the first entry still
   gives 46.20% CAGR because the flat period is excluded from the denominator,
   not because the post-entry timing is superior. The 2018-start test
   (37.70%) is the meaningful check.

---

## 8. How this differs from the existing strategies

I read `research/revisit/` and `research/agents*` before designing this.

- **`dynamic-leverage-throttle`** (revisit): buys TQQQ *after* a volatility
  shock is decaying *inside a market drawdown*, sized inversely to the still
  high vol; it is an event/recovery strategy that sits in BIL during calm
  uptrends. VVT is the opposite base: it is long TQQQ in calm low-vol
  uptrends and uses the shock state only to decide when to re-risk. VVT has no
  drawdown gate, no inverse-vol sizing formula, and no 165-day trend gate.
- **`vol-kelly-overlay`** (revisit): waits for a 1-minute realised-vol spike
  plus an oversold QQQ drawdown plus the first up-close, then holds 1–3
  sessions. VVT has no 1-minute event trigger, no oversold condition, no fixed
  holding period, and no price stop. It is a persistent daily risk-state
  allocation, not an event trade.
- **`vol-scaled-crash-stop`**: always-long TQQQ with an ATR-scaled stop. VVT
  is not always long, has no stop, and sizes by a range-vol state rather than
  a stop distance.
- **`ratio-pairs` / ratio-froth**: uses the TQQQ/QQQ ratio. VVT does not use
  the ratio or any relative-value signal.
- **`risk-parity-hrp`**: static/HRP allocation across QQQ and TQQQ. VVT is a
  dynamic TQQQ/BIL state machine with a vol-of-vol trigger.
- **`ensemble-signals` / `drawdown-regime`**: those use vol spikes as
  *recovery entries* or drawdown gates. VVT uses the vol *level* as a
  continuous risk budget and the vol-of-vol *direction* as the V-recovery
  trigger; it is long in calm markets, which those strategies are not.

The closest existing idea is the vol ladder inside `vol-kelly-overlay`, but
that strategy uses a 1-minute RV spike and an oversold price condition; VVT
uses a daily Parkinson range state and the direction of vol-of-vol. The
distinct state is the point.

---

## 9. Honest verdict

**Literal pass; not a broad all-weather edge.**

- The strategy beats the task bar on CAGR (45.35% vs 36.72%), max drawdown
  (53.55% vs 82.29%) and Sharpe (1.197 vs 0.82) at 1 bp, and it still passes
  at 5 bp and 10 bp.
- **Two pre-registered falsifiers are not cleanly passed.** #4: the de-risk
  cuts reduce max DD by only 0.65 pp, less than the 1 pp threshold. #6: 2022
  contributes 200.6% of the net log excess; excluding 2022 the strategy's
  cumulative relative wealth vs TQQQ is 0.618. The CAGR edge is essentially a
  **2022 crash-avoidance bet**, not a broad timing premium.
- It is a **risk-managed TQQQ beta**, not a new alpha source. The static
  exposure-matched mix earns 31.21% / 68.72%; the timing adds +14.1 pp CAGR
  and −15.2 pp DD, but the return is still TQQQ beta.
- The **vov V-recovery block is the genuinely new mechanism** and it has
  forward-return evidence (10-day +6.36% vs +1.87%, t = 3.55) and a placebo
  p ≈ 0.02. It is also the source of the worst whipsaws (2018-11, 2022-02).
- The **acceleration cut is the weakest rule**; it costs return and has no
  forward-return edge in the event study. The vov-spike cut is the useful
  de-risk rule (5-day −4.64% vs +1.16%, t = −2.19).
- The **2022 drawdown is still 53.55%**. The strategy is not a crash hedge and
  should not be sold as one. It is a way to own TQQQ with a smaller permanent
  capital loss, not a way to avoid bear markets.
- The result is **development-window only**. I did not inspect the holdout;
  any 2024-2026 run belongs to the lead. Given the high turnover, the 2022
  concentration and the weak acceleration rule, I would not assume the same
  CAGR out of sample.

If the next decade is a low-vol melt-up with no 2022-style bear, this strategy
will lag TQQQ. That is the trade: it gives up upside in strong bull years to
cut the left tail of a 3x daily-reset product.

---

## 10. Reproduction

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
$env:BT_THREADS = "1"
python research/new/vol-of-vol-timing/strategy.py
```

Outputs `result.json` in the same folder. The 1-minute panel is truncated at
2023-12-29; the daily high/low parquet is read with a `date <= 2023-12-29`
predicate. No 2024-2026 data is loaded or inspected.
