> **Post-test note (2026-11-27):** this file is the pre-registration, not
> the result. The frozen development result is in `../SUMMARY.md`; the
> full 2016-2026 audit, the post-tune variants and the research-validity
> verdicts are in `../WHY_UNDERPERFORM.md`. The published website curve is
> the freeze named in `../SUMMARY.md`.

# Expiry-cycle strategy (rebuild of `event-risk-overlay`)

**Status: SPEC FROZEN, BACKTEST PAUSED — no results yet.**
Development period: 2016-01-04 → 2023-12-29. Holdout 2024-01-02 → 2026-10-23
is **not** loaded by `strategy.py` unless the lead passes `--with-holdout`.

Original: `research/agents2/event-risk-overlay` (10y 67.06% / 40.65%, 5y 53.83% /
35.88% at 1 bp, as an overlay on the 165-day base).

---

## 1. What the original did, and what is actually new

The original was **99% the round-1 winner**: a QQQ 165-day SMA regime holding
TQQQ/BIL, plus a 4% armed minute stop, with one extra rule — be in BIL for the
intraday session on monthly option-expiry Fridays. Everything that made its
equity curve was the base; the overlay only decided 12 sessions a year.

The genuinely new content is the **event fact**, not the overlay:

> On the monthly option-expiry session (third Friday, holiday-rolled), the
> equity session itself carries a large negative open→close drift, while the
> overnight into it and the sessions around it are normal or better.

That fact is independent of any regime filter — it is a property of the
calendar, measured on all sessions, with no QQQ moving average anywhere. So the
idea is **not** overlay-only; it is a standalone calendar effect. What *is*
overlay-only is the way the original monetised it.

## 2. Hypothesis (written before any rebuild backtest)

**H1.** The expiry session is the one systematically weak session of the monthly
expiry cycle because dealer gamma rolls off and covered-call writers roll
exposure into the same print. The weakness is a temporary liquidity concession,
not new information about cash flows.

**H2.** Therefore a calendar-only strategy that owns the cycle but never holds
through the expiry session earns a *flow* premium that is structurally
unrelated to trend following, and should have low correlation with the 165-day
base.

**H3.** Because the concession is temporary, the sessions immediately after
expiry should be at least normal, so the window can be held long-only.

**What the harness forces.** `research/bt.py` accepts only
non-negative weights (`_check_inputs` rejects `weights < -1e-9`), so the
negative expiry-session drift cannot be shorted. The rebuild therefore
monetises the *complement*: it is long the cycle and flat the expiry session.
This is a real constraint, not a design choice, and it is the main reason the
rebuild could fail while the underlying effect stays true.

## 3. Evidence collected on the development sample (pre-pause)

From `explore.py`, all sessions 2016-01-04 → 2023-12-29, 1-minute TQQQ, no
regime filter, no base weights. 2,012 sessions, 96 expiry sessions.

| | n | TQQQ open→close | TQQQ close→open | TQQQ close→close | sd(o2c) | % negative |
|---|---:|---:|---:|---:|---:|---:|
| Expiry session | 96 | **−83.9 bp** | +21.0 bp | −65.4 bp | 331 bp | **58%** |
| Other days | 1,916 | +14.6 bp | +10.8 bp | +25.8 bp | 334 bp | 44% |
| Other Fridays | 311 | +22.3 bp | −1.5 bp | +21.5 bp | 342 bp | 41% |
| QQQ on expiry | 96 | −28.4 bp | — | — | — | — |
| QQQ other days | 1,916 | +5.4 bp | — | — | — | — |

Expiry vs other Fridays, open→close: **−106.2 bp, t = −2.72**. The effect is
the same sign in all three dev sub-periods (2016-19 −54.7 bp, 2020-21 −164.9 bp,
2022-23 −61.2 bp), in 6 of 8 calendar years (2016 −10.4, 2017 +12.3, 2018 −159.0,
2019 −61.6, 2020 −253.3, 2021 −76.5, 2022 −69.3, 2023 −53.0), and in QQQ at 1/3
the size — exactly what a 3× wrapper should show.

Session offsets around expiry (TQQQ open→close, bp):

| offset | −5 | −4 | −3 | −2 | −1 | **0** | +1 | +2 | +3 | +4 | +5 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| mean | −3.7 | **+49.2** | **+34.8** | −1.5 | **+48.3** | **−83.9** | **+45.1** | +16.2 | **+34.0** | −19.6 | +16.2 |
| median | 46.3 | 79.9 | 49.3 | 0.6 | 58.0 | −44.2 | 78.1 | 10.9 | 17.6 | −7.9 | 9.3 |

