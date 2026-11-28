# Repairs of the eight flagged strategies

**Scope.** The eight names flagged by `HEALTH_AUDIT.md` were diagnosed and
rebuilt in `research/new/<slug>-v2/`.  This is a research follow-up, not a
promotion: no v2 repair clears the full-window TQQQ bar (37.54% CAGR /
81.68% max DD), so none is a family winner or a replacement for the published
37-strategy library.  Four have full-holdout re-specifications, three are
retired (`vol-kelly-overlay`, `volume-orderflow`, `drawdown-stop-overlay`),
and one remains development-only (`gap-fill-fade`).  The frozen v1 curves and
metrics remain the historical records in `LIBRARY.json` and on the website;
`LIBRARY.json` now carries a `repair_status`, `repair_source` and, where a
full holdout exists, `repair_full` block for each of the eight.

**Full-window numbers below are daily-close marks**, matching the website
comparison.  Development numbers are 1 bp where stated.  TQQQ full benchmark:
**37.54% CAGR / 81.68% DD / 0.82 Sharpe**.

| Original | Family | Repair | v2 full CAGR / DD / Sharpe | v2 status |
|---|---|---|---:|---|
| `dynamic-leverage-throttle` | event-recovery | Arm on shock + drawdown, trigger on the first decay inside 15 sessions | **7.07% / 17.16% / 0.78** | full holdout; not promoted |
| `drawdown-regime` | event-recovery | Arm at -10% (was -20%), 20-session confirmed turn, 60-session hold, faster re-arm | **20.51% / 38.34% / 0.87** | full holdout; not promoted |
| `gap-capitulation-reversal` | event-recovery | -1.5% close threshold (was -2.0%), 5-session hold (was 3), 35% vol cap (was 30%) | **17.05% / 25.54% / 0.86** | full holdout; not promoted |
| `stop-reentry-recovery` | rebalance-flow | Replace the 1 pp relative-overshoot trigger with a -5% / z <= -2.0 own-volatility shock, one-session hold | **16.26% / 8.33% / 0.99** | full holdout; not promoted |
| `vol-kelly-overlay` | event-recovery | Count repair reaches 28 entries but the edge stays insignificant (best grid p = 0.223) | — | **retired** |
| `volume-orderflow` | intraday-microstructure | Relaxed conjunction reaches 44 events, but volume is not additive and the close-location sign is backwards | — | **retired** |
| `drawdown-stop-overlay` | short-reversal | Primary 1-day trend/vol variant; static mix at the same exposure is better | 3.36% / 23.37% / 0.54 (dev) | **retired (overlay-only)** |
| `gap-fill-fade` | short-reversal | Small-gap fade, 25-50 bp band, no 10:00 confirmation, 2x inverse sleeve | 3.21% / 4.69% / 1.09 (dev) | development only; not promoted |

## What was wrong and what changed

### `dynamic-leverage-throttle` -> `dynamic-leverage-throttle-v2`

The original required the vol shock, its decay and the drawdown on the same
daily close.  The three-way conjunction occurred on **32 days in 6 episodes**,
producing 6 entries and only **1.17% average TQQQ weight**.  v2 arms on the
shock plus drawdown and triggers on the first decay day within 15 sessions
while the drawdown persists.  It produces **18 entries / 3.41% average
weight**; the event mean is **+2.37% (p = 0.019)**, the 8-cell grid is a
positive plateau, and all three sub-periods are positive.  The full record is
**7.07% CAGR / 17.16% DD / 0.78 Sharpe**, a low-exposure diversifier rather
than a standalone return engine.

### `drawdown-regime` -> `drawdown-regime-v2`

The original -20% arm was the binding constraint: 8 entries / 14.3%
exposure.  v2 arms at **-10%**, keeps the 20-session confirmed turn and
60-session hold, tightens the failure exit to a 15-session low, and re-arms
3 pp faster.  It produces **19 entries / 28.8% exposure**; dev is
**26.79% / 39.83% / 0.97** and full is **20.51% / 38.34% / 0.87**.  The
2024-26 holdout has **0 entries** (the book stays in BIL), so this is a
broader drawdown-recovery sleeve, not evidence for the original >=20%
capitulation state.  Keep as a diversifier only.

### `gap-capitulation-reversal` -> `gap-capitulation-reversal-v2`

The original event was too narrow, the 3-session hold too short, and the 30%
vol cap forced QQQ in 20 of 24 trades.  v2 lowers the close threshold to
**-1.5%**, holds **5 sessions**, and raises the cap to **35%**.  It produces
**39 events / 26 starts**, dev **20.55% / 22.25% / 1.05**, full
**17.05% / 25.54% / 0.86**.  The 5-session TQQQ event mean is **+7.40%
(t = 3.27)**; the heavy-volume subset is +0.34% (t = 0.22).  The 2024-26
holdout is positive but weaker (**7.73% CAGR**).  Average exposure is still
only 7.3%.

