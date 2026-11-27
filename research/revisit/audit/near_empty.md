# Near-empty audit: six revisit strategies

**Scope.** Development window only: 2016-01-04 .. 2023-12-29 (2,012 sessions).
No 2024-2026 data was used to select, tune, or judge anything. Read-only audit:
no strategy file, threshold, weight matrix, website asset, or git state was
changed. The holdout/10y/5y numbers that some `result.json` files contain were
not used.

**Method.** Raw event counts were recomputed independently from
`data/intraday-hf/{QQQ,TQQQ,BIL}-1m.parquet` using only pandas/numpy: first bar
open, last bar close, session high/low/volume. The strategy counts then come
from importing each `strategy.py` and calling its side-effect-free
`build_weights`/`info` (never `main()`). The two counts are compared date by
date. The probe scripts are listed in section 7. No strategy code was used for
the raw counts.

**Headline.** **No event-count bug was found.** All six strategies reproduce
their stated rules, their strategy counts match the independent raw counts (with
the expected suppression of signals that arrive while a position is open), and
there is no wrong column, wrong sign, wrong unit, or session-boundary error that
causes the near-empty samples. The samples are the event definitions. At least
four of the six are clearly below their own design document's sample-size bar;
`gap-fill-fade` is below the bar as literally written (20-40 shorts per year) but
in range if that meant 20-40 over eight years; `gap-capitulation-reversal` is
inside its 30-50 range. The 2% rebalance band is not the cause: entries and full
exits always trade, and a band=0 vs band=0.02 run leaves the event counts and
returns essentially unchanged (section 3.5).

## 1. Summary table

| Strategy | Stated event rule (source) | Raw count (independent) | Strategy count | Consistent? | Design document's own bar | Binding condition / likely cause | Bug or by design | Exact fix if bug |
|---|---|---|---:|---|---|---|---|---|
| `stop-reentry-recovery` | TQQQ intraday `<= -3%` AND `r_t - 3*r_q <= -1pp` (`report.md` L93-98) | **1** day (2020-03-12) | **1 event, 1 entry, 1 stop** | Yes | `>= 100` events (`report.md` L169) | The 1pp excess is the binding condition: only 3 days in 8y, 2 of them *up* days. The 3% drop alone has 282 days. | By design as coded; design/calibration error. The rule is genuinely rare. Not a code bug. | None. Do not loosen; retire or re-specify. |
| `volume-orderflow` | QQQ `rvol >= 1.5` AND `close/open <= -0.8%` AND `CLV >= 0` (`spec.md` L31-46) | **3** days (2020-09-04, 2021-05-04, 2021-07-27) | **3 events, 15 sessions long** | Yes | 15-30 in 8y (`report.md` L80); ~40 (`hypothesis.md` L136-137) | `CLV >= 0` on a down close: only 6 days in 8y, 3 with rvol. Mean CLV on down days is -0.67. | By design/rare; the design's expected count is wrong. Not a code bug. | None. Do not loosen; retire or re-specify. |
| `gap-fill-fade` | +0.10..0.75% gap, weak 10d tape, stressed vol, 10:00 confirmation (`spec.md` L21-43) | **25** days | **25 trades, 101 fills** | Yes | 20-40 shorts per year (`report.md` L174) -> actual 3.1/yr (if the report meant 20-40 over 8y, 25 is in range) | weak+stress+band 95 -> gap_open 77 -> confirm 25. | By design; 25 is a real sample. Low CAGR is BIL carry + 0.043% short exposure, not missing events. | None. |
| `dynamic-leverage-throttle` | `v20 >= 1.25*v60`, `v5 <= 0.85*v20`, `-35% <= dd252 <= -8%` (`report.md` L101-113) | **32** eligible days | **6 entries, 6 exits** | Yes (26 suppressed by holds) | 10-25 entries (`report.md` L244); `<12` is a falsifier (`hypothesis.md` L144) | 32 eligible days cluster into 6 episodes; ~15-session holds. | By design (one position, clustered signals). Not a code bug. | None. Underpowered vs its own bar. |
| `vol-kelly-overlay` | `RV5/RV20 >= 1.5`, 10d drawdown `<= -5%`, up close (`report.md` L100-115) | **15** signal days | **11 entries** | Yes (4 suppressed by holds) | `<15` valid entries is a falsifier (`report.md` L195) | 4 signals occur while an earlier event is still held. | By design (one position); borderline 11 vs 15. Not a code bug. | None. Underpowered. |
| `gap-capitulation-reversal` | `(QQQ close-to-close <= -2% OR QQQ low <= -3%)` AND `rvol <= 1.2` AND `20d return <= -3%` (`SPEC.md` L30-54) | **30** days | **30 events, 24 trade starts** | Yes (6 overlaps) | 30-50 events (`report.md` L120) | 30 events, 6 overlap an open hold and extend it -> 24 starts. | By design; inside the stated range. | None. |

