# Intraday volume asymmetry: development report

**Family:** `family-volume-skew` (reserve family). Primary mechanism: the
asymmetry of QQQ's intraday volume distribution is a fragility state; hold
TQQQ for the next session when down-volume dominates its recent distribution,
stay in cash when up-volume dominance is crowded.

**Verdict: passes every kill criterion, including the above-TQQQ CAGR bar at
1 bp: 42.02% CAGR vs 36.72%, with a 34.84% max drawdown vs 82.29% and Sharpe
1.21 vs 0.82. The honest caveats are that the headline is sensitive to 2020
(ex-2020 CAGR 34.16%, just below the bar), the signal is partly a volume-
weighted short-term reversal (0.450 correlation with `family-short-reversal`),
and 10 bp costs cut CAGR to 19.33%. It is the strongest of the three reserve
families.**

Development window 2016-01-04 .. 2023-12-29, 1-minute marks, next-open fills,
2% band, long-only, weights >= 0, sum <= 1. The panel is requested with
`end=2023-12-29`; no 2024-2026 bar is used. The signal uses QQQ minute volume;
the position is TQQQ.

---

## 1. Headline

| | CAGR | Max DD | Sharpe | Sortino | Vol | Bar-time exposure | Fills | Turnover | Ending equity |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Primary, 1 bp** | **42.02%** | **34.84%** | **1.21** | **1.73** | 34.0% | 38.41% | 1,544 | 7,237x | $1,645,749 |
| Primary, 2 bp | 39.30% | 35.23% | 1.15 | 1.64 | 34.0% | 38.41% | 1,544 | 6,487x | $1,410,291 |
| Primary, 5 bp | 31.45% | 36.39% | 0.98 | 1.40 | 34.0% | 38.41% | 1,544 | 4,718x | $887,449 |
| Primary, 10 bp | 19.33% | 42.32% | 0.69 | 0.99 | 34.0% | 38.41% | 1,544 | 2,876x | $410,079 |
| Primary, 0 bp (gross) | 44.79% | 34.45% | 1.26 | 1.81 | 34.0% | 38.41% | 1,544 | 8,086x | $1,920,519 |
| TQQQ buy & hold (sim) | 36.15% | 82.29% | 0.80 | 1.12 | 66.5% | 100% | 1 | 1x | $1,175,283 |
| TQQQ bar from the brief | 36.72% | 82.29% | 0.82 | -- | -- | 100% | -- | -- | -- |

- At 1 bp the strategy is **+5.30 pp above** the TQQQ CAGR bar and cuts max
  drawdown by **47.5 pp** (34.84% vs 82.29%). Sharpe is 1.21 vs 0.82.
- At 2 bp it is still above the bar (+2.58 pp). At 5 bp it is 5.27 pp below
  (31.45%); at 10 bp it is 19.33%. The result is cost-sensitive because the
  book trades every held day.
- Exposure is **38.41% of 1-minute bars** and **10.5% of calendar time**
  (781 signals, 772 events, day session only). The rest is cash.
- Daily correlation to TQQQ is **0.489**. This is a high-exposure TQQQ
  strategy, not a small sleeve; the drawdown reduction comes from being out of
  the worst sessions.
- Max drawdown episode: **2022-01-19 -> 2022-04-25, 34.84%**. The strategy
  still finished 2022 at +25.5%; the drawdown is an early-year giveback.

---

## 2. What it is

Universe: QQQ (signal), TQQQ (position), cash.

At 15:59 ET on session `d`:

```
U_d = sum(volume of 1-min bars with close > open)
D_d = sum(volume of 1-min bars with close < open)
A_d = (U_d - D_d) / (U_d + D_d)
ref_d = 40th percentile of A over the prior 60 full sessions
```

If `A_d < ref_d`, buy TQQQ at the next session's **09:30 open** and sell at
that session's **15:59 open**. Otherwise hold cash. No overnight position.

**Clock.** The signal is fixed at 15:59:00 on `d`, after all 390 bars are
complete. The reference uses `d-60 .. d-1` only; the current value is excluded.
The entry is the next 09:30 open; the exit is the next 15:59 open (target zero
at the 15:58 close). There is no same-bar fill and no future data.

