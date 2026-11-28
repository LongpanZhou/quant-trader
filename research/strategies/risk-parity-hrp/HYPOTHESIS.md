# Hypothesis — risk-parity-hrp rebuild

**Slug:** `risk-parity-hrp`
**Status:** design only. Backtests paused by the lead (2026-11-26). No result.json.
**Dev window (when authorised):** 2016-01-04 → 2023-12-29. Holdout 2024-01-02 →
2026-10-23 is not to be inspected by this agent.

## 1. The idea extracted from the original

The original agent's genuinely new content was **not** the 165-day regime and not
the 4% stop. It was the risk model: an inverse-volatility / HRP allocation across
QQQ, TQQQ and BIL, used to size the equity sleeve (a 70% vol target with a TQQQ
cap). Everything else was the shared base.

Two facts from the original work survive and constrain any rebuild:

1. **HRP across QQQ/TQQQ/BIL is degenerate.** With 60-day covariances, HRP
   allocated 99.99% to BIL (QQQ 0.0089%, TQQQ 0.0010%). Inverse-vol/ERC across
   the three assets gives 1.03% QQQ / 0.34% TQQQ / 98.63% BIL. BIL's variance is
   about four orders of magnitude smaller, so "risk parity" over the full set is
   a T-bill portfolio.
2. **QQQ and TQQQ are one factor.** Ten-year daily correlation 0.99951; the
   average 60-day correlation is 0.99986. Equal-risk weights on the pair are
   ~75% QQQ / 25% TQQQ, a ~34% vol sleeve. There is no second equity risk
   premium to diversify into.

So the only honest risk-parity object on this universe is the **QQQ/TQQQ pair**
(a leverage choice), plus BIL as the funding/defensive leg.

## 2. Why the naive rebuild fails the diversity rule

Measured on dev before the pause (exploratory scripts `explore_dev.py`,
`explore_dev2.py`; 1 bp, 1-minute marks, 2% band):

| Variant | CAGR | Max DD | Daily corr vs 165d base |
|---|---:|---:|---:|
| 165d base (reference) | 43.73% | 59.60% | 1.00 |
| 100% TQQQ buy-and-hold | 36.15% | 82.29% | **0.71** |
| ERC QQQ/TQQQ (75/25), always invested | 27.04% | 52.69% | 0.72 |
| ERC to a 45% vol target | 25.85% | 51.20% | 0.77 |
| Vol-target 60%, 20d | 45.23% | 74.10% | 0.78 |
| Reversal tilt on the risk budget (r20, k=6) | 20.18% | 49.20% | 0.68 |
| Realised-Sharpe tilt | 21.75% | 43.14% | 0.88 |

The floor for a long-equity strategy is 0.71 (buy-and-hold TQQQ), because the
base is itself long TQQQ 74% of sessions and its BIL days are exactly the
high-volatility days. **Volatility targeting makes correlation worse (0.78),
not better**: the vol regime and the trend regime coincide. A pro-cyclical
risk-parity rebuild therefore cannot satisfy the < 0.60 rule, no matter how the
sleeve is weighted.

The only way down is to hold equity on a **different subset of days** from the
trend base. Since the base is out during stress, the rebuild must be *in* during
at least part of it.

## 3. The hypothesis

**The conditional Sharpe ratio of the equity factor rises after a *transient*
volatility spike and does not rise in a *persistent* high-volatility regime.**

A risk-parity investor who sizes by risk alone (weight ∝ 1/σ) is implicitly
assuming a constant Sharpe ratio. If the Sharpe ratio is instead state-dependent,
the correct risk budget is proportional to the *conditional* Sharpe ratio, not
to 1/σ. Empirically the relation between volatility and forward returns is weak
and horizon-dependent: volatility increases are associated with price revisions
and higher subsequent expected returns at short horizons (French-Schwert-
Stambaugh 1987; Schwert 1989; the 1991 JF paper on volatility changes), while at
long horizons the risk-return trade-off is weak or negative and slow-moving
beliefs produce delayed overreaction (NBER w28102). Persistent high-volatility
regimes (2022) are therefore different from transient spikes (2018 Q4, 2020 Q1).

**Rebuild thesis:** make the risk model the whole strategy.