The single robust feature is offset 0. Everything else is noise around the
+14.6 bp unconditional daily mean — which is why the window is treated as a
*carry vehicle*, not as a second signal, and why F1 (placebo) is the decisive
falsifier.

## 4. Spec (frozen)

```
Universe   QQQ, TQQQ, BIL, 1-minute regular session.
Calendar   expiry = third Friday of the month; if that Friday is a full-day NYSE
           holiday it rolls back to the prior session (Good Friday cases:
           2019-04-18, 2022-04-14, 2026-06-18). NYSE holidays from the standard
           observance rules (computus for Good Friday, Juneteenth from 2022).
           Nothing here uses price data.

Signal     the session is in the window  W = {expiry-4 .. expiry-1} U {expiry+1 .. expiry+2}
           (6 sessions: Mon-Thu before expiry, Mon-Tue after). Session offsets,
           not weekdays, so a Thursday expiry shifts the block by one session.

Position   Long TQQQ during W, held through the intervening nights.
           BIL on the expiry session and on every other session.
           On the last invested session of each block, exit on the 15:59 print
           (target set at bar last-1, filled at the open of the last bar).

Sizing     100% TQQQ inside W, halved to 50% when QQQ's 20-session realised
           volatility through the prior close exceeds 25% annualised.
           The vol rule only ever cuts exposure.

Risk       no stop, no intraday leverage beyond TQQQ's own 3x, no shorts,
           no position of any kind outside W; ~29% of sessions designated,
           ~71% in T-bills. No 100-250 day moving average of QQQ/TQQQ/SPY/NDX
           appears anywhere in build_weights.

Fills      harness convention: target set at bar i fills at open(i+1), 2% band,
           1 bp headline and 5/10 bp reported.
```

Exposure is concentrated in two blocks per month, so the strategy is out of the
market for the expiry session and for roughly 16 of every 20 sessions.

## 5. Why this is not the old base

| Check | Old | Rebuild |
|---|---|---|
| Gate | QQQ close vs 165-day SMA | none — calendar only |
| Time in market | ~79% of sessions | ~29%, fixed by the calendar |
| Holding period | months (until the regime flips) | 4 and 2 sessions, monthly |
| Stop | armed 4% minute stop | none |
| Sizing | 100% TQQQ / 100% BIL | 100%/50% TQQQ, BIL otherwise |
| What decides the position | trend + stop | the expiry date |

`build_weights` imports nothing from the original and never reads a weight
matrix. The 165-day base is reconstructed **only** inside
`reference_165d_daily_returns`, a benchmark function that `build_weights` never
calls, because the brief requires the correlation number. If the auditor
prefers, that function can be deleted and the correlation supplied by the lead.

## 6. Falsifiers (pre-registered — the run decides, not me)

| id | test | fails if |
|---|---|---|
| **F1** | cycle window vs the same "4 before + 2 after, skip the anchor Friday" shape anchored one week and two weeks later | primary CAGR ≤ either placebo CAGR |
| **F2** | risk | dev Sharpe < 0.50 or dev max DD > 30% |
| **F3** | independence | correlation vs the 165-day base ≥ 0.60 |
| **F4** | stability | the window is unprofitable in 2 of the 3 dev sub-periods |
| **F5** | cost | 5 bp CAGR < 60% of 1 bp CAGR |

If **F1** fails while the expiry-session effect stays true, the honest verdict is
`retired_overlay_only`: the calendar fact is real, but a long-only harness can
only express it as an exclusion, and the stand-alone version is just 29% TQQQ
beta with a calendar costume. I will report that outcome rather than dress it up.

Additional falsifiers that are not pass/fail gates but will be reported:
- if the 2020-21 sub-period dominates the whole result, the strategy is a
  crash-timing accident, not a flow premium;
- if `session_only` (no overnight holds) beats the primary at 1 bp but loses at
  5 bp, the edge is a cost artefact of the fill schedule;
- if `qqq_instead` matches `primary` on Sharpe, TQQQ's 3× is doing the work and
  the calendar is not.

## 7. Overfitting controls (planned, reported in `result.json`)

- **Variants tried:** 13, all listed in `strategy.py::variants`; 1 bp dev table
  for each (primary, no vol cap, half size, week only, post only, wider,
  narrower, QQQ instead, session only, vol thresholds 20% and 30%, and the two
  structural placebos).
