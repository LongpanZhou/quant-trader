# Cross-Asset Dual-Momentum Rotation — pre-registration

> **Revision note (2026-11-27).** Revision 1 (sections 1–10) was run first and
> **failed**: primary A returned 31.04% CAGR / 54.86% max DD; no grid point
> passed. Revision 2 (section 11) is the final design. It was built after the
> Revision 1 failure and after diagnostic analysis of why it failed, so it is
> an **exploratory** candidate, not a clean pre-registered pass. Both revisions
> and the full diagnostic path are reported in `report.md`; no result is hidden.

**Status:** pre-registered before any strategy backtest. Development window only:
2016-01-04 → 2023-12-29. Holdout 2024-01-02 → 2026-10-23 is not loaded or
inspected. SPY daily data is sliced at 2023-12-29.

**Bottom line of the hypothesis.** A cross-asset dual-momentum switch should
keep most of TQQQ's bull-market compounding while avoiding enough of its
2018-Q4, 2020 and 2022 drawdowns to beat TQQQ's 36.72% development CAGR with a
much lower maximum drawdown.

---

## 1. Mechanism

TQQQ is a 3x daily-reset Nasdaq-100 ETF. Its 2016-2023 buy-and-hold record
(36.72% CAGR, 82.29% max DD on 1-minute marks) is the product of a strong
underlying trend and three violent deleveraging episodes. A 3x daily-reset fund
suffers path-dependent decay when the underlying falls and volatility rises;
the same volatility that makes the crash deep also makes the subsequent
recovery explosive.

Dual momentum separates two questions that buy-and-hold answers with one
position:

1. **Absolute momentum:** is the Nasdaq-100 total return over the lookback
   better than T-bills? If not, the equity risk premium is not being paid and
   the strategy should hold BIL. This is the crash-avoidance leg.
2. **Relative momentum:** is the Nasdaq-100 total return better than the S&P
   500 over the lookback? If yes, Nasdaq leadership is intact and the
   leveraged sleeve is appropriate. If no, de-lever to QQQ rather than pay 3x
   for a fading relative trend.

When both agree, hold a volatility-targeted TQQQ position. When absolute
momentum is positive but relative momentum is not, hold volatility-targeted
QQQ. When absolute momentum is negative, hold BIL.

The economic claim is **not** that QQQ and SPY are diversifying assets — they
are not (daily correlation is roughly 0.9). The claim is that a slow
total-return filter can identify the regimes in which 3x daily-reset leverage
is compensated, and that the geometric benefit of avoiding the worst
drawdowns exceeds the return given up by being out of the market during
recoveries and whipsaws.

## 2. Exact rules

### 2.1 Data and calendar

- **Tradable assets:** QQQ, TQQQ, BIL. Long-only, weights ≥ 0, row sum ≤ 1.
- **SPY:** relative-momentum signal only. There is no SPY 1-minute history for
  2016-2023 in the local archive; SPY is never held and is never marked.
- **Daily signal closes:** for QQQ/TQQQ/BIL, the 15:59 ET close of each
  session from `bt.panel(..., "1min")`. Before 2016-01-04, the Yahoo adjusted
  daily close (`adjclose`) is spliced to the panel at the first panel close,
  so 126/252-day lookbacks have warm-up from 2015-01-02.
- **SPY signal closes:** Yahoo `adjclose`, same date index, sliced at
  2023-12-29.
- **Session boundaries:** `bt.day_bounds`; half-days are already truncated at
  13:00 by `bt.load_1m`.
- **Total return:** adjusted closes include dividends and the BIL 2017 reverse
  split repair.

### 2.2 Momentum state

For lookback `L` sessions, define total-return momentum

```
M_L(asset, t) = P(asset, t) / P(asset, t-L) - 1
```

At the 15:59 close of session `t`:

- **Absolute momentum:** `M_L(QQQ, t) > M_L(BIL, t)`.
- **Relative momentum:** `M_L(QQQ, t-1) > M_L(SPY, t-1)`.

