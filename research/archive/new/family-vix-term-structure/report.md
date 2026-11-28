# VIX term structure — development report

**Family:** `vix-term-structure`  
**Directory:** `research/new/family-vix-term-structure/`  
**Window:** 2016-01-04 .. 2023-12-29 (development only). No 2024-2026 data
enters any signal, result or robustness calculation; the external series are
truncated at the development end before the features are computed.  
**Headline marks:** 1-minute panel, next-session 09:30 open, 2% band, 1 bp
headline cost; 5 bp and 10 bp reported.  
**Pre-registration:** `HYPOTHESIS.md`.

## Verdict (short)

**Qualified pass on the pre-registered development bar, with a weak placebo and
a severe 2022 drawdown.** At 1 bp the strategy earns **48.82% CAGR, 65.45% max
drawdown and 1.080 Sharpe** versus the TQQQ bar of **36.72% / 82.29% / 0.82**.
It has **165 fills**, 82 state changes, 41 round trips and 79.3% average TQQQ
exposure. Six of the eight pre-registered box cells clear the bar, the
circular-shift placebo is significant at 10% (p = 0.074 for the signal shift,
p = 0.054 for the matched state-path shift), and the maximum correlation with
the nine winners is 0.735.

The pass is not clean. The 2022 calendar year is **-55.9%**; the max drawdown is
a **63.3% peak-to-trough** fall from 2021-11-19 to 2022-06-16 on session-end
marks (65.45% intraday). The term-structure signal did not anticipate the slow
2022 bear market: it reacted to vol spikes, re-entered on calm, and was
whipsawed through the H1 2022 bear rallies. The edge is a handful of large
regime calls (2018, 2020, 2022 relative), not a consistent monthly timing rule.
It should go to a one-shot holdout only as a diversifying regime overlay, not as
a crash shield.

## 1. What was tested

The VIX/VIX3M ratio is the shape of the implied-vol curve. Contango (ratio < 1)
is a calm state; backwardation (ratio > 1) is a stressed state. The strategy
trades a long-only TQQQ/BIL book on a hysteresis machine:

| Condition | Target |
|---|---|
| `vr >= 1.05` or `d20 >= +0.10` | 100% BIL |
| `vr <= 0.95` and `d20 <= +0.05` | 100% TQQQ |
| otherwise | hold previous state |

where, for official external closes:

```
vr_t  = VIX_t / VIX3M_t
d20_t = vr_t - vr_{t-20}
```

The 0.95-1.05 level band is the deadband. The 0.05-0.10 change band is the
second deadband: re-entry requires the 20-session change to have cooled to
+0.05, not merely to be below the +0.10 stress trigger. The decision is taken
from the session's official external close, written at the session's 15:59 bar
and filled at the next session's 09:30 open. Bars inside a session carry the
target written at the previous close. Idle capital is BIL.

The centre is a round-number cell (`0.95 / 1.05 / 0.10`, 20 sessions). A coarse
exploration on the same development window preceded the centre; the full 8-cell
box and the 5-day/level-only ablations are reported in section 6 so the reader
can judge the selection.

## 2. Data and execution

- Signal series: Yahoo daily `^VIX` and `^VIX3M` adjusted closes, 2015-01-02
  onward. Both start more than a year before the first development session.
- Execution: local 1-minute QQQ/TQQQ/BIL panel, next-session 09:30 open, 2%
  rebalance band, 1 bp headline cost, 5/10 bp sensitivity. The benchmark is
  100% TQQQ on the same panel and cost.
- No 2024+ row is loaded: `vix_features(DEV_END)` truncates both series before
  the ratio is formed. The panel itself ends 2023-12-29.

## 3. Headline development metrics

1-minute panel, next-session open, 2% band. "TQQQ exposure" is the mean TQQQ
weight; the harness "exposure" is 100% because idle capital is BIL.

| Cost | CAGR | Max DD | Sharpe | Sortino | Vol | TQQQ exp. | Fills | Turnover | Ending equity |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 bp | **48.82%** | **65.45%** | **1.080** | 1.526 | 47.31% | 79.33% | **165** | 1020.1x | $2,390,509 |
| 5 bp | 47.59% | 65.72% | 1.062 | 1.500 | 47.31% | 79.33% | 165 | 974.1x | $2,237,829 |
| 10 bp | 46.07% | 66.07% | 1.040 | 1.469 | 47.32% | 79.33% | 165 | 919.8x | $2,060,619 |
| TQQQ B&H | 36.15% | 82.29% | 0.801 | 1.122 | 66.55% | 100% | 1 | 1.0x | $1,175,165 |
| QQQ B&H | 18.91% | 37.30% | 0.900 | — | 22.02% | 0% | 1 | 1.0x | $398,628 |
| **TQQQ dev bar** | **36.72%** | **82.29%** | **0.82** | — | — | — | — | — | — |

