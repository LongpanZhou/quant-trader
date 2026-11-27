# Fill audit — drawdown-recovery-v2

**Verdict: the strategy's fill accounting is CORRECT. One reporting bug exists in
`research/new/run_holdout.py` (not in the strategy): window `fills` and
`turnover` are full-run scalars and are not sliced, so every window in
`holdout.json` reports 35 fills / 702.04x.**

- `result.json` dev **27 fills**: correct.
- `holdout.json` full **35 fills / 80.71% exposure**: correct.
- `holdout.json` dev **35 fills / 702.04x**: **wrong**; the dev slice is
  **27 fills / 202.24x**. The same full-run scalar is repeated in the
  holdout, 10y and 5y windows.
- 35 = 27 dev + 8 holdout fills. The 8 extra are **4 new entries + 4 exits**,
  not band rebalances. Full exposure 80.71% is consistent with dev 78.78%.
- No duplicate, missing, band-rebalance or wrong-index fill. Weights are
  non-negative and sum to 1.0 around every fill.

---

## 1. Reproduction

Frozen code: `research/new/drawdown-recovery-v2/strategy.py` as it stands.
No strategy logic was changed for this audit.  Panels:
`bt.panel(("QQQ","TQQQ","BIL"), "2016-01-04", end, "1min", warmup_days=0)`
with `end=2023-12-29` for dev and `end=2026-10-23` for the full window.
Fills from `bt.run` (band 2%, 1 bp).

| Replay | Fills | Turnover | Exposure | End equity |
|---|---:|---:|---:|---:|
| `result.json` dev | 27 | 202.241 | 78.78% | $3,783,755.38 |
| dev panel, `bt.run` | **27** | **202.241** | **78.78%** | **$3,783,755.38** |
| full weights, dev slice | **27** | **202.241** | **78.78%** | **$3,783,755.38** |
| full panel, `bt.run` | **35** | **702.038** | **80.71%** | — |
| `holdout.json` full | 35 | 702.038 | 80.71% | — |
| `holdout.json` dev | 35 | 702.038 | 78.78% | $3,783,755.38 |

The dev slice replay is not a different simulation with a different starting
cash: the full weights' first 781,880 bars are exactly the dev weights.

- `len(tsd) == 781,880`, `len(tsf) == 1,056,144`.
- `np.allclose(w_dev, w_full[:781,880])` → **True**, max difference **0.0**.
- Weight changes: dev **27**, full **35** — exactly the fill counts.
- An independent trade tracer that copies `bt.simulate_python`'s loop and logs
  every fill matches both the pure-Python and compiled simulators exactly:
  equity max abs diff **0.0**, cash max abs diff **0.0**, fills and turnover
  identical to the last digit.

## 2. Exact counts

| Window | Fills | Buys (entries) | Sells (exits) | Band rebalances | Completed round trips | Open at end | Post-exit cash episodes |
|---|---:|---:|---:|---:|---:|---:|---:|
| Dev 2016-01-04..2023-12-29 | **27** | **14** | **13** | **0** | **13** | **1** | **13** |
| Holdout 2024-01-02..2026-10-23 | **8** | **4** | **4** | **0** | 3 new + 1 carry-in exit | **1** | **4** |
| Full 2016-01-04..2026-10-23 | **35** | **18** | **17** | **0** | **17** | **1** | **17** |
| 10y 2017-01-03..2026-10-23 | 32 | 16 | 16 | 0 | — | — | — |
| 5y 2021-10-25..2026-10-23 | 16 | 8 | 8 | 0 | — | — | — |

Definitions:

- **Entry** = a buy from target 0 to target 1. **Exit** = a sell from target 1
  to target 0. No positive-to-positive resize occurs, so the 2% band never
  triggers a rebalance.
- The dev **14 positions** = 13 completed round trips + the still-open
  2023-01-10 position. The 13 post-exit cash episodes are the 13 intervals
  after those exits. There is also one **initial pre-entry cash day**
  (2016-01-04), which is not a post-exit cash episode; the report's
  `n_cash_episodes=13` counts only the 13 post-exit ones.
- The full **18 positions** = 17 completed + the still-open 2026-08-05
  position. The 17 post-exit cash episodes are the 13 dev episodes plus 4
  holdout episodes (`2024-07-26..2024-09-27`, `2025-03-05..2025-05-07`,
  `2026-03-31..2026-04-07`, `2026-07-29..2026-08-05`), plus the initial day.
