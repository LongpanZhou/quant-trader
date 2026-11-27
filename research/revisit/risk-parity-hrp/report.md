> **Post-test note (2026-11-27):** this file is the pre-registration, not
> the result. The frozen development result is in `../SUMMARY.md`; the
> full 2016-2026 audit, the post-tune variants and the research-validity
> verdicts are in `../WHY_UNDERPERFORM.md`. The published website curve is
> the freeze named in `../SUMMARY.md`.

# Volatility-State Risk Parity (VSRP) — rebuild of `risk-parity-hrp`

**Status:** design / hypothesis. **Not tested.** Backtests paused by the lead on
2026-11-26; `strategy.py` has not been executed and `result.json` does not exist.
**Dev window (when authorised):** 2016-01-04 → 2023-12-29.
**Holdout:** 2024-01-02 → 2026-10-23 — not inspected by this agent.

---

## 1. Idea extracted from the original

The original agent's `risk-parity-hrp` was a 70%-vol-target / HRP sizing overlay
on the shared 165-day QQQ regime with a 4% armed minute stop. Its genuinely new
content was the risk model, not the regime or the stop.

Two measured facts from that work define the rebuild:

- HRP across QQQ/TQQQ/BIL allocated **99.99% to BIL** (QQQ 0.0089%, TQQQ
  0.0010%); inverse-vol/ERC across the three gives 1.03% / 0.34% / 98.63%. With
  a near-riskless asset in the set, risk parity is a T-bill portfolio.
- QQQ and TQQQ are one factor: 10-year daily correlation **0.99951**, average
  60-day correlation **0.99986**. Equal-risk weights on the pair are ~75% QQQ /
  25% TQQQ, a ~34%-vol sleeve.

So the only honest risk-parity object here is the QQQ/TQQQ pair (a leverage
choice) plus BIL as the defensive leg. There is no second equity risk premium to
diversify into with the available data.

## 2. Hypothesis

**The conditional Sharpe ratio of the equity factor rises after a *transient*
volatility spike and does not rise in a *persistent* high-volatility regime.**

Standard risk parity and vol targeting size by 1/σ, implicitly assuming a
constant Sharpe ratio. If the conditional Sharpe ratio is state-dependent, the
risk budget should follow it: raise risk when short-horizon variance is elevated
relative to its own norm (transient stress, mean reversion), but do **not** raise
it when the long-horizon variance is itself in a high regime (persistent stress,
weak long-horizon risk-return trade-off).

This is the opposite of the original's pro-cyclical vol ladder, and it is the
only design that can plausibly satisfy the brief's < 0.60 correlation rule: the
base is flat exactly when volatility spikes, so a risk budget that rises on
spikes must hold a different subset of days.

## 3. Why the naive rebuild was rejected before coding

Measured on dev before the pause (1 bp, 1-minute marks, 2% band; scripts
`explore_dev.py`, `explore_dev2.py`). These are **exploratory** numbers for
variants that are *not* the final strategy:

| Variant | CAGR | Max DD | Daily corr vs 165d base |
|---|---:|---:|---:|
| 165-day base (reference) | 43.73% | 59.60% | 1.00 |
| 100% TQQQ buy-and-hold | 36.15% | 82.29% | 0.71 |
| Static 75% TQQQ / 25% QQQ | 34.04% | 74.74% | 0.71 |
| ERC QQQ/TQQQ, always invested | 27.04% | 52.69% | 0.72 |
| ERC to a 45% vol target | 25.85% | 51.20% | 0.77 |
| Vol target 60% (no gate) | 45.23% | 74.10% | 0.78 |
| Vol target 60% + cash switch at 90% vol | 50.23% | 58.64% | 0.79 |
| Reversal tilt on the budget (r5, k=6) | 27.19% | 47.32% | 0.73 |
| Reversal tilt (r20, k=6) | 20.18% | 49.20% | 0.68 |
| Realised-Sharpe tilt (60d) | 21.75% | 43.14% | 0.88 |

Conclusion: **every pro-cyclical or always-invested risk-parity variant sits at
0.71–0.83 correlation**, and volatility targeting is *worse* than buy-and-hold
(0.78 vs 0.71) because the vol regime and the trend regime coincide. Stripping
the 165-day gate off the old overlay does not produce a diverse strategy; it
produces the same equity factor with a different leverage.

## 4. Exact rules (primary)

All signals use closes through the prior session. Weights fill at the next
session's open. Full detail in `SPEC.md`.

**Composition (ERC).**
`w_TQQQ = clip(σ_QQQ(60) / (σ_QQQ(60) + σ_TQQQ(60)), 0.10, 0.50)`, `w_QQQ = 1 − w_TQQQ`.
Typical 75/25; sleeve vol ≈ 34%.

**Volatility state.**
`slope = log(σ_QQQ(20) / σ_QQQ(120))`;
`persist = clip((σ_QQQ(120) / median_756(σ_QQQ(120)) − 1) / 0.50, 0, 1)`;
`tilt_raw = clip(slope / 0.35, −1, +1) × (1 − 0.70 × persist)`;
`tilt = 5-day mean of tilt_raw`.

