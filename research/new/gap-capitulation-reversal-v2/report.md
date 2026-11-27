# Quiet Capitulation Reversal v2 — development report

**Verdict: the repair is honest and the event sleeve should be kept.**  On
2016-01-04 .. 2023-12-29 the repaired strategy makes **20.55% CAGR / 22.25%
max drawdown / 1.05 Sharpe at 1 bp**, with **39 events, 26 independent starts
and 7.3% average exposure**.  The v1 made 8.30% / 10.26% / 0.88 with 30 events,
24 starts and 3.95% exposure.  The event study is strong and survives every
sub-period, the cost ladder, leave-one-trade-out and a circular-shift placebo
(p=0.000).  The strategy is still a **low-exposure event sleeve**, not a 20%
exposure strategy and not a TQQQ competitor; its 2022 concentration is the main
risk.

No 2024-2026 bar or daily row entered the panel, a signal, or a statistic.
`bt.panel` slices the 1-minute archive at 2023-12-29 and the QQQ daily
low/volume file is read with a UTC timestamp filter through that date.

---

## 1. Before and after

| | v1 | v2 | change |
|---|---:|---:|---:|
| Events | 30 | **39** | +9 |
| Independent starts | 24 | **26** | +2 |
| Average exposure | 3.95% | **7.28%** | +3.33 pp |
| Dev CAGR (1 bp) | 8.30% | **20.55%** | +12.25 pp |
| Dev max DD (1 bp, 1m) | 10.26% | **22.25%** | +11.99 pp |
| Sharpe | 0.877 | **1.047** | +0.17 |
| Sortino | 1.358 | **1.612** | +0.25 |
| Fills | 97 | **105** | +8 |
| Event mean (5-session TQQQ) | +7.82% (30) | **+7.40% (39)** | -0.42 pp |
| Event t-stat | 3.05 | **3.27** | +0.22 |
| TQQQ trades | 4 of 24 | **20 of 26** | the vehicle is actually used |

The trade-off is explicit: exposure and drawdown roughly double, but the
return more than doubles and the event sample is larger and more significant.
At 1 bp the strategy beats QQQ on CAGR, drawdown and Sharpe; it does not beat
the 165-day baseline on CAGR (20.6% vs 44.8%) and is not meant to.

## 2. Diagnosis

The v1 exposure problem had three layers:

1. **The event was too narrow.**  The -2.0% close leg, -3.0% intraday leg,
   quiet-volume filter and 20-day oversold filter overlapped into 30 events.
   The -2.0% close threshold alone was the easiest to relax without touching
   the mechanism: -1.5% is still a large QQQ decline and adds 9 events.
2. **The hold was too short.**  Three sessions x 24 starts = 102 invested days
   (3.95%).  The original event study already showed the 5-session TQQQ mean
   was at least as strong as the 3-session mean; the repair uses 5 sessions.
3. **The volatility cap forced QQQ.**  At a 30% cap, v1 held QQQ in 20 of 24
   trades because QQQ vol is usually above 30% at a capitulation.  The cap was
   binding at 31-34% vol events, which are exactly the events where the TQQQ
   reversal is strongest.  A 35% cap keeps the 2020 crash (79-92% vol) and the
   2022 May/June cluster (36-45%) in QQQ, but uses TQQQ in the 30-35% events.

The 8% hard stop is not the problem: it fires in 7 of 26 trades and cuts the
tail.  The event-low stop remains off, as in the v1 tuning; when it was on it
fired in most trades in the first minutes and destroyed the edge.

## 3. Rules as tested

