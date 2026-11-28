# Hypothesis and pre-registration — `time-of-day` (revisit)

Written before any code was run. Nothing in this file has been fitted to data.
Backtests are paused; the numbers in `report.md` do not exist yet.

## 1. What the original strategy actually contained

The original (`research/agents/time-of-day/`) held TQQQ from the 15:59 open to
the 10:01 open next morning and was in cash otherwise, gated by QQQ versus its
165-day SMA with a 2% hysteresis band. Its own report attributes the return to
two facts: **78% of TQQQ's log return accrues outside the cash session**, and
**the last 30 minutes of the session are the only reliably negative block of the
day** (−5.74% CAGR, −1.48 bp/day over 2,700 sessions).

Strip the 165-day gate and what remains is "be long TQQQ every night". That is
the residue the clarification warns about, and it is the *reference variant*
V0 here, not the strategy.

## 2. The one genuinely new idea

The old strategy treats every night as identical except for a slow trend gate.
But the reason the overnight block pays is that **it is the settlement window for
the session's imbalances**: the closing 30 minutes are systematically sold, and
that selling pressure is reversed once liquidity returns the next morning
(Berkman et al. 2012 on the open; Heston et al. 2010 on half-hour periodicity;
Lou et al. 2019 on the overnight/intraday clientele split).

If that is the mechanism, the overnight return should be *conditional on the
closing block*: nights that follow a **sold close** should pay more than nights
that follow a **bought close**. The old strategy could not express this — it was
unconditional (modulo the trend gate) and binary.

**Hypothesis H1.** The overnight+first-30m block return is a decreasing function
of the QQQ return over the last 30 minutes of the preceding session. A strategy
that holds only after negative closing blocks, and sizes with the magnitude of
the closing move, earns a higher return per night and a higher Sharpe than the
unconditional version.

**Hypothesis H2 (risk).** The conditional edge is destroyed in high-volatility
states, so the sleeve must also require the block's *own* realised volatility to
be within 1.5× its 60-session median.

**Hypothesis H0 (null).** Closing-block information is worthless; the conditional
strategy is a random subset of nights and cannot beat V0 after costs.

## 3. Why this is not the old overlay

| dimension | original | this rebuild |
|---|---|---|
| position rule | every night, gated by QQQ/165d SMA | only nights after a sold close, gated by the block's own realised vol |
| gate input | 165-day price trend on QQQ | last-30-minute return + 10-session realised vol of the strategy's own block |
| sizing | binary 0/1, driven by the gate | continuous 0–1, driven by closing-pressure magnitude and vol |
| holding | 15:59 → 10:01 every night | 15:59 → 10:01 on a conditioned ~45% of nights |
| return driver | equity beta overnight | the closing-to-open reversal, i.e. *when* the overnight is held |
| assets | TQQQ / BIL | TQQQ / cash (BIL tested as V5) |

No 100–250-day moving average on QQQ, TQQQ, SPY or NDX appears anywhere. No
weights, functions or files from the original implementation are reused.

## 4. Universe, signal, holding period, sizing, risk

- **Universe:** TQQQ long (3× QQQ), cash. BIL only as a pre-registered variant.
- **Clock:** one decision per session at 15:58 ET. Entry at the open of the
  session's last 1-minute bar (~15:59), exit at the open of the next session's
  32nd bar (~10:01). Holding period ≈ 17 hours. Half days use the same
  bar offsets, so the entry is the half-day close.
- **Signal 1 (closing pressure):** `c30` = QQQ log return from the 15:29 close to
  the 15:58 close, i.e. the last 30 minutes *before* the entry. `z = c30 /
  median(|c30|, previous 20 sessions)`.
- **Signal 2 (risk state):** `v` = annualised stdev of the previous 10 completed
  block log returns; `m` = median of `v` over the previous 60 sessions.
- **Gate:** on iff `sign(c30) == close_sign` (default −1), `|c30| >= 0.5 ·
  median(|c30|, previous 20 sessions)` (the closing move must be at least half a
  typical one, so noise does not trigger a trade), and `v <= 1.5 m`, and both
  statistics exist.
- **Size:** `min(1, 0.40 / v)` when the gate is on, else 0. 0.40 is roughly the
  block's own median annualised vol, so a normal-vol night gets size ≈ 1 and a
  2× vol night gets ≈ 0.5. The magnitude of `c30` is used only as the entry
  threshold, not as a continuous size, to keep the number of fitted continuous
  parameters small.
- **Risk:** no leverage beyond size 1, no shorts, one block at a time, hard flat
  when `v > 1.5 m`.

## 5. Falsifiers (all evaluated on development only, 2016-01-04 → 2023-12-29)

