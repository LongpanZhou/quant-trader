# Data check — revisit rebuild

Checked 2026-11-26. Scope: the local data available for `research/revisit`,
development 2016-01-04 → 2023-12-29 and holdout 2024-01-02 → 2026-10-23.
No strategy backtests were run. Paths are relative to the repo root.

## Bottom line

The QQQ/TQQQ/BIL archive covers the full development and holdout periods, and
the two windows are cleanly separable. The adjusted daily series are sound.
Four things must be handled before results are trustworthy:

1. **11 pre-2021 half-days contain after-hours bars.** They run to 15:5x
   instead of 13:00. Truncate every half-day at 13:00 (21 dates listed below).
   Otherwise last-bar exits, daily closes and minute marks on those days use
   after-hours prices; the error reaches −0.62% (QQQ) and −1.89% (TQQQ) on
   2018-12-24.
2. **2026-05-26 is a bad-print day in the holdout.** QQQ and TQQQ contain
   repeated, impossible high/low values (TQQQ highs 8.4–11.0% above the bar
   body, four 5-minute bars affected). Any strategy using intraday highs/lows
   must clean or skip this day. TQQQ 2022-06-21 has a smaller suspect low
   cluster in development.
3. **`bt.panel` has no daily warm-up at the dev start.** It builds daily bars
   from the 1-minute archive, which begins 2016-01-04. The first 165-day SMA on
   that panel is 2016-08-26. For daily features from 2016-01-04, read
   `data/intraday-hf/*-1d-yahoo.parquet`, which starts 2015-01-02 (252 warm-up
   sessions; first 165-day SMA 2015-08-27).
4. **SPY cannot be a traded asset or a 1-minute full-period benchmark.** Local
   SPY 1-minute data covers only 2026-08-31 → 2026-11-20 (39 real holdout
   sessions), and there is no SPY intraday data in development. A complete SPY
   daily series was fetched to `data/round3/yahoo/` for the buy-and-hold
   benchmark only.

## 1. Files and coverage

| Dataset | Rows | Coverage | Notes |
|---|---:|---|---|
| `data/intraday-hf/QQQ-1m.parquet` | 1,115,162 raw / 1,057,023 RTH | 2016-01-04 09:30 → 2026-10-23 15:59 ET | 2,718 sessions |
| `data/intraday-hf/TQQQ-1m.parquet` | 1,109,359 raw / 1,051,741 RTH | same | 2,718 sessions |
| `data/intraday-hf/BIL-1m.parquet` | 949,046 raw / 825,961 RTH | same | 2,718 sessions; sparse |
| `data/intraday-hf/*-1d-yahoo.parquet` | 2,970 each | 2015-01-02 → 2026-10-23 | Yahoo daily OHLC + `adjclose` |
| `data/round3/yahoo/SPY-1d-yahoo.parquet` | 2,970 | 2015-01-02 → 2026-10-23 | **new**, benchmark only; see §5 |
| `data/cache/dukascopy/SPY/*.bi5` | 60 daily files | 2026-08-31 → 2026-11-20 | 1-minute candles, raw; see §5 |
| `research/simcore/target/release/simcore.dll` | 146,432 bytes | mtime 2026-11-26 17:18:34 | current, loads; see §6 |

Structural checks, all three 1-minute files:

- no duplicate timestamps, no non-zero seconds, no weekend sessions;
- all OHLC positive, `high >= max(open, close)`, `low <= min(open, close)`;
- no negative or zero-volume RTH bars;
- first bar is 09:30 on every QQQ and TQQQ session. BIL lacks 09:30 on four
  sessions (2016-07-29, 2016-08-02, 2017-08-21, 2018-04-19), which `bt.panel`
  forward-fills from the prior close.

Rows outside 09:30–16:00 are dropped by `bt.load_1m`: QQQ 58,139, TQQQ 57,618,
BIL 123,085. They are mostly after-hours; on normal days the 16:00 filter
removes them correctly.

