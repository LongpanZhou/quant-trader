# Hypothesis and pre-registration — `tqqq-vol-target-aggressive`

**Status:** frozen for the development evaluation. This file is written **before**
the final grid run; every number in `report.md` comes from the exact grid and
rules below.
**Development window:** 2016-01-04 → 2023-12-29 only. The 2024-01-02 →
2026-10-23 holdout is not loaded, inspected or used for selection.
**Universe:** TQQQ (long), BIL (cash). QQQ is used only for benchmark context,
never as a signal.
**Execution:** daily target set at session close `t`, filled at the open of
`t+1`; 2% band; 1 bp headline, 5 bp and 10 bp sensitivity. Long-only,
weights ≥ 0, sum ≤ 1. Headline marks are 1-minute; daily marks are a
cross-check.

## 1. Mechanism

TQQQ is a 3× daily-reset fund. Its compound return is taxed by realised
variance and its drawdowns are amplified by the daily reset. The mandate is the
**aggressive end** of the always-long volatility-target family: hold TQQQ at
all times, sized inversely to a causal realised-vol estimate with a high
nominal target (0.8–1.0 annualised), and add only a **fast crash cut** — no slow
trend gate, no moving-average regime, no discretionary flat.

The economic bet is asymmetric:

1. In calm and normal-vol tapes, TQQQ's drift is large relative to its variance
   and the strategy should be close to fully invested. A high target preserves
   that participation.
2. In acute high-vol states the 3× reset drag and gap risk are largest; scaling
   down is cheap insurance.
3. A fast drawdown brake is needed because TQQQ's worst damage (2020Q1, 2022)
   is a *path* of accelerating losses, not a single vol spike. The brake cuts
   when price is meaningfully below its recent high and restores when the
   recent high is recovered.

The honest prior is that the nominal target is **not** leverage: weights are
capped at 1. The average realised exposure will be below 1 and may end up close
to a much lower vol target. The report therefore separates (a) the value of vol
timing, (b) the value of the crash brake, and (c) the value of the average
exposure itself (matched constant and 80–100% constant controls).

## 2. Exact rules

Let `C_t` be TQQQ's adjusted daily close, `r_t = ln(C_t/C_{t-1})`.

**Volatility estimators** (computed through the close of session `t`, strictly
causal):

- `RV_N`: annualised sample standard deviation (`ddof=1`) of the last `N` daily
  log returns, `sqrt(252)·std(r_{t-N+1..t})`. Primary.
- `PARK_N`: Parkinson range estimator over the last `N` sessions,
  `sqrt(252/(4 ln 2)·mean(ln(H_i/L_i)²))`, adjusted daily high/low. Rival.
- `EWMA_λ`: RiskMetrics variance recursion with `λ = 0.94`, annualised. Rival.

**Base position:**

```
base_t = clip(target_vol / sigma_t, 0, 1)
```

**Fast crash brake:**

```
hi15_t  = max(C_{t-14..t})
dd15_t  = 1 - C_t / hi15_t
brake_t = clip(1 - (dd15_t - 0.06) / (0.12 - 0.06), 0.25, 1)
```

So the brake is full at a drawdown of 6% or less, declines linearly to a floor
of 0.25 at a 12% drawdown, and stays at the floor beyond. It uses only the
completed daily bar and is applied from the next session's open.

**Target:**

```
raw_t = base_t · brake_t
w_t   = EMA_3(raw_t)          # span 3, adjust=False, causal
b_t   = 1 - w_t               # BIL
```

The 3-session EMA is a turnover control, not a signal: it reduces traded
notional at the 2% band. It is applied to the final target, so the decay is
causal.

If `sigma_t` is missing or non-positive, `w_t = 0`; with the 2015 prehistory this
can only happen in the first few sessions of 2016, not in the evaluation window.
There is no trend filter, no slow moving average, no volatility-of-volatility
term, no stop-loss and no shorting.

## 3. Pre-registered grid (8 cells)

The brake is fixed at the values above for every cell. The grid spans the
mandated target range and two rival estimator families. **Primary:
`rv20_t080`** — the lowest target in the mandated 0.8–1.0 range, chosen a priori
as the most conservative point and the one that prioritises the DD < 60%
constraint. It is not chosen from the results. The report discloses that it is
the best CAGR cell of the pre-registered grid; the out-of-grid 0.70 and 0.75
targets are marginally better on both axes and are disclosed but not promoted,
to avoid selecting the best out-of-grid cell on the evaluation window.