Notes: "Raw count" is the number of session-level signal days recomputed from
the 1m panel; "Strategy count" is what the strategy's own `info` reports.
"Consistent?" means the dates and counts agree, not that the sample is large
enough.

## 2. Per-strategy findings

### 2.1 `stop-reentry-recovery` - 1 event

**Stated rule.** `report.md` L93-98:

```
r_t    = TQQQ_close[d] / TQQQ_open[d] - 1
r_q    = QQQ_close[d]  / QQQ_open[d]  - 1
excess = r_t - 3 * r_q
overshoot[d] = (r_t <= -0.03) and (excess <= -0.01)
```

`strategy.py` L78-86 implements exactly that, with `DROP = 0.030` (L54) and
`EXCESS = 0.010` (L55). Entry is the next session at the 09:31 open (L117-128),
the add-on is at the 09:31 open of the following session (L131-135), the 2% stop
is anchored to the initial entry (L141-146), and the exit is the close of the
third held session (L148-155). All of that matches `report.md` section 6.

**Independent raw count.** 2,012 sessions. `TQQQ intraday <= -3%`: **282** days.
`excess <= -1pp`: **3** days (2020-03-12, 2020-03-13, 2020-03-17). Joint:
**1** day, 2020-03-12.

**Strategy count.** `build_signal` returns 1; `info` reports `events=1`,
`entries=1`, `stops=1`, `event_dates=["2020-03-12"]`,
`entry_dates=["2020-03-13"]`, `stop_dates=["2020-03-13"]`. The one trade:
entry at 6.540 (TQQQ 09:31 open on 2020-03-13), stop threshold 6.409, the 09:36
close 6.403 triggers, exit at the 09:37 open 6.401 (about -2.13%). TQQQ then
rallied to 7.135 by the close. The stop was legitimate; the trade was simply
unlucky. It is not a bug in the stop or the entry price.

**Why 1, not 100.** The binding condition is the **1pp excess**, not the 3%
drop. The excess distribution is centred at roughly -0.014pp with a 0.12pp
standard deviation; 1pp is about 8 standard deviations and occurs 3 times in
eight years. Two of the three excess days are *up* days:

| date | TQQQ intraday | QQQ intraday | excess |
|---|---:|---:|---:|
| 2020-03-12 | -10.05% | -2.66% | -2.08pp |
| 2020-03-13 | +9.13% | +3.72% | -2.03pp |
| 2020-03-17 | +10.03% | +3.77% | -1.27pp |

The report's economic story is a *down-day* rebalancing overshoot. The data says
the large negative excess is mostly an *up-day* beta lag: on down days TQQQ
tracks 3x QQQ closely, while after a drawdown its up-day beta is below 3. That
is why the joint with `r_t <= -3%` leaves only the COVID crash day. This is a
design/mechanism mismatch, not an implementation error.

Threshold sensitivity (diagnostic only, not a recommendation): at a 0.5pp
excess the joint is 2; at 0.25pp it is 16; at 0.1pp it is 52. Even a 0.1pp
threshold would not reach the report's 100-event bar. Loosening the threshold
would be tuning, and the rule as written is rare.

**Consistency with the original.** The original `research/agents2/`
`stop-reentry-recovery` reports **160 stop events** (2016-2026), but those are
4% TQQQ stop events on a continuously long 165-day QQQ base, not this
relative-overshoot event. The rebuild replaced the stop trigger with a 3%
intraday drop plus 1pp excess; the two counts are not comparable.

**Verdict.** By design as coded; the design's own `>=100` event bar is
unreachable. Not a code bug. Do not loosen the threshold; retire or re-specify.

**Minor, non-causal issue.** `strategy.py` L161 gates a new signal with
`k >= hold_until`. After a stop, `hold_until` still points at the originally
scheduled exit, so a new overshoot signal on the next session is ignored until
the old hold expires, although `report.md` section 6.5 says a stopped event is
finished. With the current one-event sample this suppresses nothing. If the
report's intent is authoritative, the one-line fix is to set `hold_until = k`
inside the stop block (L141-146). Not applied.

### 2.2 `volume-orderflow` - 3 events

**Stated rule.** `spec.md` L31-46:

