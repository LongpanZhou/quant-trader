# ml-regime-v2 — walk-forward path-drawdown-risk allocator

## Verdict

**Pass on the development bar.** On 1-minute marks, 2016-01-04..2023-12-29,
next-open fills, 2% band:

| Cost | CAGR | Max DD | Sharpe | Fills |
|---:|---:|---:|---:|---:|
| 1 bp | **59.61%** | **42.89%** | **1.28** | 103 |
| 5 bp | 58.79% | 42.89% | 1.27 | 103 |
| 10 bp | 57.77% | 42.89% | 1.26 | 103 |
| TQQQ bar | 36.72% | 82.29% | 0.82 | — |
| TQQQ harness | 36.15% | 82.29% | 0.80 | — |

The strategy clears the 36.72% CAGR bar by 22.9 pp, with roughly half of TQQQ's
drawdown. It also clears 5 bp and 10 bp.

**But the ML adds essentially nothing over a one-line vol rule.** The same
momentum state with `rv5 < 0.60` instead of the model produces 59.84% CAGR /
42.89% DD / 1.24 Sharpe, and the ML and the rule choose the same asset on
**91.0%** of sessions. The pre-registered three-state ML is 0.23 pp *below* the
rule on CAGR and 0.04 above on Sharpe. A post-hoc binary ML variant (no QQQ
state) reaches 60.91% / 42.89% / 1.31, 1.07 pp above the rule, which is inside
the noise. The honest description is: **momentum regime + short-vol crash
filter, with a walk-forward ML calibration layer that is not reliably
additive.**

The strategy is also highly correlated with the old 165-day base
(**0.937** daily-return correlation). It is an improved version of the same
trend-timing family, not a new return driver. That is the main reason to be
sceptical of the headline.

## 1. What it trades and why

The mechanism is the arithmetic of a 3x daily-reset ETF:

```
log TQQQ return over a horizon  ~=  3 * log QQQ return  -  4.5 * variance
```

The drift term pays only if the position survives the path. TQQQ's 2016-2023
record is a 36.7% CAGR buried inside an 82% drawdown; most of the damage is
concentrated in a few volatility regimes. The strategy therefore separates
two questions:

1. **Is the equity trend up?** A majority vote of QQQ 60-, 100- and 150-session
   total returns being positive. This is deliberately not the 165-day
   moving-average gate of the old base; it is a multi-horizon momentum state.
2. **Is the path likely to be crash-prone over the next month?** A quarterly
   walk-forward logistic model estimates
   `P(TQQQ peak-to-trough drawdown over the next 20 sessions > 15%)`
   from nine volatility-term-structure features. The label is a **path**
   drawdown, not a terminal return, so it captures a crash that recovers by the
   end of the horizon.

Allocation, set at the close and filled at the next open:

| Condition | Weight |
|---|---|
| momentum score < 2/3 | 100% BIL |
| momentum >= 2/3, risk probability < 0.60 | 100% TQQQ |
| momentum >= 2/3, risk probability 0.60-0.90 | 100% QQQ |
| momentum >= 2/3, risk probability >= 0.90 | 100% BIL |

The QQQ middle state is intentionally a half-risk state: keep equity beta but
drop the 3x reset when the path is dangerous. In practice it is used on only
2.2% of sessions; the data says QQQ is almost always dominated by either TQQQ
or BIL for this signal.

## 2. Model and causality

- Features (9, all through the current close): QQQ 5/10/20/60-session realised
  vol (annualised), 5d/60d and 20d/60d vol ratios, 20-session Parkinson range
  vol, 20-session downside-semivariance share, 20-session vol-of-vol.
- Label: `1` if the maximum peak-to-trough drawdown of TQQQ over the next 20
  sessions exceeds 15%. Base rate 31.7%.
- Model: L2 logistic regression (`lambda=10`), refit every calendar quarter,
  trained on an expanding window; labels whose forward window crosses the test
  quarter are purged (36 calendar days). Features are median-imputed and
  standardised on the training window only. No full-sample fitting.
- The first prediction is 2017-01-03; 2016 is BIL while the model accumulates
  its 200 labelled training rows. This is a deliberate, conservative warm-up
  and it costs return (see §7).
- Weights are fractions of current equity, long-only, sum to 1. The harness
  (`research/bt.py`) executes at the next open with the 2% band.

The design was pre-registered in `HYPOTHESIS.md` before the 1-minute run, with
an 8-combination grid. That grid is reported in §5 and was not used to pick the
primary configuration.

## 3. Results

### 3.1 Headline

