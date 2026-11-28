# Deep Drawdown Recovery v2 — development report

**Verdict: the exposure repair is honest, but it is a repair of the
drawdown-recovery *sleeve*, not of the original >=20% capitulation claim.**
On 2016-01-04 .. 2023-12-29 the repaired strategy makes **26.79% CAGR / 39.83%
max drawdown / 0.97 Sharpe at 1 bp**, with **19 entries and 28.8% average TQQQ
exposure**.  The v1 made 17.20% / 49.02% / 0.78 with 8 entries and 14.3%
exposure.  The sample and the risk-adjusted return both improve, but the
drawdown is still above the original 35% standalone bar and the circular-shift
placebo p-value is 0.11.  The strict **-20%** version cannot be repaired to a
usable sample and should be retired; v2 is a broader **-10% drawdown-recovery**
strategy and should be kept only as a diversifier.

No 2024-2026 bar or daily row entered the panel, a signal, or a statistic.
`bt.panel` slices the 1-minute archive at 2023-12-29 and the daily QQQ file is
read with `date <= 2023-12-29`.

---

## 1. Before and after

| | v1 | v2 | change |
|---|---:|---:|---:|
| Entries | 8 | **19** | +11 |
| Average TQQQ exposure | 14.3% | **28.8%** | +14.5 pp |
| Dev CAGR (1 bp) | 17.20% | **26.79%** | +9.59 pp |
| Dev max DD (1 bp, 1m) | 49.02% | **39.83%** | -9.19 pp |
| Sharpe | 0.776 | **0.968** | +0.19 |
| Sortino | 1.146 | **1.397** | +0.25 |
| Fills | 33 | **77** | +44 |
| Episode mean / t | +21.8% / 1.4 | **+12.6% / 2.04** | better sample, lower mean |
| Circular-shift placebo p | — | **0.11** | marginal |

The v2 entry list spans 2016, 2018, 2019, 2020, 2021, 2022 and 2023.  It is not
one bear market repeated: the largest single episode (2020-04-09, +97.7%)
accounts for 10.4 pp of CAGR (removing it leaves 16.42%), so the result is not
one-event dependent, but 2020 and 2023 still dominate the absolute returns.

## 2. Diagnosis

v1's low exposure is structural, not a sizing error:

- **The -20% arm is rare.**  Only 2018, 2020, 2022 and 2023 reached a 20%
  drawdown from the 52-week high.  The arm then waits for a 20-session high, so
  the first entry of a bear market is often in the following year (2019-01-16
  for the 2018 Q4 drawdown; 2020-04-09 for the 2020 crash).
- **The 2022 whipsaws cut the holds.**  Five 2022 entries lasted 7-28 sessions
  and three lost 12-14%; the 20-session-low exit was doing its job, but it
  removed most of the invested days.
- **The re-arm rule delayed the next bounce.**  A 5pp recovery from the
  post-exit low is a high bar in a bear market; the 3pp v2 rule re-enters on the
  next confirmed 20-session high.
- **The 60-session hold is not the problem.**  Extending it alone raises
  exposure from 14.3% to 18.2% and still leaves 8 entries.

Lowering the arm is the only lever that produces a sample.  The grid shows the
result is a plateau from -10% to -15%, not a single fitted point.

## 3. Rules as tested

```
dd(k)      = QQQ_close[k-1] / max(QQQ_close[k-252 .. k-1]) - 1
trough(k)  = lowest dd since the last 52-week high, through k-1
hi20(k)    = max(QQQ_close[k-20 .. k-1])
lo15(k)    = min(QQQ_close[k-15 .. k-1])

arm        once trough <= -10%; stay armed until an entry
enter      100% TQQQ when QQQ_close[k-1] > hi20(k) while armed
hold       60 sessions
exit       first close < lo15(k), or after 60 sessions
re-arm     after an exit, wait for dd >= post-exit low + 3pp
           (reference capped at -3%, so a new high always re-arms)
```

Idle weight is BIL.  No 100-250 day moving average is used.  Decisions use
closes through k-1; fills are at k's first open by `research/bt.py`.

## 4. Headline development result