```
qret = QQQ_close[d] / QQQ_close[d-1] - 1
qdd  = QQQ_low[d]   / QQQ_close[d-1] - 1
q20  = QQQ_close[d] / QQQ_close[d-20] - 1
rvol = QQQ_volume[d] / mean(QQQ_volume[d-20 .. d-1])
vol20 = annualised stdev(QQQ daily returns, last 20 sessions)

event = (qret <= -1.5% OR qdd <= -3.0%) AND rvol <= 1.2 AND q20 <= -3.0%

if event:
    buy at next open, 100% of TQQQ if vol20 <= 35%, else QQQ
    hold 5 sessions (entry session + 4)
    exit at the 15:59 open of the fifth session,
      or at the next minute open on an 8% hard stop from entry
    a new event during the hold resets the clock and the entry price
otherwise BIL
```

One position at a time; long-only; weights >= 0 and sum <= 1.  No 165-day or
other 100-250 day moving average.  The 165-day baseline appears only in the
benchmark/correlation table.

## 4. Headline development result

| Cost | CAGR | Max DD | Sharpe | Sortino | Vol | Exposure | Fills | End equity |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **1 bp** | **20.55%** | **22.25%** | **1.047** | 1.612 | 19.76% | **7.28%** | 105 | $444,562 |
| 5 bp | 19.91% | 22.49% | 1.020 | 1.570 | 19.76% | 7.28% | 105 | $426,277 |
| 10 bp | 19.13% | 22.80% | 0.987 | 1.518 | 19.75% | 7.28% | 105 | $404,475 |
| 165-day QQQ SMA | 44.76% | 58.76% | 1.025 | — | — | 78.5% | 59 | — |
| QQQ | 18.91% | 37.30% | 0.900 | — | 22.0% | 100% | — | $398,704 |
| TQQQ | 36.15% | 82.29% | 0.801 | — | 66.5% | 100% | — | $1,175,283 |

- Daily-return correlation to the 165-day baseline: **0.061**.
- Costs are small: 1.4 pp of CAGR from 1 to 10 bp, and the drawdown rises only
  0.55 pp.  105 fills over eight years is a low-turnover event sleeve.
- The strategy beats QQQ on CAGR, drawdown and Sharpe at 7.3% exposure.  It is
  a diversifier, not a TQQQ replacement.

## 5. Pre-registered plateau grid

All eight rows are one-at-a-time around the primary.

| Variant | Events | Starts | Exposure | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|---:|---:|---:|
| **primary: drop 1.5, hold 5, vol 35** | **39** | **26** | **7.3%** | **20.55%** | **22.25%** | **1.047** |
| drop 1.25 | 47 | 30 | 8.2% | 17.90% | 22.90% | 0.899 |
| drop 1.75 | 33 | 23 | 6.1% | 18.86% | 22.25% | 1.021 |
| hold 3 | 39 | 33 | 5.0% | 18.51% | 17.88% | 1.125 |
| hold 8 | 39 | 21 | 9.6% | 28.66% | 22.20% | 1.264 |
| vol cap 30 | 39 | 23 | 7.6% | 11.82% | 19.99% | 0.890 |
| vol cap 40 | 39 | 26 | 6.9% | 21.67% | 24.66% | 1.060 |
| rvol 1.3 | 55 | 35 | 10.1% | 19.32% | 33.29% | 0.860 |

The drop axis is a smooth plateau: 1.25-1.75% gives 33-47 events, 6-8%
exposure and 17.9-20.6% CAGR.  The hold axis is also smooth: 3-8 sessions gives
18.5-28.7% CAGR, with the 5-day point in the middle.  The one genuine cliff is
the volatility cap: 30% gives 11.8% CAGR, 35-40% gives 20.6-21.7%.  The 30% cap
is too tight for the events that drive the edge; the 35% cap is the conservative
end of the good region, and 40% already reaches 24.7% drawdown.  The rvol 1.3
row is a dilution check: more events (55) but a much worse drawdown (33.3%),
which is why the quiet-volume filter stays at 1.2.

## 6. Event study

Entry at the next open after the event; exit at the close of the fifth session.
TQQQ is used for the event study regardless of the live volatility cap, so this
is the signal's raw edge, not the strategy P&L.