1. **F1 sign and size.** Mean block log return after `c30 < 0` must exceed the
   mean after `c30 >= 0` by at least 5 bp/night, two-sample t ≥ 1.5. If the sign
   is reversed, the "sold close reverses overnight" mechanism is wrong. One
   re-specification to the opposite sign is allowed (`c30 > 0`, variant V4);
   if that also fails, retire.
2. **F2 conditioning must pay.** V1 (conditioning only, size fixed at 1) must
   beat V0 (unconditional, size fixed at 1) on dev CAGR at 1 bp. Comparing V1
   with V0 keeps size out of it, so the test isolates the conditioning. If V1
   does not beat V0, the closing condition adds nothing and the remainder is the
   old residue → `retired_overlay_only`.
3. **F3 risk.** Dev max DD ≤ 45%, Sharpe ≥ 0.70 at 1 bp.
4. **F4 stability.** The conditional sign must hold in at least 2 of the 3 dev
   sub-periods (2016–19, 2020–21, 2022–23).
5. **F5 placebo.** 200 random night selections with the same number of active
   nights must produce a mean dev CAGR below the real strategy, p < 0.10.
6. **F6 independence.** Daily-return correlation with the rebuilt 165-day
   baseline < 0.60 on dev. Expected 0.35–0.55. If ≥ 0.60 the design fails the
   brief even if profitable.
7. **F7 cost.** At 5 bp the strategy must still beat TQQQ buy-and-hold on dev,
   else it is marked `fragile` rather than `passed`.

## 6. Pre-registered variants (6) and parameter neighbourhood

| id | rule |
|---|---|
| V0 | unconditional always-on (reference / residue) |
| V1 | `c30 < 0` only, size 1, no vol gate |
| V2 | vol gate only, no closing condition |
| **V3** | **full: `c30 < 0` + vol gate + continuous size (the strategy)** |
| V4 | full, opposite sign (`c30 > 0`) — the momentum branch |
| V5 | full, but BIL instead of cash while flat |

Neighbourhood (±1 step, chosen from a plateau, not the peak): `vol_look`
5/10/20; `ref_look` 40/60/90; `vol_mult` 1.25/1.50/2.00; `close_window`
20/30/45 minutes; `vol_target` 0.30/0.40/0.50.

The neighbourhood is reported in full, including losing cells. Parameters are
only accepted if V3 sits on a plateau, not a spike.

## 7. Freeze protocol

1. All development work, including the neighbourhood and the placebo, uses only
   2016-01-04 → 2023-12-29. The panel loader is called with `panel_end=DEV_END`.
2. Parameters are frozen to the values in §4 before the holdout is touched.
3. Only then is the panel re-loaded through 2026-10-23 and the frozen weights run
   once to fill `windows.10y` and `windows.5y` (these overlap the holdout and are
   labelled as such).
4. `windows.holdout` is left for the lead.

## 8. Provenance

See `report.md` §"Provenance" for the full source table with URLs. Primary
sources for this hypothesis:

- Berkman, Koch, Tuttle & Zhang (2012), *Paying Attention: Overnight Returns and
  the Hidden Cost of Buying at the Open*, JFQA 47(4) — positive overnight returns
  followed by intraday reversal, driven by a temporary inflation of the opening
  price. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1625495
- Heston, Korajczyk & Sadka (2010), *Intraday Patterns in the Cross-Section of
  Stock Returns*, JF 65(4) — return continuation at half-hour intervals that are
  exact multiples of a trading day. https://arxiv.org/abs/1005.3535
- Lou, Polk & Skouras (2019), *A Tug of War: Overnight versus Intraday Expected
  Returns*, JFE — separate clienteles at the open and the close.
  https://ifr.hkust.edu.hk/uploads/upload/files/20250212/445bce5ab83ffca69c4fe4b56c8055e1.pdf
- Cliff, Cooper & Gulen (2008), *Return Differences between Trading and
  Non-Trading Hours* — the unconditional overnight premium that V0 tests.
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1004081
- Gao, Han, Li & Zhou (2018), *Market Intraday Momentum*, JFE 129(2) — the first
  half-hour predicts the last half-hour; the reason the exit is at 10:01 rather
  than 09:31. https://doi.org/10.1016/j.jfineco.2018.05.009

The closing-pressure *direction* is the part I am least sure about: the
cross-sectional literature (Berkman et al.) says the open is temporarily
inflated then reverses, while the market-level intraday-momentum literature
(Gao et al.) says the close continues the first half-hour. F1 and V4 are
designed to settle exactly this, and the sign is not assumed in the code —
`close_sign` is an explicit parameter.