Only 390-bar sessions are eligible. Half-days are skipped; they still update
the previous close.

---

## 3. Event statistics

772 events over 8 years, **96.7 events/year**. Per-event TQQQ return, next
09:30 open to next 15:59 open:

| Metric | Value |
|---|---:|
| Events | 772 |
| Mean | **+44.1 bp** |
| Median | +50.1 bp |
| Win rate | 58.4% |
| t-stat | **3.60** |
| Worst | -1,237.4 bp |
| Best | +2,146.7 bp |
| Sum of log returns | +2.955 |

The mean is supported by the median and the win rate; the t-stat is 3.60. The
best event is +21.5% and the worst -12.4%, both real TQQQ day moves.

---

## 4. Why the signal, not price, volume level or volatility

| Control | CAGR | Max DD | Sharpe | Fills | What it says |
|---|---:|---:|---:|---:|---|
| **Volume asymmetry < q0.40** | **42.02%** | **34.84%** | **1.21** | 1,544 | The strategy. |
| Breadth (equal-weight up/down bars) < q0.40 | 31.22% | 30.70% | 0.98 | 1,528 | Volume weighting adds 10.8 pp CAGR and 0.23 Sharpe over an equal-weight count. |
| Price-only return < q0.40 | 9.78% | 62.35% | 0.45 | 1,554 | The signal is not just "buy after a down day". |
| Total volume < q0.40 | 6.73% | 48.08% | 0.38 | 1,686 | Volume level is not the driver. |
| Realized 5-min vol < q0.40 | -2.78% | 59.73% | 0.01 | 1,698 | Volatility is not the driver. |
| Top-5% volume concentration < q0.40 | -4.28% | 68.30% | 0.06 | 1,486 | Concentration is not the driver. |
| Minute-volume skew < q0.40 | -0.42% | 68.99% | 0.16 | 1,554 | Distribution skew alone is not the driver. |
| Stale signal | 5.80% | 70.44% | 0.34 | 1,536 | The same-day volume is doing the work. |
| All full sessions, day-only | 2.40% | 71.52% | 0.30 | 3,938 | TQQQ's return is mostly overnight; the day-only book is not beta. |
| Buy & hold TQQQ | 36.15% | 82.29% | 0.80 | 1 | The absolute-return bar. |

The controls are decisive: the price-only version earns 9.78% with a 62.4%
drawdown, the volume-level version 6.73%, and the realized-vol version -2.78%.
The volume asymmetry is the object doing the work. The breadth control is the
closest competitor at 31.22% / 30.70% / 0.98; the volume weighting is what
lifts the strategy above the TQQQ bar.

The continuation sign is a strong negative control: holding when `A` is above
its 60th percentile earns **-19.31% CAGR with an 89.8% drawdown** (Sharpe
-0.60). The fragility direction is the right one in this sample.

---

## 5. Robustness

### 5.1 Pre-registered grid (8 cells)

All cells use the next-session 09:30 -> 15:59 clock and TQQQ 1.0. The centre is
cell 6.

| Cell | Lookback | Percentile | 1 bp CAGR | 1 bp DD | 1 bp Sharpe | 5 bp CAGR | Fills |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 20 | 0.30 | 28.77% | 36.43% | 0.99 | 21.22% | 1,206 |
| 2 | 20 | 0.40 | 41.04% | 44.26% | 1.19 | 30.37% | 1,570 |
| 3 | 40 | 0.30 | 38.20% | 34.72% | 1.22 | 30.17% | 1,196 |
| 4 | 40 | 0.40 | 41.93% | 33.06% | 1.20 | 31.30% | 1,554 |
| 5 | 60 | 0.30 | 35.69% | 33.73% | 1.15 | 27.93% | 1,176 |
| **6** | **60** | **0.40** | **42.02%** | **34.84%** | **1.21** | **31.45%** | **1,544** |
| 7 | 100 | 0.30 | 30.04% | 30.29% | 1.01 | 22.79% | 1,146 |
| 8 | 100 | 0.40 | 32.18% | 34.84% | 0.99 | 22.36% | 1,540 |

