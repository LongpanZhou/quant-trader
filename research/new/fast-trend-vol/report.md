# `fast-trend-vol` — development report

**Window:** 2016-01-04 → 2023-12-29 only. The 2024-01-02 → 2026-10-23
holdout was not loaded, inspected or used for selection.
**Execution:** 1-minute marks, next-open fills, 2% band, long-only,
weights ≥ 0 and sum ≤ 1.
**Bar:** TQQQ buy-and-hold, 2016-2023: **36.72% CAGR / 82.29% max DD /
0.82 Sharpe** (official 1-minute marks; this harness measures 36.15% / 82.29% /
0.80 on the same bars).

## Verdict

**PASS on the stated bar, with a serious whipsaw caveat.** The frozen base
earns **51.51% CAGR, 42.54% max DD and 1.20 Sharpe** at 1 bp on 1-minute
marks. It beats the TQQQ bar by **+14.79 pp of CAGR** with a drawdown
**39.75 pp lower**, and it is inside the 60% design-DD target. At 5 bp it is
49.70% / 43.00% / 1.17; at 10 bp it is 47.46% / 43.56% / 1.14. The 8-cell
pre-registered grid is a plateau (all 8 pass), and the 165-day QQQ SMA
baseline (benchmark only) is beaten on CAGR, drawdown and Sharpe.

The caveat is not cosmetic. The 42.54% max DD is a **2019 whipsaw**, and in
2019 the strategy returned +54.92% with a 42.54% DD while TQQQ returned
+148.23% with a 31.96% DD — worse on both return and drawdown. The full-period
pass is carried by the 2020 and 2023 recoveries and by avoiding 2022. This is
a crash-avoidance strategy that pays a large whipsaw cost in volatile bull
markets, not a uniformly superior TQQQ substitute.

The strategy is also **not** a low-correlation diversifier: daily-return
correlation to TQQQ is 0.666, because it carries a ~78% average TQQQ weight
and is long on ~80% of sessions. The edge is risk-managed TQQQ beta, not a new
return stream.

| Metric | 1 bp | 5 bp | 10 bp |
|---|---:|---:|---:|
| CAGR | **51.51%** | 49.70% | 47.46% |
| Max drawdown | **42.54%** | 43.00% | 43.56% |
| Sharpe | **1.20** | 1.17 | 1.14 |
| Sortino | 1.69 | 1.65 | 1.60 |
| Annualised vol | 42.19% | 42.18% | 42.18% |
| TQQQ exposure (mean weight) | 78.41% | 78.41% | 78.41% |
| Time in TQQQ | 79.75% | 79.75% | 79.75% |
| Fills | 374 | 374 | 370 |
| Turnover (× initial equity) | 1,765.0 | 1,652.2 | 1,521.0 |
| Correlation to TQQQ (daily) | 0.666 | 0.666 | 0.667 |
| Ending equity on $100k | $2,758,815 | $2,506,615 | $2,221,500 |

For reference, the same harness over the same bars:

| Asset | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| TQQQ buy & hold | 36.15% | 82.29% | 0.80 |
| QQQ buy & hold | 18.91% | 37.30% | 0.90 |
| BIL buy & hold | 1.39% | 0.24% | 0.92 |
| 165-day QQQ SMA → TQQQ (benchmark only) | 43.60% | 59.64% | 1.00 |

The 165-day baseline is computed only for comparison; it is never an input
to `build_weights`. The official revisit figure for that baseline is 44.76% /
58.76%; either measurement is below the candidate.

## What the strategy does

Exact rules are in `HYPOTHESIS.md`; the short version:

1. **Two-speed daily trend.** Enter TQQQ when QQQ's 15:59 close is above its
   20-day EMA. Exit when QQQ's 15:59 close is 2.5% below its 50-day EMA. The
   2.5% buffer is hysteresis; the 20-day entry is the fast leg, the 50-day
   exit is the slow leg. No 165-day (or 100–250-day) moving average is used.
2. **Volatility target.** TQQQ weight is multiplied by
   `min(1, 0.85 / vol20)`, where `vol20` is annualised TQQQ daily-return
   volatility over the prior 20 sessions. The remainder is BIL.
3. **Daily crash cooldown.** After a QQQ daily log return ≤ −3.5%, go to BIL
   at the next open and stay out for 5 sessions.
