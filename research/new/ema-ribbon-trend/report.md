# `ema-ribbon-trend` - development report

**Window:** 2016-01-04 -> 2023-12-29 only. The 2024-01-02 -> 2026-10-23
holdout was not loaded, inspected or used for selection.
**Execution:** 1-minute marks, next-open fills, 2% band, long-only,
weights >= 0 and sum <= 1.
**Bar:** TQQQ buy-and-hold, 2016-2023: **36.72% CAGR / 82.29% max DD /
0.82 Sharpe** (official 1-minute marks; this harness measures 36.15% / 82.29% /
0.80 on the same bars).

## Verdict

**PASS on the stated bar, with real path dependence and a weak 2022-2023.**
The frozen base earns **46.77% CAGR, 44.13% max DD and 1.09 Sharpe** at 1 bp on
1-minute marks. It beats the TQQQ bar by **+10.05 pp of CAGR** with a
drawdown **38.16 pp lower**, and it is inside the 60% design-DD target. At
5 bp it is 46.14% / 44.14% / 1.08; at 10 bp it is 45.35% / 44.16% / 1.06. All
8 pre-registered grid cells pass, and the 165-day QQQ SMA baseline
(benchmark only, never an input) is beaten on CAGR, drawdown and Sharpe.

The caveats are material:

- **2022-2023 is the weak stretch:** 17.33% CAGR / 38.48% DD / 0.64 Sharpe
  over the last two development years. The full-period pass is helped by
  2020-2021 (103.16% CAGR) and by avoiding most of 2022.
- **2022 is -30.31%.** The ribbon was still stacked entering January 2022 and
  exited on 19 January, after TQQQ had already fallen about a quarter. The
  QQQ repair tier was then long during the March-April and August bear
  rallies.
- **2019 is the worst risk-adjusted year:** +38.85% versus TQQQ's +148.2%,
  with a 36.18% intra-year drawdown versus TQQQ's 32.0%. The June 2019 exit
  is the remaining whipsaw the buffer did not remove.
- **The base is the highest-CAGR cell of the buffer dimension** (46.77%,
  versus 45.57% at a 2.0% buffer). The buffer curve is a plateau from 0.3% to
  2.0% (40.78-46.77%), but individual years move by tens of points when the
  exit date moves by two days. This is path dependence, not a knife-edge fit.
- **A 1-session lag is slightly better** (47.78% CAGR), because it delays the
  January 2022 exit by one more day and captures the 20 January rebound. The
  exact day is not sharply identified; the 5/10/20-session lags decay
  monotonically.
- **Two of 30 shuffled-run placebos beat the base on CAGR** (50.70% and
  47.68% versus 46.77%). The drawdown and Sharpe separation is much stronger:
  the base is below all 30 placebo drawdowns and above all but one Sharpe.

| Metric | 1 bp | 5 bp | 10 bp |
|---|---:|---:|---:|
| CAGR | **46.77%** | 46.14% | 45.35% |
| Max drawdown | **44.13%** | 44.14% | 44.16% |
| Sharpe | **1.09** | 1.08 | 1.06 |
| Sortino | 1.53 | 1.51 | 1.49 |
| Annualised vol | 44.70% | 44.70% | 44.70% |
| TQQQ exposure (mean weight) | 73.63% | 73.63% | 73.63% |
| Time in TQQQ | 74.14% | 74.14% | 74.14% |
| Time in QQQ | 7.13% | 7.13% | 7.13% |
| Mean BIL weight | 19.19% | 19.19% | 19.19% |
| Fills | 164 | 164 | 164 |
| Turnover (x initial equity) | 682.2 | 666.0 | 646.3 |
| Correlation to TQQQ (daily) | 0.698 | 0.698 | 0.698 |
| Ending equity on $100k | $2,140,291 | $2,067,617 | $1,980,236 |

For reference, the same harness over the same bars:

| Asset | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| TQQQ buy & hold | 36.15% | 82.29% | 0.80 |
| QQQ buy & hold | 18.91% | 37.30% | 0.90 |
| BIL buy & hold | 1.39% | 0.24% | 0.92 |
| 165-day QQQ SMA -> TQQQ (benchmark only) | 43.61% | 59.64% | 1.00 |