```
rvol[d]     = q_vol[d] / mean(q_vol[d-20 .. d-1])
intraday[d] = q_close[d] / q_open[d] - 1
clv[d]      = ((q_close - q_low) - (q_high - q_close)) / (q_high - q_low)
event[d]    = rvol[d] >= 1.5 AND intraday[d] <= -0.008 AND clv[d] >= 0
```

`strategy.py` L87-112 implements exactly that; the holding-window mapping
(`W[d]` = position during session `d`, last bar writes `W[d+1]`) is L132-162 and
matches `spec.md` section 3.

**Independent raw count.** The marginal counts are: `rvol >= 1.5` **192**,
`intraday <= -0.8%` **342**, `clv >= 0` **1,184**, `rvol & intraday` **96**,
`rvol & clv` **67**, `intraday & clv` **6**, joint **3**. Dates: 2020-09-04,
2021-05-04, 2021-07-27. The strategy's own `session_features` gives the same
three dates (marginal `clv` 1,183; a one-day raw-vs-adjusted difference).

**Strategy count.** `events=3`, `sessions_long=15`, `exposure=0.007455`. The
result is CAGR 0.87%, max DD 16.66% at 1 bp, status `pending_audit`.

**Why 3.** The binding condition is `CLV >= 0` on a down close. The mean CLV on
a down day is **-0.67** (the close is usually near the low); a down day that
closes in the top half of its range is a long lower wick, and only 6 such days
exist in the 2,012-session dev sample. Of those 6, 3 also have `rvol >= 1.5`.
The funnel is exactly the stated conjunction. With a looser `CLV >= -0.25` it
would be 16; with no CLV filter 96; if `intraday` were measured as
`low/open <= -0.8%` instead of `close/open`, 34 at `CLV >= 0`. None of those is
the stated rule, so 3 is the correct count for what was written.

**Consistency with the original.** The original `research/agents2/`
`volume-orderflow` reports **195 stop events** and 110 volume-rearmed events over
2016-2026. Those are 4% TQQQ stop events on the shared 165-day base, not the
new QQQ participation-exhaustion event. Not comparable.

**Verdict.** By design/rare; the design document's 15-30 (and the hypothesis's
~40) is inconsistent with the rule. The hypothesis's exploratory `n = 142`
(`hypothesis.md` L120-129) used a looser event: rvol > 1.5 and a down close, with
no intraday-decline or close-off-the-low filter. The frozen spec added both, and
the count fell to 3. This is an expectation error, not a coding bug. Do not
loosen the filter; retire or re-specify.

### 2.3 `gap-fill-fade` - 25 events

**Stated rule.** `spec.md` L21-43: a +0.10% to +0.75% QQQ opening gap, a weak
10-day tape (prior close below the 10-day SMA and negative prior 5-day return),
stressed volatility (prior 20-day vol above its trailing 1-year median), a
negative first 30 minutes at the 10:00 close, and the gap still open
(`close[10:00] > prior close`). Entry is the 10:01 open, the target is the prior
close, the stop is the opening-range high with a +0.2% floor and +1.5% cap, the
time stop is 11:30, and the position is flat overnight.

`strategy.py` L121-152 computes exactly those conditions, and L161-222 builds the
trade. The signal uses the 10:00 close (`f+30`), the fill uses the 10:01 open
(`f+31`), and the exit is at the next bar's open after the stop/target/time
condition. The one-bar look-ahead that was removed in tuning (the old
`opens[e] <= target` check) is correctly replaced by `closes[e-1] <= target`
(L171-174). This matches `spec.md` section 2, point 5.

**Independent raw count.** **25** signal days. The strategy's own signal frame
gives the funnel: weak 640, stress 943, gap band 715, gap still open 1,112,
10:00 confirmation 942; `weak & stress & band` 95; `+gap_open` 77; `+confirm`
25. Removing any one condition gives:
without weak 90, without stress 55, without band 55, without gap_open 43,
without confirm 77. The 25 is the true rate of the stated conjunction, not a
missing-event artifact.

**Strategy count.** `n_events=25`, `event_study.n=25`, 101 fills. Dates:
2017-06-14, 06-30, 07-03, 07-05, 08-01, 11-30, 12-04, 12-28; 2018-03-27,
04-24, 07-31, 08-16, 11-13, 12-13, 12-21, 12-28; 2019-05-14, 08-27;
2020-01-29, 09-18, 10-22; 2021-10-13; 2022-02-18, 11-08, 11-30.

