# Macro-event TQQQ: the FOMC intermeeting drift

**Status: pre-registration.** Development window only:
**2016-01-04 → 2023-12-29**. The 2024-2026 holdout is not loaded by
`strategy.py` and was not inspected. Next-open fills, 2% band, long-only,
weights ≥ 0 and sum ≤ 1. TQQQ bar: **36.72% CAGR / 82.29% max DD / 0.82
Sharpe** on 1-minute marks.

This is a standalone strategy. It does **not** use the 165-day QQQ SMA, the
4% intraday stop, the old event-risk overlay, or the OpEx-cycle rebuild.

---

## 1. What is different from the existing event work

| | `agents2/event-risk-overlay` | `revisit/event-risk-overlay` (expiry cycle) | this |
|---|---|---|---|
| Base | 165-day QQQ SMA + 4% armed stop | none (calendar only) | none |
| Exposure | ~100% TQQQ except one session | own the OpEx cycle, flat the expiry session | TQQQ only inside FOMC windows |
| Event | OpEx intraday de-risk, FOMC/CPI as controls | monthly OpEx only | scheduled FOMC only |
| Timing | overlay on a trend strategy | flat the weak expiry session | hold the **middle of the intermeeting period** |
| Result | 67.1% / 40.7% on its 2017-2026 10y window (overlay, not standalone) | 26.94% / 39.04% dev, standalone | see `result.json` |

The existing work says *avoid* one event session. This study says the equity
premium is **earned in a specific phase of the FOMC cycle** and is absent in
the adjacent phases. It is a different signal, a different holding pattern and
a different failure mode.

## 2. Mechanism

Scheduled FOMC meetings are the highest-attention macro events on the calendar.
The literature documents two adjacent effects:

1. **Announcement premium.** Lucca & Moench (2015) and Savor & Wilson (2013)
   find excess equity returns in the 24 hours before scheduled FOMC decisions:
   investors pay for protection into the event, and the announcement resolves
   that uncertainty.
2. **FOMC cycle.** Cieslak, Morse & Vissing-Jorgensen (2019) show the equity
   premium is not uniform across the intermeeting period; it is concentrated in
   particular weeks of the cycle, with flat or negative phases elsewhere.

The development-sample offset profile (2016-2023, TQQQ close-to-close, all 63
scheduled meetings) shows a consistent three-phase shape:

| phase | sessions | mean TQQQ | reading |
|---|---:|---:|---|
| pre-meeting run-up | −1, 0 | +64.5, +80.8 bp | announcement premium |
| immediate post-decision | +1, +2 | −76.6, −50.0 bp | positioning unwind / pay-back |
| intermeeting drift | +3 … +20 | positive on most sessions, ~+35 bp/day | risk is redeployed once the path is known |
| late pre-meeting | −9 … −2 | choppy / negative | de-risking into the next meeting |

**H1.** After the two-day post-decision unwind, the policy path is known and
volatility sellers have re-established supply. The equity risk premium is then
earned over the following ~3 weeks. The last week before the next meeting is
de-risking noise and should be avoided.

**H2.** This is an index-level calendar effect, not a TQQQ artefact. On QQQ the
same +3…+20 window returns +2.29% per cycle over 62 cycles (t = 4.03, 74%
positive) — a weaker but highly significant version of the same premium. TQQQ
is the leveraged implementation.

**H3.** Because TQQQ's 3× daily reset suffers volatility drag, being out of the
market during the negative phases (the two post-decision days and the late
pre-meeting week) should improve the *geometric* return even at ~55% exposure.

## 3. Exact rules

Calendar (hardcoded, published by the Fed roughly a year ahead):

* 63 **scheduled** FOMC decision days, 2016-2023, from the Fed's own meeting
  calendars. Unscheduled emergency meetings (2020-03-03, 2020-03-15) are
  excluded because they were not knowable in advance.
* The scheduled March 2020 meeting (2020-03-17/18) was cancelled and replaced
  by the 2020-03-15 emergency decision; it is **not** used as an event. A
  sensitivity that adds 2020-03-18 is reported in `report.md`.
* No CPI, NFP, OpEx or holiday dates are used by the primary. They appear only
  in two pre-registered grid cells as diversifiers.

For each scheduled FOMC decision day `F` (session index `k`):