The 165-day baseline is computed only for comparison; it is never an input to
`build_weights`. The candidate beats it by +3.16 pp CAGR and -15.51 pp DD.

## What the strategy does

Exact rules are in `HYPOTHESIS.md`; the short version:

1. **Ribbon state.** Compute QQQ's 20-, 50- and 100-session EMAs from the
   15:59 close. Enter TQQQ when `EMA20 > EMA50 > EMA100`. Leave only when
   `EMA20 < 0.995 * EMA50` - a 0.5% Schmitt trigger, not a daily line test.
2. **QQQ middle tier.** When the stack is off but QQQ is above its 100-day
   EMA, hold QQQ. Below the 100-day EMA, hold BIL.
3. **Volatility target.** TQQQ weight is `min(1, 0.85 / vol20_tqqq)`; the
   QQQ sleeve is `min(1, 0.85 / vol20_qqq)`. The residual is BIL.
4. **Execution.** The target set at the 15:59 close fills at the next
   session's open. No intraday override, no event brake, no stop, no 165-day
   SMA.

The state machine changes state about 1.75 times per year (14 transitions in
8 years), and the book trades 164 times in 8 years. The 100-day EMA is an
entry gate and the anchor of the QQQ tier; it is deliberately **not** a hard
exit. Making it a hard exit is the worst ablation below.

## Results by year

| Year | Strategy | Strategy intra-year DD | TQQQ | TQQQ DD | Comment |
|---|---:|---:|---:|---:|---|
| 2016 | +9.86% | -29.49% | +19.9% | -38.1% | lag; exited the January crash late, re-entered in April |
| 2017 | +114.54% | -15.97% | +114.5% | -16.0% | essentially TQQQ, full year |
| 2018 | +7.33% | -33.27% | -20.8% | -58.6% | win; left in April and October |
| 2019 | +38.85% | -36.18% | +148.2% | -32.0% | **whipsaw: -109 pp return, worse DD than TQQQ** |
| 2020 | +125.22% | -44.13% | +104.1% | -72.7% | win; crash loss, then re-entered 30 April |
| 2021 | +80.90% | -32.84% | +81.1% | -32.8% | essentially TQQQ |
| 2022 | -30.31% | -31.62% | -79.4% | -81.1% | win, but the January exit was late |
| 2023 | +97.08% | -28.75% | +192.0% | -34.9% | lag; the October pullback broke the stack |

The profile is crash avoidance plus two near-perfect trend years (2017,
2021), not consistent alpha. The strategy beats TQQQ on return in 2016,
2017 (a tie), 2018, 2020 and 2022; it loses badly in the V-shaped 2019 and
2023.

Log-P&L shares: 2020 27.3%, 2017 25.6%, 2023 22.8%, 2021 19.9%, 2019 11.0%,
2016 3.2%, 2018 2.4%; 2022 -12.1%. No year contributes more than 80% of the
total. 2020 + 2023 contribute 50.0%, so the result is helped by the two
recovery years but is not carried by a single one.

## Pre-registered 8-cell grid (plateau)

All cells are complete strategies with the same execution and costs; each
non-base cell moves one parameter by one step. The base is the centre of the
design, not the best cell found by a search.

| Cell | Fast | Buffer | Vol target | CAGR | Max DD | Sharpe | TQQQ expo | QQQ time | Fills |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **base** | 20 | 0.5% | 85% | **46.77%** | 44.13% | 1.086 | 73.6% | 7.1% | 164 |
| `buf_0.3` | 20 | 0.3% | 85% | 40.78% | 44.13% | 0.996 | 72.4% | 7.9% | 188 |
| `buf_1.0` | 20 | 1.0% | 85% | 43.71% | 52.97% | 1.020 | 76.7% | 5.2% | 164 |
| `buf_2.0` | 20 | 2.0% | 85% | 45.57% | 51.71% | 1.031 | 77.7% | 4.9% | 174 |
| `entry_15` | 15 | 0.5% | 85% | 39.51% | 44.80% | 0.982 | 71.9% | 8.1% | 192 |
| `entry_25` | 25 | 0.5% | 85% | 45.84% | 52.97% | 1.054 | 76.5% | 5.2% | 164 |
| `tv_0.70` | 20 | 0.5% | 70% | 44.11% | 42.79% | 1.069 | 72.4% | 7.1% | 325 |
| `tv_1.00` | 20 | 0.5% | 100% | 46.72% | 45.97% | 1.074 | 74.0% | 7.1% | 114 |

