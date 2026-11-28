# Day-of-month — month-end five-session TQQQ overweight

**Development window only:** 2016-01-04 → 2023-12-29. The 2024-2026 holdout
was not loaded, inspected or used for selection.

**Verdict (short):** a dev pass at 1 bp and 5 bp. Hold a 60% TQQQ core and
raise TQQQ to 100% for the last five sessions of each calendar month; idle is
BIL. Dev 1 bp: **38.56% CAGR, 61.18% max DD, 0.93 Sharpe, 1,048 fills**,
versus TQQQ 36.15% / 82.29% / 0.80. At 5 bp: **37.40% / 61.50% / 0.92**, still
above the bar. At 10 bp: 35.92% / 61.99% / 0.89, below the return bar by
0.80 pp. The core-weight plateau is broad (45-80% all pass), but the five-session
event window is a local optimum: 3-4 and 6-7 sessions do not clear the CAGR
bar. This is a dev-only reserve, not a holdout claim.

---

## 1. Rules and decision clock

The only input is the session's rank inside its calendar month:

```
rank_k  = 1 + number of earlier sessions in the same calendar month
n_k     = number of sessions in that month
target_k = 1.00  if rank_k > n_k - 5
         = 0.60  otherwise
w_tqqq(k) = target_k
w_bil(k)  = 1 - target_k
```

| Item | Rule |
|---|---|
| Decision clock | target for session `k` known at the close of `k-1` |
| Fill | 09:30 open of `k`, next-open rule of `research/bt.py` |
| Core | TQQQ 60%, BIL 40% outside the event window |
| Event | TQQQ 100%, BIL 0% in the last 5 sessions of the month |
| Band | 2% rebalance band, harness default |
| Costs | 1 bp headline; 5 bp and 10 bp reported |
| Constraints | long only, weights >= 0, row sum <= 1 |

The month length and the session rank are calendar facts known in advance.
There is no trend, volatility, drawdown, opening-range, close-flow,
relative-strength or ML input. The core is a risk-budget implementation; the
seasonal claim is the *overweight* in the last five sessions.

## 2. Headline development result

| Cost | CAGR | Max DD | Sharpe | Sortino | Vol | TQQQ exposure | Fills | Turnover | Ending equity |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 bp | 38.84% | 61.10% | 0.94 | 1.33 | 46.7% | 69.5% | 1,048 | 850x | $1,367,000 |
| **1 bp** | **38.56%** | **61.18%** | **0.93** | **1.32** | **46.7%** | **69.5%** | **1,048** | **841x** | **$1,351,928** |
| 5 bp | 37.40% | 61.50% | 0.92 | 1.29 | 46.7% | 69.5% | 1,046 | 802x | $1,263,938 |
| 10 bp | 35.92% | 61.99% | 0.89 | 1.26 | 46.7% | 69.5% | 1,048 | 758x | $1,159,269 |

The task bar is 36.72% CAGR / 82.29% DD / 0.82 Sharpe. The 1 bp and 5 bp
results clear both. The 10 bp result clears the drawdown bar by 20.3 pp but is
0.80 pp short on CAGR. The drawdown is 21.1 pp lower than TQQQ at 1 bp.

### Benchmarks (same harness)

| Asset | CAGR | Max DD | Sharpe | Vol |
|---|---:|---:|---:|---:|
| TQQQ buy & hold | 36.15% | 82.29% | 0.80 | 66.5% |
| BIL | ~1.4% | ~0.2% | ~0.9 | ~1.5% |

The official brief bar (36.72% / 82.29% / 0.82) differs from the harness TQQQ
buy-and-hold (36.15% / 82.29% / 0.80) only by daily-close versus 1-minute
marking.

## 3. Activity

| Metric | Value |
|---|---:|
| Fills | 1,048 |
| Signal changes (session targets) | 192 |
| Event sessions | 480 (23.9%) |
| Core sessions | 1,532 (76.1%) |
| Mean TQQQ session exposure | 69.5% |
| Turnover at 1 bp | 841x |
| Round trips (event windows) | ~96 |

The activity floor is met: 1,048 fills and 192 independent target changes.
The low turnover (841x) is why the result survives 5 bp; the strategy trades
mainly at the two month boundaries and on 2%-band rebalances.

## 4. Pre-registered 8-cell core-weight grid

Window = last 5 sessions, event weight = 100%.

| Core TQQQ | CAGR | Max DD | Sharpe | Fills | Passes bar |
|---:|---:|---:|---:|---:|---|
| 45% | 36.98% | 50.36% | 0.98 | 1,052 | yes |
| 50% | 37.58% | 53.63% | 0.97 | 1,066 | yes |
| 55% | 38.06% | 57.64% | 0.95 | 1,052 | yes |
| **60%** | **38.56%** | **61.18%** | **0.93** | **1,048** | **yes** |
| 65% | 38.73% | 64.51% | 0.92 | 982 | yes |
| 70% | 38.55% | 67.86% | 0.90 | 864 | yes |
| 75% | 38.64% | 70.49% | 0.88 | 786 | yes |
| 80% | 38.42% | 73.04% | 0.86 | 674 | yes |

