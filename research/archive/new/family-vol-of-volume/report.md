# Volume-dispersion rotation — last-hour entropy, TQQQ / QQQ

**Development window only:** 2016-01-04 → 2023-12-29. The 2024-2026 holdout
was not loaded, inspected or used for selection.

**Verdict (short):** a dev pass at 1 bp and 5 bp. The centre holds TQQQ when
the entropy of the last hour's QQQ minute volume is below its prior-year 60th
percentile, and QQQ otherwise. Dev 1 bp: **46.85% CAGR, 70.49% max DD, 1.11
Sharpe, 1,371 fills**, versus TQQQ 36.15% / 82.29% / 0.80. At 5 bp it is
**37.11% / 73.36% / 0.95**, still above the bar on both return and drawdown.
At 10 bp it fails the return bar (25.83%). The 8-cell threshold plateau passes
in all eight cells; the 30-minute neighbour fails, so the construction is not
uniformly robust. This is a dev-only reserve, not a holdout claim.

---

## 1. Rules and decision clock

The primary object is the **dispersion of minute volume**, measured as the
Shannon entropy of the 1-minute QQQ volume shares over the closing hour:

```
p_i    = v_i / sum(v_i)                 for the 60 bars 15:00-15:59 ET
H_k    = -sum p_i log p_i / log(60)
rank_k = fraction of H_j <= H_k         for j in k-252 .. k-1
```

| Item | Rule |
|---|---|
| Decision clock | 15:59 ET close of session `k`; target written on that bar |
| Fill | 09:30 open of session `k+1`, next-open rule of `research/bt.py` |
| TQQQ weight | 1.0 if `rank_k < 0.60`, else 0.0 |
| Defensive weight | QQQ 1.0 when TQQQ is 0.0; always fully invested |
| Rank reference | prior 252 sessions, strictly before `k`; current value excluded |
| Warm-up | first 60 sessions hold QQQ; no signal |
| Costs | 1 bp headline; 5 bp and 10 bp reported |
| Band | 2% rebalance band, harness default |
| Constraints | long only, weights >= 0, row sum <= 1 |

The entropy is a *shape* object. It does not use the volume level, volume
acceleration, price trend, realised volatility, drawdown, opening range,
closing flow, relative strength or an ML model. QQQ is the defensive asset
rather than BIL so that the book keeps full equity exposure and the equity
drift; the signal only chooses the amplification.

## 2. Headline development result

| Cost | CAGR | Max DD | Sharpe | Sortino | Vol | TQQQ exposure | Fills | Turnover | Ending equity |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 bp | 49.40% | 69.73% | 1.15 | 1.63 | 42.9% | 58.2% | 1,371 | 12,722x | $2,466,185 |
| **1 bp** | **46.85%** | **70.49%** | **1.11** | **1.58** | **43.0%** | **58.2%** | **1,371** | **11,591x** | **$2,150,224** |
| 5 bp | 37.11% | 73.36% | 0.95 | 1.34 | 43.0% | 58.2% | 1,371 | 8,054x | $1,242,558 |
| 10 bp | 25.83% | 76.65% | 0.75 | 1.06 | 43.0% | 58.2% | 1,371 | 5,212x | $626,048 |

The task bar is 36.72% CAGR / 82.29% DD / 0.82 Sharpe. The 1 bp and 5 bp
results clear both the return and drawdown bars. The 10 bp result clears the
drawdown bar but not the return bar.

### Benchmarks (same harness)

| Asset | CAGR | Max DD | Sharpe | Vol |
|---|---:|---:|---:|---:|
| TQQQ buy & hold | 36.15% | 82.29% | 0.80 | 66.5% |
| QQQ buy & hold | 18.91% | 37.30% | 0.90 | 22.0% |

The official brief bar (36.72% / 82.29% / 0.82) differs from the harness TQQQ
buy-and-hold (36.15% / 82.29% / 0.80) only by daily-close versus 1-minute
marking. The strategy is compared with the official bar in the verdict.

## 3. Activity

| Metric | Value |
|---|---:|
| Fills | 1,371 |
| Signal changes (session targets) | 685 |
| TQQQ session exposure | 58.3% |
| QQQ session exposure | 41.7% |
| Mean TQQQ bar weight | 58.2% |
| Turnover at 1 bp | 11,591x |
| Entries into TQQQ (approx.) | 342 |

The activity floor is met with room: 1,371 fills and 685 independent target
changes. The strategy is not flat; it is fully invested in one of the two
equity legs at every bar.

## 4. Pre-registered 8-cell plateau

Only the rank threshold varies. Window = 60 minutes, lookback = 252 sessions.

