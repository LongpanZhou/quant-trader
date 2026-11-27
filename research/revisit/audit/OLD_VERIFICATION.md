# Original-27 verification

Second-pass review of the original `research/revisit/` strategies: the **25 below the TQQQ bar** plus the two above-bar legacy names (`ratio-froth`, `vol-scaled-crash-stop`). Each runnable strategy was rerun in an isolated sandbox on the full 2016-2026 window, next-open, 2% band, 1 bp, long-only; no strategy code, parameter, curve, website file or exporter was changed.

Full-window bar: TQQQ **37.54% CAGR / 81.68% max DD / 0.82 Sharpe**, daily-close marks. Metrics below are daily-close. `dev` is the frozen 2016-2023 `result.json` 1 bp headline for the freeze that produced the curve; `published full` is `web/public/data/compare/all.json`; `rerun full` is the clean sandbox rerun; `current full` is the current `strategy.py` rerun where it differs from the frozen curve.

## Counts

| Item | Count |
|---|---:|
| Original 27 reviewed | 27 |
| Below TQQQ bar | 25 |
| Above TQQQ bar | 2 |
| **Verified-full** | **17** |
| — below-bar verified-full | 16 |
| — above-bar verified-full | 1 |
| **Stale** | **9** |
| **Curve-only / needs-adapter** | **1** |
| Overlay-only | 0 |
| No-code | 0 |

`ratio-froth` has no local code in the revisit tree but is lead-verified; it is counted as verified-full, not no-code.

The nine stale names are the eight curves in `curve_integrity.md` plus `ml-classifier`. All eight pre-tune stale curves were reproduced from `_before_tune/` code. `ml-classifier` needs the corrected monthly-refit extension. `ratio-froth` is lead-verified (no local code); `vol-scaled-crash-stop` needs an OHLC/ATR adapter for the shared runner.

## Verification table

