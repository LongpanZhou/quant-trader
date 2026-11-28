# Session-timing TQQQ: development report

**Family:** session / time-of-day timing. The position is chosen by *when*
TQQQ is held inside the 24-hour day, not by a daily trend or volatility
regime.

**Verdict: passes the stated development bar at the mandated 1 bp headline,
with a broad 8-cell plateau and exact causality; fails the 5 bp cost stress.**
The family can beat the 36.72% bar at 1 bp, but the edge is cost-fragile and
should not be promoted as a robust standalone without a cheaper execution.

Development window 2016-01-04 .. 2023-12-29, 1-minute marks, next-open fills,
2% band, long-only, weights >= 0, sum <= 1. No 2024+ bar enters the panel or
any signal: the shared loader reads the archive, but the strategy is physically
sliced at 2023-12-29. The 10-day volatility warmup reads only the 252 QQQ
daily rows from 2015.

---

## 1. Headline

| | CAGR | Max DD | Sharpe | Sortino | Vol | TQQQ weight (bar-time) | Fills | Ending equity |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **Primary, 1 bp** | **56.31%** | **37.86%** | **1.34** | 1.89 | 39.4% | 19.1% | 4,048 | $3.539M |
| Primary, 2 bp | 49.08% | 39.68% | 1.21 | 1.72 | 39.4% | 19.1% | 4,048 | $2.425M |
| Primary, 3 bp | 42.19% | 42.17% | 1.09 | 1.55 | 39.4% | 19.1% | 4,048 | $1.662M |
| Primary, 4 bp | 35.62% | 45.00% | 0.97 | 1.38 | 39.4% | 19.1% | 4,048 | $1.139M |
| Primary, 5 bp | 29.35% | 47.70% | 0.85 | 1.20 | 39.4% | 19.1% | 4,048 | $0.780M |
| Primary, 10 bp | 2.10% | 60.48% | 0.25 | 0.35 | 39.5% | 19.1% | 4,049 | $0.118M |
| Primary, 0 bp (gross) | 63.89% | 36.65% | 1.46 | 2.06 | 39.4% | 19.1% | 4,048 | $5.164M |
| TQQQ buy & hold (sim) | 36.15% | 82.29% | 0.80 | 1.12 | 66.5% | 100% | 1 | $1.175M |
| TQQQ bar from the brief | 36.72% | 82.29% | 0.82 | -- | -- | 100% | -- | -- |

* The 1 bp result beats the published CAGR bar by **19.59 pp** and cuts max
  drawdown by **44.43 pp**.
* The cost curve crosses the 36.72% bar between **3 bp and 4 bp**. At 5 bp the
  strategy is **7.37 pp below** the bar; at 10 bp it is effectively flat.
  This is the binding weakness. The strategy pays two fills a day (one exit,
  one entry) on a book that compounds, so its turnover is 41,692x initial
  equity over 8 years (~5,222x/yr).
* Daily-return correlation to TQQQ **0.726**, beta **0.416**. This is a TQQQ
  beta product, not market-neutral alpha.
* Max drawdown episode: **2022-08-15 -> 2023-03-02, 37.86%**. The raw
  (no vol overlay) drawdown is **2020-02-19 -> 2020-03-18, 66.48%**.
* Exposure: **73.7% clock-time** (78.4% of minutes held x mean size 0.939);
  the 19.1% figure is the 1-minute-bar average and excludes the overnight gap,
  which has no bars. 54.1% of sessions enter early at 14:30; the rest at 15:59.
* Idle weight is cash at 0%. BIL was tested and rejected: it earns ~1.4%/yr on
  ~26% idle time but doubles the fill count and the cost.

---

## 2. What it is

Universe: QQQ (volatility input only), TQQQ (position), cash.

At **14:29 ET** of session k, with

```
r_k = TQQQ_close(14:29) / TQQQ_open(09:30) - 1
```

