# Strategy Research Library

> **Final update:** the machine-readable `LIBRARY.json` now contains 65 records,
> including 20 additional new-family strategies added on 2026-11-28. The
> website uses 23 verified above-TQQQ family winners; the two legacy above-bar
> names are retained as research records but are not family winners. See
> `FAMILY_POLICY.md`, `NEW_FAMILIES.md` and `RATIO_FROTH_BEATER.md` for the
> final selection.

**Current inventory:** **65 records**, **37 above the TQQQ bar**, **23 family
winners**, and **65 `verified-full`**.  Full-window bar: TQQQ **37.54% CAGR /
81.68% max DD / 0.82 Sharpe** on 2016-01-04 to 2026-10-23 daily-close marks.

**Flat-line removal:** 13 non-winners with full-window CAGR below **5%** were
removed from the visible library on 2026-11-28; see `FLAT_REMOVAL.md`.

**Repair follow-up:** the eight names flagged in `HEALTH_AUDIT.md` are resolved
in `REPAIRS.md`.  Four have full-holdout re-specifications (all below the bar),
three are retired (`vol-kelly-overlay`, `volume-orderflow`,
`drawdown-stop-overlay`), and one remains development-only
(`gap-fill-fade`).  `drawdown-recovery-v2` was removed from the visible
library because its 2016-2026 record has only 35 fills; no other published
curve, metric or winner changed.

The family tables below preserve the **pre-final audit snapshot** and are kept
for provenance; `LIBRARY.json` is authoritative for current status, metrics and
repair fields.  `dev` there is the frozen 2016-2023 result (1 bp headline);
`full` is the 2016-2026 daily-close result.

## trend-vol (8)

_QQQ trend (EMA/Donchian/52-week high/momentum, plus the legacy ratio overlay) decides when to own TQQQ; volatility targeting sizes the sleeve._

| Strategy | slug | Dev CAGR / DD / Sharpe | Full CAGR / DD / Sharpe | Above TQQQ | Status | Winner |
|---|---|---|---|:--:|---|:--:|
| Ratio froth | `ratio-froth` | — | 62.21% / 36.65% / 1.43 | **yes** | failed | **yes** |
| Fast trend + vol target | `fast-trend-vol` | 51.51% / 42.54% / 1.20 | 44.61% / 40.26% / 1.06 | **yes** | verified-full |  |
| EMA ribbon trend | `ema-ribbon-trend` | 46.77% / 44.13% / 1.09 | 40.09% / 46.58% / 0.97 | **yes** | verified-full |  |
| 52-week-high trend | `tqqq-52week-high` | 43.30% / 37.42% / 1.18 | 38.64% / 39.43% / 1.04 | **yes** | verified-full |  |
| Momentum + crash brake | `momentum-crash-filter` | 42.70% / 47.57% / 1.01 | 35.61% / 50.06% / 0.88 | no | failed |  |
| Donchian two-sleeve trend | `donchian-trend` | 49.14% / 43.95% / 1.10 | 35.13% / 54.27% / 0.88 | no | failed |  |
| Donchian alignment ladder | `donchian-breakout` | 13.40% / 15.02% / 1.00 | -0.94% / 35.77% / 0.01 | no | failed |  |
| SPY-confirmed trend | `spy-confirmed-trend` | 50.36% / 43.27% / 1.20 | — | no (dev yes) | dev-only |  |

## vol-crash (10)

_Volatility level, term structure, vol-of-vol, an ML path-risk state or a crash composite decides when 3x exposure is being taxed; de-risk into vol expansion._

