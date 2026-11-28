# Full-curve integrity audit (2016-2026 website curves)

**Scope:** the 27 curves in `research/revisit/curves_full/` used by
`web/public/data/compare/all.json`, against the frozen development result in
`research/revisit/<slug>/result.json` and the 2026-11-26 audit
(`research/revisit/audit/report.md`).

**Status:** read-only. No strategy, result, curve, cache or website file was
modified. No backtest was run; the only computations were replays of already
saved weight matrices through the existing `research/bt.py` compiled engine.

> **Decision (2026-11-27, main session):** the 8 pre-tune curves are the
> published freeze. They were not regenerated to the post-tune variants; the
> post-tune results are documented in `WHY_UNDERPERFORM.md` §3. §6 is retained
> as the plan for a future decision to adopt those variants.

**Headline:** 18 curves are valid, 8 are stale (generated from the pre-tune
`strategy.py`), and 1 (`ml-classifier`) has a valid development window but a
wrong 2024-2026 extension. `vol-scaled-crash-stop` is *not* stale: its curve is
correct and `result.json`'s "dev" block is actually the full 2016-2026 run.

---

## 1. Method

For every curve I:

1. loaded `dates`/`values` and computed daily-close CAGR, max drawdown and
   Sharpe on 2016-01-04 -> 2023-12-29 (2017-01-03 for `ml-classifier`, whose
   `TRADE_START` is 2017-01-03). CAGR uses calendar years (365.25), the same
   convention as `export_compare_full.stats`; `bt.stats` uses the exact
   first-to-last timestamp, a ~6-hour difference that is <0.01% on 8 years.
2. compared that with `result.json -> windows.dev.1bp` (the `5bp` block was
   never needed) and with the 10y (2017-01-03 -> 2026-10-23) and 5y
   (2021-10-25 -> 2026-10-23) numbers in `audit/report.md`.
3. replayed the 2026-11-26 audit capture
   (`audit/cache/<slug>-full.npz`, 1-minute weights) through
   `bt.simulate(..., band=0.02, slippage_bps=1.0)` and compared its daily
   closes with the curve. This is the decisive test: if the replay is
   bit-identical to the curve, the curve *is* that code version, regardless of
   mtimes.
4. diffed the current `strategy.py` against `<slug>/_before_tune/strategy.py`
   and compared `_before_tune/result.json` with the current `result.json` and
   with the audit's stored dev number.

All replay comparisons used the existing compiled `simcore` DLL; the Rust
simulator was not rebuilt.

### The one fact that explains the audit

`_before_tune/result.json` equals the 2026-11-26 audit's `dev_repro.stored`
CAGR for all 21 strategies that have a `_before_tune` directory (to 1e-9), and
the current `result.json` differs for 9 strategies (8 tuned, plus
`vol-scaled-crash-stop`, whose result picked up the full window). The pre-tune
results were the frozen ones. The current files were written later.

| slug | pre-tune dev CAGR | current dev CAGR |
|---|---:|---:|
| daily-regime-minute-entry | -0.0450% | +0.9145% |
| donchian-breakout | -3.3825% | +13.4042% |
| drawdown-regime | -1.6406% | +17.1984% |
| drawdown-stop-overlay | -1.7440% | -9.2482% |
| dual-speed-regime | +5.3803% | +28.7622% |
| dynamic-leverage-throttle | +2.6471% | +5.2446% |
| ensemble-signals | -5.2123% | -6.3358% |
| gap-capitulation-reversal | +4.1806% | +8.3023% |
| vol-scaled-crash-stop | +57.8428% | +51.4629% (this is the *full* window, see §3.4) |

---

## 2. The 27-row table

Mtimes are `MM-DD HH:MM` local. `curve / strategy / result` are the three file
mtimes. "before" = `_before_tune/` exists. Dev CAGR is daily-close; result CAGR
is the 1-minute `result.json` dev 1 bp value. 10y and 5y are `curve / audit`
CAGRs. DD is `curve / result` (daily-close DD is systematically smaller than
1-minute DD; that is expected and is not evidence of staleness).

