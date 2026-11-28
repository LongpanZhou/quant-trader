# Failed-breakdown spring, repaired — report

**Slug:** `drawdown-stop-overlay-v2`
**Window:** 2016-01-04 .. 2023-12-29 (development only; the 2024-2026 holdout
and the 10y/5y windows were not loaded).
**Execution:** `research/bt.py`, 1-minute marks, next-open fills, 2% band,
long-only (TQQQ + BIL), 1 bp headline; 5 bp and 10 bp also reported.
**Primary:** `h1_trend_vol_nostop_close` — one-session hold, QQQ > 200-day SMA,
20-day vol < 30%, no stop, exit at the 15:59 open (decision 15:58).
**Verdict:** **retired as a standalone.** The repair removes the catastrophic
63% drawdown and turns the CAGR positive, but it is not a risk-adjusted edge.
The signal's only positive horizon is a weak one-day pop; a static TQQQ/BIL mix
with the same average exposure has a 1.13 Sharpe and a 2.1% drawdown versus the
repair's 0.54 Sharpe and 23.4% drawdown. The old overlay remains an overlay on
the 165-day base.

---

## 1. Headline

| book | CAGR | max DD | Sharpe | Sortino | vol | TQQQ time | fills | turnover |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **original rebuild** | **-9.25%** | **63.09%** | **-0.27** | -0.36 | 24.8% | 7.36% | 153 | 108.0x |
| **primary `h1_trend_vol_nostop_close`** | **3.36%** | **23.37%** | **0.54** | 0.77 | 6.5% | 1.14% | 93 | 104.2x |
| stop neighbour `h1_trend_vol_stop8_close` | 3.13% | 24.45% | 0.52 | 0.74 | 6.5% | 1.11% | 93 | 107.6x |
| static TQQQ/BIL at primary exposure | 1.96% | 2.11% | **1.13** | 1.61 | 1.7% | 1.14% | 6 | 1.1x |
| TQQQ buy & hold | 35.98% | 81.68% | 0.80 | — | 67.7% | 100% | — | — |
| QQQ buy & hold | 18.86% | 35.11% | 0.87 | — | 22.7% | — | — | — |
| 165-day QQQ SMA baseline | 43.62% | 59.64% | 1.01 | 1.40 | 47.2% | 100% | 59 | 265.0x |

The repair removes the 63% drawdown and turns the CAGR positive, but it does
**not** produce a better risk-adjusted use of TQQQ exposure. The event book
earns 3.36% with a 23.37% drawdown; a static 1.14% TQQQ sleeve earns 1.96% with
a 2.11% drawdown and a 1.13 Sharpe. The event timing is concentrated risk, not
alpha.

---

## 2. Diagnosis of the old rebuild

### 2.1 Counts, exposure and fills

| item | old rebuild |
|---|---:|
| signal days (unfiltered) | 41 |
| entries | 38 |
| fills | 153 |
| TQQQ minutes | 7.36% |
| average TQQQ weight | 7.36% |
| average gross leverage | 0.22x |
| average hold | 3.9 sessions |
| exits | 15 stop, 4 recovery, 19 time |

The strategy was **long TQQQ only 7.4% of the time**, but at 100% notional per
event. It was flat/BIL the rest of the time. The old result was not a
low-exposure cash drag; it was a concentrated series of bad event days.

### 2.2 The signal has a one-day pop and no five-day edge

Forward TQQQ return from the next open after a signal, 2016-2023:

| horizon | signal mean | unconditional | signal hit | bootstrap p |
|---|---:|---:|---:|---:|
| 1 day | +0.47% | +0.10% | 61.0% | 0.23 |
| 3 days | +0.39% | +0.50% | 51.2% | 0.54 |
| 5 days | +0.93% | +0.91% | 58.5% | 0.51 |
| 10 days | +0.71% | +1.93% | 63.4% | 0.74 |

Only the first day is above the unconditional base, and even that is not
significant. The five-day hold has no return driver; it adds crash exposure.

### 2.3 The 8% stop and the next-open exit did the damage

The average trade was **-1.75%**; 25 of 38 lost. The worst:

| signal | entry | exit | return | note |
|---|---|---|---:|---|
| 2020-02-28 | 2020-03-02 | 2020-03-09 | **-22.4%** | 8% stop could not fill; weekend/COVID gap |
| 2022-05-02 | 2022-05-03 | 2022-05-09 | -14.7% | stop through a fast decline |
| 2018-10-08 | 2018-10-09 | 2018-10-11 | -13.6% | stop through a fast decline |
| 2022-04-18 | 2022-04-19 | 2022-04-25 | -12.7% | stop through a fast decline |
| 2018-02-06 | 2018-02-07 | 2018-02-09 | -11.7% | stop through a fast decline |

An 8% TQQQ stop is only ~2.7% on QQQ. At TQQQ's 3x daily volatility it is hit
by ordinary path noise, and the fill can be far below the stop. The
"exit at the fifth session close" also filled at the next open, adding an
overnight gap; the 2020-03-09 exit alone cost about -20%.

### 2.4 Regime concentration

The old book's per-year returns: 2016 +4.3%, 2017 -0.9%, 2018 -6.1%, 2019
-9.9%, 2020 -24.4%, 2021 +10.0%, 2022 -39.4%, 2023 +4.4%. The 2022 cluster
(12 of 41 signals) compounded -39.8%; 2020 added -24.4%. Failed breakdowns in
a bear/crisis tape are continuations, not springs.

---

## 3. What the repair changed

- **Trend filter:** QQQ close > 200-day SMA. This is the single most important
  filter. The no-trend 1-day neighbour (`h1_vol_stop8_close`) earns 0.88% with
  a 30.2% drawdown and a 0.15 Sharpe; the trend version with no vol cap
  (`h1_trend_stop8_close`) earns 2.40% with a 24.5% drawdown and a 0.39 Sharpe.
- **Volatility cap:** 20-day realised vol < 30%. It adds about +0.7 pp of CAGR
  and +0.13 Sharpe to the 1-day trend version with the stop (2.40% → 3.13%);
  the no-stop trend version is 3.36%.
- **Horizon:** one session. The 3-day and 5-day holds are weaker (1.72% and
  1.85% CAGR with 25-27% drawdowns) and the 5-day 8% stop version is
  approximately flat (+0.01% CAGR) with a 34% drawdown. The edge is a one-day
  pop, not a five-day drift.
- **Exit:** 15:59 open instead of next open. This removes the overnight gap
  after the exit decision. It is the difference between the old -9.25% and the
  positive repair, but it does not create an edge.
- **Stop:** an 8% intraday stop does **not** help at the one-day horizon:
  3.13% / 24.45% / 0.52 versus 3.36% / 23.37% / 0.54 without it. The only stop
  in the sample is 2021-12-02, and it fills at -7.89% versus -6.23% for the
  time exit. Earlier exploratory work showed 4.02% for the stop variant; that
  number came from letting a 15:59 stop fill at the next open, which is an
  overnight exposure inconsistent with the close-exit design. The corrected,
  flat-overnight result is the 3.13% above. The stop is not the repair.

---

## 4. Grid and plateau

All 8 pre-registered variants, 1 bp headline (5/10 bp in `result.json`):

| variant | signals | entries | CAGR | max DD | Sharpe | TQQQ time | 5 bp CAGR | 10 bp CAGR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `orig` | 41 | 38 | -9.25% | 63.09% | -0.27 | 7.36% | -9.94% | -10.80% |
| `h5_trend_vol_stop12_close` | 24 | 22 | 1.85% | 27.17% | 0.20 | 4.86% | 1.39% | 0.83% |
| `h5_trend_vol_stop8_close` | 24 | 22 | 0.01% | 34.15% | 0.08 | 4.61% | -0.43% | -0.99% |
| **`h1_trend_vol_nostop_close`** | 24 | 23 | **3.36%** | **23.37%** | **0.54** | 1.14% | 2.88% | 2.28% |
| `h1_trend_vol_stop8_close` | 24 | 23 | 3.13% | 24.45% | 0.52 | 1.11% | 2.65% | 2.05% |
| `h3_trend_vol_stop8_close` | 24 | 22 | 1.72% | 25.56% | 0.20 | 2.80% | 1.27% | 0.71% |
| `h1_vol_stop8_close` | 32 | 31 | 0.88% | 30.15% | 0.15 | 1.46% | 0.25% | -0.53% |
| `h1_trend_stop8_close` | 26 | 25 | 2.40% | 24.45% | 0.39 | 1.19% | 1.88% | 1.24% |