| Strategy | slug | Dev CAGR / DD / Sharpe | Full CAGR / DD / Sharpe | Above TQQQ | Status | Winner |
|---|---|---|---|:--:|---|:--:|
| Vol-scaled crash system | `vol-scaled-crash-stop` | 57.84% / 39.29% / 1.42 | 51.32% / 37.88% / 1.26 | **yes** | failed | **yes** |
| Volatility term structure | `vol-term-structure` | 51.57% / 37.90% / 1.37 | 42.48% / 35.80% / 1.15 | **yes** | verified-full |  |
| Vol-of-vol risk timing | `vol-of-vol-timing` | 45.35% / 53.55% / 1.20 | 42.17% / 51.64% / 1.08 | **yes** | verified-full |  |
| Crash early-warning | `crash-early-warning` | 40.38% / 54.86% / 0.97 | 42.06% / 52.96% / 0.99 | **yes** | verified-full |  |
| Walk-forward ML regime | `ml-regime-v2` | 59.61% / 42.89% / 1.28 | 41.74% / 35.98% / 1.10 | **yes** | verified-full |  |
| Always-long vol target | `always-long-vol-target` | 39.20% / 58.94% / 0.99 | 37.25% / 57.48% / 0.94 | no | failed |  |
| Close-momentum weakness exit | `intraday-close-momentum` | 46.21% / 53.87% / 1.08 | 31.21% / 52.06% / 0.89 | no | failed |  |
| Volatility contraction recovery | `ensemble-signals` | -6.34% / 76.04% / -0.05 | 1.34% / 75.91% / 0.20 | no | failed |  |
| Fast-drawdown brake | `tqqq-fast-drawdown-stop` | 52.83% / 45.90% / 1.19 | — | no (dev yes) | dev-only |  |
| Aggressive vol target | `tqqq-vol-target-aggressive` | 40.16% / 57.77% / 1.07 | — | no (dev yes) | dev-only |  |

## relative (5)

_A cross-asset or TQQQ/QQQ ratio/relative-momentum gate decides how much leverage is paid for._

| Strategy | slug | Dev CAGR / DD / Sharpe | Full CAGR / DD / Sharpe | Above TQQQ | Status | Winner |
|---|---|---|---|:--:|---|:--:|
| TQQQ/QQQ relative value | `relative-value-tqqq` | 43.65% / 54.65% / 1.01 | 40.50% / 51.54% / 0.94 | **yes** | verified-full | **yes** |
| QQQ/SPY relative ladder | `qqq-spy-relative` | 44.36% / 55.03% / 1.06 | 38.98% / 53.64% / 0.96 | **yes** | verified-full |  |
| Cross-asset dual momentum | `cross-asset-momentum` | 40.00% / 42.89% / 1.08 | 30.58% / 40.69% / 0.89 | no | failed |  |
| Ratio-cycle standalone | `ratio-pairs` | 18.96% / 34.59% / 1.11 | 20.42% / 33.94% / 1.13 | no | verified-full |  |
| Dual-momentum TQQQ | `dual-momentum-tqqq` | 41.15% / 57.95% / 0.98 | — | no (dev yes) | dev-only |  |

## event-recovery (5)

_A deep drawdown or capitulation event opens a time-limited recovery window; cash between episodes._

| Strategy | slug | Dev CAGR / DD / Sharpe | Full CAGR / DD / Sharpe | Above TQQQ | Status | Winner |
|---|---|---|---|:--:|---|:--:|
| Quiet capitulation reversal | `capitulation-reversal-v2` | 39.75% / 26.44% / 1.46 | 32.21% / 20.86% / 1.30 | no | failed |  |
| Quiet capitulation | `gap-capitulation-reversal` | 8.30% / 10.26% / 0.88 | 4.64% / 10.63% / 0.82 | no | verified-full |  |
| Volatility-shock recovery | `dynamic-leverage-throttle` | 5.24% / 9.16% / 1.06 | 2.38% / 15.30% / 0.54 | no | failed |  |
| Vol-spike reflation | `vol-kelly-overlay` | 1.81% / 19.22% / 0.25 | 1.03% / 16.50% / 0.17 | no | failed |  |
| Deep drawdown recovery | `drawdown-regime` | 17.20% / 49.02% / 0.78 | -0.11% / 47.55% / 0.07 | no | failed |  |

## calendar (5)

_A date known in advance (month boundary, FOMC, OpEx, holiday) decides the holding window._