| Strategy | CAGR | Max DD | Sharpe | Sortino | Vol | Fills |
|---|---:|---:|---:|---:|---:|---:|
| **ml-regime-v2, 1 bp** | **59.61%** | **42.89%** | **1.28** | **1.83** | 44.2% | 103 |
| ml-regime-v2, 5 bp | 58.79% | 42.89% | 1.27 | 1.81 | 44.2% | 103 |
| ml-regime-v2, 10 bp | 57.77% | 42.89% | 1.26 | 1.79 | 44.2% | 103 |
| TQQQ buy & hold | 36.15% | 82.29% | 0.80 | — | 66.6% | — |
| QQQ buy & hold | 18.91% | 37.30% | 0.90 | — | 22.0% | — |
| BIL buy & hold | 1.39% | 0.24% | 0.92 | — | 1.5% | — |
| **Simple vol rule** | **59.84%** | **42.89%** | **1.24** | — | — | 67 |
| Momentum only (no risk gate) | 52.56% | 62.49% | 1.11 | — | — | — |
| Binary ML (no QQQ state) | 60.91% | 42.89% | 1.31 | — | — | — |
| Old 165-day base (1m marks) | 45.02% | 58.76% | 1.03 | — | — | 59 |

The TQQQ harness number is 36.15% rather than the stated 36.72% because
`bt.benchmark` starts from the first bar's close; the drawdown (82.29%) matches
the stated bar exactly. The strategy is compared against the stricter 36.72%
throughout.

### 3.2 Exposure, trading, correlation

- Time in TQQQ: **67.0%**; QQQ: **2.2%**; BIL: **30.8%**.
- 51 state switches, 103 fills over 8 years. Each switch is a sell plus a buy;
  the low fill count is why 10 bp costs remove only 1.8 pp of CAGR.
- Cumulative traded notional / initial equity is 1,823x, but that is dominated
  by compounding: the book grows ~41x, so a late 100% switch trades ~41x the
  initial equity. The economically meaningful number is ~6 switches per year.
- Daily-return correlation to TQQQ: **0.683**. To QQQ: 0.679.
- Correlation to the old 165-day base: **0.937**.
- Correlation to the simple vol rule: **0.963**; state overlap **91.0%**.
- Correlation to momentum-only: 0.933.

### 3.3 Yearly returns

| Year | Strategy | TQQQ | TQQQ time | Comment |
|---|---:|---:|---:|---|
| 2016 | +0.1% | +18.6% | 0% | model warm-up, all BIL |
| 2017 | +110.4% | +113.0% | 100% | fully invested, tracks TQQQ |
| 2018 | +7.0% | -23.5% | 81% | exits for Q4, the main win |
| 2019 | +62.9% | +130.5% | 82% | lags a melt-up |
| 2020 | +205.8% | +99.8% | 89% | exits the Feb-Mar crash, re-enters |
| 2021 | +89.8% | +90.9% | 99% | fully invested |
| 2022 | -24.3% | -79.7% | 5% | early-January whipsaw, then BIL |
| 2023 | +137.3% | +208.9% | 80% | lags the recovery |

The pattern is consistent with the mechanism: the strategy wins by avoiding
crash years (2018, 2022) and one crash quarter (2020Q1), and loses relative
performance in strong bull years (2019, 2023) and during the 2016 warm-up.
It beats TQQQ in 3 of 8 calendar years (2018, 2020, 2022) and beats it by a
wide margin in the two bear/crash years.

## 4. Risk-model diagnostics

| Metric | Value |
|---|---:|
| OOS AUC | **0.677** |
| Accuracy at p=0.50 | 0.681 |
| Accuracy at deployed p=0.60 | 0.669 |
| Base rate | 0.317 |
| Brier score | 0.213 |
| OOS observations | 1,739 |
| First prediction | 2017-01-03 |

AUC by year:

| Year | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 |
|---|---:|---:|---:|---:|---:|---:|---:|
| AUC | n/a* | 0.493 | 0.317 | 0.785 | 0.692 | 0.549 | 0.557 |

\*2017 has no positive path-drawdown events (a completely calm year), so AUC is
undefined.

The overall AUC of 0.677 is flattered by the cross-year level of volatility:
the model is good at saying "2020-2022 is more dangerous than 2017", which is
trivially true. Within 2018 and 2019 it is at or below chance. This is exactly
why the simple `rv5 < 0.60` rule matches it: both are reading the current
short-horizon volatility level, not forecasting a regime change. The model's
one genuine success is 2020 (AUC 0.785), where the vol spike persisted long
enough to be tradeable.

**This is the central negative result of the study.** The label is different
from the existing ML strategies and the model is causal and honestly
walk-forward, but on this sample it does not extract information beyond a
one-dimensional volatility threshold.