| slug | family | dev CAGR / DD / Sharpe | published full | rerun full | current full | difference (rerun - published) | status | reason |
|---|---|---|---|---|---|---|---|---|
| `event-risk-overlay` | calendar | 26.94% / 39.04% / 1.08 | 22.20% / 36.97% / 0.96 | 22.20% / 36.97% / 0.96 | — | +0.00 pp / +0.00 pp / +0.000 | verified-full | Frozen-code full rerun reproduces the published curve exactly (0.00 pp CAGR/DD, 0.000 Sharpe). |
| `gap-fill-fade` | short-reversal | 1.42% / 0.48% / 0.93 | 2.21% / 0.38% / 6.53 | 2.20% / 0.38% / 6.53 | — | -0.01 pp / +0.00 pp / -0.006 | verified-full | Frozen-code full rerun reproduces the published curve within 0.01 pp CAGR/DD and 0.006 Sharpe. |
| `intraday-mean-reversion` | short-reversal | 11.31% / 31.47% / 0.58 | 12.41% / 21.48% / 0.71 | 12.41% / 21.48% / 0.71 | — | +0.00 pp / +0.00 pp / +0.000 | verified-full | Frozen-code full rerun reproduces the published curve exactly (0.00 pp CAGR/DD, 0.000 Sharpe). |
| `intraday-momentum` | session-timing | 13.51% / 63.98% / 0.57 | 14.65% / 63.55% / 0.61 | 14.65% / 63.55% / 0.61 | — | +0.00 pp / +0.00 pp / +0.000 | verified-full | Frozen-code full rerun reproduces the published curve exactly (0.00 pp CAGR/DD, 0.000 Sharpe). |
| `intraday-seasonality` | rebalance-flow | 21.84% / 43.75% / 0.75 | 26.41% / 39.24% / 0.96 | 26.41% / 39.24% / 0.96 | — | +0.00 pp / +0.00 pp / +0.000 | verified-full | Frozen-code full rerun reproduces the published curve exactly (0.00 pp CAGR/DD, 0.000 Sharpe). |
| `letf-rebalance-flow` | rebalance-flow | 13.20% / 41.80% / 0.52 | 7.80% / 42.98% / 0.40 | 7.80% / 42.98% / 0.40 | — | +0.00 pp / +0.00 pp / +0.000 | verified-full | Frozen-code full rerun reproduces the published curve exactly (0.00 pp CAGR/DD, 0.000 Sharpe). |
| `ml-crash-overlay-winner` | ml-microstructure | 15.80% / 22.42% / 0.81 | 15.07% / 23.33% / 0.76 | 15.07% / 23.33% / 0.76 | — | +0.00 pp / +0.00 pp / +0.000 | verified-full | Frozen-code full rerun reproduces the published curve exactly (0.00 pp CAGR/DD, 0.000 Sharpe). |
| `opening-range-breakout` | intraday-microstructure | -2.10% / 17.22% / -0.53 | -1.32% / 19.99% / -0.33 | -1.32% / 19.99% / -0.33 | — | +0.00 pp / +0.00 pp / +0.000 | verified-full | Frozen-code full rerun reproduces the published curve exactly (0.00 pp CAGR/DD, 0.000 Sharpe). |
| `overnight-crash-filter` | session-timing | 10.37% / 27.62% / 0.76 | 11.34% / 26.98% / 0.81 | 11.34% / 26.98% / 0.81 | — | +0.00 pp / +0.00 pp / +0.000 | verified-full | Frozen-code full rerun reproduces the published curve exactly (0.00 pp CAGR/DD, 0.000 Sharpe). |
| `ratio-pairs` | relative | 18.96% / 34.59% / 1.11 | 20.42% / 33.94% / 1.13 | 20.43% / 33.94% / 1.13 | — | +0.01 pp / +0.00 pp / +0.000 | verified-full | Frozen-code full rerun reproduces the published curve within 0.01 pp CAGR/DD and 0.006 Sharpe. |
| `risk-parity-hrp` | other | 5.70% / 18.46% / 0.65 | 6.49% / 17.89% / 0.69 | 6.49% / 17.89% / 0.69 | — | +0.00 pp / +0.00 pp / +0.000 | verified-full | Frozen-code full rerun reproduces the published curve exactly (0.00 pp CAGR/DD, 0.000 Sharpe). |
| `stop-reentry-recovery` | rebalance-flow | 1.26% / 1.81% / 0.80 | 2.05% / 1.25% / 5.09 | 2.05% / 1.25% / 5.09 | — | +0.00 pp / +0.00 pp / +0.000 | verified-full | Frozen-code full rerun reproduces the published curve exactly (0.00 pp CAGR/DD, 0.000 Sharpe). |
| `time-of-day` | session-timing | 19.70% / 31.81% / 0.97 | 17.21% / 31.78% / 0.89 | 17.21% / 31.78% / 0.89 | — | +0.00 pp / +0.00 pp / +0.000 | verified-full | Frozen-code full rerun reproduces the published curve exactly (0.00 pp CAGR/DD, 0.000 Sharpe). |
| `vol-kelly-overlay` | event-recovery | 1.81% / 19.22% / 0.25 | 1.03% / 16.50% / 0.17 | 1.03% / 16.50% / 0.17 | — | +0.00 pp / +0.00 pp / +0.000 | verified-full | Frozen-code full rerun reproduces the published curve exactly (0.00 pp CAGR/DD, 0.000 Sharpe). |
| `volume-orderflow` | intraday-microstructure | 0.87% / 16.66% / 0.15 | 2.49% / 13.11% / 0.36 | 2.49% / 13.11% / 0.36 | — | +0.00 pp / +0.00 pp / +0.000 | verified-full | Frozen-code full rerun reproduces the published curve exactly (0.00 pp CAGR/DD, 0.000 Sharpe). |
| `winner-ensemble-blend` | other | 0.30% / 32.67% / 0.08 | 3.04% / 30.53% / 0.33 | 3.04% / 30.53% / 0.33 | — | +0.00 pp / +0.00 pp / +0.000 | verified-full | Frozen-code full rerun reproduces the published curve exactly (0.00 pp CAGR/DD, 0.000 Sharpe). |
| `daily-regime-minute-entry` | intraday-microstructure | -0.04% / 64.18% / 0.11 | 2.04% / 62.82% / 0.20 | 2.04% / 62.82% / 0.20 | 2.84% / 60.24% / 0.24 | +0.00 pp / +0.00 pp / +0.000 | stale | Published curve is the pre-tune freeze; the _before_tune rerun reproduces 2.04/62.82/0.20 exactly, but current code gives 2.84/60.24/0.24 (+0.80 pp CAGR). |
| `donchian-breakout` | trend-vol | -3.38% / 37.05% / -0.16 | -0.94% / 35.77% / 0.01 | -0.94% / 35.77% / 0.01 | 12.50% / 14.50% / 0.94 | +0.00 pp / +0.00 pp / +0.000 | stale | Published curve is the pre-tune freeze; the _before_tune rerun reproduces -0.94/35.77/0.01 exactly, but current code gives 12.50/14.50/0.94 (+13.44 pp CAGR). |
| `drawdown-regime` | event-recovery | -1.64% / 48.81% / -0.02 | -0.11% / 47.55% / 0.07 | -0.11% / 47.55% / 0.07 | 18.19% / 47.77% / 0.84 | +0.00 pp / +0.00 pp / +0.000 | stale | Published curve is the pre-tune freeze; the _before_tune rerun reproduces -0.11/47.55/0.07 exactly, but current code gives 18.19/47.77/0.84 (+18.30 pp CAGR). |
| `drawdown-stop-overlay` | short-reversal | -1.74% / 45.45% / 0.07 | -2.37% / 55.33% / 0.06 | -2.37% / 55.33% / 0.06 | -8.17% / 71.74% / -0.21 | +0.00 pp / +0.00 pp / +0.000 | stale | Published curve is the pre-tune freeze; the _before_tune rerun reproduces -2.37/55.33/0.06 exactly, but current code gives -8.17/71.74/-0.21 (-5.80 pp CAGR). |
| `dual-speed-regime` | intraday-microstructure | 5.38% / 38.02% / 0.36 | 5.15% / 36.93% / 0.35 | 5.15% / 36.93% / 0.35 | 25.17% / 44.79% / 0.96 | +0.00 pp / +0.00 pp / +0.000 | stale | Published curve reproduces only with the documented pre-tune variant overnight=False, idle="bil" (5.15/36.93/0.35); the _before_tune default gives 4.51 and current code gives 25.17/44.79/0.96. |
| `dynamic-leverage-throttle` | event-recovery | 2.65% / 9.16% / 0.69 | 2.38% / 15.30% / 0.54 | 2.38% / 15.30% / 0.54 | 4.49% / 17.66% / 0.73 | +0.00 pp / +0.00 pp / +0.000 | stale | Published curve is the pre-tune freeze; the _before_tune rerun reproduces 2.38/15.30/0.54 exactly, but current code gives 4.49/17.66/0.73 (+2.11 pp CAGR). |
| `ensemble-signals` | vol-crash | -5.21% / 76.04% / -0.02 | 1.34% / 75.91% / 0.20 | 1.34% / 75.91% / 0.20 | 0.35% / 75.91% / 0.17 | +0.00 pp / +0.00 pp / +0.000 | stale | Published curve is the pre-tune freeze; the _before_tune rerun reproduces 1.34/75.91/0.20 exactly, but current code gives 0.35/75.91/0.17 (-0.98 pp CAGR). |
| `gap-capitulation-reversal` | event-recovery | 4.18% / 12.49% / 0.58 | 4.64% / 10.63% / 0.82 | 4.64% / 10.63% / 0.82 | 8.90% / 8.34% / 1.05 | +0.00 pp / +0.00 pp / +0.000 | stale | Published curve is the pre-tune freeze; the _before_tune rerun reproduces 4.64/10.63/0.82 exactly, but current code gives 8.90/8.34/1.05 (+4.25 pp CAGR). |
| `ml-classifier` | ml-microstructure | 20.69% / 36.04% / 0.81 | 16.15% / 36.60% / 0.67 | 17.93% / 36.60% / 0.70 | 17.93% / 36.60% / 0.70 | +1.79 pp / +0.00 pp / +0.033 | stale | Published 2024-26 extension freezes the 2023-12 model; the clean monthly-refit rerun gives 17.93/36.60/0.70 vs published 16.15/36.60/0.67 (+1.79 pp CAGR). |
| `ratio-froth` | trend-vol | 61.56% / 39.11% / 1.47 | 62.21% / 36.65% / 1.43 | 62.21% / 36.65% / 1.43 | — | +0.00 pp / +0.00 pp / +0.000 | verified-full | Lead clean rerun in research/new/ratio-froth/holdout.json (no strategy.py/result.json in the revisit tree): dev 61.56/39.11/1.47, holdout 64.88%, full 62.21/36.65/1.43, matching the published full curve. |
| `vol-scaled-crash-stop` | vol-crash | 57.65% / 37.88% / 1.39 | 51.32% / 37.88% / 1.26 | 51.32% / 37.88% / 1.26 | — | +0.00 pp / +0.00 pp / +0.000 | curve-only | Own-main rerun reproduces the lead (dev 57.65/37.88/1.39, holdout 36.19/31.74/0.97, full 51.32/37.88/1.26) and cut tests are 0.0; but build_weights needs first/last/ATR and cannot be driven by the shared 3-array runner, so curve-only/needs-adapter. |