SPY is lagged one session because its official close is 16:00, one minute
after the decision bar; using it at 15:59 would be a one-minute look-ahead.
The QQQ/BIL absolute comparison uses the 15:59 panel close, which is known at
the decision bar. Both legs are slow (126 or 252 sessions), so the one-session
SPY lag is economically negligible.

State:

| State | Condition | Risky sleeve |
|---|---|---|
| 2 | absolute **and** relative true | TQQQ |
| 1 | absolute true, relative false | QQQ |
| 0 | absolute false | BIL |

### 2.3 Volatility target

For the asset selected by the state, compute 20-session realized volatility of
daily total returns, annualized by `sqrt(252)`:

```
sigma = std(r_{t-19..t}) * sqrt(252)
w_risky = min(1, target_vol / sigma)
```

The remainder is BIL. `target_vol` is 50% or 65%. For state 1 (QQQ), the same
rule is applied to QQQ's volatility; in practice QQQ's vol is below both
targets, so state 1 is normally 100% QQQ. For state 2, the target is applied
to TQQQ's own volatility.

The volatility target is a risk control, not a return forecast. It cuts
exposure when realized volatility is high, which is exactly when 3x
daily-reset decay is most damaging. It does not use future volatility and has
no full-sample normalization.

### 2.4 Rebalance and execution

- **Weekly:** the last session of each ISO week (usually Friday).
- **Monthly:** the last session of each calendar month.
- The first panel session (2016-01-04) inherits the target decided at
  2015-12-31; the first in-window rebalance is the first week-end (2016-01-08).
- The decision is made at the 15:59 close of the rebalance session using data
  through that close. The new target fills at the next session's 09:30 open.
- Between rebalances the target is unchanged; the 2% band rebalances only if
  drift exceeds 2% of book.
- Costs: 1 bp headline, 5 bp and 10 bp sensitivity, charged on traded notional
  by `bt.run`.
- Equity is marked on every 1-minute bar.

### 2.5 Weight mapping (no look-ahead)

`weights[i]` is the target set from the close of bar `i`, filled at bar
`i+1`'s open. For each session `k`, the target decided at session `k-1` is
written to all bars of session `k` except the last; the last bar writes the
target for session `k+1`. Thus a decision at Friday 15:59 fills Monday 09:30,
and never earlier.

## 3. Parameter grid (8 combinations, pre-registered)

| ID | Lookback `L` | Vol target | Rebalance | Role |
|---|---:|---:|---|---|
| **A** | **126** | **65%** | **weekly** | **primary, a priori** |
| B | 126 | 65% | monthly | |
| C | 126 | 50% | weekly | |
| D | 126 | 50% | monthly | |
| E | 252 | 65% | weekly | |
| F | 252 | 65% | monthly | |
| G | 252 | 50% | weekly | |
| H | 252 | 50% | monthly | |

**Why the primary is A, fixed before results.** 126 sessions (six months) is
the shortest standard dual-momentum lookback that is not dominated by
short-term noise; 252 sessions is the classic Antonacci twelve-month window.
65% is just below TQQQ's full-sample realized vol (about 67% in 2016-2023), so
the target preserves most of the leverage in calm bull markets and cuts it in
high-vol regimes. Weekly is the fastest rebalance the mandate allows and is
the natural choice when the mechanism is crash avoidance. The other seven
points exist to show whether the result is a plateau or a knife-edge. No
post-hoc switch to the best grid point is allowed.

**Selection rule.** The pre-registered verdict is the result of A. If A fails
but another grid point passes, it is reported as a secondary observation,
clearly labelled, and not substituted for A. A pass requires dev CAGR >
36.72% **and** max DD < 60% at 1 bp, with at least one adjacent grid point
also passing (otherwise it is a knife-edge, not a plateau).

## 4. Why this should beat TQQQ