**Why the CAGR is BIL-like.** 25 trades over eight years is 3.1 per year, so the
strategy is not "near-empty" in event count. The event study mean is +0.0556%
per trade, t = 1.01, bootstrap p = 0.152. The actual risk-asset exposure is
**0.0432%** of equity-time (25 trades x about 22 minutes x an average size near
0.5). The 1.43% CAGR is therefore almost entirely BIL carry (the BIL benchmark
is 1.39%); the 0.48% max DD is BIL-like. The low return is not a missing-event
bug; it is a tiny, short-lived short overlay.

**Consistency with the original.** The original `research/agents2/gap-fill-fade`
reports **160 stop events** and 172 overlay days. Those are 4% TQQQ stop events
on the long-only 165-day base, not standalone gap-up shorts. The original
standalone gap-down fades had 316 / 119 / 20 entries for 0.5% / 1.0% / 2.0%
gaps; the rebuild is a different direction (short gap-up fade) and a different
event. Not comparable. The report's expectation of "20-40 shorts a year" is
about 10x the actual 3.1/year.

**Verdict.** By design; 25 is a real sample. The low CAGR is BIL, not a code
bug. Do not tune.

**Minor, non-causal issues.**

- `strategy.py` L132: `vol_med = pd.Series(vol20).rolling(252,
  min_periods=60).median()` includes the current session's `vol20`; the spec says
  the median of the prior 252 sessions. Recomputing with `.shift(1)` still gives
  25 events, so this is immaterial. One-line fix if desired: append `.shift(1)`
  after the rolling median.
- `hypothesis.md` L51 says "or the 10:01 entry is at or below the prior close,
  skip the session"; the code uses the 10:00 close (L173) to avoid a one-bar
  look-ahead, and `spec.md` L41-42 only requires the 10:00 close. The hypothesis
  is stale; the code is right.

### 2.4 `dynamic-leverage-throttle` - 6 entries

**Stated rule.** `report.md` L101-113 and `hypothesis.md`:

```
v20 >= 1.25 * v60          (vol shock, TQQQ daily log returns)
v5  <= 0.85 * v20          (shock decaying)
-0.35 <= dd252(QQQ) <= -0.08
```

Entry at the next session's open, size `min(0.75, 0.30/v20)`, one position at a
time, exits on vol normalisation (`v20 <= 1.05*v60`), recovery (`dd >= -3%`),
catastrophe (`dd <= -40%`), or a 60-session time stop, with a 5-session cooldown.
`strategy.py` L141-185 computes the indicators and entry conditions exactly;
L215-285 builds the weights with the fill at `k+1`. One documented tuning change:
`use_reaccel=False` (L58) disables the report's re-acceleration exit. That
lengthens holds (it can only reduce the number of entries), but it does not
change the 32 eligible signal days or the entry rule. The exits in the result
are five vol-normalised and one recovered; no re-acceleration exit fires.

**Independent raw count.** **32** eligible signal days. The strategy's own
`daily_signals` gives `v20 >= 1.25*v60` 303, `v5 <= 0.85*v20` 901, `dd` in band
518; the joint is 32. The 32 days cluster into six episodes: 2016-02 (3 days),
2018-11 (5), 2019-05/06 (2), 2020-03/04 (14), 2020-09 (7), 2022-05 (1). The
strategy's own `entry_ok` list also has 32 dates; the independent raw count
differs on one boundary date (2018-11-09 vs 2016-02-04) because the raw close is
unadjusted, but the six entry clusters are identical.

**Strategy count.** 6 entries, 6 exits, median hold 14.5 sessions, actual
risk-asset exposure **1.17%**. Result: CAGR 5.24%, max DD 9.16%, Sharpe 1.06,
corr 0.108, status `pending`.

**Why 6.** The event is clustered. The strategy holds about 15 sessions, so the
later eligible days in each cluster are ignored by the one-position rule. The
six entries are the first eligible day of each cluster: 2016-02-04, 2018-11-02,
2019-05-31, 2020-03-23, 2020-09-16, 2022-05-25. That is the correct number of
independent episodes; it is not a missing-event bug. The report's expected
"10-25 entries" and its `<12` falsifier are too high for a one-position rule
with 15-session holds.

**Consistency with the original.** The original `dynamic-leverage-throttle` was
continuous inverse-vol sizing on the 165-day QQQ SMA base; it had no discrete
entry clock. The rebuild is episodic. The two counts are not comparable.

**Verdict.** By design (one position, clustered signals). Underpowered against
its own 12-entry bar, but not a code bug. Do not tune.

