# Momentum with a crash brake on TQQQ — pre-registration

**Slug:** `momentum-crash-filter`
**Status:** frozen before the final 1-minute development run.
**Window:** 2016-01-04 → 2023-12-29 only. The 2024-01-02 → 2026-10-23
holdout is not loaded, inspected or used for selection by this study; every
`bt.panel` call ends at 2023-12-29.
**Bar:** TQQQ 2016-01-04 → 2023-12-29 is **36.72% CAGR / 82.29% max DD / 0.82
Sharpe** on 1-minute marks. Pass = dev CAGR > 36.72% and max DD < 82.29%
(ideally < 60%). A lower-CAGR but much better Sharpe/Calmar result is reported
as risk-adjusted, not as a pass.

This is a standalone strategy. It does not use the 165-day QQQ SMA, the 4%
intraday stop, the old drawdown-regime exit, the old event-risk overlay, the ML
crash classifier, the overnight-only structure, or the EMA/vol-target structure
of `fast-trend-vol`. It has no stop-loss and no intraday override.

---

## 1. Mechanism

TQQQ is a 3× daily-reset Nasdaq-100 fund. Two empirical regularities do the
work:

1. **Momentum persists at the 1–3 month horizon.** QQQ total return over the
   prior 20 and 60 sessions is positively autocorrelated at these horizons
   (Jegadeesh & Titman 1993; Moskowitz, Ooi & Pedersen 2012). A positive
   20/60-session return is a simple, causal proxy for "the equity risk premium
   is currently being paid". Holding TQQQ while either horizon is positive
   keeps the strategy in the long bull legs (2017, 2019, 2020H2, 2021, 2023)
   without a slow 100–200-day moving average.
2. **Crashes are partly predictable from their own dynamics.** Volatility
   clusters (Engle 1982; Bollerslev 1986), and a fast drawdown that is
   accompanied by a volatility spike or a sharp 3-day loss is more likely to
   continue than a quiet drift down. For a 3× fund the asymmetry is large: a
   20% QQQ drawdown is roughly a 45–60% TQQQ drawdown because of the daily
   reset and the path-dependent variance drag (Avellaneda & Zhang 2010; Cheng &
   Madhavan 2009). Cutting the first part of such an episode is worth far more
   than the CAGR given up by occasionally re-entering late.

The strategy is therefore a **trend-following core with an explicit crash
brake**, not a default-long overlay:

- The **momentum gate** decides whether TQQQ is an eligible asset. It is
  deliberately loose ("either 20 or 60 sessions positive") because TQQQ's
  recoveries are violent and a strict "both positive" gate re-enters too late.
- The **crash brake** overrides the gate. It requires a *fast drawdown from a
  20-session high* **and** at least one fast-stress confirmation (a 5/20-day
  volatility spike or a sharp 3-day loss). A slow grind lower does not trigger;
  a one-day gap without a prior drawdown does not trigger.
- **Re-entry** is a price-confirmation rule: a close at or above the prior
  5-session high **and** a positive 20-session return. This is the
  "stabilisation/reclaim" leg. It is faster than waiting for the 60-session
  momentum to turn positive, which is what allows the strategy to participate
  in V-shaped recoveries such as April 2020.

Why this can beat TQQQ: TQQQ's 2016–2023 CAGR is high because the bull years
compound strongly, but the 2018 Q4, 2020 COVID and 2022 bear episodes account
for the 82% drawdown. If the brake avoids the majority of the 2020 and 2022
declines while the momentum gate keeps most of the bull years, the compounded
result can be higher with a much lower tail. The strategy does not need to beat
TQQQ every year; it needs to beat it over the full window with a smaller
drawdown.

## 2. Exact rules

All signals are computed at the close of session `t` from QQQ regular-session
daily bars (open, close), using data through `t` only. Weights are set at that
close and filled at the **next session's open** (`bt.run`, 2% band, next-open
fills). No full-sample statistics are used.

Let `C_t` be the QQQ close of session `t`.

```
r20_t    = C_t / C_{t-20} - 1
r60_t    = C_t / C_{t-60} - 1
r_t      = ln(C_t / C_{t-1})
RV5_t    = stdev(r_{t-4..t})  * sqrt(252)
RV20_t   = stdev(r_{t-19..t}) * sqrt(252)
VA_t     = RV5_t / RV20_t
DD20_t   = C_t / max(C_{t-19..t}) - 1
R3_t     = ln(C_t / C_{t-3})
HI5_t    = max(C_{t-5..t-1})          # prior 5 sessions, excludes t
```