| Strategy | slug | Dev CAGR / DD / Sharpe | Full CAGR / DD / Sharpe | Above TQQQ | Status | Winner |
|---|---|---|---|:--:|---|:--:|
| FOMC intermeeting drift | `macro-event-tqqq` | 51.06% / 48.83% / 1.17 | 37.09% / 44.63% / 1.02 | no | failed |  |
| Turn-of-month | `turn-of-month` | 41.41% / 49.21% / 0.98 | 33.62% / 64.07% / 0.85 | no | failed |  |
| OpEx cycle | `event-risk-overlay` | 26.94% / 39.04% / 1.08 | 22.20% / 36.97% / 0.96 | no | failed |  |
| FOMC + post-OpEx calendar | `fomc-opex-window` | 58.26% / 42.60% / 1.36 | — | no (dev yes) | dev-only |  |
| Pre-holiday drift | `pre-holiday` | 4.23% / 31.22% / 0.34 | — | no (dev no) | dev-only |  |

## session-timing (5)

_The overnight vs intraday session block is the unit; the clock, not the price trend, is the signal._

| Strategy | slug | Dev CAGR / DD / Sharpe | Full CAGR / DD / Sharpe | Above TQQQ | Status | Winner |
|---|---|---|---|:--:|---|:--:|
| Overnight drift filter | `overnight-drift-filter` | 44.29% / 59.71% / 1.12 | 37.07% / 58.35% / 0.97 | no | failed |  |
| Closing-pressure overnight carry | `time-of-day` | 19.70% / 31.81% / 0.97 | 17.21% / 31.78% / 0.89 | no | failed |  |
| Time-of-day leverage ladder | `intraday-momentum` | 13.51% / 63.98% / 0.57 | 14.65% / 63.55% / 0.61 | no | failed |  |
| Night continuation / day reversal | `overnight-crash-filter` | 10.37% / 27.62% / 0.76 | 11.34% / 26.98% / 0.81 | no | failed |  |
| Overnight + intraday trend | `overnight-intraday-trend` | 64.63% / 35.66% / 1.42 | — | no (dev yes) | dev-only |  |

## short-reversal (3)

_A short-horizon price overreaction (intraday flush, gap, failed breakdown) mean-reverts over 1-5 sessions._

| Strategy | slug | Dev CAGR / DD / Sharpe | Full CAGR / DD / Sharpe | Above TQQQ | Status | Winner |
|---|---|---|---|:--:|---|:--:|
| Post-capitulation reversal | `intraday-mean-reversion` | 11.31% / 31.47% / 0.58 | 12.41% / 21.48% / 0.71 | no | verified-full |  |
| Failed gap-up fade | `gap-fill-fade` | 1.43% / 0.48% / 0.94 | 2.21% / 0.38% / 6.53 | no | failed |  |
| Failed-breakdown spring | `drawdown-stop-overlay` | -9.25% / 63.09% / -0.27 | -2.37% / 55.33% / 0.06 | no | failed |  |

## intraday-microstructure (5)

_Intraday bar, range and volume structure (ORB, 60-minute trend, order flow) with flat overnight._

| Strategy | slug | Dev CAGR / DD / Sharpe | Full CAGR / DD / Sharpe | Above TQQQ | Status | Winner |
|---|---|---|---|:--:|---|:--:|
| Intraday 60-minute trend | `dual-speed-regime` | 28.76% / 45.45% / 1.07 | 5.15% / 36.93% / 0.35 | no | failed |  |
| Participation exhaustion | `volume-orderflow` | 0.87% / 16.66% / 0.15 | 2.49% / 13.11% / 0.36 | no | failed |  |
| Crash-continuation short | `daily-regime-minute-entry` | 0.91% / 61.74% / 0.15 | 2.04% / 62.82% / 0.20 | no | failed |  |
| Opening-range failed-breakdown reclaim | `opening-range-breakout` | -2.10% / 17.22% / -0.53 | -1.32% / 19.99% / -0.33 | no | failed |  |
| Opening-range breakout | `orb-tqqq-volume` | 17.89% / 21.38% / 1.02 | — | no (dev no) | dev-only |  |

## rebalance-flow (3)

_Mechanical leveraged-ETF / closing-flow pressure creates a temporary overshoot that reverses._