**Minor, non-causal issue.** `strategy.py` L261-262 stores
`"session": int(k + 1)` (the fill session) but `"date": str(sig["dates"]
[sig["first"][k]])` (the signal day), so the reported "date" is one session
before the fill. The P&L uses `session`, so returns are correct. One-line fix:
use `sig["dates"][sig["first"][min(k + 1, nd - 1)]]`, or rename the field to
`signal_date`. Not applied.

### 2.5 `vol-kelly-overlay` - 11 entries

**Stated rule.** `report.md` L100-115: TQQQ within-day 1-minute realised variance
`RV`, `v5 = sqrt(252*mean(RV[t-4..t]))`, `v20 = sqrt(252*mean(RV[t-19..t]))`,
entry when `v5/v20 >= 1.50`, QQQ 10-day drawdown `<= -5%`, and today's QQQ close
is up. Size `clip(0.35/v20, 0.25, 0.75)`. Exit on the 3-session clock, the
`v5/v20 < 1.00` normalisation, or a 4% QQQ stop. `strategy.py` L99-162 implements
exactly that; the entry fills at the next open.

**Independent raw count.** **15** signal days: 2018-02-06, 02-09, 02-12,
2018-10-12, 2019-05-14, 2019-08-06, 08-07, 2020-02-26, 02-28, 03-02, 03-04,
03-17, 2020-09-09, 2021-02-26, 2022-01-26. The marginal counts are
`ratio >= 1.5` 50, `dd10 <= -5%` 221, up close 1,123, `ratio & dd` 33, joint 15.
The strategy's own `signal` mask sums to 15 and the dates match.

**Strategy count.** `n_events=11`; four signals occur while an earlier event is
still held, so they are not entries. Event study `n=11`, mean +0.0146%,
bootstrap p = 0.488. Result: CAGR 1.81%, max DD 19.22%, corr 0.273, status
`pending_test`. Actual risk-asset exposure **0.91%**.

**Why 11.** The holding period is 1-3 sessions, so 4 of the 15 signals arrive
inside an open event and are ignored. The report's falsifier is "fewer than 15
valid entries" (`report.md` L195); the strategy has 11 entries, so it is
borderline underpowered. If the bar is read as raw signals, 15 meets it; the
strategy's own `n_events` is 11. This is a definition of "entry", not a coding
bug.

**Consistency with the original.** The original `research/agents/vol-kelly-overlay`
was a continuous vol ladder on the 165-day SMA base; it had no discrete entries.
The rebuild is a standalone event strategy. The counts are not comparable.

**Verdict.** By design (one position); borderline sample. Not a code bug. Do not
tune.

### 2.6 `gap-capitulation-reversal` - 30 events / 24 starts

**Stated rule.** `SPEC.md` L30-54 and `report.md` L61-73:

```
event = (QQQ close-to-close <= -2.0% OR QQQ intraday low <= -3.0% vs prior close)
        AND QQQ volume <= 1.2x the prior 20-session mean
        AND QQQ 20-day return <= -3.0%
```

Entry at the next session's open, TQQQ if 20-day realised vol <= 30% else QQQ,
hold three sessions, exit on the third close / a QQQ close below the event-day
low / an 8% hard stop. The current file has `event_low_stop=False` (documented
tuning at `strategy.py` L50-54); that affects exits, not the event count.

**Independent raw count.** **30** event days. The strategy's own `event_masks`
gives the marginal counts: cap 150, quiet 1,533, oversold 373, `cap & quiet` 46,
`cap & oversold` 88, joint 30. The independent raw count and the strategy's event
dates agree on all 30.

**Strategy count.** 30 events, 24 trade starts, 1 hard stop, 23 time exits,
actual risk-asset exposure **3.95%**. Result: CAGR 8.30%, max DD 10.26%,
Sharpe 0.88, corr 0.032, status `passed`.

**Why 24 starts, not 30.** Six events occur while a position is open; the spec
says a new event extends the three-session window and resets the asset/entry
price. Those six extend an existing trade rather than start a new one. That is
by design and is the correct mapping from 30 events to 24 starts.

**Consistency with the original.** The original standalone event (gap <= -1.5%,
1-day hold, 4% stop) had 175 fills, about 87 entries, over 10y. The rebuild adds
the quiet-volume filter, the 20-day oversold filter, and the three-session hold;
30 events over 8y is the deliberate narrowing and is inside the stated 30-50
range. Not a bug.

**Verdict.** By design; 30 is in the design's expected range and the event study
passes (n=30, mean +6.03%, t=2.89, bootstrap p=0.001). No bug.