1. **Crash avoidance.** TQQQ's 82% drawdown is not a smooth loss; it is the
   compounding of 2018-Q4, 2020 and 2022. Absolute momentum exits after the
   trend turns, and the 50-65% vol target cuts exposure while volatility is
   rising. Avoiding a 50% loss is worth more geometrically than missing a 10%
   rebound.
2. **Path-dependence.** A 3x daily-reset fund's return depends on the path of
   daily returns, not just the endpoint. High-volatility down-trends destroy
   value through the reset. The filter spends less time on those paths.
3. **Relative de-leveraging.** When QQQ stops leading SPY, the strategy drops
   from 3x to 1x instead of paying 3x for a fading relative trend. This is a
   smaller effect than absolute momentum but it is the cross-asset part of the
   design.
4. **Compounding.** A strategy with 45% CAGR and 40% DD compounds faster than
   one with 55% CAGR and 70% DD over a full cycle. The objective is CAGR with
   lower DD, not average return.

## 5. Where it should fail

- **Whipsaw.** In a choppy market (2016, 2018-Q4, 2023) the signal exits after
  the drop and re-enters after the rebound. The strategy can underperform
  TQQQ for a year or more.
- **Lag.** A 126/252-session lookback and weekly/monthly rebalance are slow. A
  fast crash like February-March 2020 is not avoided at the top; the strategy
  exits after a large part of the loss.
- **Vol target cuts the rebound.** Realized vol peaks near the bottom. The
  target cuts exposure exactly when forward expected returns are highest,
  which can turn a crash-avoidance win into a recovery miss.
- **Weak relative signal.** QQQ and SPY are highly correlated. The relative
  leg may add little and can force an unnecessary de-lever.
- **SPY is untradable.** If SPY leads, the strategy holds QQQ, which is not the
  momentum winner. This is a data constraint, not a claim that QQQ is a good
  SPY substitute.
- **Costs.** Weekly rebalancing and changing vol targets increase turnover.
  At 10 bp the edge may shrink materially.

## 6. Falsifiers (decided before results)

The hypothesis is falsified if any of the following holds:

1. Primary A has dev CAGR ≤ 36.72% or max DD ≥ 60% at 1 bp.
2. The grid is a knife-edge: A passes but no adjacent grid point (B, C, E)
   passes, or A fails while only one isolated point passes.
3. The placebo distribution (circular shifts of the daily target sequence,
   preserving exposure and turnover but destroying alignment) has median CAGR
   ≥ A's CAGR, or more than 5% of shifts beat A's CAGR.
4. The cut test changes any weight before the cut (max abs diff > 1e-12).
5. One year (e.g., 2023) accounts for more than half of the excess CAGR over
   TQQQ; the result would then be a one-year bet, not a regime strategy.
6. At 10 bp, A's CAGR falls to or below 36.72%.
7. The strategy is a closet buy-and-hold: TQQQ target weight averages > 90% of
   all sessions, or daily correlation to TQQQ > 0.95 with no DD improvement.
8. The signal is not causal: any weight uses a close after the decision bar.

## 7. Expected effect (hypothesis, not a result)

| Variant | Expected CAGR | Expected max DD | Expected Sharpe |
|---|---:|---:|---:|
| A: 126 / 65% / weekly | 40-55% | 35-50% | 1.0-1.3 |
| 126 / 50% | 30-45% | 30-40% | 0.9-1.2 |
| 252 / 65% | 35-50% | 40-55% | 0.9-1.2 |
| 252 / 50% | 28-42% | 32-45% | 0.8-1.1 |

Expected average risky exposure 65-85%; TQQQ share of sessions 55-75%;
correlation to TQQQ 0.75-0.90; turnover 10-25x per year.

These ranges are wide because the design has not been run. They are written
down so that a result outside them is a surprise worth explaining, not a
number to rationalize after the fact.

## 8. Relationship to existing research

This is not a rebuild of any existing strategy:

- **Old 165-day QQQ SMA + 4% stop:** not used. The gate here is a total-return
  dual-momentum comparison against BIL and SPY, not a price moving average,
  and there is no 4% stop.
