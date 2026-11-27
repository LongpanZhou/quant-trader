> **Post-test note (2026-11-27):** this file is the pre-registration, not
> the result. The frozen development result is in `../SUMMARY.md`; the
> full 2016-2026 audit, the post-tune variants and the research-validity
> verdicts are in `../WHY_UNDERPERFORM.md`. The published website curve is
> the freeze named in `../SUMMARY.md`.

# Intraday-momentum rebuild — Time-of-Day Leverage Ladder (TODL)

**Status:** designed; **backtests paused**. No development, 10-year, 5-year or
holdout result has been produced for this rebuild. All numeric result fields
below are placeholders to be filled by the authorized run.

**Slug:** `intraday-momentum`
**Original:** `research/agents/intraday-momentum`
**Design date:** 2026-11-26
**Files:** `HYPOTHESIS.md` (pre-registration), `provenance.md` (sources),
`strategy.py` (implementation, not run).

## 1. Extracted idea

The original strategy was the 165-day QQQ trend base plus an overlay. Its
genuinely new content was:

1. TQQQ's return is concentrated in the **overnight** window (close → open) and
   the **first hour** (09:30 → 10:30).
2. The **first-hour return** carries information about the rest of the session.

The rebuild makes those two time-of-day components the **entire** signal. It
does not use a price trend, and it does not reuse the old base weights.

## 2. Standalone idea

A **weekly three-state leverage ladder** on the Nasdaq-100:

- **3x TQQQ** when the last 5 sessions' overnight-minus-intraday spread and
  first-hour return are both above their 26-week medians.
- **1x QQQ** when exactly one of the two is above its median.
- **BIL** when neither is.

A 20-session overnight-volatility cap reduces TQQQ to QQQ above 60% annualized
vol and moves the book to BIL above 80%.

The bet is that the **time-of-day drift is persistent enough at a weekly
horizon** to justify leverage, and that the overnight-vs-intraday spread is a
different return driver from the old 165-day price trend.

## 3. Hypothesis

Weeks with an unusually strong overnight-vs-intraday spread and unusually
strong first-hour momentum have a stronger time-of-day drift. A 3x/1x/0x ladder
in those weeks should deliver a better return/drawdown trade-off than static
QQQ or TQQQ, with daily-return correlation below 0.60 against the old 165-day
base.

The mechanism is the one in Boyarchenko, Larsen & Whelan (2023): overnight
returns continue overnight and reverse intraday; intraday returns continue
intraday and reverse overnight. The first-hour component is the Gao et al.
(2018) intraday-momentum idea, aggregated to a weekly state rather than used as
a same-day afternoon gate.

## 4. Why this is not the old base

| Dimension | Old strategy | This rebuild |
|---|---|---|
| Gate | QQQ close > 165-day SMA | 5-session sums of overnight-minus-intraday and first-hour returns vs their 26-week medians |
| Universe | TQQQ / BIL | QQQ / TQQQ / BIL |
| Base asset | TQQQ when the trend is on | QQQ in the middle state; TQQQ only when both time-of-day signals are above normal |
| Holding period | daily (overnight + first hour + afternoon gate) | 5 sessions, continuous |
| Sizing | 100% TQQQ or 100% BIL | 100% in one of TQQQ (3x), QQQ (1x), BIL (0x) |
| Risk | none beyond the trend | 20-session overnight-vol cap |
| Turnover | ~100 round trips/year | ~52 rebalances/year |

No 100–250-day moving average on QQQ, TQQQ, SPY or NDX is used. No old
`build_weights` or old base weights are called or copied.

## 5. Universe and data

- **Universe:** QQQ (1x), TQQQ (3x), BIL (0x).
- **Data:** local adjusted 1-minute QQQ/TQQQ/BIL, 2016-01-04 → 2023-12-29
  development. No new data is required.
- **Why not sectors/SPY:** the local 1-minute archive does not contain sector
  ETFs; SPY 1-minute data starts only in 2026. The brief requires 1-minute
  equity marks, so the primary uses the supported universe. The cross-sectional
  sector version is specified as the first fallback if the data subagent can
  supply sector data.
- **SPY benchmark:** no local daily SPY history; the SPY buy-and-hold benchmark
  is marked `TBD` until the data subagent supplies it. QQQ is the equity
  benchmark in the meantime.

## 6. Exact rules

### 6.1 Signal (QQQ, per session `d`)

- `on_d = QQQ_open_d / QQQ_close_{d-1} - 1` — overnight return.
- `id_d = QQQ_close_d / QQQ_open_d - 1` — intraday return.
- `fh_d = QQQ_close(60th bar)_d / QQQ_open_d - 1` — first-hour return, 60
  one-minute bars. A session with fewer than 60 bars is excluded from the
  signal.

### 6.2 Weekly (5-session) block ending at session `w`

