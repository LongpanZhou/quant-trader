# Revisit: ML crash-day classifier → leverage-decay timing

**Slug:** `ml-crash-overlay-winner`
**Original:** `research/agents2/ml-crash-overlay-winner`
**Status:** hypothesis / spec — **backtests paused (2026-11-26)**. No `result.json` has been generated and no development or holdout performance has been inspected.

---

## 1. What was actually new in the original

The original added a walk-forward logistic classifier of a **20-session TQQQ crash
(< −15%)** on top of the shared 165-day QQQ SMA + armed 4% stop winner. The
genuinely new part was the **walk-forward ML crash-day classifier**, not the base.
The old overlay's headline (10y 72.24% / 41.50%, 5y 53.10% / 31.67% at 1 bp) came
from a classifier that flagged about 11% of held days; its OOS AUC was unstable
(0.225–0.757, median ≈ 0.50), the 10y edge was heavily 2020-dependent (ex-2020
CAGR 50.0%), and the 5y edge was entirely the 2026 selloff. As an overlay it was
already fragile. Simply deleting the 165-day base would leave a low-exposure
version of the same trade, not a new strategy.

## 2. The standalone idea: leverage-decay timing

TQQQ's 3× daily reset makes its return path-dependent. To second order,

```
log(TQQQ_t / TQQQ_0) ≈ 3 · log(QQQ_t / QQQ_0) − 3 · Σ r²
```

so the 3× fund loses value when the path is choppy and gains when it is smooth
(Avellaneda & Zhang 2010; Cheng & Madhavan 2009). The decay is not a fixed fee:
it is large in high-volatility, mean-reverting regimes and can be small or even
negative (favorable compounding) in calm, trending regimes.

**Hypothesis:** a walk-forward ML classifier can predict, from causal 1-minute
features, when the next five sessions will have unusually large TQQQ-vs-3×QQQ
decay. The strategy uses that prediction to choose the *right risk asset*:

| Predicted decay risk | Position | Rationale |
|---|---|---|
| lowest 15% | **TQQQ 100%** | leverage is favorable; smooth path |
| middle 55% | **QQQ 100%** | no decay; keep equity beta |
| highest 30% | **BIL 100%** | decay and crash risk are high; de-risk |

This is a complete, long-only, three-state rotation. The return driver is the
**timing of leverage** (TQQQ only when its reset is favorable), not crash
avoidance on a TQQQ base. It is not a renamed 165-day filter: the signal is a
forward-looking model of the *relative* TQQQ/QQQ return, and the default asset is
QQQ, not TQQQ.

## 3. Universe and data

- **Universe:** QQQ, TQQQ, BIL.
- **Data:** local adjusted 1-minute regular-session bars in `data/intraday-hf/`,
  500 calendar days of warm-up, via `research/bt.py`.
- **Why not a wider universe:** historical 1-minute SPY is not local (only a
  2026 dukascopy cache exists), and sector/bond/gold/vol products would require
  new data with a `SOURCE.md`. The local data supports QQQ/TQQQ/BIL cleanly, and
  the leverage-decay thesis is specific to a 3× Nasdaq-100 ETF. SPY is left as a
  `null` benchmark until the data is available; QQQ is the equity benchmark.
- **No 100–250 day moving-average gate** anywhere in the strategy. All features
  use windows of 120 days or less, and the only long lookback is a 120-day
  *volatility percentile*, not a price MA.

## 4. Signal

### 4.1 Features (37, all causal through the decision close)

Groups:

- **Returns / short trend:** QQQ 1, 2, 5, 10, 20, 60-session log returns.
- **Realized volatility:** 1-minute realized vol for the session, 5/20/60-session
  means, 5/60 vol ratio, 120-session percentile of 5-session vol.
- **Tail shape:** 1-minute skew, 20-session mean skew, downside vol, 20-session
  mean downside vol.
- **Intraday structure:** close vs session VWAP, close vs session high, first-30
  and last-30 minute returns, close location in the day's range, overnight gap,
  20-session mean gap, intraday return, 20-session up-day fraction.
- **Drawdown / stretch:** 20- and 60-session drawdown, distance from the 20-day
  SMA, RSI(14).
- **Leverage / carry / calendar:** TQQQ-vs-3×QQQ 5- and 20-session decay, BIL
  5-session return, day-of-week, day range and 20-session mean range, volume
  ratio and 20-session volume z-score.

The full ordered list is in `strategy.py:FEATURES`.