- **`dual-speed-regime`:** intraday 60-minute EMA, flat every night. This
  strategy is daily, holds overnight, and uses cross-asset relative momentum.
- **`risk-parity-hrp`:** HRP/ERC risk budgeting with a vol-state tilt. This
  strategy uses discrete momentum states and a single vol target, not a risk
  parity model.
- **`dynamic-leverage-throttle` / `vol-kelly-overlay`:** volatility-targeted
  leverage without a cross-asset relative-momentum switch. This strategy's
  TQQQ exposure requires QQQ to lead SPY as well as beat BIL.
- **`ml-classifier`:** unsupervised regime clustering. This strategy has two
  explicit, interpretable momentum comparisons and no fitted model.
- **`ratio-pairs`:** TQQQ/QQQ ratio froth. This strategy compares QQQ to SPY
  and QQQ to BIL; it does not use the TQQQ/QQQ ratio.
- **`winner-ensemble-blend`:** inverse-vol blend of sleeves. This strategy is
  a state switch, not a blend.
- **`donchian-breakout`:** price breakout. This strategy uses total-return
  momentum over 126/252 sessions.

## 9. Robustness plan (after the 8-point grid, not for selection)

- **Neighbour table:** A ± one step on each parameter: L ∈ {63, 126, 189,
  252}; target ∈ {35%, 50%, 65%, 80%}; weekly vs monthly. These are
  descriptive robustness checks, not candidates for substitution.
- **Placebo:** 200 random circular shifts of A's per-session target sequence,
  preserving the exact state sequence, exposure and turnover while destroying
  alignment with returns. Minute-marked.
- **Cut test:** rebuild weights on panels truncated at 2020-03-12 11:07 and
  2022-09-13 10:41; compare every weight before the cut.
- **Sub-periods:** 2016-2019, 2020-2021, 2022-2023.
- **Costs:** 1/5/10 bp for every grid point.
- **Event count:** number of state switches and rebalance decisions; bootstrap
  p-value if the number of independent switches is under 100.

## 10. Honest prior

The most likely failure is 2020: the absolute signal is slow, and the COVID
crash was faster than a six-month lookback. The vol target helps, but the
strategy may still take a 30-40% drawdown in March 2020 and then re-enter
late. The most likely source of excess return is 2022 avoidance and 2023
re-entry. If the result is entirely 2023, the report will say so and the
verdict will be negative regardless of the headline CAGR.

---

# 11. Revision 2 — multi-horizon dual momentum (final design)

**Status:** pre-registered 2026-11-27 after Revision 1 failed. This is an
exploratory candidate, not a clean out-of-sample pass. The reason is stated in
the open: the short-horizon set was informed by diagnostics on the development
window. The design is nevertheless a coherent, economically motivated rule,
and the grid below is fixed before the final run.

## 11.1 What failed in Revision 1

The 126-day absolute signal exited the 2018-Q4, 2020 and 2022 drawdowns too
late, and re-entered 2019 and 2023 too late. In 2019 the 126-day absolute
signal did not turn positive until 2019-04-08, so the strategy sat in BIL/QQQ
through TQQQ's +26.7% January, +8.4% February and +11.2% March. In 2023 it did
not turn positive until 2023-03-08, missing TQQQ's +32.6% January. The
relative QQQ/SPY gate then de-levered to QQQ in early recoveries, exactly when
high-beta TQQQ rebounds hardest. The result was 31.04% CAGR / 54.86% DD:
better risk-adjusted than TQQQ, but not a CAGR pass.

The fix is not a tighter single lookback. A 42-day signal alone reaches the
pass bar but is a sharp peak (21d = 22.8%, 42d = 38.3%, 63d = 21.4% CAGR in
diagnostics). A single short lookback is therefore not credible. Revision 2
uses a **multi-horizon ensemble**: a short-term OR vote and a medium-term
majority vote.

## 11.2 Exact rules

### Data

