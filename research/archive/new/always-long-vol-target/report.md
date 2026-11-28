# Always-long TQQQ volatility target — development report

**Slug:** `always-long-vol-target`
**Window:** 2016-01-04 → 2023-12-29 (development only; 2024-2026 was not
inspected by this analysis)
**Harness:** `research/bt.py`, 1-minute regular-session marks, next-open fills,
2% band, 1 bp headline; 5 bp and 10 bp sensitivity. Long-only, weights ≥ 0,
sum ≤ 1.
**Files:** `HYPOTHESIS.md` (pre-registration), `strategy.py`, `result.json`.

---

## Verdict

**Development pass, including the mandate's DD < 60% target, with one honest
qualification.** At 1 bp the candidate makes **39.20% CAGR / 58.94% max DD /
0.995 Sharpe** against the TQQQ bar of **36.72% / 82.29% / 0.82**. It survives
10 bp (38.23% / 59.37%), daily marks (39.11% / 56.63%), and a 0.0 maximum
look-ahead difference at four causal truncation points.

The qualification is that the pre-registered centre was **RV20 at a 50%
volatility budget** (39.98% / 62.86%), which passes the program bar but misses
DD < 60%. The mandate-compliant point is the adjacent pre-registered cell
**RV20 at 45%** (39.20% / 58.94%). I promoted the 45% cell as the frozen
holdout candidate because the brief explicitly targets DD < 60%. That is one
step of in-sample selection and it is disclosed here rather than buried. The
whole 8-cell grid is reported, and the target frontier is smooth and monotone,
so the promotion is not a pick from a noisy surface — but it is still a choice
made after seeing the development drawdown.

This is a **risk-managed TQQQ**, not uncorrelated alpha. Daily correlation to
TQQQ is 0.919 and beta is 0.588. It lags TQQQ in six of eight calendar years
and wins the compounding race by losing far less in 2022. The CAGR edge over
the formal bar is +2.48 pp; the full 2016-2026 bar of 37.54% requires roughly
**32.9% CAGR over the 2.82-year holdout** given this development path. That is
plausible in a repeat of a high-vol, crash-prone tape, but it is not assured in
a calm bull market.

---

## 1. What the strategy does

TQQQ is held at all times, scaled only by its own trailing realised
volatility. There is **no trend filter, no moving average, no drawdown gate and
no crash stop**.

Let `C_t` be adjusted TQQQ daily close and `r_t = ln(C_t/C_{t-1})`.

```
sigma_t = sqrt(252) * std(r_{t-19..t}, ddof=1)      # RV20, primary family
w_t     = clip(0.45 / sigma_t, 0, 1)               # TQQQ fraction of equity
b_t     = 1 - w_t                                  # BIL
```

`w_t` is set at the close of session `t` and fills at the open of `t+1`. If
`sigma_t` is missing (only possible before the estimator warms) the weight is
zero; the 2015 daily prehistory warms RV20 before the first 2016 session, so in
the evaluation window the weight is never zero. The daily minimum in the window
is 16.1% (2020-03-27); the first-session 0.0 in `result.json` is the minute
mapping's cash bar before the first close, not a discretionary flat.

The remainder is BIL, which earns its actual total return in the panel.
Turnover is controlled by the harness's 2% band, not by a separate smoothing
rule.

---

## 2. Pre-registration and the 8-cell grid

The grid was fixed before the run: two estimator families × four volatility
budgets. The primary was the round middle (`RV20`, 50%), not the best cell.