| Rank threshold | CAGR | Max DD | Sharpe | TQQQ exposure | Fills | Passes bar |
|---:|---:|---:|---:|---:|---:|---|
| 0.40 | 38.77% | 66.11% | 1.08 | 40.5% | 1,399 | yes |
| 0.45 | 38.94% | 63.44% | 1.06 | 44.1% | 1,419 | yes |
| 0.50 | 42.22% | 68.57% | 1.09 | 50.1% | 1,363 | yes |
| 0.55 | 44.73% | 72.09% | 1.10 | 54.6% | 1,363 | yes |
| **0.60** | **46.85%** | **70.49%** | **1.11** | **58.2%** | **1,371** | **yes** |
| 0.65 | 42.71% | 74.46% | 1.02 | 62.7% | 1,251 | yes |
| 0.70 | 40.77% | 75.30% | 0.97 | 67.7% | 1,219 | yes |
| 0.75 | 41.34% | 71.78% | 0.95 | 72.6% | 1,083 | yes |

All eight cells clear 36.72% CAGR and 82.29% DD. The centre is not a single
lucky cell: the CAGR range is 38.77-46.85%, DD range 63.44-75.30%. The
threshold is a monotone exposure dial, not a narrow event trigger.

## 5. Neighbour checks

| Variant | CAGR | Max DD | Sharpe | Fills |
|---|---:|---:|---:|---:|
| Entropy 30 min | 27.49% | 83.85% | 0.78 | 1,415 |
| Entropy 45 min | 40.87% | 78.31% | 1.01 | 1,331 |
| **Entropy 60 min (centre)** | **46.85%** | **70.49%** | **1.11** | **1,371** |
| Entropy 90 min | 42.29% | 70.91% | 1.04 | 1,347 |
| Entropy 120 min | 46.29% | 72.28% | 1.11 | 1,359 |
| Rank lookback 126 | 42.32% | 74.91% | 1.02 | 1,459 |
| Rank lookback 252 | 46.85% | 70.49% | 1.11 | 1,371 |
| Rank lookback 504 | 44.90% | 61.04% | 1.12 | 1,319 |
| Continuous ramp 0.40→0.80 | 42.30% | 69.51% | 1.05 | 2,605 |

The 45-120 minute windows are all above the bar; the 30-minute window fails
the drawdown bar (83.85%). The rank lookbacks 126/252/504 are all above the
bar. The continuous ramp also passes, with a smoother exposure profile and
more fills. The 30-minute failure is reported honestly: very short windows are
noisier and the entropy estimate is less stable.

## 6. Subperiods, yearly returns and drawdown

| Period | CAGR | Max DD |
|---|---:|---:|
| 2016-2019 | 50.33% | 28.38% |
| 2020-2021 | 93.15% | 30.91% |
| 2022-2023 | 4.46% | 65.07% |

The edge is not only a 2020-2021 artifact: 2016-2019 is 50.33% CAGR with a
28.38% drawdown. 2022-2023 is weak in CAGR (4.46%) but still positive, and its
65.07% drawdown is below TQQQ's 81.10% for 2022. The 2022 drawdown is the
honest failure mode: the strategy is still a long 3x book on many days.

| Year | Strategy | TQQQ | 
|---|---:|---:|
| 2016 | +12.27% | +19.86% |
| 2017 | +59.64% | +114.54% |
| 2018 | +38.81% | −20.76% |
| 2019 | +101.68% | +148.23% |
| 2020 | +198.77% | +104.14% |
| 2021 | +23.29% | +81.05% |
| 2022 | −61.89% | −79.39% |
| 2023 | +180.14% | +192.05% |

The maximum drawdown is **70.49%**, peak 2021-11-22 to trough 2022-12-28. It
beats TQQQ's 82.29% but is not a low-risk profile. 2018 and 2020 are the years
where the entropy gate adds the most; 2017, 2021 and 2023 lag a pure TQQQ
melt-up, which is the expected cost of rotating to QQQ on diffuse-volume days.

## 7. Placebo

Circular shifts of the target series preserve the exact exposure, holding
lengths and turnover structure, but destroy the alignment with returns. 300
draws, daily open-to-open approximation (the real result is the 1-minute run):

| Statistic | Value |
|---|---:|
| Real daily CAGR | 49.64% |
| Placebo mean | 28.11% |
| Placebo p95 | 42.88% |
| Placebo p99 | 49.69% |
| Placebo max | 59.16% |
| p-value (draws >= real) | **0.0133** |

The real signal is above 98.7% of the shifted nulls. This is evidence that
the alignment, not just the exposure, carries the result. It is not a
multiple-testing correction for the whole research programme.

## 8. Mechanism evidence

Forward capturable return = open of session `k+1` to open of `k+2`, i.e. the
return a target written at the close of `k` can actually earn.

| Bucket | n | Mean TQQQ | Median | Win | t |
|---|---:|---:|---:|---:|---:|
| Low entropy rank (<0.60) | 1,171 | **+32.1 bp** | +32.5 bp | 55.7% | **3.25** |
| High entropy rank (>=0.60) | 777 | +5.6 bp | +42.7 bp | 55.9% | 0.31 |
| Spread | | **+26.5 bp** | | | |

