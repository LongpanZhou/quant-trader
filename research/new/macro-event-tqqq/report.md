# Macro-event TQQQ: the FOMC intermeeting drift

**Development window:** 2016-01-04 -> 2023-12-29. 1-minute marks, next-open
fills, 2% band, long-only, weights >= 0 and sum <= 1. **No 2024+ data was
loaded by this study.**

**Verdict:** the strategy **passes the literal development gate** (51.06% CAGR
vs 36.72%, 48.83% max DD vs 82.29%) at 1, 5 and 10 bp. It is **not robust to
dropping 2020**: the ex-2020 CAGR is about 33.4%, below the bar, and 2016-2019
also lags TQQQ. The honest reading is a genuine risk-adjusted improvement
(Sharpe 1.17 vs 0.82, Calmar 1.05 vs 0.44) whose CAGR edge is concentrated in
the 2020 and 2022 regimes.

---

## 1. Headline

| | CAGR | max DD | Sharpe | Sortino | vol | TQQQ exposure | fills | turnover |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **Primary, 1 bp** | **51.06%** | **48.83%** | **1.17** | 1.67 | 43.3% | **55.8%** | 253 | 2,079x |
| Primary, 5 bp | 49.16% | 49.08% | 1.14 | 1.63 | 43.3% | 55.8% | 253 | 1,929x |
| Primary, 10 bp | 46.81% | 49.38% | 1.11 | 1.58 | 43.3% | 55.8% | 253 | 1,758x |
| TQQQ bar (published) | 36.72% | 82.29% | 0.82 | -- | -- | 100% | -- | -- |
| TQQQ recomputed on this panel | 36.15% | 82.29% | 0.80 | -- | 66.6% | 100% | -- | -- |

* Ending equity at 1 bp: **$2.694M** from $100k (25.9x).
* Daily correlation to TQQQ: **0.657**; beta **0.429**. Correlation to QQQ:
  0.653; beta 1.269.
* Max drawdown episode: peak **2021-12-27**, trough **2022-05-24**. Daily-mark
  drawdown is 44.63%; the 1-minute mark is 48.83%.
* The TQQQ benchmark recomputed on the same 1-minute panel is 36.15% / 82.29%
  / 0.80, i.e. 0.57 pp below the published 36.72% CAGR. The program bar is the
  published figure; the comparison is conservative by that amount.

## 2. Exact rules

For every **scheduled FOMC decision day** `F` (63 dates, 2016-2023):

```
long TQQQ from the open of session F+3
through the close of session F+20      (18 sessions)
BIL otherwise
```

* Entry is a target set on the prior session's last bar, filled at the next
  session's 09:30 open.
* Exit is a target set at 15:58 and filled at the 15:59 open, so the position
  is not carried overnight after the window.
* If a window runs past the end of the development sample it is truncated at
  the last available session. That happens once, for the December 2023
  meeting; 62 cycles are complete, 1 is truncated.
* No stop, no trend filter, no volatility target, no shorting, no CPI/OpEx in
  the primary. Weights are 0/1 in TQQQ and the complement in BIL.
* Event count: 63 scheduled meetings; 63 windows (62 complete + 1 truncated).
  TQQQ is held for 55.8% of the 781,880 one-minute bars (2,012 sessions).

The 2020-03-03 and 2020-03-15 emergency meetings are excluded because they
were not knowable in advance. The scheduled 2020-03-18 meeting was cancelled
and is not used; a sensitivity that adds it is in section 6.6.

## 3. Why this window should carry a premium

Scheduled FOMC meetings are the highest-attention macro events on the
calendar. The literature documents two adjacent effects:

1. **Announcement premium.** Lucca & Moench (2015) and Savor & Wilson (2013)
   find excess equity returns in the 24 hours before scheduled FOMC decisions:
   investors pay for protection into the event, and the announcement resolves
   the uncertainty.
2. **FOMC cycle.** Cieslak, Morse & Vissing-Jorgensen (2019) show the equity
   premium is not uniform across the intermeeting period; it is concentrated
   in particular weeks, with flat or negative phases elsewhere.

The development-sample offset profile has a consistent three-phase shape
(TQQQ close-to-close, all 63 meetings, bp):

| phase | sessions | mean TQQQ |
|---|---|---:|
| pre-meeting run-up | -1, 0 | +64.5, +80.8 |
| immediate post-decision | +1, +2 | -76.6, -50.0 |
| intermeeting drift | +3 ... +20 | mostly positive, ~+35/day |
| late pre-meeting | -9 ... -2 | choppy / negative |

The story is: the decision resolves the policy path; the first two days are a
positioning unwind and a pay-back of the announcement premium; capital is then
redeployed over the next three weeks. In the last week before the next meeting
the market de-risks again.