The strategy clears the bar on all three headline metrics. The 1 bp to 10 bp
cost is 2.75 pp of CAGR. The daily-bar cross-check (same decision clock, one
open/close per session) is 48.41% CAGR / 63.30% DD / 1.061 Sharpe / 165 fills.
The two paths agree within 0.4 pp of CAGR; the 1-minute path has a slightly
deeper intraday drawdown.

## 4. Activity and trade anatomy

| Item | Value |
|---|---:|
| Full-window fills | **165** |
| State changes | **82** (41 entries, 41 exits) |
| TQQQ buys / sells | 42 / 41 |
| Average on-run | 38.0 sessions |
| Median on-run | 28.0 sessions |
| On sessions / fraction | 1,597 / 79.4% |
| State changes by year | 11, 13, 12, 14, 9, 15, 11, 4 (2016-2023) |
| Final state | risk-on |

The strategy is active in every year. The largest number of state changes is
2021 (15), the smallest 2023 (4). The 2022 path is the important one: it went
off on 2022-01-21, re-entered on 2022-02-08, off on 2022-02-10, on 2022-02-15,
off on 2022-03-02, on 2022-03-15, off on 2022-04-26, on 2022-05-20, off on
2022-09-06 and on 2022-11-03. That is a whipsaw through the H1 bear rallies, not
a clean exit.

## 5. Subperiods and yearly returns

| Subperiod | Strategy CAGR | Strategy DD | Strategy Sharpe | TQQQ CAGR | TQQQ DD |
|---|---:|---:|---:|---:|---:|
| 2016-2019 | 45.91% | 35.69% | 1.240 | 48.60% | 58.0% |
| 2020-2021 | 92.93% | 30.29% | 1.523 | 91.47% | 69.9% |
| 2022-2023 | **14.36%** | **61.58%** | 0.528 | -22.33% | 81.0% |

The strategy roughly matches TQQQ in the two bull subperiods (slightly below in
2016-2019, slightly above in 2020-2021) with much smaller drawdowns, and turns
the 2022-2023 bear from -22.3% CAGR into +14.4% CAGR. But the 2022-2023 path
contains a 61.6% drawdown; the positive subperiod CAGR is driven by 2023, not
by avoiding 2022.

| Year | Strategy | TQQQ | QQQ |
|---:|---:|---:|---:|
| 2016 | +26.1% | +18.6% | +9.3% |
| 2017 | +66.6% | +113.0% | +31.5% |
| 2018 | -4.9% | -23.5% | -1.8% |
| 2019 | +109.4% | +130.5% | +38.4% |
| 2020 | +147.9% | +99.8% | +45.9% |
| 2021 | +56.2% | +90.9% | +29.2% |
| 2022 | **-55.9%** | -79.7% | -33.2% |
| 2023 | +202.4% | +204.9% | +55.9% |

The 2022 monthly losses are the honest core of the result: January -35.1%,
April -34.3%, June -27.6%, December -26.5%, August -16.6%. A "crash filter"
that loses 56% in the bear year is not a crash filter. It is a regime overlay
that reduces, but does not remove, bear-market beta.

## 6. 8-cell parameter plateau

The pre-registered 2 x 2 x 2 box around the centre `(0.95, 1.05, 0.10)`:

| `lo` | `hi` | `thr` | CAGR | Max DD | Sharpe | Fills | Clears bar |
|---:|---:|---:|---:|---:|---:|---:|:--:|
| 0.93 | 1.03 | 0.08 | 40.94% | 68.75% | 1.003 | 189 | yes |
| 0.93 | 1.03 | 0.12 | 33.32% | 78.47% | 0.842 | 141 | no |
| 0.93 | 1.07 | 0.08 | 40.94% | 68.75% | 1.003 | 189 | yes |
| 0.93 | 1.07 | 0.12 | 32.33% | 78.47% | 0.824 | 141 | no |
| 0.97 | 1.03 | 0.08 | 51.97% | 57.65% | 1.144 | 205 | yes |
| 0.97 | 1.03 | 0.12 | 42.29% | 73.43% | 0.952 | 149 | yes |
| 0.97 | 1.07 | 0.08 | 51.79% | 57.65% | 1.142 | 205 | yes |
| 0.97 | 1.07 | 0.12 | 42.83% | 73.43% | 0.958 | 145 | yes |
| **centre 0.95/1.05/0.10** | | | **48.82%** | **65.45%** | **1.080** | **165** | **yes** |

Six of eight cells clear the full bar; the two failures are the `thr=0.12`
cells at the lower re-entry level, where the strategy waits too long to
re-enter. The centre is not the box maximum (the 0.97/0.08 cells are higher),
so the result is not a single-cell selection. The `hi` dimension is nearly
inert at 1.03 vs 1.07: the 20-day change trigger, not the inversion level,
does most of the work.

