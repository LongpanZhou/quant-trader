# Archive verification

**Scope.** The 16 Research archive strategies: `source` starts `research/new/`,
absent from `web/public/data/compare/all.json` metrics, and `above_tqqq=false`
in `research/new/LIBRARY.json`.

**Cut.** 2020-03-12 11:07 America/New_York, rebuilt on a panel truncated at the
cut; pre-cut weights compared with the full-panel weights. `cutMax` is the max
absolute weight difference before the final (partial) session of the truncated
panel. `cutMax incl. final bar` also includes that session; the final bar is
treated as a boundary only when the strategy's documented decision clock is the
session close. Weights are checked for shape, long-only and row sum <= 1.
Freshness is the count of weight changes and the mean TQQQ weight in
2024-01-02..2026-10-23. Performance was not re-tuned.

**Status (all 16).** 16 `verified-full`, 0 `stale`, 0 `needs-adapter`,
0 `no-code`, 0 `dev-only`.

**History.** The initial 9-entry holdout-only pass was 5 `verified-full`,
3 `stale`, 1 `needs-adapter`. The six below were repaired and rerun; all now
pass.

| Slug | Family | Status | cutMax | cutMax incl. final bar | 2024-26 changes | 2024-26 mean TQQQ | Reason |
|---|---|---|---:|---:|---:|---:|---|
| `always-long-vol-target` | vol-crash | **verified-full** | 0.0 | 0.0 | 489 | 82.7% | Repaired: daily signal ends on the last *completed* session; the 11:07 cut uses 2020-03-11, so the 11:06 bar carries the prior target. Dev 39.204%, full 37.253% / 58.94% / 0.95; 2024-26 freshens (489 changes, 472 unique rows). |
| `capitulation-reversal-v2` | event-recovery | **verified-full** | 0.0 | 0.0 | 86 | 3.7% | Full 2016-2026 record; pre-cut weights bit-identical; long-only, sum <= 1; 2024-26 freshens (event sleeve, 2 unique rows); dev slice exact. |
| `cross-asset-momentum` | relative | **verified-full** | 0.0 | 0.0 | 33 | 58.5% | Full 2016-2026 record; pre-cut weights bit-identical; long-only, sum <= 1; 2024-26 freshens (33 changes, 4 unique rows); dev slice exact. |
| `donchian-trend` | trend-vol | **verified-full** | 0.0 | 0.0 | 37 | 79.2% | Full 2016-2026 record; pre-cut weights bit-identical; long-only, sum <= 1; 2024-26 freshens (37 changes, 24 unique rows). Dev number differs by 0.46 pp only because `result.json` is daily-mark and the holdout dev is 1-minute-mark. |
| `intraday-close-momentum` | vol-crash | **verified-full** | 0.0 | 0.0 | 188 | 86.5% | Repaired: `_daily_vol` reads through the panel's actual last completed session, and a partial final session is excluded. 2024-26 trades again (188 changes, 114 unique rows). Dev 46.208%; full 37.478% / 54.375% / 0.93, 0.06 pp below the TQQQ full bar. |
| `macro-event-tqqq` | calendar | **verified-full** | 0.0 | 0.0 | 45 | 57.3% | Repaired: ex-ante FOMC dates added through 2026-09-16 (the 2026-10-28 meeting is after the 2026-10-23 panel end). Dev-panel rerun is exactly 51.061% / 48.831%; full 44.391% / 57.194% / 1.06. 2024-26 freshens (45 changes, mean TQQQ 57.3%). Above the TQQQ full bar but **not promoted**. |
| `momentum-crash-filter` | trend-vol | **verified-full** | 0.0 | 0.0 | 32 | 84.5% | Full 2016-2026 record; pre-cut weights bit-identical; long-only, sum <= 1; 2024-26 freshens (32 changes, mean TQQQ 84.5%); dev slice exact. |
| `overnight-drift-filter` | session-timing | **verified-full** | 0.0 | 3.85e-3 | 275 | 79.5% | Full 2016-2026 record; pre-session prefix exact. The only 11:07 difference is the final partial bar, where the 15:58 rule writes the truncated session's 11:05 close as the 15:58 close; boundary artifact, not price look-ahead. 2024-26 freshens strongly (275 changes, 185 unique rows); dev slice exact. |
| `turn-of-month` | calendar | **verified-full** | 0.0 | 0.0 | 69 | 52.8% | Repaired: optional ex-ante exchange-calendar adapter; the 11:07 audit passes the full 2016-2026 session calendar, so 2020-03-12 is correctly mid-month. Full record unchanged (41.409% dev; 33.621% full; 69 changes, mean TQQQ 52.8%). |
| `dual-momentum-tqqq` | relative | **verified-full** | 0.0 | 0.0 | 57 | 93.6% | One-shot full run after `run_holdout`'s authorized guard lift. Dev exact (41.149% vs 41.15%); pre-cut weights bit-identical; long-only, sum <= 1; 2024-26 freshens (57 changes, 50 unique rows). Full 41.61% / 57.95% / 0.96 is above the TQQQ full bar but is **not promoted**. |
| `orb-tqqq-volume` | intraday-microstructure | **verified-full** | 0.0 | 0.0 | 394 | 20.3% | Repaired: `build_weights` accepts a full-panel TQQQ bars frame, and `run_holdout.py` calls the optional `build_holdout_weights()` hook. Dev exact (17.895%); full 14.992% / 21.376% / 0.91; 2024-26 freshens (394 changes, mean TQQQ 20.3%). Cut 0.0 using only bars through 11:06. |
| `overnight-intraday-trend` | session-timing | **verified-full** | 0.0 | 0.0 | 384 | 66.5% | One-shot full run. Dev exact (64.631% vs 64.631%); pre-cut weights bit-identical; long-only, sum <= 1; 2024-26 freshens (384 changes, 2 unique rows). Full 56.62% / 35.66% / 1.32 is above the TQQQ full bar but is **not promoted**. |
| `pre-holiday` | calendar | **verified-full** | 0.0 | 0.0 | 58 | 9.4% | Repaired: 2024-26 scheduled NYSE holidays added, and `_pairs()` suppresses holidays after the panel's last session. Dev-panel rerun is exactly 4.231% / 31.216%; full-run dev slice is 4.055% because the 2024-01-01 window adds 2023-12-27..29. Full 6.820% / 31.216% / 0.49; holdout 16.25%; 58 changes, mean TQQQ 9.4%. |
| `spy-confirmed-trend` | trend-vol | **verified-full** | 0.0 | 0.0 | 48 | 82.1% | One-shot full run after the module's own authorized guard lift. Dev exact (50.362% vs 50.362%); pre-cut weights bit-identical; long-only, sum <= 1; 2024-26 freshens (48 changes, 20 unique rows). Full 47.57% / 43.27% / 1.13 is above the TQQQ full bar but is **not promoted**. |
| `tqqq-fast-drawdown-stop` | vol-crash | **verified-full** | 0.0 | 0.0 | 13 | 76.1% | One-shot full run. Dev exact (52.829% vs 52.829%); pre-cut weights bit-identical; long-only, sum <= 1; 2024-26 freshens (13 changes, 2 unique rows). Full 50.72% / 45.90% / 1.16 is above the TQQQ full bar but is **not promoted**. |
| `tqqq-vol-target-aggressive` | vol-crash | **verified-full** | 0.0 | 0.0 | 705 | 77.8% | One-shot full run. Dev exact (40.156% vs 40.156%); pre-cut weights bit-identical; long-only, sum <= 1; 2024-26 freshens strongly (705 changes, 647 unique rows). Full 37.17% / 57.77% / 1.00 is below the TQQQ full bar. |

