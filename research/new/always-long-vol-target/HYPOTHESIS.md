# Hypothesis and pre-registration — `always-long-vol-target`

**Status:** frozen for the development evaluation. This file is written **before**
the grid run; the numbers in `report.md` come from the exact grid below.
**Development window:** 2016-01-04 → 2023-12-29 only. The 2024-01-02 →
2026-10-23 holdout is not loaded, inspected or used for selection.
**Universe:** TQQQ (long), BIL (cash). QQQ is not used as a signal.
**Execution:** daily target set at session close `t`, filled at the open of
`t+1`; 2% band; 1 bp headline, 5 bp and 10 bp sensitivity. Long-only,
weights ≥ 0, sum ≤ 1. Headline marks are 1-minute (the bar's convention);
daily marks are reported as a cross-check.

## 1. Mechanism

TQQQ is a 3× daily-reset fund. Its compound return is penalised by realised
variance (`log E[1+r] ≈ 3μ_QQQ − 3σ_QQQ²`) and its drawdowns are amplified by
the daily reset. Realised volatility clusters strongly, so the current level of
TQQQ volatility is a causal state variable that says how much of the 3× bet is
being paid for. Holding TQQQ permanently but scaling the position inversely to
its own realised volatility should:

1. cut exposure in the high-vol regimes that produce the deepest drawdowns
   (2018Q4, 2020Q1, 2022), where the 3× reset drag and gap risk are largest;
2. restore full exposure when volatility normalises, so the strategy still
   participates in the recoveries that dominate TQQQ's long-run return;
3. keep a positive average exposure at all times — there is **no trend filter,
   no moving average, no drawdown gate and no crash stop**. The only signal is
   volatility.

This is deliberately a test of **vol targeting alone** versus buy-and-hold
TQQQ. If the timing value of realised volatility is not large enough to pay for
the average under-exposure, the strategy must not be promoted.

## 2. Exact rules

Let `C_t` be TQQQ's adjusted daily close (from the daily archive), and
`r_t = ln(C_t / C_{t-1})`.

**Volatility estimators** (all computed through the close of session `t`, so
strictly causal):

- `RV_N`: annualised sample standard deviation (`ddof=1`) of the last `N`
  daily log returns, `sqrt(252) · std(r_{t-N+1..t})`.
- `PARK_N`: annualised Parkinson range estimator over the last `N` sessions,
  `sqrt(252 / (4 ln 2) · mean(ln(H_i/L_i)²))`, using the adjusted daily
  high/low. It is more efficient than close-to-close but ignores overnight
  gaps; that is why it is in the grid as a rival, not as the primary.
- `EWMA_λ`: RiskMetrics variance recursion
  `σ²_t = λσ²_{t-1} + (1−λ) r_t²`, `λ = 0.94`, annualised. Neighbour only.
- `BLEND`: `sqrt(0.5·RV10² + 0.5·RV60²)`. Neighbour only.

**Position:**

```
w_t = clip(target_vol / σ_t, 0, 1)          # TQQQ fraction of equity
b_t = 1 - w_t                               # BIL fraction
```

If `σ_t` is missing or non-positive, `w_t = 0` (BIL). With the 2015 prehistory
this can only happen in the first few sessions of 2016, before the estimator is
warmed; it is not a discretionary flat.

**No other state.** There is no smoothing, no floor, no cap other than 1, no
volatility-of-volatility, no trend, no stop. `w_t` is set from the close of `t`
and filled at the open of `t+1`.

## 3. Pre-registered grid (8 cells)

The target levels bracket the economically relevant range: TQQQ's dev-window
unconditional volatility is ~69% and its median 20-day realised volatility is
~50%; a 45–60% budget therefore spans "de-risk materially" to "de-risk only in
the top decile". The primary is the round middle (`RV20`, 50%), not the best
cell.

| id | estimator | lookback | target vol |
|---|---|---:|---:|
| `rv20_t45` | RV | 20 | 0.45 |
| **`rv20_t50` (primary)** | **RV** | **20** | **0.50** |
| `rv20_t55` | RV | 20 | 0.55 |
| `rv20_t60` | RV | 20 | 0.60 |
| `park20_t45` | PARK | 20 | 0.45 |
| `park20_t50` | PARK | 20 | 0.50 |
| `park20_t55` | PARK | 20 | 0.55 |
| `park20_t60` | PARK | 20 | 0.60 |

**Plateau rule:** the primary is promoted only if (a) it passes the bar
(CAGR > 36.72%, DD < 82.29%), (b) at least 6 of the 8 cells pass, (c) the
sign of the CAGR/DD trade-off is the same across both estimator families, and
(d) the primary is not the single best cell. If only the highest-exposure cell
passes, that is reported as a near-control failure, not a plateau.

## 4. Out-of-grid diagnostics (not used for selection)

- **Target sweep** at `RV20`: 0.35, 0.40, 0.65, 0.70 (the grid already has
  0.45–0.60). This maps the CAGR/DD frontier, not a search for the best cell.
- **Estimator sweep** at target 0.50: `RV5`, `RV10`, `RV60`, `RV120`,
  `EWMA0.94`, `PARK10`, `PARK60`, `BLEND`.
- **Constant blends:** 60, 65, 70, 75, 80, 90, 100% TQQQ, remainder BIL,
  rebalanced daily under the same 2% band. The 70–80% band is the direct
  comparison the mandate asks for.

## 5. Placebos and robustness

- **Matched constant:** a constant TQQQ weight equal to the primary's realised
  average weight. It has the same average exposure but no timing; the
  difference is the value of vol timing.
- **Circular-shift placebo:** the primary weight path is shifted by a random
  offset (uniform in `[60, n−60]`, 500 draws), preserving the exact weight
  distribution, turnover and autocorrelation while destroying alignment with
  returns. The real CAGR/DD is compared with the placebo distribution.
- **Lag placebo:** `σ_{t−k}` for `k = 5, 20, 60`. A stale volatility signal
  should lose the timing edge if the signal is genuinely about the current
  regime.
- **Cut tests:** causal truncation at 2018-12-31, 2020-03-12, 2021-12-31 and
  2022-09-13 (weights before the cut must be identical); performance cuts
  dropping the best calendar year, dropping 2020, dropping 2022, dropping the
  best 20 sessions, and starting in 2017 and 2018.
- **Subperiods:** 2016–2019, 2020–2021, 2022–2023, plus yearly returns.

## 6. Pass criterion and interpretation

The formal bar is the program bar: **dev CAGR > 36.72% and max DD < 82.29%**
on 1-minute marks at 1 bp. The mandate's tighter target is DD < 60%. A pass on
CAGR with DD between 60% and 82% is reported as a partial pass, not a clean
one.

The honest prior is that vol targeting is a **risk-reduction** technology: it
usually lowers CAGR as well as drawdown. The strategy is only interesting if
the drawdown avoided in 2018Q4/2020/2022 is large enough that the compounded
path beats buy-and-hold despite the average under-exposure. The report will
state which of those two happened, including the CAGR ex the best episode.

## 7. Data and causality notes

- The 1-minute archive starts 2016-01-04. The daily yahoo archive starts
  2015-01-02 and is used **only to warm the volatility estimators** before the
  first 1-minute session; every decision in the evaluation window uses data
  through that session's close only.
- Daily OHLC are adjusted by `adjclose/close` (the same factor convention as
  `bt.load_1m`). The signal is computed on the daily bars; execution and marks
  use the 1-minute panel.
- No full-sample statistic enters the weight: every estimator is a trailing
  window or a recursion seeded only with past data.