## 2. Calendar, sessions and half-days

### 2.1 Session counts

| Year | Sessions | Year | Sessions |
|---|---:|---|---:|
| 2016 | 252 | 2022 | 251 |
| 2017 | 251 | 2023 | 250 |
| 2018 | 251 | 2024 | 252 |
| 2019 | 252 | 2025 | 250 |
| 2020 | 253 | 2026 to 10-23 | 204 |
| 2021 | 252 | | |

- **Development** 2016-01-04 → 2023-12-29: **2,012 sessions**.
- **Holdout** 2024-01-02 → 2026-10-23: **706 sessions**.
- 2,012 + 706 = 2,718. There is no session between 2023-12-29 and 2024-01-02
  (2024-01-01 was a holiday), so the windows do not overlap and cannot leak
  into each other by date.
- The 1-minute archive has every session the daily archive has from 2016 onward
  (the 252 daily-only dates are exactly 2015). No whole sessions are missing.

### 2.2 Half-days: 21 dates, two different behaviours

Half-days end at **13:00**, which means the last bar is the 13:00 bar and a
complete half-day has **211 bars** (09:30–13:00 inclusive), not 210. The data
behaves differently before and after 2021:

- **10 correct half-days** (2021-11-26 onward): 211 bars, last bar 13:00.
- **11 contaminated half-days** (2016–2020): the QQQ 09:30–13:00 session is
  complete (TQQQ and BIL remain sparse as usual), but the file continues with
  after-hours bars from 13:01 to 15:5x. `bt.load_1m`'s `< 16:00` filter keeps
  them.

| Half-day | QQQ bars | after-hours bars | QQQ 13:00→last | TQQQ 13:00→last |
|---|---:|---:|---:|---:|
| 2016-11-25 | 247 | 36 | −0.025% | +0.113% |
| 2017-07-03 | 305 | 94 | −0.037% | +0.025% |
| 2017-11-24 | 279 | 68 | −0.084% | −0.154% |
| 2018-07-03 | 288 | 77 | −0.139% | −0.298% |
| 2018-11-23 | 290 | 79 | −0.057% | +0.114% |
| 2018-12-24 | 344 | 133 | **−0.620%** | **−1.890%** |
| 2019-07-03 | 291 | 80 | −0.026% | −0.276% |
| 2019-11-29 | 292 | 81 | −0.019% | −0.154% |
| 2019-12-24 | 256 | 45 | −0.033% | −0.093% |
| 2020-11-27 | 317 | 106 | +0.090% | +0.051% |
| 2020-12-24 | 291 | 80 | −0.036% | −0.183% |
| 2021-11-26 → 2025-12-24 (10 dates) | 211 | 0 | 0 | 0 |

The 10 correct dates are 2021-11-26, 2022-11-25, 2023-07-03, 2023-11-24,
2024-07-03, 2024-11-29, 2024-12-24, 2025-07-03, 2025-11-28, 2025-12-24.

**Required handling.** On a known half-day, keep bars with
`time <= 13:00` and drop everything after. This makes all 21 half-days 211 bars
and fixes both the session close and the daily close. It also fixes the daily
panel: `bt.panel(..., "1D")` currently marks the close of those 11 days at the
last after-hours print.

Minimal filter, applied after `bt.load_1m` and before resampling/reindexing:

```python
from datetime import date, time
HALF_DAYS = {
    date(2016, 11, 25), date(2017, 7, 3), date(2017, 11, 24),
    date(2018, 7, 3), date(2018, 11, 23), date(2018, 12, 24),
    date(2019, 7, 3), date(2019, 11, 29), date(2019, 12, 24),
    date(2020, 11, 27), date(2020, 12, 24), date(2021, 11, 26),
    date(2022, 11, 25), date(2023, 7, 3), date(2023, 11, 24),
    date(2024, 7, 3), date(2024, 11, 29), date(2024, 12, 24),
    date(2025, 7, 3), date(2025, 11, 28), date(2025, 12, 24),
}
after_close = df["date"].isin(HALF_DAYS) & (df["ts"].dt.time > time(13, 0))
df = df.loc[~after_close].copy()
```