| # | slug | curve / strategy / result | before | dev start | dev curve | dev result | gap (pp) | DD curve/result | 10y curve/audit | 5y curve/audit | verdict |
|---:|---|---|:--:|---|---:|---:|---:|---|---:|---:|---|
| 1 | daily-regime-minute-entry | 11-27 00:14 / 00:40 / 00:44 | yes | 01-04 | -0.05% | 0.91% | **-0.96** | 62.8/61.7 | 3.54/3.55 | 15.85/15.85 | **STALE** |
| 2 | donchian-breakout | 11-27 00:23 / 00:31 / 00:45 | yes | 01-04 | -3.42% | 13.40% | **-16.82** | 35.8/15.0 | -0.14/-0.14 | 0.19/0.16 | **STALE** |
| 3 | drawdown-regime | 11-27 00:14 / 00:31 / 00:45 | yes | 01-04 | -1.64% | 17.20% | **-18.84** | 47.5/49.0 | -0.14/-0.13 | -1.20/-1.20 | **STALE** |
| 4 | drawdown-stop-overlay | 11-27 00:14 / 00:20 / 00:44 | yes | 01-04 | -1.75% | -9.25% | **+7.50** | 39.6/63.1 | -3.03/-3.02 | 0.91/0.91 | **STALE** (too kind) |
| 5 | dual-speed-regime | 11-27 00:21 / 00:38 / 00:45 | yes | 01-04 | 5.89% | 28.76% | **-22.88** | 36.9/45.5 | 4.86/4.27 | 8.94/7.82 | **STALE** (exact pre-tune variant) |
| 6 | dynamic-leverage-throttle | 11-27 00:16 / 00:31 / 00:45 | yes | 01-04 | 2.65% | 5.24% | **-2.60** | 8.3/9.2 | 2.61/2.61 | 2.97/2.97 | **STALE** (2016 only) |
| 7 | ensemble-signals | 11-27 00:21 / 00:31 / 00:45 | yes | 01-04 | -5.21% | -6.34% | **+1.12** | 75.9/76.0 | -0.30/-0.27 | -8.83/-8.72 | **STALE** (2016 only) |
| 8 | event-risk-overlay | 11-27 00:28 / 00:31 / 00:45 | yes | 01-04 | 26.94% | 26.94% | +0.00 | 37.0/39.0 | 19.71/19.71 | 8.55/8.55 | VALID |
| 9 | gap-capitulation-reversal | 11-27 00:16 / 00:31 / 00:45 | yes | 01-04 | 4.18% | 8.30% | **-4.12** | 10.6/10.3 | 5.40/5.41 | 6.00/6.00 | **STALE** |
| 10 | gap-fill-fade | 11-27 00:29 / 00:31 / 00:45 | yes | 01-04 | 1.43% | 1.43% | -0.00 | 0.4/0.5 | 2.42/2.41 | 3.75/3.75 | VALID |
| 11 | intraday-mean-reversion | 11-27 00:30 / 00:38 / 00:45 | yes | 01-04 | 11.31% | 11.31% | +0.00 | 21.5/31.5 | 14.19/14.19 | 6.19/6.19 | VALID |
| 12 | intraday-momentum | 11-27 00:53 / 00:33 / 00:45 | yes | 01-04 | 13.51% | 13.51% | -0.00 | 63.6/64.0 | 13.91/13.94 | 1.85/1.97 | VALID |
| 13 | intraday-seasonality | 11-27 00:31 / 00:31 / 00:45 | yes | 01-04 | 21.85% | 21.84% | +0.00 | 39.2/43.8 | 28.56/28.50 | 26.07/26.07 | VALID |
| 14 | letf-rebalance-flow | 11-27 00:31 / 00:24 / 00:45 | yes | 01-04 | 13.20% | 13.20% | -0.00 | 40.8/41.8 | 13.19/13.27 | 6.26/6.65 | VALID |
| 15 | ml-classifier | 11-27 00:54 / 11-26 17:43 / 00:45 | yes | **01-03** | 20.69% | 20.69% | +0.00 | 35.3/36.0 | 21.05/17.93 | 19.39/13.56 | **WRONG EXTENSION** |
| 16 | ml-crash-overlay-winner | 11-27 00:54 / 00:31 / 00:45 | yes | 01-04 | 15.80% | 15.80% | -0.00 | 21.2/22.4 | 15.62/17.87 | 16.37/20.94 | VALID (audit 10y is the artifact) |
| 17 | opening-range-breakout | 11-27 00:31 / 00:26 / 00:45 | yes | 01-04 | -2.04% | -2.10% | +0.06 | 17.2/17.2 | -1.19/-1.16 | -1.00/-1.00 | VALID |
| 18 | overnight-crash-filter | 11-27 00:31 / 00:31 / 00:45 | yes | 01-04 | 10.37% | 10.37% | +0.00 | 27.0/27.6 | 13.68/13.69 | 8.63/8.66 | VALID |
| 19 | ratio-froth | 11-27 00:54 / -- / -- | no | 01-04 | 61.56% | n/a | n/a | 36.7/n/a | 69.38/69.50 | 63.15/63.74 | VALID (ref = agents2) |
| 20 | ratio-pairs | 11-27 00:31 / 00:38 / 00:45 | yes | 01-04 | 18.96% | 18.96% | +0.00 | 33.9/34.6 | 21.67/21.69 | 16.97/17.11 | VALID |
| 21 | risk-parity-hrp | 11-27 00:53 / 00:32 / 00:45 | yes | 01-04 | 5.70% | 5.70% | -0.00 | 17.9/18.5 | 6.32/6.34 | 4.70/4.79 | VALID |
| 22 | stop-reentry-recovery | 11-27 00:31 / 00:38 / 00:45 | yes | 01-04 | 1.25% | 1.25% | -0.00 | 1.2/1.8 | 2.25/2.25 | 3.72/3.72 | VALID |
| 23 | time-of-day | 11-27 00:32 / 00:38 / 00:45 | no | 01-04 | 19.70% | 19.68% | +0.02 | 31.8/31.8 | 17.32/17.37 | 9.37/9.42 | VALID (ends 10-22) |
| 24 | vol-kelly-overlay | 11-27 00:33 / 11-26 17:41 / 00:45 | no | 01-04 | 1.81% | 1.81% | -0.00 | 16.5/19.2 | 1.13/1.13 | 1.76/1.76 | VALID |
| 25 | vol-scaled-crash-stop | 11-27 00:53 / 00:31 / 00:45 | no | 01-04 | 57.65% | 51.46% | **+6.18** | 37.9/39.3 | 56.67/56.78 | 37.77/38.26 | **VALID curve / result dev = full window** |
| 26 | volume-orderflow | 11-27 00:33 / 00:31 / 00:45 | no | 01-04 | 0.87% | 0.87% | -0.00 | 13.1/16.7 | 2.74/2.74 | 5.32/5.32 | VALID |
| 27 | winner-ensemble-blend | 11-27 00:35 / 00:48 / 00:49 | no | 01-04 | 0.30% | 0.30% | -0.00 | 30.5/32.7 | 2.67/2.67 | 2.87/2.87 | VALID |