## Repairs applied (verification only)

1. **`always-long-vol-target`** — `build_weights` now ends the daily signal on
   the last completed session. A partial final session (the 11:06 bar at a
   11:07 cut) carries the prior session's target. Full record unchanged; cut
   max 0.0.
2. **`intraday-close-momentum`** — `_daily_vol` uses the panel's actual last
   completed session instead of `DEV_END=2023-12-29`; `_session_indices` drops a
   partial final session. 2024-26 now trades; cut max 0.0.
3. **`macro-event-tqqq`** — added ex-ante FOMC decision dates for 2024-2026
   through 2026-09-16. Dev-panel result unchanged; 2024-26 now trades; cut
   max 0.0.
4. **`turn-of-month`** — added an optional ex-ante exchange-calendar parameter
   to `build_weights`. The full record is unchanged; the 11:07 audit with the
   full calendar gives 0.0.
5. **`orb-tqqq-volume`** — added a `bars=` adapter and `build_holdout_weights()`
   hook; the frozen `build_weights` no longer has to ignore the supplied panel.
   Full record 14.99% / 21.38% / 0.91; cut max 0.0.
6. **`pre-holiday`** — added 2024-26 scheduled NYSE holidays and made `_pairs()`
   suppress holidays after the panel's last session. Dev-panel result unchanged;
   full record 6.82% / 31.22% / 0.49, holdout 16.25%; cut max 0.0.

## Notes

1. **No parameter tuning.** The six repairs are data-window/calendar fixes:
   completed-session signal ends, panel-end vol, ex-ante FOMC and NYSE calendars,
   full-panel TQQQ bars, and an ex-ante month-end calendar. Signal thresholds,
   weighting rules and selection logic are unchanged.
2. **Dev reproduction.** Dev-panel reruns reproduce the frozen `result.json`
   exactly for all six: 39.204%, 46.208%, 51.061%, 41.409%, 17.895%, 4.231%.
   The full-run dev slices differ only where the longer panel changes a final
   bar (`macro-event` +0.045 pp) or adds a 2024-01-01 pre-holiday window to late
   2023 (`pre-holiday`, 4.055% vs 4.231%).
3. **No promotion.** Five one-shot records have full-window CAGR above the TQQQ
   full bar: `dual-momentum-tqqq`, `overnight-intraday-trend`,
   `spy-confirmed-trend`, `tqqq-fast-drawdown-stop`, `macro-event-tqqq`. They
   are recorded as verification results only; `LIBRARY.json`, `above_tqqq` and
   the website data were not changed.
4. **Files changed.** The six `strategy.py` files, the optional
   `build_holdout_weights()` hook in `research/new/run_holdout.py`, the six
   regenerated `holdout.json` records and their `research/new/curves/` entries,
   plus this report and `research/new/ARCHIVE_VERIFICATION.json`. This task
   did not modify any website, META or exporter file; pre-existing worktree
   changes are from the parent session.