4. **Intraday QQQ crash brake.** While long, if QQQ's 1-minute close falls
   2.5% below the session open, exit at the next minute and stay BIL for the
   rest of the session and the night. Re-enter at the next open if the daily
   target is still on. This is a **QQQ** 2.5% stop, not the old **TQQQ** 4%
   stop; a 4% QQQ stop is too wide to matter (ablation below).

The signal uses each session's **15:59 1-minute close**, not the official
16:00 daily close, so the decision is made with the price actually known at
15:59. The daily parquet is used only for the pre-2016 EMA/volatility warmup.
The truncation check confirms every weight before 2020-12-31 is unchanged
when all later data is removed.

## Results by year

| Year | Strategy | TQQQ | TQQQ DD | Comment |
|---|---:|---:|---:|---|
| 2016 | +7.71% | +19.86% | 38.10% | lag; missed part of the post-Brexit recovery |
| 2017 | +120.86% | +114.54% | 15.97% | win |
| 2018 | −18.67% | −20.76% | 58.62% | win, but a difficult whipsaw year |
| 2019 | +54.92% | +148.23% | 31.96% | **whipsaw: 42.5% DD vs TQQQ's 32.0%; −93 pp return** |
| 2020 | +178.48% | +104.14% | 72.74% | win; crash brakes and April re-entry |
| 2021 | +53.82% | +81.05% | 32.84% | lag |
| 2022 | −28.80% | −79.39% | 81.10% | win; trend exit avoided the bear, but rallies hurt |
| 2023 | +177.17% | +192.05% | 34.93% | slight lag |

The profile is crash avoidance, not consistent alpha: the strategy beats TQQQ
in 4 of 8 years, but the 2020 win (+74.3 pp) and the 2022 win (+50.6 pp)
dominate. The 2019 lag (−93.3 pp) is the largest single-year opportunity cost,
and it came with a larger drawdown than TQQQ.

Log-P&L shares: 2020 31.7%, 2023 31.6%, 2017 24.5%, 2019 13.5%, 2021 13.3%,
2016 2.3%; 2018 −6.4%, 2022 −10.5%. No single year contributes more than 80%
of the total, but 2020 + 2023 contribute 63% and the result is clearly helped
by the two recovery years.

## Pre-registered 8-cell grid (plateau)

All cells are complete strategies with the same execution and costs; each
non-base cell moves one parameter by one step. The base is the centre of the
design, not the best cell.

| Cell | Entry | Buffer | Vol target | QQQ stop | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|---:|---:|---:|---:|
| **base** | 20 | 2.5% | 85% | 2.5% | **51.51%** | 42.54% | 1.20 |
| `buf_2.0` | 20 | 2.0% | 85% | 2.5% | 48.52% | 41.52% | 1.16 |
| `buf_3.0` | 20 | 3.0% | 85% | 2.5% | 52.85% | 43.13% | 1.21 |
| `entry_15` | 15 | 2.5% | 85% | 2.5% | 51.53% | 42.54% | 1.20 |
| `entry_25` | 25 | 2.5% | 85% | 2.5% | 50.69% | 40.91% | 1.19 |
| `tv_0.70` | 20 | 2.5% | 70% | 2.5% | 50.46% | 41.85% | 1.21 |
| `istop_2.0` | 20 | 2.5% | 85% | 2.0% | 52.12% | 47.30% | 1.22 |
| `istop_3.0` | 20 | 2.5% | 85% | 3.0% | 45.83% | 43.14% | 1.10 |

Every cell clears the bar (CAGR > 36.72%, DD < 82.29%) and every cell is
inside the 60% DD target. The base is not the best cell on CAGR
(`buf_3.0` 52.85%, `istop_2.0` 52.12%) or Sharpe (`istop_2.0` 1.22,
`buf_3.0`/`tv_0.70` 1.21); it is the centre of the plateau, not a peak. The
spread is 7.0 pp of CAGR and 6.4 pp of DD, which is a broad, usable
neighbourhood. The one soft spot is `istop_2.0`: more aggressive stops raise
CAGR to 52.1% but push the DD to 47.3%.

## Neighbourhood beyond the grid

One-step changes that were not part of the pre-registered 8:

| Variant | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| Base | 51.51% | 42.54% | 1.20 |
| Daily crash −3.0% | 47.17% | 41.52% | 1.14 |
| Daily crash −4.0% | 47.94% | 40.87% | 1.13 |
| Daily crash −4.5% | 47.96% | 40.83% | 1.13 |
| Exit EMA 40 | 42.53% | 50.89% | 1.06 |
| Exit EMA 60 | 51.35% | 41.52% | 1.19 |
| Vol window 15 | 50.81% | 42.46% | 1.19 |
| Vol window 30 | 51.19% | 42.59% | 1.20 |

The crash threshold and the vol window are flat. The 50-day exit is a plateau
between 40 and 60; EMA40 is the weak neighbour (42.5% / 50.9%) but still
passes. Nothing here is a knife-edge.

## Component attribution (ablations, 1 bp)

| Variant | CAGR | Max DD | Sharpe | Reading |
|---|---:|---:|---:|---|
| Base | 51.51% | 42.54% | 1.20 | — |
| No intraday QQQ stop | 45.26% | 44.64% | 1.09 | stop adds +6.3 pp CAGR, −2.1 pp DD |
| No daily crash cooldown | 48.25% | 40.83% | 1.13 | daily brake adds +3.3 pp CAGR but +1.7 pp DD |
| No crash brake at all | 42.86% | 44.33% | 1.02 | both brakes add +8.7 pp CAGR |
| No vol target | 53.35% | 42.59% | 1.20 | vol target costs 1.84 pp CAGR, saves 0.05 pp DD; Sharpe unchanged |
| Fast exit EMA20 | 43.98% | 50.42% | 1.08 | slow 50-day exit adds +7.5 pp CAGR |
| Slow entry EMA50 | 48.98% | 42.98% | 1.18 | fast 20-day entry adds +2.5 pp CAGR |
| Wide QQQ stop 4% | 45.29% | 44.64% | 1.09 | 4% QQQ is too wide; same as no stop |

The **trend legs are the main driver**: the slow exit and fast entry together
account for most of the return and the drawdown reduction. The crash brakes
add return but only a few points of drawdown, because the 42.5% max DD is a
2019 whipsaw, not a single crash. The **volatility target is a drag in this
sample**: without it the CAGR is 53.35% vs 51.51%, the DD is 42.59% vs 42.54%,
and the Sharpe is unchanged at 1.20. It costs 1.84 pp of CAGR and saves only
0.05 pp of DD. That is an honest negative on the vol target's contribution;
the mandate asked for a volatility target and it is included, but it is not
the source of the edge.

## Placebo and lag tests

**Lag placebo** — shift the entire daily target by N sessions:

| Lag | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| 0 (base) | 51.51% | 42.54% | 1.20 |
| 1 | 49.63% | 56.15% | 1.16 |
| 5 | 44.34% | 50.72% | 1.05 |
| 10 | 27.83% | 69.52% | 0.76 |
| 20 | 9.44% | 83.07% | 0.43 |

The monotonic decay is the strongest single piece of evidence that the timing
carries information. A 1–5 session delay is tolerable; 10–20 sessions is not.

**Shuffled-run placebo** — 30 random paths with the same number of on/off days
and the same run-length distribution, the same vol target, the same crash mask
and the same intraday QQQ stop:

| Statistic | Value |
|---|---:|
| Placebo CAGR median | 32.44% |
| Placebo CAGR p90 | 45.32% |
| Placebo CAGR max | 53.56% |
| Placebo DD median | 67.17% |
| Placebo DD minimum | 48.98% |
| Placebo Sharpe median | 0.855 |
| Placebo Sharpe max | 1.188 |
| Base CAGR percentile | 93.3% |
| Base Sharpe percentile | 100% |

The base is at the 93.3rd percentile on CAGR and above **every** placebo draw
on Sharpe (100th percentile); its 42.54% DD is below every placebo draw
(minimum 48.98%). One placebo draw has a slightly higher CAGR (53.56%) than
the base, so the return edge is not statistically unique with 30 draws. The
drawdown and Sharpe separation is much stronger: the timing mainly buys risk
control.

## Cut tests and sub-periods

Fresh start at later dates (same weights, new $100k book):

| Start | CAGR | Max DD | Sharpe | TQQQ exposure |
|---|---:|---:|---:|---:|
| 2017-01-03 | 58.69% | 42.54% | 1.30 | 77.4% |
| 2018-01-02 | 49.76% | 42.54% | 1.13 | 73.7% |
| 2019-01-02 | 69.23% | 42.54% | 1.38 | 74.3% |
| 2020-01-02 | 71.89% | 38.89% | 1.39 | 71.0% |
| 2021-01-04 | 45.88% | 38.89% | 1.06 | 70.2% |
| 2022-01-03 | 40.86% | 38.89% | 0.98 | 61.2% |