## 5. Parameter plateau (pre-registered 8-combination grid)

| # | Window | lo | hi | CAGR | Max DD | Sharpe |
|---:|---|---:|---:|---:|---:|---:|
| 1 | expanding | 0.60 | 0.90 | 59.61% | 42.89% | 1.28 |
| 2 | expanding | 0.60 | 0.85 | 59.18% | 42.89% | 1.28 |
| 3 | expanding | 0.65 | 0.90 | 60.12% | 42.89% | 1.29 |
| 4 | expanding | 0.65 | 0.85 | 59.69% | 42.89% | 1.28 |
| 5 | 750d | 0.60 | 0.90 | 48.19% | 47.89% | 1.13 |
| 6 | 750d | 0.60 | 0.85 | 49.77% | 43.30% | 1.15 |
| 7 | 750d | 0.65 | 0.90 | 50.32% | 51.00% | 1.14 |
| 8 | 750d | 0.65 | 0.85 | 51.92% | 49.89% | 1.16 |

All eight pass the bar. The expanding window is clearly better than the 750-day
window (59-60% vs 48-52%), which is a real choice, not noise: the 750-day
window forgets the 2018 and 2020 crash examples by 2022. The threshold
neighbourhood 0.60-0.65 / 0.85-0.90 is flat.

Neighbour checks outside the grid (not used for selection):

| Variant | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| Label horizon 10 | 56.30% | 44.11% | 1.20 |
| Label horizon 40 | 49.11% | 43.23% | 1.18 |
| Drawdown threshold 10% | 49.15% | 40.35% | 1.25 |
| Drawdown threshold 20% | 57.07% | 42.89% | 1.23 |
| Momentum (60,100) | 57.36% | 48.84% | 1.23 |
| Momentum (100,150,200) | 49.98% | 49.10% | 1.12 |
| Monthly refit | 52.61% | 42.89% | 1.19 |
| One-session execution delay | 52.28% | 44.35% | 1.17 |
| Binary ML, no QQQ state | 60.91% | 42.89% | 1.31 |
| Momentum only | 52.56% | 62.49% | 1.11 |

Every neighbour still beats 36.72% CAGR with DD below 82.29%. The plateau is
wide. The QQQ middle state costs about 1.3 pp of CAGR and 0.03 Sharpe; the
binary version is slightly better but does not use the third asset.

## 6. Placebo and cut test

**Placebo A — circular shifts of the risk-probability series** (200 draws;
preserves the probability distribution and its autocorrelation, breaks the
alignment with returns, keeps the momentum state):

- mean CAGR 46.8%, 5th pct 41.4%, 95th pct 53.8%, max 59.9%.
- The strategy's 59.61% is at the **99.5th percentile**.

**Placebo B — random permutation of the state array** (200 draws; same counts
of TQQQ/QQQ/BIL days, random timing):

- mean CAGR 19.8%, 5th pct -0.9%, 95th pct 40.2%, max 70.0%.
- The strategy is at the **99.5th percentile**.

Both placebos say the timing, not just the exposure, is doing the work. The
permutation placebo is weak evidence on its own because a random 67% TQQQ
exposure has a wide CAGR distribution; the shift placebo, which preserves the
momentum state, is the more relevant control and still puts the strategy at the
top of the distribution.

**Cut test.** Rebuilding the daily features, labels and walk-forward model on
data truncated at 2022-06-30 leaves all 1,635 earlier daily states identical.
Since the daily states are expanded to constant weights within each minute
session, a mid-session truncation cannot change any earlier minute weight
either. No look-ahead was found.

## 7. Sub-periods and ex-year robustness

| Period | Strategy CAGR / DD | TQQQ CAGR / DD |
|---|---:|---:|
| 2016-2019 | 40.3% / 33.2% | 48.6% / 58.0% |
| 2020-2021 | 136.3% / 36.0% | 91.5% / 69.9% |
| 2022-2023 | 34.3% / 30.1% | -21.8% / 81.0% |

The strategy **lags TQQQ on CAGR in 2016-2019** but with much lower drawdown.
The overall win comes from 2020-2023: crash avoidance in 2020Q1 and 2022, and a
strong 2023 recovery. This is not a uniformly dominant strategy; it is a
crash-hedged one.

Ex-year CAGR (remove one calendar year's return and re-annualise the remaining
chain):

| Excluded year | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| CAGR | 68.3% | 51.3% | 66.7% | 57.0% | **43.5%** | 53.6% | 75.2% | 48.8% |

The worst ex-year result is 43.5% (excluding 2020), still 6.8 pp above the
36.72% bar. The result is not a single-year artifact.

