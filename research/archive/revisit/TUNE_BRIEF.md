# Tune brief: why doesn't this strategy beat TQQQ?

You own exactly **one** strategy: `research/revisit/<slug>/`. Twenty-five other
agents are working on the other strategies at the same time, in the same
folder tree. Touch nothing outside your own folder.

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
$env:BT_THREADS = "1"      # 26 agents share 12 cores: always set this
```

Don't use `python -I`. Write files with `open(path, "w", newline="\n", encoding="utf-8")`.

## Background

Read `research/revisit/BRIEF.md` (rules for these rebuilds) and
`research/revisit/SUMMARY.md` (where each one landed). The engine is
`research/bt.py` (next-bar-open fills, 2% band, 1 bp headline, $100k start,
compiled Rust core). An independent audit (`research/revisit/audit/report.md`)
found every strategy clean: no look-ahead, real prices, native 1-minute bars.

Benchmarks (1 bp, 1-minute marks):

| window | TQQQ CAGR / DD | QQQ CAGR / DD |
|---|---|---|
| dev 2016-01-04 → 2023-12-29 | 36.39% / 82.29% | see `bt` |
| 10y 2017-01-03 → 2026-10-23 | 39.38% / 82.29% | 20.67% / 37.30% |

Most rebuilds return 0–20% a year. Your job is to find out **why yours does**,
fix anything that is wrong, and improve it if a real improvement exists.

## Step 1. Check the implementation (spec vs code)

1. Read `SPEC.md` / `HYPOTHESIS.md` / `report.md` and `strategy.py` line by line.
2. List every rule in the spec and confirm the code does exactly that:
   thresholds, `<` vs `<=`, which bar a decision uses, which bar it fills on,
   session boundaries (index by bar, half days end 13:00, 18 sessions have
   missing minutes), warm-up, units (pandas 3 timestamps may be microseconds:
   use `.as_unit("ns").asi8`), and the array index each weight is written to.
3. Look for silent bugs of the kind already found in this repo: a session
   number used as a minute index, a rolling window that includes the value it
   is compared against, a cache read in the wrong unit, a signal that never
   fires (count the events), a position that never closes.
4. Fix real bugs. Each fix is a finding: what was wrong, the evidence, and how
   the numbers moved (including when they got worse).

## Step 2. Diagnose the gap to TQQQ (development period only)

Measure, don't guess. Report at least:

- **exposure:** fraction of minutes held in TQQQ, QQQ, BIL, synthetic short;
  average gross leverage (TQQQ counts 3×);
- **leverage-matched comparison:** the return of simply holding TQQQ at your
  average exposure (e.g. 30% TQQQ / 70% BIL, rebalanced daily). If you can't
  beat that, the signal adds nothing over a static mix;
- **per-year table:** your CAGR vs TQQQ vs QQQ for 2016…2023;
- **where the gap comes from:** missed up-days (time out of the market in
  rallies), losses during your positions, costs and turnover (trades/yr, cost
  drag at 1/5/10 bp);
- **event count and hit rate** of the core signal; bootstrap p-value if
  fewer than 100 events.

Write a one-paragraph verdict: is the shortfall because the signal is weak,
because it is rarely active (low exposure), because of a bug, or because of
costs?

## Step 3. Improve it, if you honestly can

Allowed: changing sizing (e.g. TQQQ instead of QQQ when the signal is on, or
scaling by signal strength), filling idle time with something justified by
the idea, entry/exit timing, holding period, adding assets the data supports.

Rules (non-negotiable):

- **Development period only (2016-01-04 → 2023-12-29).** Never compute,
  print or look at any result after 2023-12-29. The lead runs 10y/holdout.
- **BRIEF.md hard rules still apply:** no 100–250-day moving-average gate on
  QQQ/TQQQ/SPY/NDX under any name; no reuse of old base weights; daily-return
  correlation with the 165-day baseline below 0.60 on dev. Don't "beat TQQQ"
  by quietly holding TQQQ most of the time: if your corr rises above 0.60,
  that version is rejected.
- **Overfitting controls** for every change: count of variants tried,
  a ±1-step parameter neighbourhood table (choose from a plateau, not a peak),
  sub-periods 2016–19 / 2020–21 / 2022–23, and a placebo/random control.
  A change that helps only one sub-period is not an improvement.
- **Keep the interface:** `build_weights(...)` name and existing call
  signature, `main()` writing `result.json` with the same keys, so
  `research/revisit/run_all.py` and `run_holdout.py` still work. Weights must
  be finite, ≥ 0, row sum ≤ 1; synthetic short columns must be 0 on each
  session's last bar.
- **No look-ahead.** Decision at bar i's close uses only data up to bar i.
  Re-run your own cut test: build weights on data truncated at
  2020-03-12 11:07 and 2022-09-13 10:41 (see
  `research/revisit/audit/worker.py:install_cut` and `audit/cut_direct.py`);
  every weight before the cut must be unchanged.
- **Before changing anything,** copy `strategy.py`, `result.json`,
  `report.md` into `<slug>/_before_tune/`.
- It is fine, and often correct, to conclude "no honest improvement exists".
  Say so with the evidence. Beating TQQQ's CAGR is not required; a strategy
  with a much lower drawdown, a better Sharpe, or low correlation can be the
  right answer. A curve-fit win is worse than an honest loss.

Do **not** edit `research/bt.py`, anything in `research/revisit/audit/`,
`run_all.py`, `run_holdout.py`, `web/`, or another strategy's folder.

## Step 4. Deliverables in your folder

1. `DIAGNOSIS.md`: step 1 findings, step 2 tables and verdict, step 3
   variants tried with the overfitting tables, and the final decision
   (changed / unchanged / retire), with before→after dev numbers at 1/5/10 bp
   and the correlation with the 165-day baseline.
2. If changed: updated `strategy.py`, re-run `result.json` (produced by the
   script, never edited by hand), and a short "Tuning (2026-11-27)" section
   appended to `report.md`.
3. A final reply to the lead of at most 15 lines: bugs found, why it trails
   TQQQ (one sentence), what changed, dev CAGR / DD / Sharpe / corr before →
   after, and anything the lead should double-check.