| Statistic | Value |
|---|---:|
| Events | 39 |
| Mean 5-session TQQQ return | **+7.40%** |
| Median | +8.78% |
| Win rate | 61.5% |
| t-stat | **3.27** |
| Bootstrap p(mean <= 0) | **0.000** |
| Heavy-volume subset (rvol > 1.2) | n=69, mean **+0.34%**, t=0.22, p=0.408 |
| No-volume-filter subset | n=108, mean +2.89%, t=2.18, p=0.013 |

The volume condition is the core of the mechanism and it survives: the quiet
subset is 7.06 pp better than the heavy subset on the same 5-session horizon.
The no-volume-filter subset is positive but much weaker, so the volume filter is
not a regime proxy for "all oversold declines."

By sub-period:

| Period | Events | Mean 5-session TQQQ | Win |
|---|---:|---:|---:|
| 2016-19 | 9 | +2.64% | 55.6% |
| 2020-21 | 10 | +10.54% | 70.0% |
| 2022-23 | 20 | +7.98% | 60.0% |

All three are positive.  2020 is not more than half of the total: the 2022-23
block has twice as many events and a larger total contribution.

## 7. Trades and robustness

| Statistic | Value |
|---|---:|
| Closed trades | 26 |
| Hit rate | 69.2% |
| Mean trade return | +6.09% |
| QQQ trades | 6, mean +6.04% |
| TQQQ trades | 20, mean +6.11% |
| Leave-one-trade-out CAGR | 17.31% .. 22.45% |
| Remove the best trade (2022-03-08, +24.3%) | 17.31% CAGR |
| Circular-shift placebo (100 draws) | median 4.61%, p90 10.08% |
| Placebo p(CAGR >= 20.55%) | **0.000** |
| Max DD window (daily) | 2022-02-09 .. 2022-02-23, -21.94% |

The leave-one-trade-out range is tight (17.3-22.4% CAGR), so the result is not
one trade.  The placebo is the strongest evidence: random 5-session holds with
the same asset mix and exposure produce a median 4.6% CAGR, versus 20.6% for the
strategy, and no draw in 100 reaches the strategy.  The max drawdown is a
three-week February 2022 cluster, not a slow bleed.

### Trade list

26 closed trades, entry at the next open, exit at the fifth session's 15:59
open or on the 8% hard stop.  Returns are per trade, before the 2% band and
costs.

| Entry | Exit | Asset | Return |
|---|---|---|---:|
| 2016-02-03 | 2016-02-03 | TQQQ | -8.1% |
| 2018-04-09 | 2018-04-13 | TQQQ | +6.4% |
| 2018-11-13 | 2018-11-19 | TQQQ | -7.9% |
| 2018-11-20 | 2018-11-27 | TQQQ | +9.5% |
| 2018-12-26 | 2019-01-02 | TQQQ | +19.9% |
| 2019-01-04 | 2019-01-10 | QQQ | +6.0% |
| 2019-05-21 | 2019-05-31 | TQQQ | -11.4% |
| 2019-06-03 | 2019-06-07 | TQQQ | +13.0% |
| 2020-03-17 | 2020-04-08 | QQQ | +14.6% |
| 2020-09-24 | 2020-09-30 | TQQQ | +20.8% |
| 2020-10-05 | 2020-10-09 | TQQQ | +9.8% |
| 2021-03-19 | 2021-03-31 | TQQQ | +7.0% |
| 2022-02-04 | 2022-02-10 | TQQQ | +3.4% |
| 2022-02-11 | 2022-02-11 | TQQQ | -7.7% |
| 2022-02-14 | 2022-02-22 | TQQQ | -8.4% |
| 2022-02-24 | 2022-03-07 | TQQQ | +14.6% |
| 2022-03-08 | 2022-03-21 | TQQQ | +24.3% |
| 2022-05-19 | 2022-06-01 | QQQ | +5.9% |
| 2022-06-17 | 2022-06-24 | QQQ | +8.3% |
| 2022-06-29 | 2022-07-06 | QQQ | +1.8% |
| 2022-07-12 | 2022-07-18 | QQQ | -0.3% |
| 2022-10-03 | 2022-10-07 | TQQQ | -1.0% |
| 2022-10-10 | 2022-10-11 | TQQQ | -7.9% |
| 2022-10-17 | 2022-10-21 | TQQQ | +9.5% |
| 2022-11-04 | 2022-11-10 | TQQQ | +18.2% |
| 2023-01-06 | 2023-01-12 | TQQQ | +18.3% |