### 4.2 Label

```
decay5[t] = log(TQQQ[t+5]/TQQQ[t]) − 3 · log(QQQ[t+5]/QQQ[t])
```

A **high-decay event** is `decay5` below the 25th percentile of the *training
window* (the quantile is recomputed inside each walk-forward fold; the test-year
labels are never used to set the threshold). The model predicts the probability
of that event over the next five sessions.

The label is deliberately **relative**: it asks when TQQQ will lag its 3× beta,
not when the absolute market will crash. That is the return driver of the
TQQQ/QQQ choice.

### 4.3 Model and walk-forward protocol

- L2 logistic regression, λ = 10, 750-session rolling training window,
  retrained once per calendar year (2016 … 2023 in the development run).
- **Purge:** the last `horizon + 1 = 6` training rows are dropped so no training
  label overlaps the test year.
- Features with less than 50% finite coverage in the training window are dropped
  for that fold; remaining NaNs are median-imputed, then standardised and
  winsorised at ±6 sd using training-window statistics only.
- The probability is converted to a trailing 252-session percentile rank
  (`min_periods=60`). The rank is the only input to the position rule.
- For 2016 the model necessarily trains on the 2015 warm-up only; that fold is
  reported separately and is not allowed to carry the result.

## 5. Position, holding period, sizing and risk

At the close of session `d`, with the rank from data through `d`:

1. `rank < 0.15` → target **TQQQ 100%**.
2. `0.15 ≤ rank < 0.70` → target **QQQ 100%**.
3. `rank ≥ 0.70` → target **BIL 100%**.

Execution and risk rules:

- Weights are set at the close and fill at the next bar's open. 2% no-trade band.
- **Minimum hold: 5 sessions.** A state is not changed for at least five sessions
  after entry, except that a crossing into the high-risk BIL state exits
  immediately (crash exit). Re-entry waits for the minimum hold.
- One asset at a time, 100% of equity, no leverage, no shorts. BIL earns its
  carry. There is no stop-loss overlay; the classifier is the risk control.
- The minimum hold is a turnover/robustness rule, not a return forecast: a
  5-session label and daily rebalancing would otherwise create overlapping
  decisions and unnecessary fills.

## 6. Expected correlation vs the old base

**Expected: 0.50–0.65, centred around 0.58; hard fail if ≥ 0.60 on the
development period.**

Reasoning: the old base is a slow binary 3×/0 switch: TQQQ on roughly 80% of
sessions, BIL on the rest. The new strategy is a faster three-state 3×/1×/0
switch: TQQQ on roughly 15% of sessions, QQQ on roughly 55%, BIL on roughly 30%.
What matters for correlation is not the average beta but *when* the beta changes.
The BIL state is triggered by high decay/volatility, which often happens during
fast bull-market corrections while the 165-day gate is still long; those are the
days that diversify the return stream. The TQQQ state is a selective subset of
the base's long days, and the QQQ state has one-third of TQQQ's beta, so the
overlap is not a clone of the base. The estimate is deliberately a range: the
measured value could sit near 0.65 if the BIL state coincides with the base's own
BIL periods (bear markets) rather than with base-long corrections. If the measured
correlation is ≥ 0.60, the pre-registered fallback is to lower `q_bil` (more BIL
days) and/or the TQQQ share; if that still fails, the idea is retired rather than
forced.

## 7. Falsifiers (pre-registered, before any test)

The idea is falsified if any of the following holds on the development window
(2016-01-04 → 2023-12-29):

1. **No discrimination:** OOS AUC of the decay classifier ≤ 0.55.
2. **No standalone return:** dev Sharpe < 0.5, or max drawdown > 25%, or CAGR
   below BIL at 1 bp.
3. **Still the old base:** daily-return correlation with the 165-day baseline
   ≥ 0.60.
4. **No decay separation:** realized `decay5` in the TQQQ state is not lower
   (more favorable) than in the QQQ state, or the difference is not significant
   in a block bootstrap.
5. **Single-episode dependence:** ex-2020 or ex-2022 Sharpe < 0.3.
6. **Costs kill it:** at 10 bp the strategy loses to QQQ buy-and-hold on Sharpe
   or drawdown.
7. **Placebo:** random states with the same frequencies (300 draws) match or beat
   the strategy's Sharpe.
8. **QQQ dominance:** QQQ buy-and-hold beats the strategy on both Sharpe and
   drawdown, i.e. the ML adds nothing over simply holding QQQ.