This is an **index-level** effect, not a TQQQ artefact. On QQQ the same
+3...+20 window returns +2.29% per cycle over 62 cycles: **t = 4.03, 74%
positive**. TQQQ is the leveraged implementation; the 3x reset amplifies the
timing alpha.

## 4. Results

### 4.1 Yearly returns

| Year | Strategy | TQQQ | Comment |
|---|---:|---:|---|
| 2016 | +29.7% | +19.9% | beats |
| 2017 | +42.4% | +114.5% | lags a strong bull |
| 2018 | +8.5% | -20.8% | beats the drawdown year |
| 2019 | +72.2% | +148.2% | lags |
| 2020 | +249.3% | +104.1% | the COVID gap and rebound |
| 2021 | +45.1% | +81.1% | lags |
| 2022 | -8.5% | -79.4% | the main risk-management year |
| 2023 | +61.2% | +192.0% | lags the AI bull |

The profile is consistent: the strategy wins in flat/down years and loses in
strong bull years. It is not a bull-market replacement.

### 4.2 Subperiods

| Period | Strategy CAGR / DD / Sharpe | TQQQ CAGR (approx.) |
|---|---:|---:|
| 2016-2019 | 35.36% / 44.96% / 0.99 | 38.2% |
| 2020-2021 | 126.64% / 35.90% / 2.20 | 92.3% |
| 2022-2023 | 22.94% / 47.98% / 0.65 | -22.4% |

The strategy lags TQQQ in the calm 2016-2019 bull, then beats by a wide margin
in the two crisis regimes. That is the whole source of the full-window pass.

### 4.3 Drawdown

The 48.83% 1-minute drawdown runs from the 2021-12-27 peak to the 2022-05-24
trough. It is not a single bad close: the strategy is long 100% TQQQ inside a
window, so an intra-window crash is taken in full. The worst complete cycles
were:

| FOMC | window | TQQQ |
|---|---|---:|
| 2018-09-26 | 2018-10-01 -> 2018-10-24 | -32.75% |
| 2020-01-29 | 2020-02-03 -> 2020-02-27 | -20.52% |
| 2019-05-01 | 2019-05-06 -> 2019-05-30 | -16.68% |
| 2022-01-26 | 2022-01-31 -> 2022-02-24 | -12.89% |
| 2023-07-26 | 2023-07-31 -> 2023-08-23 | -12.22% |

The best cycles were 2020-06-10 (+42.65%), 2018-12-19 (+40.64%),
2020-09-16 (+35.37%), 2022-11-02 (+30.51%) and 2023-05-03 (+28.24%).

## 5. Event evidence

### 5.1 Per-cycle distribution

| | n | mean | median | sd | t | positive |
|---|---:|---:|---:|---:|---:|---:|
| TQQQ | 62 | +6.33% | +5.71% | 14.01% | **3.55** | 71.0% |
| QQQ | 62 | +2.29% | +2.16% | 4.47% | **4.03** | 74.2% |

The QQQ result is the more important number: the same 18-session window earns
a significant positive return in the unlevered index, so the strategy is not
a TQQQ-specific curve fit. It is a calendar premium implemented with leverage.

### 5.2 Offset profile

Key offsets (TQQQ close-to-close, bp, 63 events; standard errors are roughly
40-60 bp, so individual cells are noisy):

| offset | -5 | -3 | -2 | -1 | **0** | +1 | +2 | +3 | +4 | +5 | +10 | +14 | +20 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| mean | +95.6 | -22.7 | -19.8 | +64.5 | **+80.8** | -76.6 | -50.0 | +51.5 | +56.0 | -1.6 | -0.9 | +109.2 | +43.5 |

The three-phase shape is visible, but the individual cells are noisy. The
robust part is the cycle-level result and the QQQ replication, not any single
offset.

### 5.3 Turn-of-month is not the explanation

A first-three-sessions-of-month TQQQ strategy (14.2% exposure) returns only
4.04% CAGR with a 42.05% DD. The FOMC window is not a repackaged turn of the
month.

## 6. Robustness

### 6.1 Pre-registered grid (8 cells, 1 bp)

| cell | FOMC window | extra | CAGR | max DD | Sharpe | exposure |
|---|---|---|---:|---:|---:|---:|
| **G1 (primary)** | **+3...+20** | -- | **51.06%** | **48.83%** | **1.17** | 55.8% |
| G2 | +1...+15 | -- | 23.27% | 47.31% | 0.72 | 46.7% |
| G3 | +3...+15 | -- | 37.11% | 35.72% | 1.04 | 40.4% |
| G4 | +3...+25 | -- | 52.87% | 63.04% | 1.11 | 71.2% |
| G5 | +5...+20 | -- | 36.57% | 55.96% | 0.97 | 49.5% |
| G6 | +3...+20 | CPI [-1,+2] | 40.22% | 70.33% | 0.94 | 63.7% |
| G7 | +3...+20 | OpEx [+1,+3] | **61.42%** | **47.78%** | **1.27** | 61.8% |
| G8 | +3...+20 | CPI + OpEx | 50.31% | 68.08% | 1.06 | 69.2% |

