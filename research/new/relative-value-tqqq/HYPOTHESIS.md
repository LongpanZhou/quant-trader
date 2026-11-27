# relative-value-tqqq — hypothesis and pre-registration

**Window:** 2016-01-04 .. 2023-12-29 only. The 2024-2026 holdout is not loaded.
**Benchmark bar:** TQQQ 36.72% CAGR / 82.29% max DD / 0.82 Sharpe (1-minute marks).

## 1. Mechanism

The tradable identity behind a leveraged ETF is

```
log(TQQQ_t / QQQ_t) = 2 * log(QQQ_t) - 3 * cum_t(realised variance) + financing/tracking noise
```

so the log TQQQ/QQQ ratio is a **variance-adjusted Nasdaq trend meter**. It rises
when QQQ rises faster than three times its accumulated variance drag, and falls
when the trend breaks or when variance expands. This is not the froth/discount
level used by `ratio-pairs`; the signal here is the **change** in the ratio over
a medium horizon, i.e. whether the leverage cycle is currently compounding for
the holder or against him.

Three facts motivate the rule:

1. TQQQ's 82% drawdown is not a constant property of the Nasdaq; it is created
   by 3x daily compounding through a trend break plus a variance spike. The
   ratio momentum turns down at exactly those transitions because both terms
   (2 x QQQ trend and -3 x variance) move against TQQQ at the same time.
2. A dollar of TQQQ is only worth its leverage when the ratio is not in a
   drawdown. When `log(TQQQ/QQQ)` has fallen materially over ~100 sessions, the
   position has been losing the leverage-cycle race; the next dollar is better
   spent on unlevered QQQ.
3. Variance drag is quadratic. Scaling the TQQQ sleeve down as QQQ's 20-day
   realised volatility rises from 30% to 40% keeps most of the up-capture while
   removing the convex left tail. The filter is continuous, not a cliff.

The strategy is **always fully invested** (long-biased): QQQ is the fallback,
TQQQ is the satellite, and no cash timing is used. This keeps the comparison
against TQQQ honest — the only question is whether the leverage-cycle signal
beats holding the 3x fund.

## 2. Exact rules

All signals are computed from the **close of session t** and applied from the
**open of session t+1**. There is no same-bar information.

Let `R_t = TQQQ_close_t / QQQ_close_t`, `r_t = log R_t`.

* `mom_t = r_t - r_{t-100}` — 100-session ratio momentum.
* `v_t = std(log(QQQ_close/QQQ_close_prev), 20 sessions) * sqrt(252)` — QQQ
  annualised realised volatility.
* `w_tqqq_t = clip((0.40 - v_t) / (0.40 - 0.30), 0, 1)` if `mom_t > -0.10`,
  otherwise `0`.
* `w_qqq_t = 1 - w_tqqq_t`.

The TQQQ weight is held constant inside session `t+1`; the simulator executes
the target at the next bar open (09:31 on the 1-minute panel), with the standard
2% band and 1 bp/5 bp/10 bp one-way costs. Weights are fractions of equity,
non-negative, sum to 1.

At the first development session there is no prior panel close, so the strategy
is 100% QQQ. Pre-2016 Yahoo adjusted daily closes are used **only** to warm the
100-session ratio momentum and 20-session volatility; the performance window
starts 2016-01-04.

## 3. Why it should beat TQQQ

TQQQ's arithmetic is path-dependent. In a smooth bull market the ratio rises and
the strategy is 100% TQQQ. In a trend break or a variance spike the ratio
momentum turns negative and/or the vol filter cuts the sleeve; the book moves to
QQQ, which has roughly one third of TQQQ's downside and no daily-reset drag.
The expected result is a large reduction in max drawdown (from ~82% to ~50-60%)
with CAGR at or above TQQQ's, because the strategy gives up only part of the
strong years and avoids the -80% years.

## 4. Falsifiers

The hypothesis is rejected if any of the following holds on the development
window:

1. CAGR ≤ 36.72% at 1 bp, or max DD ≥ 82.29%.
2. The edge disappears at 5-10 bp (turnover is low, so this would indicate the
   result is a microstructure artefact).
3. A static blend with the same average QQQ/TQQQ weights matches the CAGR and
   drawdown (then the result is just beta, not timing).
4. A block-permutation placebo with the same weight distribution and run lengths
   matches the result (then the timing carries no information).
5. The result is concentrated in a single year or a single cut (2016-2019 vs
   2020-2023), or removing 2023 collapses it.
6. The signal is indistinguishable from a plain QQQ trend gate — we report the
   decomposition and the correlation, and say so if the "relative value" label
   is doing no work.

## 5. Pre-registered grid (8 combinations)

Fixed: `mom_min = -0.10`, `v_lo = v_hi - 0.10`, continuous vol scaling,
QQQ fallback. The grid varies the two structural horizons:

| # | ratio momentum n | vol band (v_lo, v_hi) |
|---:|---:|---|
| 1 | 60 | 0.25, 0.35 |
| 2 | 60 | 0.35, 0.45 |
| 3 | 80 | 0.25, 0.35 |
| 4 | 80 | 0.35, 0.45 |
| 5 | 100 | 0.25, 0.35 |
| 6 | **100** | **0.30, 0.40** (primary) |
| 7 | 100 | 0.35, 0.45 |
| 8 | 120 | 0.30, 0.40 |

The centre is chosen from the mechanism (roughly half a year of ratio momentum;
30-40% QQQ vol is the range where 3x drag becomes convex). The grid deliberately
probes both sides; the report must show the whole plateau, not just the best
cell.

**Exploration disclosure.** A daily-bar screen on the development window was
used to choose the mechanism family (ratio momentum + vol scale) and the centre
of the grid. This is in-sample design, not out-of-sample validation. The final
numbers below are 1-minute, but they are not a clean holdout; the honest test is
the plateau, the placebo, the static-blend attribution and the cut tests.

## 6. Expected effect

| metric | expectation |
|---|---|
| CAGR (1 bp) | 38-46% |
| max DD | 48-60% |
| Sharpe | 0.95-1.05 |
| average TQQQ weight | 0.70-0.78 |
| corr to TQQQ (daily) | 0.85-0.92 |
| beta to TQQQ | 0.58-0.68 |
| static blend at same weights | 30-34% CAGR / 65-72% DD |

If the realised numbers are in these ranges and the placebo/static blend are far
worse, the strategy passes the numeric bar. Even then the report will state
plainly that the edge is variance-adjusted TQQQ beta timing, not a
market-neutral relative-value premium.

## 7. Relation to existing work

* `research/agents2/ratio-pairs` and `research/revisit/ratio-pairs`: hold QQQ by
  default, use the **level** of the ratio versus a 200-day mean (froth/discount)
  and a v20/v60 stress ratio, and only take a bounded 40% TQQQ sleeve after a
  deep discount turns up. They earn 18.96% dev CAGR. This strategy uses ratio
  **momentum** (not level), a continuous absolute-vol scale, and a full TQQQ
  sleeve in the favourable state; no froth threshold, no stress ratio, no
  40% cap.
* `ratio-froth` (the original): the banned 165-day QQQ SMA plus 4% armed stop,
  with a ratio-level overlay. This strategy contains no QQQ moving average, no
  stop, and no froth/discount level.
* `fast-trend-vol`, `cross-asset-momentum` and the other `research/new` agents:
  they use price trend, cross-asset momentum or intraday setups. This one is
  driven by the TQQQ/QQQ log ratio, a leveraged-fund-specific quantity.
