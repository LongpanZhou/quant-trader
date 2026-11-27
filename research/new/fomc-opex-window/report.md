# FOMC + post-OpEx calendar TQQQ: development report

**Development window:** 2016-01-04 -> 2023-12-29. 1-minute marks, next-open
fills, 2% band, long-only, weights >= 0 and sum <= 1. **No 2024+ bar was
loaded by this study**; the volatility warmup reads only 2015 daily rows via a
parquet row filter. The hardcoded FOMC/OpEx calendar now covers the 2026-10-23
holdout end; the 2024-2026 dates are not used by the development backtest
(section 2).

**Verdict:** the strategy **passes the literal development gate** at 1, 5 and
10 bp: **58.26% CAGR / 42.60% max DD / 1.36 Sharpe** vs the TQQQ bar of
36.72% / 82.29% / 0.82. The parameter plateau is broad and the calendar beats
four independent random-calendar placebos. The honest weakness is that the
return edge is concentrated in 2020-2023: the calm 2016-2019 subperiod returns
34.4%, and the ex-2020 CAGR is 37.49%, only 0.77 pp above the published bar
(1.34 pp above the benchmark recomputed on this panel). It is a legitimate
standalone candidate with a real chance at the full-window bar, not a
calm-bull replacement.

---

## 1. Headline

| | CAGR | max DD | Sharpe | Sortino | vol | TQQQ exposure | fills | turnover | ending equity |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Primary, 1 bp** | **58.26%** | **42.60%** | **1.36** | 1.95 | 39.5% | **55.4%** | 617 | 4,344x | $3.906M (39.1x) |
| Primary, 5 bp | 55.14% | 42.88% | 1.31 | 1.88 | 39.5% | 55.4% | 617 | 3,846x | $3.33M |
| Primary, 10 bp | 51.34% | 43.23% | 1.25 | 1.79 | 39.6% | 55.4% | 617 | 3,309x | $2.73M |
| TQQQ bar (published) | 36.72% | 82.29% | 0.82 | -- | -- | 100% | -- | -- | -- |
| TQQQ recomputed here | 36.15% | 82.29% | 0.80 | -- | 66.6% | 100% | -- | -- | 11.8x |

* Daily-mark max DD is **40.64%**; the 42.60% headline is the 1-minute mark.
* Max drawdown episode: peak **2018-09-26**, trough **2018-12-24**.
* Daily correlation to TQQQ **0.663**, beta **0.387**. Correlation to QQQ is
  not reported because QQQ is never held; the QQQ event study is in section 3.
* Calmar 1.37 vs 0.44 for TQQQ. The benchmark recomputed on the same panel is
  0.57 pp below the published bar, so all comparisons are slightly
  conservative.
* Exposure: 49.2% of sessions full TQQQ, 12.7% at half, 38.1% zero; mean TQQQ
  weight 55.4%, mean BIL weight 44.6%. The 20/100 vol ratio is above 1.25 on
  19.7% of sessions.

## 2. Exact rules

Hardcoded calendars, no network access at run time:

* **85 scheduled FOMC decision days**, from 2016-01-27 through 2026-09-16
  (the last scheduled decision before the 2026-10-23 holdout end), hardcoded
  from the Fed's published meeting calendars. The 2016-2023 development panel
  contains 63 of them; the 22 dates from 2024-01-31 through 2026-09-16 are
  ex-ante schedule entries for the holdout. The unscheduled emergency meetings
  (2020-03-03, 2020-03-15) are excluded because they were not knowable in
  advance. The scheduled 2020-03-18 meeting was cancelled and is excluded from
  the centre; a sensitivity adds it.
* **130 monthly OpEx dates, 2016 through 2026-10-16**, hardcoded from the
  third-Friday rule with holiday rolls. The development panel contains 96; the
  34 dates from 2024-01-19 through 2026-10-16 are ex-ante schedule entries for
  the holdout. The only holiday roll in the extension is 2025-04-17 (Good
  Friday 2025-04-18); the development rolls are 2019-04-18 and 2022-04-14.

**Holdout readiness.** The 2024-2026 entries are calendar dates only. No 2024+
price or return row is read by `strategy.py`; the panel remains
2016-01-04..2023-12-29. `event_windows()` skips any event outside the loaded
panel, so the extended list leaves every development weight and metric
unchanged. Re-running the 2016-2023 backtest after the extension reproduces
the frozen **58.26% / 42.60% / 1.36** exactly; the only `result.json` change is
the event-count metadata (85 FOMC / 130 OpEx hardcoded, 63 / 96 in the dev
panel). Running the same `build_weights()` on a 2016-2026 panel will use the 22
added FOMC dates and 34 added OpEx dates without a code change.