Every fresh start passes the bar, including the 2022 start at the top of the
bear market (40.86% CAGR / 38.89% DD). The 2022 start is the weakest, which is
expected; it still beats TQQQ's full-window 36.72% CAGR with less than half
the drawdown.

Fixed sub-periods:

| Period | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| 2016–2019 | 32.75% | 42.54% | 0.96 |
| 2020–2021 | 108.32% | 30.81% | 1.76 |
| 2022–2023 | 40.83% | 38.89% | 0.98 |

**Honesty caveat:** the 2016–2019 sub-period CAGR is 32.75%, below the
full-period 36.72% bar. The full-period pass is helped by the 2020–2021
recovery and 2023. The 2022–2023 sub-period is still 40.8% CAGR, so the result
is not purely a 2020 artifact, but the early half is the weaker evidence.
The 2019 whipsaw is the main reason the early half is weak.

## The 2019 whipsaw (the real failure mode)

The 42.54% max DD runs **2019-04-29 14:44 → 2019-10-03 10:08**. It is not a
crash drawdown; it is the cost of the fast entry and the crash brakes in a
volatile, range-bound bull market.

August 2019 daily illustration (strategy return, TQQQ return, daily target
weight for the session):

| Date | Strategy | TQQQ | Session target | What happened |
|---|---:|---:|---:|---|
| 2019-08-02 | −4.22% | −4.22% | 1.00 | long into the drop |
| 2019-08-05 | −10.85% | −10.85% | 1.00 | long into the crash |
| 2019-08-06 | +2.87% | +4.31% | 0.00 | sold at the open after the gap; missed the intraday rebound |
| 2019-08-08 | 0.00% | +6.90% | 0.00 | flat; missed the rebound |
| 2019-08-14 | −4.44% | −9.15% | 1.00 | re-entered into the next drop |
| 2019-08-23 | −9.52% | −9.25% | 1.00 | long into the next drop |
| 2019-08-26 | 0.00% | +4.19% | 0.00 | sold at the bottom; missed the rebound |

The pattern is classic whipsaw: sell the low, miss the rebound, re-enter before
the next drop. In 2019 the strategy returned +54.9% with a 42.5% DD while TQQQ
returned +148.2% with a 32.0% DD. A range-bound, high-volatility bull market is
the worst regime for this design. The 2018 loss (−18.7%) and the 2022 loss
(−28.8%) are smaller problems by comparison.

Worst five days:

| Date | Strategy return |
|---|---:|
| 2020-06-11 | −12.51% |
| 2016-06-24 | −12.17% |
| 2020-09-03 | −12.11% |
| 2020-02-24 | −11.64% |
| 2020-10-28 | −11.60% |

These are mostly overnight gaps or days when the intraday QQQ stop did not
trigger before the close. The strategy has no overnight gap protection; the
daily crash cooldown only acts at the next open. This is a structural
limitation, not a bug.

## Why it works, and where it could fail

**Why it works.** TQQQ's 82% drawdown is a multi-month bear-market phenomenon,
not a single-day phenomenon. The 50-day exit with a 2.5% buffer leaves 2018Q4,
2020 and 2022; the 20-day entry re-enters the recovery. The crash brakes cut
the first days of a shock and the 2.5% QQQ stop catches the intraday
continuation of a market-wide sell-off. The strategy retains a ~78% average
TQQQ weight and is long on ~80% of sessions, so it keeps most of the drift.

**Where it could fail.**

- **Whipsaw is the dominant risk, and 2019 is the proof.** The strategy sold
  the May and August 2019 lows, missed the rebounds, and re-entered before the
  next drop. It returned +54.9% vs TQQQ's +148.2% and had a 42.5% DD vs
  TQQQ's 32.0%. A choppy, high-volatility bull market is worse for this
  strategy than a clean bear market.
- **2020 V-recovery.** The 50-day exit is slow; the 20-day entry and the
  5-session cooldown can re-enter too late. The strategy still earned 178.5%
  in 2020, but part of that is the April–August trend, not the bottom.
- **Intraday stop at the low.** A 2.5% QQQ break can be a stop-run that
  reverses; the stop sells near the low and misses the rebound. The 34 stop
  events over 8 years are a small sample; the parameter is a round-number
  centre, not a fitted optimum.
