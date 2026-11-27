# Pre-registered hypothesis — intraday-momentum rebuild

**Date:** 2026-11-26
**Status:** designed; all backtests paused until the lead/user authorizes the new test.
**Slug:** `intraday-momentum`
**Working name:** Time-of-Day Leverage Ladder (TODL)

## 1. What was genuinely new in the original?

The original `research/agents/intraday-momentum` strategy was the 165-day QQQ
SMA base plus an overlay. The new content was:

1. TQQQ earns most of its return in the **overnight** window (close → open) and
   in the **first hour** (09:30 → 10:30), not uniformly through the day.
2. The **first-hour return** carries information about the rest of the session
   (the original used it to gate the afternoon).

The 165-day price trend was the base, not the idea. The rebuild therefore drops
the price trend entirely and makes the two time-of-day components the signal.

## 2. Hypothesis

Weeks in which the Nasdaq-100's **overnight return has beaten its intraday
return** (the "overnight vs intraday tug of war") and in which the **first hour
has been strong relative to its own history** have a stronger time-of-day
drift. A weekly three-state leverage ladder — 3x TQQQ when both signals are
above their usual levels, 1x QQQ when only one is, and BIL when neither is —
should deliver a better return/drawdown trade-off than static QQQ or TQQQ, with
a different return driver from the old 165-day price-trend base.

The economic mechanism is the one documented by Boyarchenko, Larsen & Whelan
(2023): overnight returns continue overnight and reverse intraday, while
intraday returns continue intraday and reverse overnight. The first-hour signal
adds the Gao et al. (2018) intraday-momentum component. Combining the two at a
weekly horizon diversifies their noise and keeps turnover low enough to survive
5–10 bp costs.

## 3. Exact design (pre-registered)

### Universe

QQQ (1x core), TQQQ (3x), BIL (0x). Local adjusted 1-minute QQQ/TQQQ/BIL data,
2016-01-04 → 2023-12-29 development. No new data.

### Signal (computed on QQQ)

For each regular session `d`:

- `on_d = QQQ_open_d / QQQ_close_{d-1} - 1` — overnight return.
- `id_d = QQQ_close_d / QQQ_open_d - 1` — intraday return.
- `fh_d = QQQ_close(60th bar)_d / QQQ_open_d - 1` — first-hour return
  (60 one-minute bars; if a session has fewer than 60 bars, the session is
  excluded from the signal).

Every 5th session `w` (a "week" of 5 trading sessions):

- `S_on(w) = Σ_{d=w-4..w} (on_d - id_d)` — overnight-minus-intraday spread.
- `S_fh(w) = Σ_{d=w-4..w} fh_d` — first-hour momentum.
- `med_on(w)` = median of the trailing 26 weekly `S_on` values, including `w`.
- `med_fh(w)` = median of the trailing 26 weekly `S_fh` values, including `w`.
- `on_signal = S_on(w) > med_on(w)`.
- `fh_signal = S_fh(w) > med_fh(w)`.

The median normalization is deliberate. Both raw signals have a positive
average, so a zero threshold would leave the strategy long most of the time and
would recreate the old base's high correlation. The median asks "is this week's
time-of-day drift stronger than its own recent usual level?" — a signal-derived
normalization, not a price moving average.

### State and sizing

- Both signals true → **TQQQ 100%**.
- Exactly one true → **QQQ 100%**.
- Neither true → **BIL 100%**.

No leverage beyond 100% TQQQ; no shorting; one asset at a time.

### Risk cap

- `vol_on(w) = std(on_d over the last 20 sessions) * sqrt(252)`.
- If `vol_on > 0.80` → **BIL** (override).
- Else if `vol_on > 0.60` and the state is TQQQ → cap at **QQQ**.
- Else leave the state unchanged.

The cap is derived from the overnight return series itself and is designed to
cut the 2020/2022 tail without a price trend.

### Holding period and fills

- Rebalance at the **close of every 5th session** (`w`).
- The weight set at that bar fills at the **next session's open**.
- Hold the new state for the next 5 sessions.
- 2% band; 1 bp headline, 5 bp and 10 bp sensitivity.
- No look-ahead: the signal at `w` uses only bars through `w`'s close.

### Warmup

- The first 5-session window needs valid `on`, `id`, `fh` values; the first
  rebalance is at the 10th session.
- The median needs 13 weekly observations (26-week median, minimum 13). The
  first live rebalance is therefore around 2016-04. The report will state the
  effective dev start.

## 4. Why this is not the old base

