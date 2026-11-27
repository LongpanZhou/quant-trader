# FOMC + post-OpEx calendar TQQQ with a volatility throttle

**Status: pre-registration.** Development window only:
**2016-01-04 -> 2023-12-29**. The 2024-2026 holdout is not loaded by
`strategy.py` and was not inspected. Next-open fills, 2% band, long-only,
weights >= 0 and sum <= 1. TQQQ bar: **36.72% CAGR / 82.29% max DD / 0.82
Sharpe** on 1-minute marks (recomputed on this panel: 36.15% / 82.29% / 0.80).

This is a standalone calendar strategy. It does **not** use the 165-day QQQ
SMA, the 4% intraday stop, the old event-risk overlay, or any price-based
trend signal. Its only price input is a causal realised-volatility throttle.

---

## 1. What is new

The existing `macro-event-tqqq` study owns the FOMC intermeeting drift alone and
reports, as a *post-hoc* grid cell, that adding a post-OpEx sleeve is the one
diversifier that improved both CAGR and drawdown. That cell was not its
deliverable and was not pre-registered. This study takes the **combined
FOMC + post-OpEx calendar as the primary hypothesis**, adds an explicit
volatility throttle, and tests it as a standalone strategy with its own
pre-registered grid, placebo, shift curve and cut tests.

| | `macro-event-tqqq` G1 | its post-hoc G7 | this |
|---|---|---|---|
| Base | none | none | none |
| FOMC sleeve | +3..+20 | +3..+20 | +3..+20 |
| OpEx sleeve | none | +1..+3 | +1..+3 |
| Volatility filter | none | none | 20d/100d vol ratio, half at >1.25 |
| Status of the combination | not used | post-hoc cell | **pre-registered primary** |
| Dev result | 51.06% / 48.83% | 61.42% / 47.78% | see `result.json` |

## 2. Mechanism

**FOMC sleeve.** Scheduled decisions resolve a known macro uncertainty. The
literature documents an announcement premium into the decision (Lucca & Moench
2015; Savor & Wilson 2013) and a non-uniform FOMC-cycle equity premium
(Cieslak, Morse & Vissing-Jorgensen 2019). In this sample the two sessions
after the decision are a positioning unwind (TQQQ -77 bp and -50 bp on average),
and the following three weeks carry the intermeeting drift (+3..+20 returns
+6.33% per cycle on TQQQ, t = 3.55; +2.29% on QQQ, t = 4.03, 74% positive).
The last week before the next meeting is de-risking noise and is excluded.

**OpEx sleeve.** Monthly option expiry is a flow event, not a macro event. The
expiry session itself is weak (TQQQ -65 bp, t = -1.99, only 39% positive), while
the three sessions after expiry are positive (+1.25% per month on TQQQ,
t = 2.49; +0.45% on QQQ, t = 2.70, 64% positive). The reading is expiry
pinning and roll flow reversing into the post-expiry week. This sleeve is
monthly (12/yr) and only partly overlaps the eight-per-year FOMC windows, so
the union raises exposure in the two strongest calendar phases rather than
repackaging one event.

**Volatility throttle.** TQQQ's 3x daily reset has a convex volatility drag:
the same arithmetic mean return compounds worse when volatility is high. A
scale-free stress measure is the ratio of 20-session to 100-session realised
vol. When the short vol is more than 25% above its own 100-day baseline, the
TQQQ target is halved; otherwise it is full. The ratio is causal (computed
through the prior close), needs no full-sample normalisation, and cuts only the
top ~20% of sessions. The throttle is risk management, not an alpha claim: in
the development sample it trades a few points of CAGR for a materially lower
drawdown and a higher Sharpe.

## 3. Exact rules (centre)

Hardcoded calendars (no network access at run time):

* 63 **scheduled** FOMC decision days, 2016-2023, from the Fed's published
  meeting calendars. Unscheduled emergency meetings (2020-03-03, 2020-03-15)
  are excluded because they were not knowable in advance. The scheduled
  2020-03-18 meeting was cancelled and is excluded; a sensitivity that adds it
  is reported.
* 96 monthly OpEx dates: the third Friday, rolled back to Thursday when the
  Friday is a market holiday (2019-04-18 and 2022-04-14 are Good Friday rolls).
  Frozen list.

For each event, with `k` the event's session index:

```
FOMC:    long TQQQ from the open of session k+3 through 15:59 of session k+20
OpEx:    long TQQQ from the open of session k+1 through 15:59 of session k+3
Union:   a session in either window is held; adjacent windows are continuous
Filter:  scale(k) = 0.5 if sigma20(k-1) / sigma100(k-1) > 1.25 else 1.0
         sigma20/sigma100 = annualised stdev of TQQQ daily log returns over the
         last 20 / 100 sessions, known at the prior close
Idle:    BIL
```

