# Volume clock — 13:00 volume acceleration, overnight TQQQ

**Development window only:** 2016-01-04 → 2023-12-29. The 2024-2026 holdout
was not used in this analysis; the lead owns the one-shot holdout.

**Verdict (short):** a dev-only family candidate that **clears the TQQQ dev
bar at 1 bp on all three axes** — 37.25% CAGR, 21.87% max drawdown, 1.49
Sharpe, 594 entries / 1,188 fills. The volume-acceleration attribution is
strong and survives volatility controls and placebos. **But the CAGR edge over
TQQQ is only +0.53 pp at 1 bp, and costs erase it at 5 bp (29.32%).** The
durable improvement is risk: drawdown falls from 82.3% to 21.9% and Sharpe
rises from 0.82 to 1.49. The exact 13:00 sampling is a tuned choice and is the
main overfit risk. This is not a holdout claim.

---

## 1. Rules and decision clock

The strategy is an overnight TQQQ position gated by a **volume-acceleration
state** measured at 13:00 ET:

```
accel_k = sum(QQQ volume, 12:31..13:00, session k)
          --------------------------------------------------
          median over sessions k-20..k-1 of the same 30-minute sum
```

| Item | Rule |
|---|---|
| Decision clock | close of the 13:00 ET bar (offset 210 from 09:30); fill at 13:01 open |
| Volume window | 12:31-13:00 ET (30 one-minute QQQ bars) |
| Normalisation | prior-20 same-time-of-day median; strictly before session k |
| State | enter overnight long if `accel < 0.75`; exit if `accel > 0.85`; otherwise hold prior state (deadband) |
| Position | 100% TQQQ at 13:01, hold through 15:59, sell at next 09:30 open; cash otherwise |
| Costs / fills | next-open fills, 2% band, 1 bp headline plus 5/10 bp |
| Constraints | long only, weights ≥ 0, row sum ≤ 1 |

No daily trend SMA, volatility targeting, drawdown/capitulation event,
calendar window, opening range, closing-auction/rebalance-flow signal, or ML
classifier. The 13:00 clock is an intraday sampling time for the volume state,
not a day-level calendar rule. The BIL-flat variant is reported separately;
the headline uses cash because the BIL leg doubles the traded legs in the
shared simulator and is much more cost-sensitive.

## 2. Headline development result

| Cost | CAGR | Max DD | Sharpe | Sortino | Vol | Exposure | Fills | Turnover | Ending equity |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 bp | 39.31% | 21.48% | 1.56 | 2.53 | 23.07% | 13.6% | 1,188 | 4,945x | $1,410,995 |
| **1 bp** | **37.25%** | **21.87%** | **1.49** | **2.41** | **23.05%** | **13.6%** | **1,188** | **4,534x** | **$1,252,943** |
| 5 bp | 29.32% | 23.42% | 1.24 | 1.98 | 23.00% | 13.6% | 1,188 | 3,233x | $779,031 |
| 10 bp | 20.05% | 36.05% | 0.91 | 1.44 | 22.96% | 13.6% | 1,188 | 2,164x | $430,114 |

Daily-close marks (comparable to the task bar): **37.25% CAGR, 20.84% max DD,
1.47 Sharpe.** The task bar is 36.72% CAGR / 82.29% DD / 0.82 Sharpe. The
1 bp result clears all three, but the CAGR margin is 0.53 pp; at 5 bp the
strategy is below the bar on CAGR and above it on DD/Sharpe.

### Benchmarks (same harness)

| Asset | CAGR | Max DD | Sharpe | Vol |
|---|---:|---:|---:|---:|
| TQQQ | 36.15% | 82.29% | 0.80 | 66.55% |
| QQQ | 18.91% | 37.30% | 0.90 | 22.02% |
| BIL | 1.39% | 0.24% | 0.92 | 1.52% |

The brief's official TQQQ dev bar is 36.72% / 82.29% / 0.82; the harness
buy-and-hold is 36.15% / 82.29% / 0.80. The difference is daily-close versus
1-minute marking and is within rounding of the bar.