For an event at session `k`:

```
FOMC:    long TQQQ from the open of k+3 through 15:59 of k+20   (18 sessions)
OpEx:    long TQQQ from the open of k+1 through 15:59 of k+3    (3 sessions)
Union:   a session in either window is held; adjacent windows are continuous
Filter:  scale(k) = 0.5 if sigma20(k-1) / sigma100(k-1) > 1.25 else 1.0
         sigma = annualised stdev of TQQQ daily log returns, 20 / 100 sessions
Idle:    BIL
```

* An entry target is set on the prior session's last bar and filled at the next
  session's 09:30 open. A calendar block end is sold at the 15:59 open, so the
  position is not carried overnight after the window.
* A pure scale change inside a live block is rebalanced at the next open. This
  keeps the volatility signal causal: session `k` uses the ratio through the
  close of `k-1`.
* A session in both windows is held once, not double-weighted.
* No stop, no trend filter, no shorting, no leverage beyond 100% TQQQ.
* The December 2023 FOMC window runs past the sample and is truncated at
  2023-12-29: 62 complete FOMC cycles, 1 truncated.

## 3. Why this window should carry a premium

### 3.1 FOMC sleeve

Scheduled decisions resolve a known macro uncertainty. The development-sample
offset profile has the three-phase shape documented by the announcement-premium
and FOMC-cycle literature: a run-up into the decision, a two-day positioning
unwind, then an intermeeting drift, with de-risking in the last week before the
next meeting.

| phase | sessions | mean TQQQ close-to-close |
|---|---:|---:|
| pre-meeting run-up | -1, 0 | +64.5, +80.8 bp |
| immediate post-decision | +1, +2 | -76.6, -50.0 bp |
| intermeeting drift | +3 ... +20 | mostly positive, ~+40 bp/day |
| late pre-meeting | +24, +25 | +74.1, -61.4 bp |

Per complete cycle (open of +3 to close of +20, 62 cycles):

| | mean | median | sd | t | positive |
|---|---:|---:|---:|---:|---:|
| TQQQ | +6.33% | +5.71% | 14.01% | **3.55** | 71.0% |
| QQQ | +2.29% | +2.16% | 4.47% | **4.03** | 74.2% |

The QQQ result matters more than the TQQQ one: the same 18-session window
earns a significant positive return in the unlevered index, so this is not a
TQQQ leverage or split artefact.

### 3.2 OpEx sleeve

Monthly expiry is a flow event. The expiry session itself is weak; the
pre-expiry run-up and the post-expiry re-risking are both positive, with the
expiry print in the middle:

| offset | -4 | -3 | -2 | -1 | **0** | +1 | +2 | +3 | +4 | +5 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| mean TQQQ, bp | +14.7 | **+124.7** | -26.5 | -3.5 | **-65.4** | +30.4 | +47.3 | +38.3 | +21.7 | +5.3 |
| t | +0.28 | +2.92 | -0.71 | -0.09 | **-1.99** | +0.81 | +1.02 | +1.06 | +0.46 | +0.12 |

Per post-expiry cycle (+1..+3, 96 months):

| | mean | median | sd | t | positive |
|---|---:|---:|---:|---:|---:|
| TQQQ | +1.25% | +1.35% | 4.92% | **2.49** | 59.4% |
| QQQ | +0.45% | +0.51% | 1.64% | **2.70** | 63.5% |

The OpEx sleeve is monthly and only partly overlaps the eight-per-year FOMC
windows (overlap 8.3% of sessions). The union covers 61.9% of sessions before
the vol filter, 55.4% after it.

### 3.3 Held versus unheld sessions

The open-to-open return of held sessions averages **+28.5 bp** (t = 2.59,
n = 1,245); unheld sessions average **+8.7 bp** (t = 0.53, n = 766). The
close-to-close event study is the stronger evidence; the open-to-open split is
consistent but noisier.

## 4. Results

### 4.1 Yearly returns

| Year | Strategy | TQQQ | Comment |
|---|---:|---:|---|
| 2016 | +33.1% | +19.9% | beats |
| 2017 | +37.7% | +114.5% | lags a strong bull |
| 2018 | +2.6% | -20.8% | beats the drawdown year |
| 2019 | +72.8% | +148.2% | lags |
| 2020 | +312.7% | +104.1% | COVID gap + rebound |
| 2021 | +47.4% | +81.1% | lags |
| 2022 | +19.8% | -79.4% | the main risk-management year |
| 2023 | +54.3% | +192.1% | lags the AI bull |

