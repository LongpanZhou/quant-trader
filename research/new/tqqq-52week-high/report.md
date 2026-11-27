# 52-week-high trend TQQQ — development report

**Slug:** `tqqq-52week-high`
**Window:** 2016-01-04 → 2023-12-29 (2,012 sessions). Development only.
**Data:** official adjusted daily QQQ/TQQQ OHLC for signals; daily panel from the
1-minute archive in `research/bt.py` for next-open fills.
**Status:** dev pass, with caveats documented below.

---

## 1. Verdict

| | CAGR | max DD | Sharpe | Sortino | TQQQ expo | time in TQQQ | fills | corr to TQQQ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **Strategy @ 1 bp** | **43.30%** | **37.42%** | **1.18** | 1.63 | 65.0% | 65.3% | 151 | 0.537 |
| Strategy @ 5 bp | 42.59% | 37.6% | 1.16 | — | 65.0% | 65.3% | 151 | 0.537 |
| Strategy @ 10 bp | 41.71% | 37.9% | 1.15 | — | 65.0% | 65.3% | 151 | 0.537 |
| TQQQ buy-hold (panel) | 35.98% | 81.68% | 0.80 | — | 100% | 100% | — | 1.000 |
| TQQQ official bar | 36.72% | 82.29% | 0.82 | — | 100% | 100% | — | 1.000 |
| QQQ buy-hold | 18.86% | 35.1% | 0.87 | — | — | — | — | — |
| BIL buy-hold | 1.39% | 0.2% | 6.84 | — | — | — | — | — |
| 165-SMA TQQQ, benchmark only | 43.63% | 58.7% | 1.01 | — | — | — | — | 0.724* |

\* correlation of the strategy's daily returns to the 165-SMA benchmark curve.

At 1 bp the strategy clears the dev CAGR bar by **+6.58 pp** and the DD bar by
**−44.9 pp**; it meets the < 60% DD target with room. Calmar is 1.16 versus 0.44
for TQQQ. Ending equity on $100k is $1.77m. Costs are not the issue: at 10 bp the
CAGR is still 41.71%.

**Honest verdict.** This is a real dev pass, not a knife-edge: the base is
43.3%, and 6 of the 8 pre-registered cells pass, with the exit/vol dimensions
flat. But the entry gate is a *ridge*, not a broad plateau: a 5% band fails at
31.1%, and the pass depends on the two big bull years (dropping 2017 or 2020
from the product leaves 35.9%/36.2%, just under the bar). The strategy is a
risk-managed TQQQ participation strategy, not a return miracle: the old 165-SMA
base has a similar CAGR with a much larger drawdown. Its holdout chance is
moderate-to-good, not certain.

---

## 2. Mechanism

### 2.1 Why proximity to the 52-week high is a momentum signal

The 52-week high is not a forecast of next month's return; it is a **regime
identifier**. When an index is within a few percent of its 52-week high, the
average holder is near or above water. There is little overhead supply from
trapped buyers, the marginal seller has already been absorbed, and the price is
revealing that demand exceeds supply at the top of the range. The behavioural
literature (George & Hwang, 2004, "The 52-Week High and Momentum Investing")
attributes the continuation to anchoring and under-reaction: investors anchor
on the old high and under-price good news near it, so the trend persists.

For a 3x daily-reset ETF the same regime has a second, mechanical benefit.
TQQQ's long-run return is the leveraged index return minus a path-dependent
volatility drag that is convex in realised variance. The regimes that produce
20-35% index drawdowns (2018Q4, 2020, 2022) produce 55-80% ETF drawdowns and
destroy capital that later compounding cannot recover. Being long TQQQ in the
calm, near-high regime and out in the high-vol bear regime is therefore worth
more than the simple average of the index returns suggests. The 52-week high is
a slow, low-turnover way to identify that regime.

### 2.2 Why the 20-day trend and the exits are needed