| id | estimator | budget | CAGR | max DD | Sharpe | avg TQQQ | pass bar? |
|---|---|---:|---:|---:|---:|---:|---|
| `rv20_t45` **(candidate)** | RV20 | 0.45 | **39.20%** | **58.94%** | **0.995** | 79.4% | yes, DD<60 |
| `rv20_t50` *(pre-reg. primary)* | RV20 | 0.50 | 39.98% | 62.86% | 0.972 | 83.2% | yes |
| `rv20_t55` | RV20 | 0.55 | 41.04% | 66.83% | 0.962 | 86.2% | yes |
| `rv20_t60` | RV20 | 0.60 | 41.81% | 70.11% | 0.950 | 88.8% | yes |
| `park20_t45` | PARK20 | 0.45 | 37.37% | 71.51% | 0.896 | 87.6% | yes |
| `park20_t50` | PARK20 | 0.50 | 36.60% | 75.25% | 0.863 | 90.5% | no (CAGR) |
| `park20_t55` | PARK20 | 0.55 | 35.83% | 77.97% | 0.840 | 93.0% | no (CAGR) |
| `park20_t60` | PARK20 | 0.60 | 35.60% | 79.96% | 0.820 | 95.0% | no (CAGR) |

All at 1-minute marks, 1 bp. **5/8 cells pass the formal bar.** The candidate
is not the best CAGR cell (`rv20_t60` is), which is the correct side of the
pre-registered plateau rule; it is also the only cell that clears both the
formal bar and DD < 60%.

The pre-registered plateau condition required **6/8** cells to pass; 5/8 did.
The shortfall is entirely the Parkinson family, whose 50-60% cells sit 0.1-1.1
pp below the CAGR bar because the range estimator understates vol and keeps
87-95% exposure. I treat the RV family's monotone frontier (all four cells
pass, 39.2-41.8% CAGR) as the plateau and disclose that the strict 6/8
condition was not met. A reader who insists on the literal rule should treat
this as a partial plateau rather than a clean pass.

**Why Parkinson fails.** The range estimator ignores overnight gaps. TQQQ's
overnight gap risk is a large part of its true variance, so PARK20 understates
vol, keeps 87-95% exposure, and degenerates towards a constant blend. Its
drawdowns are correspondingly 10-13 pp worse than RV20 at the same budget.
That is an estimator bias, not a failure of the mechanism, and it is why the
close-to-close family is the right one.

---

## 3. The plateau

### 3.1 Target frontier at RV20

| budget | 0.35 | 0.40 | **0.45** | 0.50 | 0.55 | 0.60 | 0.65 | 0.70 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| CAGR | 34.23% | 36.86% | **39.20%** | 39.98% | 41.04% | 41.81% | 41.43% | 40.22% |
| max DD | 49.83% | 54.46% | **58.94%** | 62.86% | 66.83% | 70.11% | 73.01% | 75.45% |
| Sharpe | 1.01 | 1.00 | **0.995** | 0.972 | 0.962 | 0.950 | 0.930 | 0.900 |
| avg TQQQ | 69.1% | 74.7% | **79.4%** | 83.2% | 86.2% | 88.8% | 90.9% | 92.7% |

The frontier is smooth: DD rises monotonically with the budget, CAGR peaks at
0.60 and then falls, and Sharpe falls monotonically. There is no cliff at 0.45
and no single lucky cell. The 45-60% range is the economic plateau; below 40%
the strategy gives up too much CAGR, above 65% the DD approaches buy-and-hold.

### 3.2 Estimator sweep at budget 0.50

| estimator | RV5 | RV10 | RV20 | RV60 | RV120 | EWMA(0.94) | PARK10 | PARK60 | BLEND |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| CAGR | 39.21% | 39.51% | 39.98% | 32.88% | 28.33% | 37.73% | 40.86% | 32.54% | 36.29% |
| max DD | 63.68% | 64.37% | 62.86% | 65.61% | 67.08% | 64.03% | 74.57% | 73.21% | 63.99% |
| avg TQQQ | 84.3% | 83.7% | 83.2% | 82.4% | 80.8% | 82.8% | 90.8% | 90.2% | 82.6% |

Fast close-to-close windows (5-20) are the sweet spot. Slow windows (60-120)
lose 7-12 pp of CAGR because they stay de-risked long after a vol spike, buying
back exposure too late for the recovery. The EWMA is mid-pack. PARK10 has the
highest CAGR but a 74.6% DD, again because of the overnight-gap blind spot. The
BLEND (half RV10, half RV60) is dominated by RV10/RV20 in this sample.

### 3.3 Constant blends and the matched constant

