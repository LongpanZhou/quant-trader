# Overnight-drift capture with a volatility / short-trend crash throttle

**Verdict: passes the stated development bar.**
Dev 2016-01-04..2023-12-29, 1-minute marks, next-open fills, 2% band:

| | CAGR | Max DD | Sharpe | Exposure | Fills |
|---|---:|---:|---:|---:|---:|
| **Strategy, 1 bp** | **44.29%** | **59.71%** | **1.12** | 76.6% | 745 |
| Strategy, 5 bp | 43.52% | 60.03% | 1.11 | 76.6% | 746 |
| Strategy, 10 bp | 42.56% | 60.44% | 1.09 | 76.6% | 746 |
| TQQQ buy & hold (local 1-min marks) | 36.15% | 82.29% | 0.80 | 100% | 1 |
| TQQQ bar from the brief | 36.72% | 82.29% | 0.82 | 100% | — |

Daily-return correlation to TQQQ: **0.868**. Turnover 632x initial equity
over 8 years (~79x/yr). Ending equity $1.87M from $100k at 1 bp.

The strategy beats the 36.72% CAGR bar by **+7.6 pp** and cuts max drawdown by
**22.6 pp**, with the drawdown just under the 60% "ideal" line. It still clears
the CAGR bar at 10 bp (42.56%). The drawdown is 2021-11-22 to 2022-12-28 —
the 2022 bear, not COVID.

---

## 1. What it is

Universe: QQQ (signal), TQQQ (position), cash. One decision per session at
15:58 ET, filled at the 15:59 open; the position is held through the overnight
block and the whole of the next session, and re-decided at the next 15:58.

```
q_k      = QQQ close of the 15:58 bar of session k
sigma_k  = annualised stdev of the last 10 completed QQQ daily log returns
sma20_k  = mean of q over the last 20 sessions including k
base_k   = min(1, 0.20 / sigma_k)
trend_k  = 1.0 if q_k >= sma20_k else 0.5
w_k      = base_k * trend_k
```

No 165-day (or any 100-250 day) moving average, no intraday stop, no BIL, no
closing-pressure signal, no gap-continuation selection. Idle weight is cash at
0%. The 20-day SMA, the 10-day vol and the 20% target are the only parameters.
The 2015 daily QQQ closes are used only to warm the indicators so the strategy
is live on 2016-01-04; nothing on or after 2024-01-01 is loaded.

## 2. Why the overnight framing is literal, and what it costs

The overnight block is real in this sample:

| Block, TQQQ | Mean | Annualised log contribution | Max DD of the block |
|---|---:|---:|---:|
| 15:59 open -> next 09:30 open | **+12.5 bp/night** | +19.8%/yr (unconditional, 1 bp) | 66.6% |
| 09:30 open -> 15:59 open | +10.0 bp/day | +14.0%/yr | — |
| Both, buy & hold | — | +36.2%/yr | 82.3% |

But the overnight block **alone cannot pass**: the unconditional
overnight-only portfolio compounds at **19.77%** with a 66.6% drawdown, because
it pays two fills a night and sits in cash for the day drift. Even with the
throttle applied it reaches only 24.07% / 47.67%. So the strategy carries a
24-hour position anchored at the close: it owns the overnight block every night
after warmup, keeps the day session attached, and uses the close decision to
size the whole exposure. This is the honest construction. A "night-only fund"
does not clear 36.72% on this data.

Attribution of the centre's log P&L (approximate, block-level):

| | Strategy | TQQQ B&H |
|---|---:|---:|
| Overnight contribution | **+28.9%/yr** | +25.9%/yr |
| Day contribution | +12.1%/yr | +8.0%/yr |
| Night share of total log P&L | **68.9%** | 74.9% |

The strategy earns *more* in the overnight block than buy & hold despite a
76.6% average exposure, because it is at 0.10-0.20 weight on the COVID gap
nights where B&H's compounding is destroyed. That is the crash filter doing its
job.

### The avoided bad nights

The ten worst TQQQ nights in the window cost **-80.5% in log terms** at full
exposure; at the strategy's weights they cost **-39.4%**. The four worst
(2020-03-13 -27.6%, 2020-03-06 -20.5%, 2020-03-11 -20.4%, 2020-03-17 -15.1%)
were held at 0.10-0.20 weight. One top-ten night, 2020-02-21, was held at full
weight; the filter is not clairvoyant.

The other side of the ledger: the 386 nights held below half weight returned
**+9.1 bp/night on average** — net positive. The filter is **not** a bad-night
predictor that dodges a negative-mean subset. It is a variance/drawdown
throttle: it gives up some positive high-vol nights to cut the left tail and
the quadratic volatility drag. That distinction is the main honest caveat.

## 3. Results

### Yearly returns