`bt.panel` has no calendar hook, so a strategy that needs this must rebuild the
panel with `bt.load_1m` + `bt.resample` (the body of `bt.panel` is ~20 lines) or
mask the half-day afternoons out of its signals and marks. Indexing by
"last bar of the session" is not enough on the 11 contaminated days, because
the data's last bar is an after-hours bar.

### 2.3 Genuine missing QQQ minutes

QQQ has **7 sessions / 117 missing minutes**, all other minutes present:

| Date | Missing | Note |
|---|---|---|
| 2016-02-02 | 11:18–11:26 (9) | midday |
| 2016-02-22 | 10:26–11:11, 11:14–11:17 (50) | source outage |
| 2020-03-09 | 09:35–09:48 (14) | **opening 15 minutes, COVID crash** |
| 2020-03-12 | 09:36–09:49 (14) | **opening 15 minutes, COVID crash** |
| 2020-03-16 | 09:31–09:44 (14) | **opening 15 minutes, COVID crash** |
| 2020-03-18 | 12:57–13:10 (14) | midday |
| 2026-08-31 | 09:47–09:48 (2) | holdout |

The 2020 openings matter for any opening-range or first-hour rule: skip those
three sessions, or use a range that starts after the gap. Do not forward-fill
the missing opening minutes and pretend they were tradable.

### 2.4 TQQQ and BIL sparsity

- **TQQQ:** 5,183 missing minutes across 458 sessions (0.49% of RTH bars), but
  concentrated in 2016–17: 2,619 minutes in 2016, 2,443 in 2017, 63 in 2018,
  56 in 2020, 2 in 2026, none in 2019 or 2021–25. On the dev panel, **0.675%**
  of TQQQ bars are forward-filled from the previous QQQ minute. Fills on those
  bars use a stale TQQQ price; the effect is small but not zero.
- **BIL:** 230,805 missing minutes across 1,943 sessions. It is intrinsically
  sparse (29.6% of dev panel bars forward-filled; ~59% missing in 2016–17,
  ~0.3% in 2023 and later). BIL moves only a few basis points a day, so
  forward-filling is acceptable for marks and fills, but never use BIL's own
  last bar to define a session boundary.
- QQQ is the only dense series. Use **QQQ's calendar** for session starts,
  ends and half-days; TQQQ/BIL should be reindexed onto it (as `bt.panel`
  already does).

### 2.5 The brief's "18 sessions with missing minutes"

For QQQ, 2,718 sessions = 2,690 full 390-bar sessions + 10 correct half-days
(211 bars) + 18 other sessions. Those 18 are the **11 contaminated half-days**
(which have extra after-hours bars, not missing minutes) plus the **7 genuine
gaps** above. So "18" is the right count of non-standard sessions, but only 7
actually have missing minutes. Treat the 11 as a half-day-truncation problem.

## 3. Split and dividend adjustment

`bt.load_1m` multiplies the 1-minute OHLC by the daily Yahoo
`adjclose / close` factor. The 1-minute source is already split-adjusted for
QQQ and TQQQ; BIL is raw and has a 1:2 reverse split on 2017-11-30, which
`bt.load_1m` repairs by doubling BIL prices before that date.

Verified:

| Check | Result |
|---|---|
| BIL 2017-11-30 continuity | prev close 73.0279, next open 73.0438 (+0.022%) — split repair correct |
| TQQQ 2018-01-25 (2:1) | prev close 6.9059, next open 7.0426 (+1.979%) — no split jump |
| TQQQ 2022-01-13 (2:1) | prev close 36.3057, next open 36.6790 (+1.028%) — no split jump |
| Factor drops | largest is −8.5e-5% (float noise); no unadjusted splits |