The 52-week high alone is too slow: it stays satisfied during the first months
of a bear market because the old high is still in the window. The 20-session SMA
entry gate and the 20-session closing-low exit provide the fast trend break; the
10% drawdown stop is the disaster backstop for a gap through the low. The
volatility target de-risks the position when TQQQ's own 20-session vol is high;
it binds on 17% of sessions at the 0.85 target (mean scale 0.967, minimum 0.30),
so it is a crisis brake rather than a constant drag.

### 2.3 Where it fails, stated up front

- **Whipsaw.** A 20-session closing low is a routine event in an uptrend. On a
  3x ETF the round trip is expensive: sell at 1x, rebuy 3-8% higher in QQQ,
  which is 10-25% higher in TQQQ. 2016, 2019, 2021 and 2023 all show this.
- **Late re-entry.** After a bear market the 52-week high is stale. QQQ must
  recover most of the drawdown before the 8% gate re-opens, so the strategy
  systematically misses the first leg (H1 2019, H1 2023). This is structural,
  not a parameter error.
- **2018/2022.** The exit is necessarily after the first 10-20% of the decline.
  The point is not to sell the top; it is to avoid the remaining 50-70% of the
  leveraged drawdown.
- **The 8% entry band is a ridge.** 5% is too strict (re-entry is too late),
  6-7% is at the bar, 8-11% works. The edge requires *enough* room to re-enter
  after an ordinary correction while still excluding deep bear markets.

---

## 3. Rules and pre-registration

### 3.1 Signal (all through session close t; fills at t+1 open)

```
H_t     = max(QQQ high[t-251 .. t])          # 52-week high, includes t
dist_t  = QQQ close[t] / H_t - 1
trend_t = SMA20(QQQ close)[t]
L_t     = min(QQQ close[t-20 .. t-1])        # prior 20-session closing low

state:
  off -> on   iff dist_t >= -0.08 and close_t > trend_t
  on  -> off  iff close_t < L_t
                 or (dist_t <= -0.10 for 2 consecutive closes)

weight_t = state_t * min(1, 0.85 / sigma_t)
sigma_t  = stdev(log TQQQ returns, 20 sessions) * sqrt(252)
TQQQ = weight_t, BIL = 1 - weight_t
```

The 2-close confirmation on the 10% stop is a debounce. The 20-day closing-low
exit uses the standard one-close Donchian rule. The 52-week high uses intraday
highs, the standard definition.

### 3.2 Specification revision (disclosed)

Revision 1 was pre-registered with the 20-day low taken from **intraday lows,
buffered 2%, confirmed over 2 closes**. After the first run, the event counter
showed the low exit fired **0 times in eight years**: a 2% break below the
lowest intraday low of 20 sessions is almost always deeper than the 10% stop, so
the rule was decorative. Revision 1 still produced 42.21% CAGR / 45.4% DD / 1.03
Sharpe, but only the drawdown stop was active.

Revision 2 changes the low to the standard **20-day closing low, no buffer, one
close**. That exit now fires 22 times, and the drawdown stop remains active
(2 times). The revision is an implementation fix, not a search: it was made
because v1 did not implement "exit on a 20-day low". Both versions are in
`result.json` (`v1_intraday_low_2pct` ablation reproduces v1 exactly). The
revision-2 grid was frozen before its own results were computed.

### 3.3 Pre-registered 8-cell grid (revision 2)

| cell | change from base |
|---|---|
| `base` | — |
| `entry_5` | 5% proximity band |
| `entry_10` | 10% proximity band |
| `exit_dd_8` | 8% drawdown stop |
| `exit_dd_12` | 12% drawdown stop |
| `dd_confirm_3` | 3-close stop confirmation |
| `low_buf_2` | 2% buffer on the 20-day closing low |
| `tv_0.65` | 0.65 vol target |

No cell was added or removed after the results were seen.

### 3.4 Execution and data discipline

- Signals use official adjusted daily OHLC (the 16:00 print); fills use the
  1-minute panel's next 09:30 open. This is conservative relative to a 15:59
  decision.