Notes on the table:

- `ml-classifier`'s result is on 2017-01-03 -> 2023-12-29 (`TRADE_START`), not
  2016-01-04. On that window the curve matches exactly; the 10y/5y columns are
  the real defect. On the literal 2016-01-04 start the curve gives 17.90%,
  which is the same equity path plus one BIL year before the model starts; it
  is not a second defect. `ratio-froth` has no revisit `result.json`; its
  10y/5y reference is `research/agents2/ratio-pairs/result.json` (69.50% /
  63.74%, 1-minute marks), so its dev column is the curve's own 2016-2023 CAGR
  and its result column is not applicable.
- The DD columns are not a quality signal: daily-close marks hide intraday
  troughs. E.g. `intraday-mean-reversion` 21.5% vs 31.5%, `drawdown-stop-overlay`
  39.6% vs 63.1%. The same reason inflates daily Sharpe for near-cash curves
  (`gap-fill-fade` 4.24 vs 0.94, `stop-reentry-recovery` 2.84 vs 0.80).
- `time-of-day` ends 2026-10-22, one session before the uniform end.

---

## 3. Root causes

### 3.1 Generation order: curves are a snapshot of the pre-tune code

The pipeline ran in this order on 2026-11-27:

| time | event |
|---|---|
| 00:14-00:35 | `capture_full.py` / `full_direct.py` wrote 21 `curves_full/*.json` |
| 00:20-00:48 | the 2026-11-27 tune edited `strategy.py` across the tree (24 files now carry 11-27 mtimes; 21 dirs have a `_before_tune/` snapshot) |
| 00:44-00:49 | every `result.json` was rewritten from the post-tune code |
| 00:53-00:54 | `full_missing.py` wrote the remaining 6 curves |
| 01:07 | `cleanup_useless.py` deleted all logs, caches and `result_dev_backup.json` |

`capture_full.py` matches a captured run to the `result.json` that exists
**when it runs** (lines 32 and 90-93). That was the pre-tune file. Nothing in
the curve records which source hash or result hash it was validated against,
so when `result.json` was replaced 20 minutes later, the curve silently became
stale. This is a versioning bug, not a backtest bug.

Proof: replaying the 2026-11-26 audit's *pre-tune* full capture through
`bt.simulate` reproduces 21 of the 27 curves bit-for-bit (max relative
difference 0.000e+00 on every common day), including 7 of the 8 stale ones
(`dual-speed-regime` differs from that capture because the capture is a
slightly different pre-tune variant, but the curve is exactly the
`overnight=False, idle="bil"` build, 5.89% dev). For the 8 stale curves the
dev CAGR equals the `_before_tune` dev CAGR (within 0.05 pp, except dual-speed
0.51 pp from daily marks) and differs from the current `result.json`.

`dual-speed-regime` is the cleanest case: the curve is exactly the pre-tune
`overnight=False, idle="bil"` variant (5.89% dev), while the current code is
`overnight=True, idle="cash"` (28.76% dev). The variant is identified by
`audit/dual_speed_audit.json`, which was produced independently.

### 3.2 `result.json` is not a frozen artifact

All 27 `result.json` files have mtime 00:44-00:49, after the tune. The
`_before_tune/result.json` snapshots and the 2026-11-26 `audit.json` agree with
each other to 1e-9 and disagree with the current files for the same 9
strategies. For the 8 tuned strategies the frozen dev result is the pre-tune
number and the current number is a post-tune rerun; `vol-scaled`'s difference
is the window bug in §3.4. Any downstream comparison must say which one is the
freeze. The website currently mixes both.