| Cost | CAGR | Max DD | Sharpe | Sortino | Vol | TQQQ exposure | Fills | End equity |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **1 bp** | **26.79%** | **39.83%** | **0.968** | 1.397 | 28.93% | **28.8%** | 77 | $665,330 |
| 5 bp | 26.30% | 40.11% | 0.955 | 1.377 | 28.93% | 28.8% | 77 | $645,150 |
| 10 bp | 25.69% | 40.47% | 0.938 | 1.352 | 28.92% | 28.8% | 77 | $620,784 |
| 165-day QQQ SMA | 45.46% | 58.76% | 1.027 | — | — | 78.5% | 81 | — |
| QQQ | 18.91% | 37.30% | 0.900 | — | 22.0% | 100% | — | $398,704 |
| TQQQ | 36.15% | 82.29% | 0.801 | — | 66.5% | 100% | — | $1,175,283 |

- Daily-return correlation to the 165-day baseline: **0.371**.
- Costs are almost irrelevant: 1.1 pp of CAGR from 1 to 10 bp over eight years.
- The strategy beats QQQ on CAGR and Sharpe but not on drawdown; it is far
  below TQQQ's drawdown.  It does not beat the 165-day baseline on CAGR.

## 5. Pre-registered plateau grid

All eight rows are one-at-a-time around the primary.

| Variant | Entries | Exposure | CAGR | Max DD | Sharpe | Fills |
|---|---:|---:|---:|---:|---:|---:|
| **primary: -10%, hold 60, exit 15, rearm 3pp** | **19** | **28.8%** | **26.79%** | **39.83%** | **0.968** | 77 |
| deep 12% | 15 | 23.6% | 23.21% | 39.83% | 0.903 | 61 |
| deep 15% | 13 | 20.0% | 21.62% | 39.83% | 0.904 | 53 |
| deep 18% | 10 | 15.4% | 19.47% | 39.83% | 0.860 | 41 |
| exit 10 | 20 | 27.0% | 23.57% | 48.26% | 0.905 | 81 |
| exit 20 | 17 | 30.6% | 24.55% | 49.02% | 0.879 | 67 |
| hold 45 | 19 | 26.5% | 18.29% | 43.79% | 0.748 | 77 |
| rearm 5pp | 18 | 27.5% | 24.88% | 39.83% | 0.920 | 73 |

The deep-drawdown axis is a genuine plateau: -10% to -15% gives 13-19 entries,
20-29% exposure, 21.6-26.8% CAGR and the same 39.8% drawdown.  The failure exit
is the risk lever: `exit 10`/`exit 20` change CAGR by only 1-3 pp but both push
the drawdown to 48-49%, versus 39.8% at exit 15.  The 45-session hold is a cliff
(18.3% CAGR, 43.8% DD); the 60-session hold is the stable point.  The result is not a
single-cell fit, but it is also not insensitive to the threshold.

## 6. Episodes and robustness

| Statistic | Value |
|---|---:|
| Entries | 19 |
| Mean episode return | +12.61% |
| Median | +5.92% |
| Hit rate | 73.7% |
| Episode t-stat | 2.04 |
| Best / worst | +97.7% / -17.8% |
| Leave-one-episode-out CAGR | 16.42% .. 29.96% |
| Remove the best episode | 16.42% CAGR |
| Circular-shift placebo (100 draws) | median 12.04%, p90 26.85% |
| Placebo p(CAGR >= 26.79%) | **0.11** |
| Max DD window (daily) | 2022-08-15 .. 2023-01-19, -38.34% |

The episode t-stat of 2.04 treats entries as independent, but they cluster:
the 19 entries come from roughly 11 distinct drawdown troughs.  The
circular-shift placebo, which keeps the same holding lengths and exposure but
moves them in time, is the more honest test.  It gives p=0.11: the timing adds
about 15 pp of CAGR over the median placebo, but not enough to clear a 10%
significance bar with this sample.

### Entry list

Episode returns are TQQQ open-to-open, before the 2% band and costs.

