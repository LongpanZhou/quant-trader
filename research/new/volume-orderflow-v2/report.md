# Repair report — volume-orderflow → v2

**Status:** **`retired` as a participation strategy.** The headline development
return is positive, but the close-location plateau fails and the volume
condition is not established as additive. It is not evidence for participation
exhaustion.
**Development window:** 2016-01-04 → 2023-12-29. **Holdout 2024-2026:**
outside the analysis panel, not inspected.
**Original:** `research/revisit/volume-orderflow/`
**New code:** `strategy.py` · **Pre-registration:** `HYPOTHESIS.md` · **Raw
numbers:** `result.json`

---

## 1. The original: three events, thirteen fills, 0.75% exposure

The original signal required

```
rvol    = QQQ volume / mean(prior 20 sessions) >= 1.5
intraday= QQQ close / QQQ open - 1             <= -0.8%
clv     = ((close-low) - (high-close)) / range >= 0
```

Development counts (2012 sessions):

| Component | Days |
|---|---:|
| `rvol >= 1.5` | 192 |
| `QQQ intraday <= -0.8%` | 342 |
| `clv >= 0` | 1183 |
| all three | **3** |

The close-location leg is the problem. `clv >= 0` is common in general (1183
days), but conditional on QQQ falling at least 0.8% intraday, only **5**
sessions close in the upper half of their range. A large down day normally
closes near its low, so `clv >= 0` and `intraday <= -0.8%` are almost
self-contradictory. The conjunction, not any single component, is the
bottleneck. The three original events were 2020-09-04, 2021-05-04 and
2021-07-27; the original 1 bp development result was CAGR 0.87%, DD 16.66%,
Sharpe 0.15, 13 fills and **0.746% session exposure** (the `bt.stats`
"exposure" is ~100% only because BIL is a security). Three trades in eight years
is not a strategy.

## 2. What was changed

The pre-registered repair is a **count fix**: relax the close-location floor
from the upper half to the upper three-quarters of the range, and the volume
floor from 1.5× to 1.3×:

```
event = (rvol >= 1.3) AND (QQQ intraday <= -0.8%) AND (clv >= -0.5)
```

Repaired component counts:

| Component | Days |
|---|---:|
| `rvol >= 1.3` | 336 |
| `QQQ intraday <= -0.8%` | 342 |
| `clv >= -0.5` | 1559 |
| all three | **44** |

Execution is unchanged from the original: buy 100% TQQQ at the next open, hold
5 sessions, exit at the following open, otherwise 100% BIL. Overlapping events
extend the window. This produces **44 events / 36 entries** and **10.18%**
session exposure.

**Alignment:** the event is known at session *d*'s close and the weight is
placed on the last bar of *d*; the fill is the next session's open (*d+1*). The
exit is placed on the last bar of *d+5* and filled at the following open. No
2024+ bar is requested or read.

## 3. Development result

| Cost | CAGR | Max DD | Sharpe | Sortino | Fills | Turnover | TQQQ exposure | End equity |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 bp | **15.54%** | **29.40%** | **0.72** | 1.06 | 145 | 282× | 10.18% | $316,780 |
| 5 bp | 14.70% | 29.63% | 0.69 | 1.01 | 145 | 272× | 10.18% | $298,929 |
| 10 bp | 13.66% | 29.91% | 0.66 | 0.96 | 145 | 260× | 10.18% | $278,024 |

### Sub-periods and yearly path

| Period | CAGR | Max DD | Sharpe | TQQQ exposure |
|---|---:|---:|---:|---:|
| 2016-2019 | +9.84% | 29.40% | 0.54 | 11.49% |
| 2020-2021 | **+50.63%** | 21.66% | 1.45 | 14.70% |
| 2022-2023 | **−1.98%** | 25.42% | −0.01 | 3.00% |

Calendar-year strategy returns: 2016 +11.2%, 2017 +6.4%, 2018 +28.0%,
2019 −4.0%, **2020 +95.3%**, 2021 +16.0%, **2022 −8.4%**, 2023 +4.9%. The
result is concentrated in 2020 and the 2022-23 sub-period is negative. This is
a crash-contingent profile, not a stable participation effect.

## 4. Event study (44 events, open-to-open by hold)