## 3. Cross-checks required by the brief

### 3.1 Off-by-one / index alignment

Checked for every strategy; no error that changes the event count:

- **Session opens/closes.** All strategies use `first`/`last` from
  `bt.day_bounds` or `bt.session_dates`; the first bar is 09:30 and the last is
  15:59 (or the half-day close). The QQQ and TQQQ 1m files have no late first
  bars; the early last bars are the known half-days.
- **Signal vs fill.** `stop-reentry`: signal at close `d`, entry at `d+1` 09:31
  open (`opens[f+1]`), correct. `volume-orderflow`: `W[d]` is written on the
  last bar of `d-1` and fills at the open of `d`, correct. `gap-fill`: signal at
  `f+30` (10:00 close), fill at `f+31` (10:01 open), correct. `dynamic`:
  `day_w[k+1]` is the fill session, correct. `vol-kelly`: signal at close `i`,
  fill at `opens[i+1]`, correct. `gap-capitulation`: signal at close `s-1`,
  `pos[last[s-1]]` fills at the 09:30 open of `s`, correct.
- **Wrong column.** `stop-reentry` uses column 1 (TQQQ) for the trade and column
  0 (QQQ) for the signal. `volume-orderflow` uses column 0 for QQQ and column 1
  for TQQQ. `gap-fill` uses column 0 (QQQ) and the synthetic inverse QQQ column
  3. `dynamic` uses QQQ for drawdown and TQQQ for vol. `vol-kelly` uses TQQQ RV
  and QQQ drawdown. `gap-capitulation` uses QQQ for the signal and columns 0/1
  for the expression. All match the specs.
- **Date labels.** One reporting-only off-by-one: `dynamic` `entries["date"]` is
  the signal date while `session` is the fill session (section 2.4). No return
  effect.

### 3.2 Sign and threshold direction

All six match their stated rules; none is inverted:

- `stop-reentry`: `r_t <= -0.03` and `excess <= -0.01`. Correct for "falls at
  least 3% and underperforms 3x QQQ by at least 1pp".
- `volume-orderflow`: `rvol >= 1.5`, `intraday <= -0.008`, `clv >= 0`. Correct
  for "high volume, down close, close in the upper half".
- `gap-fill`: gap in `[+0.0010, +0.0075]`, `r30 < 0`, `close1000 < open0930`,
  `close1000 > prior`. Correct for a failed gap-up that has not filled.
- `dynamic`: `v20 >= 1.25*v60`, `v5 <= 0.85*v20`, `-0.35 <= dd <= -0.08`.
  Correct for a decaying vol shock inside a drawdown.
- `vol-kelly`: `ratio >= 1.5`, `dd <= -0.05`, up close. Correct.
- `gap-capitulation`: `close-to-close <= -2% OR low <= -3%`, `rvol <= 1.2`,
  `20d return <= -3%`. Correct.

The only sign-related observation is economic, not a coding error: the
`stop-reentry` negative-excess days are mostly *up* days (section 2.1), which is
why the joint with a 3% down day is 1.

### 3.3 Units

All thresholds are fractions of return, not percent points accidentally scaled:

- `stop-reentry`: 0.030 = 3%, 0.010 = 1pp, 0.020 = 2% stop.
- `volume-orderflow`: 1.5x rvol, -0.008 = -0.8%, CLV in [-1, 1] with 0 =
  midpoint.
- `gap-fill`: 0.0010 = 0.10%, 0.0075 = 0.75%, 0.10 = 10% vol target.
- `dynamic`: 1.25/0.85 are ratios, -0.08/-0.35 = -8%/-35%, 0.30 = 30% target.
- `vol-kelly`: 1.50 ratio, -0.05 = -5%, 0.35 = 35% vol target, 0.04 = 4% QQQ
  stop.
- `gap-capitulation`: -0.02 = -2%, -0.03 = -3%, 1.2x volume, 0.30 = 30% vol.

Annualised volatility is used only in ratios (`v5/v20`, `v20/v60`) or against an
annualised target (`0.30/v20`, `0.10/vol20`), so the units cancel or are
consistent. No 0.03-vs-3.0 or bps-vs-percent error was found.

### 3.4 Data coverage

- The QQQ/TQQQ/BIL 1m files cover 2016-01-04 .. 2026-10-23; the dev slice is
  2016-01-04 .. 2023-12-29, 2,012 sessions.
- QQQ has a 09:30 open and a 15:59 (or half-day) close on every dev session.
  TQQQ has a few missing minutes but a 09:30 open and a session close on every
  dev session; the panel forward-fills the gaps, which cannot change a
  session-level open/close.