Six of eight cells clear the literal bar; G2 fails and G5 is 0.15 pp short.
The plateau is broad in CAGR but not in drawdown: G4, G6 and G8 have 63-70%
drawdowns, above the 60% ideal.

**G7 is the strongest cell** (61.42% / 47.78% / 1.27 at 1 bp; 54.08% / 48.72%
/ 1.17 at 10 bp). It is not the deliverable because G1 was fixed as the
primary before the final run. Switching to G7 after seeing the grid would be
exactly the post-hoc selection the protocol forbids. G7 is a legitimate
follow-up candidate and is consistent with the existing OpEx literature
(post-expiry sessions are positive). It also contradicts the pre-run
expectation in `HYPOTHESIS.md` that CPI/OpEx additions would only add
drawdown: the post-OpEx sleeve is the one addition that improved both CAGR and
DD.

### 6.2 Random-date placebo (500 draws)

Same event count (63) and hold length (18 sessions), random start sessions;
overlaps allowed, so the median exposure is 43.1% versus the primary's 55.8%.

| | median | p90 | p95 | p99 | max | primary | percentile |
|---|---:|---:|---:|---:|---:|---:|---:|
| CAGR | 16.1% | 33.1% | 37.7% | 46.0% | 48.1% | 51.06% | 100.0% |
| max DD | 68.9% | -- | -- | -- | -- | 48.83% | 93.8% better |
| Sharpe | 0.57 | -- | 1.01 | -- | 1.28 | 1.17 | 98.8% |

No random calendar beats the primary on CAGR; the joint fraction with
CAGR >= 51.06% **and** DD <= 48.83% is **0 / 500**.

Because random windows overlap, their exposure is lower. The next placebo
fixes that.

### 6.3 Exposure-matched phase placebo (30 phases)