The factor **rises** on ex-dividend dates by the dividend yield; that is the
correct total-return adjustment, not a data error. Largest one-day rises:

| Symbol | Factor first → last | Largest one-day rise |
|---|---|---|
| QQQ | 0.91765 → 1.00000 | +0.305% on 2015-12-18 |
| TQQQ | 0.94904 → 1.00000 | +0.583% on 2023-03-22 |
| BIL | 0.79359 → 0.99664 | +0.462% on 2023-12-18 |

BIL's large factor rise is its monthly dividend (~0.46% in late 2023), not a
data problem.

### 3.1 1-minute vs daily consistency

Absolute differences in basis points, after truncating the contaminated
half-days. `p99 / max`:

| Symbol | Open | Close | High | Low |
|---|---:|---:|---:|---:|
| QQQ | 7.1 / 18.3 | 10.8 / 84.2 | 2.4 / 107.1 | 3.3 / 103.0 |
| TQQQ | 11.5 / 205.5 | 28.4 / 65.9 | 4.2 / 818.0 | 3.7 / 63.0 |
| BIL | 0.55 / 2.2 | 2.19 / 4.35 | 1.09 / 18.8 | 1.09 / 2.19 |

- The QQQ/TQQQ max **high** values are the 2026-05-26 bad prints. The max
  **low** differences (QQQ 2021-01-20, TQQQ 2022-08-03) are cases where the
  daily low is below any 1-minute low — a missing print, not a bad bar. The
  p99 values are the honest measure of agreement.
- **Close is the 15:59 bar, not the official 16:00 closing auction.** The
  normal difference is under ~10 bps, but it reaches 84 bps on QQQ 2020-03-13
  and 66 bps on TQQQ 2020-03-27. A daily signal defined on the official close
  will differ slightly from one defined on the 1-minute panel's close.
- **TQQQ 2018-03-13:** Yahoo's daily open is 2.05% below the first 1-minute
  open, and its daily high is 1.26% below the 1-minute high. The 1-minute bars
  are internally consistent (tight 09:30 bar, 1.77M volume) and QQQ matches its
  daily open on the same day. Treat the 1-minute data as truth for intraday
  fills; do not use Yahoo's TQQQ daily OHLC for that date. This is the only
  open discrepancy above 50 bps (next worst is 32 bps).

## 4. Bad prints and outliers

### 4.1 2026-05-26 (holdout) — must handle

TQQQ's high field is corrupted in the first half-hour. The same impossible
high, **88.624176**, repeats across five bars; the normal price is ~80:

| Time | Open | High | Close | Upper wick |
|---|---:|---:|---:|---:|
| 09:35 | 79.82 | 88.62 | 79.71 | 11.0% |
| 09:45 | 80.49 | 88.62 | 80.70 | 9.8% |
| 09:50 | 80.81 | 88.62 | 80.50 | 9.7% |
| 09:52 | 80.55 | 88.62 | 80.63 | 9.9% |
| 09:54 | 80.44 | 88.62 | 80.68 | 9.8% |
| 09:55 | 80.68 | 87.63 | 80.83 | 8.4% |

The 5-minute bars 09:35, 09:45, 09:50 and 09:55 carry highs of 88.62/87.63,
versus a daily high of 82.27. A 5-minute Donchian or opening-range rule would
see a false +8–10% breakout. QQQ has smaller but real corruption on the same
date: high **737.4203** repeated at 10:25–10:26 (1.07% above the daily high),
low **718.4609** repeated across 09:57–10:15 (0.57% below the daily low), and
an open low of **719.4588** at 09:30–09:33 (0.44% below the daily low).

Only the high/low fields look wrong; closes are normal, so close-to-close
marks are unaffected. Clean the high/low fields on this date, or skip signal
generation for the day, before the holdout run.

### 4.2 TQQQ 2022-06-21 (development) — suspect