### 3.3 `capture_full.py` rewrites only one date literal

It replaces the exact strings `"2023-12-29"` / `'2023-12-29'` (lines 36-37).
`worker.py` needs three literals (lines 41-45):

```
"2023-12-29" -> "2026-10-23"
"2023-12-30" -> "2026-10-24"     (exclusive end / subperiod label)
"2023-12-01" -> "2026-10-01"     (ml-classifier monthly refit schedule)
```

Consequences:

- **`ml-classifier`**: `build_weights` hard-codes
  `pd.date_range("2017-01-01", "2023-12-01", freq="MS")`; the sentinel `n`
  extends the last block to the panel end. `full_missing.py` calls
  `build_weights` without the `"2023-12-01"` replacement, so 2024-2026 is run
  with the model fitted through 2023-11-30 only. The dev path (2016-2023) is
  identical to `result.json`; the 2024-2026 path is not the monthly-refit rule
  the strategy specifies. Evidence: 10y curve 21.05% vs the audit's 17.93%,
  5y 19.39% vs 13.56%.
- **`overnight-crash-filter`** happens to be safe because its `"2023-12-30"`
  only appears in a subperiod label; its data end uses `DEV_END`.
- `capture_full.py` also does not disable strategy caches. `worker.py` does
  (`if CACHE.exists(): -> if False:`, `if cache.exists(): -> if False:`), and
  that difference is what corrupts `vol-scaled` (next section).

### 3.4 `vol-scaled-crash-stop`: the result window is wrong, not the curve

`load_dev_panel()` reads `dev_panel.npz` whenever the file exists, **ignoring
its `start`/`end` arguments** (strategy.py lines 61-65). A full-period cache
must have been present when `main()` wrote `result.json` at 00:45, because the
"dev" headline is the 2016-2026 simulation:

- `result.json` dev: CAGR 51.4629%, DD 39.2871%, 3,950 fills.
- Full 2016-2026 replay of the frozen weights: CAGR **51.4629%**, DD
  **39.2871%**, **3,950** fills, 10.801 years.
- True dev 2016-2023 replay: CAGR 57.84%, DD 39.29%, 2,897 fills.
- The curve's dev slice is 57.65% daily-close / 37.9% DD, i.e. the true dev
  window. Its 10y/5y (56.67/37.77) match `audit/report.md` (56.78/38.26).

So the curve is **valid**; `result.json`'s `windows.dev` is the full-period
number. `full_missing.py` avoided the bug by deleting the cache first
(line 55); `main()` and `capture_full.py` do not. The cache is still on disk
and still full-period, so any future dev run of this strategy will repeat the
error unless the cache is deleted.

### 3.5 `full_missing.py` bypasses `main()`

It imports the module and calls `build_weights` directly for six strategies.
That is how `ml-classifier` lost the refit extension and how
`vol-scaled-crash-stop` was generated from a panel that `main()` would have
loaded differently. It also means no `--dev`/`--run` guard and no result.json
cross-check by the strategy itself. The builder arguments are otherwise
correct (`opens` is passed where `opens` is expected; `atr` is built from the
same highs/lows), but they are a re-implementation of each `main()` and must
be kept in sync manually.

`full_missing.py` also passes `warmup_days=0` to the 1-minute panel
(lines 45, 65) while `main()` normally uses the default 500. For these
strategies the 1-minute archive starts at the dev start, so `warmup_days=500`
loads no extra bars anyway; the call is equivalent today but is a latent
difference if the archive is ever extended backwards.

### 3.6 `full_direct.py` calls the current defaults

`dual-speed-regime` and `ensemble-signals` are built with
`build_weights(ts, o, c)` and no flags. For dual-speed, the current defaults
are `overnight=True, idle="cash"`; the pre-tune defaults (used at 00:21) were
`overnight=False, idle="bil"`. Re-running `full_direct.py` today would produce
a different curve than the one on disk, which is exactly what "stale" means
here. Nothing in the file pins the parameter set.

### 3.7 The 2026-11-26 audit does not certify the current code

`audit/report.md` says "Generated 2026-11-26"; its cache is from 20:39-20:46.
The tune is 2026-11-27 00:20-00:48. So its `look-ahead clean` verdicts and its
10y/5y numbers describe the pre-tune code only. The tuned code has not been
re-audited, and `audit_all.py` would need `--only <the tuned slugs>` after a
new freeze. The pre-tune audit found `lookahead_identical_share = 1.0` for all
26, which is good evidence that the *old* builders were causal; it says
nothing about `short_nav`, the Yahoo prehistory splices, or the new fill
timing.

### 3.8 Holdout contamination