- In the holdout window the 4 buys are new entries. Of the 4 sells, the first
  (2024-07-26) closes the 2023-01-10 position carried in from dev; the other
  three close the first three new entries. The 2026-08-05 buy remains open.
  Hence 3 completed **new** round trips + 1 open.
- The 10y and 5y windows start with a position already held and end with one
  open, so their buys/sells are fills, not complete round trips. The 10y
  first sell closes the 2016-03-17 carry-in; the 5y first sell closes the
  2021-03-17 carry-in.

## 3. Every fill

All fills are TQQQ (column 1). QQQ and BIL weights are zero throughout, so
there are no QQQ/BIL fills. All timestamps are US/Eastern. `Target` is the
strategy weight before → after; `Book` is the actual equity weight at the
fill price (entry shows 0.9999 because of the 1 bp slippage charge; exit
shows 0.0000). The audit's tracer logs the fill price after slippage.

| # | Fill (ET) | Ticker | Side | Qty | Price | Notional | Target before -> after | Book weight before -> after | Window | Reason |
|---:|---|---|---|---:|---:|---:|---|---|---|---|
| 1 | 2016-01-05 09:30 | TQQQ | buy | 46,614.54 | 2.15 | 100,000 | 0 -> 1 | 0.0000 -> 0.9999 | dev | entry (initial; ends initial cash) |
| 2 | 2016-01-08 09:30 | TQQQ | sell | 46,614.54 | 1.89 | 88,124 | 1 -> 0 | 1.0000 -> 0.0000 | dev | exit (opens cash episode) |
| 3 | 2016-03-17 09:30 | TQQQ | buy | 46,164.90 | 1.91 | 88,124 | 0 -> 1 | 0.0000 -> 0.9999 | dev | entry (closes cash episode) |
| 4 | 2018-02-09 09:30 | TQQQ | sell | 46,164.90 | 5.35 | 246,794 | 1 -> 0 | 1.0000 -> 0.0000 | dev | exit (opens cash episode) |
| 5 | 2018-02-26 09:30 | TQQQ | buy | 36,317.20 | 6.80 | 246,794 | 0 -> 1 | 0.0000 -> 0.9999 | dev | entry (closes cash episode) |
| 6 | 2018-03-26 09:30 | TQQQ | sell | 36,317.20 | 5.89 | 213,967 | 1 -> 0 | 1.0000 -> 0.0000 | dev | exit (opens cash episode) |
| 7 | 2018-04-13 09:30 | TQQQ | buy | 36,065.95 | 5.93 | 213,967 | 0 -> 1 | 0.0000 -> 0.9999 | dev | entry (closes cash episode) |
| 8 | 2018-10-12 09:30 | TQQQ | sell | 36,065.95 | 6.85 | 247,228 | 1 -> 0 | 1.0000 -> 0.0000 | dev | exit (opens cash episode) |
| 9 | 2019-01-23 09:30 | TQQQ | buy | 48,444.94 | 5.10 | 247,228 | 0 -> 1 | 0.0000 -> 0.9999 | dev | entry (closes cash episode) |
| 10 | 2019-06-03 09:30 | TQQQ | sell | 48,444.94 | 5.92 | 286,828 | 1 -> 0 | 1.0000 -> 0.0000 | dev | exit (opens cash episode) |
| 11 | 2019-06-10 09:30 | TQQQ | buy | 42,065.93 | 6.82 | 286,828 | 0 -> 1 | 0.0000 -> 0.9999 | dev | entry (closes cash episode) |
| 12 | 2020-02-26 09:30 | TQQQ | sell | 42,065.93 | 10.61 | 446,453 | 1 -> 0 | 1.0000 -> 0.0000 | dev | exit (opens cash episode) |
| 13 | 2020-04-23 09:30 | TQQQ | buy | 59,382.82 | 7.52 | 446,453 | 0 -> 1 | 0.0000 -> 0.9999 | dev | entry (closes cash episode) |
| 14 | 2020-09-09 09:30 | TQQQ | sell | 59,382.82 | 15.34 | 910,911 | 1 -> 0 | 1.0000 -> 0.0000 | dev | exit (opens cash episode) |
| 15 | 2020-10-28 09:30 | TQQQ | buy | 59,187.48 | 15.39 | 910,911 | 0 -> 1 | 0.0000 -> 0.9999 | dev | entry (closes cash episode) |
| 16 | 2020-11-02 09:30 | TQQQ | sell | 59,187.48 | 14.24 | 842,621 | 1 -> 0 | 1.0000 -> 0.0000 | dev | exit (opens cash episode) |
| 17 | 2020-11-05 09:30 | TQQQ | buy | 47,346.85 | 17.80 | 842,621 | 0 -> 1 | 0.0000 -> 0.9999 | dev | entry (closes cash episode) |
| 18 | 2021-03-04 09:30 | TQQQ | sell | 47,346.85 | 19.96 | 945,114 | 1 -> 0 | 1.0000 -> 0.0000 | dev | exit (opens cash episode) |
| 19 | 2021-03-17 09:30 | TQQQ | buy | 44,082.16 | 21.44 | 945,114 | 0 -> 1 | 0.0000 -> 0.9999 | dev | entry (closes cash episode) |
| 20 | 2022-01-19 09:30 | TQQQ | sell | 44,082.16 | 32.03 | 1,411,938 | 1 -> 0 | 1.0000 -> 0.0000 | dev | exit (opens cash episode) |
| 21 | 2022-07-15 09:30 | TQQQ | buy | 113,010.28 | 12.49 | 1,411,938 | 0 -> 1 | 0.0000 -> 0.9999 | dev | entry (closes cash episode) |
| 22 | 2022-08-30 09:30 | TQQQ | sell | 113,010.28 | 14.17 | 1,600,808 | 1 -> 0 | 1.0000 -> 0.0000 | dev | exit (opens cash episode) |
| 23 | 2022-09-29 09:30 | TQQQ | buy | 157,986.52 | 10.13 | 1,600,808 | 0 -> 1 | 0.0000 -> 0.9999 | dev | entry (closes cash episode) |
| 24 | 2022-09-30 09:30 | TQQQ | sell | 157,986.52 | 9.58 | 1,514,097 | 1 -> 0 | 1.0000 -> 0.0000 | dev | exit (opens cash episode) |
| 25 | 2022-11-29 09:30 | TQQQ | buy | 149,323.71 | 10.14 | 1,514,097 | 0 -> 1 | 0.0000 -> 0.9999 | dev | entry (closes cash episode) |
| 26 | 2022-12-21 09:30 | TQQQ | sell | 149,323.71 | 8.75 | 1,307,174 | 1 -> 0 | 1.0000 -> 0.0000 | dev | exit (opens cash episode) |
| 27 | 2023-01-10 09:30 | TQQQ | buy | 153,483.50 | 8.52 | 1,307,174 | 0 -> 1 | 0.0000 -> 0.9999 | dev | entry (closes cash episode) |
| 28 | 2024-07-26 09:30 | TQQQ | sell | 153,483.50 | 31.83 | 4,885,640 | 1 -> 0 | 1.0000 -> 0.0000 | holdout | exit (opens cash episode) |
| 29 | 2024-09-27 09:30 | TQQQ | buy | 135,050.47 | 36.18 | 4,885,640 | 0 -> 1 | 0.0000 -> 0.9999 | holdout | entry (closes cash episode) |
| 30 | 2025-03-05 09:30 | TQQQ | sell | 135,050.47 | 34.28 | 4,629,955 | 1 -> 0 | 1.0000 -> 0.0000 | holdout | exit (opens cash episode) |
| 31 | 2025-05-07 09:30 | TQQQ | buy | 164,383.04 | 28.17 | 4,629,955 | 0 -> 1 | 0.0000 -> 0.9999 | holdout | entry (closes cash episode) |
| 32 | 2026-03-31 09:30 | TQQQ | sell | 164,383.04 | 38.92 | 6,397,959 | 1 -> 0 | 1.0000 -> 0.0000 | holdout | exit (opens cash episode) |
| 33 | 2026-04-07 09:30 | TQQQ | buy | 147,858.41 | 43.27 | 6,397,959 | 0 -> 1 | 0.0000 -> 0.9999 | holdout | entry (closes cash episode) |
| 34 | 2026-07-29 09:30 | TQQQ | sell | 147,858.41 | 61.39 | 9,076,310 | 1 -> 0 | 1.0000 -> 0.0000 | holdout | exit (opens cash episode) |
| 35 | 2026-08-05 09:30 | TQQQ | buy | 120,277.14 | 75.46 | 9,076,310 | 0 -> 1 | 0.0000 -> 0.9999 | holdout | entry (closes cash episode; open at end) |