The profile is consistent: wins in flat/down years, lags in strong bull years.
It beats TQQQ in 4 of 8 years; the wins are the crisis years.

### 4.2 Subperiods

| Period | Strategy CAGR / DD | TQQQ CAGR / DD |
|---|---:|---:|
| 2016-2019 | 34.38% / 42.60% | 49.97% / 58.62% |
| 2020-2021 | 148.31% / 24.09% | 92.25% / 72.74% |
| 2022-2023 | 37.75% / 37.17% | -22.42% / 81.10% |

The calm 2016-2019 bull is the weak regime: the strategy lags TQQQ by 15.6 pp
of CAGR with a lower DD, roughly the same Calmar. The full-window pass comes
from 2020-2023, especially the COVID gap and the 2022 bear.

### 4.3 Drawdown

The 42.60% 1-minute drawdown runs from the 2018-09-26 peak to the 2018-12-24
trough. It is not a single bad close: the strategy was long 100% TQQQ inside
the 2018-09-26 FOMC window (2018-10-01 -> 2018-10-24, **-32.75%**), and the
vol filter only halved part of it. The worst complete cycles were:

| FOMC | window | TQQQ |
|---|---|---:|
| 2018-09-26 | 2018-10-01 -> 2018-10-24 | -32.75% |
| 2020-01-29 | 2020-02-03 -> 2020-02-27 | -20.52% |
| 2019-05-01 | 2019-05-06 -> 2019-05-30 | -16.68% |
| 2022-01-26 | 2022-01-31 -> 2022-02-24 | -12.89% |
| 2023-07-26 | 2023-07-31 -> 2023-08-23 | -12.22% |

The best cycles were 2020-06-10 (+42.65%), 2018-12-19 (+40.64%),
2020-09-16 (+35.37%), 2022-11-02 (+30.51%) and 2023-05-03 (+28.24%).
The worst OpEx window was 2018-10-19 (-15.06%); the best was 2020-03-20
(+18.64%).

## 5. Robustness

### 5.1 Pre-registered grid (8 cells, 1 bp)

| cell | FOMC | OpEx | filter | CAGR | max DD | Sharpe | exposure |
|---|---|---|---:|---:|---:|---:|---:|
| **G1 (primary)** | **+3..+20** | **+1..+3** | **1.25 half** | **58.26%** | **42.60%** | **1.36** | 55.4% |
| G2 | +3..+15 | +1..+3 | 1.25 half | 42.85% | 34.79% | 1.19 | 43.6% |
| G3 | +3..+18 | +1..+3 | 1.25 half | 52.52% | 40.75% | 1.31 | 51.0% |
| G4 | +3..+22 | +1..+3 | 1.25 half | 55.46% | 41.82% | 1.28 | 60.2% |
| G5 | +5..+20 | +1..+3 | 1.25 half | 48.50% | 40.92% | 1.24 | 51.4% |
| G6 | +3..+20 | +1..+2 | 1.25 half | 58.22% | 41.34% | 1.39 | 53.5% |
| G7 | +3..+20 | +1..+4 | 1.25 half | 58.14% | 38.21% | 1.33 | 57.9% |
| G8 | +3..+20 | +1..+3 | none | 62.21% | 47.78% | 1.28 | 61.8% |

**All eight cells clear 36.72% CAGR and all have DD below 48%.** The centre is
not the best cell (G8 and G6 are marginally better on CAGR/Sharpe), which is
the point: it sits in a broad plateau, not on a spike. G8 reproduces the
`macro-event-tqqq` post-hoc G7 cell within 0.8 pp of CAGR (61.42% vs 62.21%;
the difference is that this study holds continuously when an OpEx window starts
the session after an FOMC window ends, instead of exiting and re-entering).

### 5.2 Neighbour ladders

| ladder | range | CAGR range | DD range |
|---|---|---:|---:|
| FOMC entry/exit | (2..5) x (15..24) | 42.9-56.9% | 34.8-50.2% |
| OpEx window | (0..2) x (2..4) | 44.5-58.2% | 38.2-49.9% |
| vol cut, half | 1.0-1.75 | 53.1-64.9% | 36.3-48.6% |
| vol cut, flat | 1.0-1.5 | 43.5-66.6% | 33.6-51.1% |
| absolute vol target | 0.45-0.75 | 44.8-56.2% | 36.0-43.6% |