**8/8 cells are positive at 1 bp and 8/8 at 5 bp.** The 1 bp CAGR range is
28.8% to 42.0%; 4 of 8 cells are above the 36.72% TQQQ bar at 1 bp. The 20/0.30
cell is the weak spot (28.77%). The plateau is broad in sign and level, and the
centre is not a knife-edge: 40/0.40 is nearly identical.

### 5.2 Neighbours (not used to choose the centre)

| Neighbour | 1 bp CAGR | 1 bp DD | Sharpe | 5 bp CAGR | 10 bp CAGR |
|---|---:|---:|---:|---:|---:|
| q 0.35 | 40.82% | 35.10% | 1.22 | 31.57% | 20.86% |
| q 0.45 | 34.84% | 38.14% | 1.01 | 23.46% | 10.58% |
| Look 30 | 36.83% | 32.50% | 1.09 | 26.57% | 14.82% |
| Look 80 | 38.05% | 35.00% | 1.12 | 27.69% | 15.82% |
| Look 120 | 33.27% | 35.46% | 1.02 | 23.44% | 12.16% |
| Hold 2 sessions | 29.54% | 54.25% | 0.83 | 14.29% | -2.27% |
| Size 0.50 | 20.96% | 17.94% | 1.21 | 16.34% | 10.83% |
| QQQ execution | 12.61% | 12.84% | 1.12 | 4.23% | -5.38% |

The result is stable to the percentile (0.35-0.45) and the lookback (30-120).
A two-session hold is much worse (29.54% CAGR, 54.25% DD), so the effect is a
one-session rebalancing, not a persistent regime. QQQ execution has the same
Sharpe (1.12) with a much lower drawdown (12.84%), confirming that TQQQ is a
capital-efficiency choice.

### 5.3 Placebo

| Placebo | Draws | Real CAGR | Placebo mean | Placebo p95 | Max | p-value | Real DD percentile |
|---|---:|---:|---:|---:|---:|---:|---:|
| Random days, same count, same clock | 200 | 42.02% | 1.48% | 14.45% | 23.59% | **0.000** | 100.0% |

The real result beats all 200 random-day draws; the best random draw is
23.59% CAGR, 18.4 pp below the strategy. The real drawdown is better than
every random draw. The volume asymmetry is selecting the days, not riding beta.

### 5.4 Subperiods and yearly

| Period | CAGR | Max DD |
|---|---:|---:|
| 2016-2019 | 19.80% | 29.54% |
| 2020-2021 | 84.04% | 24.59% |
| 2022-2023 | 54.36% | 34.84% |

| Year | Strategy | TQQQ |
|---|---:|---:|
| 2016 | +33.53% | +19.86% |
| 2017 | +38.42% | +114.54% |
| 2018 | **-8.32%** | -20.76% |
| 2019 | +21.71% | +148.23% |
| 2020 | **+111.86%** | +104.14% |
| 2021 | +59.55% | +81.05% |
| 2022 | +25.48% | -79.39% |
| 2023 | +88.70% | +192.05% |

The strategy is positive in 7 of 8 calendar years and all 3 subperiods. 2018
is the only loss (-8.3%). 2020 is the dominant year (+111.9%) and the reason
the headline is above the TQQQ bar; the report does not hide that.

### 5.5 Cut tests

| Cut | Strategy CAGR | Strategy DD | TQQQ ex-year CAGR |
|---|---:|---:|---:|
| ex-2016 | 43.28% | 32.98% | 38.66% |
| ex-2017 | 42.60% | 32.98% | 27.06% |
| ex-2018 | 51.21% | 32.98% | 46.60% |
| ex-2019 | 45.22% | 35.76% | 25.90% |
| ex-2020 | **34.16%** | 32.98% | 27.84% |
| ex-2021 | 39.70% | 35.83% | 30.34% |
| ex-2022 | 44.56% | 26.74% | 77.75% |
| ex-2023 | 36.33% | 32.98% | 21.49% |

No single year carries the result: the cut range is 34.16% to 51.21%.
**Excluding 2020 lowers CAGR to 34.16%, just below the 36.72% bar**, while
Sharpe remains around 1.0. The above-TQQQ claim is therefore sensitive to the
2020 rebound year; the strategy is still a strong risk-adjusted performer
without it.

---

## 6. Correlation to the nine current winners