The entry and exit quantities are identical within every round trip (full
liquidation), e.g. 46,614.54 bought on 2016-01-05 and 46,614.54 sold on
2016-01-08; 153,483.50 bought on 2023-01-10 and 153,483.50 sold on
2024-07-26. This is a clean 0/1 implementation, not a partial-resize system.

## 4. Why 27 dev vs 35 full is correct

The difference is exactly the 8 fills after 2024-01-02:

| # | Fill | Side | Notional |
|---:|---|---|---:|
| 28 | 2024-07-26 | sell | 4,885,640 |
| 29 | 2024-09-27 | buy | 4,885,640 |
| 30 | 2025-03-05 | sell | 4,629,955 |
| 31 | 2025-05-07 | buy | 4,629,955 |
| 32 | 2026-03-31 | sell | 6,397,959 |
| 33 | 2026-04-07 | buy | 6,397,959 |
| 34 | 2026-07-29 | sell | 9,076,310 |
| 35 | 2026-08-05 | buy | 9,076,310 |

That is 4 new entries and 4 exits, 0 band rebalances. The first exit closes
the 2023-01-10 position carried into 2024; the other three close the first
three new entries; the last entry remains open at the end. So the full
window has 17 completed round trips + 1 open, and 17 post-exit cash episodes
+ the initial day.