| State | Entry | Exit |
|---|---|---|
| `r_k > 0` (up session) | 14:30 open | 10:00 open of the next session |
| `r_k <= 0` (down session) | 15:59 open | 10:00 open of the next session |

In both cases the position is held through the overnight block. Size:

```
sigma_k = annualised stdev of the last 10 completed QQQ daily log returns
          through session k-1
s_k     = min(1, 0.25 / sigma_k),  0 if sigma_k is undefined
```

No daily trend SMA of any length, no volatility/drawdown regime switch, no
relative strength, no drawdown recovery. The only use of volatility is the
continuous sizing overlay, disclosed above and separated in section 5.

Execution is causal: the 14:29 bar close decides the 14:30 open; the same
signal sets the down-session entry at the 15:58 close, which fills at the
15:59 open; the 09:59 close decides the 10:00 exit. The vol input uses only
completed daily returns through the prior session.

---

## 3. Why this window

The design comes from a descriptive decomposition of the development window
(TQQQ, open-to-open). It is not a parameter search over strategy returns.

| Segment | Mean / session | Log sum 2016-2023 | Annualised log | Win |
|---|---:|---:|---:|---:|
| Overnight (15:59 -> next 09:30) | +12.5 bp | 1.84 | +25.9% | 56.7% |
| Opening 30m (09:30 -> 10:00) | +6.4 bp | 1.11 | +14.9% | 53.0% |
| Midday (10:00 -> 14:30) | -0.3 bp | -0.67 | -8.0% | 53.4% |
| Last 90m (14:30 -> 15:59) | +2.2 bp | 0.18 | +2.2% | 52.9% |
| Last 30m (15:30 -> 15:59) | -2.8 bp | -0.67 | -8.0% | 47.2% |

The overnight and opening drive carry the positive drift; the midday is a
drag. The last 90 minutes is **conditional** on the session's own trend:

| Sessions through 14:29 | n | Last-90m mean | Log sum | Win |
|---|---:|---:|---:|---:|
| Up (r > 0) | 1,089 | +9.2 bp | 0.89 | 55.8% |
| Down (r <= 0) | 923 | -6.1 bp | -0.71 | 49.4% |

The unconditional last 90 minutes is only +2.2 bp. Entering at 14:30 on up
sessions and at 15:59 on down sessions costs **no extra fill**: either way
there is one entry and one exit per day. The late-day condition is the
weakest leg statistically (t ~ 2.08 on the +9.2 bp mean), which is the main
research risk.

---

## 4. Robustness

### 4.1 Pre-registered grid (8 cells)

All eight cells use the 0.25 vol target and the 10:00 exit. The decision is
one minute before the entry shown.

| Cell | Entry | Threshold | 1 bp CAGR | 1 bp DD | 1 bp Sharpe | 5 bp CAGR | Early frac |
|---|---|---:|---:|---:|---:|---:|---:|
| 1 | 14:00 | 0.0% | 50.32% | 37.02% | 1.22 | 24.39% | 53.6% |
| 2 | 14:00 | +0.5% | **57.14%** | 41.09% | 1.34 | 30.03% | 43.7% |
| 3 | **14:30** | **0.0%** | **56.31%** | **37.86%** | **1.34** | **29.35%** | 54.1% |
| 4 | 14:30 | +0.5% | 49.49% | 47.72% | 1.23 | 23.71% | 43.2% |
| 5 | 15:00 | 0.0% | 46.31% | 44.79% | 1.18 | 21.07% | 54.9% |
| 6 | 15:00 | +0.5% | 47.68% | 45.49% | 1.21 | 22.21% | 44.7% |
| 7 | 15:30 | 0.0% | 41.04% | 50.23% | 1.10 | 16.72% | 54.6% |
| 8 | 15:30 | +0.5% | 41.95% | 50.10% | 1.12 | 17.47% | 45.0% |