**Momentum state** (eligible to hold TQQQ):

```
M_t = (r20_t > 0) or (r60_t > 0)
```

The first 60 sessions (2016-01-04 → 2016-03-28) have no 60-session history in
the 1-minute archive. The strategy is default-long TQQQ during that warm-up;
the crash brake is active from the first session in which `DD20` and `VA`/`R3`
are defined (20 sessions). This is a real limitation, not a choice.

**Crash trigger** (evaluated at the close, overrides `M_t`):

```
CRASH_t = (DD20_t < -0.08) and ( (VA_t > 1.50) or (R3_t < -0.06) )
```

**State machine** (`off` = defensive):

```
off_0 = False
for t = 0..n-1:
    if off_{t-1}:
        if (C_t >= HI5_t) and (r20_t > 0):     # reclaim + short momentum
            off_t = False
    elif CRASH_t:
        off_t = True
    else:
        off_t = False

TQQQ weight_t = 1 if (M_t and not off_t) else 0
BIL  weight_t = 1 - TQQQ weight_t
```

Execution: the target for session `t` is written on the 15:59 bar and fills at
the next session's 09:30 open. Every other bar in session `t` carries the
position already held. No intraday signal, no stop, no short, no leverage above
100%.

### Pre-registered core parameters

| Parameter | Value | Role |
|---|---:|---|
| `mom_fast` | 20 sessions | fast momentum horizon |
| `mom_slow` | 60 sessions | slow momentum horizon |
| `mom_buf` | 0.0% | strict positive momentum (no buffer) |
| `dd_win` | 20 sessions | fast drawdown lookback |
| `dd_t` | −8.0% | QQQ drawdown from 20-session high |
| `va_t` | 1.50 | RV5 / RV20 volatility-spike threshold |
| `loss_t` | −6.0% | 3-day QQQ log-return crash threshold |
| `reentry` | 5 sessions | prior-high reclaim window |
| `re_mom` | yes | re-entry also requires r20 > 0 |
| `defensive` | BIL | cash proxy |

The thresholds are round, mechanism-driven values, fixed after a **daily-mark
screen** and before the final 1-minute run. The screen is not the headline; the
1-minute run below is the single final evaluation. The volatility threshold
1.50 is a 50% spike in 5-day versus 20-day realised vol; the 8% drawdown is
roughly a 24% TQQQ drawdown; the 6% 3-day QQQ loss is roughly an 18% TQQQ loss.

## 3. Pre-registered 8-cell grid

One-at-a-time neighbours around the core, everything else fixed. The grid is a
**plateau test**, not a search for the best cell.

| # | Cell | Change |
|---:|---|---|
| 1 | **core** | — |
| 2 | dd early | `dd_t = −6.0%` |
| 3 | dd late | `dd_t = −10.0%` |
| 4 | vol tight | `va_t = 1.80` |
| 5 | loss tight | `loss_t = −4.0%` |
| 6 | loss loose | `loss_t = −8.0%` |
| 7 | re-entry fast | `reentry = 3` |
| 8 | re-entry slow | `reentry = 7` |

Additional diagnostics (not part of the 8-cell selection grid): momentum
buffers −0.5%/−1%/−2%, `dd_win` 15/30, the no-crash variant, the momentum-only
variant, the crash-only variant, the component legs (dd+loss, dd+vol, loss only,
vol only), and a 10/15/20-day re-entry horizon.

## 4. Expected effect (written before the final 1-minute run)

- 1 bp: CAGR 39–44%, max DD 42–50%, Sharpe 0.92–1.02.
- 5 bp / 10 bp: CAGR 40–43% / 38–41%; the pass should survive 10 bp because
  turnover is low (~150 fills, ~350× start equity over eight years).
- TQQQ exposure: 78–82% of sessions; BIL 18–22%.
- Daily-return correlation to TQQQ: 0.65–0.75.
- Yearly shape: strong 2020 and 2022 relative performance; weak 2016 (no
  warm-up), 2018 (choppy bear with false alarms), 2019/2021/2023 below TQQQ
  because the momentum gate and the re-entry lag give up part of the upside.
- The edge is expected to be concentrated in crash avoidance: ex-2020 CAGR
  should still be positive and above TQQQ's ex-2020 CAGR (about 27.8% on daily
  marks), but it will be well below the headline.

