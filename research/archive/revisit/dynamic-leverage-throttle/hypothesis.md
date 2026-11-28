# Hypothesis and pre-registration: Volatility-Shock Recovery (VSR)

**Slug:** `dynamic-leverage-throttle`
**Date:** 2026-11-26
**Status:** design only. Backtests are paused. No `result.json` has been
generated for this version and no return, drawdown or correlation number below
is a result. They are pre-registered expectations and falsifiers.

---

## 1. What is genuinely new in the original strategy

The original `dynamic-leverage-throttle` is a volatility-targeted leverage
sleeve: `w = 0.30 + 0.70 × min(1, 0.65 / vol20)` on top of the shared 165-day
QQQ SMA regime and the round-1 armed 4% minute stop. The new idea is the
**inverse-volatility risk budget**: the position is sized by its own realised
volatility rather than held at a constant 100%.

The shared base, the 30% core and the 4% stop are *not* the idea. They are the
old implementation.

## 2. Why stripping the old base is not enough

Before the 2026-11-26 pause I ran a development-only exploration
(2016-01-04..2023-12-29) of the stripped continuous version. It failed the
independence test:

| Stripped variant | Dev CAGR / max DD | Corr vs 165d base |
|---|---:|---:|
| 165d base (benchmark) | 44.76% / 58.76% | 1.00 |
| Continuous inverse-vol TQQQ, 20–60% target | 22.5–45.7% / 31.6–69.8% | 0.79–0.82 |
| Continuous TQQQ→QQQ vol rotation | 31.1–41.1% / 41.1–48.2% | 0.76–0.81 |
| Vol gate to BIL, 45–50% threshold | 17.3–26.6% / 39.3–42.9% | 0.47–0.54 |
| Vol gate to QQQ, 40–60% threshold | 25.8–39.4% / 40.6–44.2% | 0.71–0.79 |

Any always-on TQQQ/QQQ exposure correlates about 0.8 with the old base, because
the base is long TQQQ in exactly the calm periods when a continuous vol target
is also long. The binary vol gate gets under 0.60 only by sitting in BIL most of
the time, and its return is weak. This is why the rebuild changes the
**mechanism**, not just the gate: VSR is deliberately long in a state the old
base avoids (high but falling volatility after a drawdown), and in BIL in the
calm uptrends where the old base is long.

These exploratory numbers are pre-pause, dev-only, 1 bp, 2% band, and are not
audited. They are motivation, not the candidate's result.

## 3. Standalone hypothesis

**H1 (main).** After a volatility shock, the *decay* of short-horizon realised
volatility identifies the end of forced deleveraging. When the market is also
in a drawdown, the next 2–8 weeks have positive convexity that can be captured
with TQQQ, and sizing the position inversely to the still-elevated volatility
keeps the risk budget roughly constant. The strategy should therefore earn a
respectable return with a much lower correlation to the trend base than any
always-on leverage rule.

**H2 (mechanism).** The signal is not price trend. It is the joint state
`v20 ≥ 1.25·v60` (a genuine vol shock), `v5 ≤ 0.85·v20` (the shock is
decaying), and `−35% ≤ QQQ drawdown from its 252-day high ≤ −8%` (there is
fear to recover from). The old base is usually *out* in this state; VSR is
*in*. In calm uptrends VSR is in BIL and the base is in TQQQ. The return
drivers are therefore close to orthogonal.

**H3 (sizing).** `w_TQQQ = min(0.75, 0.30 / v20)`; BIL for the rest. This is
the original inverse-vol idea, but now it owns the whole position instead of
tilting a 100% TQQQ base.

## 4. Universe, data and holding period

- **Signal:** QQQ daily close (drawdown) and TQQQ daily close (realised vol).
- **Instrument:** TQQQ; **cash:** BIL.
- **Data:** local adjusted 1-minute QQQ/TQQQ/BIL, 2016-01-04..2023-12-29.
  Daily bars are the 15:59 close. SPY daily exists at
  `data/round3/yahoo/SPY-1d-yahoo.parquet`, but its `SOURCE.md` restricts it to
  the buy-and-hold benchmark and there is no SPY 1-minute history for the
  development period. No sector, bond, gold or volatility-product data is
  local. The universe therefore stays QQQ/TQQQ/BIL rather than inventing a
  tradable series.
- **Holding period:** episodic, 2–8 weeks. Entry at the next session's open,
  hold across days and nights, exit at the next open after an exit signal.
  This is deliberately different from the old daily rebalance.

## 5. Exact primary specification (pre-registered)

Let `v5`, `v20`, `v60` be the annualised standard deviations of TQQQ daily
close-to-close log returns over 5, 20 and 60 sessions, using data through the
close of session `t`. Let `dd252_t = QQQ_t / max(QQQ over the last 252
sessions) − 1`.

**Entry** (only if flat and past the cooldown), evaluated at the close of `t`:

1. `v20_t ≥ 1.25 × v60_t` (vol shock);
2. `v5_t ≤ 0.85 × v20_t` (shock decaying);
3. `−0.35 ≤ dd252_t ≤ −0.08` (fear, but not a >35% catastrophe);
4. all inputs finite.

At the next session's open, buy `w = min(0.75, 0.30 / v20_t)` TQQQ; the rest
is BIL.