All eight cells clear 36.72% CAGR and 82.29% DD. The CAGR range is
36.98-38.73%, and the drawdown rises monotonically with the core. The 45-55%
cells are the risk-adjusted choice; the 60% centre is a balanced point with a
1.84 pp CAGR margin.

## 5. Event-window neighbours

Core = 60%, event weight = 100%.

| Event window | CAGR | Max DD | Sharpe | Fills |
|---:|---:|---:|---:|---:|
| Last 3 | 35.52% | 57.03% | 0.91 | 1,122 |
| Last 4 | 35.80% | 64.20% | 0.91 | 1,084 |
| **Last 5** | **38.56%** | **61.18%** | **0.93** | **1,048** |
| Last 6 | 30.12% | 64.06% | 0.79 | 1,010 |
| Last 7 | 32.79% | 67.55% | 0.82 | 970 |

This is the main overfit risk. The five-session window is a local optimum;
3-4 sessions are close but 0.8-1.0 pp below the CAGR bar, and 6-7 sessions are
materially worse. The 3-4 session variants have lower drawdowns (57-64%) and
similar Sharpe, so they are risk-adjusted alternatives, not return passers.
The five-session choice is pre-registered on the month-end flow mechanism, but
the reader should treat the 38.56% as a local estimate, not a plateau average.
The core-weight plateau (Section 4) is much broader than the window plateau.

## 6. Subperiods, yearly returns and drawdown

| Period | CAGR | Max DD |
|---|---:|---:|
| 2016-2019 | 39.96% | 35.34% |
| 2020-2021 | 75.13% | 54.86% |
| 2022-2023 | 5.41% | 59.83% |

The edge is present in both halves, though 2022-2023 is weak in CAGR (5.41%)
and still carries a 59.83% drawdown. 2016-2019 at 39.96% / 35.34% is the
cleanest evidence that the month-end tilt is not only a 2020-2021 artifact.

| Year | Strategy | TQQQ |
|---|---:|---:|
| 2016 | +18.03% | +19.86% |
| 2017 | +74.55% | +114.54% |
| 2018 | +1.33% | −20.76% |
| 2019 | +88.92% | +148.23% |
| 2020 | +103.47% | +104.14% |
| 2021 | +48.65% | +81.05% |
| 2022 | −55.58% | −79.39% |
| 2023 | +144.21% | +192.05% |

The maximum drawdown is **61.18%**, peak 2021-11-22 to trough 2022-10-13.
The strategy beats TQQQ's drawdown by 21.1 pp but lags the strongest melt-up
years (2017, 2019, 2021, 2023), which is the expected cost of holding only a
60% core outside the event window. 2018 and 2022 are the drawdown-protection
years.

## 7. Placebos

### Shifted-day windows

The event mask is shifted by ±5 and ±10 sessions. The event count and window
length are unchanged; only the alignment with month-end moves.

| Variant | CAGR | Max DD | Sharpe | Fills |
|---|---:|---:|---:|---:|
| Real last 5 | **38.56%** | 61.18% | 0.93 | 1,048 |
| Shift −10 | 27.28% | 74.36% | 0.74 | 1,006 |
| Shift −5 | 23.45% | 69.32% | 0.69 | 1,038 |
| Shift +5 | 29.04% | 72.00% | 0.78 | 1,021 |
| Shift +10 | 27.16% | 73.54% | 0.74 | 1,004 |

### Same-length wrong window

The first five sessions of the month are the same length but the wrong clock:
**29.04% CAGR / 72.00% DD / 0.78 Sharpe**. The last-five window is 9.5 pp
better in CAGR and 10.8 pp better in drawdown.

### Random blocks

300 random sets of 480 sessions (the event count), same 60/100 weights, daily
open-to-open approximation:

| Statistic | Value |
|---|---:|
| Real daily CAGR | 38.67% |
| Placebo mean | 29.55% |
| Placebo p95 | 37.85% |
| Placebo p99 | 43.63% |
| Placebo max | 46.97% |
| p-value (draws >= real) | **0.0333** |

The real window is above 96.7% of random same-size blocks. This is evidence
for the month-end alignment, not just for a high-exposure book.

## 8. Mechanism evidence

Forward capturable return = open of session `k` to open of `k+1`, the return a
target known at the prior close can actually earn.