| id | estimator | lookback | target vol | brake |
|---|---|---:|---:|---|
| **`rv20_t080` (primary)** | **RV** | **20** | **0.80** | **on** |
| `rv20_t090` | RV | 20 | 0.90 | on |
| `rv20_t100` | RV | 20 | 1.00 | on |
| `rv10_t080` | RV | 10 | 0.80 | on |
| `rv60_t080` | RV | 60 | 0.80 | on |
| `park20_t080` | PARK | 20 | 0.80 | on |
| `ewma_t080` | EWMA 0.94 | 20 | 0.80 | on |
| `rv20_t080_nocut` | RV | 20 | 0.80 | **off** |

**Plateau rule:** the primary is promoted only if (a) it passes the program bar
(CAGR > 36.72%, DD < 82.29%), (b) it meets the mandate's DD < 60% target, (c) at
least 5 of the 7 cut cells pass the program bar, and (d) the 0.9 and 1.0 targets
are not catastrophic (both still pass the program bar, or are within 1 pp CAGR
of it). If only the lowest-exposure cell passes, that is reported as a
near-control failure, not a plateau.

## 4. Out-of-grid diagnostics (not used for selection)

- **No-cut control:** the same target and estimator without the brake. This is
  the cleanest test of whether the crash cut is the real edge.
- **Constant TQQQ blends:** 60, 70, 80, 85, 90, 95 and 100% TQQQ, remainder BIL,
  rebalanced daily under the same 2% band. The 80–100% band is the direct
  "is this just leverage?" control.
- **Matched constant:** a constant TQQQ weight equal to the primary's realised
  average weight. Same average exposure, no timing.
- **Brake neighbours:** high lookback 10/15/20/30; start 0.04/0.05/0.06/0.08;
  end 0.12/0.15/0.20/0.25; floor 0.00/0.10/0.20/0.25/0.30/0.40. Reported as a
  plateau, not a search for the best cell.
- **Cut-shape rivals:** a binary cut at a 12% drawdown (floor 0.25) and a
  volatility-acceleration cut (`RV5 > 1.5·RV20` and `RV5 > 0.70`, weight 0.30).
- **Estimator neighbours:** RV5, RV120, PARK10, PARK60, RV10+RV60 blend, and
  EWMA with a longer span.
- **Smoothing neighbours:** raw (no EMA), EMA span 2 and 5.
- **Lag placebo:** the primary weight path delayed by 5, 20 and 60 sessions.
- **Circular-shift placebo:** the primary daily weight path shifted by a random
  offset (uniform in `[60, n−60]`, 500 draws), preserving the exact weight
  distribution, turnover and autocorrelation while destroying alignment with
  returns.

## 5. Cut tests

- **Causal truncation:** rebuild the weights on panels truncated at 2018-12-31,
  2020-03-12 11:07, 2021-12-31 and 2022-09-13; every pre-cut weight must be
  identical to the full-panel weight.
- **Performance cuts:** drop the best calendar year, drop 2020, drop 2022, drop
  the best 20 sessions, and start in 2017 and 2018.
- **Subperiods:** 2016–2019, 2020–2021, 2022–2023, plus yearly returns.
- **Episodes:** 2018Q4, the COVID crash and recovery, the 2022 bear and the 2023
  recovery.

## 6. Pass criterion and interpretation

The formal bar is **dev CAGR > 36.72% and max DD < 82.29%** on 1-minute marks at
1 bp. The mandate's tighter target is **DD < 60%**. A pass on CAGR with DD
between 60% and 82% is reported as a partial pass, not a clean one.

The report must answer three questions explicitly:

1. **Is the target just leverage?** No weight exceeds 1; the 80–100% constant
   controls and the matched constant answer whether the average exposure alone
   explains the result.
2. **Is the crash cut the real edge?** The no-cut, binary-cut and
   vol-acceleration-cut rows separate the CAGR effect from the DD effect.
3. **Is the result a plateau or a single cell?** The 8-cell grid plus the brake
   neighbours and the two estimator families answer this.

## 7. Data and causality notes

- The 1-minute archive starts 2016-01-04. The daily yahoo archive starts
  2015-01-02 and is used only to warm the volatility and drawdown estimators
  before the first 1-minute session; every decision in the evaluation window
  uses data through that session's close only.
- Daily OHLC are adjusted by `adjclose/close` (the same factor convention as
  `bt.load_1m`). Execution and marks use the 1-minute panel.
- `build_weights` loads the daily signal only through the **session before the
  panel's last session**, and maps session `j`'s target from the signal at
  `j−1` to session `j`'s bars. No same-day close enters that session's weight.
  The last bar of session `j−1` carries session `j`'s target so the 2% band and
  the next-open fill happen at the session boundary.
- No full-sample statistic enters the weight: every estimator is a trailing
  window or a recursion seeded only with past data.