### BIL-flat variant

| Cost | CAGR | Max DD | Sharpe | Sortino | Fills | Turnover | Ending equity |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 bp | 36.68% | 22.28% | 1.47 | 2.38 | 2,377 | 8,687x | $1,211,731 |
| 5 bp | 21.33% | 34.81% | 0.96 | 1.51 | 2,377 | 4,496x | $468,251 |
| 10 bp | 4.55% | 57.17% | 0.31 | 0.47 | 2,377 | 2,179x | $142,666 |

BIL at 1 bp is 0.04 pp below the TQQQ CAGR bar and is essentially tied; at
5/10 bp it is materially worse than cash because every TQQQ entry/exit also
trades the BIL leg. The neutral state is therefore implemented as cash in the
headline; the BIL state is available and reported.

## 3. Activity

| Metric | Value |
|---|---:|
| Entries (TQQQ buys) | 594 |
| Fills (buys + sells) | 1,188 |
| Entries per year | 74.4 |
| Average holding period | 29.8 h (median 20.5 h, max 92.5 h) |
| TQQQ bar-time exposure | 13.6% |
| Overnight participation | ~29.5% of sessions |
| Turnover at 1 bp | 4,534x |

The activity floor is met with room: 594 entries and 1,188 fills over 8 years.
The median holding period is one overnight (20.5 h); the mean is pulled up by
weekends and holidays. The position is flat during the day.

## 4. Mechanism evidence

At 13:00 the acceleration state splits the overnight distribution sharply:

| Bucket | n | Mean overnight TQQQ | Median | t | Win |
|---|---:|---:|---:|---:|---:|
| `accel < 0.75` | 537 | **+41.4 bp** | +32.4 bp | 4.53 | 58.1% |
| deadband 0.75-0.85 | 193 | -4.0 bp | 0.0 bp | -0.23 | 50.8% |
| `accel > 0.85` | 1,246 | +0.2 bp | +18.9 bp | 0.02 | 56.2% |

Low minus high = **+41.2 bp per night**. The high-acceleration bucket has a
positive median but a near-zero mean: its left tail is the problem. The ten
worst overnight TQQQ returns in the sample all occurred after high-acceleration
days, including 2020-03-13 (-29.1%, accel 1.71), 2020-03-06 (-20.0%, accel
1.39), 2020-03-11 (-19.6%, accel 1.32), 2020-03-17 (-16.2%, accel 1.66), and
2020-09-04 (-11.9%, accel 4.81).

The acceleration effect is not a volatility proxy. Regressing the overnight
return on the `accel < 0.75` dummy, log realised 13:00 volatility, and the
absolute open-to-13:00 return:

| Term | Coefficient | t |
|---|---:|---:|
| constant | -1.7 bp | -0.03 |
| `accel < 0.75` | **+40.4 bp** | **3.07** |
| log realised vol | -1.0 bp | -0.07 |
| abs r_open | -462 bp per unit | -0.40 |

Realised volatility is insignificant once the acceleration state is included.
A double sort also survives: low-accel nights average +20.8 bp in low-vol
buckets and +23.8 bp in high-vol buckets; high-accel nights average +5.3 bp
and -3.8 bp respectively.

### The sign of the volume-weighted move

The secondary hypothesis — that the sign of the volume-weighted price move
predicts the overnight return — has standalone content but does not add to the
acceleration gate:

| Rule | CAGR | Max DD | Sharpe | Fills |
|---|---:|---:|---:|---:|
| VWAP deviation > -10 bp only | 40.40% | 46.29% | 1.08 | 2,758 |
| r_open > -20 bp only | 38.93% | 53.18% | 1.05 | 2,660 |
| `accel < 0.75` and VWAP > -10 bp | 28.31% | 21.21% | 1.43 | 924 |
| **`accel` state only (headline)** | **37.25%** | **21.87%** | **1.49** | **1,188** |