Low **11.3323** repeats at 13:14, 13:16, 13:17 and 13:26, 3.4–3.9% below the
bar body. It may be a stale bad low. Stop and ATR rules should treat it with
suspicion; at minimum do not let a single 1-minute low at 13:14 trigger a stop
without a confirming close.

### 4.3 Other wicks

QQQ's remaining >2% wicks (six up, three down) are isolated and on genuinely
volatile days (2020-03-16/18, 2022-05-09, 2022-06-28/30, 2023-05-05,
2024-08-07, 2025-04-04); they look real. TQQQ's >3% lower wicks outside
2022-06-21 are on
2020-03-16, 2024-08-05, 2025-04-09 and 2025-04-30, all real high-volatility
sessions. The only other repeated extreme is a QQQ low of 162.0592 at
15:51–15:52 on 2020-03-18 (2.2% wick); on a COVID crash day that may be real,
but it is worth a look if a stop rule fires there.

## 5. SPY

### 5.1 Local 1-minute cache (`data/cache/dukascopy/SPY/`)

- 60 `.bi5` files, one per UTC day, **2026-08-31 → 2026-11-20**.
- Each file decodes to 1,440 one-minute candles (00:00–23:59 UTC). Format:
  LZMA-alone, 24-byte big-endian records `(time_sec, open, close, low, high,
  volume)`, prices `int32 / 1000`. Only the 390 RTH minutes have volume; the
  rest are flat fillers.
- 60 RTH dates (59 real sessions plus Labor Day), **390 bars every date**.
  2026-09-07 (Labor Day) is a zero-volume flat filler and must be excluded.
- The overlap with the holdout is **2026-08-31 → 2026-10-23: 39 real sessions**.
  It runs four weeks past the holdout end; truncate at
  2026-10-23.
- Against the Yahoo daily SPY series on the overlap: raw open/high/low agree
  within ~2 bps median (high p99 10 bps), confirming the price scale and
  timestamps. The 1-minute data is **raw, not dividend-adjusted**; close
  differences of up to 28 bps before 2026-09-18 are the upcoming dividend, and
  disappear after the ex-date. Apply `adjclose/close` if total return is needed.
- Dukascopy volume units are undocumented and not comparable to the HF
  archive's share volume. Do not use SPY volume for signals.

**There is no SPY 1-minute data in development or from 2024-01-02 to
2026-08-28.** The 39-session tail is a sanity-check sample, not a benchmark
period.

### 5.2 New daily benchmark (`data/round3/yahoo/`)

Because the brief requires a SPY buy-and-hold benchmark and no local daily SPY
existed, I fetched it from the same Yahoo chart endpoint that produced the
local daily archive:

- `data/round3/yahoo/SPY-1d-yahoo.parquet`: 2,970 rows, **2015-01-02 →
  2026-10-23**, same columns as `data/intraday-hf/*-1d-yahoo.parquet`
  (`date, open, high, low, close, adjclose, volume`).
- `data/round3/yahoo/SOURCE.md` records the source, fetch date and adjustment.
- Reproducibility check: the same endpoint and parser reproduce the local
  `QQQ-1d-yahoo.parquet` **exactly** for all 2,970 rows (OHLCV identical;
  adjclose within 2.4e-4). SPY was fetched the same way.
- Integrity: no duplicate dates, no nulls, no non-positive prices; the date set
  equals QQQ's exactly. Maximum daily move 10.94% (2020-03-16); maximum factor
  change 0.595% (a dividend).

### 5.3 Verdict on SPY

| Use | Safe? |
|---|---|
| SPY buy-and-hold benchmark, daily closes, dev + holdout | **Yes** — use `data/round3/yahoo/SPY-1d-yahoo.parquet` |
| SPY benchmark on 1-minute marks, full period | **No** — only 39 holdout-tail sessions exist |
| SPY as a traded asset in development | **No** — no intraday data; daily closes only, so it cannot be minute-marked or traded intraday |
| SPY as a traded asset in the holdout | **No** — only the last 39 sessions, an asymmetric sample |
| SPY intraday feature study in the holdout tail | Possible, but label it as an 8-week tail and adjust for dividends |

