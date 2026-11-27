# Hypothesis and pre-registration - `ema-ribbon-trend`

**Status:** frozen before the final 1-minute development run.
**Development window:** 2016-01-04 -> 2023-12-29 only. The 2024-01-02 ->
2026-10-23 holdout is not loaded, inspected or used for selection.
**Universe:** QQQ (signal and middle-tier asset), TQQQ (leveraged long), BIL
(cash). Long-only, weights >= 0, sum <= 1.
**Execution:** weights set at the 15:59 close of a session fill at the next
session's open; 2% band; 1 bp headline, 5 bp and 10 bp sensitivity.

## 1. Mechanism

TQQQ's 82% development drawdown is a multi-month phenomenon: 2018Q4, 2020 and
2022. A trend state can own TQQQ through the up-legs and stand aside during
those bears. The problem with a single slow average is that it is a line test:
every close near the line flips the regime, so the strategy repeatedly sells
after a decline and re-buys after the rebound.

This strategy uses a **three-EMA ribbon on QQQ** (20/50/100 sessions) as a
confirmation ladder, a small **hysteresis buffer** on the fast cross, a
**QQQ middle tier** for bull-market pullbacks, and a **volatility target** on
the leveraged sleeve:

- **FULL (TQQQ).** Enter when the ribbon is stacked: EMA20 > EMA50 > EMA100.
  Leave only when EMA20 falls more than 0.5% below EMA50. The 100-day EMA
  gates entry but does not force a daily exit.
- **REPAIR (QQQ).** When not FULL but QQQ is still above its 100-day EMA,
  hold QQQ. This keeps a 1x position through an ordinary pullback instead of
  going to cash and having to re-enter TQQQ from zero.
- **OFF (BIL).** When not FULL and QQQ is below its 100-day EMA, hold BIL.
- **Volatility target.** TQQQ weight is `min(1, 0.85 / vol20)`, where `vol20`
  is annualised TQQQ daily-return volatility over the prior 20 sessions. The
  QQQ sleeve is `min(1, 0.85 / vol20_qqq)`, which is 1.0 in practice; it only
  de-risks in an extreme QQQ-vol spike.

The rhythm is deliberately slow: roughly one state change per year, ~150
fills over eight years, and no intraday stops or event brakes.

## 2. Exact rules

Let `Q_t` be QQQ's adjusted 15:59 1-minute close of session `t` (the price
known at the decision time). Let `F_t`, `M_t`, `S_t` be the 20-, 50- and
100-session EMAs of `Q_t`, computed recursively (`adjust=False`) through the
close of `t`. Let `H_t` be the TQQQ state:

```
H_0 = 0
if   H_{t-1} = 0 and F_t > M_t and M_t > S_t:   H_t = 1    # stacked entry
elif H_{t-1} = 1 and F_t < 0.995 * M_t:         H_t = 0    # buffered exit
else:                                           H_t = H_{t-1}
```

Let `R_t` be the QQQ repair state:

```
R_t = 1 if H_t = 0 and Q_t > S_t else 0
```

Let `sigma_t` be the annualised standard deviation of TQQQ daily log returns
over the last 20 sessions through `t`, and `sigmaQ_t` the same for QQQ. The
target weights for the next session's open are:

```
w_tqqq = H_t * min(1, 0.85 / sigma_t)
w_qqq  = R_t * min(1, 0.85 / sigmaQ_t)
w_bil  = 1 - w_tqqq - w_qqq
```

`H_t` and `R_t` are mutually exclusive, so the sum is at most 1 by
construction; a final normalisation is applied only as a guard.

Mapping to the 1-minute panel: every bar of session `t` except the last
carries the target known at the close of `t-1`; the 15:59 bar carries the
target computed at the close of `t`, which fills at the open of `t+1`. There
is no intraday override.

No 165-day (or any 100-250 day) simple moving average is used. The slow input
is the 100-day EMA, the top of the mandated 20/50/100 ribbon.

## 3. Why ribbon alignment avoids whipsaw better than a single slow average

1. **A single average is a line test; a ribbon is a conjunction.** With one
   average, one close below the line flips the whole regime. With the stack,
   a dip only moves the fastest line; the state cannot flip unless the 20/50
   relationship actually inverts. The 50/100 pair is a slower confirmation
   that the medium-term trend has rolled over, and the 100-day EMA is the
   regime anchor for the middle tier.
2. **The 0.5% exit buffer is a Schmitt trigger.** A shallow 20/50 cross does
   not trade. This matters exactly at the noisy tests of a trend: in May and
   June 2016 the 20/50 cross was smaller than 0.5%, so the no-buffer version
   exited and re-entered twice around the Brexit dip and lost 8% in a year in
   which TQQQ rose 19%. With the buffer the same year is +25%.