`intraday-mean-reversion/DIAGNOSIS.md` calls the tune "post-holdout work" and
says the lead had already run the holdout once. No equivalent change log
exists for the other 20 tuned strategies. The curves on disk were generated
before most of the tune, so their 2024-2026 segment may have been visible to
the tuner. Any regenerated curve is therefore **post-tune and not a clean
holdout**, regardless of how the code is run.

### 3.9 Smaller, non-material issues

- **First-day normalization.** Curves are normalized at the 2016-01-04
  *close*; `result.json` starts at 100k at the 09:30 bar. This biases the dev
  CAGR by roughly the first-day return / 8 years. It explains the +0.06 pp on
  `opening-range-breakout`, the +0.02 pp on `time-of-day`, and part of
  dual-speed's 0.51 pp. It cannot explain a 4-23 pp gap.
- **`metrics` blocks use the wrong bar count.** `capture_full.stats_at` and
  `full_direct.stats_at` pass `252*390` for every strategy, including daily
  and 5-minute ones. The Sharpe/vol in those blocks are wrong for coarse
  strategies. `export_compare_full.py` ignores them and recomputes from the
  daily values, so the website is unaffected.
- **`time-of-day` ends one session early** (2026-10-22). `export_compare_full`
  forward-fills it to 2026-10-23, so the last point is flat; its CAGR is over
  the slightly shorter own window. Minor.
- **Benchmarks are aligned correctly.** `export_compare_full` loads the same
  1-minute panel, takes daily closes, and normalizes QQQ/TQQQ at the same
  first close as the strategies. No benchmark misalignment was found.
- **`export_compare_full` has no coverage assertion.** It never checks that
  each curve reaches `END`; a truncated curve would be forward-filled silently.
  All 27 currently reach 2026-10-23 (time-of-day 10-22), so no live error.

---

## 4. Per-strategy notes (every row that needs a note beyond `VALID`)

### Stale (8)

| slug | what changed | evidence |
|---|---|---|
| `dual-speed-regime` | tuned to hold overnight (`OVERNIGHT=True`) and leave idle equity in cash instead of BIL | curve == pre-tune `overnight=False, idle="bil"` exactly; current result is `overnight=True, idle="cash"` |
| `drawdown-regime` | arm/breakout state machine fixed (drawdown trough, daily-close breakout), fill moved from session-first bar to prior last bar | 137-line diff; curve == audit pre-tune capture bit-for-bit |
| `donchian-breakout` | signal bars 5-minute -> 1-hour (`RULE="1h"`) and ATR annualization changed | 37-line diff; curve == audit pre-tune capture |
| `drawdown-stop-overlay` | stop now measured on TQQQ (was QQQ); signal/exit state machine factored and fixed | 68-line diff; curve == audit pre-tune capture |
| `gap-capitulation-reversal` | `event_low_stop` turned off; entry target moved to the event day's last bar (one-minute-late fill fix) | 30-line diff; curve == audit pre-tune capture |
| `daily-regime-minute-entry` | synthetic short changed from rebalanced -1x to constant-share NAV | new `short_nav()`; pre-tune result -0.045% == curve |
| `dynamic-leverage-throttle` | added pre-2016 Yahoo daily history so 60-day vol and 252-day high are defined from 2016-01-04; disabled the re-acceleration exit | diff + `warmup_daily`; pre-tune 2.647% == curve |
| `ensemble-signals` | added pre-2016 Yahoo daily history for the 252-day volatility percentile | new `_warm_daily()`; pre-tune -5.212% == curve |

`daily-regime`, `dynamic-leverage` and `ensemble-signals` are the three
smallest dev gaps (0.96-2.60 pp). For the latter two the diff is a pre-2016
daily-history splice, so the change is structurally 2016-only; for
`daily-regime` the new constant-share short NAV can affect any short episode,
so the 2017+ path is unverified. In all three cases the post-tune 10y/5y were
not recomputed.

### Wrong extension (1)

`ml-classifier`: dev window is correct at its own 2017-01-03 start. From
2024-01 the curve reuses the model fitted at the 2023-12 refit because
`full_missing.py` does not replace `"2023-12-01"`. The stated rule is a refit
on the first trading day of every month. The audit's full capture does refit:
its post-2023 weights change by year (2024 mean 73% QQQ, 2025 47% QQQ/36% BIL,
2026 54% QQQ/46% BIL). Fix the generator, not the strategy.

### Valid but the audit's 10y is the artifact (1)

`ml-crash-overlay-winner`: dev matches exactly (15.80%). The strategy's
`main(--full)` sets `last_year=2026`; `full_missing.py` passes the same
`last_year=2026`, so the curve is the intended full-period rule. `worker.py`
does not pass `--full`, so the audit's full run has no probabilities after
2023 (they are NaN) and `state_weights` falls back to QQQ: the audit's
post-2023 weights are 98% QQQ in 2024 and 100% QQQ in 2025-2026. Its 10y
17.87% / 5y 20.94% are therefore not the strategy applied to 2024-2026. The
curve's 15.62% / 16.37% are the correct full-period numbers.

