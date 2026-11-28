# family-kelly-sizing — hypothesis and pre-registration

**Slug:** `family-kelly-sizing`
**Family:** Kelly sizing
**Development window:** 2016-01-04 .. 2023-12-29 only. 2024-2026 is not loaded
or inspected.
**Benchmark bar:** TQQQ 36.72% CAGR / 82.29% max DD / 0.82 Sharpe (published
1-minute-mark bar). TQQQ on this panel is 35.81% / 82.30% / 0.80.

## 1. Mechanism

A fixed volatility target sizes the book by risk, not by edge. Kelly sizing
sizes it by the estimated growth rate of the bet:

```
f* = argmax_f E[log(1 + f * x)]
```

where `x` is the excess return of the TQQQ-over-QQQ overlay. For a Gaussian,
`f* = mean(x) / var(x)`. The strategy uses a fourth-order expansion of the log
growth on the empirical sample,

```
g(f) = f*mu - 0.5*f^2*var + (1/3)*f^3*m3 - 0.25*f^4*m4
```

so negative skew (`m3 < 0`) and fat tails (`m4`) reduce the Kelly fraction
relative to the Gaussian ratio. This is the sense in which the sizing uses
mean, variance **and skew**, rather than a pure vol target.

Two edges are estimated:

* `f_q = mean(r_QQQ) / var(r_QQQ)` — QQQ versus cash. If `f_q <= 0`, the
  unlevered index itself has no estimated edge and the book goes to BIL.
* `f_lev` — the Kelly fraction of `r_TQQQ - r_QQQ`, i.e. of the decision to
  replace a QQQ dollar with a TQQQ dollar. This is the leverage-sizing
  decision, not a separate asset-selection model.

The TQQQ weight is `clip(kappa * f_lev, 0, 1)`; QQQ takes the remainder. The
fractional cap is `kappa = 0.90` and the hard TQQQ weight cap is 100% of
capital.

## 2. Exact rules

All inputs use daily closes through session `t`; the target is set at that
close and executed at the first bar open of `t+1`.

1. Simple daily returns `r_Q,t = QQQ_t/QQQ_{t-1} - 1`, `r_T,t` likewise.
2. For each lookback `w in {126, 168, 210}`:
   * `f_q,w = mean(r_Q, w) / var(r_Q, w)`;
   * `f_lev,w = argmax_{f in [0,1]} g_w(f)` on the overlay `r_T - r_Q`, using
     201 equally spaced grid points and the four central moments of the
     window.
3. Average the available estimates: `f_q = mean_w f_q,w`,
   `f_lev = mean_w f_lev,w`. A window contributes only after it is full.
4. If `f_q <= 0` or no window is available: **BIL**.
   Otherwise `w_T = clip(0.90 * f_lev, 0, 1)`, `w_Q = 1 - w_T`, `w_BIL = 0`.
5. The target is held through the next session. Long-only, sum to 1.

## 3. Estimation window and decision clock

| Item | Choice |
|---|---|
| Kelly windows | 126, 168, 210 sessions, averaged |
| Overlay | `TQQQ simple return - QQQ simple return` |
| Expansion | fourth-order log-growth, `f in [0,1]`, 201 grid points |
| Fractional cap | 0.90 |
| Data | local adjusted 1-minute QQQ/TQQQ/BIL panel via `research/bt.py` |
| Decision | close of session `t` |
| Fill | first bar open of `t+1` |
| Costs | 1 bp headline; 5 bp and 10 bp reported |
| Band | 2% notional |

## 4. Why this is not an existing family

* Not a volatility target: the position is the estimated Kelly fraction of the
  leverage overlay, including its skew and kurtosis; there is no
  `target_vol / realised_vol` term.
* Not `relative-value-tqqq` or `ratio-froth`: no TQQQ/QQQ price ratio, no ratio
  momentum, no trend gate.
* Not `vol-scaled-crash-stop`: no drawdown or capitulation event.
* The name `vol-kelly-overlay-v2` in the archive is a different, retired
  volatility-spike reflation strategy; its own documentation says it does not
  use Kelly sizing. This family is the actual Kelly allocator.

## 5. Pre-registered 8-cell grid

| # | windows | kappa |
|---:|---|---:|
| 1 | 126 | 0.80 |
| 2 | 126 | 0.90 |
| 3 | 168 | 0.80 |
| 4 | 168 | 0.90 |
| 5 | 210 | 0.80 |
| 6 | 210 | 0.90 |
| 7 | 126, 168, 210 | 0.80 |
| 8 | **126, 168, 210** | **0.90** (primary) |

The primary is the multi-window average at 90% fractional Kelly. The single
windows are the robustness probes; the 210-session corner is expected to be the
weakest because it adapts slowest to a regime change.

## 6. Falsifiers (pre-registered)

1. 1 bp CAGR <= 36.72% or max DD >= 82.29%.
2. 10 bp CAGR <= 36.72%.
3. Circular-shift placebo CAGR percentile < 90%.
4. Correlation with any current winner > 0.95.
5. Fewer than 100 fills or fewer than 30 independent fill events.
6. Any subperiod with negative CAGR.
7. Static average-weight book within 1 pp of the 1 bp CAGR.

## 7. Expected effect

| metric | expectation |
|---|---|
| CAGR (1 bp) | 37-42% |
| max DD | 52-62% |
| Sharpe | 0.92-1.00 |
| average TQQQ weight | 0.55-0.70 |
| correlation to winners | 0.75-0.90 |

Kelly is an aggressive sizer: it will hold a high TQQQ weight in strong trends
and cut hard when the overlay's mean, variance or skew deteriorate. The
pre-registered placebo threshold is the main risk to acceptance; a high raw
CAGR with a placebo percentile below 90% means the sizing is mostly a
high-TQQQ beta, not a timing edge.