| Strategy | slug | Dev CAGR / DD / Sharpe | Full CAGR / DD / Sharpe | Above TQQQ | Status | Winner |
|---|---|---|---|:--:|---|:--:|
| Close-flow exhaustion | `intraday-seasonality` | 21.84% / 43.75% / 0.75 | 26.41% / 39.24% / 0.96 | no | verified-full |  |
| Relative Nasdaq flow dip | `letf-rebalance-flow` | 13.20% / 41.80% / 0.52 | 7.80% / 42.98% / 0.40 | no | failed |  |
| LETF overshoot recovery | `stop-reentry-recovery` | 1.26% / 1.81% / 0.80 | 2.05% / 1.25% / 5.09 | no | failed |  |

## ml-microstructure (2)

_A walk-forward ML model on intraday/short-horizon price-volume features replaces a hand-coded threshold._

| Strategy | slug | Dev CAGR / DD / Sharpe | Full CAGR / DD / Sharpe | Above TQQQ | Status | Winner |
|---|---|---|---|:--:|---|:--:|
| Unsupervised regime allocator | `ml-classifier` | 20.69% / 36.04% / 0.81 | 16.15% / 36.60% / 0.67 | no | failed |  |
| Leverage-decay timing | `ml-crash-overlay-winner` | 15.80% / 22.42% / 0.81 | 15.07% / 23.33% / 0.76 | no | failed |  |

## other (2)

_Allocation or ensemble wrappers that do not isolate a single market signal._

| Strategy | slug | Dev CAGR / DD / Sharpe | Full CAGR / DD / Sharpe | Above TQQQ | Status | Winner |
|---|---|---|---|:--:|---|:--:|
| Volatility-state risk parity | `risk-parity-hrp` | 5.70% / 18.46% / 0.65 | 6.49% / 17.89% / 0.69 | no | failed |  |
| Two-stream risk parity | `winner-ensemble-blend` | 0.30% / 32.67% / 0.08 | 3.04% / 30.53% / 0.33 | no | failed |  |

## Duplicate above-TQQQ families

Rule: one above-TQQQ keeper per family, chosen by highest full CAGR, then Sharpe, then lowest DD. Three families have more than one candidate. `FAMILY_POLICY.md` names only trend-vol and vol-crash; `relative` is a third duplicate because both of its candidates clear the bar.

### trend-vol - 4 candidates

| Candidate | Full CAGR | Full DD | Full Sharpe | Status |
|---|---:|---:|---:|---|
| `ratio-froth` - Ratio froth | 62.21% | 36.65% | 1.43 | failed |
| `fast-trend-vol` - Fast trend + vol target | 44.61% | 40.26% | 1.06 | verified-full |
| `ema-ribbon-trend` - EMA ribbon trend | 40.09% | 46.58% | 0.97 | verified-full |
| `tqqq-52week-high` - 52-week-high trend | 38.64% | 39.43% | 1.04 | verified-full |

**Keeper: `ratio-froth` (Ratio froth).** Highest full CAGR at 62.21% with 36.65% DD and 1.43 Sharpe. It is the legacy 165-day base + 4 percent stop + ratio overlay, not a standalone trend strategy, and has no frozen holdout; the verified alternative is `fast-trend-vol` (44.61% CAGR, 40.26% DD, 1.06 Sharpe).

### vol-crash - 5 candidates

| Candidate | Full CAGR | Full DD | Full Sharpe | Status |
|---|---:|---:|---:|---|
| `vol-scaled-crash-stop` - Vol-scaled crash system | 51.32% | 37.88% | 1.26 | failed |
| `vol-term-structure` - Volatility term structure | 42.48% | 35.80% | 1.15 | verified-full |
| `vol-of-vol-timing` - Vol-of-vol risk timing | 42.17% | 51.64% | 1.08 | verified-full |
| `crash-early-warning` - Crash early-warning | 42.06% | 52.96% | 0.99 | verified-full |
| `ml-regime-v2` - Walk-forward ML regime | 41.74% | 35.98% | 1.10 | verified-full |

