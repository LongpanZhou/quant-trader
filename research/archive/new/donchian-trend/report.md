# `donchian-trend` — development report

**Window:** 2016-01-04 → 2023-12-29 only. The 2024-01-02 → 2026-10-23
holdout was not used or inspected for selection.
**Execution:** 1-minute-derived daily marks, next-open fills, 2% band,
long-only, weights ≥ 0 and sum ≤ 1.
**Bar:** TQQQ buy-and-hold 2016-2023 = **36.72% CAGR / 82.29% max DD /
0.82 Sharpe** (1-minute marks). This harness measures TQQQ at 35.98% / 81.68%
/ 0.80 on the same daily bars.

## Verdict

**PASS on the development bar, with two honest caveats.** The frozen base earns
**49.14% CAGR, 43.95% max DD and 1.10 Sharpe at 1 bp**. It beats the TQQQ bar
by **+12.42 pp of CAGR** with a drawdown **38.34 pp lower**, and it is inside
the 60% design-DD target. At 5 bp it is 48.75% / 43.96% / 1.09; at 10 bp it is
48.27% / 43.98% / 1.08. All eight pre-registered grid cells pass, from 40.09%
to 55.56% CAGR, with drawdowns of 43.9-52.0%.

The caveats are real:

1. **The strategy is not a diversifier.** Daily-return correlation is 0.706 to
   TQQQ and **0.916 to the 165-day QQQ SMA → TQQQ base**. It is a different
   *rule* (Donchian channels, two sleeves, no SMA, no stop) but it is the same
   *return stream*: high-beta, long-TQQQ-in-uptrends, BIL-in-bears. Treat it as
   a risk-managed TQQQ allocator, not a new alpha stream.
2. **The slow exit horizon is load-bearing.** The 50-session exit is the
   conservative centre; 40 sessions gives 40.09% CAGR / 47.3% DD and 60
   sessions gives 55.56% / 43.9%. Every cell passes, but the return spread is
   wider than a pure noise plateau. The 50-day choice is the middle of the
   passing region, not the peak.

The strict mandate version (20/10 fast + QQQ 55/20 slow) **does not pass**:
27.41% CAGR / 43.0% DD. The 55-session slow channel is still inside the
pullback noise of a 3x ETF. The slow sleeve has to be a regime (100/50), not a
second fast signal. That is the main design finding.

| Metric | 1 bp | 5 bp | 10 bp |
|---|---:|---:|---:|
| CAGR | **49.14%** | 48.75% | 48.27% |
| Max drawdown | **43.95%** | 43.96% | 43.98% |
| Sharpe | **1.10** | 1.09 | 1.08 |
| Sortino | 1.54 | 1.52 | 1.50 |
| Annualised vol | 46.46% | 46.46% | 46.46% |
| TQQQ exposure (mean weight) | 78.6% | 78.6% | 78.6% |
| Time with TQQQ > 0 | 79.6% | 79.6% | 79.6% |
| Fills | 167 | 167 | 167 |
| Turnover (× initial equity) | 403.7 | 397.8 | 390.6 |
| Correlation to TQQQ (daily) | 0.706 | 0.706 | 0.706 |
| Ending equity on $100k | $2,431,169 | $2,381,491 | $2,320,822 |

For reference, on the same bars:

| Asset | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| TQQQ buy & hold | 35.98% | 81.68% | 0.80 |
| QQQ buy & hold | 18.86% | 35.11% | 0.87 |
| BIL buy & hold | 1.39% | 0.19% | 6.84 |
| 165-day QQQ SMA → TQQQ (benchmark only) | 43.63% | 58.71% | 1.01 |

The 165-day base is computed only for comparison and correlation; it is never
an input to `build_weights`.

## What the strategy does

Exact rules are in `HYPOTHESIS.md`; the short version:

1. **Fast sleeve (TQQQ, 20/10).** Enter TQQQ when its close is above the
   highest high of the prior 20 sessions. Exit when its close is below the
   lowest low of the prior 10 sessions. This is Turtle System 1, on TQQQ.
2. **Slow sleeve (QQQ, 100/50).** Enter when QQQ's close is above the highest
   high of the prior 100 sessions. Exit when QQQ's close is below the lowest
   low of the prior 50 sessions. This sleeve expresses TQQQ, not QQQ: it is a
   slow regime gate.