## How many can be made verified-full

- **16 of the 25 below-bar strategies are verified-full today** against their published curve: `event-risk-overlay`, `gap-fill-fade`, `intraday-mean-reversion`, `intraday-momentum`, `intraday-seasonality`, `letf-rebalance-flow`, `ml-crash-overlay-winner`, `opening-range-breakout`, `overnight-crash-filter`, `ratio-pairs`, `risk-parity-hrp`, `stop-reentry-recovery`, `time-of-day`, `vol-kelly-overlay`, `volume-orderflow`, `winner-ensemble-blend`.
- **8 of the 25 can be made verified-full by re-publishing the pre-tune freeze**: `daily-regime-minute-entry`, `donchian-breakout`, `drawdown-regime`, `drawdown-stop-overlay`, `dual-speed-regime`, `dynamic-leverage-throttle`, `ensemble-signals`, `gap-capitulation-reversal`. Their `_before_tune` code reproduces the published curve; their current code does not (differences in the table).
- **1 of the 25 can be made verified-full only by replacing the curve**: `ml-classifier`. The published 2024-26 extension freezes the 2023-12 model; the clean monthly-refit rerun is 17.93% full vs 16.15% published.
- **0 of the 25 are permanently unverifiable**: every below-bar name has runnable code and a reproducible freeze. The blocker for the nine stale names is a version/freeze decision, not missing code.