- **Neighbourhood:** ±1 session on the window start/end plus ±5 pp on the vol
  threshold; the primary is chosen as the centre of a plateau, not the argmax.
- **Sub-periods:** 2016-19, 2020-21, 2022-23.
- **Placebo:** the shifted-week anchors above (structural, not random) plus a
  permutation test that compares the mean TQQQ close-to-close return of the 576
  designated sessions with 1,000 random same-size session sets.
- **Event count / bootstrap:** 96 expiry events; month-level bootstrap (2,000
  draws) over the dev period for CAGR and max-drawdown percentiles.
- **Costs:** 1/5/10 bp.

## 8. Results

**Not run.** Backtests are paused by instruction; `result.json` does not exist.
This section will be filled from a single run of `strategy.py` after
authorisation, with dev 1/5/10 bp, the correlation numbers, the neighbourhood
and placebo tables, the sub-periods, and the bootstrap.

## 9. Expected shape (predictions, not results)

- CAGR: positive but far below the old base — this is a ~29%-exposure strategy,
  so ~8-20%/yr at 1 bp is the plausible band; the old base made 58.8% by being
  long TQQQ 79% of the time.
- Max DD: 15-25%, driven by whichever expiry week lands in a crash (the March
  2020 window, Mon 16 – Thu 19 Mar, is the obvious candidate and is a known
  weakness of the design).
- Correlation vs the 165-day base: **0.30-0.55** expected. It is 29% invested
  on calendar-fixed days, so the overlap with a TQQQ-beta series is partial.
- The honest risk: most of the return is TQQQ beta earned on 576 of 2,012
  sessions; only the avoided expiry day (≈ −84 bp × 12 = +1.0%/yr of relative
  edge) is attributable to the event.

## 10. Provenance

| claim | source | role |
|---|---|---|
| Expiry-day returns are weak (SPY 1993-2024: −0.77% average, 51.4% win rate, −23.55% compounded) | QuantifiedStrategies, *The Options Expiration Week Effect* — https://quantifiedstrategies.substack.com/p/the-options-expiration-week-effect-aa2 | inspired the rule; my dev measurement is the same sign, smaller |
| Expiry-cycle flow is a real order-imbalance phenomenon (rollover on the third Friday and the following Monday) | *Option returns: a tale of the expiration rollover day*, FMA 2025 — https://www.fma.org/assets/docs/Derivatives2025/GarciaAres.pdf | supports the mechanism (read as excerpt only) |
| Expiry **weeks** have above-average returns (the complement of the day effect) | Quantpedia, *Option-Expiration Week Effect* — https://quantpedia.com/strategies/option-expiration-week-effect | partial: opposite sign to the day-level claim, so it is used only as a map of the cycle, not as support for the window |
| The expiry-session drift measured here (dev only) | Own test, `explore.py`, 2016-01-04 → 2023-12-29 | the evidence the strategy rests on |
| NYSE holiday / third-Friday calendar | Own implementation of the published observance rules | ex-ante by construction |

Rejected for this rebuild: the pre-FOMC drift (Lucca–Moench) and the FOMC leg
from the original — the FOMC intraday swap gain was only +26.3 bp at t = 1.04 in
the full sample and the pre-2015 drift has disappeared. Pre-holiday de-risking
was also rejected: pre-holiday sessions are strongly positive, so avoiding them
loses money.

## 11. Known risks

1. **Long-only constraint.** The profitable side of the finding is the short
   side of the expiry session, which this engine cannot express. The rebuild is
   a proxy, and that is the single biggest reason it might not clear F1.
2. **Crash weeks.** The window is calendar-fixed, so it will sometimes hold
   TQQQ straight into a macro shock (March 2020). The vol cap halves that, it
   does not remove it.
3. **Selection.** The window boundaries came from the dev offset table, which is
   in-sample. The placebos and the ±1 session neighbourhood are there to expose
   that, not to hide it.
4. **Only 96 events** in dev; a calendar effect with a 331 bp daily sd needs a
   large sample to resolve.

## 12. Reproduction

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
python research\strategies\event-risk-overlay\strategy.py            # dev only
python research\strategies\event-risk-overlay\strategy.py --with-holdout   # lead only
```

`strategy.py::build_weights(ts, opens, closes, **kw) -> (weights, info)` writes
only `research/strategies/event-risk-overlay/result.json`. `explore.py` holds the
dev event study quoted in section 3 and is not part of the strategy.