- 2015 daily history warms the 252-session high; the in-window signal uses each
  session's official close. No full-sample normalisation.
- The daily parquet read is hard-filtered at `2023-12-29`. The 2024-2026
  holdout is never read by `strategy.py`.
- 2% weight band, 1 bp headline plus 5/10 bp, long-only, weights ≥ 0, sum ≤ 1.

---

## 4. Results

### 4.1 Yearly returns

| year | strategy | TQQQ | comment |
|---:|---:|---:|---|
| 2016 | +14.6% | +18.6% | 5 entries / 4 round trips; still positive |
| 2017 | +106.2% | +113.0% | one June exit, then held |
| 2018 | +2.8% | −23.5% | Oct 5 low exit before Q4; Nov re-entry stopped at −11% |
| 2019 | +52.0% | +130.5% | May/Aug/Oct whipsaws; missed H1 recovery |
| 2020 | +103.6% | +99.8% | Feb 25 exit before COVID; big re-entry |
| 2021 | +56.7% | +90.9% | Feb/May/Sep/Dec whipsaws |
| 2022 | −18.1% | −79.7% | Jan 7 low exit; out for the whole bear |
| 2023 | +63.8% | +204.9% | missed H1; Aug-Oct whipsaws; still +64% |

The pattern is exactly the mechanism: protect the down years (2018, 2022), lag
the strongest recovery years (2019, 2023), and roughly match the calm bull years.

### 4.2 Exposure and turnover

- Mean TQQQ weight: **65.0%**; time with any TQQQ: **65.3%**.
- Cash residual: 0.05% (BIL carries the rest).
- 151 fills over 8 years; turnover 625× starting equity, or ~78×/year.
- Correlation of daily strategy returns to TQQQ: **0.537**.
- Worst days: 2020-09-03 −15.4%, 2020-06-11 −14.8%, 2020-09-08 −14.2%,
  2016-06-24 −12.2%, 2018-02-05 −11.7%. All are whipsaw/crash days while long.

---

## 5. Grid and plateau

| cell | CAGR | max DD | Sharpe | TQQQ expo | pass? |
|---|---:|---:|---:|---:|:---:|
| **base** | **43.30%** | **37.4%** | **1.18** | 65.0% | ✅ |
| entry_5 | 31.13% | 48.6% | 0.95 | 61.2% | ❌ |
| entry_10 | 37.00% | 48.1% | 1.03 | 66.8% | ✅ |
| exit_dd_8 | 41.90% | 36.4% | 1.16 | 64.3% | ✅ |
| exit_dd_12 | 38.60% | 43.8% | 1.08 | 65.3% | ✅ |
| dd_confirm_3 | 40.48% | 43.8% | 1.12 | 65.2% | ✅ |
| low_buf_2 | 36.19% | 46.1% | 0.97 | 71.5% | ❌ |
| tv_0.65 | 41.78% | 36.7% | 1.18 | 63.5% | ✅ |

6 of 8 pass; grid median 39.5%, median of passers 41.1%. **Disclosure:** the
base is also the highest-CAGR cell in this grid. It was fixed from the mandate's
design point (8% proximity, 10% stop, 20-day low, 0.85 vol target) before the
grid was run, but the reader should not treat the grid as independent evidence
that 8% is the optimum. The neighbourhood table below is the better guide.

The two failures are
the two rules that add friction: a 5% entry band (re-entry too late) and a 2%
buffer on the low exit (exit too late). This is a coherent direction, not random
noise: both reduce the strategy's ability to re-enter after a correction.

**Where the plateau is flat.** Along the exit and sizing dimensions the surface
is well behaved:

- `exit_dd` 8/9/10/11/12%: 41.90, 41.26, 43.30, 41.39, 38.60 — all pass.
- `dd_confirm` 1/2/3: 41.37, 43.30, 40.48 — all pass.
- `target_vol` 0.65/0.75/0.85/0.95/1.00: 41.78, 42.79, 43.30, 43.09, 43.02 —
  essentially flat.
