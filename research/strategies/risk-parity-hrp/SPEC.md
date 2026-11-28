# Spec — Volatility-State Risk Parity (VSRP)

**Slug:** `risk-parity-hrp` · **Status:** design, not yet run (backtests paused).
**Dev:** 2016-01-04 → 2023-12-29. **Holdout:** 2024-01-02 → 2026-10-23 (lead only).

## 1. Universe and data

| Symbol | Role | Data |
|---|---|---|
| QQQ | equity factor, linear leg | `data/intraday-hf/QQQ-1m.parquet` (1m) |
| TQQQ | equity factor, 3x leg | `data/intraday-hf/TQQQ-1m.parquet` (1m) |
| BIL | cash / risk-off leg | `data/intraday-hf/BIL-1m.parquet` (1m) |
| SPY | benchmark only | `data/round3/yahoo/SPY-1d-yahoo.parquet` (daily) |

SPY is **not tradable** in this rebuild: `data/round3/yahoo/SOURCE.md` states
there is no SPY intraday history for 2016-01-04..2023-12-29 and restricts the
file to the buy-and-hold benchmark. No bond, gold or volatility-product history
exists locally, so the universe is QQQ/TQQQ/BIL. This is the binding data
constraint on the risk-parity idea.

## 2. Timing contract (no look-ahead)

- Session `k` = one regular-session day (09:30–15:59 ET); the last bar is that
  session's close, including half days (13:00).
- Every daily signal used for session `k` is computed from data **through the
  close of session k−1** (`lag(·)` in code). The only current-session input is
  none: the budget, composition and brake state are all decided at the prior
  close.
- Weights for session `k` are `weights[i] = tgt[k]` for every bar of session `k`,
  and the last bar of session `k−1` also carries `tgt[k]`. `bt.simulate` fills
  `weights[i]` at bar `i+1`'s open, so the sleeve is traded at the **09:30 open
  of session k** and held to the next open.
- The drawdown brake uses the strategy's own equity through the prior close,
  computed sequentially in `build_weights` with the same targets (a daily
  recursion, no future prices).

## 3. Daily signals

All vols are annualised standard deviations of daily close-to-close simple
returns, computed through session `k−1`:

```
sigma_Q(w), sigma_T(w)      w-day vol of QQQ / TQQQ, w in {20, 60, 120}
sleeve_vol = sqrt((wQ*sQ)^2 + (wT*sT)^2 + 2*wQ*wT*sQ*sT*rho)
rho = 0.9995               fixed; the 60-day estimate is 0.99986
```

### 3.1 Composition — equal risk contribution (ERC)

```
wT = clip( sigma_Q(60) / (sigma_Q(60) + sigma_T(60)), 0.10, 0.50 )
wQ = 1 - wT
```

At typical vols (22.6% QQQ, 67.4% TQQQ) this is **75% QQQ / 25% TQQQ**. The
clips stop the sleeve collapsing into one leg if the vol ratio moves.

### 3.2 Volatility state — term structure and persistence

```
slope   = log( sigma_Q(20) / sigma_Q(120) )
persist = clip( ( sigma_Q(120) / median_756( sigma_Q(120) ) - 1 ) / 0.50, 0, 1 )
tilt_raw = clip( slope / 0.35, -1, +1 ) * ( 1 - 0.70 * persist )
tilt     = mean( tilt_raw over the last 5 sessions )        # through k-1
```

- `slope > 0`: short-horizon vol is elevated relative to the 4-month norm
  (transient stress) → raise the risk budget.
- `persist → 1`: the 4-month vol is itself ≥ 1.5× its 3-year median
  (persistent high-vol regime, e.g. 2022) → damp the raise by 70%.
- `tilt` is bounded to [−1, +1] and 5-day smoothed.

### 3.3 Risk budget

```
b0 = 0.35 + 0.20 * tilt                 # range [0.15, 0.55]
b1 = min( b0, 0.18 / sleeve_vol )       # forecast portfolio-vol cap
b2 = b1 * brake_mult                    # brake_mult in {1.0, 0.5, 0.2}
b  = clip( b2, 0.03, 0.60 )
```

### 3.4 Drawdown brake (own risk control)

State machine on the strategy's own equity drawdown `dd = eq/peak − 1`
(through the prior close), with hysteresis:

```
if   dd <= -0.20                      -> state 2   (mult 0.20)
elif dd <= -0.12 and state == 0       -> state 1   (mult 0.50)
elif state == 2 and dd >= -0.14       -> state 1
elif state == 1 and dd >= -0.06       -> state 0
```

The brake is **not** the old stop: it is a slow allocation multiplier on a
continuous risk budget, it has no intraday trigger, and the strategy re-enters
gradually when the drawdown recovers. It is ablated in the controls.

### 3.5 Weights

```
tgt[k, QQQ] = b * wQ
tgt[k, TQQQ] = b * wT
tgt[k, BIL]  = 1 - b
```

Long-only, weights ≥ 0, sum = 1, gross ≤ 1 (no leverage).

## 4. Parameters (primary)