| Bucket | n | Mean | Median | Win | t |
|---|---:|---:|---:|---:|---:|
| Last 5 sessions | 479 | **+48.2 bp** | +55.7 bp | 57.6% | **2.61** |
| Other sessions | 1,532 | +12.5 bp | +31.5 bp | 55.1% | 1.17 |
| Spread | | **+35.7 bp** | | | |
| First 5 sessions (placebo) | 480 | +19.8 bp | +26.8 bp | 55.8% | 0.99 |

The last-five mean is almost four times the rest-of-month mean, and the
first-five placebo is close to the unconditional mean. The effect is a
month-end effect, not a "beginning-of-month" effect.

## 9. Controls and decomposition

| Control | CAGR | Max DD | Sharpe | Fills |
|---|---:|---:|---:|---:|
| TQQQ buy & hold | 36.15% | 82.29% | 0.80 | 1 |
| Constant 69.5% TQQQ / 30.5% BIL | 30.43% | 67.39% | 0.81 | 666 |
| Pure event, no core | 27.52% | 35.62% | 0.96 | 383 |
| First 5 sessions, same length | 29.04% | 72.00% | 0.78 | 1,021 |

The constant mix with the same average TQQQ exposure earns 30.43%, so the
month-end timing adds 8.1 pp of CAGR at a lower drawdown. The pure event book
is a low-drawdown, low-return strategy (27.52% / 35.62%); the core is what
makes the return bar, and the event overweight is what makes the core
competitive. This decomposition is reported honestly: the family is a
core-plus-seasonal-tilt, not a pure five-day trade.

## 10. Correlation with the nine current winners

Daily strategy returns, dev slice only.

| Winner | Correlation |
|---|---:|
| `ratio-froth` | 0.595 |
| `vol-scaled-crash-stop` | 0.773 |
| `relative-value-tqqq` | 0.868 |
| `fomc-opex-window` | 0.647 |
| `family-session-timing` | 0.706 |
| `family-short-reversal` | 0.870 |
| `family-rebalance-flow` | 0.852 |
| `family-intraday-microstructure-day` | 0.600 |
| `family-ml-microstructure` | 0.848 |

Range **0.595-0.870**, mean 0.751. The highest are `family-short-reversal`
(0.870) and `relative-value-tqqq` (0.868), both below the 0.90 kill threshold
but close enough that the family should be described as a distinct *clock*
over a similar long-TQQQ exposure, not as an orthogonal return stream.

## 11. Causality

A truncation test rebuilds all weights from data ending 2022-01-03 and
compares every prior weight with the full-panel build:

```
truncation at 2022-01-03, compare through 2021-12-29
prior weights unchanged = True
```

The target for session `k` uses only the calendar rank of `k` and the month
length, both known before the session. The target is written at the prior
15:59 close and fills at the next open.

## 12. Kill criteria and verdict

| Test | Result |
|---|---|
| 1 bp CAGR > 36.72% | 38.56%, pass (+1.84 pp) |
| 1 bp max DD < 82.29% | 61.18%, pass (−21.11 pp) |
| Fills >= 100 | 1,048, pass |
| 5 bp still above bar | 37.40% / 61.50%, pass |
| Shifted/random placebo | all shifted windows 23.45-29.04%; random p=0.0333, pass |
| 2016-2019 and 2022-2023 positive | +39.96% / +5.41%, pass |
| Max winner correlation <= 0.90 | 0.870, pass |
| Event-window neighbours 3-7 positive | all positive CAGR, but 3/4/6/7 below bar |
| 10 bp above bar | 35.92%, **fail** |

**Verdict: PASS at 1 bp and 5 bp; FAIL at 10 bp on CAGR.** The core-weight
plateau is broad and the placebos are strong, but the five-session event
window is a local optimum. The reserve is best used with the 60% core and a
1-5 bp cost assumption; at 10 bp it is a lower-drawdown, slightly-below-bar
strategy rather than a pass.

## 13. Caveats

- The five-session window is a local optimum. 3-4 sessions are close but below
  the CAGR bar; 6-7 are worse.
- The strategy is a long TQQQ book 69.5% of the time; its 61.18% drawdown is
  high in absolute terms, and 2022-2023 is only +5.41% CAGR.
- The core-plus-overweight design means beta dominates; the seasonal timing
  adds 8.1 pp over a constant-exposure control, not a standalone 38% return.
- Correlations with `family-short-reversal` (0.870) and `relative-value-tqqq`
  (0.868) are high, though below the kill threshold.
- The 10 bp result is 0.80 pp below the CAGR bar. The strategy is not
  cost-insensitive.
- 1-minute data starts in 2016. The sample cannot test 2000/2008.
- No 2024-2026 data was loaded. The lead owns the one-shot holdout.

## 14. Reproduction

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
$env:BT_THREADS = "1"
python research/new/family-day-of-month/strategy.py
```

`strategy.py` regenerates `result.json` from the local 1-minute panel. All
numbers above are from that file or from the run log printed by the script.