1. **Composition — true risk parity within the factor.** ERC on QQQ/TQQQ:
   `w_TQQQ = σ_QQQ / (σ_QQQ + σ_TQQQ)` using 60-day vols, clipped to
   [0.10, 0.50]. Typical 75/25, sleeve vol ~34%. TQQQ never becomes the whole
   book.
2. **Risk budget — contrarian to the volatility *state*, not the trend.**
   `tilt = clip(log(σ20/σ120)/0.35, -1, +1) * (1 - 0.70 * persist)`, where
   `persist` measures whether the 120-day vol is itself in a high regime
   (vs its 3-year median). Transient stress raises the budget; persistent stress
   damps the raise by 70%. Budget `b = 0.35 + 0.20 * tilt`, in [0.15, 0.55].
3. **Risk controls of its own, not the old stop.**
   - forecast-vol cap: `b ≤ 0.18 / σ_sleeve`;
   - a drawdown brake on the strategy's *own* equity (hysteresis: −12% halves
     the budget, −20% cuts it to 20%, release at −6% / −14%);
   - long-only, gross ≤ 1, BIL for the rest.
4. **Holding period.** Daily decisions, 5-day-smoothed state, 2% band. The state
   variable moves over weeks, so positions persist; the brake is the only fast
   component.

There is no price moving average, no 165-day gate, no 4% stop, and no reused
weight code. The strategy is long when the base is usually flat (after
volatility spikes) and small when the base is usually long (calm uptrends).

## 4. Expected correlation with the old base

**0.30–0.55.** Justification: the exposure pattern is structurally opposite to
the trend state on the days that matter. The base is out in 2018 Q4, 2020 Q1 and
most of 2022; the rebuild's budget is highest in exactly those windows (damped
in 2022 by the persistence term). In calm 2017/2019/2021/2023 the rebuild runs at
15–25% equity while the base runs at 100%.

The pre-pause evidence is consistent with this direction but does not prove the
magnitude: the strongest contrarian tilt tested (r20, k=6) reached 0.68 with a
much cruder signal. The vol-state signal is designed to be more asymmetric than
that tilt. **If the measured dev correlation is ≥ 0.60 the design fails the
brief and must be reported as such, not tuned until it passes.**

## 5. What would falsify it

1. **Diversity:** dev daily-return correlation with the 165-day baseline ≥ 0.60.
2. **No premium:** dev CAGR below BIL, or Sharpe < 0.35.
3. **The tilt is not the source:** a sign-flipped (pro-cyclical) placebo has an
   equal or higher Sharpe, or a constant-35%-budget ablation beats the strategy.
4. **All of it is 2020:** both 2016–19 and 2022–23 sub-periods have negative CAGR
   while the full-dev result is positive.
5. **No event effect:** forward 20-day sleeve return after transient vol spikes
   (slope > +0.5, persist < 0.3) is not greater than the unconditional mean, with
   a bootstrap p-value > 0.10.
6. **Underpowered:** fewer than 40 transient-spike events in dev.
7. **Parameter cliff:** a ±1-step change in `tilt_strength` (0.15/0.20/0.25),
   `slope_scale` (0.30/0.35/0.40) or `base` (0.30/0.35/0.40) flips the sign of
   the tilt contribution.
8. **Risk control is the whole story:** removing the drawdown brake improves
   Sharpe by more than the brake's drawdown benefit is worth.

If (1), (2) or (3) fails, the correct outcome is `rejected`, not a re-tune.

## 6. Why this is not the original in disguise

| | Original | Rebuild |
|---|---|---|
| Regime | QQQ vs 165-day SMA | none (no price MA) |
| Signal | realised vol level (ladder) | volatility **term structure** + persistence |
| Direction of risk response | pro-cyclical (cut when vol rises) | contrarian on transient spikes, damped when persistent |
| Composition | 100% TQQQ or ladder to QQQ | ERC QQQ/TQQQ, capped |
| Crash control | armed 4% minute stop | own-equity drawdown brake |
| Holding period | daily, binary | daily, 15–55% risk budget, weeks-long state |
| Expected corr vs base | 1.00 (it *is* the base + overlay) | 0.30–0.55 |