### Valid, with a reference rather than a revisit result (1)

`ratio-froth` has no `research/revisit/ratio-froth/result.json`; it is the
`agents2/ratio-pairs` original run on the full panel by `full_missing.py`.
Against that original's `result.json` 10y/5y (69.50% / 63.74%, 1-minute marks),
the curve gives 69.38% / 63.15% (daily close). The 0.12 pp 10y gap is
consistent with the daily-vs-1-minute mark difference.

---

## 5. Generator audit

### `capture_full.py` — safe by accident, not by design

- **Date rewrite:** literal-only (one string). Not safe in general. It works
  for the 19 strategies it was actually used for, whose only end literal is
  `"2023-12-29"`. It cannot express an exclusive end or a refit schedule, and
  it silently produces a curve that stops early or freezes a model.
- **`main()` re-run:** yes. For the 8 stale strategies, `main()` does **not**
  select parameters on the extended sample: `donchian --dev` runs one
  `run_dev()`, `drawdown-regime --run` builds one weight matrix,
  `drawdown-stop-overlay` runs named variants but the headline is fixed
  `primary`, `dual-speed` builds one matrix, `gap-capitulation` builds one and
  runs placebos, `daily-regime` builds one plus diagnostic variants,
  `dynamic-leverage --authorised` builds one (the `itertools.product` grid
  exists but `main()` does not call it), `ensemble --run` builds one.
  So no full-sample tuning was observed. That is a property of today's
  `main()`s, not a guarantee of the generator.
- **Selection guard:** the only guard is a dev-slice CAGR/DD match within
  5e-4 (lines 90-93). It will accept a full-period-selected variant if its dev
  slice happens to land within 5e-4, and it takes the first match in
  `captured`. For the three strategies that emit several candidate portfolio
  weight sets (`drawdown-stop-overlay`, `vol-scaled`, `daily-regime`), a
  near-duplicate variant could be saved. No such collision is visible in the
  current curves (they match `primary`), but the generator is fragile.
- **Backup/restore:** `result.json` is backed up to `result_dev_backup.json`
  and restored in `finally`. A hard kill leaves the full-period result in
  place; the cleanup script deletes the backup. No source hash, result hash or
  generation timestamp is stored in the curve.
- **Caches:** not disabled. This is the direct cause of the vol-scaled result
  bug.

### `full_missing.py` / `full_direct.py`

- They bypass `main()` and therefore bypass its guards and its exact argument
  wiring. They are the only path for the six strategies whose `main()` is hard
  to extend, so they are necessary, but each call must be checked against
  `main()` by hand.
- `full_missing` handles `vol-scaled` correctly (deletes the cache) and
  `ml-crash` correctly (`last_year=2026`), but `ml-classifier` incorrectly
  (no refit-schedule extension).
- `full_direct` calls the current `build_weights` defaults, so it is not
  reproducible across code versions, and it writes the curve **without any
  dev-slice assertion** against `result.json`. The two curves it produced
  (`dual-speed-regime`, `ensemble-signals`) match the pre-tune result only
  because they were written before the tune.

### `export_compare_full.py`

- Correct daily-close normalization and benchmark alignment. No look-ahead.
- It forward-fills to the union of dates without asserting each curve reaches
  `END`; a truncated curve would be silently flat.
- It recomputes metrics from the daily series and ignores the `metrics` blocks,
  so the `252*390` bug in those blocks does not reach the website.

### `bt.py` panel/stats

- `panel(warmup_days=500)` subtracts **calendar** days from `start`. For a
  2016-01-04 start the 1-minute archive has no earlier bars, so the warm-up is
  empty. This is why the 2026-11-27 tune had to splice Yahoo daily history for
  the 252-day indicators (`ensemble-signals`, `dynamic-leverage-throttle`).
  It is not a dev-vs-full difference: both runs used the same empty warm-up.
- `load_1m` applies `adjclose/close` from the daily file and `ffill().bfill()`
  on the factor; `panel` reindexes BIL to QQQ's grid with `ffill().bfill()`.
  These are consistent between dev and full runs.
- `simulate` fills `weights[i]` at `open[i+1]`; no look-ahead in the engine.
- `stats(..., bars_per_year)` must match the marking frequency; all generators
  pass `252*390`. Only affects the saved `metrics` blocks, not the website.

### Look-ahead / holdout leakage / normalization verdict

- **Look-ahead introduced by extending to 2026:** none demonstrated. The
  pre-tune audit's cut tests and its `lookahead_identical_share = 1.0` cover
  the code that produced the curves. The tuned code is not re-audited; the new
  `short_nav`, the Yahoo prehistory splices and the fill-timing fixes are
  causal by inspection (each uses only data through the decision bar), but
  that is a code reading, not a replay proof.