The plateau has the right shape: one-day holds beat 3/5-day holds; the trend
filter is essential; the vol cap helps; the 8% stop is not useful. **The best
cell is the primary, and it is still only a 0.54 Sharpe with a 23.4%
drawdown.** Nothing in the grid is close to the static mix's 1.13 Sharpe and
2.11% drawdown at the same exposure.

The filtered event study is also weak: 1-day +0.61% vs +0.10% unconditional
(p = 0.22), 3-day +0.74% vs +0.50% (p = 0.43), 5-day +1.07% vs +0.91%
(p = 0.48), 10-day +1.66% vs +1.93% (p = 0.56). The 24 filtered events do not
establish a significant edge.

### Per-year and sub-periods (primary)

| year | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| primary | +0.1% | +3.5% | +0.8% | +4.1% | +10.6% | -12.1% | +6.5% | +15.4% |
| stop neighbour | +0.1% | +3.5% | +0.8% | +4.1% | +10.6% | -13.6% | +6.5% | +15.4% |

| sub-period | primary CAGR | stop neighbour CAGR |
|---|---:|---:|
| 2016-2019 | +2.16% | +2.16% |
| 2020-2021 | -1.35% | -2.24% |
| 2022-2023 | +10.87% | +10.87% |

The 2021 drawdown (-7.63%, -3.06%, -0.89%, -5.00%, -6.23% time exits) is the
23% max DD. The result is carried by 2020 and 2023; it is not a stable
year-in, year-out return stream.

Daily-return correlation of the primary: **0.17 to the 165-day baseline** and
**0.12 to QQQ**. The low correlation is real, but it does not compensate for
the drawdown: the strategy is a concentrated long-TQQQ event book, not a
diversifying return source.

---

## 5. Verdict

**Retired as a standalone strategy.**

- The repair is honest: it keeps the signal, removes the two implementation
  errors (too-tight stop, next-open exit) and adds the filters the diagnosis
  called for. It improves -9.25% / 63% DD to +3.36% / 23% DD.
- But the improvement is not an edge. The best variant has a 0.54 Sharpe and a
  23% drawdown; a static 1.14% TQQQ / 98.86% BIL mix has a 1.13 Sharpe and a
  2.11% drawdown. The event book is a concentrated, worse risk-adjusted way to
  hold the same average TQQQ exposure.
- The event study's only positive horizon is one day, and it is not
  statistically significant. There is no five-day spring drift to harvest.
- The old strategy's real value is as an **overlay on the 165-day QQQ→TQQQ
  base**, which is what the original agent was. It is not an independent
  return source.

Do not promote. Do not run the 2024-2026 holdout for this rebuild; the dev
result already fails the standalone bar. If the overlay is to be revisited,
the right test is on the 165-day base, not as a standalone.

---

## 6. Reproduction and caveats

```
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
python research/new/drawdown-stop-overlay-v2/strategy.py
```

- Development only; the 2024-2026 panel is never sliced. `bt.panel` is called
  with `end=2023-12-29`.
- 1-minute marks, next-open fills, 2% band. The "close" exit sets the target
  at the 15:58 bar and fills at the 15:59 open; this is the closest the
  long-only next-open engine can get to a market-on-close exit. Intraday stops
  are scanned only through 15:58, so the book is flat overnight.
- The original rebuild's 41 signals / 38 entries / 153 fills / -9.25% is
  reproduced exactly by `orig`.
- The 165-day baseline is a benchmark/correlation reference only; no old base
  weights are used by the signal.
- The 20-day lookback, 0.50 range, 200-day trend and 30% vol cap are own
  choices; the grid is the overfitting guard, and the plateau is reported.