The sign alone earns a similar CAGR but with more than twice the drawdown.
Conditioning on both reduces CAGR to 28.3% while improving Sharpe only
marginally (1.43 vs 1.49). The acceleration state is the primary driver; the
sign is a secondary, correlated confirmation, not an independent edge. This is
reported as a partial result for the sign hypothesis, not a win.

### Volume attribution vs controls

| Control | CAGR | Max DD | Sharpe | Fills |
|---|---:|---:|---:|---:|
| All sessions, overnight TQQQ | 10.10% | 76.47% | 0.45 | 3,992 |
| Static `accel < 0.75`, no hysteresis | 36.01% | 21.93% | 1.51 | 1,074 |
| High-acceleration state only | -15.95% | 91.30% | -0.17 | 2,492 |
| TQQQ buy & hold | 36.15% | 82.29% | 0.80 | 1 |

The all-sessions overnight control earns 10.1% CAGR; the acceleration gate
adds 27 pp and cuts drawdown from 76% to 22%. The high-acceleration state
alone loses 16% CAGR. This is not just overnight beta.

## 5. Parameter plateau

### Pre-registered 8-cell grid

| Cell | Entries | 1 bp CAGR | 1 bp DD | 1 bp Sharpe | 5 bp CAGR |
|---|---:|---:|---:|---:|---:|
| 12:45, 0.75-0.85 | 634 | 22.20% | 42.67% | 0.93 | 14.68% |
| 13:00, 0.70-0.80 | 510 | 27.42% | 23.88% | 1.27 | 21.07% |
| **13:00, 0.75-0.85 (centre)** | **594** | **37.25%** | **21.87%** | **1.49** | **29.32%** |
| 13:00, 0.75-0.90 | 637 | 32.95% | 25.51% | 1.32 | 24.73% |
| 13:00, 0.80-0.90 | 716 | 35.83% | 32.64% | 1.32 | 26.43% |
| 13:00, 0.80-1.00 | 805 | 33.60% | 42.57% | 1.20 | 23.25% |
| 13:15, 0.75-0.85 | 632 | 25.98% | 27.85% | 1.14 | 18.25% |
| 13:30, 0.75-0.85 | 641 | 12.04% | 52.25% | 0.61 | 5.07% |

All eight cells are positive at 1 bp and 5 bp, so the "at least 6 of 8 positive"
criterion passes. The **threshold** plateau at 13:00 is broad: the five 13:00
cells span 27.4-37.3% CAGR and Sharpe 1.20-1.49. The **time** dimension is a
ridge with a peak, not a flat plateau: 12:45 = 22.2%, 13:00 = 37.3%,
13:15 = 26.0%, 13:30 = 12.0%. The 13:00 cell is 11-15 pp above its nearest time
neighbours. This is the main specification risk and is not hidden.

The broader 20-cell neighbour table (12:00-13:30 × four deadbands) spans
8.9-37.3% CAGR and 0.48-1.49 Sharpe; the 13:00 row is the best row. A 60-minute
window at 13:00 drops to 19.4-22.6% CAGR, a 90-minute composite (12:45/13:00/
13:15) reaches 33.9% CAGR with a 45.4% DD, and 3/5-day smoothing reaches
22.7-27.1%. The 30-minute window is the best expression; smoothing removes the
very urgency the mechanism is trying to measure.

## 6. Subperiods and yearly

| Period | CAGR | Max DD |
|---|---:|---:|
| 2016-2019 | 22.39% | 21.87% |
| 2020-2021 | 65.26% | 15.85% |
| 2022-2023 | 43.62% | 20.66% |

All three are positive. The 2020-2021 period dominates, but 2016-2019 and
2022-2023 are not dependent on it: excluding 2020 entirely gives 27.98% CAGR,
20.84% DD, 1.23 Sharpe. Excluding the ten best strategy days gives 22.04% CAGR,
20.84% DD, 1.08 Sharpe. The maximum drawdown is in 2016-03-04 → 2016-07-13
(21.87%), not in 2020, which is a useful sign that the risk control is not just
a COVID filter.