- Volume, high and low are present for QQQ; `volume-orderflow` and
  `gap-capitulation` use them. `gap-fill` uses QQQ high/low for the opening
  range and target. No signal requires SPY or NDX. No field is missing or
  forward-filled in a way that suppresses events.

### 3.5 The 2% rebalance band

The band is **not** the cause of the near-empty samples.

- In `bt.py` `simulate_python` L437-484 and in `research/simcore/src/lib.rs`,
  new buys and full exits always trade; the band only skips *resizes* that are
  within 2% of book. The Rust header says it explicitly: "exits and new entries
  always trade".
- Empirical check on the actual weights:

  | Strategy | band=0 fills | band=0.02 fills | band=0 CAGR | band=0.02 CAGR | entries |
  |---|---:|---:|---:|---:|---:|
  | `gap-fill-fade` | 1,093 | 101 | 1.4317% | 1.4319% | 25 |
  | `dynamic-leverage-throttle` | 65,018 | 65 | 5.19% | 5.24% | 6 |

  The band changes turnover/fill count by 10-1,000x but leaves the event count
  and the CAGR essentially unchanged.
- The smallest event weights are 0.10 (`gap-fill` floor), 0.113 (`dynamic`), and
  0.25 (`vol-kelly`), all above 2% of book, so even if the band were applied to
  entries it would not block them.

### 3.6 `exposure` in `result.json` is BIL, not risk exposure

`bt.stats.exposure` is `mean((equity - cash)/equity)`. BIL is an asset, so a
100% BIL book reports about 100% exposure. The actual mean risk-asset weights
from the strategy weight matrices are:

| Strategy | actual risk-asset mean weight | result.json "exposure" |
|---|---:|---:|
| `stop-reentry-recovery` | 0.000004 (0.0004%) | 0.999999 |
| `volume-orderflow` | 0.007482 (0.75%) | 0.999999 |
| `gap-fill-fade` | 0.000432 (0.043%) | 0.999999 |
| `dynamic-leverage-throttle` | 0.011728 (1.17%) | n/a (not saved) |
| `vol-kelly-overlay` | 0.009067 (0.91%) | n/a (not saved) |
| `gap-capitulation-reversal` | 0.039473 (3.95%) | 0.999999 |

Consequence: `stop-reentry`'s measured correlation (-0.001) and `gap-fill`'s
expected correlation (its 0.043% risk exposure makes it BIL-like; the value is
not saved in `result.json`) are artifacts of being in BIL, not evidence of a
distinct edge. `gap-fill`'s 0.48% DD is also BIL-like, while `stop-reentry`'s
1.81% DD is the one stopped trade. `vol-kelly`'s
1.81% CAGR is close to BIL but its 19.22% DD is real, produced by its few 25-75%
TQQQ events. The `volume-orderflow` 16.66% DD is real (100% TQQQ for 15
sessions). The `dynamic` 9.16% and `gap-capitulation` 10.26% DDs are real. The
`stop` 1.25% CAGR is BIL carry minus the stopped trade's loss.

## 4. Why the original strategies had more events

The originals are not the same events. This is the main reason the rebuild
counts look small:

| Strategy | Original count | Original event | Rebuild event | Why the counts differ |
|---|---:|---|---|---|
| `stop-reentry-recovery` | 160 | 4% TQQQ stop on a continuously long 165-day base | 3% intraday drop + 1pp excess | The 4% stop is common; the 1pp excess on a down day is not. |
| `volume-orderflow` | 195 (110 volume-rearmed) | 4% TQQQ stop on the 165-day base | QQQ rvol + down close + CLV | A stop overlay vs a participation-exhaustion event. |
| `gap-fill-fade` | 160 stop events / 172 overlay days | Long-only step-aside overlay on the 165-day base | Standalone short QQQ on failed gap-ups | Different direction and different event; the original never shorted. |
| `dynamic-leverage-throttle` | no discrete entries | Continuous inverse-vol sizing on the 165-day base | Episodic vol-shock/drawdown entry | The original had no entry clock; the rebuild holds one position per episode. |
| `vol-kelly-overlay` | no discrete entries | Continuous vol ladder on the 165-day base | Episodic RV-spike/oversold entry | Same: continuous vs episodic. |
| `gap-capitulation-reversal` | 175 fills (~87 entries) | Gap <= -1.5%, 1-day hold, 4% stop | Quiet volume + 20d oversold + 3-day hold | The rebuild deliberately adds two filters and a longer hold; 30 is inside its 30-50 design range. |