Every cell clears the bar (CAGR > 36.72%, DD < 82.29%) and every cell is
inside the 60% DD target. The plateau spans 39.51-46.77% CAGR and
42.79-52.97% DD. The base is not an isolated peak: `tv_1.00` is 0.05 pp
behind on CAGR, `entry_25` 0.93 pp, `buf_2.0` 1.20 pp. The fast-EMA and
buffer dimensions both have a soft edge (`entry_15` 39.51%, `buf_0.3`
40.78%), but both still pass comfortably.

## Neighbourhood beyond the grid

One-step changes that were not part of the pre-registered 8:

| Variant | CAGR | Max DD | Sharpe | Fills |
|---|---:|---:|---:|---:|
| Base | 46.77% | 44.13% | 1.086 | 164 |
| EMA 15/40/80 | 33.03% | 55.91% | 0.878 | 226 |
| EMA 25/60/120 | 46.58% | 51.71% | 1.064 | 166 |
| EMA 30/75/150 | 40.10% | 54.31% | 0.957 | 188 |
| EMA 20/50/150 | 46.76% | 44.13% | 1.091 | 164 |
| EMA 20/60/120 | 45.58% | 49.92% | 1.061 | 164 |
| Vol window 10 | 47.06% | 42.81% | 1.107 | 267 |
| Vol window 30 | 45.82% | 45.44% | 1.065 | 154 |
| Buffer 0.75% | 46.09% | 47.05% | 1.067 | 164 |

The ribbon lengths are a plateau from 20/50/100 to 25/60/120 and 20/60/120,
with 30/75/150 still passing at 40.10%. The short 15/40/80 ribbon **fails**
the bar at 33.03%: a 40-day middle EMA is too fast and reintroduces the
whipsaw. This is the honest boundary of the family. The 20/50/150 cell is
statistically identical to the base (46.76% versus 46.77%); the extra 50
days on the slow line change the QQQ repair gate only slightly on this
sample, so it is a null neighbour, not evidence.

## Component attribution (ablations, 1 bp)

| Variant | CAGR | Max DD | Sharpe | Reading |
|---|---:|---:|---:|---|
| Base | 46.77% | 44.13% | 1.086 | - |
| No hysteresis (0% buffer) | 36.40% | 44.13% | 0.933 | **the raw ribbon alone is just below the bar** |
| No volatility target | 46.33% | 48.55% | 1.062 | vol target: +0.44 pp CAGR, -4.42 pp DD |
| No QQQ repair tier | 45.79% | 44.13% | 1.075 | QQQ tier: +0.98 pp CAGR, no DD change |
| Hard exit below 100-day EMA | 32.22% | 44.49% | 0.879 | using the 100-day as a stop destroys 14.6 pp |
| Entry buffer +0.5% | 44.75% | 44.13% | 1.056 | delaying entry costs 2.0 pp |

The **hysteresis is the core of the edge**. Without it, the 20/50/100 stack
earns 36.40% CAGR, 0.32 pp below the bar, and trades 213 times instead of
164. The 0.5% buffer is worth about 10.4 pp of CAGR at the same 44.13%
drawdown. That is the measured whipsaw premium: the buffer removes the
shallow 20/50 crosses in May/June/November 2016, August 2019, March/April
2021 and October 2021. It also changes the January 2022 exit date (14 versus
19 January), which is a path effect rather than a systematic improvement;
the 1-session lag placebo is slightly better for the same reason.