**Keeper: `vol-scaled-crash-stop` (Vol-scaled crash system).** Highest full CAGR at 51.32% with 37.88% DD and 1.26 Sharpe. It is a legacy always-long TQQQ overlay (72 percent of the time in TQQQ, 0.755 daily correlation) with no frozen holdout; if the site admits only holdout-verified names, the verified alternative is `vol-term-structure` (42.48% CAGR, 35.80% DD, 1.15 Sharpe).

### relative - 2 candidates

| Candidate | Full CAGR | Full DD | Full Sharpe | Status |
|---|---:|---:|---:|---|
| `relative-value-tqqq` - TQQQ/QQQ relative value | 40.50% | 51.54% | 0.94 | verified-full |
| `qqq-spy-relative` - QQQ/SPY relative ladder | 38.98% | 53.64% | 0.96 | verified-full |

**Keeper: `relative-value-tqqq` (TQQQ/QQQ relative value).** Highest full CAGR at 40.50% with 51.54% DD and 0.94 Sharpe. Both candidates are verified-full; `relative-value-tqqq` wins on CAGR and drawdown, while `qqq-spy-relative` has the higher Sharpe and is the better risk-adjusted alternative.

`event-recovery` now has no above-TQQQ winner: `drawdown-recovery-v2` was removed from the visible library because its 2016-2026 record has only 35 fills. `ml-microstructure` has no above-TQQQ member, which is exactly why it is one of the six new-family targets. No other family has an above-TQQQ strategy.

## Non-performers added

42 strategies are below the TQQQ bar and all remain visible in the library. The 17 new-programme non-performers are listed first; the 25 original-27 entries follow. `dev-only` rows have no full-window result.

### New programme (17)

| Family | Strategy | Dev CAGR / DD / Sharpe | Full CAGR / DD / Sharpe | Status |
|---|---|---|---|---|
| trend-vol | `donchian-trend` Donchian two-sleeve trend | 49.14% / 43.95% / 1.10 | 35.13% / 54.27% / 0.88 | failed |
| trend-vol | `momentum-crash-filter` Momentum + crash brake | 42.70% / 47.57% / 1.01 | 35.61% / 50.06% / 0.88 | failed |
| trend-vol | `spy-confirmed-trend` SPY-confirmed trend | 50.36% / 43.27% / 1.20 | — | dev-only |
| vol-crash | `always-long-vol-target` Always-long vol target | 39.20% / 58.94% / 0.99 | 37.25% / 57.48% / 0.94 | failed |
| vol-crash | `intraday-close-momentum` Close-momentum weakness exit | 46.21% / 53.87% / 1.08 | 31.21% / 52.06% / 0.89 | failed |
| vol-crash | `tqqq-fast-drawdown-stop` Fast-drawdown brake | 52.83% / 45.90% / 1.19 | — | dev-only |
| vol-crash | `tqqq-vol-target-aggressive` Aggressive vol target | 40.16% / 57.77% / 1.07 | — | dev-only |
| relative | `cross-asset-momentum` Cross-asset dual momentum | 40.00% / 42.89% / 1.08 | 30.58% / 40.69% / 0.89 | failed |
| relative | `dual-momentum-tqqq` Dual-momentum TQQQ | 41.15% / 57.95% / 0.98 | — | dev-only |
| event-recovery | `capitulation-reversal-v2` Quiet capitulation reversal | 39.75% / 26.44% / 1.46 | 32.21% / 20.86% / 1.30 | failed |
| calendar | `fomc-opex-window` FOMC + post-OpEx calendar | 58.26% / 42.60% / 1.36 | — | dev-only |
| calendar | `macro-event-tqqq` FOMC intermeeting drift | 51.06% / 48.83% / 1.17 | 37.09% / 44.63% / 1.02 | failed |
| calendar | `pre-holiday` Pre-holiday drift | 4.23% / 31.22% / 0.34 | — | dev-only |
| calendar | `turn-of-month` Turn-of-month | 41.41% / 49.21% / 0.98 | 33.62% / 64.07% / 0.85 | failed |
| session-timing | `overnight-drift-filter` Overnight drift filter | 44.29% / 59.71% / 1.12 | 37.07% / 58.35% / 0.97 | failed |
| session-timing | `overnight-intraday-trend` Overnight + intraday trend | 64.63% / 35.66% / 1.42 | — | dev-only |
| intraday-microstructure | `orb-tqqq-volume` Opening-range breakout | 17.89% / 21.38% / 1.02 | — | dev-only |

