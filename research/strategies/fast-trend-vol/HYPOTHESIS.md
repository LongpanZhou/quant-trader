# Hypothesis and pre-registration — `fast-trend-vol`

**Status:** frozen for the final 1-minute development evaluation.
**Development window:** 2016-01-04 → 2023-12-29 only. The 2024-01-02 →
2026-10-23 holdout is not loaded, inspected or used for selection.
**Universe:** QQQ (signal), TQQQ (long), BIL (cash). Long-only, weights ≥ 0,
sum ≤ 1.
**Execution:** weights set at the close of a 1-minute bar fill at the next
bar's open; 2% band; 1 bp headline, 5 bp and 10 bp sensitivity.

## 1. Mechanism

TQQQ's problem is not its average return, it is its path: 3× daily resetting
turns a multi-month QQQ bear market into an 80% drawdown, and high realised
volatility imposes a geometric drag. A fast trend state can own TQQQ while the
trend is up, stand aside during the multi-month bears, and re-enter quickly
after a V-shaped recovery. A volatility target reduces exposure exactly when
TQQQ's own realised volatility is high, which is when both the drag and the
left tail are largest.

The strategy is a **two-speed daily EMA trend** with a **volatility budget**
and two **crash brakes**:

- The **fast leg** (20-day EMA) decides when to enter. It is quick enough to
  participate in the recovery after a crash.
- The **slow leg** (50-day EMA) with a 2.5% exit buffer decides when to leave.
  The buffer is hysteresis: a normal pullback through the 50-day line does not
  force an exit, but a 2.5% break does.
- The **volatility target** sizes TQQQ at `min(1, 0.85 / vol20)`, where `vol20`
  is annualised TQQQ daily-return volatility over the prior 20 sessions.
- The **daily crash brake** exits after a QQQ daily log return ≤ −3.5% and
  stays out for the next 5 sessions.
- The **intraday crash brake** exits if QQQ's 1-minute close falls 2.5% below
  the session open while the book is long, and stays out for the rest of the
  session and the night. QQQ is the signal asset; a 2.5% QQQ fall is roughly a
  7.5% TQQQ fall. This is deliberately **not** the old 4% TQQQ stop.

## 2. Exact rules

Let `Q_t` be QQQ's adjusted daily close, taken as the **15:59 1-minute
close** of session `t` (the price actually known at the decision time), and
`E20_t` and `E50_t` its 20- and
50-session EMAs (all data through the close of session `t`). Let `S_t` be the
trend state:

```
S_t = 0 initially
if S_{t-1} = 0 and Q_t > E20_t:        S_t = 1     # fast entry
elif S_{t-1} = 1 and Q_t < 0.975*E50_t: S_t = 0     # slow exit with 2.5% buffer
else:                                   S_t = S_{t-1}
```

Let `r_t = ln(Q_t/Q_{t-1})`, `v_t` = annualised standard deviation of TQQQ
daily log returns over the last 20 sessions, and `C_t` the crash cooldown:

```
if r_t <= -0.035: cooldown = 5
C_t = 1 if cooldown > 0 else 0
cooldown = max(0, cooldown - 1)
```

Daily target:

```
w_t = S_t * (1 - C_t) * min(1, 0.85 / v_t)     # TQQQ weight
BIL weight = 1 - w_t
```

Intraday override, for each session `k` with open `O_k`:

```
if the book is long at the session open and QQQ 1m close < 0.975 * O_k:
    exit TQQQ at the next 1m open
    stay BIL for the rest of session k and the night
    re-enter at session k+1's open at w_k (the daily target known at k's close)
```

No 165-day (or any 100–250-day) moving average is used. The only slow filter
is the 50-day EMA, which is the upper end of the mandated 5–50 day range.

## 3. Why it should beat buy-and-hold TQQQ

1. **Crash avoidance.** TQQQ's 82% drawdown is made by 2018Q4, 2020 and 2022.
   The 50-day exit with a 2.5% buffer leaves those regimes; the 20-day entry
   re-enters after the recovery. The daily and intraday crash brakes cut the
   first days of a shock, when the compounding damage is largest.