| Horizon | n | Mean | Median | Win | t | Bootstrap p | Mean ex-top-5 | Excess vs 3×QQQ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| h3 | 44 | +2.68% | +3.74% | 65.9% | 2.07 | 0.017 | +0.90% | −0.058pp |
| h5 | 44 | **+3.21%** | +5.06% | 75.0% | **2.26** | 0.011 | +1.17% | −0.129pp |
| h10 | 44 | +3.08% | +6.73% | 68.2% | 1.61 | 0.051 | +0.78% | −0.322pp |

The h5 edge is real in the raw-return sense (bootstrap CI [+0.48%, +5.99%]),
but the **excess** return versus 3× QQQ is negative, and the edge weakens
sharply when the five best events are removed (+1.17%, versus +3.21%).
Most of the +3.21% is QQQ beta, not a TQQQ-specific supply-absorption effect.

## 5. Grid — the plateau is not where the hypothesis needs it

| # | Cell | Events | Entries | TQQQ exp. | CAGR | Max DD | Sharpe |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | **primary rvol1.3 / clv−0.50 / h5** | 44 | 36 | 10.18% | **15.54%** | 29.40% | 0.72 |
| 2 | rvol 1.2 | 50 | 42 | 11.67% | 12.02% | 43.29% | 0.52 |
| 3 | rvol 1.5 | 37 | 30 | 8.58% | 11.07% | 36.38% | 0.59 |
| 4 | clv −0.25 | 19 | 17 | 4.64% | **2.20%** | 27.12% | 0.21 |
| 5 | clv −0.75 | 79 | 54 | 16.81% | 11.05% | 41.74% | 0.48 |
| 6 | hold 3 | 44 | 39 | 6.39% | 14.94% | 27.00% | 0.81 |
| 7 | hold 10 | 44 | 34 | 19.01% | 11.21% | 43.88% | 0.50 |
| 8 | half size | 44 | 36 | 5.09% | 9.01% | 15.22% | 0.78 |

The **volume** direction is a plateau: 1.2/1.3/1.5× give 12.0/15.5/11.1% CAGR.
The **close-location** direction is not: −0.25/0.50/−0.75 give
2.2/15.5/11.0%. The primary is a spike at `clv >= -0.5`, not a plateau. The
stricter close (rvol1.3, clv−0.25) is only 19 events and 2.2% CAGR, while the
looser close adds 35 events but drops to 11.1% and raises the drawdown to 41.7%.
That is exactly the pattern the pre-registration said would falsify the
close-location repair.

## 6. Attribution — the decisive test

### Volume buckets, inside `QQQ <= -0.8% & clv >= -0.5`

| rvol bucket | n | Mean h5 | t |
|---|---:|---:|---:|
| < 1.0 | 17 | +4.35% | 1.77 |
| 1.0–1.2 | 11 | +2.80% | 0.78 |
| 1.2–1.5 | 13 | +1.47% | 0.58 |
| 1.5–2.0 | 21 | +4.13% | 1.73 |
| ≥ 2.0 | 16 | **+0.89%** | 0.44 |

There is no monotone participation effect; the highest-volume bucket is the
worst. The high-versus-low comparison is +3.21% (n=44) versus +2.46% (n=34),
a difference of **+0.76pp** with a one-sided bootstrap p of **0.36** and a 95%
CI of [−3.83pp, +5.21pp]. Volume is not statistically additive.

### The no-volume control dominates

The same `QQQ <= -0.8% & clv >= -0.5` rule **without any volume condition**:

| Rule | Events | Entries | Exposure | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|---:|---:|---:|
| Primary (with rvol ≥ 1.3) | 44 | 36 | 10.18% | 15.54% | 29.40% | 0.72 |
| No volume control | 78 | 65 | 18.28% | **23.13%** | 42.81% | **0.745** |

Adding the volume condition raises the CAGR *down* from 23.1% to 15.5% and the
Sharpe from 0.745 to 0.723. It buys a lower drawdown, not a participation
edge. The volume leg is not doing the work the hypothesis claims.

### The close-location sign is backwards

Within `QQQ <= -0.8%`, the forward 5-session TQQQ return by close location:

| clv bucket | n | Mean h5 | t |
|---|---:|---:|---:|
| < −0.8 (close at the low) | 145 | **+3.48%** | 3.97 |
| −0.8 … −0.5 | 118 | +0.39% | 0.39 |
| −0.5 … −0.25 | 45 | **+3.91%** | 2.62 |
| −0.25 … 0 | 28 | +1.95% | 1.13 |
| ≥ 0 (upper half, the original condition) | 6 | **+0.57%** | 0.11 |