Every one of the 28 neighbour cells clears 36.72% CAGR. The weakest is
42.85% (FOMC +3..+15); the strongest is 66.57% (flat at 1.5). The plateau is
broad in both window lengths and filter settings. The one local cliff is
including the expiry session itself: OpEx 0..2 and 0..3 fall to 44.5%, which is
consistent with the negative expiry-day return and is why the sleeve starts at
+1.

### 5.3 Random-calendar placebo (1,000 draws each)

| null | median CAGR | p95 | max | median DD | real CAGR percentile | joint CAGR >= 58.26% and DD <= 42.60% |
|---|---:|---:|---:|---:|---:|---:|
| circular shift of the whole calendar | 19.0% | 41.5% | 54.9% | 68.5% | 100.0% | **0 / 1,000** |
| random calendars (8 FOMC/yr, 1 OpEx/month) | 18.8% | 37.7% | 59.6% | 65.6% | 99.9% | **1 / 1,000** |
| random calendars, exposure-scaled | 19.0% | 38.0% | 59.8% | 66.2% | 99.9% | **1 / 1,000** |
| jittered calendar (each event +/- sessions) | 28.3% | 47.1% | 69.3% | 64.2% | 99.2% | **2 / 1,000** |

The circular shift preserves exposure closely (56.2% vs 55.4%) and the joint
FOMC/OpEx structure, and destroys only the phase: no shifted calendar comes
close on CAGR (max 54.9%) and only 1 of 1,000 has a lower drawdown. The
jittered null is the most adversarial: it keeps every event and its spacing,
shifts each event independently by up to +/-10 sessions, and matches exposure
(55.3%). Its median CAGR is 28.3%; 8 of 1,000 draws beat 58.26% on CAGR, 13 of
1,000 beat 42.60% on DD, and 2 of 1,000 do both. The calendar is doing real
work, not just holding TQQQ 55% of the time.

### 5.4 Shift curve

Shifting both calendars by `s` sessions, same window lengths, full windows
only:

| shift | -10 | -5 | -3 | -2 | -1 | **0** | +1 | +2 | +3 | +5 | +10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| CAGR | 20.2% | 31.5% | 11.8% | 25.0% | 36.3% | **57.4%** | 40.7% | 33.4% | 31.2% | 27.3% | 28.0% |
| max DD | 64.7% | 53.7% | 54.8% | 58.7% | 49.5% | **42.6%** | 47.6% | 64.9% | 54.7% | 67.5% | 67.9% |

The peak is at shift 0, 21 pp above either neighbour. Shift 0 is 57.44%, not
58.26%, because the shift test requires full windows and drops the truncated
December 2023 window. The peak is narrow: a one-session error still clears the
bar (36.3%/40.7%), but a two-session error does not. Exact alignment is
load-bearing.

Shifting only the FOMC sleeve (OpEx fixed): 0 = 57.4%, -1/+1 = 45.2%/48.3%,
-5/+5 = 41.4%/37.1%, beyond +/-6 = 29-34%. Shifting only the OpEx sleeve:
0 = 57.4%, -1/+1 = 44.5%/49.2%, -5 = **58.1%**, +5 = 45.7%. The -5 OpEx shift
is the pre-expiry window (the -3 day alone is +124.7 bp, t = 2.92), which is
just as good as the post-expiry window. This is an honest mechanism caveat:
the OpEx phase is a "week around expiry" effect, with the expiry print itself
negative; the post-expiry side was pre-registered, but it is not uniquely
special. See section 7.

### 5.5 Leave-one-year-out and best-month cut

| dropped year | year return | ex-year CAGR | ex-year DD |
|---|---:|---:|---:|
| 2016 | +33.1% | 62.24% | 40.64% |
| 2017 | +37.7% | 61.04% | 40.64% |
| 2018 | +2.6% | 68.04% | 31.83% |
| 2019 | +72.8% | 57.01% | 40.64% |
| **2020** | **+312.7%** | **37.49%** | **40.64%** |
| 2021 | +47.4% | 59.68% | 40.64% |
| 2022 | +19.8% | 64.51% | 40.64% |
| 2023 | +54.3% | 58.30% | 40.64% |