* An entry target is set on the prior session's last bar and filled at the next
  session's 09:30 open. An exit target is set at the 15:58 close and filled at
  the 15:59 open, so the position is not carried overnight after the window.
* A scale change inside a live block is applied at the next session's open;
  only calendar block ends are exited at 15:59. This keeps the vol signal
  causal (it uses the prior close).
* The December 2023 FOMC window runs past the development sample and is
  truncated at 2023-12-29. 62 FOMC cycles are complete, 1 is truncated.
* No stop, no trend filter, no shorting, no leverage beyond 100% TQQQ.

## 4. Pre-registered grid (8 cells, 1 bp)

| cell | FOMC window | OpEx window | volatility filter | role |
|---|---|---|---|---|
| **G1 (primary)** | **+3..+20** | **+1..+3** | **ratio > 1.25, half** | mechanism centre |
| G2 | +3..+15 | +1..+3 | ratio > 1.25, half | shorter FOMC tail |
| G3 | +3..+18 | +1..+3 | ratio > 1.25, half | shorter FOMC tail |
| G4 | +3..+22 | +1..+3 | ratio > 1.25, half | longer FOMC tail |
| G5 | +5..+20 | +1..+3 | ratio > 1.25, half | later entry, more unwind skipped |
| G6 | +3..+20 | +1..+2 | ratio > 1.25, half | shorter OpEx sleeve |
| G7 | +3..+20 | +1..+4 | ratio > 1.25, half | longer OpEx sleeve |
| G8 | +3..+20 | +1..+3 | none | filter control |

G1 is fixed **before** the final run. The other cells are a plateau test, not a
selection menu; the report does not switch the primary to a better neighbour.
A coarse development-window scan informed the +3/+20 and +1..+3 boundaries
(disclosed in `report.md`); the holdout was never involved.

## 5. Falsifiers (checked in `report.md`)

1. **QQQ replication.** The same windows on QQQ must show positive cycle means
   with t > 1.5 for both sleeves and > 55% positive cycles. Dev: FOMC
   t = 4.03 / 74% positive; OpEx t = 2.70 / 64% positive.
2. **Random-calendar placebo.** 1,000 circular shifts of the whole calendar
   (same exposure, same joint FOMC/OpEx structure, phase destroyed) and 1,000
   random calendars (8 FOMC anchors per year, 1 OpEx anchor per month, same
   window lengths). G1 should sit above the 95th percentile of CAGR and below
   the 5th percentile of drawdown; the joint fraction with CAGR >= G1 and
   DD <= G1 should be near zero.
3. **Shift curve.** Shifting the FOMC anchors, the OpEx anchors and both by
   -10..+10 sessions should put the peak at shift 0. A flat curve means the
   anchor is irrelevant.
4. **Plateau.** All eight grid cells and the neighbour ladders are reported.
   The pass must not be a single-cell spike.
5. **Costs.** The 10 bp headline must still clear 36.72% CAGR.
6. **Single-period dependence.** Leave-one-year-out; the 2016-2019 and
   2022-2023 subperiods. If dropping 2020 collapses the CAGR below the bar,
   the pass is a one-regime artefact and must be reported as such.
7. **Constant-exposure control.** A constant TQQQ weight equal to G1's mean
   exposure must be materially worse; otherwise the calendar adds nothing over
   a static de-risked TQQQ allocation.

## 6. Expected effect (written before the final run)

* Primary: **52-62% CAGR, 38-45% max DD, 1.25-1.40 Sharpe, 54-60% TQQQ
  exposure**, 550-700 fills.
* Grid: 45-65% CAGR, 40-52% DD. The shorter FOMC tails (G2/G3) and the no-filter
  control (G8) are the likely outliers; all should clear 36.72% except possibly
  the shortest tail.
* Costs: 5 bp loses ~3 pp of CAGR, 10 bp ~6-7 pp; 10 bp still clears the bar.
* Placebo: median CAGR 15-25%, p95 35-45%; G1 above p99. Joint 0-1 of 1,000.
* Leave-one-year-out: dropping 2020 leaves 35-39% CAGR, i.e. the pass survives
  but narrowly; dropping 2022 or 2018 raises it.
* QQQ: positive but roughly one-third of the TQQQ cycle return, consistent
  with leverage and the 3x reset.

## 7. Data and reproducibility

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
$env:BT_THREADS = "1"
python research/new/fomc-opex-window/strategy.py
```

`strategy.py` loads `bt.panel(("QQQ","TQQQ","BIL"), "2016-01-04", "2023-12-29",
"1min", warmup_days=0)`, so the last bar is 2023-12-29 15:59 and no 2024+ row
is read. The volatility warmup uses TQQQ daily closes from 2015-01-02 to
2015-12-31 only (252 rows, read from `TQQQ-1d-yahoo.parquet` and filtered to
dates before the first panel session).
