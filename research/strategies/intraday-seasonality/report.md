> **Post-test note (2026-11-27):** this file is the pre-registration, not
> the result. The frozen development result is in `../SUMMARY.md`; the
> full 2016-2026 audit, the post-tune variants and the research-validity
> verdicts are in `../WHY_UNDERPERFORM.md`. The published website curve is
> the freeze named in `../SUMMARY.md`.

# Close-Flow Exhaustion — `intraday-seasonality` (revisit)

**Status: design frozen, test pending. `result.json` deliberately absent.**
Backtests were paused by the lead on 2026-11-26 before this design was run.

## 1. The idea extracted from the original

The original `agents2/intraday-seasonality` was the round-1 winner with a
30-minute overlay: on a risk-on day where QQQ was more than 1% below its 09:30
open at 15:00, it sold TQQQ at the 15:01 open and bought back at 15:30.

The shared 165-day QQQ SMA supplied the entire book — when to own TQQQ, how much
crash protection to carry, and what to do in a bear market. The overlay only
removed 30 minutes. The genuinely new content was therefore a single claim about
the close:

> On a down day, part of the late selling is mechanical: daily-reset leveraged
> ETFs must reduce exposure in the direction of the day's move, and they do it in
> the close. The closing print is temporarily too cheap.

## 2. Standalone hypothesis

The standalone form of that claim is **not** "hold TQQQ and step aside for 30
minutes". It is:

> **Own TQQQ only for the reversal window.** Buy the closing print on an orderly,
> intraday-led QQQ decline, hold one session, and sit in BIL the rest of the time.

The signal now decides *when to be long at all* (about 11% of sessions), not when
to trim a permanent long. Universe, entry time, holding period, sizing and risk
all follow from the flow idea rather than from the old base.

### Why this is not just the old overlay minus the gate

| | original | rebuild |
|---|---|---|
| exposure | ~99% of bars | ~11% of bars |
| holding period | removes 30 minutes | owns a 23-hour reversal |
| position logic | long by default, de-risk on weakness | flat by default, long only after weakness |
| base | 165-day SMA + 4% stop | none |
| return driver | trend beta + crash avoidance | close-flow reversal |

The earlier attempt to keep the "de-risk" direction without the gate failed on
its own terms: a long-TQQQ book with the carve but **no** gate still correlates
**0.71** with the 165-day baseline (dev, pre-pause). Any always-in equity book
will, because both are driven by the same TQQQ beta. Only a part-time book can
pass the correlation rule, and the part-time version of the idea is the
reversal entry.

## 3. Universe, data and costs

- Tradeable: **TQQQ** long, **BIL** cash. Long-only, one position, ≤ 100%.
- Signal: **QQQ** 1-minute bars.
- Local adjusted 1-minute archive, 2016-01-04 → 2026-10-23, regular session.
- SPY daily is a benchmark only.
- Fills: next-bar open, 2% band, `research/bt.py`. 1 bp headline, 5/10 bp
  reported. 1-minute equity marks.
- No new data was needed, so nothing was added under `data/round3/`.

## 4. Exact rules

```
For each session d:
  at the 15:58 bar close (15:58:59 ET):
      q_day = QQQ(15:58) / QQQ(09:30 open) - 1
      if q_day <= -1.0%:  target = 100% TQQQ, filled at the 15:59 open
      else:               target = 100% BIL

  if long: sell at the next session's 15:01 open (one-session hold)
```

- Nothing after 15:58:59 is used for the decision.
- Early-close sessions (18 in the sample) never fire, because they lack a 15:58
  bar. If the *exit* session is an early close, the position is sold at the next
  session's open — the earliest executable price.
- No moving average anywhere in the position logic.
- If a new signal fires on the exit day, the book re-enters at that day's 15:59;
  back-to-back events are allowed and each pays its own round trip.

### Sizing and risk

- Base: 100% of equity when active, 0% otherwise. No leverage beyond TQQQ's own 3x.
- No stop in the base spec: the position is one session old and the exit is fixed.
- Pre-registered risk variants: a −5% close-based stop, a crash bound
  (`q_day >= -2.5%`), and a gap filter (`|gap| <= 0.5%`).

## 5. Pre-registered tests and variants

Full grid in `SPEC.md`. Summary:

| id | change | values |
|---|---|---|
| V1 | threshold | −0.75, **−1.0**, −1.25, −1.5% |
| V2 | crash bound | none, −2.5, −3.0% |
| V3 | gap filter | none, 0.5% |
| V4 | entry | **15:59**, 15:30 |
| V5 | exit | **next 15:00**, next open |
| V6 | stop | **none**, −5% |
| V7 | hold | **1**, 2 sessions |
| V8 | sizing | **full**, scaled by `|q_day|/2%` |

Bold = base spec, fixed before any test. 768 combinations; parameters must be
chosen from a plateau, not the best cell.

Placebos: same trade after **up** days (P1), on **random** sessions (P2), on
**shuffled** dates within year (P3), and selected on the **gap** instead of the
intraday move (P4) to measure overlap with the gap-reversal rebuild.

## 6. Preliminary evidence (pre-pause, not a result)

One development-only exploration was run before the pause
(`explore_dev.py`, 2016-01-04 → 2023-12-29, 1 bp, no holdout data loaded).
It tested the naive version (entry 15:31, exit next 15:01, threshold −1%, no
filters):