- `trend_n` 15/20/25/30: 45.45, 43.30, 40.08, 36.16 — monotone; 30 is just
  below the bar.

**Where it is a ridge, not a plateau.** The entry band and the low definition
matter:

- `entry_dist` 6/7/8/9/10/11%: 36.07, 36.40, 43.30, 40.96, 37.00, 39.21.
  8-11% passes; 6-7% is at the bar; 5% fails.
- `low_n` 15/20/25: 39.90, 43.30, 34.95.
- `low_buf` 0/0.5/1/2%: 43.30, 37.78, 32.75, 36.19. The raw closing low is the
  standard Donchian definition and also the best cell; any buffer delays the
  exit and costs CAGR.

I would not claim a broad plateau across every dimension. The defensible claim
is: **the standard-definition core (8-11% entry, 8-12% stop, 20-day closing low,
0.65-0.95 vol target) is a stable ridge**, and the two friction cells are the
ones that break it.

---

## 6. Component ablations

| variant | CAGR | max DD | Sharpe | TQQQ expo | event counts (entries/dd/low) |
|---|---:|---:|---:|---:|---|
| **base** | **43.30%** | **37.4%** | **1.18** | 65.0% | 25 / 2 / 22 |
| no low exit | 42.21% | 45.4% | 1.03 | 75.0% | 9 / 8 / 0 |
| no DD exit | 38.60% | 43.8% | 1.08 | 65.3% | 25 / 0 / 24 |
| no 52-week gate | 32.41% | 64.1% | 0.86 | 77.1% | 35 / 0 / 34 |
| no 20-day trend gate | 37.74% | 43.7% | 0.99 | 71.6% | 52 / 2 / 49 |
| 52-week high of closes | 41.09% | 40.2% | 1.13 | 66.0% | 27 / 4 / 22 |
| TQQQ-based signal | 19.50% | 46.6% | 0.67 | 62.7% | 19 / 9 / 9 |
| v1 intraday low + 2% buffer | 42.21% | 45.4% | 1.03 | 75.0% | 9 / 8 / 0 |
| always long TQQQ | 38.02% | 78.7% | 0.84 | 96.5% | — |

Every component earns its place:

- The **52-week gate** is the largest contributor: +10.9 pp CAGR and −26.7 pp DD
  versus a pure 20-day trend/20-day low system.
- The **20-day trend gate** adds +5.6 pp CAGR and −6.3 pp DD.
- The **low exit** adds +1.1 pp CAGR and −8.0 pp DD versus no low exit; the
  **DD stop** adds +4.7 pp CAGR and −6.4 pp DD versus no DD stop. Both exits are
  now active, unlike v1.
- The **vol target** adds +0.4 pp CAGR and −0.5 pp DD versus no target at this
  sample, but it is a tail brake, not a return driver.
- Using **TQQQ itself** as the 52-week/trend basis destroys the edge (19.5%):
  TQQQ's 3x path is too noisy to define the regime. QQQ is the right signal
  asset.

---

## 7. Robustness

### 7.1 Placebos

| placebo | median CAGR | p95 CAGR | max CAGR | base percentile |
|---|---:|---:|---:|---:|
| circular shift of weights (200 draws) | 21.87% | 45.76% | 75.13% | 92.5% |
| random on-days, same sizes (200 draws) | 25.38% | 41.01% | 50.06% | 97.5% |

The base at 43.30% is at the 92.5th percentile of circular shifts and the 97.5th
percentile of random-day placement. The circular-shift p95 (45.76%) is above the
base, so the timing edge is real but not overwhelming: a lucky shift can beat
it. The random-day placebo is stronger: destroying the clustering of the signal
removes ~18 pp of CAGR at the median.

Lag placebos:

| lag | CAGR | max DD | Sharpe |
|---:|---:|---:|---:|
| 1 day | 42.88% | 42.2% | 1.15 |
| 5 days | 34.50% | 45.2% | 0.94 |
| 10 days | 33.96% | 48.1% | 0.90 |
| 20 days | 31.97% | 69.9% | 0.82 |

