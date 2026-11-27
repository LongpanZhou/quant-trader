# Drawdown-recovery TQQQ v2: a two-speed circuit breaker

**Status:** pre-registered before the reported run. Development window only.
**Author:** research subagent, 2026-11-27.
**Directory:** `research/new/drawdown-recovery-v2/`

---

## 0. Scope

| Item | Value |
|---|---|
| Development window | 2016-01-04 .. 2023-12-29 |
| Data | `data/intraday-hf/` adjusted 1-minute QQQ, TQQQ, BIL |
| Fills | next-bar open, `research/bt.py`, 2% band |
| Costs | 1 bp headline; 5 bp and 10 bp reported |
| Constraints | long-only, weights >= 0, row sum <= 1, idle cash at 0% |
| Holdout | never used; the panel, signals and statistics end 2023-12-29 |
| Bar | TQQQ dev 36.72% CAGR / 82.29% max DD / 0.82 Sharpe |

Indicator warmup uses QQQ **daily** closes from 2015-01-02 to 2015-12-31
only.  The 1-minute archive starts 2016-01-04, so no 2024+ bar enters the
panel or any signal.

## 1. Hypothesis

TQQQ's 82% dev drawdown is not a smooth decay: it is a handful of fast
drawdowns (2018Q4, 2020Q1, 2022) followed by violent recoveries.  A slow
moving-average gate (the old 165-day rule) reacts late and gives back much of
the recovery.  A **fast drawdown circuit breaker with a recovery re-entry**
should keep most of TQQQ's drift, step aside during the acute phase of a
crash, and re-enter when the panic has demonstrably ended.

The key design question is the re-entry speed.  A single "buy after a 10-day
high" rule re-enters every bear-market rally; a single "wait for volatility to
contract" rule misses the first leg of a V recovery (for example the
2022-12 -> 2023-04 +50% TQQQ move).  The drawdown **depth** tells the two
cases apart:

- a shallow pullback (down 8% from the 20-day high, but not 12% from the
  60-day high) is an ordinary bull-market correction; it recovers quickly, so
  a 10-day high is enough;
- a deep drawdown (12% or more from the 60-day high) is a bear/crash regime;
  a 10-day high is usually a bear rally, so wait for realized volatility to
  contract to 0.60x its 60-day level before buying.

This is a high-exposure recovery bet: the default position is 100% TQQQ, and
only the acute drawdown phase is spent in cash.

## 2. Exact rules (one decision per session, at the close)

Let `q` be the QQQ session close, `dd20 = q / max(q[-19..0]) - 1`,
`dd60 = q / max(q[-59..0]) - 1`, `hi10 = max(q[-10..-1])`.

`v10` and `v60` are the annualised standard deviations of QQQ daily log
returns over the last 10 and 60 **completed** sessions (lagged one session),
and `vr = v10 / v60`.  All indicators are trailing and causal.

State: `LONG` (default) or `CASH`; flags `deep` and `recovery`.

**LONG -> CASH (new drawdown).**
- Normal position: exit if `dd20 <= -8%` **or** `dd60 <= -12%`.
- Recovery position (entered from a deep cash episode): exit if
  `dd20 <= -8%` **or** `q / (highest close since entry) - 1 <= -8%`.
  The stale 60-day drawdown is ignored until `dd60 > -12%`; otherwise the
  position would be stopped out the day after entry for a drawdown that
  predates it.
- On exit set `deep = (dd60 <= -12%)`.

**CASH -> LONG (recovery).**  While in cash, `deep` is sticky: it becomes
true as soon as `dd60 <= -12%` at any close.
- if `deep`: re-enter when `vr < 0.60` (volatility contraction);
- if not `deep`: re-enter when `vr < 0.60` **or** `q > hi10`
  (10-session high).
- On entry set `peak = q`, `recovery = deep`, `deep = False`.

The 2% band and next-open fills are the harness defaults.  Idle weight is
cash at 0%.  The "10-session low" exit from the mandate was implemented and
tested; it is reported as a negative ablation (it exits every ordinary
pullback and cuts CAGR to about 31%).

## 3. Pre-registered grid (8 cells)

| # | dd20 | dd60 | vol ratio |
|---:|---:|---:|---:|
| 1 | 7% | 11% | 0.60 |
| 2 | **8%** | **12%** | **0.60** |
| 3 | 9% | 13% | 0.60 |
| 4 | 10% | 15% | 0.60 |
| 5 | 8% | 12% | 0.55 |
| 6 | 8% | 12% | 0.65 |
| 7 | 7% | 11% | 0.65 |
| 8 | 9% | 13% | 0.55 |

The centre (cell 2) is the headline.  A pass is only credible if the
neighbours are also above the bar or at least close, and if the mechanism
survives the ablations below.

## 4. Planned robustness (not used to choose the centre)

- Neighbours: confirmation window 5/20, trail 6/10%, deep rule vol-or-hi,
  shallow rule hi-only, TQQQ-based signal instead of QQQ, start-in-cash.
- Ablations: vol-only re-entry, hi-only re-entry, 10-day-low exit,
  trailing-only exit, no deep/slow branch.
- Placebo: block permutation of the daily target series (preserves the
  duration distribution) and a random circuit breaker with the same number
  of exits and the same cash-duration distribution.
- Cut tests: ex-2018, ex-2020, ex-2022, ex-2023; subperiods 2016-2019,
  2020-2021, 2022-2023.
- Causality: rebuild weights on data truncated at 2022-01-03 and compare
  with the full-sample weights on the overlap.

## 5. Falsification / honest risks

- **Small number of episodes.**  The dev window contains roughly 14 round
  trips and only three deep episodes (2018Q4, 2020Q1, 2022).  A pass is
  therefore a statement about a few macro events, not a large sample.
- **2022 dependence.**  A circuit breaker can beat TQQQ's CAGR mainly by
  avoiding 2022's -80%.  If the ex-2022 cut is below TQQQ, the headline is
  crash avoidance, not broad alpha.  This will be reported explicitly.
- **Bull-market whipsaw.**  In 2019 the 8% trigger exited just before a
  +25% TQQQ rally and re-entered late; the strategy lagged TQQQ badly that
  year.  A holdout with only shallow pullbacks could do the same.
- **No shorting, no leverage beyond 100% TQQQ, no BIL yield.**  Cash earns
  0%, which is conservative relative to a T-bill sleeve.