The original counts are full-sample (2016-2026) and are used here only to explain
the difference, not to select or tune anything.

## 5. Design expectations vs the rules

| Strategy | Design's own bar | Actual dev count | Source | Outcome |
|---|---|---:|---|---|
| `stop-reentry-recovery` | `>= 100` events | 1 | `report.md` L169 | Fail; unreachable even at 0.1pp (52) |
| `volume-orderflow` | 15-30 in 8y; ~40 | 3 | `report.md` L80; `hypothesis.md` L136-137 | Fail; rule is rarer than the exploratory event |
| `gap-fill-fade` | 20-40 per year | 25 total (3.1/yr) | `report.md` L174 | Fail as written (~10x too high); if the bar meant 20-40 over 8y, pass |
| `dynamic-leverage-throttle` | 10-25 entries; `<12` falsifier | 6 | `report.md` L244; `hypothesis.md` L144 | Fail; clustering, not a bug |
| `vol-kelly-overlay` | `<15` entries is a falsifier | 11 entries (15 signals) | `report.md` L195 | Borderline fail; 4 suppressed by holds |
| `gap-capitulation-reversal` | 30-50 events | 30 | `report.md` L120 | Pass (low end) |

At least four of six are clearly below their own sample-size bar; `gap-fill`
depends on whether its "20-40 per year" was a typo for the eight-year total.
That is a design/expectation problem, not an implementation problem. The correct
response is to retire or re-specify, not to loosen thresholds to reach the
expected count.

## 6. Confirmed bugs and minor issues

**No bug causes the near-empty event counts.** The raw counts and the strategy
counts agree for all six; there is no wrong column, wrong sign, wrong unit,
wrong session boundary, or missing data field. The following are real but
**non-causal** issues. None changes an event count or the conclusion, and none
was applied.

1. **`dynamic-leverage-throttle/strategy.py:261-262` - date label off by one.**
   `"session": int(k + 1)` is the fill session, but `"date":
   str(sig["dates"][sig["first"][k]])` is the signal day. The P&L uses
   `session`, so returns are correct; only the reported date is one session
   early. Fix: use `sig["dates"][sig["first"][min(k + 1, nd - 1)]]`, or rename
   the field to `signal_date`.

2. **`stop-reentry-recovery/strategy.py:161` - post-stop gate.**
   `if sig[k] and pos == 0.0 and k >= hold_until:` waits until the original
   scheduled exit after a stop, although `report.md` section 6.5 says a stopped
   event is finished. With the current one-event sample this suppresses nothing.
   If the report's intent is authoritative, set `hold_until = k` in the stop
   block (L141-146).

3. **`gap-fill-fade/strategy.py:132` - `vol_med` includes the current
   `vol20`.** The spec says the median of the prior 252 sessions. Verified 25
   events either way, so it is immaterial. Fix: append `.shift(1)` after the
   rolling median.

4. **`gap-fill-fade/hypothesis.md:51` - stale 10:01-entry skip.** The
   hypothesis says to skip if the 10:01 entry is at or below the prior close;
   the code uses the 10:00 close to avoid a one-bar look-ahead and matches
   `spec.md` section 2, point 5. This is a documentation mismatch, not a code
   bug.

No threshold was changed and no strategy logic was edited. The recommendation is
to retire or re-specify the clearly underpowered strategies (and `gap-fill` if
its "20-40 per year" bar was literal); `gap-capitulation-reversal` is inside its
stated 30-50 event range and is the only one whose near-empty sample is both by
design and large enough for its own evidence bar.

## 7. Reproducibility

The raw counts, funnels, band check, and exposure check were produced by these
scripts (they import the strategy modules only for the comparison counts; the
raw counts use pandas/numpy on the parquet files only):

- `C:\Users\27175\AppData\Local\Temp\opencode\probe_all.py` - all six raw counts
- `C:\Users\27175\AppData\Local\Temp\opencode\probe_funnels.py` - binding-condition funnels
- `C:\Users\27175\AppData\Local\Temp\opencode\probe_strategy.py` - strategy `info` counts/dates
- `C:\Users\27175\AppData\Local\Temp\opencode\probe_band.py` - band=0 vs 0.02
- `C:\Users\27175\AppData\Local\Temp\opencode\probe_exposure.py` - actual risk-asset weights

Data: `data/intraday-hf/{QQQ,TQQQ,BIL}-1m.parquet`, dev slice only. The strategy
files, website, and git state were not modified. The holdout/10y/5y windows in
some `result.json` files were not used.