### Original 27 (25)

| Family | Strategy | Dev CAGR / DD / Sharpe | Full CAGR / DD / Sharpe | Status |
|---|---|---|---|---|
| trend-vol | `donchian-breakout` Donchian alignment ladder | 13.40% / 15.02% / 1.00 | -0.94% / 35.77% / 0.01 | failed |
| vol-crash | `ensemble-signals` Volatility contraction recovery | -6.34% / 76.04% / -0.05 | 1.34% / 75.91% / 0.20 | failed |
| relative | `ratio-pairs` Ratio-cycle standalone | 18.96% / 34.59% / 1.11 | 20.42% / 33.94% / 1.13 | verified-full |
| event-recovery | `drawdown-regime` Deep drawdown recovery | 17.20% / 49.02% / 0.78 | -0.11% / 47.55% / 0.07 | failed |
| event-recovery | `dynamic-leverage-throttle` Volatility-shock recovery | 5.24% / 9.16% / 1.06 | 2.38% / 15.30% / 0.54 | failed |
| event-recovery | `gap-capitulation-reversal` Quiet capitulation | 8.30% / 10.26% / 0.88 | 4.64% / 10.63% / 0.82 | verified-full |
| event-recovery | `vol-kelly-overlay` Vol-spike reflation | 1.81% / 19.22% / 0.25 | 1.03% / 16.50% / 0.17 | failed |
| calendar | `event-risk-overlay` OpEx cycle | 26.94% / 39.04% / 1.08 | 22.20% / 36.97% / 0.96 | failed |
| session-timing | `intraday-momentum` Time-of-day leverage ladder | 13.51% / 63.98% / 0.57 | 14.65% / 63.55% / 0.61 | failed |
| session-timing | `overnight-crash-filter` Night continuation / day reversal | 10.37% / 27.62% / 0.76 | 11.34% / 26.98% / 0.81 | failed |
| session-timing | `time-of-day` Closing-pressure overnight carry | 19.70% / 31.81% / 0.97 | 17.21% / 31.78% / 0.89 | failed |
| short-reversal | `drawdown-stop-overlay` Failed-breakdown spring | -9.25% / 63.09% / -0.27 | -2.37% / 55.33% / 0.06 | failed |
| short-reversal | `gap-fill-fade` Failed gap-up fade | 1.43% / 0.48% / 0.94 | 2.21% / 0.38% / 6.53 | failed |
| short-reversal | `intraday-mean-reversion` Post-capitulation reversal | 11.31% / 31.47% / 0.58 | 12.41% / 21.48% / 0.71 | verified-full |
| intraday-microstructure | `daily-regime-minute-entry` Crash-continuation short | 0.91% / 61.74% / 0.15 | 2.04% / 62.82% / 0.20 | failed |
| intraday-microstructure | `dual-speed-regime` Intraday 60-minute trend | 28.76% / 45.45% / 1.07 | 5.15% / 36.93% / 0.35 | failed |
| intraday-microstructure | `opening-range-breakout` Opening-range failed-breakdown reclaim | -2.10% / 17.22% / -0.53 | -1.32% / 19.99% / -0.33 | failed |
| intraday-microstructure | `volume-orderflow` Participation exhaustion | 0.87% / 16.66% / 0.15 | 2.49% / 13.11% / 0.36 | failed |
| rebalance-flow | `intraday-seasonality` Close-flow exhaustion | 21.84% / 43.75% / 0.75 | 26.41% / 39.24% / 0.96 | verified-full |
| rebalance-flow | `letf-rebalance-flow` Relative Nasdaq flow dip | 13.20% / 41.80% / 0.52 | 7.80% / 42.98% / 0.40 | failed |
| rebalance-flow | `stop-reentry-recovery` LETF overshoot recovery | 1.26% / 1.81% / 0.80 | 2.05% / 1.25% / 5.09 | failed |
| ml-microstructure | `ml-classifier` Unsupervised regime allocator | 20.69% / 36.04% / 0.81 | 16.15% / 36.60% / 0.67 | failed |
| ml-microstructure | `ml-crash-overlay-winner` Leverage-decay timing | 15.80% / 22.42% / 0.81 | 15.07% / 23.33% / 0.76 | failed |
| other | `risk-parity-hrp` Volatility-state risk parity | 5.70% / 18.46% / 0.65 | 6.49% / 17.89% / 0.69 | failed |
| other | `winner-ensemble-blend` Two-stream risk parity | 0.30% / 32.67% / 0.08 | 3.04% / 30.53% / 0.33 | failed |

