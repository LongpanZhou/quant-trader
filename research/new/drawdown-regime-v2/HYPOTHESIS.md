# Deep Drawdown Recovery v2 — hypothesis and repair plan

**Status:** repaired, development window only. 2016-01-04 .. 2023-12-29.
**Original:** `research/revisit/drawdown-regime` (8 episodes, 14.3% exposure,
17.20% CAGR / 49.02% DD / 0.78 Sharpe at 1 bp).
**Data:** QQQ (signal), TQQQ (risk), BIL (cash), adjusted 1-minute regular
session; QQQ daily closes only through 2023-12-29.  No 2024+ row is used.
**Harness:** `research/bt.py`, next-open fills, 2% band, 1/5/10 bp.

---

## 1. Diagnosis: why v1 traded only 8 times

v1 armed after a **-20% drawdown from the 52-week high** and then waited for a
confirmed 20-session high.  On the development window:

- Only four years (2018, 2020, 2022, 2023) ever reached -20%.
- The arm plus the 5pp re-arm rule produced 8 entries; the 2022 entries were
  bear-market rallies that the 20-session-low exit cut short after 7-28 sessions.
- The 60-session hold produced 287 invested days, i.e. 14.3% exposure.
- The result was 17.20% CAGR / 49.02% DD / 0.78 Sharpe, and the episode mean
  had a t-stat of only 1.4.  The sample is too small to distinguish the timing
  from luck.

The low exposure is therefore **not a sizing bug**: it is the -20% arm plus the
confirmed-turn condition.  At -20% the event is a once-per-bear-market state, and
there are not 20-60 of them in eight years.

## 2. What is preserved

The family is unchanged:

- QQQ drawdown from its 252-session high is the state variable.
- A 20-session close high is the confirmed-turn trigger.
- 100% TQQQ inside a fixed holding window, 100% BIL outside.
- A 15-session-low close is the failure exit; a 3pp recovery from the post-exit
  low is the re-arm condition.
- No 100-250 day moving average; long-only; weights >= 0 and sum <= 1.

## 3. What changed, and why

| Parameter | v1 | v2 | Reason |
|---|---:|---:|---|
| `deep_dd` | 0.20 | **0.10** | The -20% arm is the binding constraint on the sample. A 10% drawdown from the 52-week high is still a deep correction (QQQ's 2016, 2018, 2019, 2020, 2021, 2022 and 2023 corrections all qualify) and is the smallest relaxation that reaches ~20 entries. |
| `exit_low` | 20 | **15** | The 20-session-low exit let 2022 bear rallies run too long; a 15-session low cuts the failed bounces earlier. |
| `rearm` | 0.05 | **0.03** | A 5pp recovery was too slow to re-enter the same correction; 3pp keeps the "wait for a turn" idea but allows the next confirmed 20-session high. |
| `hold` | 60 | **60** | Unchanged. The 60-session hold is the original time-limited recovery window. |

This is a real relaxation of the original "deep" qualifier.  The strict -20%
strategy is not repairable to a 20-60 event sample; the report recommends
retiring the -20% claim and treating v2 as a broader **drawdown-recovery**
strategy, not as evidence that the >=20% capitulation state works.

## 4. Pre-registered plateau grid (8 variants)

Fixed before the final run.  One-at-a-time around the primary; everything else
stays at the primary value.

| # | Variant | Change |
|---|---|---|
| 1 | primary | `deep_dd=0.10, hold=60, exit_low=15, rearm=0.03` |
| 2 | deep 12% | `deep_dd=0.12` |
| 3 | deep 15% | `deep_dd=0.15` |
| 4 | deep 18% | `deep_dd=0.18` |
| 5 | exit 10 | `exit_low=10` |
| 6 | exit 20 | `exit_low=20` |
| 7 | hold 45 | `hold=45` |
| 8 | rearm 5pp | `rearm=0.05` |

All eight are reported in `result.json` and `report.md`.  A result that only
works at the primary point, with a cliff on both sides, is treated as fitted.

## 5. Falsifiers for the repair

1. Fewer than 15 entries or less than 20% average TQQQ exposure.
2. The 10-15% plateau is a cliff: neighbouring `deep_dd` values lose more than
   half the CAGR or double the drawdown.
3. The episode mean is not positive, or its t-stat is below 1.5.
4. Removing the single best episode drops CAGR below 10% (one-event dependence).
5. A circular-shift placebo with the same holding lengths has a median CAGR
   within 5 pp of the strategy, or p(CAGR >= strategy) < 0.10.
6. Dev max drawdown is still above 35%, or the 2022-23 sub-period drawdown is
   above 30%: then the strategy is a diversifier, not a standalone.

Falsifier 6 is expected to fail.  The honest headline is a repaired
**diversifier**, not a standalone replacement for TQQQ.

## 6. Timing

Every decision for session k uses QQQ daily closes through k-1 only.  The
target is written on session k-1's last 1-minute bar and fills at session k's
first bar open.  The time exit writes 0 on the last held session's penultimate
bar, so it fills at the 15:59 open of the final session.  The 1-minute panel is
physically sliced at 2023-12-29 (`bt.panel(..., DEV_END)`), and the daily QQQ
file is read with a `date <= 2023-12-29` parquet filter.

## 7. Files

- `strategy.py` — implementation and `--run`; writes `result.json`.
- `result.json` — cost ladder, episodes, sub-periods, benchmarks, 8-variant grid.
- `robustness.py` / `robustness.json` — leave-one-episode-out, circular-shift
  placebo, max-drawdown window.
- `diagnose.py` — exploratory sweeps that motivated the fix (not part of the
  pre-registered grid; writes `diagnose.json` when run).