Strict reading: if "verified-full" means the **current** `strategy.py` must reproduce the published curve, then only **16/25** qualify and the **9 stale names cannot** be counted until their published curve is replaced or re-frozen.

## Above-bar legacy names

- **`ratio-froth` — verified-full (lead rerun).** Dev 61.56% / 39.11% / 1.47, holdout 64.88%, full 62.21% / 36.65% / 1.43. There is no `strategy.py` or `result.json` in the revisit tree; the lead added a frozen wrapper and holdout at `research/new/ratio-froth/`, and it agrees with the published curve.
- **`vol-scaled-crash-stop` — curve-only / needs-adapter.** The own `main()` rerun matches the lead exactly (dev 57.65% / 37.88% / 1.39, holdout 36.19% / 31.74% / 0.97, full 51.32% / 37.88% / 1.26), and the causal cut tests are exact (0.0 weight difference at 2020-03-12 11:07 and 2022-09-13 10:41) with 618 post-2023 weight changes. However, `build_weights(ts, opens, closes, first, last, atr, ...)` needs the session bounds and ATR series and cannot be driven by the shared 3-array runner; under the task rule it is reported as curve-only/needs-adapter rather than claiming shared-runner verification.

## Stale detail

- **`daily-regime-minute-entry`** — published 2.04% / 62.82% / 0.20; `_before_tune` rerun 2.04% / 62.82% / 0.20 (reproduces); current 2.84% / 60.24% / 0.24 (+0.80 pp CAGR). Published curve is the pre-tune freeze; the _before_tune rerun reproduces 2.04/62.82/0.20 exactly, but current code gives 2.84/60.24/0.24 (+0.80 pp CAGR).
- **`donchian-breakout`** — published -0.94% / 35.77% / 0.01; `_before_tune` rerun -0.94% / 35.77% / 0.01 (reproduces); current 12.50% / 14.50% / 0.94 (+13.44 pp CAGR). Published curve is the pre-tune freeze; the _before_tune rerun reproduces -0.94/35.77/0.01 exactly, but current code gives 12.50/14.50/0.94 (+13.44 pp CAGR).
- **`drawdown-regime`** — published -0.11% / 47.55% / 0.07; `_before_tune` rerun -0.11% / 47.55% / 0.07 (reproduces); current 18.19% / 47.77% / 0.84 (+18.30 pp CAGR). Published curve is the pre-tune freeze; the _before_tune rerun reproduces -0.11/47.55/0.07 exactly, but current code gives 18.19/47.77/0.84 (+18.30 pp CAGR).
- **`drawdown-stop-overlay`** — published -2.37% / 55.33% / 0.06; `_before_tune` rerun -2.37% / 55.33% / 0.06 (reproduces); current -8.17% / 71.74% / -0.21 (-5.80 pp CAGR). Published curve is the pre-tune freeze; the _before_tune rerun reproduces -2.37/55.33/0.06 exactly, but current code gives -8.17/71.74/-0.21 (-5.80 pp CAGR).
- **`dual-speed-regime`** — published 5.15% / 36.93% / 0.35; `_before_tune` rerun 5.15% / 36.93% / 0.35 (reproduces); current 25.17% / 44.79% / 0.96 (+20.02 pp CAGR). Published curve reproduces only with the documented pre-tune variant overnight=False, idle="bil" (5.15/36.93/0.35); the _before_tune default gives 4.51 and current code gives 25.17/44.79/0.96.
- **`dynamic-leverage-throttle`** — published 2.38% / 15.30% / 0.54; `_before_tune` rerun 2.38% / 15.30% / 0.54 (reproduces); current 4.49% / 17.66% / 0.73 (+2.11 pp CAGR). Published curve is the pre-tune freeze; the _before_tune rerun reproduces 2.38/15.30/0.54 exactly, but current code gives 4.49/17.66/0.73 (+2.11 pp CAGR).
- **`ensemble-signals`** — published 1.34% / 75.91% / 0.20; `_before_tune` rerun 1.34% / 75.91% / 0.20 (reproduces); current 0.35% / 75.91% / 0.17 (-0.98 pp CAGR). Published curve is the pre-tune freeze; the _before_tune rerun reproduces 1.34/75.91/0.20 exactly, but current code gives 0.35/75.91/0.17 (-0.98 pp CAGR).
- **`gap-capitulation-reversal`** — published 4.64% / 10.63% / 0.82; `_before_tune` rerun 4.64% / 10.63% / 0.82 (reproduces); current 8.90% / 8.34% / 1.05 (+4.25 pp CAGR). Published curve is the pre-tune freeze; the _before_tune rerun reproduces 4.64/10.63/0.82 exactly, but current code gives 8.90/8.34/1.05 (+4.25 pp CAGR).
- **`ml-classifier`** — published 16.15% / 36.60% / 0.67; `_before_tune` rerun 17.93% / 36.60% / 0.70 (does not reproduce; corrected path); current 17.93% / 36.60% / 0.70 (+1.79 pp CAGR). Published 2024-26 extension freezes the 2023-12 model; the clean monthly-refit rerun gives 17.93/36.60/0.70 vs published 16.15/36.60/0.67 (+1.79 pp CAGR).