The 1 bp plateau is broad: all eight cells clear the 36.72% CAGR bar and the
82.29% DD bar, from 41.04% to 57.14% CAGR. The centre is **not** the best cell
(cell 2 is +0.83 pp), which is evidence against cherry-picking the centre.
The 5 bp stress fails in every cell; the best 5 bp cell is 30.03%, still
6.69 pp below the bar.

### 4.2 Neighbours (not used to choose the centre)

| Variant | 1 bp CAGR | 1 bp DD | 1 bp Sharpe | 5 bp CAGR |
|---|---:|---:|---:|---:|
| Entry 14:15 | 59.32% | 39.61% | 1.38 | 31.83% |
| Entry 14:45 | 49.34% | 42.01% | 1.23 | 23.58% |
| Threshold -0.25% | 55.16% | 40.55% | 1.31 | 28.39% |
| Threshold +0.25% | 51.33% | 43.49% | 1.26 | 25.23% |
| Exit 09:45 | 50.74% | 44.43% | 1.28 | 24.74% |
| Exit 10:15 | 43.42% | 54.36% | 1.09 | 18.68% |
| Exit 10:30 | 51.28% | 49.96% | 1.19 | 25.19% |
| Exit 11:00 | 39.69% | 54.57% | 0.98 | 15.59% |
| Vol target 0.20 | 52.58% | 33.91% | 1.37 | 27.55% |
| Vol target 0.30 | 57.13% | 41.84% | 1.29 | 29.27% |
| Vol target 0.35 | 58.47% | 43.35% | 1.27 | 29.97% |
| Vol target 0.40 | 58.83% | 45.79% | 1.26 | 30.09% |
| Vol lookback 5 | 54.02% | 37.36% | 1.30 | 27.51% |
| Vol lookback 20 | 55.91% | 42.53% | 1.30 | 28.95% |
| QQQ instead of TQQQ signal | 55.96% | 36.85% | 1.33 | 29.06% |
| Raw, no vol target | 53.95% | 66.48% | 1.13 | 25.85% |
| **Stale signal (k-1)** | **26.89%** | **57.18%** | **0.80** | **5.00%** |

Every 1 bp neighbour clears the bar except the stale signal, which is the
strongest evidence that the current-session signal matters. The exit-time
neighbourhood is a ridge, not a point: 09:45-11:00 all clear the 1 bp bar,
though 10:15 and 11:00 are weaker in DD. The entry-time and vol-target
neighbourhoods are smooth.

### 4.3 Placebos

| Placebo | Real CAGR | Null mean | Null p95 | Null max | p(real) | Real DD | Null DD mean | DD percentile |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Random entry minute (10:01-15:59), 100 draws | 56.31% | 39.19% | 52.42% | 60.93% | **0.02** | 37.86% | 61.85% | **1.00** |
| Random subset of 1,089 early sessions, 100 draws | 56.31% | 39.35% | 46.43% | 51.94% | **0.00** | 37.86% | 55.39% | **1.00** |

The random-entry placebo keeps the overnight + opening window and the vol
target but draws each session's entry time uniformly from 10:01-15:59. The
real CAGR is at the 98th percentile; two of 100 random schedules beat it (the
best is 60.93%), so the CAGR edge is not overwhelming. The drawdown is more
robust: the real 37.86% is below all 100 random draws (percentile 1.00).

The random-subset placebo keeps the real entry-time distribution and the same
number of early entries, but chooses which sessions enter at 14:30 at random.
The real beats all 100 draws (p=0.00) and has the lowest drawdown. This is the
cleaner test of the **selection**: the condition, not just the entry-time
distribution, carries the edge.

### 4.4 Cut tests