## 5. Falsifiers (written before the final run)

The hypothesis fails if any of these is true:

1. **Headline failure:** dev 1 bp CAGR ≤ 36.72% or max DD ≥ 82.29%.
2. **No plateau:** fewer than 6 of the 8 pre-registered grid cells pass, or the
   core collapses by more than ~5 pp CAGR versus the daily screen (42.3%).
3. **No timing value:** a circular-shift placebo that preserves the exact
   exposure-spell lengths and exposure fraction matches the observed CAGR and
   drawdown (observed CAGR percentile < 90, or more than 20% of placebo draws
   above the 36.72% bar).
4. **Look-ahead:** truncating the 1-minute panel at 2018-12-21, 2020-03-12 or
   2022-09-13 changes any weight before the cut.
5. **Only 2020:** ex-2020 CAGR ≤ TQQQ's ex-2020 CAGR. (The strategy is allowed
   to earn a large part of its edge in crash years, but not all of it. Ex-2022
   and ex-both are reported as diagnostics, not pass criteria, because TQQQ
   without its worst year is not a meaningful bar.)
6. **Old strategy in disguise:** the result is reproduced by the 165-day SMA +
   4% stop, the old drawdown-regime exit, or the `crash-early-warning`
   default-long composite. The state path and exposure profile are reported so
   this can be checked.

## 6. Relation to existing work (checked before writing this)

- `research/new/crash-early-warning`: default 100% TQQQ; de-risks on a
  3-component score (vol acceleration + drawdown acceleration + gap stress)
  with B mandatory; re-enters on a 10-day high. **This strategy has a momentum
  gate (20/60), no gap-stress component, no drawdown-acceleration velocity
  term, a 5-day reclaim and a different 3-day-loss leg.** It is not default
  long: it stands aside on negative momentum even without a crash.
- `research/new/fast-trend-vol`: 20/50-day EMA trend + volatility target +
  daily/intraday crash brakes. **No EMA, no vol target, no intraday override;
  the trend signal is total-return momentum, not a price/EMA comparison.**
- `research/new/vol-of-vol-timing`: vol-of-vol / Parkinson range risk state.
  **No range estimator, no vol-of-vol, no V-recovery re-risk.**
- `research/new/cross-asset-momentum`: dual momentum across QQQ/SPY/BIL.
  **Single signal asset (QQQ), no cross-asset ranking, 3× implementation.**
- `research/agents2/drawdown-regime` and `research/revisit/drawdown-regime`:
  exits on the level of QQQ drawdown from a 52-week high on top of the 165-day
  SMA + 4% stop. **No SMA, no stop, 20-session drawdown plus a fast-stress
  confirmation.**
- `research/agents2/stop-reentry-recovery`: post-4%-stop re-entry. **No stop.**
- `research/agents2/vol-scaled-crash-stop`: ATR-scaled 4% stop. **No stop.**
- `research/agents2/overnight-crash-filter`: overnight-only with a 20-day vol
  filter. **Holds all day.**
- `research/agents2/ml-crash-overlay-winner`: walk-forward logistic classifier
  on a 165-day SMA base. **Deterministic rule, no ML, no slow MA.**
- `research/agents2/event-risk-overlay`: FOMC/CPI/OpEx calendar events. **No
  calendar.**
- `research/new/ml-regime-v2`: walk-forward ML with momentum signs (60/100/150).
  **No ML, 20/60 only.**

No code or parameters are copied from any of them.

## 7. Diagnostics that will be reported

- 1-minute headline at 1/5/10 bp; daily screen for comparison.
- Yearly returns, the 2018 Q4 / 2020 COVID / 2022 bear attribution, and the
  max-DD peak/trough.
- All 8 pre-registered grid cells, plus the wider sensitivity table.
- Component rules (momentum only, crash only, dd+loss, dd+vol, loss only, vol
  only, no re-entry momentum) on daily marks.
- Circular-shift placebo (500 draws) preserving spell lengths and exposure.
- Cut tests at 2018-12-21, 2020-03-12 and 2022-09-13 (weights before the cut
  must be identical).
- Ex-2020, ex-2022 and ex-both CAGR/DD/Sharpe, against TQQQ on the same
  exclusions.
- Honest verdict: pass/fail, whether the edge is crash timing or just lower
  exposure, and the holdout risk.