## Family tree map

Each family is defined by the *first* thing that changes the position. If two strategies share a signal but differ in sizing, they stay in the same family.

| Family | Core signal | What it is not | Representative strategies |
|---|---|---|---|
| **trend-vol** | Slow/fast price trend (EMA stack, Donchian channel, 52-week-high proximity, momentum vote); vol target sizes the TQQQ sleeve. | Not a volatility-state or crash model: the trend decides *whether*, vol only decides *how much*. | `ratio-froth`, `fast-trend-vol`, `ema-ribbon-trend`, `tqqq-52week-high`, `donchian-trend` |
| **vol-crash** | Volatility level, term-structure slope, vol-of-vol, an ML path-risk state or a drawdown/gap early-warning composite; de-risk when vol is expanding. | Not a price-trend gate and not a post-crash recovery entry: the signal is the risk state itself. | `vol-term-structure`, `vol-of-vol-timing`, `crash-early-warning`, `ml-regime-v2`, `tqqq-fast-drawdown-stop` |
| **relative** | Cross-asset or TQQQ/QQQ relative strength/ratio momentum; leverage ladder 3x/2x/1x/0x. | Not an absolute trend model: the *relative* leg is the distinctive input. | `relative-value-tqqq`, `qqq-spy-relative`, `ratio-pairs`, `dual-momentum-tqqq` |
| **event-recovery** | A deep drawdown or capitulation event opens a recovery window; enter on stabilisation and hold for the rebound. | Not a permanent trend follower: cash between episodes and the event is the gate. | `drawdown-regime`, `capitulation-reversal-v2`, `dynamic-leverage-throttle` |
| **calendar** | A date known in advance: month boundary, FOMC decision, OpEx Friday, pre-holiday session. | Not a price signal: the calendar decides the window and BIL fills the rest. | `turn-of-month`, `macro-event-tqqq`, `fomc-opex-window`, `pre-holiday`, `event-risk-overlay` |
| **session-timing** | Which session block is held: overnight (close-to-open), first hour, or a close-anchored 24-hour position. | Not a date event and not a trend: the clock/clientèle is the signal. | `time-of-day`, `overnight-drift-filter`, `overnight-intraday-trend`, `overnight-crash-filter`, `intraday-momentum` |
| **short-reversal** | A short-horizon price overreaction (intraday flush, small gap, failed breakdown) that mean-reverts over 1-5 sessions. | Not a flow model: no leveraged-ETF relative-overshoot condition and no deep-drawdown regime. | `intraday-mean-reversion`, `gap-fill-fade`, `drawdown-stop-overlay` |
| **intraday-microstructure** | Intraday bar/range/volume structure: opening-range interaction, 60-minute trend, participation/order flow; flat overnight. | Not a daily trend or a calendar effect: the signal exists only inside the session. | `orb-tqqq-volume`, `opening-range-breakout`, `volume-orderflow`, `dual-speed-regime`, `daily-regime-minute-entry` |
| **rebalance-flow** | Mechanical leveraged-ETF/closing-flow pressure: TQQQ underperforms 3x QQQ, or a down close forces LETF selling. | Not generic mean reversion: the trigger is the mechanical flow/overshoot, not the price decline itself. | `letf-rebalance-flow`, `stop-reentry-recovery`, `intraday-seasonality` |
| **ml-microstructure** | A walk-forward ML model (logistic or k-means) on intraday/short-horizon price-volume features; the fitted model output is the signal. | Not a hand-coded vol or trend rule: the distinguishing input is the fitted classifier, not a threshold. | `ml-classifier`, `ml-crash-overlay-winner` |
| **other** | Allocation/ensemble wrappers with no single market-timing signal. | Not a standalone directional strategy. | `risk-parity-hrp`, `winner-ensemble-blend` |