Dropping any year leaves CAGR at 37.5-68.0%. The ex-2020 result is the narrow
one: 37.49% vs the published 36.72% bar, a 0.77 pp margin (1.34 pp vs the
36.15% benchmark recomputed here). The pass is not a single-year artefact, but
2020 provides most of the cushion. Dropping the single best month (2020-08,
+28.3%) leaves **54.12% CAGR / 40.64% DD**, so the month-level concentration is
not the issue.

### 5.6 Costs

The strategy trades 617 fills and 4,344x initial-equity turnover over eight
years (about 540x/year), because every switch liquidates BIL and buys TQQQ and
the vol filter adds resizes. The cost drag from 1 to 10 bp is 6.9 pp of CAGR.
The 10 bp result (51.34% / 43.23% / 1.25) still clears the bar by 14.6 pp.
Costs are not the failure mode.

### 5.7 Decomposition and constant-exposure control

| variant | CAGR | max DD | Sharpe | exposure |
|---|---:|---:|---:|---:|
| FOMC only | 48.54% | 41.34% | 1.26 | 49.7% |
| OpEx only | 14.20% | 19.20% | 0.80 | 12.9% |
| union (primary) | 58.26% | 42.60% | 1.36 | 55.4% |
| constant 55.5% TQQQ, no calendar | 26.72% | 57.47% | 0.83 | 55.5% |

The OpEx sleeve adds **+9.7 pp CAGR** for 5.7 pp of marginal exposure and
1.3 pp of extra drawdown. A constant TQQQ weight equal to the primary's mean
exposure returns 26.72% with a 57.47% DD; the calendar timing adds 31.5 pp of
CAGR and cuts the DD by 15 pp. This is the cleanest evidence that the strategy
is not a repackaged static de-risking allocation.

### 5.8 Causality and sensitivity

* **Causality.** Truncating the panel at 2022-01-03 and rebuilding all weights
  leaves every prior weight unchanged: max absolute difference **0.0** through
  2021-12-29. The calendar is static; the vol filter uses only the prior close.
* **Cancelled March 2020 meeting.** Adding 2020-03-18 as a scheduled event
  (window 2020-03-23 -> 2020-04-17) gives **63.56% / 42.60% / 1.43**. Excluding
  the cancelled meeting is conservative, not result-enhancing.
* **Warmup.** 252 TQQQ daily closes from 2015-01-02 to 2015-12-31; the last
  warmup close is 2.2587 and the first panel close is 2.1194, a -6.17% move
  that is the real 2016-01-04 TQQQ session, not a scale break.
* **Execution.** The 2% band is the harness default; the 15:59 exit is the last
  fill before the close. The next-open convention is unchanged.

## 6. Where it fails

1. **The calm-bull regime.** 2016-2019 returns 34.38%, below the 36.72% bar and
   15.6 pp below TQQQ's 49.97%. The strategy is a crisis/volatility strategy.
   If 2024-2026 is a low-volatility melt-up with no drawdown, it will lag
   buy-and-hold again.
2. **Ex-2020 is a narrow pass.** 37.49% vs 36.72%, +0.77 pp. The full-window
   pass therefore depends on the 2020-2023 regimes, even though no single year
   is strictly necessary.
3. **The Q4 2018 crash is taken in full.** The max DD (42.60%) is a calendar
   window: the 2018-09-26 FOMC cycle lost 32.75% and the following OpEx windows
   lost another 15.1% and 11.5%. The vol filter only halved part of it. A stop
   would be a different strategy; none is used.
4. **The OpEx phase is not unique.** The pre-expiry window (shift -5) returns
   58.07%, as good as the post-expiry centre. The expiry day itself is the only
   clearly negative phase. The mechanism story is therefore "own the week
   around expiry, avoid the print", not "post-expiry is special". The
   pre-registered post-expiry side is still positive and significant (TQQQ
   t = 2.49, QQQ t = 2.70), but the phase choice is partly arbitrary.
5. **Small event sample.** 63 FOMC meetings and 96 OpEx months, clustered in
   time. The FOMC cycle t-stat is 3.55 and the OpEx t-stat is 2.49, but the
   effective sample is small and the 2020 observations are extreme.
6. **The 2020 calendar accident.** The January 2020 FOMC window ended
   2020-02-27; the next window (2020-04-29 +3) began 2020-05-04, so the
   strategy was flat through the COVID crash except for two OpEx windows. A
   real-time investor knew that schedule, so this is not look-ahead, but it is
   a one-off alignment that flatters 2020. Adding the cancelled March 2020
   date *raises* CAGR to 63.56% (the added window starts near the bottom), so
   the exclusion is not what creates the pass; the gap alignment is still a
   historical accident.