| Entry | Exit | Sessions | Return | Exit |
|---|---|---|---:|---|
| 2016-03-02 | 2016-04-27 | 39 | +4.9% | low |
| 2016-05-25 | 2016-06-16 | 15 | -4.9% | low |
| 2016-07-11 | 2016-08-31 | 37 | +15.7% | low |
| 2018-05-10 | 2018-06-26 | 32 | +5.9% | low |
| 2019-01-16 | 2019-03-11 | 36 | +15.7% | low |
| 2019-03-14 | 2019-05-09 | 39 | +10.4% | low |
| 2019-06-18 | 2019-08-02 | 32 | +4.1% | low |
| 2020-04-09 | 2020-07-07 | 60 | +97.7% | time |
| 2020-10-12 | 2020-10-29 | 13 | -17.8% | low |
| 2020-11-09 | 2021-02-05 | 60 | +35.1% | time |
| 2021-04-05 | 2021-05-05 | 22 | +3.9% | low |
| 2022-03-21 | 2022-04-11 | 15 | -5.7% | low |
| 2022-07-20 | 2022-08-24 | 25 | +12.7% | low |
| 2022-10-26 | 2022-11-04 | 7 | -14.4% | low |
| 2022-11-14 | 2022-12-08 | 17 | -5.9% | low |
| 2023-01-18 | 2023-02-27 | 27 | +9.3% | low |
| 2023-03-22 | 2023-04-26 | 24 | +1.2% | low |
| 2023-05-01 | 2023-07-27 | 60 | +60.8% | time |
| 2023-11-08 | 2023-12-07 | 20 | +10.9% | low |

Per year (1 bp, 1-minute marks):

| Year | v2 | TQQQ | Note |
|---|---:|---:|---|
| 2016 | +15.4% | +18.6% | three entries after the Feb correction |
| 2017 | +0.7% | +118.3% | cash drag; no event |
| 2018 | +7.5% | -19.6% | one Q1 entry, no Q4 entry until 2019 |
| 2019 | +34.3% | +133.1% | post-Q4-2018 recovery |
| 2020 | +89.9% | +109.6% | April entry +97.7% |
| 2021 | +20.3% | +83.0% | two small entries |
| 2022 | -13.8% | -79.1% | bear rallies stopped out |
| 2023 | +101.6% | +198.4% | May entry +60.8% |

Sub-periods (CAGR / max DD):

| Period | v2 | Max DD |
|---|---:|---:|
| 2016-19 | 13.84% | 14.97% |
| 2020-21 | 51.22% | 35.68% |
| 2022-23 | 32.07% | 39.83% |

The 2016-19 sub-period is the honest baseline: 13.8% CAGR with a 15% drawdown is
a useful diversifier, not a TQQQ competitor.  The headline is lifted by the
2020 and 2023 rebounds.

## 7. What this does and does not prove

**It proves:**

- The low exposure was caused by the -20% arm, not by the hold or the sizing.
- A 10-15% drawdown-recovery sleeve can be traded 13-19 times in eight years
  with 20-29% exposure and a positive episode mean.
- The improved sample survives leave-one-episode-out (all 19 LOO CAGRs are
  16.4-30.0%) and the 10 bp cost ladder.

**It does not prove:**

- That the original **>=20% capitulation** state is a distinct return state.
  At -20% there are only 8 entries; that hypothesis is untestable at a usable
  sample in this window and should be retired.
- That the strategy is a standalone replacement for TQQQ or the 165-day
  baseline.  It still has a 39.8% drawdown, the 2022-23 sub-period drawdown is
  39.8%, and the placebo p-value is 0.11.
- That the 10% threshold is the "right" depth.  The plateau says the exact
  depth is not identified; -10% to -15% is a region, not a point.

## 8. Recommendation

1. **Retire the strict `-20%` claim.**  It cannot be repaired to 20-60 events;
   the four-year, eight-entry sample is not statistically usable.
2. **Keep v2 as a diversifier, not a standalone.**  Its correlation to the
   165-day baseline is 0.371, its 2016-19 sleeve is 13.8% CAGR / 15.0% DD, and
   its 1 bp Sharpe is 0.97.  Size it as a satellite.
3. **Do not promote it on the headline 26.8% CAGR.**  That number depends on
   the 2020 and 2023 rebounds and on a 10% arm that is a material change from
   the original strategy.
4. **If the mandate requires max DD <= 35% or the exact -20% state, retire the
   area as `overlay_only`.**  The repair does not meet either condition.

## 9. Files

- `strategy.py` — implementation; `--run` writes `result.json`.
- `result.json` — cost ladder, 19 episodes, sub-periods, benchmarks, 8-row grid.
- `robustness.py` / `robustness.json` — LOO, circular-shift placebo, max-DD
  window.
- `diagnose.py` — exploratory sweeps (not the pre-registered grid; writes
  `diagnose.json` when run).