| Dimension | Old strategy | This rebuild |
|---|---|---|
| Gate | QQQ close > 165-day SMA | 5-session sums of overnight-minus-intraday and first-hour returns vs their 26-week medians |
| Universe | TQQQ / BIL | QQQ / TQQQ / BIL |
| Base asset | TQQQ when trend on | QQQ in the middle state; TQQQ only when both time-of-day signals are above normal |
| Holding period | daily (overnight + first hour + afternoon gate) | 5 sessions, continuous |
| Sizing | 100% TQQQ or 100% BIL | 3-state 100% ladder (3x / 1x / 0x) |
| Risk | none beyond the trend | 20-session overnight-vol cap |
| Turnover | ~100 round trips/year | ~52 rebalances/year |

The old `build_weights` and the old base weights are not called or copied.

## 5. Expected correlation with the old 165-day base

**Expected: 0.35–0.55 on daily returns over the development period.**

Basis: the median normalization balances the three states; the middle state is
1x QQQ, not 3x TQQQ; the rebalance is every 5 sessions, not daily; the signal is
a time-of-day carry measure, not a price trend. The main correlation risk is
that both strategies are long Nasdaq equity during bull markets. If the dev
correlation is **≥ 0.60**, the design fails the brief and the lead should ask
for a direction change (fallback options in §8).

## 6. Falsifiers (pre-registered)

The strategy is falsified if any of the following is true in the authorized
development run:

1. Daily-return correlation with the 165-day baseline is **≥ 0.60**.
2. The TQQQ state's forward 5-session return is **not higher** than the QQQ
   state's, or the BIL state does not have a lower drawdown than QQQ/TQQQ.
3. The signals' relationship with forward returns is insignificant or the wrong
   sign in any of the three sub-periods (2016–19, 2020–21, 2022–23).
4. A placebo with random weekly states and the same state frequencies matches
   or beats the strategy's CAGR/drawdown.
5. The ±1-step parameter neighbourhood is not a plateau: the 5-session window
   (3/5/10), median lookback (13/26/52 weeks), vol caps (50/60/70 and
   70/80/90), or first-hour window (30/60/90 bars) flips the result.
6. At 5 bp or 10 bp the strategy's CAGR is below QQQ buy-and-hold, or its
   drawdown is worse than QQQ's.
7. The development CAGR is below QQQ buy-and-hold with no drawdown improvement.

## 7. Design variants considered before coding

1. **Daily overnight-only** (TQQQ overnight, BIL intraday). Rejected: two fills
   a day; at 5–10 bp the round-trip cost is 12–25%/yr and would dominate.
2. **Daily first-hour-only** (TQQQ 10:30–15:59 if first hour > 0). Rejected: the
   original dev evidence showed a weak afternoon spread (about +8 bp on
   positive-first-hour days vs −3 bp on negative days, t ≈ 1), and the old
   strategy's pure intraday variant failed the 10-year test.
3. **Daily overnight + first-hour ladder**. Rejected for the same daily
   turnover reason as (1).
4. **Weekly continuous ladder** — this design. Weekly rebalancing keeps the
   signal's economic content while cutting turnover by ~5x.
5. **Fixed-threshold weekly ladder** (±1% on the combined score). Kept as a
   neighbourhood variant; the median version is primary because it is
   self-normalizing and avoids a hard return threshold.
6. **Cross-sectional sector overnight rotation** (9 SPDR sectors, long top 3).
   Deferred: the local 1-minute archive only supports QQQ/TQQQ/BIL, and the
   brief requires 1-minute equity marks. A sector version would need a new
   1-minute data fetch; it is the first fallback if the single-asset ladder
   correlates too highly with the old base.
7. **Long-short overnight/intraday carry** (long TQQQ overnight, short QQQ
   intraday). Rejected: `research/bt.py` is long-only; the brief forbids a
   private simulator, so the short leg cannot be modelled inside the required
   harness.

## 8. Fallbacks if the correlation fails

- Replace the QQQ middle state with BIL (0x/3x only), lowering average beta.
- Use a 3x/1x/0x ladder on **QQQ only** (no TQQQ), which is structurally
  different from the old 3x TQQQ base.
- Move to the cross-sectional sector version (variant 6) if the data subagent
  can supply 1-minute or daily sector data.

## 9. Retirement rule

If the weekly ladder's states coincide with the old 165-day regime (e.g., the
TQQQ state is essentially "old base on") or if the correlation is ≥ 0.60, the
idea is overlay-only and the rebuild should be marked
`retired_overlay_only`, with the evidence in `report.md`. Do not force it.