```
long TQQQ from the open of session k+3
through the close of session k+20   (18 sessions)
BIL otherwise
```

* Entry is a target set on the prior session's last bar and filled at the next
  session's 09:30 open.
* Exit is a target set at 15:58 and filled at the 15:59 open of session k+20,
  so the position is not held overnight after the window.
* If a window would run past the end of the development sample it is truncated
  at the last available session (the December 2023 meeting).
* No stop, no trend filter, no volatility target, no shorting. Weights are
  0/1 in TQQQ and the complement in BIL.

## 4. Why it could beat TQQQ

TQQQ's 36.72% CAGR is bought with an 82.29% drawdown and 0.82 Sharpe. The
strategy holds TQQQ in 55% of sessions but in the phase with the highest
average return and avoids the two worst phases of the cycle. If the phase
effect is real, the geometric return can exceed buy-and-hold despite lower
exposure. The development sample says the held sessions average +35.3 bp/day
(arithmetic) versus +4.2 bp for non-held sessions.

It is still a long-TQQQ strategy: it will lag a strong, low-volatility bull
market, and a crash inside a held window is taken in full.

## 5. Falsifiers (checked in `report.md`)

1. **QQQ check.** The same window on QQQ must show a positive cycle mean with
   t > 1.5 and > 55% positive cycles. Dev: t = 4.03, 74% positive.
2. **Random-date placebo.** 500 random calendars with the same number of events
   (63) and the same 18-session length. The primary should sit above the 95th
   percentile of CAGR and Sharpe and below the 5th percentile of DD.
3. **Shifted calendar.** Shifting every FOMC date by −15…+15 sessions should
   produce a peak at 0; a flat curve would mean the anchor is irrelevant.
4. **Costs.** 10 bp headline must still clear 36.72% CAGR.
5. **Single-year dependence.** Leave-one-year-out. If dropping 2020 collapses
   the CAGR below 36.72%, the pass is a one-regime artefact and must be
   reported as such.
6. **Neighbour grid.** The pass must not be a single-cell spike; the 8-cell
   grid below is reported in full.

## 6. Pre-registered grid (8 cells, 1 bp unless stated)

| cell | FOMC window | extra sleeve | role |
|---|---|---|---|
| **G1 (primary)** | **+3 … +20** | — | mechanism-implied middle of the cycle |
| G2 | +1 … +15 | — | early phase, shorter |
| G3 | +3 … +15 | — | shorter middle |
| G4 | +3 … +25 | — | longer middle, includes late pre-meeting |
| G5 | +5 … +20 | — | later start, more unwind skipped |
| G6 | +3 … +20 | CPI [−1 … +2] | CPI release diversifier |
| G7 | +3 … +20 | OpEx [+1 … +3] | post-expiry flow diversifier |
| G8 | +3 … +20 | CPI + OpEx | all three event families |

The primary is fixed **before** the final run. Cells G2-G8 are a sensitivity
and plateau test, not a selection menu: the report does not switch the primary
to a better neighbour after seeing the results. A coarse offset scan informed
the choice of +3/+20; that is disclosed in `report.md` §7 rather than presented
as blind pre-registration.

CPI dates are the BLS release schedule (2016 dates reconstructed from the
published 2016 schedule; 2017-2023 from archived BLS schedules). OpEx is the
third Friday, holiday-shifted. Neither is used by G1.

## 7. Expected effect (written before the final run)

* Primary: **45-55% CAGR, 45-55% max DD, 1.1-1.2 Sharpe, ~55% TQQQ exposure**.
* Shorter windows: 15-30% CAGR; they miss the drift.
* Longer windows: higher CAGR but DD above 60%.
* CPI/OpEx additions: more exposure, worse drawdown, no improvement in Calmar.
* Placebo median: ~19% CAGR; the primary should be above the 95th percentile.
* Leave-one-year-out: dropping 2020 likely takes CAGR to ~33%, below the bar.
  This is the main honest weakness of the strategy.

## 8. Data and reproducibility

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
$env:BT_THREADS = "1"
python research/new/macro-event-tqqq/strategy.py
```

`strategy.py` loads `bt.panel(("QQQ","TQQQ","BIL"), "2016-01-04",
"2023-12-29", "1min", warmup_days=10)`, so the last bar is 2023-12-29 15:59
and no 2024+ row is read.