- **Holdout leakage:** the tuning is explicitly post-holdout at least for
  `intraday-mean-reversion`, and the curves predate the tune. Treat all
  2024-2026 segments of tuned strategies as contaminated.
- **Normalization:** consistent between strategies and benchmarks (first daily
  close = 100). The only bias is the first-day exclusion described in §3.9.
- **Daily-close bug:** none. `groupby(date).last()` takes the 15:59 (or 12:59
  half-day) close; the same convention is used for QQQ/TQQQ benchmarks.

---

## 6. Regeneration plan

### 6.1 Preconditions

1. **Freeze the current results first.** `capture_full.py` reads and restores
   `result.json`, but it does not protect against a strategy that writes other
   files. Copy each `result.json` to `result_frozen.json` (or record SHA-256)
   before starting; the 00:44-00:49 files are the only record of the post-tune
   numbers.
2. Run from the repo root with
   `$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"`.
3. Run one strategy at a time. `capture_full.py` uses a fixed
   `result_dev_backup.json` name and a fixed `__full_tmp.py` in the strategy
   directory.
4. Do not use `research/full_missing.py` for a single strategy: it rewrites
   six curves at once and re-creates the vol-scaled cache.

### 6.2 Safe commands for the 8 stale curves

```powershell
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
cd C:\Users\27175\Desktop\quant-trader-research

python research\capture_full.py donchian-breakout --dev
python research\capture_full.py drawdown-regime --run
python research\capture_full.py drawdown-stop-overlay
python research\capture_full.py dual-speed-regime
python research\capture_full.py gap-capitulation-reversal
python research\capture_full.py daily-regime-minute-entry
python research\capture_full.py dynamic-leverage-throttle --authorised
python research\capture_full.py ensemble-signals --run
```

Each command should print `WROTE ...` with 2016-01-04 .. 2026-10-23. If it
prints `NO MATCH`, stop: the current `result.json` and the current
`strategy.py` no longer agree (which is the bug this audit is about).

Then rebuild the website data and re-check:

```powershell
python research\export_compare_full.py
python research\export_research_rebuild.py
python research\export_web_catalog.py
```

`export_compare_full.py` recomputes CAGR/DD/Sharpe from the new daily curves,
so `web/public/data/compare/all.json` will change.

### 6.3 `ml-classifier` — requires a generator fix (UNSAFE as-is)

`python research\capture_full.py ml-classifier` will **not** fix the curve: it
does not replace the `"2023-12-01"` refit-schedule literal, so the 2024-2026
segment stays frozen at the 2023-12 model. Apply the `worker.py` map to
`capture_full.py` first:

```python
# research/capture_full.py, replace the two-line date rewrite with:
FULL_DATES = {
    '"2023-12-29"': '"2026-10-23"',
    '"2023-12-30"': '"2026-10-24"',
    '"2023-12-01"': '"2026-10-01"',
    "'2023-12-29'": "'2026-10-23'",
    "'2023-12-30'": "'2026-10-24'",
    "'2023-12-01'": "'2026-10-01'",
}
for a, b in FULL_DATES.items():
    source = source.replace(a, b)
```

then:

```powershell
python research\capture_full.py ml-classifier
```

This is a change to a research tool, not to a strategy or to `result.json`.

### 6.4 `vol-scaled-crash-stop` — do not regenerate the curve

The curve is valid. The defect is in `result.json`'s `windows.dev` (it is the
full 2016-2026 run). If the dev block is to be corrected, the cache must be
removed first, and the command will overwrite `result.json`:

```powershell
Remove-Item research\revisit\vol-scaled-crash-stop\dev_panel.npz
python research\revisit\vol-scaled-crash-stop\strategy.py
```