| Cut | Strategy CAGR | Strategy DD | TQQQ CAGR | TQQQ DD |
|---|---:|---:|---:|---:|
| Ex-2016 | 60.56% | 37.03% | 38.66% | 81.68% |
| Ex-2018 | 57.05% | 37.03% | 46.60% | 81.68% |
| Ex-2019 | 52.63% | 37.03% | 25.90% | 81.68% |
| Ex-2020 | 43.44% | 37.03% | 27.84% | 81.68% |
| Ex-2021 | 52.56% | 37.03% | 30.34% | 81.05% |
| Ex-2022 | 75.66% | 35.49% | 77.75% | 69.89% |
| Ex-2023 | 53.26% | 36.47% | 21.49% | 81.68% |

Every ex-year cut clears the 36.72% absolute bar. The ex-2022 cut is the only
one where the strategy does **not** beat TQQQ (75.66% vs 77.75%); the
full-period *relative* edge is therefore concentrated in 2022, even though the
absolute return is broad-based. Ex-2020 the strategy still earns 43.44% vs
27.84% for TQQQ, so the pass is not only the COVID crash. The honest reading
is: broad absolute return, but a 2022 crash-avoidance shape at the relative
level.

### 4.5 Subperiods

| Period | Strategy CAGR | Strategy DD | TQQQ CAGR | TQQQ DD |
|---|---:|---:|---:|---:|
| 2016-2019 | 53.17% | 35.45% | 48.98% | 58.62% |
| 2020-2021 | 126.56% | 36.33% | 93.48% | 72.74% |
| 2022-2023 | 10.05% | 37.86% | -21.72% | 81.10% |

The strategy beats TQQQ in all three subperiods. The 2022-2023 subperiod is
the weakest in absolute terms (+10.05%) but has a +31.8 pp relative margin,
comparable to 2020-2021's +33.1 pp.

### 4.6 Yearly

| Year | Strategy | TQQQ |
|---|---:|---:|
| 2016 | +29.6% | +19.9% |
| 2017 | +49.8% | +114.5% |
| 2018 | +48.4% | -20.8% |
| 2019 | +90.9% | +148.2% |
| 2020 | +177.1% | +104.1% |
| 2021 | +82.8% | +81.1% |
| 2022 | -32.2% | -79.4% |
| 2023 | +74.9% | +192.0% |

The profile is the expected one for a risk-managed TQQQ beta: it wins in
2016, 2018, 2020, 2021 and 2022, and lags badly in the strong bull years
2017, 2019 and 2023. The 2023 lag is 117 pp. The CAGR edge comes from
compounding a smaller 2022/2020 drawdown, not from beating TQQQ every year.

### 4.7 Causality

| Cut | Prior weights unchanged | Max abs diff |
|---|---|---:|
| 2022-01-03 (day boundary) | true | 0.0 |
| 2020-03-12 11:07 (intraday) | true | 0.0 |

Both the full-panel weights before the cut and the intraday cut are bit-exact.
The strategy has no full-sample normalization.

---

## 5. The vol overlay: disclosed, useful, not the return source

| Variant | CAGR | Max DD | Sharpe | Vol |
|---|---:|---:|---:|---:|
| Raw, no vol target (always size 1) | 53.95% | 66.48% | 1.13 | 48.9% |
| Constant size at the mean (0.939) | 50.89% | 63.87% | 1.13 | 46.0% |
| **Primary, 0.25 vol target** | **56.31%** | **37.86%** | **1.34** | **39.4%** |

The raw session-timing strategy clears the CAGR bar on its own (53.95% vs
36.72%), so the session window is the source of the return edge. The vol
overlay adds +2.4 pp CAGR and cuts DD by 28.6 pp versus raw; versus a
constant size at the same mean it adds +5.4 pp CAGR and cuts DD by 26.0 pp.
The overlay is therefore a material risk control, and the sub-40% drawdown
depends on it. The raw 66.48% drawdown is still below the 82.29% hard bar but
above the "ideal < 60%" line.

