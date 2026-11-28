# Trend/VIX regime switch — report

**Slug:** `family-regime-switch`  
**Dev:** 73.47% CAGR / 31.40% DD / 1.74 Sharpe.  
**Full:** **63.59% CAGR / 31.22% DD / 1.57 Sharpe**; 735 full fills;
35,087x turnover.  
**2024-2026 holdout:** 38.70% CAGR / 25.38% DD / 1.13 Sharpe.

## Head-to-head vs ratio-froth

| Full window | regime switch | ratio-froth |
|---|---:|---:|
| 1 bp CAGR | **63.59%** | 62.21% |
| 5 bp CAGR | **59.19%** | 56.62% |
| 10 bp CAGR | **53.87%** | 50.67% |
| Max drawdown | **31.22%** | 36.65% |
| Sharpe | **1.57** | 1.43 |
| CAGR / DD | **2.04** | 1.70 |

The switch beats ratio-froth on the full window. **That lead is not stable
through time.**

## Recent performance — the full-window lead is not robust

| Window | regime switch | ratio-froth |
|---|---:|---:|
| 2024 | **108.71%** | 89.73% |
| 2025 | 20.49% | **83.35%** |
| 2026 YTD | 0.79% | **29.83%** |
| Trailing 1 year | 13.67% | **37.35%** |
| Trailing 6 months | **−12.98%** | 23.42% |
| 2024-2026 holdout | 38.70% | **65.40%** |

The overlay wins in 2024 and over the full window, but materially underperforms
ratio-froth in 2025, 2026 and the trailing year. The full-window result should
not be read as a current edge.

## Rules

Calm (QQQ > 150-session MA **and** VIX ≤25): close-location weights.  
Stress (either condition fails): ratio-froth weights.

The regime uses the prior session close and applies to the next session, so
there is no look-ahead. Stress share is 22.5%; 106 switches.

## Grid

Development-window CAGR (1 bp):

| MA \ VIX | 20 | 25 | 30 |
|---|---:|---:|---:|
| 100 | 55.32% | 70.41% | 66.93% |
| 150 | 58.65% | **73.47%** | 71.04% |
| 200 | 57.18% | 70.41% | 68.03% |

The 150/25 cell is the development-grid maximum. That is a selection-bias
caveat. The full and holdout results are out-of-sample, but the recent table
shows the edge is period-dependent.

## Why this is an overlay

The switch is a composite of `family-close-location` and `ratio-froth`. It
inherits their signals by construction and is disclosed as an overlay, not as
an independent strategy.

## Caveats

- **No external paper is linked.** The rule was constructed manually as a
  two-strategy overlay and selected from the 3×3 grid above.
- The full-window lead is concentrated in 2016-2024; 2025-2026 underperform
  ratio-froth.
- Turnover is high (35,087x); the 5/10 bp CAGRs are 59.19% and 53.87%.
- The overlay is only as good as its two components.
