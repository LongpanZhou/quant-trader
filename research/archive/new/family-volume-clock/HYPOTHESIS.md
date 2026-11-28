# HYPOTHESIS — family-volume-clock (midday volume acceleration)

**Status:** frozen pre-registration for the confirmatory run.
**Window:** development only, 2016-01-04 → 2023-12-29. The 2024-2026 holdout
is not loaded into any analysis and is left for the lead's one-shot run.
**New code:** `strategy.py` (this directory). `robustness.py` runs the placebos.

---

## 1. Mechanism

Market time is not calendar time. The information content of a price move
depends on how much volume has been traded, and on whether volume is arriving
faster or slower than its normal same-time-of-day pace. The family tests a
**volume-acceleration state**, not a price-range, opening-range, closing-flow,
trend, volatility or calendar state.

At 13:00 ET, compare the last 30 minutes of QQQ volume with the same 30-minute
window on each of the prior 20 sessions:

```
accel_k = sum(QQQ volume, 12:31..13:00, session k)
          --------------------------------------------------
          median over k-20..k-1 of the same 30-minute sum
```

`accel` is a pure volume-clock state: it says whether the midday tape is
running hot relative to its own time-of-day norm. The economic claim:

- **Volume burst** (`accel` high): urgent, information-driven repricing.
  Liquidity is being consumed, the move is already widely observed, and the
  overnight tail risk is elevated. Do not hold TQQQ overnight.
- **Volume drought** (`accel` low): no urgent flow. The residual overnight
  drift in TQQQ persists; the absence of a burst is the continuation state.
- **Deadband** (0.75 ≤ accel ≤ 0.85): the state is ambiguous; keep the prior
  state rather than churn.

The sign of the volume-weighted price move is a **secondary** test. At the
same 13:00 decision we compute

```
vwap_dev_k = QQQ close(13:00) / VWAP(09:30..13:00) - 1
```

and test whether the sign of this volume-weighted move predicts the overnight
return, alone and conditional on `accel`. The headline rule uses `accel` only;
the sign is reported as attribution, not silently folded into the centre.

Why 13:00? It is the natural midday sampling point: the opening flow has
settled and the closing flow has not started. The 12:31-13:00 window is
therefore a clean read on whether the middle of the session is urgent. It is
not a day-level calendar window (no month-end, FOMC, opex, holiday, or
turn-of-month rule).

## 2. Exact rules

| Item | Rule |
|---|---|
| Universe | QQQ (volume state), TQQQ (position), cash (idle); BIL variant reported |
| Decision clock | close of the 13:00 ET bar (offset 210 from 09:30) |
| Volume window | 12:31-13:00 ET, 30 one-minute QQQ bars |
| Normalisation | median of the same 30-minute window over the prior 20 sessions, strictly before session k |
| State machine | state 0→1 if `accel < 0.75`; state 1→0 if `accel > 0.85`; otherwise hold |
| Position | state 1: 100% TQQQ at the 13:01 open, hold through the 15:59 close, sell at the next 09:30 open. State 0: cash (0%) |
| Holding | one overnight per entry; no intraday-only leg in the headline |
| Fills | next-minute open, 2% band, 1 bp headline plus 5 bp and 10 bp |
| Constraints | long only, weights ≥ 0, row sum ≤ 1 |
| Not used | daily trend SMA, volatility targeting, drawdown/capitulation event, calendar window, opening range, closing-auction/rebalance flow, ML classifier |

The volume ratio uses raw QQQ share volume from the adjusted 1-minute archive.
Volume is not split-adjusted, but QQQ has no split in the window and the ratio
is scale-free. Half-days and sessions with fewer than 212 bars are skipped
(the 13:00 bar does not exist). Six sessions in 2016-2023 have a missing
morning bar, so offset 210 lands at 13:09-13:50; the decision is later than
13:00 but still causal.

## 3. Pre-registered 8-cell plateau

The centre is **13:00 / enter 0.75 / exit 0.85**. The confirmatory grid varies
the time and the deadband; all cells are run at 1 bp and 5 bp.