The **volatility target is a tail brake, not a constant de-lever.** The mean
TQQQ weight is 73.63% while the time in TQQQ is 74.14%, so the target is at
1.0 on most days; it binds only when TQQQ's 20-day vol exceeds 85%. The
ablation shows the trade: +0.44 pp CAGR and -4.42 pp DD. A 70% target gives
44.11% / 42.79% (grid): it buys 1.3 pp of DD for 2.7 pp of CAGR.

The **QQQ middle tier is a small positive**, worth about 1 pp of CAGR with
no DD change. It is kept because it is the natural second rung of a
three-asset ribbon strategy and because it improves 2023 (+97% versus +89%
with BIL only), not because it is the main driver.

The **100-day EMA must not be a hard exit.** Making it one drops CAGR from
46.77% to 32.22% and raises fills from 164 to 308. The 100-day line is a
slow regime gate, and the 50/100 pair only gates entry; the exit belongs to
the buffered 20/50 cross.

## Placebo and lag tests

**Lag placebo** - shift the entire daily target by N sessions:

| Lag | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| 0 (base) | 46.77% | 44.13% | 1.086 |
| 1 | 47.78% | 47.67% | 1.098 |
| 5 | 37.45% | 62.68% | 0.906 |
| 10 | 30.49% | 70.60% | 0.780 |
| 20 | 30.34% | 72.74% | 0.767 |

The 1-session lag is within noise (it exits January 2022 one day later and
captures the 20 January rebound; TQQQ was up about 7.8% that day). From 5
sessions the decay is monotonic and the 5-session lag is already at the bar
(37.45% versus 36.72%), while 10 and 20 sessions collapse to about 30%. The
timing carries information, but the exact entry/exit day is not sharply
identified.

**Shuffled-run placebo** - 30 random paths with the same number of on/off
days, the same run-length distribution, the same volatility target and the
same QQQ repair rule:

| Statistic | Value |
|---|---:|
| Placebo CAGR median | 29.61% |
| Placebo CAGR p90 | 43.48% |
| Placebo CAGR max | 50.70% |
| Placebo DD median | 78.14% |
| Placebo DD minimum | 56.38% |
| Placebo Sharpe median | 0.760 |
| Placebo Sharpe max | 1.171 |
| Base CAGR percentile | 93.3% |
| Base Sharpe percentile | 96.7% |
| Base DD percentile | 100% |

The base is at the 93.3rd percentile on CAGR and the 96.7th on Sharpe, but
two placebo draws beat it on CAGR (50.70% and 47.68%). The drawdown
separation is unambiguous: the base's 44.13% DD is below every one of the 30
placebo draws (minimum 56.38%). The timing mainly buys risk control; the
return edge is real but not statistically unique with 30 draws.

## Cut tests and sub-periods

Fresh start at later dates (same weights, new $100k book):

| Start | CAGR | Max DD | Sharpe | TQQQ exposure |
|---|---:|---:|---:|---:|
| 2017-01-03 | 52.59% | 44.13% | 1.155 | 73.4% |
| 2018-01-02 | 43.77% | 44.13% | 1.001 | 69.0% |
| 2019-01-02 | 52.42% | 44.13% | 1.120 | 68.7% |
| 2020-01-02 | 54.98% | 44.13% | 1.133 | 66.1% |
| 2021-01-04 | 36.39% | 42.34% | 0.955 | 60.7% |
| 2022-01-03 | 17.35% | 38.48% | 0.639 | 41.3% |

The 2017-2020 starts clear the bar with 7.0-18.3 pp of CAGR margin. The 2021
start is 0.33 pp below the bar; the 2022 start (at the top of the bear
market) is well below it at 17.35% CAGR, though still positive. A strategy
started at a 2022-style top does not beat a full-window TQQQ number; that is
the honest horizon risk.

Fixed sub-periods:

| Period | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| 2016-2019 | 38.13% | 36.18% | 1.026 |
| 2020-2021 | 103.16% | 44.13% | 1.464 |
| 2022-2023 | 17.33% | 38.48% | 0.638 |

The early half (2016-2019) is **above** the full-period bar at 38.13% CAGR,
which is the strongest evidence that the result is not only a 2020-2021
recovery artifact. The last two years are the weak evidence: 2022's
January whipsaw and 2023's October exit cost the strategy most of the
2022-2023 upside.

