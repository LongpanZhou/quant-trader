# Turn-of-month TQQQ — development report

**Verdict: mechanically passes the development bar, but the edge is fragile
and is not a clean turn-of-month effect. Treat it as a defensive calendar
tilt, not a robust standalone replacement for TQQQ.**

Dev 2016-01-04..2023-12-29, 1-minute marks, next-open fills, 2% band:

| | CAGR | Max DD | Sharpe | Sortino | TQQQ weight | Fills |
|---|---:|---:|---:|---:|---:|---:|
| **Strategy, 1 bp** | **41.41%** | **49.21%** | **0.98** | **1.39** | 52.3% | 387 |
| Strategy, 5 bp | 38.69% | 50.02% | 0.94 | 1.33 | 52.3% | 387 |
| Strategy, 10 bp | 35.37% | 51.01% | 0.89 | 1.26 | 52.3% | 387 |
| TQQQ buy & hold (local 1m marks) | 36.15% | 82.29% | 0.80 | — | 100% | 1 |
| TQQQ bar from the brief | 36.72% | 82.29% | 0.82 | — | 100% | — |

Daily-return correlation to TQQQ: **0.721**. Ending equity **$1.59M** from
$100k at 1 bp. Turnover **1832x** initial equity over 8 years (~229x/yr; about
24 round trips a year). Max drawdown window: **2022-03-03 → 2022-12-28**.

The headline is a **+4.69 pp** CAGR beat over the 36.72% bar and a **33.08 pp**
drawdown reduction. It clears the bar at 1 bp and 5 bp; at 10 bp it falls
1.35 pp short. The rest of this report explains why the headline is weaker
than it looks.

---

## 1. Exact rules

Universe: QQQ (volatility input only), TQQQ (position), BIL (idle).

For each session `k`, with `pe(k)` = sessions from the end of its month
(0 = last session) and `ps(k)` = sessions from the start (0 = first):

```
in_window(k) = (pe(k) <= 4) or (ps(k) <= 5)     # last 5 + first 6 sessions
w(k) = 1.0 if in_window(k) else 0.0
```

- The decision for session `k` is taken at the 15:59 close of session `k-1`;
  fill at the next open. The harness's next-open rule is unchanged.
- Idle weight is BIL. QQQ is never held.
- No volatility throttle in the delivered centre. The optional throttle,
  `min(1, 0.75 / sigma20)`, is tested in section 3 and rejected.
- The 20-day vol for the throttle variant is warmed with TQQQ daily closes
  from 2015-01-02..2015-12-31; the strategy is live on 2016-01-04.
- No 2024+ bar is loaded. The panel ends 2023-12-29.

The window is **11 sessions** out of a typical 19-23 session month, about
**52% of sessions**. This is much wider than the classic "last 2 + first 3"
window, and that is the first warning sign.

## 2. The calendar effect is real, but modest

TQQQ open-to-open returns on held vs unheld sessions (daily marks, the
quantity the harness actually earns):

| | n | mean | sd | t | hit rate |
|---|---:|---:|---:|---:|---:|
| In-window sessions | 1,055 | **+35.1 bp** | 416 bp | **2.74** | 56.8% |
| Out-of-window sessions | 956 | +5.4 bp | 419 bp | 0.41 | 55.1% |

The turn-of-month days do carry a statistically visible premium. A random
11-session contiguous block in every month, with the same construction, is
much weaker:

| Placebo, 300 draws | CAGR |
|---|---:|
| Real centre (daily marks) | **41.42%** |
| Random mean | 12.56% |
| Random p95 | 30.71% |
| Random p99 | 41.58% |
| Random max | 50.70% |
| p-value | **0.013** |

So the *position* of the window matters, not just being out of the market.
That is the strongest positive evidence in this report.

But the strategy's monthly record against TQQQ is poor:

| Monthly strategy − TQQQ, 96 months | |
|---|---:|
| Mean excess | **−0.61%** |
| Median excess | **−3.11%** |
| t-stat | −0.49 |
| Win rate | **41.7%** |

The strategy **loses to TQQQ in 58% of months**. It wins over the full period
because it has a lower mean daily return *and much lower volatility*:

| | Strategy | TQQQ |
|---|---:|---:|
| Mean daily return | 18.5 bp | 21.5 bp |
| Total log return, 2016-2023 | **276.6%** | 245.4% |
| Top-10 days' share of total log | 49.3% | — |

This is a vol-drag / drawdown-avoidance result, not a "more return per day"
result. That matters for the holdout: in a steady bull the strategy should
lag, and it needs a drawdown or a persistent calendar premium to win.

## 3. The plateau is an island, not a plateau

Pre-registered grid (8 cells) and the immediate no-throttle neighbours:

| L | F | throttle | CAGR | Max DD | Sharpe | verdict |
|---:|---:|---:|---:|---:|---:|---|
| 3 | 5 | 0.75 | 25.42% | 35.07% | 0.82 | fail |
| 3 | 6 | 0.75 | 30.82% | 39.29% | 0.91 | fail |
| 4 | 6 | 0.75 | 30.97% | 52.85% | 0.89 | fail |
| 5 | 5 | 0.75 | 32.06% | 44.12% | 0.91 | fail |
| **5** | **6** | **none** | **41.41%** | **49.21%** | **0.98** | **pass** |
| 5 | 7 | 0.75 | 40.54% | 53.73% | 1.01 | pass |
| 5 | 6 | 0.60 | 36.07% | 35.86% | 1.02 | fail 1 bp |
| 5 | 6 | 0.75 | 37.75% | 42.35% | 0.99 | pass 1 bp, fail 5 bp |

No-throttle window neighbours (same 1m construction):

| L | F | CAGR | Max DD | Sharpe | verdict |
|---:|---:|---:|---:|---:|---|
| 5 | 4 | 34.90% | 43.53% | 0.93 | fail |
| 5 | 5 | 34.84% | 49.79% | 0.90 | fail |
| **5** | **6** | **41.41%** | **49.21%** | **0.98** | **centre** |
| 5 | 7 | 42.00% | 63.11% | 0.96 | pass CAGR, DD >60 |
| 4 | 7 | 34.21% | 69.11% | 0.86 | fail |
| 6 | 6 | 21.43% | 54.51% | 0.64 | fail |
| 6 | 7 | 21.94% | 66.68% | 0.65 | fail |
| 3 | 11 | 44.39% | 62.89% | 0.94 | pass CAGR, DD >60 |

Two cliffs matter:

- **L = 5 → 6 collapses 41.4% → 21.4%.** Adding one session per month
  (the 6th-to-last) destroys the result. This is the single most important
  fragility in the strategy.
- **F = 5 → 6 jumps 34.8% → 41.4%.** Adding the 6th session of the month
  adds about 6.6 pp of CAGR.

The pre-registered 5-day window is far below the bar: the pilot's
last-2 + first-3 portfolio compounds at about **15%** CAGR. The strategy only
passes by holding roughly half the month, which is no longer a narrow
turn-of-month window.

The volatility-throttle scan is smooth (0.50 → 32.9%, 0.60 → 36.1%,
0.75 → 37.8%, none → 41.4%), but the throttle **always costs CAGR**; the
0.60 version fails at 1 bp and the 0.75 version fails at 5 bp. It is reported
as a rejected optional overlay, not used in the centre.

The grid and neighbours in `result.json` show the local landscape; a wider
pilot scan (last 1-11 x first 0-11) was used only to choose the centre and is
not a selection claim. The passing cells are a narrow ridge around L=5,
F=6-7, not a broad plateau.

## 4. The `pe=5` problem: what is really driving the result

The L=5 boundary excludes `pe=5`, the sixth-to-last session of the month.
That session is extraordinarily bad in this sample:

| `pe=5` open-to-open, 96 months | |
|---|---:|
| Mean | **−116.7 bp** |
| Median | −53.7 bp |
| t-stat | −2.77 |
| Worst dates | 2020-02-21 (−1479 bp), 2018-12-21 (−1268 bp), 2020-09-23 (−1149 bp), 2020-01-24 (−1034 bp), 2022-04-22 (−941 bp), 2018-10-24 (−929 bp), 2016-06-23 (−918 bp), 2023-08-24 (−844 bp) |

Those are recognizable crash days, not a smooth mid-month effect. The
decomposition is decisive:

| Control (daily bars) | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| Hold TQQQ all days | 35.78% | 81.68% | 0.80 |
| Hold all days **except `pe=5`** | **57.35%** | 79.35% | 1.03 |
| Hold **only `pe=5`** | −13.35% | 69.86% | −0.89 |
| Hold **only the mid-month complement** of the window | −3.58% | 79.47% | 0.16 |
| Constant 52.3% TQQQ exposure | 25.25% | 55.17% | 0.82 |
| **Centre (L5 F6)** | **41.41%** | **49.21%** | **0.98** |

The **dominant calendar effect in this sample is the mid-month crash
cluster**, not the turn-of-month window. The TOM window inherits part of it
simply by excluding `pe=5`; the BIL sleeve then cuts the drawdown. The
constant-exposure control confirms that the *timing* adds about 16 pp of CAGR
over the same average exposure, so this is not pure leverage — but the timing
value is concentrated in the `pe=5` exclusion.

This is the main reason to distrust the headline. A strategy whose L=5
boundary is worth 20 pp of CAGR is not a broad calendar effect.

## 5. Yearly, subperiods, cut tests

| Year | Strategy | TQQQ |
|---|---:|---:|
| 2016 | −15.7% | +19.9% |
| 2017 | +62.0% | +114.5% |
| 2018 | +30.3% | −20.8% |
| 2019 | +48.7% | +148.2% |
| 2020 | +217.6% | +104.1% |
| 2021 | +19.5% | +81.1% |
| 2022 | −42.5% | −79.4% |
| 2023 | +163.7% | +192.0% |