Report the SPY benchmark as daily-marked. Do not describe it as minute-marked,
and do not use QQQ 1-minute prices as a SPY proxy.

## 6. Engine, warm-up and harness gotchas

### 6.1 simcore

- `research/simcore/target/release/simcore.dll` exists (146,432 bytes), is
  newer than `src/lib.rs`, and loads. `bt._SIMCORE` is not `None`, so
  `bt.simulate`/`bt.run` use Rust, not the Python fallback.
- Equality test on 48,691 bars with random 3-asset weights: max absolute
  equity difference **2.5e-10** (relative 3.0e-15); fills and turnover match
  exactly. The Rust core is a faithful implementation.
- Speed: 0.002 s for 48,691 bars; **0.022 s for 622,036 bars**. `run_many` is
  safe to use for sweeps.
- The engine is long-only: weights must be non-negative and sum to ≤ 1. There
  is no built-in shorting or borrow-cost model. A rebuilt strategy that wants
  shorts must model them outside the engine, which the current engine cannot
  represent; prefer long-only.

### 6.2 Warm-up: the dev start is cold

`bt.panel` always loads the 1-minute archive, even for `rule="1D"`. Since that
archive begins 2016-01-04:

| Request | Panel starts | Prior sessions | First 165d SMA |
|---|---|---:|---|
| `bt.panel(..., "2016-01-04", ..., "1D")` | 2016-01-04 | **0** | 2016-08-26 |
| `bt.panel(..., "2016-01-04", ..., "1min")` | 2016-01-04 09:30 | **0 bars** | n/a |
| `bt.panel(..., "2017-01-03", ..., "1D")` | 2016-01-04 | 252 | 2016-08-26 |
| `bt.panel(..., "2024-01-02", ..., "1D")` | 2022-08-22 | 342 | 2023-04-18 |
| Yahoo daily parquet | 2015-01-02 | 252 before dev | 2015-08-27 |

Consequences:

- A strategy that computes a 165-day SMA on `bt.panel("1D")` is flat until
  2016-08-26, losing the first 8 months of development. A 200/250-day
  indicator is worse.
- Intraday features that need prior sessions (20-day volume, prior-day range,
  etc.) have no history on 2016-01-04. Use a burn-in or daily proxies from the
  Yahoo parquet.
- For daily features at the dev start, read the Yahoo daily parquet and map
  signals to the 1-minute panel by date. That is what
  `research/agents/vol-kelly-overlay/strategy.py` does with `daily_panel()`.
  A daily bar there is the official Yahoo close, not the 15:59 panel close;
  document which one the rule uses.
- `bt.DEFAULT_START = "2021-10-25"` and `bt.run` defaults to it. Always pass
  `start="2016-01-04"` (or the intended window) explicitly, or a strategy will
  silently run the 5-year window.

### 6.3 Caching and ffill

- `bt.panel` caches panels in `data/cache/research_panels/` keyed by symbol,
  dates, rule, warm-up and source mtimes. The cache is safe to use; delete a
  panel if you change the source files.
- `bt.panel` reindexes every symbol to QQQ's calendar and applies
  `ffill().bfill()`. On the dev panel this forward-fills **0.000% of QQQ**,
  **0.675% of TQQQ** and **29.6% of BIL** bars. QQQ is the clean base; TQQQ
  fills are stale but rare; BIL fills are frequent but harmless because BIL is
  nearly flat.

## 7. Development / holdout separation and leakage

- Development 2016-01-04 → 2023-12-29: 2,012 sessions, first bar 2016-01-04
  09:30, last bar 2023-12-29 15:59.
- Holdout 2024-01-02 → 2026-10-23: 706 sessions, first bar 2024-01-02 09:30,
  last bar 2026-10-23 15:59.