A one-day lag barely matters (the signal is a daily regime, not a microstructure
effect). A five-day lag already loses the edge, which is expected for a
20-session trend system.

### 7.2 Cut tests

| start | CAGR | max DD | Sharpe | TQQQ expo |
|---:|---:|---:|---:|---:|
| 2017-01-03 | 47.34% | 37.4% | 1.24 | 64% |
| 2018-01-02 | 38.12% | 37.4% | 1.04 | 59% |
| 2019-01-02 | 46.63% | 37.4% | 1.19 | 57% |
| 2020-01-02 | 45.02% | 37.4% | 1.14 | 54% |
| 2021-01-04 | 30.06% | 37.3% | 0.96 | 47% |
| 2022-01-03 | 15.75% | 31.9% | 0.68 | 31% |

Starting in 2017-2020, the strategy clears the bar. Starting in 2021 or 2022, it
does not — those two windows contain the 2022 bear and the weak 2023 capture.
The full-window result is not a single-subperiod artifact, but the last two
years are the clear soft spot.

### 7.3 Subperiods

| period | CAGR | max DD | Sharpe |
|---|---:|---:|---:|
| 2016-2019 | 41.37% | 34.9% | 1.24 |
| 2020-2021 | 75.11% | 37.4% | 1.39 |
| 2022-2023 | 15.97% | 31.9% | 0.69 |

### 7.4 Leave-one-year-out

| year removed | CAGR of the remaining 7 years |
|---:|---:|
| 2016 | 47.82% |
| 2017 | **35.92%** |
| 2018 | 50.14% |
| 2019 | 41.98% |
| 2020 | **36.17%** |
| 2021 | 41.36% |
| 2022 | 55.08% |
| 2023 | 40.47% |

Removing 2017 or 2020 drops the CAGR just below 36.72%. The pass therefore
depends on at least one of the two strongest bull years. That is not unusual for
a long-biased strategy, but it is a real fragility: a holdout without a
2017/2020-style melt-up would be harder.

### 7.5 Causality

Truncating the daily signal data at 2021-12-31 and rebuilding the weights for
the truncated panel produces an identical prefix:

```
weight_prefix_equal: True
max_abs_diff: 0.0
```

No future data leaks into the weights, and no full-sample normalisation is used.

### 7.6 Episode table

| episode | strategy | TQQQ |
|---|---:|---:|
| 2018-09-20 → 2018-12-24 (Q4 bear) | −16.8% | −56.2% |
| 2020-02-19 → 2020-03-23 (COVID) | −24.2% | −69.8% |
| 2022-01-03 → 2022-10-14 (bear) | −18.7% | −79.5% |
| 2019 full year (recovery) | +52.0% | +130.5% |
| 2023 full year (recovery) | +63.8% | +204.9% |

The crash protection is the point: in the three big bears the strategy loses
17-24% while TQQQ loses 56-80%. The recovery lag is the price: it captures 40%
of 2019 and 31% of 2023.

### 7.7 Whipsaw anatomy (the 2020 max drawdown)

The max drawdown is **not** a crash. It is the September-November 2020 whipsaw:

| date | action | QQQ | dist to 52w high | reason |
|---|---|---:|---:|---|
| 2020-09-11 | sell | 261.09 | −10.9% | 10% stop (2 closes) |
| 2020-10-01 | buy | 272.48 | −7.0% | back within 8% and above SMA20 |
| 2020-10-28 | sell | 262.24 | −10.5% | 10% stop |
| 2020-11-04 | buy | 276.98 | −5.5% | back within 8% |

Two round trips at 4-6% in QQQ are 12-18% in TQQQ; the equity peak on
2020-09-02 to the trough on 2020-11-10 is −37.4%. This is the named failure mode
in its purest form: a fast V-shaped correction that triggers the stop twice and
then recovers without the strategy. The 2019 May/Aug/Oct and 2023 Aug/Sep/Oct
sequences are the same pattern with smaller amplitude.