The original hypothesis says the upper-half close is the absorbed-supply
signature. In this sample the upper-half bucket is the **weakest**; closing at
the low (a selling climax) is the strongest. The data support a different
mechanism — panic exhaustion, not absorption — and that is not the strategy
that was pre-registered.

## 7. Benchmarks, correlation, placebo

| Dev benchmark | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| Strategy (1 bp) | 15.54% | 29.40% | 0.72 |
| TQQQ buy-and-hold | 36.15% | 82.29% | 0.80 |
| QQQ buy-and-hold | 18.91% | 37.30% | 0.90 |
| BIL | 1.39% | 0.24% | 0.92 |
| 165-day QQQ SMA baseline *(reference only)* | 44.76% | 58.76% | 1.03 |

Daily-return correlation with the 165-day baseline is **0.336**. The placebo
(200 random same-size event sets, same hold and costs) has mean CAGR 4.48%,
95th percentile 15.21%, max 23.13%; the real 15.54% is at the **95.5th
percentile** (p = 0.045). That is barely above the pre-registered 95% bar; the
timing carries little information beyond a random five-session exposure.

## 8. Verdict — retire the participation hypothesis

Five of the seven checks in `result.json` pass (events ≥20; h5 mean >0 and
t ≥1.5; 10 bp CAGR > BIL; not a single-episode 2020-only result under the formal
definition; placebo ≥95th percentile). The two attribution checks need care;
the literal high-versus-low volume comparison is positive, so a weak reading of
check 3 would pass, but the stronger attribution test fails. Check 4 fails
unambiguously.

1. **`volume_attribution` is not established.** The literal pre-registered
   comparison is positive: high volume +3.21% (n=44) versus low volume +2.46%
   (n=34), a +0.76pp difference. But the one-sided bootstrap p is **0.36** and
   the 95% CI spans zero; the same decline/clv rule without volume has a
   slightly higher Sharpe (0.745 vs 0.723). The code therefore records the
   stronger attribution test (significant positive difference **and** an
   improvement over the no-volume control) as false. Volume is not proven to
   add; it mainly reduces exposure.
2. **`clv_plateau` fails unambiguously.** The close-location result is a spike
   at `clv >= -0.5` (2.2% / 15.5% / 11.0% at −0.25 / −0.50 / −0.75), and the
   original upper-half condition is the weakest bucket (+0.57% on 6 events).
   This is the decisive failure: the direction of the original close-location
   hypothesis is not supported.

The headline 15.54% CAGR is a real development-window return, but it is not
evidence of participation exhaustion. It is a **generic down-day close-off-low
reversal**, concentrated in 2020, with a negative 2022-23 sub-period and a
borderline placebo. Publishing it as a volume/orderflow strategy would be
dishonest. The specific `clv >= -0.5` neighbour was chosen from the count table
as the nearest relaxation of a nearly impossible condition; the grid shows it
is a spike, which is exactly why it is not accepted.

**Recommendation:** retire `volume-orderflow` as a participation strategy. If
the residual decline/close-off-low reversal is pursued, it must be pre-registered
as a separate hypothesis (selling-climax reversal), checked for collision with
the existing gap-capitulation / intraday mean-reversion family, and judged on
its own mechanism — not relabelled as orderflow.

No holdout was inspected; there is no frozen v2 to run on 2024-2026.

## 9. Reproduction

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
python research\new\volume-orderflow-v2\strategy.py
```

Writes `result.json` in this directory. All timings, fills and costs come from
`research/bt.py` (next-open fills, 2% band, 1/5/10 bp).

## Appendix — entry dates (36, actual fills at the next open)

2016-04-20, 2016-06-28, 2016-11-11, 2017-06-12, 2017-06-30, 2017-07-28,
2018-03-20, 2018-04-03, 2018-06-08, 2018-06-26, 2018-07-31, 2018-09-07,
2018-10-05, 2018-10-30, 2018-12-21, 2019-03-08, 2019-05-08, 2019-08-01,
2019-09-30, 2019-12-03, 2020-02-06, 2020-05-14, 2020-06-15, 2020-09-08,
2020-11-02, 2021-01-05, 2021-01-28, 2021-02-22, 2021-03-05, 2021-05-05,
2021-07-28, 2021-10-05, 2021-12-06, 2022-01-27, 2022-05-11, 2022-12-14.

The signal dates are one session earlier and are listed in `result.json`
(`diagnostics.event_dates`).