| Parameter | Value | Role |
|---|---:|---|
| `SHORT_WIN` | 20 | numerator of the vol slope |
| `LONG_WIN` | 120 | denominator and persistence level |
| `COMP_WIN` | 60 | ERC composition |
| `SLOPE_SCALE` | 0.35 | log-vol slope mapped to ±1 |
| `PERSIST_SCALE` | 0.50 | excess vol over median mapped to 0–1 |
| `PERSIST_DAMP` | 0.70 | how much persistent stress cancels the tilt |
| `SMOOTH` | 5 | days averaged for the tilt |
| `BASE_BUDGET` | 0.35 | budget at neutral tilt |
| `TILT_STRENGTH` | 0.20 | budget change per unit tilt |
| `VOL_CAP` | 0.18 | forecast portfolio-vol cap |
| `DD_HALF` / `DD_FLOOR` | −0.12 / −0.20 | brake thresholds |
| `DD_RELEASE` | −0.06 / −0.14 | brake release thresholds |
| `BAND` | 0.02 | harness rebalance band |
| `COSTS` | 1 / 5 / 10 bp | per side |

No parameter is chosen from a grid; values are round numbers from the
hypothesis. The neighbourhood in §7 is reported as a robustness check, not used
to pick the primary.

## 5. Warm-up

The 1-minute archive starts 2016-01-04, so there is no pre-2016 history. Vol
windows use `min_periods=60`; sessions before the first finite `sigma_Q(120)`
(or before the first finite persistence median) are **100% BIL**. Trading
effectively starts in early 2016 Q2. This is reported, not hidden. No synthetic
pre-2016 data is used.

## 6. Evaluation

- Harness: `research/bt.py`, compiled `simcore`; `bt.run` on 1-minute bars,
  2% band, next-open fills, 1 bp headline and 5/10 bp.
- Marks: 1-minute equity; `max_drawdown` positive fraction.
- Windows: **dev only** in this phase. The 10y (2017-01-03→) and 5y
  (2021-10-25→) windows overlap the holdout and are the lead's to run after
  freezing; this agent does not compute them.
- Benchmarks on dev: QQQ, TQQQ, BIL, the 165-day baseline (for correlation and
  context only — never as an input), and the original agent's 1 bp result.
- Correlation: Pearson correlation of **daily** returns (session close to
  session close from the 1-minute equity curve) with the 165-day baseline over
  dev. Must be < 0.60.
- Cross-rebuild correlation: computed by the lead from
  `research/strategies/correlations.json`; must be < 0.70.

## 7. Overfitting controls (all reported)

1. **Variants tried:** 12 pre-registered variants —
   3 `TILT_STRENGTH` (0.15/0.20/0.25) × 2 window pairs (20/120, 10/60) ×
   2 brake settings (on/off). The primary is the middle of each range.
2. **Neighbourhood:** ±1 step for `TILT_STRENGTH`, `SLOPE_SCALE`, `BASE_BUDGET`,
   `VOL_CAP`; report the full table, not the best cell.
3. **Ablations:** constant 35% budget (no tilt); ERC-only (no budget);
   tilt without the persistence damper; brake off.
4. **Placebo:** sign-flipped tilt (pro-cyclical) and a seeded random tilt with
   the same mean/std. If either matches the strategy, the state signal is noise.
5. **Sub-periods:** 2016–19, 2020–21, 2022–23.
6. **Events:** count transient-spike episodes (`slope > +0.5`, `persist < 0.3`);
   report the forward 20-day sleeve return and a stationary bootstrap p-value
   (10,000 resamples, 20-day blocks). < 40 events → underpowered, say so.
7. **No holdout peeking:** one shot by the lead after freeze.

## 8. Status rules

- `passed`: dev corr < 0.60, Sharpe ≥ 0.35, CAGR > BIL, the tilt survives the
  placebo/ablation, and the audit passes.
- `rejected`: any falsifier in HYPOTHESIS.md §5 fires and cannot be fixed without
  changing the idea.
- There is no `retired_overlay_only` outcome: the risk model is a complete
  allocation rule, not a filter on the old base. If it fails, it is rejected on
  evidence, not retired by construction.

## 9. Code map

`strategy.py`

| Function | Purpose |
|---|---|
| `load_panel()` | `bt.panel(("QQQ","TQQQ","BIL"), dev_start, dev_end, "1min")` |
| `session_arrays()` | session first/last bars, daily opens/closes, returns |
| `daily_state()` | lagged vols, slope, persistence, ERC weights, sleeve vol |
| `build_weights()` | budget + brake recursion → `(n,3)` minute weights + info |
| `expand_to_minutes()` | `tgt[k]` on every bar of session `k` (last bar of `k−1` = `tgt[k]`) |
| `baseline_weights()` | 165-day baseline, **comparison only** |
| `run_windows()` | `bt.run` at 1/5/10 bp on dev |
| `corr_vs_baseline()` | daily-return correlation |
| `controls()` | ablations, placebo, neighbourhood, sub-periods, event study |
| `main()` | writes `result.json` (only when the lead authorises a run) |

`bt.run`/`bt.run_many` only; no private simulator. The code is deliberately not
executed in this phase.