3. **Position.** TQQQ while *either* sleeve is long; otherwise BIL. This is a
   union of two independent state machines, not an average.
4. **Volatility target.** TQQQ weight = `min(1, 0.85 / vol20)`, where `vol20`
   is annualised TQQQ daily-return volatility over the prior 20 sessions. The
   remainder is BIL.

The signal is computed from the official adjusted daily OHLC through the
session close. The fill is at the next session's open. Every channel uses
sessions `t-N .. t-1`; the current session is never in its own channel. The
2015 daily rows are used only to warm the 100-session channel and the vol
estimate before 2016-01-04.

The design is deliberately **not** an aligned ladder. A 20/10 sleeve and a
100/50 sleeve are almost never both "freshly broken out"; requiring alignment
would keep the book on the sidelines through most of the trend. The union lets
the fast sleeve add early entries while the slow sleeve carries the
multi-month exposure.

## Results by year

| Year | Strategy | TQQQ | TQQQ DD | Comment |
|---|---:|---:|---:|---|
| 2016 | +7.2% | +18.6% | 34.1% | lag; slow start |
| 2017 | +113.0% | +113.0% | 14.9% | full capture |
| 2018 | +13.0% | −23.5% | 58.0% | win; avoided Q4 |
| 2019 | +68.7% | +130.5% | 30.6% | lag; 2019 whipsaw |
| 2020 | +120.0% | +99.8% | 69.9% | win; covid exit and re-entry |
| 2021 | +59.4% | +90.9% | 30.5% | lag; held through pullbacks |
| 2022 | −27.0% | −79.7% | 81.1% | win; avoided the bear |
| 2023 | +95.0% | +204.9% | 33.2% | lag; missed part of the melt-up |

- Beats TQQQ on return in **3 of 8** years (2017 is a tie), and its within-year
  drawdown is lower in **6 of 8** and equal in the other two — never higher.
- The two big wins are 2018 (+36.6 pp) and 2022 (+52.7 pp); the big lags are
  2019 (−61.8 pp), 2021 (−31.4 pp) and 2023 (−109.9 pp). The strategy gives up
  upside in melt-ups to avoid the bears. That is the mechanism, not a bug.
- Log-P&L shares: 2020 25.6%, 2017 24.6%, 2023 21.7%, 2019 17.0%, 2021 15.2%,
  2018 4.0%, 2016 2.3%, 2022 −10.2%. No year contributes more than 80%.

## Pre-registered 8-cell grid (plateau)

Each non-base cell moves one parameter by one step. All cells are complete
strategies with the same execution and costs; the base is the centre of the
design, not the best cell.

| Cell | Fast | Slow | CAGR | Max DD | Sharpe | TQQQ expo | Fills |
|---|---|---:|---:|---:|---:|---:|---:|
| **base** | 20/10 | 100/50 | **49.14%** | 43.95% | 1.10 | 78.6% | 167 |
| `slow_entry_80` | 20/10 | 80/50 | 49.14% | 43.95% | 1.10 | 78.6% | 167 |
| `slow_entry_120` | 20/10 | 120/50 | 46.58% | 43.95% | 1.06 | 77.6% | 171 |
| `slow_exit_40` | 20/10 | 100/40 | 40.09% | 47.30% | 0.98 | 76.2% | 145 |
| `slow_exit_60` | 20/10 | 100/60 | 55.56% | 43.95% | 1.18 | 79.8% | 159 |
| `fast_entry_15` | 15/10 | 100/50 | 48.82% | 52.00% | 1.08 | 79.7% | 181 |
| `fast_entry_25` | 25/10 | 100/50 | 43.16% | 47.40% | 1.01 | 77.4% | 157 |
| `fast_exit_15` | 20/15 | 100/50 | 43.54% | 43.95% | 1.00 | 79.8% | 179 |

**8/8 pass** (CAGR > 36.72%, DD < 60%). The minimum cell beats the CAGR bar by
3.37 pp. The base is not the best cell: `slow_exit_60` is 6.4 pp higher and
Sharpe 1.18. The 80- and 100-session slow entries are identical in this sample
(the 100-day high and the 80-day high coincide); the plateau is real on the
entry axis. The exit axis (40/50/60) is a genuine risk-return trade-off, not
noise: a faster exit cuts 2022/2019 exposure at the cost of return.