Until that is done, any consumer of `result.json` must use 57.84% (or the
curve's 57.65% daily) for dev, not 51.46%.

### 6.5 `ml-crash-overlay-winner` — do not use plain `capture_full`

Its curve is the `--full` semantics (`last_year=2026`). Plain
`capture_full.py` does not pass `--full`, so it would build weights with
`last_year=2023` on a 2026 panel; the probabilities after 2023 are NaN and the
state machine falls back to QQQ, which is not the strategy. If it must be
regenerated, use `full_missing.py`'s call
(`build_weights(..., last_year=2026)`) or add `--full` support to the
generator.

### 6.6 Safety flags

| strategy | regeneration | why |
|---|---|---|
| donchian-breakout | **safe** | `--dev` is a single `run_dev()`, no sweep |
| drawdown-regime | **safe** | `--run` builds one matrix |
| drawdown-stop-overlay | **safe mechanically** | variants are diagnostics; headline fixed at `primary` |
| dual-speed-regime | **safe mechanically** | one `build_weights`; post-tune variant is `overnight=True` |
| gap-capitulation-reversal | **safe mechanically** | one matrix plus placebo study |
| daily-regime-minute-entry | **safe mechanically** | fixed base; variants are diagnostics |
| dynamic-leverage-throttle | **safe mechanically** | `main()` calls one `build_weights`; the grid is not called |
| ensemble-signals | **safe mechanically** | one matrix |
| ml-classifier | **UNSAFE as-is** | `capture_full` misses `"2023-12-01"`; use §6.3 |
| vol-scaled-crash-stop | **UNSAFE without deleting the cache** | date-agnostic `dev_panel.npz` |
| ml-crash-overlay-winner | **UNSAFE with plain capture_full** | needs `last_year=2026` |
| all tuned strategies | **not a clean holdout** | the tune is post-holdout; label 2024-2026 as post-tune |

No strategy in the stale set tunes on the full sample in `main()`. The
"UNSAFE" cases are generator-window/cache bugs, not in-run parameter
selection.

### 6.7 After regeneration

1. Verify the new dev slice against `result.json`. The generator compares CAGR
   and DD to 5e-4; also check Sharpe, fills and the 2025-2026 tail by hand.
2. Re-run the look-ahead audit on the current code:

   ```powershell
   python research\revisit\audit\audit_all.py --only donchian-breakout,drawdown-regime,drawdown-stop-overlay,dual-speed-regime,gap-capitulation-reversal,daily-regime-minute-entry,dynamic-leverage-throttle,ensemble-signals,ml-classifier
   ```

   This overwrites `audit/audit.json` and `audit/report.md`; do it only after
   the result freeze is recorded.
3. Re-run `export_compare_full.py` last, so `all.json` matches the curves.

---

## 7. Still uncertain

1. **Did the tuner see 2024-2026?** Only `intraday-mean-reversion` has a
   `DIAGNOSIS.md`, and it says post-holdout dev-only work. The other 20 tuned
   strategies have no change log. The curves were generated before most of the
   tune, so a tuner could have looked at the full curve. This cannot be
   resolved from the files; it needs the tuner's logs, and the logs were
   deleted at 01:07.
2. **Exact pre-tune source for `vol-scaled-crash-stop`.** `_before_tune/` is
   absent. The pre-tune weights survive in
   `audit/cache/vol-scaled-crash-stop-full.npz`; they reproduce the curve
   exactly (tqqq_time 0.7195477471935474, 607 exits), but the source diff
   cannot be reconstructed.
3. **`overnight-crash-filter`'s audit capture is level-shifted.** Replaying
   the 2026-11-26 `-full.npz` gives a daily path about 24% above the curve at
   2023 (272.7 vs 219.8) with the same 10y/5y CAGR to 0.04 pp. The daily
   return differences are ~1e-4, consistent with a coarse-vs-minute re-mark or
   a different panel build; it does not affect the published dev/10y/5y
   numbers, but I did not isolate it. The curve matches `result.json` and the
   audit, so it is classified valid.
4. **`gap-fill-fade`'s replay differs by 6.6e-4 on one day** (2017-06-14).
   Immaterial, not root-caused.
5. **Variant-selection ambiguity in `capture_full.py`.** The current curves
   match the `primary` variant, but a future run could pick a different
   near-duplicate. The generator should record the captured call's kwargs and
   the source hash.
6. **`ratio-froth` has no revisit frozen result.** Its validation is against
   the `agents2/ratio-pairs` 10y/5y, which is a different directory and a
   different harness. The 0.12 pp 10y gap is consistent with marks, but it is
   not a revisit freeze.
7. **`ml-classifier`'s 2024-2026 "correct" path is unverified.** The audit's
   monthly-refit run (17.93% 10y) is the rule as specified, but it has not been
   compared with a `--full`-style run of the current file. The regeneration in
   §6.3 will produce that path; until then, 21.05% is known to be wrong and
   17.93% is the best available reference.

---

## 8. Relationship to the prior partial audit

`research/revisit/WHY_UNDERPERFORM.md` (§3.1) listed 9 stale curves and left
`vol-scaled` and `ml-classifier` "suspected, not root-caused". This audit
confirms 8 stale, reclassifies `vol-scaled` as a `result.json` window bug
(curve valid), and root-causes `ml-classifier` to the missing
`"2023-12-01"` replacement in `full_missing.py`. It also adds the
`_before_tune` == audit-cache proof, the bit-exact replay proof for 7 of the 8
stale curves (dual-speed is pinned to the exact pre-tune variant instead), and
the `ml-crash` audit-artifact finding.

**Bottom line for the website:** `all.json` is a mix of pre-tune and
post-tune strategies. On the 2016-2023 slice the public curve understates
`dual-speed-regime`, `drawdown-regime` and `donchian-breakout` by 16-23 pp and
overstates `drawdown-stop-overlay` by 7.5 pp; how much of that survives to
2026 depends on the regenerated 2024-2026 path. `vol-scaled-crash-stop`'s
headline CAGR is correct for the full window but mislabeled as dev.
Regenerating the 8 stale curves and fixing the `ml-classifier` extension is the
minimum needed before any ranking is read off the site.