**Risk budget.**
`b = 0.35 + 0.20 × tilt`, capped at `0.18 / sleeve_vol`, then the drawdown
multiplier, then clipped to [0.03, 0.60].

**Own drawdown brake** (hysteresis on the strategy's own equity, prior close):
−12% halves the budget, −20% cuts it to ×0.20; release at −6% / −14%.

**Weights.** `QQQ = b·w_QQQ`, `TQQQ = b·w_TQQQ`, `BIL = 1 − b`. Long-only,
gross ≤ 1.

## 5. Why this is a different strategy, not the old overlay

| | Original | This rebuild |
|---|---|---|
| Regime | QQQ vs 165-day SMA | none (no price MA anywhere) |
| Signal | realised-vol level ladder | volatility **term structure** + persistence |
| Risk response | pro-cyclical (cut when vol rises) | contrarian on transient spikes, damped when persistent |
| Composition | 100% TQQQ or ladder to QQQ | ERC QQQ/TQQQ, TQQQ capped at 50% |
| Crash control | armed 4% minute stop | own-equity drawdown brake |
| Holding period | daily, binary | daily, 15–55% budget, weeks-long state |
| Expected corr vs base | 1.00 (it is the base + overlay) | 0.30–0.55 (to be measured) |

## 6. Results

**None. Backtests paused.** This section will be filled only from a clean run of
`strategy.py` after the lead authorises the dev test. No number below is
estimated or hand-typed.

| Window | 1 bp CAGR / DD / Sharpe | 5 bp | 10 bp | Fills |
|---|---:|---:|---:|---:|
| dev 2016-01-04 → 2023-12-29 | _pending_ | _pending_ | _pending_ | _pending_ |
| 10y (overlaps holdout; lead only) | — | — | — | — |
| 5y (overlaps holdout; lead only) | — | — | — | — |

Correlation with the 165-day baseline on dev: **_pending_**, expected 0.30–0.55,
hard requirement < 0.60.

## 7. Required controls (planned, all reported)

1. **Variants tried:** 12 pre-registered (3 tilt strengths × 2 window pairs ×
   brake on/off). Primary is the middle of each range.
2. **Neighbourhood:** ±1 step for `tilt_strength`, `slope_scale`, `base_budget`,
   `vol_cap` (table, not best cell).
3. **Ablations:** constant 35% budget; tilt without the persistence damper;
   brake off; ERC-only.
4. **Placebo:** sign-flipped tilt and seeded random tilt with the same moments.
5. **Sub-periods:** 2016–19, 2020–21, 2022–23.
6. **Events:** transient-spike count, forward 20-day sleeve return, permutation
   p-value (5,000 draws). < 40 events → underpowered.
7. **Holdout:** one shot by the lead after freeze; not run here.

## 8. Falsifiers (decision rule)

The rebuild is **rejected** if any of the following holds:

1. dev correlation with the 165-day baseline ≥ 0.60;
2. dev CAGR below BIL or Sharpe < 0.35;
3. the sign-flipped placebo or the constant-35% ablation has an equal or higher
   Sharpe;
4. both 2016–19 and 2022–23 have negative CAGR while full dev is positive;
5. the forward 20-day return after transient spikes is not above the
   unconditional mean (p > 0.10);
6. the ±1-step neighbourhood flips the sign of the tilt contribution.

Passing requires (1)–(6) to clear **and** the audit to pass. There is no
`retired_overlay_only` outcome: this is a complete allocation rule, not a filter.

## 9. Honest risks

- **The contrarian bet can be wrong for years.** 2022 is the stress case: a
  persistent high-vol bear. The persistence damper is the only protection, and
  it is a single mechanism with no out-of-sample evidence yet.
- **Low return in calm bull markets.** The strategy deliberately runs at 15–25%
  equity in 2017/2019/2021/2023 while the base runs at 100%. It will lag badly
  in those years; that is the price of decorrelation.
- **Single factor, single country.** QQQ/TQQQ/BIL gives no bond or gold
  diversification, so the risk-parity label is limited to the leverage
  dimension. The data constraint is documented in `SPEC.md` §1.
- **No leverage and no shorts** (bt enforces weights ≥ 0 and sum ≤ 1), so the
  budget cannot exceed 100% and the strategy cannot express a relative-value
  view between QQQ and TQQQ.
- **1-minute marks** are used; the drawdown brake uses daily closes for its
  signal, so an intraday crash does not trigger it until the close.

## 10. Reproduction (after authorisation)

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
python research\revisit\risk-parity-hrp\strategy.py --controls
```

Writes `result.json` (dev windows, benchmarks, correlation, controls). The
holdout is run once by the lead on the frozen commit.

## 11. Provenance

See `PROVENANCE.md`. Every rule is mapped to a source or explicitly marked
"own design". The two most important attributions: the ERC composition comes
from Asness-Frazzini-Pedersen (2012) and the ERC literature; the contrarian
volatility-state budget is an **own hypothesis**, supported only indirectly by
the volatility/return-timing literature — it is not a published rule.