| variant | CAGR | max DD | Sharpe | exposure | corr vs 165d |
|---|---:|---:|---:|---:|---:|
| long TQQQ always | 36.4% | 82.3% | 0.80 | 100% | 0.71 |
| long TQQQ + 15:00-15:30 carve on weak days | 41.0% | 79.8% | 0.85 | 99% | 0.71 |
| **buy 15:30 after QQQ < −1%, hold to next 15:00** | **19.4%** | **43.4%** | **0.69** | **10.9%** | **0.25** |
| buy 15:30, hold only to next open | 1.0% | 44.5% | 0.17 | 0.9% | 0.19 |

Sub-periods of the 19.4% version: 2016-19 13.7% CAGR / 21.4% DD / 0.67;
2020-21 44.3% / 43.4% / 1.02; 2022-23 8.7% / 36.2% / 0.41.

Caveats: this used a 15:31 entry (not the close), no crash filter, no stop, and a
single threshold. It is the reason to test the idea, not proof of it. The
baseline for the correlation is the shared 165-day book; it is computed only as a
metric and is never a position in this strategy.

## 7. Expected correlation and collision risk

- **vs the 165-day baseline: ~0.20-0.30** (measured 0.25 on the pre-pause
  version). The book is invested ~11% of bars, in one-session bursts.
- **vs `gap-capitulation-reversal`: 0.4-0.6 expected.** Different trigger
  (intraday move vs opening gap) and entry (15:59 vs open), but the same broad
  "buy after a decline" family. Must be measured; if > 0.70, this strategy
  yields, because the gap version is the cleaner expression of that mandate.
- **vs `letf-rebalance-flow`: expected low.** That strategy owns the flow signal;
  this one is a long-only reversal book.
- **vs `time-of-day`: expected ~0.3.** That one is an overnight book; this one
  only incidentally spans a night.

## 8. Falsifiers

- **F1** Dev 1 bp: CAGR < 6.0% or Sharpe < 0.50.
- **F2** Correlation vs the 165-day baseline > 0.60.
- **F3** Mean return per event at 5 bp ≤ 0.
- **F4** Any dev sub-period has negative CAGR.
- **F5** The up-day placebo matches or beats the down-day signal on Sharpe.
- **F6** Fewer than 150 dev events and bootstrap p ≥ 0.05.
- **F7** With the gap filter on the edge vanishes and the base is dominated by
  gap-down days → the idea is gap-capitulation, not close flow; retire.

## 9. Results

**PENDING — not run.** Backtests are paused. When authorised, the lead runs:

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
python research\strategies\intraday-seasonality\strategy.py --windows dev
```

and, once frozen and audited, the holdout exactly once.

Placeholders to fill:

| window | 1 bp CAGR / DD / Sharpe | 5 bp | 10 bp | fills |
|---|---|---|---|---|
| dev 2016-2023 | pending | pending | pending | pending |
| holdout 2024-2026 | lead only | | | |
| 10y | pending | pending | | |
| 5y | pending | pending | | |

| control | value |
|---|---|
| corr vs 165d baseline (dev) | pending |
| corr vs gap-capitulation rebuild | pending |
| corr vs letf-rebalance-flow rebuild | pending |
| events (dev) | 237 expected signal days |
| per-event mean / t / bootstrap p | pending |
| up-day placebo | pending |
| random / shuffled placebo | pending |

## 10. Honest assessment before the test

- The pre-pause evidence is a single 8-year dev run of one parameterisation. It
  is not enough to call this working.
- Sharpe 0.69 is below the old baseline's 1.03. Even if it passes, this is a
  *diversifier*, not a replacement.
- The alternative interpretation is that this is generic short-horizon reversal
  (dip buying), not an LETF-flow effect. The gap filter (V3) and the gap-selected
  placebo (P4) are the tests of that. If they show the edge is all in gap days,
  the strategy should be retired as non-distinct.
- The 2022-23 sub-period (8.7% CAGR, Sharpe 0.41) is the weakest; the crash bound
  and stop variants exist for that reason, not because they were fitted.

## 11. Provenance

See `HYPOTHESIS.md` §5 for the full table. The load-bearing sources are:

- Cheng & Madhavan (2009) — the daily-reset trade size, `L(L−1)·r·NAV`.
- Mathis & Moerke (2022), <https://wp.lancs.ac.uk/fofi2022/files/2022/08/FoFI-2022-027-Mathis-Moerke.pdf>
  — end-of-day flow pressure and its transitory nature.
- Lenkey (2024), <https://doi.org/10.3934/QFE.2024031> — a sceptical survey; used
  as a caveat on the economic magnitude.
- ETF.com, <https://www.etf.com/sections/equity/one-bad-day-levered-qqq-etf-case-study>
  and Strasmore, <https://www.strasmore.com/blog/leveraged-etf-rebalancing-and-the-close>
  — the institutional mechanics.
- Gao, Han, Li & Zhou (2018), <https://doi.org/10.1016/j.jfineco.2018.05.009>
  — related literature; the literal first-half-hour rule did not survive here.
- Own test / no external source — the −1% signal and the one-session reversal
  book.

## 12. Files

| file | purpose |
|---|---|
| `HYPOTHESIS.md` | idea, hypothesis, provenance, falsifiers |
| `SPEC.md` | exact rules, variants, evaluation plan, hard-rule compliance |
| `strategy.py` | frozen implementation; **not run** |
| `explore_dev.py`, `explore_dev.txt` | the single pre-pause dev exploration (evidence, not part of the frozen strategy) |
| `report.md` | this file |
| `result.json` | intentionally absent until the test is authorised |