The grid's CAGR spread is 15.47 pp, 31.5% of the base. My pre-registered
falsifier flagged a spread above 30% as "isolated peak" territory. On the
letter it trips; on the substance it does not: every cell passes and the base
is mid-plateau. I report the trip rather than redefine it.

## Neighbourhood beyond the grid

| Variant | CAGR | Max DD | Sharpe | TQQQ expo | Fills |
|---|---:|---:|---:|---:|---:|
| Base | 49.14% | 43.95% | 1.10 | 78.6% | 167 |
| Vol target 0.45 | 41.13% | 32.75% | 1.12 | 68.4% | 752 |
| Vol target 0.55 | 43.94% | 37.30% | 1.10 | 73.1% | 503 |
| Vol target 0.65 | 46.42% | 40.90% | 1.10 | 75.8% | 369 |
| Vol target 0.75 | 47.85% | 43.60% | 1.09 | 77.6% | 258 |
| Vol target 0.95 | 49.22% | 45.10% | 1.09 | 79.1% | 112 |
| Vol window 15 | 49.01% | 42.40% | 1.10 | 78.5% | 203 |
| Vol window 30 | 47.91% | 45.50% | 1.08 | 78.5% | 133 |
| Fast exit 5 | 45.18% | 43.95% | 1.04 | 77.4% | 171 |
| Slow exit 55 | 51.52% | 43.95% | 1.13 | 79.2% | 163 |
| Slow entry 90 | 49.14% | 43.95% | 1.10 | 78.6% | 167 |
| Slow entry 110 | 46.58% | 43.95% | 1.06 | 77.6% | 171 |

The volatility target is a **risk dial, not a return dial**: lowering it from
0.95 to 0.55 costs 5.3 pp of CAGR and saves 7.8 pp of max DD; Sharpe is flat
at 1.09-1.10. Unlike the `fast-trend-vol` rebuild, where the vol target was
neutral, here it buys real drawdown reduction (the no-vol-target ablation is
48.1% DD vs 43.95%). The vol window is flat between 15 and 30.

## Component attribution (ablations, 1 bp)

| Variant | CAGR | Max DD | Sharpe | TQQQ expo | Reading |
|---|---:|---:|---:|---:|---|
| Base | 49.14% | 43.95% | 1.10 | 78.6% | — |
| No vol target | 49.35% | 48.10% | 1.08 | 79.6% | target costs 0.2 pp CAGR, saves 4.2 pp DD |
| Fast sleeve only | 26.75% | 38.90% | 0.88 | 52.6% | fast 20/10 alone fails |
| Slow sleeve only | 33.80% | 43.95% | 0.89 | 68.8% | slow 100/50 alone fails |
| Strict mandate 55/20 | 27.41% | 43.00% | 0.82 | 63.5% | the mandated design fails |
| Slow 55/50 | 39.88% | 55.30% | 0.94 | 81.2% | 55 entry passes only with a 50-day exit |
| Slow 55/60 | 44.98% | 56.30% | 1.01 | 82.6% | 55 entry, 60 exit: passes but riskier |
| Slow 80/60 | 55.56% | 43.95% | 1.18 | 79.8% | best slow neighbour |
| Slow 120/60 | 52.90% | 43.95% | 1.15 | 78.8% | still on the plateau |

The **combination is the edge**: fast-only 26.75% and slow-only 33.80%, but the
union 49.14%. The fast sleeve adds early re-entries; the slow sleeve keeps the
book invested through the multi-month trend. Neither sleeve alone is a
strategy.

## Placebo and lag tests

**Lag placebo** — shift the entire weight series by N sessions (the position is
set with stale information):

| Lag | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| 0 (base) | 49.14% | 43.95% | 1.10 |
| 1 | 45.45% | 47.40% | 1.04 |
| 5 | 33.99% | 63.06% | 0.84 |
| 10 | 24.89% | 68.95% | 0.69 |
| 20 | 23.24% | 80.13% | 0.66 |