Exposure is consistent with this: dev 78.78%, full 80.71%, holdout slice
86.21%. The full 80.71% is inside the stated ~79-81% range; the dev 78.78%
is just below it; the holdout slice alone is higher because it has only four
cash episodes and spends less time out.

The `holdout.json` dev count of 35 is **not** a different dev fill set. The
dev-slice replay of the full weights gives 27, and the dev equity fields in
`holdout.json` (CAGR, DD, Sharpe, exposure, ending equity $3,783,755.38)
match `result.json` exactly. Only `fills` and `turnover` are wrong in that
window, because they are full-run scalars copied through by the runner.

## 5. The 2% band and turnover

**Band rebalances: 0.** All 35 fills are 0↔1 entries/exits. For a binary
target the simulator's band is inert:
- a new entry has `is_new=True`, which bypasses the `shortfall <= band * book`
  test;
- an exit has `target == 0`, which sells the whole position without consulting
  the band;
- there is no positive-to-positive target change, so no resize can occur.

The extra 8 full-run fills are therefore new entries/exits, **not** band
rebalances.

**Turnover 202.24x is consistent with 27 fills**, with the definition
`total traded notional / initial $100,000`:

- dev total notional = **$20,224,116**; 27 fills; 202.24x.
- mean = $749,041, median = $842,621, min = $88,124, max = $1,600,808.
- The ratio is large because the notional per fill grows with the compounded
  equity (the dev ending equity is $3.78M). It is a cumulative notional
  ratio, not a count: 202x is not 202 round trips. 27 fills with 14 buys and
  13 sells and growing trade sizes produce exactly 202.24x.

Full-window turnover is $70,203,844 / $100,000 = **702.04x**. The 8 holdout
fills alone are $49,979,728 = **499.80x** because they occur at $4.6M-$9.1M
notional each; the 27 dev fills are the remaining 202.24x. The large jump is
compounding, not extra trading.

Correct window counts and turnover (global $100k denominator):

| Window | Fills | Buys | Sells | Turnover |
|---|---:|---:|---:|---:|
| Dev | 27 | 14 | 13 | 202.24x |
| Holdout | 8 | 4 | 4 | 499.80x |
| Full | 35 | 18 | 17 | 702.04x |
| 10y | 32 | 16 | 16 | 699.28x |
| 5y | 16 | 8 | 8 | 616.48x |

`holdout.json` reports **35 / 702.04x for every one of these windows**. The
full row is correct; the other four are the same full-run scalar. For the
holdout window, 499.80x is relative to the original $100k; relative to the
$3,685,636.63 equity at the 2024-01-02 open it is 13.56x. The runner does
not state which denominator it intends; the current full-run value is the
global one.

## 6. Duplicate / missing / index checks

- **Fill timing:** all 35 fills are at **09:30:00 ET**, the first bar of a
  session. All decision bars are the prior session's **15:59:00 ET** bar.
  Zero exceptions.