## Method and caveats

- Each strategy was copied to `C:\Users\27175\AppData\Local\Temp\opencode\oldverify\root`; only date literals were extended in the sandbox copy. The real `strategy.py`, `result.json`, `curves_full/` and website data were not touched.
- Reruns use `research/bt.py` (compiled simcore where available), next-open fills, 2% band, 1 bp, long-only, weights ≥ 0, sum ≤ 1. Daily-close CAGR/DD/Sharpe are computed from the simulated 1-minute equity path, matching the published curve convention.
- Stale reruns use `_before_tune/strategy.py` + `_before_tune/result.json`. Current reruns use `strategy.py` + `result.json`. The dev column is the 1 bp `result.json` headline of the selected freeze; the table's rerun full is daily-close.
- `dual-speed-regime` is the one stale curve whose `_before_tune` default does **not** reproduce the published curve. The published curve is the documented pre-tune variant `overnight=False, idle="bil"` (5.15% full), which we ran separately; the `_before_tune` default gives 4.51% and current code 25.17%.
- `ml-classifier` starts 2017-01-03, not 2016-01-04; its published and rerun full metrics are both over 2017-2026.
- `ratio-froth` has no code in the revisit tree; its verification is the lead's clean rerun in `research/new/ratio-froth/holdout.json` plus the published curve. `vol-scaled-crash-stop` is adapter-dependent as described above.

