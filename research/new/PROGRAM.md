# New-strategy research program

**Goal:** find new standalone strategies that beat TQQQ on the 2016-2023
development window, without requiring the old shared base or similarity to the
existing 27.

**Bar (development only):** TQQQ 2016-01-04 → 2023-12-29 is **36.72% CAGR /
82.29% max DD / 0.82 Sharpe** on 1-minute marks. A strategy passes if its dev
CAGR is above 36.72% with max DD below 82.29% (ideally below 60%). A lower-CAGR
but much better Sharpe/Calmar result is reported as risk-adjusted, not as a
pass.

## Protocol

- Development only: 2016-01-04 → 2023-12-29. The 2024-01-02 → 2026-10-23
  holdout is not loaded, inspected or used for selection.
- Next-open fills, 2% band, 1 bp headline plus 5/10 bp. Long-only, weights ≥0,
  sum ≤1.
- Signals causal; no full-sample normalisation; no parameter selection on the
  evaluation window.
- Pre-register a small grid (≤8 combinations) and report the plateau, not just
  the best cell.
- Each strategy lives in `research/new/<slug>/` with `HYPOTHESIS.md`,
  `strategy.py`, `result.json` and `report.md`.
- No website edits, no changes to existing strategies, no commits or pushes.

## Ten mandates

| # | Slug | Mechanism |
|---:|---|---|
| 1 | `fast-trend-vol` | Fast adaptive trend + volatility-targeted TQQQ allocator |
| 2 | `crash-early-warning` | TQQQ by default; de-risk on a vol/drawdown/gap early-warning composite |
| 3 | `cross-asset-momentum` | Dual momentum across QQQ/SPY/BIL, leveraged via TQQQ |
| 4 | `orb-tqqq-volume` | Intraday TQQQ opening-range breakout with volume/ATR confirmation |
| 5 | `overnight-drift-filter` | Overnight TQQQ premium with a crash-risk filter |
| 6 | `capitulation-reversal-v2` | Aggressive post-capitulation TQQQ reversal, 1–5 day hold |
| 7 | `macro-event-tqqq` | FOMC/CPI/OpEx event-window TQQQ exposure |
| 8 | `ml-regime-v2` | Walk-forward ML regime allocator with a new label/feature set |
| 9 | `vol-of-vol-timing` | Vol-of-vol / risk-state timing on TQQQ |
| 10 | `relative-value-tqqq` | TQQQ/QQQ or QQQ/SPY relative-value signal with a long bias |

## After the development results

The lead runs the holdout once, only for strategies that pass the dev bar. No
strategy is re-tuned after the holdout. Results are added to the website only
after the holdout and a final audit.