| Year | Strategy | TQQQ | Note |
|---|---:|---:|---|
| 2016 | +21.1% | +19.9% | warmup complete; roughly matched |
| 2017 | +79.6% | +114.5% | lags a melt-up |
| 2018 | -11.4% | -20.8% | +9.4 pp |
| 2019 | +109.0% | +148.2% | lags a melt-up |
| 2020 | +121.2% | +104.1% | +17.1 pp through COVID |
| 2021 | +52.0% | +81.1% | lags |
| 2022 | -51.0% | -79.4% | +28.4 pp |
| 2023 | +162.7% | +192.1% | lags a melt-up |

The pattern is what a de-risked position should look like: it wins 2016, 2018,
2020 and 2022, and gives up upside in the strong bull years (2017, 2019, 2021,
2023). The full-window CAGR advantage comes from compounding the smaller 2022
loss.

### Sub-periods

| Period | Strategy CAGR / DD | TQQQ CAGR / DD |
|---|---:|---:|
| 2016-2019 | 42.1% / 40.8% | 49.0% / 58.6% |
| 2020-2021 | 84.5% / 34.7% | 93.5% / 72.7% |
| 2022-2023 | +14.1% / 53.2% | -21.7% / 81.1% |

Read this honestly: the strategy **lags TQQQ on CAGR in both 2016-2019 and
2020-2021**, while cutting the drawdown by 18 pp and 38 pp respectively. The
full-window CAGR advantage comes from 2022-2023, where it makes +14.1% while
TQQQ loses 39.8% compounded. That is exactly what a crash filter is for, but it
means the CAGR edge is concentrated in the bear-market avoidance, not spread
evenly across the sample.

## 4. Pre-registered grid: the plateau

All 8 combinations, 1 bp. Bar: CAGR > 36.72%, DD < 82.29%.

| Vol target | Floor | CAGR | Max DD | Sharpe | Exposure |
|---:|---:|---:|---:|---:|---:|
| 0.15 | 0.30 | 38.18% | 47.22% | 1.14 | 65.3% |
| 0.15 | 0.50 | 38.66% | 50.93% | 1.11 | 70.0% |
| 0.20 | 0.30 | 43.07% | 54.96% | 1.15 | 71.0% |
| **0.20** | **0.50** | **44.29%** | **59.71%** | **1.12** | **76.6%** |
| 0.25 | 0.30 | 42.11% | 60.81% | 1.09 | 73.9% |
| 0.25 | 0.50 | 43.23% | 66.15% | 1.05 | 80.0% |
| 0.30 | 0.30 | 41.03% | 63.18% | 1.04 | 75.4% |
| 0.30 | 0.50 | 41.97% | 68.84% | 1.01 | 81.7% |

**8/8 clear both bars.** CAGR range 38.2-44.3% (all +1.5 to +7.6 pp over the
bar), DD range 47.2-68.8% (all 13.5-35.1 pp below the bar), Sharpe 1.01-1.15.
The surface is monotone and smooth: lower vol target → lower CAGR and lower DD;
higher floor → higher CAGR and higher DD. That is a real plateau, not a lucky
cell.

### Neighbour tests (robustness, not used to choose the centre)

| Variant | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| vol window 5 | 39.02% | 64.25% | 1.01 |
| vol window 20 | 43.08% | 59.27% | 1.11 |
| SMA 10 | 37.54% | 66.23% | 1.02 |
| SMA 50 | 36.57% | 56.83% | 0.96 |
| target 0.18 | 42.73% | 56.46% | 1.12 |
| target 0.22 | 44.24% | 62.66% | 1.10 |
| floor 0.35 | 43.52% | 55.81% | 1.15 |
| floor 0.65 | 44.60% | 63.71% | 1.08 |

All eight beat the DD bar. Seven of eight clear the CAGR bar; the 50-day SMA
lands at 36.57%, **0.15 pp short**. So the trend window is the one parameter
with a real edge: 10-20 days is the working range, 50 days is too slow. The
pre-registered centre uses 20 days. Report this as a plateau edge, not a clean
sweep.

## 5. Controls: is it just de-leveraging?

| Control | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| **Strategy** | **44.29%** | **59.71%** | **1.12** |
| Constant weight at the same 76.6% | 31.75% | 71.35% | 0.80 |
| Vol throttle only (floor 1.0) | 43.42% | 71.96% | 0.96 |
| Trend haircut only (no vol) | 40.48% | 69.48% | 0.95 |
| Overnight-only, unconditional | 19.77% | 66.56% | 0.65 |
| Overnight-only, throttled | 24.07% | 47.67% | 1.04 |
| TQQQ buy & hold | 36.15% | 82.29% | 0.80 |

This is the strongest evidence that the timing is not just lower exposure: a
constant 76.6% position earns 31.75% with a 71.4% DD, **12.5 pp less CAGR and
11.6 pp more DD** than the strategy. Both components contribute independently:
the vol throttle adds ~3 pp of CAGR over trend-only, and the trend haircut cuts
~12 pp of DD versus vol-only.

## 6. Placebo, cuts, causality