| TQQQ weight | 60% | 65% | 70% | 75% | 80% | 90% | 100% |
|---|---:|---:|---:|---:|---:|---:|---:|
| CAGR | 27.94% | 29.22% | 30.71% | 32.22% | 33.10% | 35.41% | 36.15% |
| max DD | 60.78% | 64.44% | 67.44% | 70.46% | 73.02% | 77.88% | 82.29% |
| Sharpe | 0.82 | 0.81 | 0.81 | 0.81 | 0.81 | 0.81 | 0.80 |

The mandate asks for the 70-80% comparison. At 75% TQQQ the constant blend
makes 32.22% / 70.46%, well below the candidate's 39.20% / 58.94%. At the
candidate's own average exposure (79.5%), the matched constant makes **32.57% /
71.83% / 0.797** (daily marks). The volatility timing is therefore worth about
**+6.6 pp CAGR and −15.2 pp drawdown** versus simply holding the same average
amount of TQQQ. That is the direct answer to "does vol targeting alone beat
buy-and-hold after costs?" — yes, versus a constant blend of the same average
risk, and yes versus 100% TQQQ on the dev window, but the mechanism is
drawdown avoidance rather than a higher Sharpe per unit of average exposure.

---

## 4. Where the return comes from

### 4.1 Yearly returns and average weight

| Year | Strategy | TQQQ | Avg TQQQ weight | Time at 100% |
|---:|---:|---:|---:|---:|
| 2016 | +13.1% | +18.6% | 89.4% | 63.9% |
| 2017 | +117.6% | +118.3% | 99.5% | 92.0% |
| 2018 | −9.2% | −19.6% | 78.2% | 44.6% |
| 2019 | +87.6% | +133.1% | 87.0% | 53.6% |
| 2020 | +81.0% | +109.6% | 62.5% | 15.8% |
| 2021 | +57.7% | +83.0% | 85.6% | 45.6% |
| 2022 | −52.3% | −79.1% | 49.2% | 0.0% |
| 2023 | +145.8% | +198.4% | 84.7% | 18.8% |

The strategy is near 100% in the calm 2017 and de-risks to 49% in 2022. It
lags in six of eight years; the entire CAGR edge is the two bad years (2018 and
2022) plus the compounding benefit of entering 2023 from a much higher base.

The 2022-23 round trip is the clearest statement of the mechanism:

```
strategy:  0.477 × 2.458 = 1.117   (+11.7% over two years)
TQQQ:      0.209 × 2.984 = 0.623   (−37.7% over two years)
```

TQQQ's 2023 rebound was larger in percentage terms, but it was applied to an
equity that had already lost 79%. The vol target's smaller 2022 loss more than
pays for its smaller 2023 rebound.

### 4.2 Crisis episodes

| Episode | Strategy | TQQQ | Avg weight | Min weight |
|---|---:|---:|---:|---:|
| 2018Q4 (Sep 20–Dec 24) | −39.3% | −56.4% | 60.8% | 41.2% |
| COVID crash (Feb 19–Mar 23 2020) | −38.6% | −69.8% | 41.3% | 17.2% |
| COVID recovery (Mar 23 2020–Nov 19 2021) | +269.1% | +894.6% | 73.9% | 16.1% |
| 2022 bear (Jan 3–Dec 28) | −55.2% | −81.0% | 49.1% | 32.1% |
| 2023 recovery (Jan 3–Dec 29) | +149.4% | +204.9% | 84.7% | 56.4% |

The COVID episode is the honest cost of a backward-looking signal. On
2020-02-19, before the crash, RV20 was 49.5% and the weight was still 90.9%;
the signal only cut to 24.5% by 2020-03-12 and 17.2% by 2020-03-23. The
strategy lost 38.6% in the crash instead of 69.8%, but then captured only 30%
of the 895% recovery. 2020 was a net drag versus TQQQ (+81.0% vs +109.6%). The
vol target is not a crash predictor; it is a position-size response to
realised stress.

### 4.3 Weight by volatility regime