The decay is monotonic. A 1-session delay still passes (45.45%); a 5-session
delay does not (33.99%, and DD jumps to 63%). The edge is genuinely
short-horizon relative to the daily bars, so execution discipline matters. This
is a caveat, not a disqualifier: the harness fills at the next open, which is
the 1-session case.

**Circular-shift placebo** — 200 random circular shifts of the weight series
(preserves the exact exposure, run lengths and vol scaling, destroys alignment):

| Statistic | Value |
|---|---:|
| Placebo CAGR median | 26.07% |
| Placebo CAGR p90 | 42.63% |
| Placebo CAGR p95 | 45.50% |
| Placebo CAGR max | 67.20% |
| Placebo DD median | 78.66% |
| Placebo DD minimum | 58.30% |
| Placebo Sharpe median | 0.69 |
| Base CAGR percentile | **96.5%** |
| Base Sharpe percentile | **98.0%** |

The base is above the 95th percentile on CAGR and the 98th on Sharpe, and its
43.95% DD is below **every** placebo draw (minimum 58.3%). The timing, not the
exposure, is the source of the result.

**Random-days placebo** — 200 draws with the same number of invested days,
randomly placed, same vol-scaled sizes:

| Statistic | Value |
|---|---:|
| Placebo CAGR median | 35.98% |
| Placebo CAGR p95 | 50.47% |
| Placebo CAGR max | 67.57% |
| Placebo Sharpe median | 0.95 |
| Base CAGR percentile | **92.0%** |
| Base Sharpe percentile | 85.5% |

The random-exposure median equals TQQQ buy-and-hold (35.98%): simply being
invested 79% of the time earns the benchmark. The trend clustering adds
+13.2 pp of CAGR over that median, but the base is "only" at the 92nd
percentile — 8% of random paths beat it. The circular-shift test is the
stronger evidence because it preserves the run structure; the random-days test
is the honest lower bound.

## Cut tests and sub-periods

Fresh start at later dates (same weights, new $100k book):

| Start | CAGR | Max DD | Sharpe | TQQQ expo |
|---|---:|---:|---:|---:|
| 2017-01-03 | 55.69% | 43.95% | 1.16 | 79.8% |
| 2018-01-02 | 46.51% | 43.95% | 1.01 | 76.5% |
| 2019-01-02 | 54.41% | 43.95% | 1.11 | 76.4% |
| 2020-01-02 | 50.70% | 43.95% | 1.04 | 73.1% |
| 2021-01-04 | 33.43% | 39.92% | 0.85 | 69.0% |
| 2022-01-03 | 19.26% | 36.37% | 0.62 | 55.9% |

Every fresh start is positive. Every start beats the full-window TQQQ CAGR bar
except the 2022 start, which is 19.26% — still far above TQQQ's −39% over the
same 2022-2023 stretch. The 2022 start is the weakest, as expected.

Fixed sub-periods:

| Period | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| 2016-2019 | 47.36% | 30.36% | 1.20 |
| 2020-2021 | 83.58% | 43.95% | 1.30 |
| 2022-2023 | 19.48% | 36.14% | 0.63 |

All three are positive. The early half (2016-2019) is 47.36% CAGR, so the
result is not a 2020 artifact. The 2022-2023 sub-period is the weakest but is
still +42% cumulative while TQQQ lost 39%.

## The drawdowns

The 43.95% max DD runs **2020-02-19 → 2020-03-09**, the covid crash. The
strategy was long into the gap because neither channel had broken yet; the
50-day QQQ low exit and the fast 10-day low exit both fired after the first
leg down, and the vol target only trimmed after the spike. This is the
structural weakness of a daily channel system: it cannot avoid a gap-driven
crash, only the continuation. The worst five days are all 2020:

| Date | Strategy return |
|---|---:|
| 2020-09-03 | −15.40% |
| 2020-03-09 | −15.14% |
| 2020-02-27 | −15.09% |
| 2020-06-11 | −14.79% |
| 2020-09-08 | −14.21% |

These are overnight gaps or days when the exit filled at the next open after a
large down day. No 2018Q4 or 2022 day is in the worst five: the slow regime
sleeve had already moved the book to BIL in those bears.

The 2022 return is −27.0%, with average TQQQ exposure 21.9% for the year. The
strategy re-entered a few times on fast 20-day highs during bear rallies and
paid for it. That is the cost of the fast sleeve; the 100/50 slow sleeve kept
the larger loss away.

