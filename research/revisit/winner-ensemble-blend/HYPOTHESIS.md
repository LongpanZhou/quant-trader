# Hypothesis — pre-registered before any backtest

**Strategy:** `winner-ensemble-blend` (revisit)
**Status:** SPEC ONLY. Backtests are paused by the lead on 2026-11-26. Nothing below
has been simulated. No holdout data (2024-01-02 → 2026-10-23) has been inspected.

---

## 1. What the original strategy actually contributed

The original `winner-ensemble-blend` was a fixed 75/25 or inverse-vol blend of two
round-1 sleeves:

- the winner: daily QQQ 165-day SMA regime + armed 4% minute stop, 100% TQQQ/BIL;
- the ensemble: the same 165-day trend gate + a 20-day volatility budget + a
  1-minute crash vote, 100% TQQQ/BIL.

Both sleeves share the **same 165-day QQQ base**. The blend's measured edge
(58.4%/41.2% 10y, 47.9%/32.3% 5y at 1 bp) came almost entirely from that base;
the 25% ensemble sleeve only shaved the drawdown. The blend layer itself was
never tested on independent return streams.

So the genuinely new idea is **not** "TQQQ trend following", and it is **not** a
stop. It is:

> **Allocate capital across independent return streams by inverse trailing
> volatility, so that the portfolio's risk comes from the combination rather
> than from any one regime.**

The old implementation does not test that idea, because its "streams" are the
same trade with different overlays.

## 2. Standalone idea

Rebuild the allocation idea as a complete two-stream strategy with **no slow
QQQ/TQQQ/SPY/NDX moving-average gate**:

- **Stream A — calm-regime QQQ carry (1x, partial).** Hold 70% QQQ / 30% BIL
  when short-term realised volatility is in the bottom 40% of its trailing
  60-day range and QQQ's 5-day return is positive; otherwise BIL. This harvests
  the equity risk premium only in calm, rising markets, at 1x rather than 3x.
- **Stream B — panic-reversal TQQQ (3x, short hold).** Buy TQQQ at the next
  open after a sharp QQQ selloff (3-day return ≤ −5%, or 1-day ≤ −3% with
  10-day/60-day volatility ≥ 1.5), hold at most 3 sessions, exit early on a
  close back above the 10-day mean, with an 8% close-based stop and a
  2-session cooldown. This harvests the short-term reversal / liquidity-
  provision premium, using TQQQ only for the rebound.
- **Allocation.** At each daily close, weight the streams inversely to their
  trailing 20-day realised daily volatility (shifted one day, clipped to
  [0.20, 0.80]). The residual is BIL. Rebalance with the 2% band; fills at the
  next bar's open.

Stream A and Stream B are deliberately **opposite conditional exposures**
(calm-up vs panic-down). Their returns should be weakly or negatively
correlated, which is what makes the inverse-vol blend a real allocation
strategy rather than a leverage switch.

## 3. Hypothesis

> A causal inverse-vol blend of a calm QQQ carry stream and a panic-reversal
> TQQQ stream earns a positive risk-adjusted return on the 2016–2023
> development period, with a lower drawdown than either stream alone and a
> daily-return correlation below 0.60 with the old 165-day TQQQ baseline,
> because it holds 1x equity in calm markets and 3x equity only after sharp
> selloffs instead of holding 3x throughout slow uptrends.

## 4. Expected correlation vs the old base

**Expected: 0.30–0.55.** Hard ceiling for the rebuild: **0.60**.

Reasoning: the old base is long TQQQ on about 74% of development days. Stream A
is long QQQ on roughly 40% of days, mostly calm up days, so its own correlation
with the base could be ~0.6. Stream B is long TQQQ on ~5–10% of days, after
selloffs, often when the old base is already in BIL, so its correlation should
be low or negative. A risk-balanced blend (roughly 55–65% A, 35–45% B) should
land near 0.40–0.55. If it lands at 0.60 or above, the strategy is still equity
beta in disguise and is rejected.

## 5. Falsifiers (decided before the test)

The strategy is **rejected** if any of these is true on the development period:

1. **Diversity:** daily-return correlation with the 165-day baseline ≥ 0.60.
2. **Allocation adds nothing:** blend Sharpe ≤ max(Sharpe_A, Sharpe_B) **and**
   blend max drawdown ≥ min(maxDD_A, maxDD_B). (The blend must improve at
   least one of risk or risk-adjusted return versus the better stream.)
3. **Carry stream is not a premium:** Stream A's standalone dev CAGR at 5 bp is
   ≤ BIL's dev CAGR, or its Sharpe is ≤ 0.
4. **Reversal stream is noise:** fewer than 25 Stream-B events, or a bootstrap
   p-value > 0.10 for the mean post-signal 3-day TQQQ return versus the
   unconditional distribution.
5. **Parameter knife-edge:** the sign of the blend's dev CAGR flips at both
   ±1-step neighbours of any core parameter, or the correlation crosses 0.60 at
   both neighbours.
6. **Costs:** the blend's dev CAGR at 5 bp is ≤ 0, or its 5 bp max drawdown is
   > 40%.
7. **Sub-period:** the 2022–2023 sub-period CAGR is < −10% (the result is a
   2016–2021 bull-market artefact).
8. **Placebo:** random entries with the same frequency and holding period beat
   the real signals' dev Sharpe in more than 10% of 200 draws.

If falsifier 3 or 4 fails only for one stream, the honest fallback is a
one-stream strategy, not a blend; in that case this slug is marked
`retired_overlay_only` with the evidence, because the *allocation* idea did not
stand alone.

## 6. What would make this a success

- Corr vs baseline in 0.25–0.55.
- Blend dev Sharpe > both streams, or blend max DD < both streams.
- Positive dev CAGR at 1 bp, 5 bp and 10 bp.
- Stream B has ≥ 30 events and a bootstrap p-value < 0.10.
- The parameter neighbourhood is a plateau, not a spike.
- The result is not carried by 2020 alone (2022–2023 still positive or small
  negative with a lower drawdown than QQQ).

A low absolute return (single-digit CAGR) is acceptable for this rebuild: the
goal is a genuinely independent return stream, not a replacement for the 3x
trend winner.