2. **Volatility drag.** TQQQ's geometric return is hurt by high realised
   volatility. Sizing down when `vol20 > 85%` cuts exposure in exactly the
   high-variance periods that produce the deepest drawdowns.
3. **Retained upside.** The strategy carries a ~78% average TQQQ weight and is
   long on ~80% of sessions, so it keeps most of the drift. It gives up some
   melt-up beta (2019, 2021) in exchange for crash protection.
4. **No free lunch assumed.** The 2% band, next-open fills and 1/5/10 bp costs
   are all charged. The strategy does not use shorting or leverage beyond
   TQQQ's embedded 3×.

## 4. Why it could fail

- **Whipsaw.** 2018 and 2022 had repeated false recoveries. A fast entry can
  re-enter into a bear-market rally and take another loss. The 50-day buffer
  helps but does not eliminate this.
- **2020 V-recovery.** The 50-day exit is slow to re-enter after the crash.
  The 20-day entry helps, but if the recovery is faster than the 20-day EMA the
  strategy lags. The 5-session daily cooldown can also delay re-entry.
- **Intraday stop at the low.** A 2.5% QQQ intraday break can be a stop-run
  that reverses; the stop then sells near the low and misses the rebound.
- **Cost and turnover.** About 370 fills and 1,780× cumulative turnover. At
  10 bp the CAGR is lower; if the edge is cost-fragile it should be rejected.
- **Concentration.** 2020 and 2023 are strong recovery years. If the result is
  carried by one of them, the point estimate is not representative.

## 5. Falsifiers (decided before the final run)

1. **Bar:** dev CAGR ≤ 36.72%, or dev max DD ≥ 82.29%. The design target is
   DD < 60%; a DD between 60% and 82.29% is a technical pass but not a good
   risk result.
2. **Plateau:** fewer than 6 of the 8 pre-registered cells pass the bar, or the
   base cell is an isolated peak rather than inside a neighbourhood.
3. **Costs:** 10 bp CAGR ≤ 36.72%.
4. **Placebo:** a 5/10/20-session lag of the daily signal, or a shuffled-run
   placebo with the same exposure and persistence, matches the base's CAGR and
   Sharpe. The timing must add something.
5. **Concentration:** one calendar year contributes more than 80% of total
   P&L, or both 2016–2019 and 2022–2023 are negative.
6. **Baseline:** the 165-day QQQ SMA baseline (benchmark only, never an input)
   beats the strategy on both CAGR and max DD over the same window.
7. **Core ablation:** removing the intraday crash stop drops CAGR to ≤ 36.72%
   (i.e., the trend + vol + daily-crash core is not enough on its own).
8. **Causality:** truncating the data at a cut date changes any weight before
   the cut.

## 6. Pre-registered parameter grid (8 cells)

The base is the centre of the design, not the best cell found by a search.
Each other cell moves one parameter by one step.

| Cell | Entry EMA | Exit EMA | Exit buffer | Vol target | Intraday QQQ stop | Daily crash |
|---|---:|---:|---:|---:|---:|---|
| **base** | 20 | 50 | 2.5% | 85% | 2.5% | −3.5% / 5 sessions |
| `buf_2.0` | 20 | 50 | 2.0% | 85% | 2.5% | −3.5% / 5 |
| `buf_3.0` | 20 | 50 | 3.0% | 85% | 2.5% | −3.5% / 5 |
| `entry_15` | 15 | 50 | 2.5% | 85% | 2.5% | −3.5% / 5 |
| `entry_25` | 25 | 50 | 2.5% | 85% | 2.5% | −3.5% / 5 |
| `tv_0.70` | 20 | 50 | 2.5% | 70% | 2.5% | −3.5% / 5 |
| `istop_2.0` | 20 | 50 | 2.5% | 85% | 2.0% | −3.5% / 5 |
| `istop_3.0` | 20 | 50 | 2.5% | 85% | 3.0% | −3.5% / 5 |

The daily crash threshold is held at −3.5% / 5 sessions in the grid; its
neighbourhood is reported separately as a robustness check. The exit EMA is
held at 50; the entry EMA moves 15/20/25. Every cell is a complete strategy
with the same execution, costs and universe.