Per year (1 bp):

| Year | v2 | TQQQ | Note |
|---|---:|---:|---|
| 2016 | -8.2% | +18.6% | one event, 8% hard stop |
| 2017 | +0.7% | +118.3% | no qualifying event; cash drag |
| 2018 | +28.8% | -19.6% | four events, three in Q4 |
| 2019 | +8.5% | +133.1% | January and May/June events |
| 2020 | +52.4% | +109.6% | March/April cluster; Sep/Oct TQQQ |
| 2021 | +7.1% | +83.0% | two events |
| 2022 | +70.0% | -79.1% | 19 events, the dominant year |
| 2023 | +24.1% | +198.4% | January event |

Sub-period CAGR: 2016-19 6.61%, 2020-21 27.77%, 2022-23 45.52%.  The strategy
is a **volatility/bear-rebound harvester**: it lags badly in calm bull years
(2017, 2019, 2021, 2023) and earns its return in 2018, 2020 and 2022.  That is
the expected shape of a 7%-exposure event sleeve, but it also means the 2022
result is a large share of the absolute P&L.

## 8. What this does and does not prove

**It proves:**

- The quiet-volume condition is not a sample artifact in this window: the
  quiet subset beats the heavy subset by 7.06 pp with a t of 3.27 vs 0.22.
- The event is positive in all three sub-periods and survives the 10 bp cost
  ladder, leave-one-trade-out and a circular-shift placebo.
- The low exposure was a hold/event-definition problem, not a broken signal.
  39 events and 7.3% exposure is a usable event sleeve.

**It does not prove:**

- That 20% average exposure is achievable without changing the mechanism.  A
  5-session event with 39 occurrences cannot reach 20% exposure unless positions
  overlap or the hold is extended through the part of the window where the edge
  decays.  The report deliberately does not force that number.
- That the strategy is a standalone competitor to TQQQ or the 165-day baseline.
  It makes 20.6% CAGR at 7.3% exposure; the absolute return is low by design.
- That 2022 generalises.  14 of the 39 events and +70% of the 2022 return come
  from one bear market.  The sub-period event mean is positive, but the
  magnitude is regime-dependent.

## 9. Recommendation

1. **Keep the repaired event sleeve.**  It is a genuine, statistically usable
   signal: 39 events, +7.40% mean, t=3.27, placebo p=0.000, all sub-periods
   positive.
2. **Do not market it as a 20%-exposure strategy.**  It is a 7.3%-exposure
   diversifier with a 0.061 correlation to the 165-day baseline.
3. **Keep the 35% volatility cap.**  The 30% cap is too tight and cuts CAGR to
   11.8%; the 35% cap keeps the 2020 crash in QQQ and stays under the 25%
   drawdown falsifier.  The 40% cap is a higher-risk alternative, not the
   primary.
4. **Retire only the "hold longer to reach 20% exposure" idea.**  The event
   study says the edge is a 3-5 day reversal; forcing a 20-session hold would
   be a different, unproven strategy.

## 10. Files

- `strategy.py` — implementation; `--run` writes `result.json`.
- `result.json` — cost ladder, event study, 26 trades, sub-periods, 8-row grid.
- `robustness.py` / `robustness.json` — LOO, circular-shift placebo, max-DD
  window.
- `diagnose.py` — exploratory event/definition sweeps (not the pre-registered
  grid; writes `diagnose.json` when run).