## 8. How this differs from the existing work

- **`ml-classifier`** predicts whether TQQQ beats BIL over 5/10/20 days from a
  broad feature set (daily returns, realised vol, RSI, moving averages and
  intraday microstructure such as first30, last30, VWAP, close location and
  gap) and uses the 165-day QQQ SMA as its base regime. This strategy predicts a **20-day TQQQ path maximum
  drawdown**, uses only nine daily volatility-term-structure features with no
  intraday inputs, and has no 165-day gate.
- **`ml-crash-overlay-winner`** predicts `P(TQQQ 20-day terminal return < -15%)`
  and forces BIL on the top decile of a 165-day SMA + 4% minute-stop winner.
  This strategy uses a *path* drawdown label (a crash that recovers still
  counts), a different feature set, and a three-state momentum + risk allocator
  with no 4% stop and no 165-day gate.
- **`research/revisit`** forbids the 165-day QQQ/TQQQ/SPY moving-average gate
  and asks for low correlation with the old base. This strategy satisfies the
  letter of the first rule (no moving average) but **not the spirit of the
  second**: its daily-return correlation with the 165-day base is 0.937. It is a
  trend-timing relative, not a diversifier. It should not be presented as a
  new independent return driver.
- The closest published profile is `vol-scaled-crash-stop` (dev 57.84% /
  39.29% per `research/revisit/SUMMARY.md`). This strategy is **not a clear
  improvement** on it: +1.8 pp CAGR but +3.6 pp drawdown, so a slightly worse
  Calmar ratio (1.39 vs 1.47). The mechanism is different, the risk/return
  profile is not.

## 9. Weaknesses and honest assessment

1. **The ML is not reliably additive.** The simple `rv5 < 0.60` rule matches
   the CAGR and drawdown with 91% state overlap. The pre-registered three-state
   ML is 0.23 pp below the rule on CAGR; the binary ML variant is 1.07 pp above
   it, which is inside noise. The model's AUC is inflated by cross-year
   volatility levels; within 2018 and 2019 it is at or below chance. Do not
   sell this as an ML edge.
2. **The 2016 warm-up is wasted.** The model needs 200 labelled rows, so the
   whole of 2016 is BIL. TQQQ returned +18.6% that year. A momentum-only
   warm-up would have added return but would have introduced a hand-rule
   period; I left it out to keep the specification clean.
3. **January 2022 is a real wound.** The strategy entered 2022 fully long
   because 2021 momentum was strong and 5-day vol was still low, then lost
   about 24% in the first two weeks. No price/vol signal available at the
   decision date flagged that crash. This is the same blind spot as every trend
   strategy and it accounts for most of the 42.9% drawdown.
4. **Bull-year lag is structural.** The strategy gave up 68 pp in 2019 and 72 pp
   in 2023 relative to TQQQ. In a strong melt-up it will underperform.
5. **High correlation to the old base (0.937).** The strategy is an improved
   trend variant, not a diversifier. The repo's main problem — everything is
   the same trade — is not solved here.
6. **Eight years, one crash regime.** The model has seen 2018, 2020 and 2022,
   but not 2000-02 or 2008. The risk model's crash threshold (15% over 20
   sessions) is calibrated on a period with a strong Fed put. A 2008-style
   slow bear would look different.
7. **The drawdown is still 42.9%.** This is a lower-risk way to hold a 3x ETF,
   not a low-risk strategy. The 44% volatility is close to TQQQ's 67% but not
   small.
8. **Many exploratory screens.** Roughly 300 daily-panel configurations were
   examined while choosing the mechanism and the pre-registered grid, far more
   than the eight grid points. The grid was fixed before the 1-minute run and
   all eight points pass, but the choice of momentum horizons and the 15% label
   threshold is not independent of that exploration. Treat the headline as a
   development result, not an unbiased estimate of future performance.

**Overall:** the strategy passes the stated bar with room to spare, at 1, 5 and
10 bp, on a wide parameter plateau, with a clean cut test and top-percentile
placebos. The return is real but it is the momentum + short-vol crash filter
that produces it. If the question is "did the ML regime allocator add value?",
the answer is **no** — it is a slightly noisier version of the vol rule. If the
question is "is this a new standalone strategy that beats TQQQ with a much
smaller drawdown?", the answer is **yes, but it belongs to the same trend family
as the old base.**

## 10. Reproduction

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
$env:BT_THREADS = "1"
python research/new/ml-regime-v2/strategy.py
```

The run writes `result.json` in the same folder. It loads only
2016-01-04..2023-12-29; the 2024-2026 holdout is never requested. All numbers
in this report come from `result.json`.
