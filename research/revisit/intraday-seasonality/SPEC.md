# SPEC — Close-Flow Exhaustion (`intraday-seasonality` revisit)

Design frozen 2026-11-26. **Not yet tested.** No result.json exists.

## 1. Universe and data

- Tradeable: **TQQQ** (long) and **BIL** (cash proxy). Long-only, one position at
  a time, at most 100% of equity. No leverage beyond TQQQ's own daily 3x.
- Signal input: **QQQ** 1-minute bars (the index proxy the flow is computed on).
- Source: local adjusted 1-minute archive `data/intraday-hf/QQQ|TQQQ|BIL-1m.parquet`
  (2016-01-04 → 2026-10-23), regular session only. QQQ is the calendar; BIL and
  TQQQ are reindexed and forward-filled by `research/bt.py`.
- Benchmark only: SPY daily (`data/round3/yahoo/SPY-1d-yahoo.parquet`).

## 2. Signal

Evaluated once per session, on the **15:58 bar close** (15:58:59 ET):

```
q_day = QQQ(15:58) / QQQ(09:30 session open) - 1
gap   = QQQ(09:30 session open) / QQQ(prior session close) - 1
fire  = q_day <= -1.0%            (base spec)
```

Only data through 15:58:59 is used. Sessions that close before 15:58 (the 18
early-close half-days) never fire.

## 3. Position

| | |
|---|---|
| Entry | buy TQQQ at the **15:59 open** (target set on the 15:58 bar) |
| Exit | sell at the **next session's 15:01 open** (target set on that session's 15:00 bar) |
| Hold | one session, ~23 hours |
| Size | 100% of equity when active, 0% otherwise |
| Overlap | none; a new signal on the exit day re-enters at that day's 15:59 |
| Stop | none in the base spec. Variant `stop=-5%`: if TQQQ closes 5% below the entry price before the scheduled exit, sell at the next open |

Half-days: if the exit session closes before 15:00, the exit target is set on
that session's last bar, so the fill is the next session's open. Documented, not
a bug.

## 4. Pre-registered variants (each is a one-step neighbourhood)

| id | change | values |
|---|---|---|
| V1 | threshold | −0.75%, **−1.0%**, −1.25%, −1.5% |
| V2 | crash bound `q_day >= upper` | none, −2.5%, −3.0% |
| V3 | gap filter `abs(gap) <= gap_max` | none, 0.5% |
| V4 | entry | **15:59 close**, 15:30 open |
| V5 | exit | **next 15:00**, next open |
| V6 | stop | **none**, −5% |
| V7 | hold | **1 session**, 2 sessions |
| V8 | sizing | **full**, scaled `clip(abs(q_day)/2%, 0.5, 1.0)` |

Bold = base spec. The grid is 4 × 3 × 2 × 2 × 2 × 2 × 2 × 2 = 768 combinations;
the lead should report `variants_tried` and select from a **plateau**, not the
single best cell. The base spec was chosen before any of these were run.

## 5. Placebos / controls

- **P1 up-day**: same trade after `q_day >= +1.0%`.
- **P2 random**: same trade on a random 11% of sessions (fixed seed, 100 draws,
  report the distribution).
- **P3 shuffled**: signal dates shuffled within each calendar year.
- **P4 gap-capitulation proxy**: same trade but selected on `gap <= -1%` instead
  of `q_day <= -1%`, to measure overlap with the gap-reversal rebuild.

## 6. Evaluation plan (when authorised)

- **Windows**: dev 2016-01-04 → 2023-12-29 (decision window, no holdout); 10y
  2017-01-03 → 2026-10-23; 5y 2021-10-25 → 2026-10-23; holdout
  2024-01-02 → 2026-10-23 (lead runs once, frozen).
- **Costs**: 1 bp headline, 5 bp and 10 bp.
- **Marks**: 1-minute equity marks (the strategy is already 1-minute).
- **Fills**: next-bar open, 2% band, `bt.simulate`.
- **Metrics**: CAGR, max drawdown, Sharpe, Sortino, fills, turnover, exposure,
  per-event mean/median/t, win rate.
- **Sub-periods**: 2016-19, 2020-21, 2022-23.
- **Correlations**: daily-return correlation vs the 165-day baseline (dev) and
  vs every other rebuild (lead).
- **Event count + bootstrap**: 237 dev signal days expected; bootstrap p-value
  on the mean event return (10,000 resamples).
- **Benchmarks**: TQQQ, QQQ, SPY buy-and-hold; the original
  `agents2/intraday-seasonality/result.json`.

## 7. Commands (do not run until authorised)

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
python research\revisit\intraday-seasonality\strategy.py --windows dev
```

`--holdout` is lead-only and must be run once on the frozen commit.

## 8. Hard-rule compliance

| rule | how |
|---|---|
| no 100-250 day MA gate on QQQ/TQQQ/SPY/NDX | no moving average is used anywhere in the position logic |
| no reused base weights | `build_weights` is written from scratch; nothing imports the old module |
| corr vs 165d baseline < 0.60 | measured pre-pause at 0.25 for the 15:30-entry version; to be re-measured |
| corr vs other rebuilds < 0.70 | check vs gap-capitulation-reversal and letf-rebalance-flow first |
| long-only by default | TQQQ/BIL only, gross ≤ 1 |
| no shorting | none |
| leave originals untouched | only `research/revisit/intraday-seasonality/` is written |