- **Overnight gaps.** The largest losses are gap days. The daily cooldown
  cannot avoid the gap itself.
- **Costs.** 374 fills and 1,765× turnover. At 10 bp the CAGR is 47.46% —
  still a pass, but 4 pp below the 1 bp headline.
- **Concentration.** 2020 and 2023 contribute 63% of the log P&L, and the
  2016–2019 sub-period is below the bar. The point estimate should be treated
  as high-40s to low-50s CAGR, not a guaranteed 51.5%.

## How this differs from the existing strategies

| Existing strategy | Mechanism | Difference |
|---|---|---|
| `daily-regime-minute-entry` (round-1 winner) | 165-day QQQ SMA + armed 4% **TQQQ** stop | 20/50-day EMA, no 165-day SMA, **QQQ** 2.5% stop, 85% vol target |
| `vol-scaled-crash-stop` | always-long TQQQ, inverse-ATR size, ATR barrier | trend-gated; BIL when the trend is off |
| `dynamic-leverage-throttle` | episodic post-vol-shock recovery in BIL during calm uptrends | owns calm uptrends; de-risks in shocks |
| `dual-speed-regime` | 60-minute intraday EMA, flat overnight | daily decisions, holds overnight |
| `donchian-breakout` | 5-minute 20/55/390 alignment ladder, QQQ sleeve, ATR sizing | daily 20/50 EMA, TQQQ/BIL, vol target |
| `ratio-froth`, `ratio-pairs` | TQQQ/QQQ ratio signals | no ratio |
| `drawdown-regime` | post-drawdown recovery windows | continuous trend state |

The combination — daily 20/50 EMA, 85% vol target, QQQ 2.5% intraday stop,
−3.5%/5 daily crash cooldown — is not used by any existing strategy. The
strategy also deliberately avoids the old 4% TQQQ stop: a 4% **QQQ** stop is
too wide (ablation 45.29% / 44.64%, essentially the no-stop result), so the
2.5% QQQ threshold is doing real work and is not a re-skin of the old winner.

## Falsifier checklist

| # | Falsifier | Result | Status |
|---|---|---|---|
| 1 | CAGR ≤ 36.72% or DD ≥ 82.29% | 51.51% / 42.54% | **pass** |
| 2 | Fewer than 6/8 grid cells pass, or isolated peak | 8/8 pass; base not the best cell | **pass** |
| 3 | 10 bp CAGR ≤ 36.72% | 47.46% | **pass** |
| 4 | Lag/placebo matches the base | lag 10/20 collapse; base 93rd pct CAGR, 100th pct Sharpe; one placebo CAGR higher | **mostly pass** |
| 5 | One year >80% of P&L, or both halves negative | no year >80%; 2016–2019 +32.7%, 2022–2023 +40.8% | **pass, with early-half caveat** |
| 6 | 165-day baseline beats it on CAGR and DD | 43.60% / 59.64% vs 51.51% / 42.54% | **pass** |
| 7 | Core without the intraday stop ≤ 36.72% | 45.26% | **pass** (stop is not the only source) |
| 8 | Truncation changes prior weights | daily max diff 0.0; 1m prefix identical | **pass** |

## Reproduction

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
$env:BT_THREADS = "1"
python research\new\fast-trend-vol\strategy.py
```

`strategy.py` writes `result.json` with the primary 1/5/10 bp metrics, the
8-cell grid, the ablations, the extra neighbourhood, the lag and shuffled-run
placebos, the cut tests, the sub-periods, the 165-day benchmark and the
causality check. It uses the 1-minute panel's 15:59 closes for the daily
signal (plus the daily parquet only for pre-2016 warmup) and truncates every
input at 2023-12-29; the holdout is never touched.

## Bottom line

The strategy passes the stated development bar comfortably:
**51.51% CAGR, 42.54% max DD, 1.20 Sharpe at 1 bp**, with a broad 8-cell
plateau and a monotonic lag placebo. The honest caveats are that the edge is
concentrated in 2020–2021 and 2023, the 2016–2019 sub-period is below the
full-period bar, the 2019 whipsaw produced a 42.5% drawdown (worse than TQQQ's
32.0% that year), and the volatility target is close to neutral. It is a
risk-managed TQQQ allocator with a real crash-avoidance edge, not a
low-correlation alpha stream and not a uniformly better TQQQ.
