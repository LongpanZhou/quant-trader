# Reserve cross-asset families -- index

Four reserve families built on external daily series and executed on the local
1-minute QQQ/TQQQ/BIL panel. They are used only if one of the ten primary
external families fails.

**Window:** 2016-01-04 .. 2023-12-29, development only. The 2024-2026 holdout
was physically excluded from every Parquet read.
**Execution:** `research/bt.py`, 1-minute marks, next-open fills, 2% band,
long-only, weights >= 0, sum <= 1. Headline 1 bp; 5 bp and 10 bp also reported.
**Harness:** `research/new/cross_asset.py` (shared plumbing);
`research/external.py` (`align`, `daily_targets_to_weights`).
**Verification:** `python research/new/verify_cross_asset.py`.

## Result table

| family | signal | 1 bp CAGR | 1 bp DD | Sharpe | Sortino | 5 bp CAGR | 10 bp CAGR | 8-cell plateau | max winner corr | verdict |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `family-rates-volatility` | MOVE / 252d median - 1 < 0 -> TQQQ, else BIL | **41.71%** | **38.33%** | 1.18 | 1.66 | 40.07% | 38.04% | 5/8 | 0.57 | **dev pass** |
| `family-international-relative` | EEM/QQQ 60d z > -0.5 -> TQQQ, else QQQ | **51.12%** | **54.81%** | 1.10 | 1.58 | 49.25% | 46.94% | 8/8 | 0.80 | **dev pass** |
| `family-small-cap-relative` | IWM/QQQ 20d z > -0.5 -> TQQQ, else QQQ | 45.40% | 78.08% | 0.99 | 1.41 | 42.49% | 38.94% | 8/8 | 0.83 | fail (2022-2023 CAGR -17.1%) |
| `family-copper-gold` | CPER/GLD 60d z > -0.5 -> TQQQ, else QQQ | 32.74% | 73.53% | 0.82 | 1.17 | 31.07% | 29.01% | 0/8 | 0.85 | fail (below TQQQ bar) |

TQQQ development bar: 36.72% CAGR / 82.29% max DD / 0.82 Sharpe. Local 1-minute
TQQQ: 36.15% / 82.29% / 0.80. All four families have at least 233 fills and 117
distinct fill events, so the activity floor (100 fills or 30 events) is met.

## Ranking for reserve use

1. **`family-rates-volatility`** -- the best drawdown control (38.3% vs TQQQ's
   82.3%), the lowest correlation to the nine winners (0.33-0.57), and it still
   clears the bar at 10 bp (38.04%). The 8-cell plateau is 5/8: the 252-session
   median cells work, the 126-session cells are weak, and the 20-session change
   fails as an ablation. Use it as a low-drawdown reserve.
2. **`family-international-relative`** -- the highest CAGR (51.1%) and an 8/8
   plateau, but the 60-session lookback is load-bearing (the 20-session ablation
   is 24.5% with 83.9% DD) and correlation to the winners reaches 0.80. Use it
   only if a return-oriented slot needs filling.
3. **`family-small-cap-relative`** -- headline pass but 78% drawdown and a
   -17.1% 2022-2023 subperiod. It is a levered Nasdaq beta overlay, not a crash
   hedge. The kill criterion for a negative subperiod triggers.
4. **`family-copper-gold`** -- clean negative. 32.7% CAGR, 0/8 plateau, placebo
   62nd percentile, static blend matches. The copper/gold ratio does not add
   usable timing information for a 3x Nasdaq sleeve in this sample.

## Design notes

- **No forbidden inputs.** No 100-250 day price-trend gate, no volatility
  targeting, no drawdown event, no calendar clock, no opening-range/close-flow,
  no ML and no additional relative-strength ratio gate. The 126/252-session
  windows are normalisation windows for the signal, not gates on QQQ's price.
- **Causality.** Signals use daily closes through session \(k\); the target is
  written at \(k\)'s 15:59 close and filled at \(k+1\)'s 09:30 open. A panel
  truncation at 2020-03-12 11:07 leaves every prior weight identical.
- **Exploratory.** The primary cell was chosen after daily-bar diagnostics on
  the development window; the 8-cell grid is a robustness probe, not a clean
  out-of-sample pre-registration. Every `result.json` records
  `exploratory: true`.
- **Costs.** Turnover is high (1,139x-3,454x) because the signals switch daily.
  The 10 bp column is the relevant cost stress; rates and international survive
  it, small-cap survives it on CAGR but not on the consistency kill, copper
  does not.
- **Holdout.** A separate process deposited `holdout.json` / `holdout_run.log`
  in each folder after the development run. This agent did not read or use
  them; every number above is from the 2016-2023 development window.

## Paths

```
research/new/family-rates-volatility/{HYPOTHESIS.md,strategy.py,result.json,report.md}
research/new/family-international-relative/{HYPOTHESIS.md,strategy.py,result.json,report.md}
research/new/family-small-cap-relative/{HYPOTHESIS.md,strategy.py,result.json,report.md}
research/new/family-copper-gold/{HYPOTHESIS.md,strategy.py,result.json,report.md}
research/new/cross_asset.py                  # shared harness
research/new/verify_cross_asset.py           # shape / regeneration / cut test
research/new/make_cross_asset_reports.py     # report.md generator
```