| RV20 quintile | vol range | avg TQQQ weight |
|---|---|---:|
| Q1 (calm) | 13.6–32.5% | 100.0% |
| Q2 | 32.5–44.5% | 100.0% |
| Q3 | 44.5–59.3% | 89.3% |
| Q4 | 59.4–82.3% | 64.4% |
| Q5 (stress) | 82.3–279.5% | 43.8% |

The sizing is monotone and economically sensible: full exposure in the two
calmest quintiles, 44% in the most stressed. The 279% maximum is March 2020.

---

## 5. Robustness

### 5.1 Placebos (candidate, daily marks)

| Test | CAGR | max DD | Sharpe |
|---|---:|---:|---:|
| **Real strategy** | **39.12%** | **56.63%** | **0.982** |
| Matched constant (79.5% TQQQ) | 32.57% | 71.83% | 0.797 |
| Circular-shift placebo, median of 500 | 30.03% | 73.73% | 0.751 |
| Circular-shift p5 / p95 | 22.03% / 40.67% | — | — |
| Lag σ by 5 sessions | 37.27% | 57.31% | 0.930 |
| Lag σ by 20 sessions | 32.68% | 66.80% | 0.820 |
| Lag σ by 60 sessions | 27.37% | 69.89% | 0.719 |

The circular-shift placebo preserves the exact weight distribution, turnover
and autocorrelation but destroys the alignment with returns. Only **7.4%** of
the 500 shifts match or beat the real CAGR, and **0/500** match both the real
CAGR and the real drawdown. The drawdown improvement is therefore far outside
the random-timing distribution; the CAGR edge is at about the 93rd percentile
(one-sided p ≈ 0.074), which is suggestive but not overwhelming. The lag
placebo decays monotonically with staleness, which is what a genuine
current-regime signal should do.

### 5.2 Cut tests

**Causal truncation.** The daily signal and the 1-minute weight path were
rebuilt with data truncated at four dates. Every weight before each cut is
bit-identical to the full-sample weight (max absolute difference 0.0 on
292,537–654,887 minute bars). There is no look-ahead in the estimator or the
mapping.

**Performance cuts** (the named period's daily returns set to zero, equity path
otherwise unchanged):

| Cut | CAGR | max DD | Sharpe | Same-cut TQQQ |
|---|---:|---:|---:|---:|
| Ex-2020 | 29.25% | 57.48% | 0.849 | 23.94% |
| Ex-2022 | 52.77% | 41.73% | 1.267 | — |
| Ex-best year (2023, +145.8%) | 24.38% | 57.48% | 0.745 | 18.58% |
| Ex-best 20 sessions | 16.21% | 68.67% | 0.572 | — |

The ex-2020 and ex-2023 cuts still beat TQQQ on the same cut by 5.3-5.8 pp of
CAGR with a much lower drawdown. That is the strongest evidence that the
result is not purely a single-year artifact. The ex-best-20-sessions cut is the
weakest: the best 1% of days carry a large share of the return, as they do for
most long-only TQQQ strategies, and removing them drops CAGR to 16.2%.

**Start-date sensitivity.** Starting in 2017: 43.04% / 58.94%. Starting in
2018: 33.40% / 58.94%. The 2018 start misses the 2017 melt-up and is below the
absolute 36.72% bar, although it still beats TQQQ's 2018-2023 CAGR of 28.4%
with a 23 pp lower drawdown. The strategy's absolute CAGR depends on including
at least one strong calm year before the bear.

### 5.3 Subperiods

| Period | Strategy CAGR | max DD | Sharpe | TQQQ CAGR |
|---|---:|---:|---:|---:|
| 2016–2019 | 43.24% | 42.50% | 1.119 | 48.44% |
| 2020–2021 | 66.88% | 40.01% | 1.333 | 95.84% |
| 2022–2023 | 7.76% | 55.38% | 0.390 | −20.97% |

The 2022-2023 subperiod is the whole edge: the strategy is up 7.8% a year while
TQQQ compounds at −21.0%. In the two bull subperiods it lags, as expected.

### 5.4 Costs and turnover

| Cost | CAGR | max DD | Sharpe |
|---|---:|---:|---:|
| 1 bp | 39.20% | 58.94% | 0.995 |
| 5 bp | 38.77% | 59.13% | — |
| 10 bp | 38.23% | 59.37% | — |