**Ablations.** A 5-day change window gives 26.38% CAGR / 79.36% DD / 0.706
Sharpe / 175 fills: too noisy, fails the bar. Level-only (`vr <= 0.95`) gives
28.62% CAGR / 74.80% DD / 0.775 Sharpe / 341 fills: also fails. The 20-day
change and the hysteresis are both necessary; the signal is not just "long when
VIX is low."

## 7. Placebo / randomized signal dates

Two circular-shift placebos on the daily panel, 500 draws each:

| Placebo | Observed daily CAGR | p-value | 5th pct | Median | 95th pct |
|---|---:|---:|---:|---:|---:|
| Shift the VIX/VIX3M series | 48.41% | **0.074** | 8.67% | 25.04% | 51.19% |
| Shift the state path (matched exposure/run lengths) | 48.41% | **0.054** | 9.46% | 25.63% | 48.86% |

The signal-shift p-value is 0.074 and the state-path p-value is 0.054. The
observed CAGR is near the 95th percentile of both placebo distributions. This
is suggestive, not overwhelming: the strategy is long TQQQ 79% of the time, and
a random 79%-long path in this bull market still earns a median 25% CAGR. The
timing adds roughly 23 pp of CAGR over the median random path, but the upper
tail of the placebo distribution is close to the observed result.

## 8. Correlation with the nine existing winners

Daily development returns, 2016-01-04 .. 2023-12-29:

| Winner | Correlation |
|---|---:|
| ratio-froth | 0.567 |
| vol-scaled-crash-stop | 0.722 |
| relative-value-tqqq | 0.709 |
| fomc-opex-window | 0.620 |
| family-session-timing | 0.578 |
| family-short-reversal | 0.556 |
| family-rebalance-flow | 0.735 |
| family-intraday-microstructure-day | 0.471 |
| family-ml-microstructure | 0.653 |

Range **0.471-0.735**, maximum 0.735 (rebalance-flow). This is below the 0.85
overlap threshold. The strategy shares the long-TQQQ beta of the winners, but
its drawdown path is different: it loses less in 2018 and 2022 and more in 2017
and 2021.

## 9. Mechanism check

The economic story is only partly supported:

- **Supported:** the calm-contango state is a good time to hold TQQQ; the
  backwardation/rapid-repricing state is a good time to reduce. The 2018 Q4 and
  2020 Q1 exits both helped.
- **Not supported:** the signal is not a leading crash indicator. In 2022 the
  curve did not invert decisively until the bear was well underway, and the
  re-entry rule repeatedly bought bear-market rallies. The 2022 loss is -55.9%.
- **Not supported:** the edge is not stable across the decade. 2017 (+66.6% vs
  TQQQ +113.0%) and 2021 (+56.2% vs +90.9%) are large opportunity costs.

The term structure is a **regime conditioner**, not a tail hedge. It reduces
the frequency and depth of large losses but does not eliminate them.

## 10. Kill criteria

| Criterion | Result | Pass? |
|---|---|:--:|
| 1 bp CAGR > 36.72% | 48.82% | yes |
| 1 bp Sharpe > 0.82 | 1.080 | yes |
| 1 bp max DD < 82.29% | 65.45% | yes |
| >= 100 fills or >= 30 state changes | 165 / 82 | yes |
| >= 6 of 8 box cells clear bar | 6 of 8 | yes |
| Placebo p < 0.10 | 0.074 (signal) / 0.054 (state) | yes |
| 2022-2023 CAGR > -25% | +14.36% | yes |
| Max correlation < 0.85 | 0.735 | yes |
| 10 bp CAGR > 36.72% | 46.07% | yes |

All pre-registered criteria pass. The verdict is nevertheless **qualified**, for
the reasons in section 9: the 2022 drawdown is severe, the placebo is only
marginally significant, and the 2023 result is close to TQQQ buy-and-hold. The
strategy is a legitimate diversifying regime overlay, not a replacement for a
crash filter.

## 11. Holdout recommendation

Send to the one-shot 2024-2026 holdout as a **diversifying regime overlay**,
with the following expectations stated in advance:

- The 2022-type slow bear is the failure mode; a repeat would produce a large
  drawdown even if the strategy beats TQQQ.
- The 2023-type melt-up is the opportunity-cost mode; the strategy should track
  TQQQ closely if the curve stays in contango.
- The result depends on the 20-day change window and the 0.95 re-entry level.
  If the holdout is driven by a different regime, the edge may not persist.

## 12. Reproduction

```
$env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
$env:BT_THREADS = "4"
python research/new/family-vix-term-structure/strategy.py
```

`strategy.py` exposes `build_weights(ts, opens, closes)` returning the `(n, 3)`
long-only weight matrix and regenerates `result.json` on the development panel.
