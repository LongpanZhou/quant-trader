# family-dynamic-risk-parity — hypothesis and pre-registration

**Slug:** `family-dynamic-risk-parity`
**Family:** dynamic risk parity
**Development window:** 2016-01-04 .. 2023-12-29 only. 2024-2026 is not loaded
or inspected.
**Benchmark bar:** TQQQ 36.72% CAGR / 82.29% max DD / 0.82 Sharpe (published
1-minute-mark bar). TQQQ on this panel is 35.81% / 82.30% / 0.80.

## 1. Mechanism

Fixed leverage is fragile because the covariance of QQQ and TQQQ changes. A
risk-contribution allocator should adapt: when TQQQ's marginal risk per unit of
capital rises, equal-risk weights cut it; when QQQ and TQQQ become less
redundant, the diversified sleeve should hold more of both.

The primary object is the **risk-contribution vector** of the book, not a
volatility-target rule. At each close the strategy estimates the 63-session
covariance of daily QQQ/TQQQ log returns and solves for the long-only weights
whose risk contributions are equal across the risky sleeve.

BIL is deliberately **outside the risk budget**. A near-zero-vol asset in an
equal-risk optimisation absorbs almost all of the capital: its risk
contribution is tiny even at a 99% weight, so the optimiser puts everything in
BIL. The honest way to include cash in a long-only book is as the residual
asset, not as an equal-risk asset. The risky sleeve is therefore QQQ/TQQQ, and
BIL receives the unallocated fraction (zero in the headline).

## 2. Exact rules

All inputs use daily closes through session `t`; the target is set at that
close and executed at the first bar open of `t+1`.

1. `Sigma_t` is the sample covariance of daily log returns over the prior 63
   sessions (ddof=0).
2. Let `s_T = sqrt(Sigma_TT)`, `s_Q = sqrt(Sigma_QQ)`,
   `rho = Sigma_TQ / (s_T s_Q)`.
3. Solve the two-asset equal-risk condition `RC_T = RC_Q` for
   `t = w_Q / w_T`. With `b = 0.5` the closed-form root is the positive root of

   ```
   (s_Q^2) t^2 + rho s_T s_Q (1 - target) t - target s_T^2 = 0,
   target = (1 - b) / b = 1
   ```

4. `w_T = 1 / (1 + t)`, `w_Q = 1 - w_T`, `w_BIL = 0`.
5. The target is held through the next session. Weights are long-only, sum to
   1, and are fractions of equity.

The solution is mathematically an equal-risk-contribution portfolio; because
`rho ~ 0.99` and `s_T ~ 3 s_Q`, it is numerically a 75/25 QQQ/TQQQ mix.

## 3. Estimation window and decision clock

| Item | Choice |
|---|---|
| Covariance window | 63 sessions |
| Risk budget | TQQQ 50% of risky-sleeve risk |
| Data | local adjusted 1-minute QQQ/TQQQ/BIL panel via `research/bt.py` |
| Decision | close of session `t` |
| Fill | first bar open of `t+1` |
| Costs | 1 bp headline; 5 bp and 10 bp reported |
| Band | 2% notional |

## 4. Why this is not an existing family

* Not a volatility target: the weight is the solution of a risk-contribution
  equality, not `target_vol / realised_vol`.
* Not `relative-value-tqqq` or `ratio-froth`: no TQQQ/QQQ ratio and no trend
  gate.
* Not `vol-scaled-crash-stop`: no drawdown trigger.
* The object is the covariance/risk-contribution vector; the output happens to
  be a slow 75/25 mix because the two risky assets are nearly collinear.

## 5. Pre-registered 8-cell grid

| # | window | risk_budget_tqqq |
|---:|---:|---:|
| 1 | 21 | 0.50 |
| 2 | 42 | 0.50 |
| 3 | **63** | **0.50** (primary) |
| 4 | 126 | 0.50 |
| 5 | 252 | 0.50 |
| 6 | 63 | 0.40 |
| 7 | 63 | 0.60 |
| 8 | 63 | 0.70 |

The primary is the canonical equal-risk cell: 63 sessions, 50/50 risk budget.

## 6. Falsifiers (pre-registered)

1. 1 bp CAGR <= 36.72% or max DD >= 82.29%.
2. 10 bp CAGR <= 36.72%.
3. Circular-shift placebo CAGR percentile < 90%.
4. Correlation with any current winner > 0.95.
5. Fewer than 100 fills or fewer than 30 independent fill events.
6. Any subperiod with negative CAGR.
7. Static average-weight book within 1 pp of the 1 bp CAGR.

Criterion 7 is the important one for this family: if a fixed 75/25 mix matches
the dynamic allocator, the risk-contribution machinery is not adding value.

## 7. Expected effect

| metric | expectation |
|---|---|
| CAGR (1 bp) | 22-28% |
| max DD | 45-58% |
| Sharpe | 0.80-0.90 |
| average TQQQ weight | 0.20-0.30 |

The honest prior is that this family will **not** clear the TQQQ CAGR bar. The
test is whether it delivers a materially better drawdown or Sharpe than a fixed
1.5x QQQ mix. A negative result is a valid outcome and is reported as such.