- No overlap, no gap: 2024-01-01 is a holiday. Sorting by timestamp gives
  exactly 2023-12-29 then 2024-01-02.
- The 1-minute and daily archives stop at 2026-10-23. Nothing after that can
  leak into the holdout from the QQQ/TQQQ/BIL files.
- The Dukascopy SPY cache runs to 2026-11-20, i.e. **past** the holdout. If it
  is used at all, truncate at 2026-10-23.
- The 10-year (2017-01-03 →) and 5-year (2021-10-25 →) windows overlap the
  holdout by construction; label them as overlapping, as the brief requires.

## 8. Blocking issues and required actions

1. **Half-day cutoff.** Apply the 13:00 truncation on the 21 dates in §2.2.
   Without it, 11 sessions have after-hours closes and marks, and the daily
   panel's close is wrong on those days (up to −1.89% TQQQ). This is a
   correctness bug, not a rounding issue.
2. **2026-05-26 bad prints.** Before the one-shot holdout run, cap/clean the
   QQQ and TQQQ high/low fields on this date (or skip signal generation for
   the day). TQQQ's repeated 88.624176 high affects four 5-minute bars and is
   8–11% above the real price; a Donchian/ORB/ATR rule will otherwise see a
   false breakout.
3. **Dev-start warm-up.** Daily rules that use `bt.panel("1D")` have zero
   warm-up at 2016-01-04. Read the Yahoo daily parquet for daily features from
   2015, or explicitly start those rules later. State which close is used.
4. **SPY.** Use it only as the daily buy-and-hold benchmark from
   `data/round3/yahoo/SPY-1d-yahoo.parquet`. There is no SPY **intraday** data
   for development or for 2024-01-02 → 2026-08-28; the 1-minute cache is an
   8-week holdout tail.
5. **QQQ COVID opening gaps.** Skip opening-range/first-hour signals on
   2020-03-09, 2020-03-12 and 2020-03-16; the first 14–15 minutes are missing.
   Also skip 2026-08-31 if a rule needs 09:47–09:48.
6. **TQQQ 2022-06-21 low cluster.** Treat the repeated 11.3323 low as suspect;
   require a confirming close before a stop, or exclude the cluster.
7. **TQQQ/BIL forward-fill.** 0.675% of dev TQQQ bars and 29.6% of BIL bars
   are stale forward-fills. Do not build a rule that depends on trading every
   minute in TQQQ or on BIL's intraday range.

Items 1–4 are blocking for trustworthy results. Items 5–7 are material
limitations that must be documented in each report and handled in code where
the rule is exposed.

## 9. What is safe, and what was not checked

**Safe to use now**

- QQQ 1-minute bars as the primary intraday series and session calendar.
- TQQQ 1-minute bars for intraday trading, accepting the 0.49% missing-minute
  rate and cleaning the 2026-05-26 / 2022-06-21 high-low clusters.
- The adjusted QQQ/TQQQ/BIL daily series from 2015-01-02, including the BIL
  reverse-split repair and dividend adjustment.
- `bt.run` / `bt.run_many` on the Rust core, with explicit start dates.
- The dev/holdout split: no overlap, no post-holdout data in the core archive.

**Not checked / not available**

- No stock universe, point-in-time constituents, delistings or fundamentals.
  Any rebuilt strategy that wants individual stocks or sector ETFs must fetch
  and validate its own data under `data/round3/<source>/` with a `SOURCE.md`.
- No borrow-cost or shorting data; the engine is long-only, so a short leg
  would need an external model that `bt` cannot represent.
- No corporate actions beyond splits and dividends (mergers, ticker changes,
  halts). This matters only for new single-stock data, not the three ETFs.
- No intraday SPY history for development, and no full-holdout SPY 1-minute
  history. SPY is benchmark-only.
- No verification of the Dukascopy SPY volume scale. Price data only.