A generic 30-session cycle with a random phase, 63 non-overlapping 18-session
windows (median exposure 56.4%, close to the primary's 55.8%):

* CAGR: median 16.6%, p90 32.4%, p95 34.8%, max 38.5%; primary 51.06%;
  percentile 100.
* max DD: median 68.5%, best 59.6%; primary 48.83%; percentile 100.
* Sharpe: median 0.56, p95 0.86, max 0.89; primary 1.17; percentile 100.

No phase of a generic 6-week cycle comes close. The FOMC anchor matters, not
just the 55% duty cycle.

### 6.4 Shifted calendar

All FOMC dates shifted by N sessions, same 18-session hold:

| shift | -8 | -6 | -4 | -2 | -1 | **0** | +1 | +2 | +4 | +6 | +8 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| CAGR | 15.1% | 18.9% | 25.6% | 31.4% | 41.1% | **50.6%** | 40.5% | 38.2% | 44.9% | 34.6% | 31.8% |
| max DD | 65.6% | 61.1% | 48.2% | 55.8% | 52.6% | **48.8%** | 56.0% | 59.9% | 57.6% | 79.3% | 86.5% |

The peak is at shift 0. There is a +/-4-session neighbourhood at 38-45%, and
the curve collapses beyond +/-6. The event window is not a one-day spike, but
the exact alignment is load-bearing. (Shift 0 is 50.6%, not 51.06%, because the
shift test requires a full 18-session window and drops the truncated December
2023 window.)

### 6.5 Leave-one-year-out

| dropped year | year return | ex-year CAGR |
|---|---:|---:|
| 2016 | +29.7% | 54.2% |
| 2017 | +44.9% | 51.8% |
| 2018 | +10.2% | 57.9% |
| 2019 | +61.7% | 49.5% |
| **2020** | **+258.6%** | **33.4%** |
| 2021 | +46.7% | 51.6% |
| 2022 | -7.1% | 61.8% |
| 2023 | +64.7% | 49.1% |

Dropping any year except 2020 leaves CAGR at 49-62%, comfortably above the
bar. Dropping 2020 takes it to 33.4%, below the bar. The pass is therefore
**not broad-based enough** to call the strategy robust.

### 6.6 Cancelled March 2020 meeting

Adding the cancelled 2020-03-18 scheduled date (window 2020-03-23 -> 2020-04-17)
gives **62.87% CAGR / 48.83% DD / 1.30 Sharpe**. The primary's choice to exclude
the cancelled meeting is conservative, not result-enhancing.

### 6.7 Costs

The strategy trades 253 fills and 2,079x initial-equity turnover over 8 years
(about 260x/year), because every switch liquidates BIL and buys TQQQ. The cost
drag from 1 to 10 bp is 4.25 pp of CAGR, but the 10 bp result (46.81%) still
clears the bar. Costs are not the failure mode.

## 7. Where it fails

1. **Small sample.** 63 scheduled meetings, 62 complete cycles, 8 per year.
   The cycle-level t-stat is 3.55, but the observations are clustered in time;
   the effective sample is small and the 2020 observations are extreme.
2. **Regime change.** The strategy lags TQQQ in 2016-2019 (35.4% vs ~38.2%)
   and in every strong bull year (2017, 2019, 2021, 2023). The full-window
   pass comes from 2020 (+249%) and 2022 (-8.5% vs -79.4%). Ex-2020 CAGR is
   33.4%, below the bar. A return to a low-volatility bull market with no
   crash would likely underperform buy-and-hold.
3. **The 2020 calendar accident.** The January 2020 window ended on
   2020-02-27; the next scheduled window (April 29 +3) began on 2020-05-04.
   The strategy was therefore flat through the COVID crash. A real-time
   investor knew that schedule, so this is not look-ahead, but it is a one-off
   alignment of the crash with the intermeeting gap. Adding the cancelled
   2020-03-18 date actually *raises* CAGR to 62.87% (the window starts near the
   bottom), so the exclusion is not what creates the pass; the gap alignment
   is still a single historical accident.
4. **Intra-window crash risk.** The strategy is 100% TQQQ inside a window and
   takes the full 2018 Q4 (-32.75%) and 2020 February (-20.52%) cycles. The
   max DD is 48.8%, better than TQQQ's 82.3% but still large. No stop is used;
   adding one would be a different strategy.
5. **Selection disclosure.** The +3/+20 boundaries came from a coarse
   development-sample offset scan, not from a blind theory. The grid is a
   plateau test, but the primary is at the high end of that plateau. The exact
   phase is sample-specific: the literature's "even weeks" pattern does not
   match this sample's phase, and the mechanism story is partly post-hoc.
6. **Possible confounds.** The window may proxy for month-end, OpEx-week or
   other calendar effects. The shift test and the phase placebo argue against
   a generic 6-week cycle and against turn-of-month, but they cannot rule out
   every confound.

## 8. Difference from the existing research

| | `agents2/event-risk-overlay` | `revisit` expiry cycle | this |
|---|---|---|---|
| Base | 165-day QQQ SMA + 4% stop | none | none |
| Exposure | ~100% TQQQ minus one session | own the OpEx cycle, flat expiry | 55.8% TQQQ, FOMC phase only |
| Event | OpEx intraday de-risk | monthly OpEx | scheduled FOMC |
| Timing | overlay on a trend strategy | avoid the weak expiry session | hold the middle of the intermeeting period |
| Dev result | 67.1% / 40.7% on its 2017-2026 10y window | 26.94% / 39.04% | 51.06% / 48.83% |

The original overlay de-risks *one event session* on top of a trend base; the
standalone expiry rebuild owns the OpEx cycle and avoids the expiry session.
This study has no price-based base, holds only in a multi-week phase, and its
premium comes from the phase, not from avoiding a single print. It is not a
copy or a variant of the 165-SMA + 4%-stop strategy.

## 9. Verdict

* **Literal development gate: PASS.** 51.06% CAGR > 36.72%; 48.83% max DD <
  82.29%; 1, 5 and 10 bp all pass.
* **Risk-adjusted: genuine improvement.** Sharpe 1.17 vs 0.82; Calmar 1.05 vs
  0.44; 0.657 correlation and 0.43 beta to TQQQ.
* **Robustness gate: FAIL.** Ex-2020 CAGR 33.4%; 2016-2019 CAGR 35.4%; the
  pass is concentrated in crisis years and in a calendar accident.
* **Use:** a satellite or crisis-hedged TQQQ allocation, not a standalone
  replacement. The FOMC phase effect is strong enough to deserve a follow-up
  with a longer history (pre-2016) and an explicit test of the phase stability.
  G7 (FOMC + post-OpEx) is the best grid cell and the natural next
  pre-registration, but it was not selected here.

## 10. Reproduction

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
$env:BT_THREADS = "1"
python research/new/macro-event-tqqq/strategy.py
```

`strategy.py` loads
`bt.panel(("QQQ","TQQQ","BIL"), "2016-01-04", "2023-12-29", "1min",
warmup_days=10)`. The last bar is 2023-12-29 15:59; no 2024+ row is read.
`result.json` contains the full grid, placebo distributions, shift curve,
subperiod cuts, leave-one-year-out, per-cycle event study and the March 2020
sensitivity.