### 7.8 Where the 2018 and 2022 exits happened

- **2018:** low exit on 2018-10-05 at QQQ 171.34 (dist −3.9%), before the Q4
  collapse; a November re-entry was stopped at −11.2% on 2018-11-13. Full-year
  +2.8% versus −23.5% for TQQQ.
- **2022:** low exit on 2022-01-07 at QQQ 369.15 (dist −6.9%), near the top.
  The strategy stayed in BIL for the entire bear and re-entered on 2023-04-13.
  Full-year −18.1% versus −79.7% for TQQQ. The cost was missing H1 2023.

The 2022 exit is the single best call in the sample and also the reason 2023 is
weak: the same stale-high gate that kept the strategy out of the bear kept it
out of the first-half recovery.

---

## 8. Honest verdict and holdout

**What is strong.**
- The dev pass is comfortable on both axes: +6.58 pp CAGR over the official bar,
  37.4% DD versus 82.3%, Sharpe 1.18 versus 0.82.
- The result survives 10 bp costs (41.71% CAGR), a one-day lag (42.88%), and the
  two placebos at the 92.5th/97.5th percentile.
- Every component contributes in the ablation; the 52-week gate is the largest
  single contributor.
- Both mandated exits are active (22 low exits, 2 DD exits), and the v1 bug is
  disclosed rather than hidden.

**What is fragile.**
- The entry band is a ridge: 5% fails at 31.1%, 6-7% is at the bar, 8-11%
  works. A reader who insists on "within 5% of the high" should treat this as a
  failed strategy.
- The CAGR pass depends on 2017/2020; leave-one-year-out drops to 35.9%/36.2%.
- 2023 is weak (+63.8% versus +204.9%). If the holdout is a 2023-style grind
  with frequent 20-day low breaks, the strategy will lag TQQQ badly even while
  making money.
- The 165-SMA benchmark has a similar CAGR (43.63%) with a much larger DD
  (58.7%). The 52-week strategy is a drawdown improvement, not a return
  improvement over that old base. Its value is the 37% DD and 1.18 Sharpe.

**Holdout chance.** Moderate-to-good. The strategy is long 65% of the time,
cuts the three large bears by 40-60 pp, and compounds at 43% in dev. The
full-sample TQQQ bar is 37.54%; the strategy's dev CAGR is 5.8 pp above that
full-sample bar (6.6 pp above the dev bar), so it has a cushion but not a huge
one. A 2024-2026 bull with normal pullbacks should let it participate; a
2022-style bear should let it protect; a 2023-style recovery would hurt. I would
not re-tune after the holdout, and I would not describe this as a high-conviction
winner — it is a legitimate, documented passer with a known failure mode.

**No holdout inspection was performed by this agent.** `strategy.py` filters the
daily parquet at 2023-12-29, and `build_weights` now raises if the panel extends
past the requested `end`; the lead's harness must lift `DEV_END` explicitly for
an authorized holdout run.

**Protocol note (important).** A `holdout.json` and `holdout_run.log` appeared in
this folder at 04:53:36, created by the lead's harness after revision 1's
`result.json` was written. I did not create them and did not read their
contents. They correspond to revision 1, not the final revision 2. Because the
holdout is one-shot, the lead should treat those files as stale and decide
explicitly whether to re-run on the frozen revision-2 `strategy.py`. The guard
added in revision 2 prevents a re-run from silently ffilling a 2023 signal
through 2024-2026.

---

## 9. Reproduction

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
$env:BT_THREADS = "1"
python research\new\tqqq-52week-high\strategy.py
```

Outputs: `result.json` (all primary/grid/ablation/placebo/cut/causality data) and
this report. The `build_weights(ts, o, c, params, end)` entry point is used by
the causality test and can be called by the lead's audit harness.

---

### Appendix: files

- `HYPOTHESIS.md` — pre-registration, revision 2 and the v1 disclosure.
- `strategy.py` — signal, weights, backtest, tests, `main()`.
- `result.json` — machine-readable results.
- `report.md` — this document.
