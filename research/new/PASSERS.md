# Verified full-window passers

Bar: TQQQ **37.54% CAGR / 81.68% max DD / 0.82 Sharpe** on 2016-01-04 to
2026-10-23, daily-close marks, 1 bp costs. A strategy is counted only after its
frozen development result and one-shot 2024-2026 holdout, with `holdout.json`
on disk, and it must clear the causality/freshness/weight audit in `AUDIT.md`.

| # | Strategy | Dev CAGR | 2024-26 CAGR | Full CAGR | Full DD | Full Sharpe |
|---:|---|---:|---:|---:|---:|---:|
| 1 | `drawdown-recovery-v2` | 57.63% | 32.87% | **49.99%** | 41.11% | 1.12 |
| 2 | `fast-trend-vol` | 51.51% | 29.22% | **44.61%** | 40.26% | 1.06 |
| 3 | `vol-term-structure` | 51.58% | 21.89% | **42.48%** | 35.80% | 1.15 |
| 4 | `vol-of-vol-timing` | 45.35% | 36.17% | **42.17%** | 51.64% | 1.08 |
| 5 | `crash-early-warning` | 40.21% | 50.44% | **42.06%** | 52.96% | 0.99 |
| 6 | `ml-regime-v2` | 59.33% | 3.66% | **41.74%** | 35.98% | 1.10 |
| 7 | `relative-value-tqqq` | 43.60% | 34.72% | **40.50%** | 51.54% | 0.94 |
| 8 | `ema-ribbon-trend` | 46.77% | 25.15% | **40.09%** | 46.58% | 0.97 |
| 9 | `qqq-spy-relative` | 44.18% | 27.72% | **38.98%** | 53.64% | 0.96 |
| 10 | `tqqq-52week-high` | 43.39% | 28.49% | **38.64%** | 40.59% | 1.04 |
| - | TQQQ buy & hold | 36.72% | - | 37.54% | 81.68% | 0.82 |

All ten have **0.0 pre-cut weight difference** at 2020-03-12 11:07, fresh
2024-2026 weights, valid long-only weights and a reproduced development slice
(`ml-regime-v2` dev difference -0.29 pp is the only non-zero, from its
one-change risk-off holdout; `tqqq-52week-high` is -0.09 pp from the v2 daily
signal mapping).

## Current website visibility

The site shows the best full-window CAGR in each family; the rest are hidden
but retained on disk (`META.json` `visible=false`).

| Family | Visible | Hidden |
|---|---|---|
| Trend + vol | `fast-trend-vol` (44.61%) | `ema-ribbon-trend`, `tqqq-52week-high` |
| Vol / crash | `vol-term-structure` (42.48%) | `vol-of-vol-timing`, `crash-early-warning`, `ml-regime-v2` |
| Relative ladder | `relative-value-tqqq` (40.50%) | `qqq-spy-relative` |
| Event recovery | `drawdown-recovery-v2` (49.99%) | — |

Four new strategies are visible; six are hidden. The existing 27 are unchanged.

## Not counted

| Strategy | Full CAGR | Full DD | Full Sharpe | Note |
|---|---:|---:|---:|---|
| `always-long-vol-target` | 37.25% | 58.94% | 0.95 | Frozen RV20/45 rerun is below the 37.54% bar. The earlier 50% variant reached 37.95% but failed the pre-cut test (4.7e-02). |
| `macro-event-tqqq` | 37.09% | 44.63% | 1.04 | G1 primary; G7 grid cell (61.4% dev) is post-hoc, not counted |
| `overnight-drift-filter` | 37.07% | 58.35% | 0.97 | 0.47 pp short |
| `momentum-crash-filter` | 35.61% | 50.06% | 0.89 | Holdout 20.10% |
| `donchian-trend` | 35.13% | 54.27% | 0.88 | Daily strategy; holdout 3.19% after the minute-expansion adapter |
| `turn-of-month` | 33.62% | 64.07% | 0.86 | Holdout 16.00% |
| `capitulation-reversal-v2` | 32.21% | 20.86% | 1.34 | 1 bp only; 34.67% dev at 5 bp; holdout 13.02% |
| `intraday-close-momentum` | 31.21% | 52.06% | 0.92 | Holdout -1.41% |
| `cross-asset-momentum` | 30.58% | 40.69% | 0.89 | Fragile Revision 2; holdout 9.23% |
| `orb-tqqq-volume` | - | - | - | 17.89% dev CAGR, no holdout |

Evidence: each passing strategy has `research/new/<slug>/holdout.json` and a
fresh `curves/<slug>.json`; `META.json` is the verified website set.