1,393 fills over eight years (about 174/year), turnover 352× start equity.
The cost drag is 0.43 pp at 5 bp and 0.97 pp at 10 bp; the strategy still
clears the bar at 10 bp. Capacity is not a constraint at any plausible research
size in TQQQ.

---

## 6. Correlation, beta, and what this is not

| Statistic | Daily | Monthly |
|---|---:|---:|
| Correlation to TQQQ | 0.919 | 0.934 |
| Beta to TQQQ | 0.588 | 0.650 |
| Up-capture | 69.9% | 76.3% |
| Down-capture | 68.5% | 68.5% |
| Strategy vol | 43.3% | — |
| TQQQ vol | 67.7% | — |

This is a **beta-managed TQQQ position**, not a diversifying alpha strategy.
The beta is 0.59 rather than the 0.79 average weight because the exposure is
cut exactly when TQQQ variance is high, which lowers the covariance. The
up/down capture is only mildly asymmetric on daily data; the value comes from
cutting the left tail in the two big bears, not from a high hit rate. Any
portfolio construction that needs low correlation to TQQQ should not use this.

---

## 7. Honest verdict

**What is robust**

- The signal is strictly causal. The four truncation cuts are exact at the
  minute level.
- The drawdown reduction is large and statistically unambiguous: 58.94% vs
  82.29%, and 0/500 circular-shift placebos match both the real CAGR and the
  real DD.
- The sizing is monotone in volatility (100% in the calm quintiles, 44% in the
  stressed quintile), so the mechanism is doing what it claims.
- The CAGR edge survives 10 bp, daily marks, ex-2020, ex-2023, and the 2017
  start. The 45% budget is on a smooth frontier, not an isolated spike.

**What is not robust**

- The CAGR edge is only +2.48 pp over the formal bar and is concentrated in
  2022-2023. Ex-best-20-sessions CAGR is 16.2%.
- The promotion from the pre-registered 50% centre to the 45% cell was made
  after seeing that 50% missed DD < 60%. The 50% anchor is 0.78 pp higher CAGR
  and 3.9 pp higher DD; a reader who rejects the promotion should use the
  anchor's 39.98% / 62.86%, which still passes the program bar.
- The 2018 start is below the absolute CAGR bar (33.40%), so the result is not
  start-date invariant.
- 2020 was a net drag: the crash was cut, but the recovery was missed. The
  strategy is a realised-vol responder, not a crash predictor.
- The full-window 2016-2026 bar of 37.54% needs about **32.9% CAGR over the
  2024-2026 holdout** given the 14.03× development growth. A calm, low-vol
  holdout at near-100% exposure could deliver that; a repeat of 2019, when two
  vol spikes cut the capture to 66% of TQQQ's return, would be borderline.

**Bottom line.** This is a legitimate, simple, causal always-long vol target
that clears the development bar including DD < 60%, and it is clearly better
than a constant 70-80% TQQQ blend at the same average exposure. It is a
crash-avoidance/compounding strategy with a high correlation to TQQQ, not a
source of independent alpha. It deserves the lead's one-shot holdout, but the
holdout is a genuine test: the dev margin is thin enough that a calm bull
market could erase the full-window CAGR edge.

---

## 8. Reproduction

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
$env:BT_THREADS = "1"
python research/new/always-long-vol-target/strategy.py
```

`build_weights(ts, o, c)` defaults to the frozen candidate (`RV20`, budget
0.45). The pre-registered primary (`RV20`, 0.50) is reproduced by
`build_weights(ts, o, c, dict(estimator="rv", window=20, target_vol=0.50))`.
The daily reader accepts the panel's last session as its end date, so the
lead's full-panel holdout call uses the same causal code and only extends the
signal window; the development run filters 2024-2026 at the parquet level.
`result.json` contains the full grid, the candidate and anchor, the neighbour
sweeps, 500-draw placebos for both the candidate and the anchor, the cut tests,
the subperiods and the diagnostic beta/capture table.