- `S_on(w) = Σ_{d=w-4..w} (on_d - id_d)`.
- `S_fh(w) = Σ_{d=w-4..w} fh_d`.
- `med_on(w)` = median of the trailing 26 weekly `S_on` values, including `w`.
- `med_fh(w)` = median of the trailing 26 weekly `S_fh` values, including `w`.
- `on_signal = S_on(w) > med_on(w)`.
- `fh_signal = S_fh(w) > med_fh(w)`.

### 6.3 State

- Both signals true → **TQQQ 100%**.
- Exactly one true → **QQQ 100%**.
- Neither true → **BIL 100%**.

### 6.4 Risk cap

- `vol_on(w) = std(on_d over the last 20 sessions) * sqrt(252)`.
- If `vol_on > 0.80` → **BIL**.
- Else if `vol_on > 0.60` and the state is TQQQ → **QQQ**.
- Else leave the state unchanged.

### 6.5 Timing and fills

- Rebalance at the **close of every 5th session** (`w`).
- The target set at that close fills at the **next session's open**.
- Hold the state for the next 5 sessions.
- 2% band; 1 bp headline, 5 bp and 10 bp sensitivity.
- No look-ahead: the signal at `w` uses only bars through `w`'s close.

### 6.6 Warmup

- The first 5-session window needs valid `on`, `id` and `fh` values; the first
  rebalance is at the 10th session.
- The median needs 13 weekly observations. The first live rebalance is
  therefore around 2016-04. The report will state the exact effective start.

## 7. Decision process

1. At the close of every 5th session, compute `S_on`, `S_fh`, their 26-week
   medians, and `vol_on`.
2. Set the target state (TQQQ/QQQ/BIL) and apply the volatility cap.
3. The target fills at the next session's open. If the state is unchanged, no
   trade (2% band).
4. Hold through the next 5 sessions, including overnight and intraday.
5. Repeat.

## 8. Expected correlation with the old 165-day base

**Expected: 0.35–0.55 on daily returns over the development period.**

Reasons: the median normalization balances the three states; the middle state
is 1x QQQ, not 3x TQQQ; the rebalance is every 5 sessions, not daily; the
signal is a time-of-day carry measure, not a price trend.

**This is the main risk.** Both strategies are long Nasdaq equity in bull
markets, so the correlation could exceed 0.60. The falsifier is explicit: if the
dev correlation is ≥ 0.60, the design fails the brief and the lead should ask
for a direction change. Fallbacks are in §13.

## 9. Provenance (summary)