**Placebo (200 shuffles of the decision series, same weight distribution):**
real 44.29%, shuffle mean 28.22%, 95th percentile 42.42%, **p = 0.04**. The
timing beats 96% of random-timing draws, but this is marginal at the 5% level —
the shuffled distribution's mean is close to the constant-exposure control, as
it should be. Treat the timing edge as modest and the vol/trend *level* as the
main driver.

**Cut tests** (daily returns with one year removed):

| Cut | Strategy CAGR / DD | TQQQ ex-year CAGR / DD |
|---|---:|---:|
| ex-2020 | 35.22% / 58.35% | 27.84% / 81.68% |
| ex-2016 | 47.96% / 58.35% | 38.66% / 81.68% |
| ex-2023 | 32.21% / 58.35% | 21.49% / 81.68% |
| ex-2022 | 67.98% / 40.01% | 77.75% / 69.89% |

Excluding 2020 drops the absolute CAGR to 35.22%, **below the full-window
36.72% bar**, though it still beats TQQQ by 7.4 pp on the same cut. Excluding
2022 (a strategy win) it lags TQQQ, as expected. The result is not one year,
but the full-window number is helped by COVID and by 2022.

**Causality:** truncating the panel at 2022-01-03 leaves every prior weight
identical (`prior_weights_unchanged = true`). The signals use the 15:58 close
and fill at the 15:59 open; no same-day-close information is used for the
same-day intraday position.

**Bad-gap channel (tested, excluded):** skipping the night when the minimum
QQQ gap over the last 10 sessions is worse than -3% adds +0.87 pp of CAGR
(45.16%) but +1.45 pp of DD (61.16%), so the Calmar is slightly worse
(0.738 vs 0.742) and 86 extra fills. The third mechanism in the mandate does
not add value on top of the throttle. It is reported in `result.json`, not used.

## 7. How this differs from the existing work

| Existing | Difference |
|---|---|
| `revisit/time-of-day` (19.70% dev) | Selects a 15:58→10:01 block only after a *sold* close, holds ~30% of nights, exits at 10:01. This holds a continuous 24h-anchored position every night, has no closing-pressure signal, no 10:01 exit, and throttles size by vol/trend. |
| `revisit/overnight-crash-filter` (10.37% dev) | A selective night-continuation / day-reversal system with a 3-sigma gap budget and a 40% vol ceiling. This is an always-in overnight capture, no r_day sign condition, no gap-budget sizing, no QQQ day leg. |
| `revisit/vol-scaled-crash-stop` | An ATR-scaled 4%-capped stop on the old base. This has no stop and no 165-day gate. |
| `revisit/dynamic-leverage-throttle`, `vol-kelly-overlay` | Episodic entries after a vol shock. This is continuously invested and throttles exposure. |
| Round-1 winner (165-day SMA + 4% stop) | No 165-day SMA, no 4% stop, no BIL. 20-day SMA and continuous sizing. |
| `revisit/risk-parity-hrp` | No QQQ/TQQQ risk parity; one TQQQ position and cash. |

It is **not** a diversifier: correlation to TQQQ is 0.868 and to the old
165-day base it is **0.790**. It is a risk-managed way to hold the same
underlying, which is what the mandate's CAGR/DD bar asks for.

For reference, the forbidden 165-day QQQ SMA base scores **44.99% / 56.49% /
1.03 Sharpe** on this same window (correlation to TQQQ 0.70). My strategy is
0.7 pp lower CAGR and 3.2 pp higher DD than that base, but has a higher Sharpe
(1.12) and a different construction: a 20-day trend window, continuous
volatility sizing, no stop, no BIL, and the close-anchored overnight holding
period. The point is not that this dominates the old base — it is that it clears
the bar without the forbidden gate or stop, and with a different risk process.

## 8. Honest verdict

**Pass on the stated bar.** 44.29% vs 36.72%, 59.71% vs 82.29%, 1.12 vs 0.82
Sharpe, and the result survives 5 bp and 10 bp. The 8-point plateau, the
constant-exposure control and the causality check are the parts I trust most.

What I do **not** claim:

- It is not a market-neutral or diversifying strategy; it is TQQQ with a
  throttle.
- The filter is not a bad-night oracle. The nights it de-weights were net
  positive on average; the gain is variance and tail reduction, not a negative
  conditional mean. On the 10 worst nights it avoided ~41 pp of log loss, and
  that is where most of the drawdown improvement comes from.
- The timing edge is marginal in the placebo (p = 0.04), and the ex-2020 CAGR
  (35.2%) is below the absolute full-window bar. The full-window result depends
  on COVID and 2022 being in the sample.
- 2022 still loses 51%. This is a 3x product; it is not low-risk.
- The 50-day SMA neighbour lands 0.15 pp below the CAGR bar, so the trend
  window is a real choice, not a free parameter.

## 9. Reproduction

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
$env:BT_THREADS = "1"
python research\new\overnight-drift-filter\strategy.py
```

Outputs `result.json` in the same directory: dev 1/5/10 bp, benchmark, yearly,
sub-periods, the 8-point grid, neighbours, controls, attribution, placebo, cut
tests, gap-channel diagnostic and the causality flag.