| Year | Strategy | TQQQ |
|---:|---:|---:|
| 2016 | +3.0% | +19.9% |
| 2017 | +24.6% | +114.5% |
| 2018 | -4.2% | -20.8% |
| 2019 | +82.2% | +148.2% |
| 2020 | +124.1% | +104.1% |
| 2021 | +19.9% | +81.1% |
| 2022 | +60.3% | -79.4% |
| 2023 | +28.0% | +192.0% |

2018 is the only negative calendar year. The strategy gives up a lot of the
strong TQQQ up-years (2017, 2019, 2023) and avoids the 2022 crash; the result
is a much smoother path, not a higher-return path.

## 7. Placebo and randomization

All placebos use the same state machine, thresholds and 1 bp cost.

| Test | Real | Placebo mean | Placebo p95 | Max | p-value |
|---|---:|---:|---:|---:|---:|
| Circular shift, 200 draws | 37.25% | 2.11% | 17.58% | 34.80% | 0.000 |
| Random nights, 200 draws (594 nights) | 37.25% | 3.53% | 18.39% | 26.40% | 0.000 |
| Random decision time, 100 draws (10:30-15:00) | 37.25% | 16.13% | 26.50% | 32.64% | 0.000 |
| Stale signal (prior session's accel) | 8.63% | — | — | — | retains 23% |

The circular-shift and random-night placebos are decisive: the real CAGR is
above the maximum of 200 draws. The random-time placebo is the honest
time-specificity test: the volume state works at many intraday times (mean
16.1% CAGR), but the 13:00 sampling is in the top 1% (max 32.6% < 37.25%).
The signal is timely: using yesterday's acceleration collapses CAGR to 8.6%
and raises drawdown to 50.2%.

Block bootstrap of daily returns (10-day blocks, 1,000 draws):

| Statistic | 5th pct | Median | 95th pct |
|---|---:|---:|---:|
| CAGR | 20.3% | 37.4% | 55.0% |
| Sharpe | 0.91 | 1.47 | 1.94 |
| Max DD | — | 22.6% | 33.4% |

## 8. Correlation with the current family winners

Daily-return correlation, development window:

| Winner | Correlation |
|---|---:|
| ratio-froth | +0.226 |
| vol-scaled-crash-stop | +0.366 |
| relative-value-tqqq | +0.307 |
| fomc-opex-window | +0.341 |
| family-session-timing | +0.402 |
| family-short-reversal | +0.337 |
| family-rebalance-flow | +0.324 |
| family-intraday-microstructure-day | +0.305 |
| family-ml-microstructure | +0.314 |
| overnight-drift-filter (not a required winner) | +0.397 |

Range vs the nine required winners: **+0.226 to +0.402**. The strategy is
low-beta to TQQQ (beta 0.138) with a significant daily alpha (10.69 bp/day,
30.9% annualised, t = 3.54) and a 0.399 daily correlation. It is not a clone of
any winner, though it shares the overnight/TQQQ exposure of session-timing and
overnight-drift.

## 9. Causality and implementation

- Truncating the panel at 2022-01-03 and rebuilding the weights reproduces
  every prior weight exactly (`max_abs_diff = 0.0`).
- Truncating mid-session at 2020-03-12 11:07 also reproduces every prior
  weight exactly.
- The 13:00 state uses only sessions k-20..k-1. No full-sample statistic.
- 2,006 of 2,012 sessions have offset 210 exactly at 13:00; six sessions with
  a missing morning bar land at 13:09-13:50, still causal. Half-days with
  fewer than 212 bars are skipped.
- The holdout adapter is the same `build_weights` on the full panel; it uses
  only information available at each 13:00 decision.

## 10. Kill criteria and verdict

| Criterion | Result |
|---|---|
| ≥ 100 fills / ≥ 30 entries | 1,188 fills / 594 entries — pass |
| Volume attribution: low > high, OLS t ≥ 2 | +41.2 bp; t = 3.07 — pass |
| Not a volatility proxy | log-vol t = -0.07; accel t = 3.07 — pass |
| Plateau: ≥ 6 of 8 positive | 8 of 8 positive — pass |
| All three subperiods positive | 22.4% / 65.3% / 43.6% — pass |
| 10 bp CAGR > BIL | 20.05% vs 1.39% — pass |
| Placebo p ≤ 0.10 | 0.000 for circular shift, random nights, random time — pass |
| Stale signal retains < 80% | 23% — pass |
| TQQQ bar at 1 bp | 37.25% / 21.87% / 1.49 vs 36.72% / 82.29% / 0.82 — pass |
| BIL variant within 1 pp of bar | 36.68% vs 36.72% — pass (0.04 pp below) |

**Verdict:** accept as a **dev-only family candidate**, with explicit caveats.
The mechanism is real in the development window: a midday volume burst predicts
a bad overnight tail, a volume drought predicts the normal overnight drift, and
the effect survives volatility controls and placebos. The strategy clears the
TQQQ dev bar at 1 bp on CAGR, drawdown and Sharpe, with 594 entries and 1,188
fills. But the CAGR edge is thin (+0.53 pp), it is below the bar at 5 bp
(29.32%), and the exact 13:00 sampling is the strongest cell in a time ridge.
The durable contribution is risk reduction, not return enhancement. The lead's
one-shot 2024-2026 holdout is the arbiter; this report does not claim it will
replicate.

## 11. Limitations

1. **Time specificity.** 13:00 is the peak; 12:45 and 13:15 retain 22-26% CAGR
   and 13:30 falls to 12.0%. The random-time placebo mean is 16.1% CAGR, so the
   volume state is not time-unique, but the exact minute is tuned. A holdout
   failure at 13:00 would not invalidate the volume mechanism, only this
   sampling.
2. **Thin CAGR margin.** 37.25% vs the 36.72% bar is 0.53 pp, well inside
   estimation noise. At 5 bp the CAGR is 29.32%. The honest claim is
   risk-adjusted improvement, not a CAGR win.
3. **BIL implementation.** BIL at 1 bp is 36.68% (0.04 pp below the bar) and
   much worse at 5/10 bp because the shared simulator charges the same
   slippage on the BIL leg. The cash headline is a cost-efficiency choice, not
   a claim that BIL is inferior as an asset.
4. **Overnight gap risk.** The position is 100% TQQQ overnight with no stop.
   The development max drawdown is 21.9%, but a future gap through a stop-free
   overnight could be worse. The 2020 tail is avoided by the state, not by a
   stop.
5. **Concentration in 2020 and a few days.** Ex-2020 CAGR is 28.0%; ex-top-10
   days is 22.0%. The strategy is not a one-year or one-day wonder, but both
   sensitivities are material.
6. **Single market, single asset.** QQQ/TQQQ only. No cross-asset or
   out-of-sample market validation.
7. **Turnover and capacity.** 4,534x at 1 bp; 594 round trips. The 10 bp CAGR
   is 20.05%. Capacity is not modelled.
8. **Data.** QQQ volume is the archive's consolidated share volume, not a full
   TAQ tape; odd-lot/off-exchange detail is absent. Six sessions have a
   missing morning bar; half-days are skipped.
9. **No holdout.** Every number here is development-window. The 2024-2026
   result is unknown and must be run once by the lead.

## 12. Files and reproduction

| File | Contents |
|---|---|
| `HYPOTHESIS.md` | pre-registration, mechanism, rules, falsifiers |
| `strategy.py` | runnable strategy and `result.json` generator |
| `result.json` | headline, grid, neighbours, controls, correlations, causality |
| `robustness.py` | placebo, bootstrap and ex-year tests |
| `robustness.json` | placebo/bootstrap output |
| `scratch/` | exploratory scripts from the screening sequence |

```powershell
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
$env:BT_THREADS = "1"
python research/new/family-volume-clock/strategy.py
python research/new/family-volume-clock/robustness.py
```

No 2024-2026 observation is used in any feature, weight, metric or table. The
shared loader reads the source parquet; the panel is sliced to 2023-12-29
before any computation. The `holdout.json` that may appear in this directory
belongs to the lead's one-shot run and was not opened for this report.