Daily returns, 2016-01-04 .. 2023-12-29, 2,011 overlapping days.

| Winner | Correlation |
|---|---:|
| ratio-froth | 0.357 |
| vol-scaled-crash-stop | 0.456 |
| relative-value-tqqq | 0.469 |
| fomc-opex-window | 0.347 |
| family-session-timing | 0.231 |
| family-short-reversal | **0.450** |
| family-rebalance-flow | **0.514** |
| family-intraday-microstructure-day | 0.320 |
| family-ml-microstructure | 0.441 |

Range **0.231 .. 0.514**, below the 0.70 independence gate. The highest
correlation is with `family-rebalance-flow` (0.514); the short-reversal
correlation is 0.450. The signal is a volume-weighted reversal/fragility
measure, so this overlap is expected. Extra archive correlations:
`overnight-drift-filter` 0.463, `family-volume-clock` 0.127,
`family-realized-skew` 0.430, `family-gap-continuation` 0.158.

---

## 7. Kill criteria

| Criterion | Value | Failed? |
|---|---:|---|
| 1 bp CAGR below 36.72% TQQQ bar | 42.02% | **pass** |
| 5 bp CAGR below 0 | 31.45% | pass |
| Fewer than 30 independent events | 772 | pass |
| Fewer than 100 fills | 1,544 | pass |
| Fewer than 6/8 grid cells positive at 1 bp | 8/8 | pass |
| Negative CAGR in 2+ of 3 subperiods | 0 of 3 | pass |
| Placebo random-day p-value > 0.10 | 0.000 | pass |
| Correlation > 0.70 with a winner | 0.514 | pass |
| Weight drift before a truncation cut | 0.0 | pass |

**All nine criteria pass.** This is the only one of the three reserve families
that clears the above-TQQQ CAGR bar.

---

## 8. Risks and limitations

1. **2020 dependence.** Ex-2020 CAGR is 34.16%, below the 36.72% bar. The
   headline above-TQQQ claim depends on the 2020 rebound. The strategy is still
   positive and high-Sharpe without it, but the margin is thin.
2. **Reversal overlap.** The signal is a volume-weighted breadth measure. The
   same-day price/return correlation is 0.476, and the correlation with
   `family-short-reversal` is 0.450. The price-only control (9.78%) and the
   equal-weight breadth control (31.22%) show that volume weighting adds
   materially, but this is not an independent factor. It passes the 0.70 gate.
3. **Cost sensitivity.** At 5 bp CAGR is 31.45% (below the bar); at 10 bp it is
   19.33%. Turnover is 7,237x initial equity over 8 years (~900x/yr). A real
   implementation with market impact above the flat-bps model would erode the
   edge.
4. **2018 loss.** The only negative year is 2018 (-8.3%), with a 62% drawdown
   in the price-only control but a 34.8% max DD in the strategy. A sustained
   choppy market is the weak regime.
5. **TQQQ 3x.** The book is 100% TQQQ on 38% of days. The 2% band and 1 bp cost
   model do not capture a gap through a stop; there is no stop. The QQQ
   execution variant has a much lower drawdown (12.84%) and the same Sharpe
   (1.12), which is the conservative implementation.
6. **Volume data.** QQQ minute volume is unadjusted for splits, but the
   signal is a within-day ratio, so splits cancel. The 2016-2020 archive has
   occasional after-hours prints; `bt.load_1m` filters to 09:30-16:00 and
   half-days after 13:00. The result survives lookbacks of 20-120 sessions.

---

## 9. Verdict

**Pass on every kill criterion, including the above-TQQQ CAGR bar at 1 bp.**
The intraday up/down volume asymmetry is a real fragility signal in this
sample: low asymmetry days earn +44.1 bp per next session (t = 3.60), the
continuation sign loses 19.3% CAGR, and the price-only, volume-level and
realized-vol controls are far weaker. The strategy is a volume-weighted
reversal/fragility book, not a pure independent factor; its 0.450 correlation
with `family-short-reversal` and its 2020 dependence are the reasons to treat
it as a strong reserve/winner candidate rather than a guaranteed replacement
for TQQQ. At 1 bp it is the best of the three reserve families and the only one
that clears the programme's absolute-return bar.