If (1), (3), or (8) fails, the idea is retired rather than re-parameterised.

## 8. Evaluation plan (when the lead authorises the test)

- **Development only:** 2016-01-04 → 2023-12-29. Do not inspect 2024–2026.
- **Marks:** 1-minute marks via `research/minute_marks.py:to_minutes`; next-open
  fills; 2% band; 1 bp headline, 5 bp and 10 bp reported.
- **Benchmarks:** TQQQ, QQQ, BIL, the 165-day baseline (correlation only), and
  the original overlay's published 10y/5y numbers (context only).
- **Overfitting controls:**
  - ±1-step neighbourhood: `q_tqqq ∈ {0.10, 0.15, 0.20}`,
    `q_bil ∈ {0.65, 0.70, 0.75}`, `min_hold ∈ {3, 5, 10}`,
    `label_q ∈ {0.20, 0.25, 0.30}`, rank window ∈ {120, 252}. Report the whole
    plateau, not the maximum.
  - Sub-periods 2016–19, 2020–21, 2022–23.
  - 300-draw random-state placebo at the same state frequencies.
  - Event counts: number of TQQQ-state, QQQ-state and BIL-state days; bootstrap
    p-value for the state-conditional decay difference.
- **Correlations:** vs the 165-day baseline, TQQQ, QQQ, and (when available) the
  other rebuilds in `research/strategies/`. Target: < 0.60 vs the base, < 0.70 vs
  every other rebuild.

## 9. Provenance

See `provenance.md` for the full idea → source table. In brief:

- The decay formula and path dependence come from Avellaneda & Zhang (2010) and
  Cheng & Madhavan (2009).
- The walk-forward/purge protocol comes from Arnott, Harvey & Markowitz (2019)
  and López de Prado's work on overlapping labels.
- The placebo/overfitting discipline comes from Bailey et al.
- The classifier is my own extension; no source specifies this exact three-state
  TQQQ/QQQ/BIL rule. That rule is marked **Own test / no external source**.
- The old 165-day base is used **only** as the correlation benchmark, never as a
  gate or a weight source.

## 10. Results

**TBD — backtests paused.** No development or holdout result has been generated.
The report will be filled in only after the lead authorises the test; the frozen
strategy will then be run once on the holdout by the lead, not by this agent.

## 11. Risks and limitations

- **The classifier may have no skill.** The original 20-session absolute crash
  model had an unstable OOS AUC around 0.50. If the decay label behaves the same
  way, the three-state mapping will not separate favorable from unfavorable
  leverage and the idea should be retired.
- **The QQQ default keeps equity beta.** The strategy is not market-neutral; a
  QQQ drawdown still hurts. The BIL state is the only crash protection.
- **Correlation may still be too high.** QQQ and TQQQ share the same underlying;
  if the TQQQ state is not selective enough, the daily-return correlation with
  the old base can exceed 0.60. The fallback is a lower TQQQ share or retirement.
- **Overlapping labels.** Five-session labels overlap; the 6-session purge and
  the effective sample size are handled explicitly, but the model still has
  fewer independent observations than rows.
- **Costs.** State changes are full switches. The 5-session minimum hold reduces
  turnover, but 10 bp may erase the edge.
- **Leverage-decay is partly mechanical.** A simple realized-vol threshold may
  capture much of it. The report will compare the ML rule with a vol-only rule;
  if the ML does not add value, the simpler rule wins.
- **No shorting.** The strategy is long-only, so it cannot profit directly from
  a crash; it can only move to BIL. A long/short version was rejected at design
  time because `bt.py` is long-only and a private short simulator is not allowed.

## 12. Original vs rebuilt (context, not a result)

| | Original overlay | Rebuilt standalone |
|---|---|---|
| Base | 165-day QQQ SMA + armed 4% stop | None; the ML state is the base |
| Signal | P(20-session TQQQ < −15%) | P(next-5-session TQQQ-vs-3×QQQ decay in worst quartile) |
| Position | TQQQ by default, BIL on top decile | TQQQ / QQQ / BIL by decay rank |
| Holding | Daily, base-driven | Minimum 5 sessions, crash exit immediate |
| Universe | QQQ/TQQQ/BIL | QQQ/TQQQ/BIL |
| Reported 10y / 5y (1 bp) | 72.24% / 41.50%; 53.10% / 31.67% | TBD (dev only, paused) |
| Correlation vs 165-day base | high (overlay on the base) | target < 0.60 |
