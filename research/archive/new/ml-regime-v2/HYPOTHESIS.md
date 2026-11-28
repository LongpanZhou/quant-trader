# Hypothesis: walk-forward path-drawdown-risk regime allocator

Status: pre-registered before the 1-minute evaluation. Development window only:
**2016-01-04 .. 2023-12-29**. Holdout (2024-2026) is never loaded or inspected.

## 1. Mechanism

A 3x daily-reset ETF earns roughly `3*r - 4.5*sigma^2` per day. The drift term
is what pays, but it is only realised if the position survives the path. TQQQ's
2016-2023 return came with an 82% peak-to-trough drawdown, and most of the
damage happened in a few volatility regimes (2018Q4, 2020Q1, 2022) where the
variance drag and the crash path overwhelmed the drift.

Two causal states are enough to separate the payoff:

1. **Direction / momentum.** Equity index returns have positive time-series
   persistence at the 3-7 month horizon. A majority vote of three simple
   momentum signs (QQQ 60-, 100- and 150-session total returns > 0) is a
   diversified trend state. It is deliberately *not* the 165-day moving-average
   gate used by the existing round-1/2 base.
2. **Path risk.** The probability that TQQQ suffers a >15% peak-to-trough
   drawdown over the next 20 sessions is forecast by a walk-forward logistic
   model from volatility-term-structure features. High short-horizon realised
   volatility, high range volatility and a high downside-semivariance share are
   the precursors of crash paths. This is a
   *path* label, not the terminal-return label used by `ml-crash-overlay-winner`
   and not the TQQQ-beats-BIL label used by `ml-classifier`.

The allocator holds TQQQ only when both states agree (momentum up, path risk
low), moves to QQQ when momentum is up but path risk is elevated (keep some
equity beta, drop the 3x reset), and holds BIL when momentum is down or path
risk is extreme.

Why it should beat TQQQ buy-and-hold: TQQQ's compounded return is reduced by
variance drag and by the depth of its drawdowns. Avoiding the handful of
high-risk months raises the compounded return even after giving up some upside,
and cuts the maximum drawdown substantially. The risk is that the model exits
during the sharp recoveries (2020Q2, 2023), which is the main falsifier below.

## 2. Exact rules

Daily decisions at the close of session `t`, executed at the open of session
`t+1` (the harness does this automatically for both the daily and 1-minute
panels).

Let `q_t` be the QQQ close.

- Momentum score: `M_t = mean(1[q_t/q_{t-60} > 1], 1[q_t/q_{t-100} > 1],
  1[q_t/q_{t-150} > 1])`. Positive state if `M_t >= 2/3`.
- Risk model: L2 logistic regression trained only on labels whose 20-session
  forward window ends before the test quarter starts (purge = 36 calendar days,
  well beyond the 20-session window), refit every calendar quarter, features
  standardised on the training window only. Label
  `y_t = 1[TQQQ max drawdown over t+1..t+20 > 15%]`.
- Features (9): QQQ 5/10/20/60-session realised vol (annualised), 5d/60d and
  20d/60d vol ratios, 20-session Parkinson range vol, 20-session downside
  semivariance share, 20-session vol-of-vol.
- Let `p_t` be the model's probability of the path-drawdown label.

Allocation for session `t+1`:

| Condition | Weight |
|---|---|
| `M_t < 2/3` | 100% BIL |
| `M_t >= 2/3` and `p_t < 0.60` | 100% TQQQ |
| `M_t >= 2/3` and `0.60 <= p_t < 0.90` | 100% QQQ |
| `M_t >= 2/3` and `p_t >= 0.90` | 100% BIL |

Warm-up: the model needs 200 labelled training rows. Before the first
prediction the strategy holds BIL. No full-sample fitting, no normalisation
using future data, no weight on any asset above 1, weights sum to 1.

## 3. Pre-registered parameter grid (8 combinations)

Primary configuration (chosen a priori from the daily screen, **not** from the
final 1-minute result): expanding training window, `lo = 0.60`, `hi = 0.90`.

The grid varies only the training window and the two probability thresholds:

| # | Training window | `lo` (TQQQ max risk) | `hi` (BIL min risk) |
|---|---:|---:|---:|
| 1 (primary) | expanding | 0.60 | 0.90 |
| 2 | expanding | 0.60 | 0.85 |
| 3 | expanding | 0.65 | 0.90 |
| 4 | expanding | 0.65 | 0.85 |
| 5 | 750 sessions | 0.60 | 0.90 |
| 6 | 750 sessions | 0.60 | 0.85 |
| 7 | 750 sessions | 0.65 | 0.90 |
| 8 | 750 sessions | 0.65 | 0.85 |

Fixed: 20-session label horizon, 15% path-drawdown threshold, 9 features,
quarterly refit, 22-session purge, momentum set (60,100,150) with a 2/3 vote.

Neighbour checks (reported, not used for selection): label horizon 10 and 40
sessions, drawdown threshold 10% and 20%, momentum sets (60,100) and
(100,150,200), `lo`/`hi` +/-0.05, monthly refit, and a one-session execution
delay.

## 4. Benchmarks

1. TQQQ buy-and-hold: **36.72% CAGR / 82.29% max DD / 0.82 Sharpe** on 1-minute
   marks (the pass bar).
2. QQQ and BIL buy-and-hold on the same marks.
3. **Simple vol rule**: same momentum state, but replace the ML probability with
   `rv5 < 0.60` (the centre of the daily-screen plateau). This is the honest
   "does the ML add anything?" control.
4. The existing 165-day QQQ regime (for correlation only; not used in the
   strategy).

## 5. Falsifiers

The hypothesis is false if any of the following holds on the development
window:

- OOS AUC of the risk model is below 0.60, or its accuracy is below the base
  rate.
- The strategy's 1-minute CAGR is not above 36.72%, or its max drawdown is not
  below 82.29%.
- The result is not a plateau: nearby grid points lose more than ~10 pp of CAGR
  or breach the drawdown bar.
- The ML risk gate does not beat the simple `rv5 < 0.60` rule on CAGR at similar
  drawdown. In that case the honest conclusion is "the ML adds nothing over the
  vol rule"; the strategy may still pass, but it must be reported as a
  vol-regime strategy with an ML calibration layer, not as an ML edge.
- The result is driven by fewer than 100 round trips or by one year (e.g. 2020
  or 2023); report the event count and the ex-year result.
- The edge disappears at 5 bp or 10 bp costs.

## 6. Expected effect

On the daily screen the momentum-only state produced roughly 45-52% CAGR with
62% drawdown; adding the risk gate cut the drawdown to roughly 36-42% while
keeping CAGR in the 50-60% range. I expect the 1-minute result to be slightly
worse than the daily mark (intraday troughs) but still above the 36.72% bar,
with a max drawdown well below 60%. I expect the simple `rv5 < 0.60` rule to
match or beat the ML gate; the report will state that plainly if it happens.