### Why the six new families are distinct

The four legacy families answer "is the price trend up / is vol about to hurt / is leverage relatively cheap / has a crash ended". The six new families each add a different *causal clock*:

- **calendar** - the clock is the exchange/central-bank calendar; the signal is known days ahead and contains no price information.
- **session-timing** - the clock is the trading session; the question is *which block* (overnight, first hour, close) pays, not *whether* the market is trending.
- **short-reversal** - the clock is 1-5 sessions after a price overreaction; there is no flow or volume condition, so it is not `rebalance-flow`.
- **intraday-microstructure** - the signal exists only in intraday bars and range/volume structure; it is flat overnight and does not use a daily trend or a calendar date.
- **rebalance-flow** - the trigger is a *mechanical* leveraged-ETF/closing flow (TQQQ vs 3x QQQ or LETF selling into the close), which is why it is separate from generic short-reversal.
- **ml-microstructure** - the signal is a fitted model on intraday/short-horizon price-volume features; daily vol-state ML (`ml-regime-v2`) stays in `vol-crash`.

A strategy is assigned to the family of its **entry gate**, not its exit or sizing. That is why, for example, `fast-trend-vol` (trend gate + vol sizing + stop) sits in `trend-vol`, while `tqqq-fast-drawdown-stop` (default long, no trend gate) sits in `vol-crash`.

## Data and provenance caveats

- **Original-27 full curves are a mix of pre-tune and post-tune code.** `research/revisit/audit/curve_integrity.md` finds 18 valid curves, 8 stale curves, and 1 wrong 2024-2026 extension (`ml-classifier`). The metrics above use the published `all.json` curve as instructed, so the eight stale names (`daily-regime-minute-entry`, `donchian-breakout`, `drawdown-regime`, `drawdown-stop-overlay`, `dual-speed-regime`, `gap-capitulation-reversal`, `dynamic-leverage-throttle`, `ensemble-signals`) do not reconcile with their post-tune `result.json` dev numbers.
- **Old dev vs full can disagree for a second reason.** The `dev` column is the current `result.json`; the `full` column is the published curve. For the eight stale names the curve is the pre-tune freeze and `result.json` is the post-tune rerun.
- **`vol-scaled-crash-stop`** originally had a `result.json` dev block that was actually the full 2016-2026 run. The current file reports the true dev 57.84%; this catalog uses that value and the published full curve 51.32%.
- **`ratio-froth`** has no revisit `result.json` or `report.md`; its full metrics come from `all.json` and its provenance is `web/public/data/research/ratio-froth.json`. It is a legacy 165-day base + overlay, not a standalone strategy.
- **New-programme full metrics** are daily-close (`holdout.json -> windows.full.daily`), not the 1 bp intraday headline. That is why a few values differ by a few basis points from `PASSERS.md` (e.g. `tqqq-52week-high` DD 39.43% daily vs 40.59% 1 bp).
- **`dev_above_tqqq`** is only populated for the eight dev-only strategies. It applies the same 37.54% / 81.68% thresholds to the 2016-2023 development slice, and `above_tqqq` is forced false because there is no full-window result.

## Files

- `research/new/LIBRARY.json` - machine-readable catalog (54 records).
- `research/new/LIBRARY.md` - this audit.
- `research/new/PASSERS.md`, `AUDIT.md`, `VERIFICATION.md`, `META.json` - verification context.
- `research/revisit/audit/curve_integrity.md` - original-27 curve provenance.