The mean is the relevant statistic for a long-only book: the high-entropy
bucket has a positive median but a near-zero mean, i.e. a heavier left tail.
The same split on QQQ is +11.4 bp versus +3.0 bp; the effect is not only a
TQQQ-vol artifact.

Signal diagnostics:

- Entropy mean 0.895, std 0.048.
- Rank mean 0.490; q10 0.080, q50 0.490, q90 0.905.
- Correlation of rank with log total session volume: **+0.453**. The entropy
  shape is related to, but not identical with, the volume level.
- Correlation of rank with the same-day QQQ return: **−0.112**. The signal is
  not a restatement of the day's direction.

## 9. Controls and decomposition

| Control | CAGR | Max DD | Sharpe | Fills |
|---|---:|---:|---:|---:|
| TQQQ buy & hold | 36.15% | 82.29% | 0.80 | 1 |
| QQQ buy & hold | 18.91% | 37.30% | 0.90 | 1 |
| Constant 58.2% TQQQ / 41.8% QQQ | 31.98% | 68.41% | 0.82 | 448 |
| Volume-level gate, same design | 37.05% | 68.92% | 0.97 | 939 |

The constant mix with the same average TQQQ exposure earns 31.98%, so the
timing adds about 14.9 pp of CAGR at similar drawdown. The volume-level
control (rank of total-session volume, same threshold and assets) also passes
at 37.05%, which is a real caveat: part of the result is a generic
high-volume/low-volume rotation. The entropy shape adds about 9.8 pp of CAGR
over that control at 1 bp. The family is therefore distinct in construction
but not orthogonal to volume level.

## 10. Correlation with the nine current winners

Daily strategy returns, dev slice only.

| Winner | Correlation |
|---|---:|
| `ratio-froth` | 0.588 |
| `vol-scaled-crash-stop` | 0.784 |
| `relative-value-tqqq` | 0.824 |
| `fomc-opex-window` | 0.674 |
| `family-session-timing` | 0.674 |
| `family-short-reversal` | 0.762 |
| `family-rebalance-flow` | 0.827 |
| `family-intraday-microstructure-day` | 0.553 |
| `family-ml-microstructure` | 0.790 |

Range **0.553-0.827**, mean 0.720. The highest is `family-rebalance-flow` at
0.827, below the 0.90 kill threshold. The strategy is a long equity book most
of the time, so high correlations with other long TQQQ sleeves are expected;
the distinguishing object is the volume-dispersion clock, not a claim of
statistical independence.

## 11. Causality

A truncation test rebuilds all weights from data ending 2022-01-03 and
compares every prior weight with the full-panel build:

```
truncation at 2022-01-03, compare through 2021-12-29
prior weights unchanged = True
```

The entropy rank at session `k` uses sessions `k-252 .. k-1` only. The target
is written at 15:59 and fills at the next open. The first 60 sessions hold QQQ
because the rank is undefined, not because of a selected start date.

## 12. Kill criteria and verdict

| Test | Result |
|---|---|
| 1 bp CAGR > 36.72% | 46.85%, pass |
| 1 bp max DD < 82.29% | 70.49%, pass |
| Fills >= 100 | 1,371, pass |
| 5 bp still above bar | 37.11% / 73.36%, pass |
| Placebo p <= 0.10 | 0.0133, pass |
| 2016-2019 and 2022-2023 positive | +50.33% / +4.46%, pass |
| Max winner correlation <= 0.90 | 0.827, pass |
| Neighbours positive | 45-120 min and 126/252/504 lookback pass; 30 min fails DD |
| 10 bp above bar | 25.83%, **fail** |

**Verdict: PASS at 1 bp and 5 bp; FAIL at 10 bp on CAGR.** The result is a
genuine dev pass with a broad threshold plateau, a positive placebo, and a
plausible mechanism. It is not robust to a 30-minute entropy window and it is
cost-sensitive at 10 bp, so the reserve is best used at institutional costs
(1-5 bp), not as a high-turnover retail strategy.

## 13. Caveats

- The strategy is long TQQQ 58% of sessions. Its 70.49% drawdown is high in
  absolute terms; it is a lower-drawdown way to hold a 3x book, not a
  defensive product.
- The 2022-2023 subperiod is only +4.46% CAGR with a 65.07% drawdown.
- The volume-level control also passes, so the entropy shape is an
  improvement over volume level rather than a completely independent effect.
- The rank threshold is a selection parameter. The full 0.40-0.75 grid passes,
  but the centre 0.60 is the best cell; the honest expectation is the plateau
  average (about 42%), not the centre.
- 1-minute data starts in 2016. The sample cannot test 2000/2008.
- No 2024-2026 data was loaded. The lead owns the one-shot holdout.

## 14. Reproduction

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
$env:BT_THREADS = "1"
python research/new/family-vol-of-volume/strategy.py
```

`strategy.py` regenerates `result.json` from the local 1-minute panel. All
numbers above are from that file or from the run log printed by the script.