| Rule | Source | Role |
|---|---|---|
| `S_on = Σ(overnight − intraday)` | Boyarchenko, Larsen & Whelan (2023), *The Overnight Drift*, RFS 36(9) — [NY Fed SR917](https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr917.pdf), [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3546173) | inspired rule |
| Overnight and intraday are separate premia | Lou, Polk & Skouras (2019), *A Tug of War*, JFE 134(1) — [DOI](https://doi.org/10.1016/j.jfineco.2019.03.011) | supports assumption |
| `S_fh = Σ first_hour` | Gao, Han, Li & Zhou (2018), *Market Intraday Momentum*, JFE 129(2) — [DOI](https://doi.org/10.1016/j.jfineco.2018.05.009) | inspired rule |
| QQQ as the signal asset; TQQQ path caveat | Cheng & Madhavan (2009), *The Dynamics of Leveraged and Inverse ETFs* — [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1393995) | supports assumption |
| Cross-sectional sector fallback | Bogousslavsky (2021), *The Cross-Section of Intraday and Overnight Returns*, JFE 141 — [DOI](https://doi.org/10.1016/j.jfineco.2020.07.020) | fallback only |
| 26-week median, 5-session holding, 3-state ladder, vol caps | Own test / no external source | design choices |
| Last-30-minute timing | Gao et al. (2018) | **tested and rejected** in this sample |
| Pure daily intraday momentum | Own test / no external source | **tested and rejected** |
| Overnight-only + 165-day regime | Own test / no external source | **tested and rejected as standalone** |

Full detail, exact quotes and the source-to-rule map: `provenance.md`.

## 10. Evaluation plan (after authorization)

### 10.1 Development windows

- Development: 2016-01-04 → 2023-12-29, 1-minute marks, 2% band.
- Costs: 1 bp headline, 5 bp and 10 bp sensitivity.
- Report CAGR, max drawdown (positive fraction), Sharpe, fills, turnover.

### 10.2 Benchmarks

- TQQQ, QQQ and (when available) SPY buy-and-hold.
- The original strategy's own `result.json` numbers, labelled as overlapping the
  holdout.
- The 165-day baseline itself, for the correlation check.

### 10.3 Overfitting controls

- **Variants tried:** 7 design variants (HYPOTHESIS §7), plus the parameter
  neighbourhood below. Count reported in `result.json`.
- **Parameter neighbourhood (±1 step):**
  - holding/rebalance: 3, 5, 10 sessions;
  - median lookback: 13, 26, 52 weeks;
  - vol cap pair: (0.50, 0.70), (0.60, 0.80), (0.70, 0.90);
  - first-hour window: 30, 60, 90 bars.
  The primary is chosen from a plateau, not the best cell.
- **Sub-periods:** 2016–19, 2020–21, 2022–23.
- **Placebo:** 200 random weekly state sequences with the same TQQQ/QQQ/BIL
  frequencies, rebalanced on the same dates. Report the percentile of the
  strategy's CAGR and max drawdown in the placebo distribution.
- **Event count:** number of state changes and the number of TQQQ-state weeks.
  If the TQQQ state has fewer than 100 weeks, report a bootstrap p-value for
  the TQQQ-vs-QQQ forward-return difference.
- **Parameter stability:** the plateau table above.
- **No peeking:** the holdout is never loaded by this agent. The lead runs the
  frozen strategy once on 2024-01-02 → 2026-10-23.

### 10.4 Expected result shape

The strategy should show:

- A TQQQ state with a higher forward 5-session return than the QQQ state.
- A BIL state with a lower drawdown than QQQ/TQQQ.
- A dev correlation with the 165-day base below 0.60.
- A 5 bp/10 bp result that is not erased by the ~52 annual rebalances.

If the TQQQ state's forward return is not higher than the QQQ state's, the
ladder is not adding information and the idea is falsified.

## 11. Results (development)

**Not run — backtests are paused.** No number below has been produced.

| Window | Cost | CAGR | Max DD (1m marks) | Sharpe | Fills | Turnover |
|---|---|---:|---:|---:|---:|---:|
| dev 2016-01-04 → 2023-12-29 | 1 bp | TBD | TBD | TBD | TBD | TBD |
| dev | 5 bp | TBD | TBD | TBD | TBD | TBD |
| dev | 10 bp | TBD | TBD | TBD | TBD | TBD |
| holdout (lead only) | 1/5/10 bp | — | — | — | — | — |
| 10y (overlaps holdout) | 1/5 bp | — | — | — | — | — |
| 5y (overlaps holdout) | 1/5 bp | — | — | — | — | — |

Correlation vs the 165-day baseline (dev): **TBD**
(design target: < 0.60; expected 0.35–0.55)

State frequencies (dev): **TBD** (TQQQ / QQQ / BIL counts)

Sub-periods (dev, 1 bp): **TBD**

### Context: original strategy (not this rebuild)

For comparison only, the original strategy's verified numbers were:

| Window | 1 bp | 5 bp |
|---|---|---|
| 10y 2017-01-03 → 2026-10-23 | 55.63% CAGR / 44.89% DD / 1.24 Sharpe | 43.46% / 46.90% / 1.05 |
| 5y 2021-10-25 → 2026-10-23 | 46.36% / 32.64% / 1.14 | 35.80% / 34.50% / 0.96 |

These overlap the holdout and are not a development comparison. The rebuild's
dev numbers are the ones that matter for the revisit decision.

## 12. Risks and failure modes

1. **Correlation risk.** The old base and the rebuild are both long Nasdaq
   equity in bull markets. If the correlation is ≥ 0.60, the rebuild is not
   independent enough.
2. **Signal risk.** The weekly sums are noisy; the 26-week median may not
   separate strong from weak time-of-day regimes. The first-hour effect is
   statistically weak in the original dev evidence (t ≈ 1–2).
3. **Weekly aggregation risk.** The overnight/intraday continuation-reversal in
   Boyarchenko et al. is a daily phenomenon; aggregating to 5 sessions may
   weaken it.
4. **Cost risk.** ~52 rebalances/year; if the state flips often, 10 bp costs can
   still be material.
5. **TQQQ path dependence.** The 3x daily reset and leveraged-ETF rebalancing
   flows can make realized TQQQ returns differ from a simple 3x overlay.
6. **Data risk.** The primary uses QQQ/TQQQ/BIL only; the sector and SPY
   extensions are not tested. The SPY benchmark is pending.

## 13. Fallbacks and retirement rule

**Fallbacks if the dev correlation is ≥ 0.60:**

1. Replace the QQQ middle state with BIL (0x/3x only), lowering average beta.
2. Use a 3x/1x/0x ladder on QQQ only (no TQQQ), structurally different from the
   old 3x TQQQ base.
3. Move to the cross-sectional sector version (9 SPDR sectors, long top 3
   overnight) if the data subagent can supply sector data.

**Retirement rule:** if the weekly ladder's states coincide with the old
165-day regime (e.g., the TQQQ state is essentially “old base on”) or the
correlation is ≥ 0.60, the idea is overlay-only. Mark it
`retired_overlay_only` with the evidence; do not force it.

## 14. Files

- `HYPOTHESIS.md` — pre-registered hypothesis, exact design, falsifiers,
  variants.
- `provenance.md` — sources, exact claims, source-to-rule map, rejected ideas.
- `strategy.py` — `build_weights()` and `main()`; development-only; not run.
- `report.md` — this document.

No `result.json` is written while backtests are paused. `strategy.py:main()`
will write it after authorization.