| # | Decision | Enter | Exit | Purpose |
|---:|---|---:|---:|---|
| 1 | 12:45 | 0.75 | 0.85 | 15 min earlier |
| 2 | 13:00 | 0.70 | 0.80 | lower state |
| 3 | 13:00 | 0.75 | 0.85 | **centre** |
| 4 | 13:00 | 0.75 | 0.90 | wider deadband |
| 5 | 13:00 | 0.80 | 0.90 | higher state |
| 6 | 13:00 | 0.80 | 1.00 | highest state / widest band |
| 7 | 13:15 | 0.75 | 0.85 | 15 min later |
| 8 | 13:30 | 0.75 | 0.85 | 30 min later |

A broader 5×4 neighbour table (12:00-13:30 × four deadbands) is reported in
`result.json`.

## 4. Falsifiers (kill criteria)

The family is **not accepted** if any of these holds on the development window:

1. **Too thin:** fewer than 100 fills, or fewer than 30 entries.
2. **No volume attribution:** the low-acceleration bucket's mean overnight
   TQQQ return is not above the high-acceleration bucket, or the OLS dummy
   `accel < 0.75` has t < 2.0 controlling for log realised volatility and
   |open-to-13:00 return|.
3. **Volatility proxy:** the acceleration dummy loses significance in that
   same OLS. Volume acceleration must not be a renamed low-vol filter.
4. **No plateau:** fewer than 6 of the 8 grid cells have positive 1 bp CAGR,
   or both time neighbours (12:45 and 13:15) have CAGR below half the centre.
5. **One-episode wonder:** any of 2016-2019, 2020-2021, 2022-2023 has
   non-positive CAGR.
6. **No risk compensation:** 10 bp CAGR ≤ BIL's development CAGR.
7. **Placebo:** the real CAGR is below the 95th percentile of the
   circular-shift or random-night placebo, or either p-value > 0.10.
8. **Stale signal:** using the prior session's acceleration retains ≥ 80% of
   the real CAGR (the signal would not be timely).
9. **Bar:** the 1 bp result fails both the TQQQ CAGR bar (36.72%) and the
   TQQQ Sharpe bar (0.82). Clearing only one is a risk-adjusted improvement,
   not a CAGR win, and must be stated as such.
10. **BIL requirement:** if the brief requires BIL as the idle asset, the BIL
    variant's 1 bp CAGR must not fall more than 1 pp below the TQQQ bar.

## 5. Data and alignment

- `research/bt.py` 1-minute QQQ/TQQQ/BIL panel, 2016-01-04..2023-12-29,
  60 calendar days of pre-start warmup for the 20-session volume baseline.
- QQQ volume is aligned to the QQQ minute grid by `load_1m` + reindex. No
  forward-filled volume is used in the signal: a missing minute contributes 0
  and the session is skipped if the 13:00 bar is absent.
- `accel[k]` uses only sessions k-20..k-1. No full-sample statistic.
- State at session k is known at 13:00:59; the TQQQ weight is placed on the
  13:00 bar and filled at the 13:01 open. The exit is placed on the 15:59 bar
  and filled at the next session's 09:30 open.
- Next-open fills, 2% band, 1/5/10 bp, long only, weights ≥ 0, sum ≤ 1.
- No 2024-2026 observation is used in any feature, weight, metric or table.
  The shared loader reads the source parquet; the panel is sliced to
  2023-12-29 before any computation.

## 6. Exploratory sequence (honesty note)

Before this freeze, the following volume-clock states were screened on the
development window: cumulative-volume thresholds at 40/50/60/75/100/125% of
the prior-20 median day; fixed-time 30-minute acceleration at 10:30-15:00;
volume-synchronised return and VWAP deviation; intraday-only, overnight and
next-close holds; BIL and cash idle states; and random-time/fixed-time
attribution. The centre was chosen for mechanism coherence and a broad
threshold plateau, not as the single highest cell. The exploratory scripts are
kept in `scratch/`. The confirmatory grid, controls and placebos in
`result.json` / `robustness.json` are reported in full, including the cells
that are weaker than the centre. The 2024-2026 holdout remains untouched.