## The drawdowns

**The 44.13% max DD is the COVID crash: 2020-02-19 14:44 -> 2020-03-09
09:30.** The ribbon was still stacked at the February top; the volatility
target had cut the TQQQ weight only modestly because 20-day vol was still
below 85% on 19 February. The state left on 9 March, at the circuit-breaker
low, and the book re-entered on 30 April. The strategy still made +125.2% in
2020 because it re-entered into the April-August recovery, but the exit was
late and the drawdown is the price of a daily ribbon.

**2022 is -30.31%.** The state was FULL at the end of 2021. It exited on
19 January 2022 after TQQQ had fallen about a quarter. The QQQ repair tier
then held QQQ during the March-April and August bear rallies, which is where
most of the remaining loss came from. The strategy avoided the -79.4% TQQQ
year but not the whipsaw.

**2019 is +38.85% versus TQQQ's +148.2%, with a 36.18% intra-year DD versus
TQQQ's 32.0%.** The June 2019 exit sold after the May decline and re-entered
on 18 June; the August churn was removed by the buffer. A V-shaped,
high-volatility bull market is the worst regime for this design.

**2023 is +97.08% versus TQQQ's +192.0%.** The stack broke on 3 October 2023
and re-formed on 10 November, so the book was in QQQ/BIL for part of the
November melt-up. This is the participation cost of a 100-day anchor.

Worst five days: 2020-09-03 -15.40%, 2020-02-27 -15.09%, 2020-06-11
-14.79%, 2020-03-09 -14.75%, 2020-09-08 -14.21%. Four of the five are 2020
gap or crash days; the strategy has no overnight-gap protection.

## Why it works, and where it could fail

**Why it works.** TQQQ's 82% drawdown is made by multi-month bears, not by
single days. The 20/50/100 stack plus the 0.5% buffer leaves 2018Q4, 2020
and 2022, and the QQQ tier keeps a 1x position through ordinary pullbacks.
The volatility target cuts the leveraged sleeve exactly when TQQQ's
realised vol is extreme. The book is in TQQQ 74% of the time, so it keeps
most of the drift; the 2017 and 2021 returns are essentially TQQQ's.

**Where it could fail.**

- **A 2022-style top.** The ribbon cannot anticipate a top; it exits after
  the 20/50 cross confirms. A repeat of January 2022 costs about 25% before
  the exit.
- **A 2019/2023-style V-year.** The strategy gives up a large part of a
  sharp, high-volatility bull market. If the holdout is one long V, the
  strategy can lag TQQQ badly even while making money.
- **Path dependence.** The 2016, 2019 and 2022 outcomes move by 10-40 pp
  when the exit date moves by two days. The grid and the buffer plateau are
  the defence, not a claim that the point estimate is stable.
- **Costs.** 164 fills and 682x turnover are low; 10 bp costs only 1.42 pp
  of CAGR. Cost fragility is not the issue.
- **Concentration.** 2020 + 2023 contribute 50% of the log P&L; the
  2022-2023 sub-period is below the bar.

## How this differs from the existing strategies

| Existing strategy | Mechanism | Difference |
|---|---|---|
| `fast-trend-vol` | two-speed 20/50 EMA with a 2.5% exit buffer, -3.5% daily crash cooldown, 2.5% QQQ intraday stop, TQQQ/BIL | three-EMA 20/50/100 stack, 0.5% Schmitt trigger, QQQ middle tier, no event brakes, no intraday stops |
| `daily-regime-minute-entry` (round-1 winner) | 165-day QQQ SMA + armed 4% TQQQ stop | no 165-day SMA, no stop |
| `vol-scaled-crash-stop` | always-long TQQQ, inverse-ATR size, ATR barrier | trend-gated TQQQ/QQQ/BIL |
| `dynamic-leverage-throttle` | episodic post-vol-shock recovery, BIL in calm uptrends | owns calm uptrends, de-risks in shocks |
| `dual-speed-regime` | 60-minute intraday EMA, flat overnight | daily decisions, holds overnight |
| `donchian-breakout` | 5-minute 20/55/390 alignment ladder, ATR sizing | daily 20/50/100 EMA ribbon |
| `ratio-froth` / `ratio-pairs` | TQQQ/QQQ or QQQ/SPY ratio signals | no ratio |
| `drawdown-regime` | post-drawdown recovery windows | continuous ribbon state |

