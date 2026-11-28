> **Post-test note (2026-11-27):** this file is the pre-registration, not
> the result. The frozen development result is in `../SUMMARY.md`; the
> full 2016-2026 audit, the post-tune variants and the research-validity
> verdicts are in `../WHY_UNDERPERFORM.md`. The published website curve is
> the freeze named in `../SUMMARY.md`.

# Deep Drawdown Recovery (DDR) — standalone rebuild of `drawdown-regime`

**Status: DESIGN ONLY. Backtests paused (2026-11-26). No strategy backtest has
been run since the pause; no `result.json` has been generated.** This document
is the pre-registered hypothesis, specification, provenance and falsification
plan. The lead must authorise the test before `strategy.py --run` is used.

---

## 1. What the original strategy actually was

`research/agents2/drawdown-regime` held the round-1 trend base (100% TQQQ while
QQQ's prior close is above its 165-day SMA, else BIL) and added one rule that
survived: **halve the intraday stop from 4% to 2% while QQQ is at least 8%
below its 52-week high**. The position-level version of the idea — move to BIL
when the drawdown exceeds 5/10/15% — was tested and failed, even with the trend
base underneath it.

So the extracted idea is narrower than "drawdown is a regime": *the depth of
QQQ's drawdown changes the risk of holding leveraged equity*. The old strategy
expressed that only as a stop. A rebuild that merely strips the 165-day gate
leaves the same continuous TQQQ-beta trade with a different trigger, which is
what the pre-pause tests confirmed (§9).

## 2. New hypothesis

> After a deep drawdown, the **confirmed recovery** is a distinct, time-limited
> return state. A strategy that is flat most of the time, enters only when a
> ≥20% QQQ drawdown has turned (a 20-session high), holds for a fixed three
> months, and then waits for the drawdown to heal can capture that state with
> low exposure and low correlation to slow trend-following.

This is deliberately *not* a de-risking rule. It uses the drawdown as an
**arming condition for re-risk**, which is the one use the pre-pause evidence
did not reject: unconditional 20-day forward TQQQ returns were highest in the
−5…−8% bucket and positive at ≤−20%, while a *binary exit* at those levels was
destroyed by whipsaw and late re-entry.

The prior is genuinely negative. AQR's *Hold the Dip* (2025) finds that buying
weakness at a weeks-to-months horizon does not work on average; the only reason
to test DDR is that it requires a confirmed turn rather than buying the decline,
and that it uses a fixed, short holding period instead of holding through the
bear market. If the confirmation does not change the result, the area should be
retired.

## 3. Universe and data

| Role | Asset | Why |
|---|---|---|
| Signal | QQQ | drawdown from the 52-week high; the same reference the original used |
| Risk | TQQQ | 3× QQQ, the return driver the original monetised |
| Cash | BIL | risk-off asset, carries the T-bill rate |

Local data check: `data/intraday-hf/` has adjusted 1-minute and daily QQQ /
TQQQ / BIL from 2015 (daily) and 2016-01-04 (1-minute). The SPY cache in
`data/cache/dukascopy/` contains only 2026 files, so SPY, sectors, bonds, gold
and volatility products are **not available for 2016–2023** without a new data
fetch. The design is therefore constrained to QQQ/TQQQ/BIL. If the lead later
authorises daily TLT/GLD/VIX data, a cross-asset extension is possible, but it
is not part of this frozen spec.

Warmup: the 52-week high needs 252 daily closes. The 2015 daily parquet supplies
them, so the signal is fully warmed at the 2016-01-04 dev start.

## 4. Signal

All values are known at the **open** of session *t* (i.e. computed from daily
closes through *t−1*):

```
hi252(t) = max(QQQ_close[t-252 .. t-1])
dd(t)    = QQQ_close[t-1] / hi252(t) - 1          # drawdown from the 52-week high
hi20(t)  = max(QQQ_close[t-20  .. t-1])           # prior 20-session high
lo20(t)  = min(QQQ_close[t-20  .. t-1])           # prior 20-session low
```

No moving average of 100–250 days is used anywhere. `hi20`/`lo20` are rolling
extremes, not averages.

## 5. Exact rules

1. **Arm.** The strategy is armed for a new recovery attempt when `dd(t) ≤ −20%`.
2. **Enter.** While armed and flat, buy 100% TQQQ at session *t*'s open when
   `QQQ_close[t−1] > hi20(t)` — the first confirmed 20-session high after the
   deep drawdown.
3. **Hold.** Hold for exactly **60 sessions** (≈3 months).
4. **Failure exit.** Exit to BIL at the next open if, during the hold,
   `QQQ_close[t−1] < lo20(t)` (a close below the prior 20-session low).
5. **Re-arm.** After any exit the strategy disarms and tracks the lowest drawdown
   since the exit, `ref` (initialised to `min(dd_exit, −5%)`). It re-arms only
   when `dd(t) ≥ ref + 5 pp` — a 5 pp recovery from the local low. Because the
   reference is capped at −5%, a new 52-week high always re-arms it. This
   prevents re-entering the same failed bounce and allows a later recovery
   attempt.
6. **Sizing.** 100% TQQQ inside a window, 100% BIL otherwise. Long-only, no
   leverage beyond 100% TQQQ, no shorts, weights sum to ≤ 1.
7. **Fills.** Decisions use closes through *t−1*; the target is set on the prior
   session's last bar and fills at session *t*'s first bar open, with the 2%
   rebalance band. Equity is marked on 1-minute bars.

Parameters (all round, chosen a priori from the mechanism, not fitted):
`window=252, deep_dd=0.20, entry_break=20, hold=60, exit_low=20, rearm=0.05`.

## 6. Holding period, turnover and capacity

- Holding period: 60 sessions, cut short by the 20-session-low exit. Expected
  5–8 windows over 2016–2023, i.e. 15–25% exposure.
- Turnover: 2 fills per window plus band rebalances; roughly 40–80 fills over
  8 years. Capacity is not a constraint at this size.
- The strategy is flat overnight in BIL outside windows, so it does not earn
  the overnight TQQQ drift except inside the windows. That is the explicit
  trade: less time in the market, much lower drawdown.

## 7. Expected correlation with the old base

The 165-day baseline is invested ~78.5% of dev sessions. DDR is expected to be
invested 15–25%. If most of DDR's invested days fall inside the baseline's
invested days (recoveries usually occur once the slow trend has turned), then

```
corr ≈ overlap / sqrt(exposure_DDR * exposure_base)
     ≈ (0.8 * exposure_DDR) / sqrt(exposure_DDR * 0.785)
```

At 15% exposure: ≈ 0.35. At 25%: ≈ 0.45. **Expected range 0.30–0.50**, target
below 0.50 with a hard limit of 0.60.

The early-recovery entries should *help*: the first 20-session high after a
bottom often occurs before QQQ reclaims its 165-day SMA (e.g. April 2020), so
the overlap is lower than the formula's 0.8 assumption.

## 8. Pre-registered falsifiers

The test fails, and the area is retired as `overlay_only`, if any of these hold:

| # | Falsifier |
|---|---|
| F1 | Dev CAGR < 8%, or dev max drawdown > 35% (dominated by a simple QQQ/BIL mix). |
| F2 | Daily-return correlation with the 165-day baseline ≥ 0.60. |
| F3 | Fewer than 5 windows, or a block-bootstrap p-value > 0.10 on the episode returns. |
| F4 | Removing the single best window drops CAGR below 3% (one-event dependence). |
| F5 | The `breakout_only` control (no 20% drawdown arm) has CAGR within 2 pp and a higher Sharpe — the drawdown condition adds nothing. |
| F6 | The 2022–23 sub-period drawdown exceeds 25% — the bear-rally failure mode is not controlled. |
| F7 | The 20-session-low exit does not reduce max drawdown versus a pure fixed 60-session hold. |

If F1 and F5 both hold, the honest conclusion is that the drawdown/underwater
area contains no standalone strategy and the original should be marked
`retired: overlay-only` for good.

## 9. Evidence available before the pause (not re-run)

These numbers were computed on 2026-11-26 **before** the pause order, on the dev
window 2016-01-04…2023-12-29, with 1 bp costs and 1-minute marks. They are kept
as design evidence only; no DDR result exists yet. The scripts `explore.py`,
`sweep.py` and `sweep2.py` in this folder are the pre-pause exploration; they
are not part of the frozen design and must not be run while the pause is on.

**Unconditional forward TQQQ returns by QQQ drawdown bucket (dev):**

| dd bucket | days | fwd 5d | hit | fwd 20d | hit | fwd 60d | hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0…−3% | 1,028 | +1.02% | 62% | +2.84% | 66% | +7.68% | 69% |
| −3…−5% | 231 | +0.95% | 55% | +6.25% | 68% | +15.93% | 79% |
| −5…−8% | 234 | +1.38% | 62% | +9.37% | 82% | +21.95% | 86% |
| −8…−12% | 158 | +0.60% | 53% | +2.71% | 61% | +16.90% | 77% |
| −12…−20% | 155 | +0.66% | 59% | +1.81% | 56% | +14.58% | 63% |
| ≤ −20% | 206 | +1.29% | 55% | +5.01% | 53% | +11.96% | 56% |

The −5…−8% bucket is the best at 20 days; deep drawdowns are positive but
noisy. That is why DDR waits for a confirmed turn instead of buying the decline.

**Direct rebuilds of the old de-risking idea (dev, 1 bp):**

| Variant | CAGR / DD | corr vs 165d |
|---|---:|---:|
| 165-day baseline | 45.46% / 58.76% | 1.00 |
| exit at dd ≤ −5%, re-enter at −2% | 25.47% / 53.64% | 0.65 |
| exit at dd ≤ −8% / −2% | 30.54% / 53.81% | 0.75 |
| exit at dd ≤ −12% / −5% | 35.63% / 54.01% | 0.86 |
| trough-recovery exit −15% / +5pp | 45.99% / 54.41% | 0.85 |
| 3-state ladder 8/15 | 35.42% / 47.23% | 0.90 |
| de-lever to QQQ at −5/−10% | 28.31% / 44.24% | 0.84 |
| underwater ≥ 180 sessions → BIL | 32.79% / 76.68% | 0.72 |
| continuous scale, 15% depth | 28.29% / 40.27% | 0.89 |
| contrarian: long at −10%, exit at −5% | 17.42% / 75.20% | 0.33 |
| hold QQQ instead of TQQQ, gate −8% | 12.43% / 18.72% | 0.75 |

Every decent-return variant has correlation ≥ 0.65; the only low-correlation
one (contrarian) has a 75% drawdown. This is the evidence that killed the
"strip the base" approach and motivates the event-window redesign.

**Stop-only controls (always long TQQQ, no regime gate):**

| Variant | CAGR / DD | corr |
|---|---:|---:|
| TQQQ buy & hold | 36.15% / 82.29% | 0.72 |
| 4% stop, MA20-armed | 50.78% / 60.98% | 0.71 |
| 4% stop, always armed | 57.20% / 60.22% | 0.68 |
| 2% stop, MA20-armed | 63.56% / 57.18% | 0.68 |
| 2% at dd ≤ −8%, else 4% | 61.10% / 53.21% | 0.74 |

The stop family makes money but keeps a 52–61% drawdown and correlates 0.68–0.74
with the base. It is an overlay, not a standalone strategy.

## 10. Controls to run with the test (after authorisation)

1. `breakout_only`: any 20-session high, no drawdown arm (F5).
2. `deep_only`: enter on the first day of a ≥20% drawdown, no breakout.
3. Fixed-hold-only: remove the 20-session-low exit (F7).
4. Circular-shift placebo: shift all entries by 63 sessions, matched exposure.
5. QQQ instead of TQQQ in the window (asset robustness).
6. ±1-step neighbourhood on all five parameters (`NEIGHBOURS` in `strategy.py`).
7. Sub-periods 2016–19, 2020–21, 2022–23; leave-one-window-out.
8. Block bootstrap on episode returns (F3).

## 11. Results

**TBD — no backtest has been run.** When authorised, `strategy.py --run` writes
`result.json` in this folder with dev 1/5/10 bp, the episode list, the
correlation vs the 165-day baseline, and the benchmark. The lead runs the
holdout once on the frozen build; this agent will not inspect 2024–2026.

| Window | 1 bp CAGR | 1 bp DD | 5 bp CAGR | 5 bp DD | 10 bp CAGR | 10 bp DD |
|---|---:|---:|---:|---:|---:|---:|
| Dev 2016-01-04…2023-12-29 | TBD | TBD | TBD | TBD | TBD | TBD |
| 10y (overlaps holdout) | — | — | — | — | — | — |
| 5y (overlaps holdout) | — | — | — | — | — | — |

## 12. Provenance

| Idea / claim | Source | Role |
|---|---|---|
| Drawdown-based de-risking cuts volatility and drawdown but lowers CAGR and does not improve Sharpe/Sortino; the losses come from underexposure in recoveries and whipsaws in shallow drawdowns | Strahle (2025), *How Does Reducing Exposure During Drawdowns Impact Portfolio Performance?* — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7542498 | supports the decision to abandon the de-risking rebuild |
| Drawdown rules trade expected return for risk; no free drawdown control | van Hemert et al. (2020), *Drawdowns* — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3583864 | supports assumption |
| Buying weakness at a weeks-to-months horizon does not earn reliable alpha; "value investing at a momentum horizon" | AQR (2025), *Hold the Dip* — https://www.aqr.com/Insights/Research/Alternative-Thinking/Hold-the-Dip (summary: https://alphaarchitect.com/is-trend-following-better-than-buy-the-dip/) | **negative prior** for DDR; the confirmation filter is the test |
| No reliable dip-buying outperformance vs passive | Bonini, Shohfi & Simaan (2024), *Buy the dip?*, European Financial Management 30(4) — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3835376 | negative prior |
| Stop-loss rules add value only when returns have positive serial correlation | Kaminski & Lo (2014), *When do stop-loss rules stop losses?* — https://doi.org/10.1016/j.finmar.2013.07.001 | why the old stop overlay worked, and why it is not a strategy |
| Time-series momentum / breakout confirmation | Moskowitz, Ooi & Pedersen (2012), *Time series momentum*, JFE 104(2) — https://doi.org/10.1016/j.jfineco.2011.11.003 | supports the 20-session breakout as a turn confirmation |
| Drawdown constraints are costly insurance | Grossman & Zhou (1993) — https://doi.org/10.1111/j.1467-9965.1993.tb00044.x; Chekhlov, Uryasev & Zabarankin (2005) — https://math.columbia.edu/~chekhlov/ChekhlovUryasevZabarankin--03-2004.pdf | framing |
| The unconditional forward-return table and all pre-pause numbers in §9 | Own test (pre-pause, 2026-11-26) | design evidence; not a DDR result |

Constraint provenance: only QQQ/TQQQ/BIL have local 2016–2023 history
(`data/intraday-hf/`); the local SPY cache covers 2026 only.

## 13. Honest risks

1. **Negative prior.** This is a conditional dip-buy. The published evidence
   says dip-buying at this horizon fails. F5/F1 are designed to catch that.
2. **Few events.** 5–8 windows over 8 years. Even if the result is good, it is
   a handful of trades and the bootstrap may be insignificant.
3. **2022 is the acid test.** Bear-market rallies produce confirmed 20-session
   highs that fail. The re-arm rule limits re-entry but cannot eliminate the
   losses; F6 makes this explicit.
4. **TQQQ path dependency.** A 60-session hold in a 3× ETF is exposed to
   volatility drag; the 20-session-low exit is the only protection.
5. **No new assets.** The design is constrained to one equity factor; a
   genuinely different return driver (bonds/gold) would need new data.

## 14. Status

- `retired_overlay_only` is the **default expectation** if F1/F5/F6 fail.
- `passed` requires: dev CAGR ≥ 8%, DD ≤ 35%, correlation < 0.60, ≥5 windows,
  and survival of the controls above.
- No `result.json` yet, by instruction. The lead runs the holdout once after
  audit and freeze.