**While held:**

- Re-size every 5 sessions to `min(0.75, 0.30 / v20_t)`.
- Exit at the close of `t` (fill next open) if any of:
  - `v20_t ≤ 1.05 × v60_t` (vol normalised);
  - `dd252_t ≥ −0.03` (recovered to within 3% of the high);
  - `v5_t ≥ 1.10 × v20_t` (vol re-accelerating);
  - `dd252_t ≤ −0.40` (catastrophe stop);
  - 60 sessions held (time stop).
- After an exit, wait 5 sessions before a new entry (cooldown).

No 165-day moving-average gate, no 30% core, no 4% minute stop, no shorting.
Maximum TQQQ weight 75%; BIL earns its own return.

### Pre-registered parameter neighbourhood

The primary is the round middle of:

| Parameter | Primary | ±1 step grid |
|---|---:|---|
| `shock_mult` | 1.25 | 1.15 / 1.25 / 1.35 |
| `decay_ratio` | 0.85 | 0.80 / 0.85 / 0.90 |
| `dd_entry` | −8% | −6% / −8% / −10% |
| `target_vol` | 30% | 25% / 30% / 35% |
| `time_stop` | 60 | 40 / 60 / 80 |

The strategy is only promoted if the primary is inside a plateau: at least
2/3 of the 3×3×3×3×3 neighbourhood has the same sign of CAGR and a correlation
below 0.60, and the primary is not the single best cell.

## 6. Expected correlation vs the old base

**Prior: 0.15–0.45 daily-return correlation on the development period.**
Reasoning: VSR is long TQQQ mainly when QQQ is below its 165-day SMA and the
base is in BIL; it is in BIL in calm uptrends when the base is long. Overlap is
limited to the later part of recoveries, after the base re-enters and before
VSR's vol-normalisation exit. A correlation at or above **0.60** falsifies the
independence claim.

## 7. Falsifiers (pass/fail before any holdout)

1. **Correlation:** dev daily correlation with the 165-day baseline ≥ 0.60.
2. **Return:** dev CAGR < 8%, or Calmar (CAGR / max DD) < 0.50, or max DD > 35%
   on 1-minute marks.
3. **Events:** fewer than 12 independent entries, or episode-return bootstrap
   p-value > 0.10 (mean episode return not positive).
4. **Concentration:** 2020 contributes more than 80% of total P&L, or both
   2016–2019 and 2022–2023 are negative.
5. **Ablation:** removing the vol-decay condition performs as well (the decay
   filter is the mechanism, not a decoration).
6. **Neighbourhood:** the primary's ±1-step neighbourhood is unstable (CAGR
   sign flips or median Calmar below 0.35).
7. **Cost:** the edge disappears at 5 bp (10 bp can be reported as a caveat).

If 1, 2, 3 or 6 fails, mark the rebuild `rejected` rather than forcing it.

## 8. Provenance summary

| Claim | Source | Role |
|---|---|---|
| Inverse-vol sizing; vol-managed portfolios raise Sharpe | Moreira & Muir (2017) | inspired the sizing |
| Vol targeting cuts drawdowns/tails; slow estimator | Harvey et al. (2018) | supports sizing/risk |
| Vol-managed portfolios can fail OOS; temper the rule | Cederburg et al. (2020) | supports episodic design |
| Volatility clusters and mean-reverts | Bollerslev (1986) | supports v5/v20/v60 signal |
| Realised vol is a good forecast of future vol | Andersen & Bollerslev (1998) | supports signal |
| Realised vol has long memory | Andersen, Bollerslev, Diebold & Labys (2003) | supports signal |
| VIX spikes are a fear gauge; rebounds follow | Whaley (2000) | supports post-shock entry |
| Fear sentiment spikes predict high subsequent returns | Da, Engelberg & Gao (2015) | supports post-shock entry |
| Volatility feedback/asymmetry after shocks | Campbell & Hentschel (1992) | supports mechanism |
| 3× ETF path dependence and vol drag | Cheng & Madhavan (2009) | supports sizing TQQQ by vol |

Full URLs and exact evidence are in `report.md` §9.

## 9. What is explicitly not used

- No QQQ/TQQQ/SPY/NDX 100–250-day moving-average gate in the strategy.
  The 165-day SMA appears only in a benchmark function used to measure
  correlation, never in `build_weights`.
- No round-1 winner weights, no `build_weights` reuse, no 4% armed minute stop.
- No 30% permanent core. The position is either episodic TQQQ or BIL.
- No shorting and no leverage beyond TQQQ's embedded 3×.

## 10. Backtest plan after authorisation

1. Freeze this spec; run only 2016-01-04..2023-12-29.
2. Compute 1/5/10 bp metrics on 1-minute marks; benchmark TQQQ, QQQ, BIL and
   the original result.json numbers (the latter overlap the holdout).
3. Correlation of daily returns vs the 165-day baseline; correlation vs other
   rebuilds when their daily returns are available.
4. Sub-periods 2016–19, 2020–21, 2022–23; yearly returns.
5. Event count, median holding period, episode-return bootstrap p-value.
6. The 3×3×3×3×3 neighbourhood and the four ablations (drop shock, drop decay,
   drop drawdown, always-on vol target).
7. Only then hand the frozen candidate to the lead for the single holdout run.