7. **It is still a long-TQQQ strategy.** Correlation 0.663, beta 0.387. It will
   not replace TQQQ in a strong, calm bull; it is a satellite or a
   crisis-hedged allocation.

## 7. Relationship to the existing research

| | `macro-event-tqqq` G1 | its post-hoc G7 | this |
|---|---|---|---|
| Base | none | none | none |
| FOMC sleeve | +3..+20 | +3..+20 | +3..+20 |
| OpEx sleeve | none | +1..+3 | +1..+3 |
| Volatility filter | none | none | 20/100 ratio, half at 1.25 |
| Status of the combination | not used | post-hoc grid cell | **pre-registered primary** |
| Dev result | 51.06% / 48.83% | 61.42% / 47.78% | **58.26% / 42.60%** |

The combination is the one the earlier study flagged as a follow-up but did not
deliver. This study pre-registers it as the primary, adds the volatility
throttle, and reproduces the unfiltered combination at 62.21% / 47.78% (G8);
the 0.8 pp CAGR difference from the earlier G7 is the adjacent-block treatment.
The filter trades about 4 pp of CAGR for a 5.2 pp lower drawdown and a higher
Sharpe (1.36 vs 1.28), which is the intended risk-management trade.

## 8. Verdict

* **Literal development gate: PASS.** 58.26% CAGR > 36.72%; 42.60% max DD <
  82.29% (and < 60%); Sharpe 1.36 vs 0.82; 1, 5 and 10 bp all pass.
* **Plateau: PASS.** All 8 pre-registered cells and all 28 neighbour cells
  clear the CAGR bar with DD below 52%. The centre is not the best cell.
* **Placebo: PASS.** 0/1,000 circular shifts, 1/1,000 random calendars and
  2/1,000 jittered calendars match or beat the primary on both CAGR and DD. The
  real CAGR is at the 99.2-100th percentile of the nulls.
* **Single-period dependence: PARTIAL.** Ex-2020 is 37.49%, a narrow 0.77 pp
  pass; 2016-2019 alone is 34.38%. The pass is broad across years but
  concentrated in the 2020-2023 regimes.
* **Risk-adjusted: genuine improvement.** Calmar 1.37 vs 0.44; Sortino 1.95 vs
  --; correlation 0.663 and beta 0.387 to TQQQ.
* **Holdout readiness: PASS.** The ex-ante calendar covers the 2026-10-23
  holdout end (85 FOMC / 130 OpEx dates; 63 / 96 in the development panel).
  Extending the list leaves the development result byte-identical, and no
  2024+ price or return data is read.

**Full-window chance.** At 1 bp the development multiple is **39.06x**. The
full 2016-2026 bar of 37.54% CAGR over 10.8 years requires **31.26x**, so the
one-shot 2024-2026 holdout can lose **20.0%** and the full-window CAGR still
clears 37.54%. That is a real cushion, not a guarantee: the strategy has a
42.6% max DD and a crisis-concentrated return profile. The worst rolling
1-year return in the development sample is -13.7%, the worst rolling 2-year
return is +23.6%, and the worst rolling 3-month return is -40.4% (Q4 2018). A
-20% holdout over 2.8 years would be worse than any 2-year stretch in the
development sample, but it is not impossible given the 3-month tail. At 10 bp
the development multiple is 27.35x, so the holdout would need **+14.3%** to
clear the bar; the cost assumption matters.

**Recommendation.** Send G1 to the one-shot holdout at 1 bp, frozen as
specified. Do not re-tune after the holdout. Report G8 (no filter) as the
higher-CAGR / higher-DD variant, not as a replacement.

## 9. Reproduction

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
$env:BT_THREADS = "1"
python research/new/fomc-opex-window/strategy.py
```

`strategy.py` loads `bt.panel(("QQQ","TQQQ","BIL"), "2016-01-04", "2023-12-29",
"1min", warmup_days=0)`. The last bar is 2023-12-29 15:59. The volatility
warmup reads only 2015 daily rows via a parquet row filter, so no 2024+ row is
read into memory. The hardcoded FOMC and OpEx lists extend through 2026-10-23;
events outside the loaded panel are skipped by `event_windows()`, which is why
the development result is unchanged. `result.json` contains the full grid, all
neighbours, the four placebo distributions, the shift curves, the
leave-one-year-out cuts, the event study and the causality test.