A supplementary ablation (not in `result.json`): forcing the entry to 15:59
every session, i.e. removing the late-day condition but keeping the same
overnight + opening window and the 0.25 vol target, gives **40.05% CAGR /
58.96% DD / 1.09 Sharpe at 1 bp** (5 bp: 15.89%). The raw version of that
unconditional window (no vol target) is **37.77% / 67.77% / 0.93 at 1 bp**.
So the core close-to-10:00 session window clears the CAGR bar on its own,
though only just in the raw form; the conditional late-day leg lifts it from
40.05% to 56.31% and cuts DD from 58.96% to 37.86%.

---

## 6. Honest assessment

**What passes.**
- 1 bp dev CAGR 56.31% > 36.72%, DD 37.86% < 82.29%, Sharpe 1.34 > 0.82.
- All 8 pre-registered grid cells pass at 1 bp; the centre is not the best
  cell. The entry-time, threshold, exit-time, vol-target and vol-lookback
  neighbourhoods are smooth.
- Both placebos reject random timing: random-subset p=0.00, random-entry
  p=0.02. The real drawdown is below all 100 draws of both placebos.
- The stale-signal placebo collapses to 26.89%, so the current-session
  condition is doing real work.
- Every ex-year cut clears the bar; the 2016-2019, 2020-2021 and 2022-2023
  subperiods all beat TQQQ.
- Causality is exact at both the day-boundary and intraday cuts.

**What fails or is fragile.**
- **Cost.** At 5 bp the CAGR is 29.35%, 7.37 pp below the bar; at 10 bp it is
  2.10%. The breakeven is between 3 bp and 4 bp. The strategy pays two fills
  a day on a compounding book; turnover is 41,692x initial equity. The 1 bp
  headline is the mandated convention, but a realistic 5 bp implementation
  does not clear the bar.
- **The late-day condition is a ~2-sigma effect.** The +9.2 bp mean on 1,089
  up sessions has t ~ 2.08. The random-entry placebo has a max draw of 60.93%
  above the real 56.31%, so a lucky random entry schedule can beat the real
  CAGR. The drawdown advantage is more robust than the CAGR advantage.
- **The vol overlay carries the sub-40% drawdown.** Without it the DD is
  66.48%; with a constant size at the same mean it is 63.87%. The overlay is
  disclosed and the raw passes, but the headline DD is not a pure
  session-timing result.
- **Strong-bull lag.** 2023 is +74.9% vs TQQQ +192.0%; 2017 and 2019 also lag
  by 65 pp and 57 pp. The strategy is not a bull-market replacement.
- **Beta, not alpha.** Daily correlation 0.726, beta 0.416. The edge is the
  overnight/opening-drift premium plus the conditional late-day continuation,
  not independent market-neutral alpha.
- **The relative edge is concentrated in 2022.** The ex-2022 cut is 75.66%
  versus TQQQ's 77.75%, so outside 2022 the strategy roughly matches TQQQ's
  return; the full-period CAGR advantage comes from losing much less in 2022.
  The absolute CAGR is broad-based (every ex-year cut clears the bar), but the
  *edge over TQQQ* is a crash-avoidance shape.

**Bottom line.** This is a legitimate, causal, family-pure session-timing
strategy that clears the 1 bp development bar with a broad plateau and a real
drawdown improvement. It is **not** robust to 5 bp costs, and its CAGR edge is
partly a 2-sigma late-day momentum effect. Treat it as a promising
cost-sensitive candidate for a cheaper execution venue, not as a verified
standalone replacement for TQQQ.

---

## 7. Reproduction

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
$env:BT_THREADS = "1"
python research/strategies/family-session-timing/strategy.py
```

`strategy.py` writes `result.json` with the centre, the 0-10 bp cost curve,
the 8-cell grid, the neighbours, the controls, both placebos, the cut tests,
the yearly table and the two causality cuts. The strategy numbers above come
from that file; the TQQQ subperiod benchmarks are computed from the same
1-minute panel, and the unconditional-window ablation is marked
supplementary.