- **One fill per change:** 27 dev weight changes = 27 dev fills; 35 full
  weight changes = 35 full fills. There is no weight change without a fill
  and no fill without a weight change.
- **Duplicates/missing:** none. Each target change produces exactly one fill;
  every round-trip entry and exit quantity matches exactly.
- **Weight validity:** across all 1,056,144 full bars, `min(weight)=0.0` and
  `max(row sum)=1.0`; across the 781,880 dev bars the same. There is no
  negative weight and no row above 1.0 at any bar, including the bars around
  each fill.
- **Index identity:** `w_dev` equals `w_full[:781880]` exactly (max diff
  0.0), and the 27 dev fills match the first 27 full fills exactly (date,
  side, quantity, price). The dev slice is therefore the same frozen
  decision path, not a re-simulation with different starting cash.
- **Tracer identity:** the independent fill logger matches
  `bt.simulate_python` and the compiled `bt.simulate` on equity, cash,
  fills and turnover with max abs difference **0.0**. The table above is the
  simulator's actual trade sequence, not a reconstruction from weights.
- **Only label nuance:** the episode table in `report.md` uses the decision
  date (e.g. "entry 2016-01-04"), while the fill is the next open
  (2016-01-05 09:30). That is a signal-date vs fill-date convention, not a
  weight-index error. The weight index is correct: the target set at the
  last bar of session k (15:59) fills at the first bar of session k+1
  (09:30).
- **`w1[-1] = w1[-2]`:** this line overwrites the last bar's target, but the
  last bar's weight is never used as a fill trigger because there is no
  next bar. It neither creates nor suppresses a fill. In both the dev and
  full runs the last two weights are 1.0, so it is a no-op anyway.

## 7. Code issue in the runner (not the strategy)

`research/new/run_holdout.py::minute_stats` lines 117-128:

```python
rr = {k: (np.asarray(v)[mask] if isinstance(v, (list, np.ndarray)) else v)
      for k, v in r.items()}
rr["ts"] = ts[mask]
s = bt.stats(rr, 252 * 390)
return {k: float(s[k]) for k in (..., "fills", "turnover", ...)}
```

`r["fills"]` is a Python `int` and `r["turnover"]` is a Python `float`.
Neither is a list/ndarray, so neither is masked. `bt.stats` then returns
`result["fills"]` and `result["turnover"]` unchanged. The equity and cash
arrays are masked, which is why CAGR, DD, Sharpe, exposure and ending equity
are correct for each window, but `fills` and `turnover` are the full-run
scalars for every window.

**Proposed fix (not applied, pending lead approval):**

1. Add per-fill information to the simulation result. The cleanest is a fill
   log of `(timestamp, notional)`; alternatively add cumulative
   `fills_cum[i]` and `traded_cum[i]` arrays to `bt.simulate`/`simulate_many`
   (both the Python and simcore paths).
2. In `minute_stats`, filter by the window:
   - `fills = sum(1 for t, n in fill_log if a <= t < b)`;
   - `turnover = sum(n for t, n in fill_log if a <= t < b) / start_equity`
     (global denominator) or `/ equity_at_window_start` (window-relative).
   If using cumulative arrays, diff across the mask boundaries, taking care
   that a fill at the first bar of the window is included.
3. Add a regression check: dev 27 / 202.24x, full 35 / 702.04x, holdout
   8 / 499.80x, 10y 32 / 699.28x, 5y 16 / 616.48x (global denominator).
4. State the turnover denominator explicitly in the JSON; the current
   full-run metric is traded notional / initial $100k, while a window-relative
   holdout value would be 13.56x.

The strategy's `build_weights`, `weights_from_daily` and `state_machine` do
not need any change. The strategy's `result.json` 27 is correct; the
`holdout.json` full 35 is correct; the per-window `fills`/`turnover` fields
in `holdout.json` are the reporting bug.

## 8. Verdict

**Correct strategy; bug in the runner's window aggregation.** The dev count
is 27 (14 entries + 13 exits + 0 rebalances), not 35. The full count is 35
(18 entries + 17 exits + 0 rebalances), which is exactly 27 dev + 8 holdout
fills. The 2% band produces zero rebalances. The 202.24x dev turnover is the
cumulative traded notional / $100k and is consistent with 27 fills. No fill
is duplicated, missing or caused by a wrong weight index; the independent
tracer reproduces the simulator exactly.
