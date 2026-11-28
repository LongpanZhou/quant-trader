# Realized-volatility term structure on TQQQ

**Slug:** `vol-term-structure`
**Development window:** 2016-01-04 → 2023-12-29 (only)
**Status:** pre-registered before the final development run. The holdout
(2024-01-02 → 2026-10-23) is not loaded, inspected, or used for any choice.

## 1. Hypothesis

TQQQ is a 3x daily-reset fund. Its long-run return is high, but its drawdowns
are dominated by a small number of volatility regime shifts: the short end of
realized volatility rises faster than the long end, the realized-vol term
structure inverts, and the leveraged fund compounds the decline. A signal built
on the **slope** of realized volatility — the ratio of short-window to
long-window RV — should therefore identify stress earlier than a price trend
and more selectively than a plain volatility target.

The economic claim is:

- When short-run RV is **below** its longer-run level (upward-sloping / calm
  term structure), volatility is mean-reverting down and the risk of a
  compounding drawdown is low. Hold TQQQ.
- When the term structure **inverts** (short RV > long RV), the market is in a
  volatility expansion; forward risk is asymmetric. De-risk.
- When the short end **spikes** (5-day RV more than ~1.8x 60-day RV), the
  expansion is acute. Go to cash regardless of the slower signals.
- A slow price trend (QQQ above its 165-session SMA) is a second, independent
  risk state. Trend and term structure are combined as two equal sleeves rather
  than as a single all-or-nothing rule, because their exits occur at different
  times (trend catches slow bears; term structure catches fast ones).

This is deliberately **not** a volatility target. A vol target scales exposure
by the *level* of volatility and is therefore fully invested in a high-but-
falling vol regime and only lightly invested in a low-but-rising one. The term
structure ratio is dimensionless: it can be calm at a high level and inverted at
a low level. The level is not used at all in the primary rule.

## 2. Data and causality

- 1-minute adjusted QQQ/TQQQ/BIL bars from `data/intraday-hf/`, regular session
  only, `2016-01-04 09:30` → `2023-12-29 15:59` ET. The panel is requested with
  `end="2023-12-29"`; the daily parquet reads are filtered with
  `date <= 2023-12-29` so no 2024+ row is materialised.
- Daily signals use the official adjusted daily closes. 2015 is used only as
  indicator warmup (the 165-day SMA and 60-day RV need it); no 2015 position is
  taken and no 2015 return enters the evaluation.
- A weight for session `d+1` is computed from the close of session `d` and
  filled at the **open of session `d+1`** by `research/bt.py`. Inside the
  session the weight is held constant; the 15:59 bar carries the next session's
  target so the harness executes it at the next open. No intraday signal is
  used.
- Long-only, weights ≥ 0, sum ≤ 1. Idle weight is cash at 0%. No BIL sleeve in
  the primary (a BIL-idle variant is reported as a sensitivity, not selected).
- 2% no-trade band, 1 bp headline slippage, 5 bp and 10 bp sensitivities.

## 3. Exact primary rule

Let `C_t` be the QQQ adjusted close of session `t`, `r_t = ln(C_t/C_{t-1})`,
and

```
RV_n(t) = sqrt( mean(r_{t-n+1..t}^2) ) * sqrt(252)
```

Define, at the close of session `t`:

```
trend_t = 1 if C_t > SMA_165(C)_t else 0
calm_t  = 1 if RV_20(t) / RV_60(t) < 0.95 else 0
spike_t = 1 if RV_5(t)  / RV_60(t) > 1.80 else 0

raw_t   = 0.50 * trend_t + 0.50 * calm_t
w_t     = 0 if spike_t else raw_t
```

`w_t` is the TQQQ target for session `t+1`; the remainder is cash. The four
non-spike states are therefore:

| trend | term structure | weight |
|---|---|---:|
| up | calm (RV20/RV60 < 0.95) | 1.00 |
| up | inverted | 0.50 |
| down | calm | 0.50 |
| down | inverted | 0.00 |
| any | acute spike (RV5/RV60 > 1.8) | 0.00 |

The 50/50 blend is an equal-risk allocation to two independent state machines,
not a tuned weight. The two sleeves rarely turn off together, which is the
diversification the strategy relies on.

## 4. Pre-registered grid (8 cells, one parameter at a time)

The centre was chosen as the middle of the broad region that survived a coarse
exploratory screen of thresholds and windows. The screen is disclosed here; the
eight cells below were frozen before the final 1-minute evaluation, and the
report shows the whole plateau rather than the best cell.

| # | cell | change from primary |
|---:|---|---|
| 1 | primary | SMA165, RV20/RV60 < 0.95, spike 1.8, 50/50 |
| 2 | theta 0.92 | calm threshold 0.92 |
| 3 | theta 0.98 | calm threshold 0.98 |
| 4 | SMA150 | trend window 150 |
| 5 | SMA180 | trend window 180 |
| 6 | spike 1.6 | acute-spike threshold 1.6 |
| 7 | spike 2.0 | acute-spike threshold 2.0 |
| 8 | blend 40/60 | trend sleeve 0.40, term-structure sleeve 0.60 |

Supplementary diagnostics (not used for selection): blend 60/40, SMA120/200,
RV windows 10/60, 20/90, 30/60, all signals on TQQQ closes, no-trend,
no-term-structure, no-spike, plain trend, plain term-structure gate, 14% vol
target, vol-level gate, BIL idle, costs 5/10 bp.

## 5. Evaluation and falsification

Primary metric: `bt.run` on the 1-minute panel, 2% band, 1 bp, `bt.stats` with
`bars_per_year = 252*390`. Pass requires **dev CAGR > 36.72%** and
**max DD < 82.29%**; the design target is DD < 60%. Sharpe, exposure, daily
correlation to TQQQ, fills, turnover and yearly returns are reported.

The strategy is falsified as an *edge* if:

1. dev CAGR ≤ 36.72% or DD ≥ 82.29% (hard fail), or
2. the pre-registered grid collapses outside a narrow cell (no plateau), or
3. a block-shuffled / circularly-shifted placebo matches the actual CAGR, or
4. the term-structure sleeve adds nothing over a simple volatility-level rule
   (RV20 gate or 14% vol target) at comparable exposure, or
5. the result is concentrated in one year or a handful of days such that the
   relative edge over TQQQ disappears in cut tests.

## 6. Known risks

- Thresholds (0.95, 1.8, 165) were chosen on the development window. The grid
  and placebo are the only honest defence; the holdout is a single shot.
- The 2020 COVID crash is a large contributor. The spike rule is economically
  motivated, but one crash is one observation.
- A calm, persistent bull with no inversions would leave the term-structure
  sleeve partly in cash; the strategy can lag TQQQ in a strong low-vol rally
  (2017 and 2019 are examples).
- TQQQ's daily-reset path dependence means a timing strategy's compounded
  return is not a simple function of QQQ timing; all results are simulated on
  the actual TQQQ bars.
- No shorting, no leverage above 100%, no borrow assumptions.