The combination - 20/50/100 QQQ EMA stack + 0.5% 20/50 hysteresis + QQQ
middle tier + 85% TQQQ volatility target - is not used by any existing
strategy. It also deliberately avoids the old 165-day SMA and the 4% TQQQ
stop.

## Falsifier checklist

| # | Falsifier | Result | Status |
|---|---|---|---|
| 1 | CAGR <= 36.72% or DD >= 82.29% | 46.77% / 44.13% | **pass** |
| 2 | Fewer than 6/8 grid cells pass, or isolated peak | 8/8 pass; base 0.05-1.20 pp from the nearest cells | **pass** |
| 3 | 10 bp CAGR <= 36.72% | 45.35% | **pass** |
| 4 | Lag/placebo matches the base | lag 5 at the bar, lag 10/20 collapse; base 93.3rd pct CAGR, 96.7th Sharpe, 100th DD; two placebo CAGRs higher | **mostly pass, with an honest CAGR caveat** |
| 5 | One year >80% of P&L, or both halves negative | no year >80%; 2016-2019 +38.1%, 2022-2023 +17.3% | **pass, but 2022-2023 is weak** |
| 6 | 165-day baseline beats it on CAGR and DD | 43.61% / 59.64% versus 46.77% / 44.13% | **pass** |
| 7 | Core without hysteresis <= 36.72% | 36.40% | **pass** (just below) |
| 8 | Truncation changes prior weights | max daily diff 0.0; weight prefix identical | **pass** |

## Holdout arithmetic (not a forecast)

The development endpoint is 21.40x on $100k over 7.98 years. The holdout is
about 2.81 years (2024-01-02 -> 2026-10-23). For the full window to beat
TQQQ's 37.54% CAGR, the holdout needs about **14.3% CAGR**:

```
(1.3754^10.79 / 21.40)^(1/2.81) - 1 ~ 14.3%
```

For calibration, the weakest two-year development stretch (2022-2023) did
17.33%; a repeat of that would map to about **38.5% full-window CAGR**, a
narrow pass. A flat holdout would map to about 32.8% and fail. These are
arithmetic scenarios, not observations: the holdout was not loaded.

## Data discipline and reproduction

- Signals are the adjusted 1-minute QQQ 15:59 closes from the development
  panel. The adjusted daily parquet is used only for the pre-2016 EMA and
  volatility warmup, filtered to dates before 2016-01-04.
- Every weight at session `t` uses only closes through 15:59 of `t`; the
  fill is at the next session's open. The truncation check at 2020-12-31 is
  exact (daily max abs diff 0.0, weight prefix identical).
- No full-sample normalisation, no holdout bars, no selection on the
  holdout.

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
$env:BT_THREADS = "1"
python research\new\ema-ribbon-trend\strategy.py
```

`strategy.py` writes `result.json` with the primary 1/5/10 bp metrics, the
8-cell grid, the ablations, the extra neighbourhood, the lag and shuffled-run
placebos, the cut tests, the sub-periods, the 165-day benchmark and the
causality check.

## Bottom line

The strategy passes the development bar with a comfortable return margin:
**46.77% CAGR, 44.13% max DD, 1.09 Sharpe at 1 bp**, 45.35% at 10 bp, 73.6%
average TQQQ weight and 0.698 daily correlation to TQQQ. The 8-cell grid is a
real plateau, the no-hysteresis ablation shows the raw ribbon is just below
the bar, and the lag/placebo tests show the timing adds risk control more
than it adds a unique return stream. The honest risks are a 2022-style
lagging exit, a 2019/2023-style V-year participation cost, and a weak
2022-2023 sub-period. It is a risk-managed TQQQ trend allocator, not a
low-correlation alpha stream.