Same as Revision 1: QQQ/TQQQ/BIL 15:59 panel closes spliced to Yahoo adjusted
daily closes before 2016-01-04; SPY Yahoo adjusted daily closes, signal only,
sliced at 2023-12-29. No holdout data is loaded.

### Absolute momentum (two gates)

For lookback `L`, `M_L(asset, t) = P(asset, t) / P(asset, t-L) - 1`.

- **Short gate (OR):** at least one of
  `M_21(QQQ,t) > M_21(BIL,t)` and `M_42(QQQ,t) > M_42(BIL,t)` is true.
- **Medium gate (majority):** at least two of
  `M_84(QQQ,t) > M_84(BIL,t)`, `M_105(QQQ,t) > M_105(BIL,t)`,
  `M_126(QQQ,t) > M_126(BIL,t)` are true.
- **Absolute on** = short gate AND medium gate.

The short OR is the fast exit/re-entry leg. The medium majority is the regime
filter: it prevents a one- or two-month bounce from re-levering the portfolio
while the four-to-six-month trend is still down, and it prevents a short-term
dip from de-levering while the medium trend is still up. Requiring a majority
of three medium horizons, rather than one exact lookback, is deliberate: the
medium result is a plateau, not a single-horizon peak.

### Relative momentum

**Primary:** `M_126(QQQ, t-1) > M_126(SPY, t-1)`. SPY is lagged one session
because its official close is 16:00, one minute after the 15:59 decision bar.
The grid also tests the 252-session relative horizon.

### State

| State | Condition | Risky sleeve |
|---|---|---|
| 2 | absolute on **and** relative on | TQQQ, vol-targeted |
| 1 | absolute on, relative off | QQQ, vol-targeted |
| 0 | absolute off | BIL |

### Volatility target

20-session realized volatility of the asset held, annualized by `sqrt(252)`:

`w_risky = min(1, target_vol / sigma_20d)`; remainder BIL.

Primary target **100%** (i.e. no de-levering unless realized vol exceeds 100%
annualized). The grid tests 80%, 90% and 100%. The point of the high target is
that the multi-horizon momentum gate, not the vol target, is the crash control;
the vol target only cuts the tail where 3x daily-reset decay is extreme.

### Rebalance and execution

- Weekly: last session of each ISO week. The first panel session (2016-01-04)
  inherits the 2015-12-31 target; the first in-window rebalance is 2016-01-08.
- Decision at 15:59 close; fill at the next session's 09:30 open.
- 2% band; long-only; weights >= 0, sum <= 1.
- Costs 1 bp headline, 5 bp and 10 bp sensitivity.
- Equity marked on every 1-minute bar.
- Monthly rebalance is tested in the grid as a negative control.

## 11.3 Parameter grid (8 combinations, fixed before the final run)

| ID | Vol target | Relative L | Rebalance | Role |
|---|---:|---:|---|---|
| **A** | **100%** | **126** | **weekly** | **primary, a priori** |
| B | 90% | 126 | weekly | target neighbour |
| C | 80% | 126 | weekly | target neighbour |
| D | 100% | 252 | weekly | relative-horizon neighbour |
| E | 90% | 252 | weekly | |
| F | 80% | 252 | weekly | |
| G | 90% | 126 | monthly | slow-rebalance control |
| H | 100% | 126 | monthly | slow-rebalance control |

**Why A is primary.** 100% is the least interventionist vol target: the
multi-horizon gate already cuts exposure, so the vol target should only act in
extreme volatility. 126 sessions (six months) is the standard relative-
leadership horizon and the midpoint of the medium absolute horizons. Weekly is
the fastest rebalance the mandate allows and is necessary for the fast short
gate to matter; monthly is the control.

**Selection rule.** The verdict is A. A pass requires dev CAGR > 36.72% and
max DD < 60% at 1 bp, with at least two other weekly grid points (B–F) also
passing. If A passes but the weekly plateau does not, the result is labelled a
knife-edge and not a pass.

## 11.4 Why this should beat TQQQ