3. **The QQQ middle tier absorbs bull-market pullbacks.** When the stack
   breaks but price is above the 100-day EMA, the book holds QQQ rather than
   cash. That is a 1x participation in the rebound, and it avoids the
   "sell the low, rebuy the high" round trip at 3x.
4. **The measured whipsaw premium is large and broad.** On the daily
   development panel: 0% buffer = 37.98% CAGR / 43.80% DD / 205 fills; 0.5%
   buffer = 49.19% / 43.80% / 152 fills. Buffers from 0.3% to 2.0% all give
   44.9-51.0% CAGR, so the gain is a hysteresis effect, not a knife-edge fit.
   The mechanism is a reduction in false exits, and the fill count falls by a
   quarter.

## 4. Why it should beat buy-and-hold TQQQ

1. **Bear avoidance.** The 100-day anchor and the buffered 20/50 exit leave
   2018Q4, 2020 and 2022. Those three episodes contain almost all of TQQQ's
   82% drawdown.
2. **Retained upside.** The strategy is FULL on ~74% of sessions and holds
   QQQ on another ~10%, so it keeps most of the drift in 2017, 2019, 2020,
   2021 and 2023.
3. **Volatility drag.** The 0.85 target cuts TQQQ exposure when its realised
   volatility exceeds 85%, which is when the geometric drag and the left tail
   are largest. At a 0.70 target the drawdown falls to 42.4% but the CAGR is
   46.4%; the target is a risk dial, not a return source.
4. **No free lunch assumed.** Next-open fills, a 2% band and 1/5/10 bp costs
   are all charged. The strategy does not short and does not use leverage
   beyond TQQQ's embedded 3x.

## 5. Why it could fail

- **Lagging exit.** The ribbon is slow. The 43.8% max drawdown is the
  2020-02-19 -> 2020-03-09 crash: the state was still FULL when the sell-off
  began and only left on 2020-03-09. A faster exit would cut that drawdown
  but add whipsaw; the 0% buffer experiment shows the trade-off.
- **Whipsaw is reduced, not eliminated.** 2022 is still about -31% because
  the QQQ repair tier is long during bear-market rallies. 2019 is +39% versus
  TQQQ's +130%: the strategy gives up a lot of a V-shaped year.
- **Bull-market lag.** In 2023 TQQQ rose about 205% and the strategy made
  about 97%: the September-October 2023 pullback broke the stack and the
  November re-entry was late.
- **Concentration.** 2020 and 2023 carry a large share of the P&L. If the
  edge is only the two recovery years, the point estimate is not
  representative.
- **Parameter sensitivity.** The EMA lengths and the buffer are round-number
  centres of a plateau, but the 2016 and 2022 outcomes move by tens of points
  when the exit date moves by two days. That is path dependence, not a bug,
  and it is reported honestly.

## 6. Falsifiers (decided before the final run)

1. **Bar:** dev CAGR <= 36.72%, or dev max DD >= 82.29%. Design target:
   DD < 60%.
2. **Plateau:** fewer than 6 of the 8 pre-registered cells pass, or the base
   is an isolated peak rather than inside a neighbourhood.
3. **Costs:** 10 bp CAGR <= 36.72%.
4. **Placebo:** a 1/5/10/20-session lag of the daily target, or a
   shuffled-run placebo with the same exposure and persistence, matches the
   base's CAGR and Sharpe. The timing must add something.
5. **Concentration:** one calendar year contributes more than 80% of total
   log P&L, or both 2016-2019 and 2022-2023 are negative.
6. **Baseline:** the 165-day QQQ SMA baseline (benchmark only, never an
   input) beats the strategy on both CAGR and max DD over the same window.
7. **Core ablation:** removing the hysteresis buffer drops CAGR to <= 36.72%
   (the raw ribbon alone is not enough).
8. **Causality:** truncating the data at a cut date changes any weight before
   the cut.

## 7. Pre-registered parameter grid (8 cells)

The base is the centre of the design, not the best cell found by a search.
Each other cell moves one parameter by one step.

| Cell | Fast EMA | Mid EMA | Slow EMA | Exit buffer | Vol target |
|---|---:|---:|---:|---:|---:|
| **base** | 20 | 50 | 100 | 0.5% | 85% |
| `buf_0.3` | 20 | 50 | 100 | 0.3% | 85% |
| `buf_1.0` | 20 | 50 | 100 | 1.0% | 85% |
| `buf_2.0` | 20 | 50 | 100 | 2.0% | 85% |
| `entry_15` | 15 | 50 | 100 | 0.5% | 85% |
| `entry_25` | 25 | 50 | 100 | 0.5% | 85% |
| `tv_0.70` | 20 | 50 | 100 | 0.5% | 70% |
| `tv_1.00` | 20 | 50 | 100 | 0.5% | 100% |