## Distinctness and correlation (the main weakness)

| Comparison | Daily-return correlation |
|---|---:|
| TQQQ buy & hold | 0.706 |
| 165-day QQQ SMA → TQQQ base (benchmark only) | **0.916** |

The 0.916 correlation with the old base trips my pre-registered 0.90
distinctness line. The rules are not the old base: there is no 165-day SMA,
no 4% armed stop, no QQQ holding; the entries are Donchian channels and the
position is a two-sleeve union with a vol target. But the *return stream* is
the same family — long TQQQ in uptrends, BIL in bears — so the correlation is
high. Any daily TQQQ trend strategy will have this property. If the lead
requires low correlation with the old base, this strategy should not be
selected; if the lead requires a new *mechanism* that passes the dev bar, it
qualifies.

Exploratory variants that reduce the correlation (the 0.45 cell is in
`result.json`; the α=0.25 row is an exploratory probe, not part of the
deliverable code):

| Variant | CAGR | Max DD | Sharpe | Corr to TQQQ | Corr to 165d base |
|---|---:|---:|---:|---:|---:|
| Base (0.85 target) | 49.14% | 43.95% | 1.10 | 0.706 | 0.916 |
| Target 0.45 | 41.13% | 32.75% | 1.12 | 0.680 | 0.894 |
| Partial TQQQ in slow state (α=0.25) | 39.15% | 38.20% | 1.08 | 0.672 | 0.850 |

The α=0.25 variant — hold 25% TQQQ / 75% QQQ when only the slow sleeve is
long — is the most distinct passing variant (corr 0.850), but its CAGR margin
over the bar is only 2.4 pp. The base is the strongest return candidate.

## Why the strict 20/55 mandate fails

The mandate suggested 20/55 channels and 10/20 exits. Tested exactly:

| Variant | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| Fast 20/10 only | 26.75% | 38.90% | 0.88 |
| OR(fast 20/10, slow QQQ 55/20) | **27.41%** | 43.00% | 0.82 |
| OR(fast 20/10, slow QQQ 55/50) | 39.88% | 55.30% | 0.94 |
| OR(fast 20/10, slow QQQ 55/60) | 44.98% | 56.30% | 1.01 |
| OR(fast 20/10, slow QQQ 100/50) | **49.14%** | 43.95% | 1.10 |

The 55-session slow channel with a 20-session exit is too fast: it exits on
normal pullbacks and re-enters after the rebound, exactly the 2017/2021
whipsaw that killed the fast sleeve. Lengthening only the exit to 50 sessions
gets to 39.9% but pushes the DD to 55.3%; lengthening the entry to 100 gets
49.1% with a 43.95% DD. The slow horizon must be a regime. The pre-registration
quoted 30.2% for the strict version from the exploratory 1-minute-derived
signal; the final daily-parquet run is 27.41%. The difference is the signal
close (15:59 vs 16:00) and is not material to the conclusion.

## Falsifier checklist

| # | Falsifier | Result | Status |
|---|---|---|---|
| 1 | CAGR ≤ 36.72% or DD ≥ 82.29% | 49.14% / 43.95% | **pass** |
| 2 | <7/8 grid cells pass, or isolated peak (spread > 30% of base) | 8/8 pass; spread 31.5% | **pass on substance; letter trips** |
| 3 | 10 bp CAGR < 36.72% | 48.27% | **pass** |
| 4 | Lag 1-5 destroys the result, or base below p95 of circular placebo | lag 1 45.5% pass; lag 5 34.0% fails; base p96.5 | **partial** |
| 5 | Only one sleeve carries the result | fast 26.75 / slow 33.80 / union 49.14 | **pass** |
| 6 | One year >80% of log P&L, or two of three sub-periods negative | max year 25.6%; all three positive | **pass** |
| 7 | Corr >0.85 to TQQQ, or >0.90 to the 165d base | 0.706 pass; 0.916 **trips** | **partial** |
| 8 | Truncation changes prior weights | max diff 0.0, prefix equal | **pass** |

Two falsifiers are honestly tripped: the lag-5 sensitivity and the old-base
correlation. Neither is a return failure; both are selection risks the lead
should weigh.