1. **Faster crash exit without a single-horizon whipsaw.** The 21/42 OR turns
   off early in 2018-Q4, 2020 and 2022; the 84/105/126 majority keeps it off
   until the medium trend actually recovers. This addresses the exact failure
   of Revision 1.
2. **Faster recovery re-entry.** In 2019 and 2023 the short gate turns on in
   January/February, while the medium majority confirms in February/March.
   Revision 1 waited until April 2019 and March 2023.
3. **Relative de-lever, not relative exit.** When QQQ stops leading SPY, the
   book drops from 3x TQQQ to 1x QQQ; it does not go to cash while the absolute
   trend is still positive. The 126/252 relative horizon is slow enough not to
   de-lever in the first weeks of a high-beta recovery.
4. **High vol target keeps the bull-market compounding.** With a 100% target,
   the strategy is close to fully invested in calm uptrends; the momentum gate,
   not a low vol target, does the risk control.
5. **Geometric asymmetry.** Avoiding the 2020 and 2022 drawdowns is worth more
   than missing part of the rebounds. The target is a higher CAGR with a much
   lower drawdown, not a higher average return.

## 11.5 Where it should fail

- **Short-horizon sensitivity.** The 21/42 OR is an ensemble, but the
  short-horizon family is the weakest part of the design. A 21-day-only or
  63-day-only signal does not work; the 42-day leg is doing real work. If the
  result disappears when the short gate is perturbed, it is not robust.
- **Weekly dependence.** Monthly rebalancing is too slow for the short gate and
  is expected to fail. A strategy that only works weekly is more sensitive to
  execution.
- **Whipsaw.** The short OR can flip in choppy markets (2016, 2021), raising
  turnover and occasionally missing a sharp rebound.
- **Relative drag.** The QQQ/SPY gate may still cost return; if it does, the
  report says so and shows the absolute-only comparison.
- **Not a diversifier.** The strategy is still a TQQQ-beta strategy with a
  timing overlay. Correlation to TQQQ is expected to be 0.7–0.85.
- **Exploratory selection.** Revision 2 was designed after Revision 1 failed.
  The development result is not a clean out-of-sample test.

## 11.6 Falsifiers (fixed before the final run)

1. Primary A dev CAGR <= 36.72% or max DD >= 60% at 1 bp.
2. Fewer than two other weekly grid points (B–F) pass; the result is a
   knife-edge.
3. Placebo median CAGR >= A's CAGR, or more than 5% of circular shifts beat A.
4. Cut test changes any weight before the cut (max abs diff > 1e-12).
5. One year accounts for more than half of the excess CAGR over TQQQ.
6. A's 10 bp CAGR <= 36.72%.
7. TQQQ average target weight > 90% of sessions, or daily correlation to TQQQ
   > 0.95 with no DD improvement.
8. Perturbing the short gate to 21-only or 63-only removes the pass; if so,
   the pass is labelled a short-horizon artifact.

## 11.7 Expected effect

| Variant | Expected CAGR | Expected max DD | Expected Sharpe |
|---|---:|---:|---:|
| A: 100% / rel126 / weekly | 37-41% | 40-47% | 1.0-1.1 |
| 90% / rel126 | 36-40% | 40-47% | 1.0-1.1 |
| 80% / rel126 | 35-39% | 40-47% | 1.0-1.1 |
| monthly | 20-28% | 50-60% | 0.6-0.8 |

Expected TQQQ session share 55-70%; average risky exposure 75-90%; correlation
to TQQQ 0.70-0.85; turnover 50-80x per year. The high turnover is acceptable
because the 10 bp result is still expected to clear 36.72%; if it does not, the
edge is too cost-sensitive.

## 11.8 Honest prior

The most likely failure is that the 21/42 OR is a development-window artifact.
The most likely source of genuine excess return is the 2020 and 2022
drawdown avoidance plus the 2019/2023 re-entry. If the yearly table shows that
2023 alone accounts for the excess, or if the placebo distribution overlaps
the strategy, the verdict will be negative regardless of the headline CAGR.