## 7. Expected effect (design target, not a result)

- CAGR in the 40–50% range, max DD in the 35–50% range, Sharpe around 1.0–1.2.
- TQQQ exposure around 75–80% of sessions, daily-return correlation to TQQQ
  around 0.6–0.7 (high, because it is still a TQQQ allocator, but lower than
  buy-and-hold's 1.0).
- The pass condition is strict: **CAGR > 36.72% and max DD < 82.29%**, with
  DD < 60% as the design target. A lower-CAGR but much better Sharpe/Calmar
  result would be reported as risk-adjusted, not as a pass.

## 8. How this differs from the existing strategies

- **`daily-regime-minute-entry` (round-1 winner):** 165-day QQQ SMA + an armed
  4% **TQQQ** stop. This strategy uses a 20/50-day EMA pair (no 165-day SMA),
  an 85% volatility target, a **QQQ** 2.5% intraday stop, and a daily −3.5%
  crash cooldown. It does not use the 4% TQQQ stop.
- **`vol-scaled-crash-stop`:** always-long TQQQ at inverse-ATR size with an
  ATR barrier; no trend gate. This strategy is trend-gated and sits in BIL when
  the trend is off.
- **`dynamic-leverage-throttle` (VSR):** episodic post-vol-shock recovery,
  deliberately in BIL during calm uptrends. This strategy is the opposite: it
  owns calm uptrends and de-risks in shocks.
- **`dual-speed-regime`:** 60-minute intraday EMA, flat overnight. This
  strategy makes daily decisions and holds overnight.
- **`donchian-breakout`:** 5-minute 20/55/390 alignment ladder, QQQ sleeve,
  ATR sizing. This strategy is daily 20/50 EMA, TQQQ/BIL, volatility-targeted.
- **`ratio-froth` / `ratio-pairs`:** TQQQ/QQQ ratio signals. This strategy
  uses no ratio.
- **`drawdown-regime`:** post-drawdown recovery windows. This strategy uses a
  continuous trend state, not a drawdown-triggered window.

No existing strategy uses the daily 20/50 EMA + 85% vol target + QQQ 2.5%
intraday stop + −3.5% daily crash cooldown combination.

## 9. Data discipline and causality

- Signal prices are the adjusted 1-minute QQQ/TQQQ **15:59 session closes**
  from the dev panel. The local adjusted daily parquet is used only for the
  pre-2016 EMA/volatility warmup, filtered to dates before 2016-01-04.
- Execution and marks come from the adjusted 1-minute QQQ/TQQQ/BIL panel,
  truncated at 2023-12-29.
- Every weight at session `t` uses only closes through 15:59 of `t`; the
  last-bar mapping fills the next session's open. The official 16:00 daily
  close is not used at 15:59, so there is no one-minute look-ahead.
- The causality check rebuilds the daily target with data truncated at
  2020-12-31 and confirms that every weight before the cut is unchanged.
- No full-sample normalisation, no future data in any rolling window, no
  holdout inspection.

## 10. Design provenance (honest note)

The strategy family was calibrated on the daily development panel before this
pre-registration. The final 8-cell grid above and the 1-minute evaluation were
frozen before the final `strategy.py` run. The report contains the full grid,
the ablation and placebo results, and the negative evidence, not only the best
cell. The design choices (20/50 EMA, 2.5% buffer, 85% vol target, 2.5% QQQ
stop, −3.5%/5 daily crash) are round-number centres of the explored
neighbourhood, not the single best values from a search.

**Implementation note (post-freeze causality fix, 2026-11-27).** The first
1-minute evaluation used the official 16:00 daily close at the 15:59 bar,
which is a one-minute look-ahead. The final run uses the 15:59 1-minute close.
The frozen grid and parameters were unchanged. The causal fix reduced the
1 bp CAGR from 51.70% to 51.51% and moved the max-drawdown episode from a
January–May 2018 whipsaw (41.47%) to an April–October 2019 whipsaw (42.54%).
The final `result.json` and `report.md` reflect the causal 15:59 run.