### `stop-reentry-recovery` -> `stop-reentry-recovery-v2`

The original 1 pp TQQQ-vs-3x-QQQ underperformance condition is an **8.3-sigma
event**: 3 days and one conjunction in 8 years.  v2 replaces it with a
**-5% intraday drop and z <= -2.0** against trailing 20-session volatility,
holds one session, and trades 100% TQQQ or BIL.  It produces **56 events**,
dev **14.50% / 17.39% / 0.96**, full **16.26% / 8.33% / 0.99** with 313
fills.  The h1 mean is +1.98% (t = 2.99).  Caveat: the edge is mostly QQQ
beta (h1 excess vs 3x QQQ only +0.055 pp); removing the top five events
leaves +0.95% (t = 1.94).  Honest as a volatility-normalised dip reversal,
not as LETF-rebalancing alpha.

### `vol-kelly-overlay` -> retired

Only 51 spike days and 33 spike-and-oversold days; the up-close filter
leaves **15 signal days / 11 entries**, and the up-close subset is the
*worse* subset (forward 3-day QQQ -0.12% after up-close vs +1.12% after
down-close).  The count repair reaches 28 entries, but the event mean is
+0.59% **p = 0.223** and no cell in the 8-cell grid reaches p <= 0.10.  The
count is fixable; the edge is not.  **Retired.**

### `volume-orderflow` -> retired

The original conjunction was nearly self-contradictory: conditional on QQQ
falling >=0.8% intraday, only **5** sessions close in the upper half of the
range.  The relaxed version reaches 44 events / 36 entries / 145 fills, but:
the high-vs-low volume difference is +0.76 pp with one-sided **p = 0.36**;
the no-volume control has a *higher* CAGR (23.1% vs 15.5%) and Sharpe (0.745
vs 0.723); the close-location sign is backwards (upper-half +0.57% on 6
events, close-at-low +3.48% on 145 events); 2020 alone is +95.3% and
2022-23 is -2.0%.  **Retired as a participation strategy.**  The residual
decline/close-off-low reversal is a different hypothesis and was not claimed.

### `drawdown-stop-overlay` -> retired (overlay-only)

The original failed-breakdown spring lost 9.3%/yr and every one of its 10
variants was negative; a "buy any -1% day" control earned +15.8%, so the
pattern itself was the problem.  The v2 primary keeps the 200-day trend and
30% vol filters but holds only **one day**, with a close exit: 24 signals,
**1.14% TQQQ time**, dev **3.36% / 23.37% / 0.54**.  A static TQQQ/BIL mix at
the same 1.14% average exposure earns **1.96% / 2.11% / 1.13** — the event
book is a worse risk-adjusted use of the exposure.  **Retire as a standalone;
overlay-only.**  The 5-session variants are weaker still.

### `gap-fill-fade` -> development-only

The original fade had 25 events at +5.6 bp (t = 1.01, p = 0.15), the
no-confirmation variant was better, and 10 bp CAGR was below BIL.  The v2
small-gap fade uses a +25 to +50 bp gap band, **no 10:00 confirmation**,
09:31 entry, a 2x inverse sleeve, and a 0.46% average short notional.  Dev is
**3.21% / 4.69% / 1.09** in 145 fills; the event mean is +0.416% net
(t = 2.73, p = 0.0069).  It beats the BIL bar at 1/5/10 bp, but 2018+2022
contribute 80% of event P&L and 2023 has no events.  Keep as a conditional
development-only satellite, not a core strategy.

## Verification status

- The four full-holdout v2 records have `holdout.json` with
  `full.fills = dev.fills + holdout.fills` and the corrected per-window
  turnover denominator (see `FILL_AGGREGATION_FIX.md`).
- `drawdown-regime-v2` has **77 dev fills and 0 holdout fills**; the full
  fills equal the dev fills because the sleeve stays in BIL through 2024-26.
  This is an activity caveat, not a fill-accounting bug.
- `gap-fill-fade-v2` is **development-only**: it has no 2024-26 record and is
  not presented as verified-full.
- `vol-kelly-overlay`, `volume-orderflow` and `drawdown-stop-overlay` remain
  in `LIBRARY.json` as verified historical records but are flagged
  `retired: true`; they are not family winners and should not be traded.
  `drawdown-stop-overlay-v2` is a development-only overlay result, not a
  standalone strategy.

None of the eight repairs changes a family winner, a site curve or a
published metric.  The five re-specifications are research records for the
next round; the three retired names should not be traded.