| Subperiod | Strategy CAGR / DD | TQQQ CAGR |
|---|---:|---:|
| 2016-2019 | **26.64% / 38.36%** | **49.97%** |
| 2020-2023 | **56.93% / 49.21%** | **22.13%** |

The strategy **underperforms TQQQ by 23 pp a year in 2016-2019** and
outperforms by 35 pp a year in 2020-2023. The full-period beat is a
2020-2023 phenomenon: the 2022 crash avoidance plus the 2020 rebound.

Cut tests (daily returns compounded with one period removed):

| Cut | Strategy CAGR | Max DD |
|---|---:|---:|
| Ex-2016 | 52.29% | 48.12% |
| Ex-2020 | **25.50%** | 48.12% |
| Ex-2022 | 60.50% | 36.43% |
| Ex-2023 | **28.92%** | 48.12% |
| Drop best month 2020-04 | 37.27% | 48.12% |
| Drop best month 2022-07 | 38.00% | 58.43% |

Removing **either 2020 or 2023** puts the strategy below the 36.72% bar.
Removing the single best month still leaves 37.3%, so it is not one month —
but it is two years.

Best months: 2020-04 (+30.3% vs +45.7%), 2020-07 (+30.2% vs +22.5%),
2020-11 (+26.7% vs +34.7%), 2022-07 (+24.8% vs +39.4%),
2018-11 (+21.0% vs −2.7%).
Worst months: 2016-02 (−24.1% vs −5.9%), 2022-04 (−23.5% vs −37.3%),
2018-02 (−21.7% vs −6.2%), 2019-05 (−17.3% vs −24.1%),
2022-08 (−14.1% vs −16.6%).

## 6. Costs, execution, causality

- **1 bp:** 41.41% CAGR, 49.21% DD, 0.98 Sharpe.
- **5 bp:** 38.69% CAGR, 50.02% DD, 0.94 Sharpe — still passes.
- **10 bp:** 35.37% CAGR, 51.01% DD, 0.89 Sharpe — fails the 36.72% bar by
  1.35 pp.
- 387 fills, 1832x initial-equity turnover, ~24 round trips/year. The 2% band
  and the 11-session window keep trading moderate.
- The causality truncation test passes: rebuilding the weights on a panel
  truncated at 2022-01-03 leaves every weight before 2021-12-29 unchanged.
- The `pe`/`ps` labels use the exchange session calendar (known in advance),
  not future prices. The vol throttle, when enabled, uses only returns through
  the prior close.
- No 2024+ bar is loaded or inspected.

## 7. Holdout arithmetic

The brief's full-period TQQQ 2016-2026 CAGR is 37.54%. The dev TQQQ CAGR is
36.72% over 8 years; the holdout is about 2.8 years. That implies a
**~39.9% holdout TQQQ CAGR**.

At the strategy's 41.41% dev CAGR, the strategy needs **~27.1% in the
holdout** to beat 37.54% for the full period. A 52%-exposed strategy with no
alpha in a 40% bull makes roughly 21%; with the calendar premium persisting,
25-35% is plausible. If the holdout contains a drawdown, the BIL sleeve wins
easily.

So the strategy has a *conditional* chance, not a comfortable one. It is a
defensive bet on a drawdown or a persistent calendar premium, not a high-CAGR
replacement for TQQQ.

## 8. Honest verdict

**What passes:** the mechanical dev bar. CAGR 41.41% > 36.72%, max DD 49.21%
< 82.29% (and < 60%), Sharpe 0.98 > 0.82, at 1 bp and 5 bp. The calendar
effect is real: held sessions earn +35 bp/day versus +5 bp unheld, the
random-window placebo is beaten at p = 0.013, and the same-average-exposure
control is 16 pp worse.

**What does not:** the robustness story.

1. The monthly excess vs TQQQ is **negative** (−0.61% mean, 41.7% win rate).
   The strategy wins on volatility and drawdown, not on monthly batting
   average.
2. The **2016-2019 subperiod underperforms TQQQ by 23 pp a year**. The
   full-period beat is a 2020-2023 phenomenon.
3. Removing **2020 or 2023** drops the CAGR to 25.5% / 28.9%, below the bar.
4. The L=5 boundary excludes a single **`pe=5`** session whose −117 bp mean is
   a cluster of crash days; L=6 collapses to 21.4%. That is a knife-edge, not
   a plateau.
5. The classic 5-day turn-of-month window is only ~15% CAGR. The strategy
   passes only by holding about half the month, which is really a
   "skip the mid-month" strategy with a BIL sleeve.
6. At 10 bp costs it fails the bar.

**Recommendation:** keep it as a defensive calendar tilt / diversifier, not
as a standalone TQQQ replacement. If the lead wants a high-CAGR candidate for
the one-shot holdout, this is not it. If the lead wants a low-drawdown
calendar strategy and is willing to accept that the edge is concentrated in
2020/2023 and in the `pe=5` exclusion, it is mechanically eligible. I would
not describe it as robust.