The mid and slow EMAs are held at 50/100 in the grid. Their neighbourhood is
reported separately as a robustness check (15/40/80, 20/60/120, 25/60/120,
30/75/150). Every cell is a complete strategy with the same execution, costs
and universe.

## 8. Expected effect (design target, not a result)

- CAGR 45-50%, max DD 40-48%, Sharpe 1.0-1.15.
- TQQQ exposure around 74-78% of sessions (time), plus about 8-10% in QQQ;
  daily-return correlation to TQQQ around 0.65-0.75.
- The pass condition is strict: **CAGR > 36.72% and max DD < 82.29%**, with
  DD < 60% as the design target. A lower-CAGR but much better Sharpe/Calmar
  result would be reported as risk-adjusted, not as a pass.

## 9. How this differs from the existing strategies

- **`fast-trend-vol`:** a two-speed 20/50 EMA (fast entry, slow exit with a
  2.5% buffer), a -3.5% daily crash cooldown and a 2.5% QQQ intraday stop,
  TQQQ/BIL only. This strategy uses a three-EMA 20/50/100 stack, a 0.5%
  Schmitt trigger on the 20/50 cross, a QQQ middle tier, and no event brakes
  or intraday stops. The mechanism is ribbon hierarchy and hysteresis, not
  event-driven de-risking.
- **`daily-regime-minute-entry` (round-1 winner):** 165-day QQQ SMA plus an
  armed 4% TQQQ stop. This strategy uses no 165-day SMA and no stop.
- **`vol-scaled-crash-stop`:** always-long TQQQ with inverse-ATR size and an
  ATR barrier. This strategy is trend-gated and holds QQQ/BIL when the ribbon
  is not stacked.
- **`dynamic-leverage-throttle`:** episodic post-vol-shock recovery. This
  strategy owns calm uptrends and de-risks in shocks.
- **`dual-speed-regime`:** 60-minute intraday EMA, flat overnight. This is a
  daily strategy that holds overnight.
- **`donchian-breakout`:** 5-minute 20/55/390 alignment ladder with an ATR
  stop. This is a daily 20/50/100 EMA ribbon.
- **`ratio-froth` / `ratio-pairs`:** TQQQ/QQQ or QQQ/SPY ratio signals. This
  strategy uses no ratio.
- **`drawdown-regime`:** post-drawdown recovery windows. This uses a
  continuous ribbon state.

No existing strategy uses the 20/50/100 QQQ EMA stack + 0.5% 20/50
hysteresis + QQQ middle tier + 85% TQQQ volatility target combination.

## 10. Data discipline, causality and design provenance

- Signal prices are the adjusted 1-minute QQQ 15:59 session closes from the
  development panel. The local adjusted daily parquet is used only for the
  pre-2016 EMA/volatility warmup, filtered to dates before 2016-01-04.
- Execution and marks come from the adjusted 1-minute QQQ/TQQQ/BIL panel,
  truncated at 2023-12-29. No later bar enters any signal or weight.
- Every weight at session `t` uses only closes through 15:59 of `t`, and
  fills at the next session's open. The state machine is one-sided recursive
  and has no full-sample statistic.
- The causality check rebuilds the daily target with data truncated at
  2020-12-31 and confirms that every weight before the cut is unchanged.
- No full-sample normalisation and no holdout inspection.

**Design provenance (honest note).** The family (20/50/100 EMA stack +
volatility target) was explored on a daily development panel before this
pre-registration; the 0.5% buffer was chosen as a round-number centre after
seeing that 0.3-2.0% all sit on a plateau. The eight-cell grid above and the
1-minute evaluation were frozen before the final `strategy.py` run. The
report contains the full grid, the ablations, the placebos and the negative
evidence, not only the best cell.

**Post-freeze implementation note (2026-11-27).** The exploratory daily panel
used `bt.panel(..., "1D", warmup_days=800)`, but the 1-minute archive starts
on 2016-01-04, so that daily panel had **no pre-2016 warmup**: its EMAs and
state machine were cold-started at the first development bar. The final
1-minute run uses the adjusted daily parquet only for the pre-2016 warmup, so
its signal is warm and is the authoritative one. The frozen rules, the base
and the eight-cell grid were not changed. The indicative daily numbers in
sections 3 and 8 are therefore superseded by the 1-minute ablation and grid:
the no-hysteresis cell is 36.40% CAGR (not 37.98%) and the base is 46.77%
(not 49.19%), both at 1 bp on the warm 1-minute signal. The qualitative
conclusion is unchanged and in fact sharper: without hysteresis the raw
ribbon is just below the bar, and the 0.5% buffer is worth about 10 pp of
CAGR at the same 44.1% drawdown. On the warm signal the 2016 return is
+9.9% with the buffer versus -16.5% without it, and 2021 is +80.9% versus
+40.7% without it; the illustrative "+25%" 2016 figure in section 3 came
from the cold-start exploratory panel and should be read as that.
