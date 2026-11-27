# ML-microstructure-b: walk-forward intraday price-action model for TQQQ

**Pre-registration written 2026-11-27 15:24 ET, before the final `strategy.py`
run. Development window only: 2016-01-04 through 2023-12-29. No 2024-2026
observation is used, inspected, or scored.**

## Hypothesis

Late-session order-flow imbalance in QQQ carries information about the next
24 hours of TQQQ. When QQQ closes near the low of its intraday range after a
weak final 30 minutes, and participation is subdued relative to its recent
norm, the next session has historically drawn speculative dip-buying. The
effect is a short-horizon reversal, not a trend or volatility-premium signal.
A regularised walk-forward model can combine several weak, correlated
intraday shape features into a higher-conviction conditional forecast.

The model is deliberately small and causal:

- signal at the close of the **15:58** one-minute bar;
- fill at the **15:59** one-minute open (a next-open fill in `research/bt.py`);
- hold from that open to the 15:59 open of the next session;
- TQQQ when the forecast exceeds a threshold, BIL otherwise.

The 15:58-to-15:59 timing captures the overnight reaction that follows the
signal, while still using only information available before the fill.

## Data and timing

- QQQ, TQQQ and BIL adjusted one-minute bars from `data/intraday-hf/`.
- QQQ is the session calendar; TQQQ and BIL are aligned to it.
- Panel is sliced at 2023-12-29. The last used bar is 2023-12-29 15:59 ET.
- Features are built from QQQ bars through the 15:58 bar (whose close is the
  15:59 print). Highs and lows use the same bars.
- The TQQQ entry price is the 15:59 open; the label is the next 15:59-open
  return. This is the tradable entry-to-entry return; the simulator marks
  equity at each one-minute close.
- The 2016 H1 period is a no-signal burn-in: 100 is required before the first
  fit, so the strategy is in BIL until the first 2016Q3 forecast. Missing
  forecasts always map to BIL, never to TQQQ.

## Features (all QQQ, measured through 15:58)

Let `o_d` be the 09:30 open, `c_d` the 15:58 close, `h_d`/`l_d` the high/low
through 15:58, `c30_d` the 10:00 close, `o30_d` the 15:29 open, and `v_d` the
session volume through 15:58.

| feature | definition | economic reading |
|---|---|---|
| `gap` | `o_d / c_{d-1} - 1` | overnight gap / opening imbalance |
| `first30` | `c30_d / o_d - 1` | first-30-minute price action |
| `last30` | `c_d / o30_d - 1` | final-30-minute price action |
| `clv` | `2 (c_d - l_d)/(h_d - l_d) - 1` | close location in the daily range |
| `rng` | `(h_d - l_d)/c_d` | intraday range |
| `volr` | `log(v_d / mean(v_{d-20..d-1}))` | participation vs its 20-day norm |

No volatility, drawdown, trend or relative-strength feature is a primary
predictor. `rng` is the mandated intraday-range feature, not a volatility
regime filter. A 45% annualised vol-target overlay is evaluated only as a
risk-control diagnostic; it is not part of the headline cell.

## Target and model

- Target: `y_d = entry_{d+1}/entry_d - 1`, where `entry_d` is the TQQQ
  15:59 open on session `d`. The last row is NaN.
- Ridge: L2 penalty 30 on standardised features, target demeaned and scaled by
  the training mean/std; forecast converted back to return units. Long when
  `forecast - mean_train >= threshold`.
- Logistic: L2 penalty 5, target `1[y_d > 0]`; long when
  `P(y_d > 0) >= threshold`.
- Standardisation: training-window median imputation, mean/std scaling and
  clipping to [-5, 5]. Test rows use the training statistics only.
- Walk-forward: expanding window, quarterly refit, first test quarter 2016Q3,
  minimum 100 training rows, 3-calendar-day purge between the last training
  label and the test quarter. No full-sample scaling or fitting.

## Pre-registered cells (8)

| # | model | features | threshold | role |
|---:|---|---|---|---|
| 1 | ridge | 6 (`gap, first30, last30, rng, clv, volr`) | excess >= 50 bp | **headline** |
| 2 | ridge | 6 | excess >= 0 bp | plateau |
| 3 | ridge | 6 | excess >= 10 bp | plateau |
| 4 | ridge | 6 | excess >= 20 bp | plateau |
| 5 | ridge | 6 | excess >= 30 bp | plateau |
| 6 | ridge | 2 (`clv, volr`) | excess >= 0 bp | parsimonious ablation |
| 7 | ridge | 2 | excess >= 10 bp | parsimonious ablation |
| 8 | logistic | 6 | P(up) >= 0.58 | model alternative |

Cell 1 is fixed a priori as the headline because it uses the full mandated
feature set and a high-conviction threshold. The other cells are not used to
replace it after seeing results; they map the plateau and the feature-set
ablation. The threshold plateau is additionally reported at 0, 5, 10, 20, 30,
40, 50, 60, 75 and 100 bp, but those extra points are diagnostics, not new
cells.

## Evaluation protocol

- `research/bt.py::simulate`, next-open fills, 2% band, long-only, weights
  >= 0 and sum <= 1; TQQQ plus BIL, no QQQ sleeve.
- Headline at 1 bp slippage, with 5 bp and 10 bp reported honestly.
- Benchmark: TQQQ buy-and-hold on the same one-minute panel. The programme bar
  is 36.72% CAGR / 82.29% max DD / 0.82 Sharpe; a pass is CAGR > 36.72% and
  max DD < 60% (ideally).
- Metrics: CAGR, max drawdown, Sharpe, TQQQ exposure (`mean(w_daily)`), fills,
  daily correlation to TQQQ, yearly returns.

## Required diagnostics

1. **Plateau**: headline ridge across the threshold grid above.
2. **Feature ablation**: leave-one-feature-out on the headline cell, plus the
   2-feature and 5-feature subsets.
3. **Shuffled-label placebo**: 20 seeds; within each quarterly training window
   the training labels are permuted, the model is refit, and the same
   threshold/weight/simulation pipeline is run. Report the placebo
   distribution and the real strategy's percentile.
4. **Risk-control diagnostic**: headline signal multiplied by a causal 45%
   vol target (`clip(0.45/sigma20, 0, 1)`, `sigma20` from entry returns through
   d-1). Reported but not used in the headline because the raw drawdown is
   already below the 60% risk bar.

## Decision rule

The family passes if the headline cell has dev CAGR > 36.72% and max DD < 60%
at 1 bp. The 5 bp and 10 bp results determine whether the result is robust or
cost-fragile; they are reported as such and do not trigger re-tuning. If the
headline fails, the best honest cell is reported and the family is not
switched.

## Prohibitions honoured

- No 2024-2026 data in any feature, fit, weight or metric.
- No full-sample normalisation.
- No website edits, commits, pushes or nested subagents.
- All outputs under `research/new/family-ml-microstructure-b/`.