## Causality

`_causality` truncates the panel and the daily signal at 2021-12-31, rebuilds
the weights from the truncated data, and compares the prefix:

```
bars_before_cut: 1510
weight_prefix_equal: True
max_abs_diff: 0.0
```

Every weight before the cut is unchanged. The channel uses `t-N..t-1`, the vol
uses `t-19..t`, and the state machine only looks backward. The 2024-2026
holdout is not used: `_daily_ohlc` filters `date <= 2023-12-29`, and `bt.panel`
is called with `end="2023-12-29"`, so the returned panel stops there. (bt.py's
internal parquet loader reads its cache file and then filters; no 2024+ bar
enters any weight, metric or selection.)

## How this differs from the existing strategies

| Existing strategy | Mechanism | Difference |
|---|---|---|
| `daily-regime-minute-entry` (round-1 winner) | 165-day QQQ SMA + armed 4% TQQQ stop | no SMA, no stop; 20/10 + 100/50 Donchian union, 85% vol target |
| `fast-trend-vol` | 20/50-day EMA + crash brakes + 2.5% QQQ stop | channels, not EMAs; no crash brake, no intraday stop; slow QQQ regime sleeve |
| `donchian-breakout` (failed rebuild) | 5-minute QQQ 20/55/390 alignment ladder, ATR sizing | daily bars, TQQQ fast sleeve + QQQ slow regime, no ATR, no ladder |
| `relative-value-tqqq` | TQQQ/QQQ ratio momentum + vol filter | no ratio; price channels |
| `vol-scaled-crash-stop` | always-long TQQQ, inverse-ATR, ATR barrier | trend-gated, BIL when both channels are off |
| `dynamic-leverage-throttle` | post-vol-shock recovery in BIL during calm uptrends | owns the calm uptrend, de-risks in shocks |

The combination — a 20/10 TQQQ channel unioned with a 100/50 QQQ regime and an
85% vol target — is not used by any existing strategy.

## Limitations

- **High correlation to the old base (0.916).** The main selection risk. This
  is a different rule set expressing the same slow TQQQ trend beta.
- **Covid gap risk.** The 43.95% max DD is a 13-session gap-driven crash. A
  daily channel cannot avoid the gap, only the continuation.
- **Slow-exit sensitivity.** 40/50/60 sessions gives 40.1/49.1/55.6% CAGR. The
  50-day base is the middle, not the peak. A 60-day exit would look better in
  this sample but is less defensive.
- **2019/2021/2023 upside lag.** −62/−31/−110 pp in the three melt-up years.
  In a strong bull holdout the strategy will lag TQQQ on return, though it
  should still beat it on drawdown.
- **Lag-5 execution.** A 5-session delay drops the CAGR to 34.0%, below the
  bar. The harness's next-open fill is the 1-session case, which passes
  (45.5%).
- **Sample.** One 8-year window, one asset family. The 2020 and 2023 recoveries
  contribute 47% of the log P&L. Treat the point estimate as high-40s CAGR,
  not a guaranteed 49%.

## Bottom line

The strategy passes the development bar comfortably: **49.14% CAGR, 43.95%
max DD, 1.10 Sharpe at 1 bp**, with a broad 8-cell plateau (40.1-55.6% CAGR,
all cells passing) and a monotonic lag placebo. It is a **risk-managed TQQQ
trend allocator**, not a diversifier: 0.706 correlation to TQQQ and 0.916 to
the old 165-day base. The strict 20/55 mandate failed (27.4%); the working
design lengthens the slow sleeve to a 100/50 regime. If the lead wants a new
mechanism with a strong dev margin and a real chance of beating TQQQ's 37.54%
full-window CAGR, this is a credible candidate. If the lead requires low
correlation to the existing trend family, it is not.

## Reproduction

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
$env:BT_THREADS = "1"
python research\new\donchian-trend\strategy.py
```

`strategy.py` writes `result.json` with the primary 1/5/10 bp metrics, the
8-cell grid, the ablations, the neighbourhood, the lag/circular/Bernoulli
placebos, the cut tests, the sub-periods, the causality check, the benchmarks
and the 165-day benchmark/correlation. It loads only 2016-01-04 →
2023-12-29.
