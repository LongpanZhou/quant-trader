# Stop re-entry and recovery on the round-1 winner

**Agent:** `stop-reentry-recovery` · **Date:** 2026-11-25
**Mandate:** after the winner's 4% intraday stop, test same-day re-entry on TQQQ
VWAP / 5m / 15m EMA reclaim or QQQ 20-day-MA reclaim, with a tighter stop; test
next-open re-entry only if the close recovers. Target: higher CAGR without higher
drawdown than the winner, or lower drawdown with similar CAGR.

## Verdict

**Same-day reclaim re-entry is rejected.** Almost every VWAP, 5m-EMA, 15m-EMA and
QQQ-MA20 reclaim variant lowers CAGR and raises (or barely changes) drawdown; the
few that add a little 5-year CAGR give up more elsewhere and fail the bar. The
post-stop drift is negative, the reclaims arrive late, and forward returns after a
reclaim are negative even before costs (Section 5).

**The next-open branch works, but only as a gradual re-entry, not a binary
"re-enter if the close recovers".**

- If the stopped session closes *above* its stop level, re-enter 100% at 09:31
  but with a **2% stop** for that session instead of 4%.
- If the stopped session closes *below* its stop level, re-enter only **50%** at
  09:31 and keep that half through the session and the following night; restore
  100% the next session.

This is a strict improvement on the headline metrics at 1, 5 and 10 bp:

| Window | 1 bp CAGR / DD | 5 bp CAGR / DD | 10 bp CAGR / DD |
|---|---:|---:|---:|
| 10y candidate | **61.03% / 39.92%** | **57.02% / 40.68%** | **52.15% / 43.63%** |
| 10y winner | 58.80% / 44.56% | 54.60% / 47.08% | 49.50% / 50.06% |
| 5y candidate | **51.57% / 29.96%** | **47.65% / 30.38%** | **42.90% / 30.90%** |
| 5y winner | 49.88% / 33.49% | 45.89% / 34.13% | 41.05% / 34.93% |
| TQQQ buy-and-hold | 39.28% / 81.68% (10y) · 13.47% / 81.68% (5y) | — | — |

TQQQ rows use the README's daily-bar figures; the 1-minute harness benchmark for
the same windows is 39.38% / 82.29% and 14.29% / 82.29%. The pass/fail conclusion
is identical either way.

The drawdown improvement is the robust part (lower in 19 of 27 rolling 3-year
windows and in all five sub-periods). The CAGR improvement is positive in both
windows and at all three cost levels but is **not statistically strong**: a
monthly block bootstrap puts the 90% interval of the annualized return difference
at **−2.1 to +5.2 pp** (median +1.3 pp, t = 0.65). Treat this as a cheaper
left-tail, not a new alpha source.

## 1. Idea and sources

The round-1 winner deliberately stays in BIL for the rest of the stop day *and*
the following night. The obvious question is whether some of that time can be
recovered when the sell-off is a whipsaw rather than a crash.

Prior evidence is mixed and mostly cautionary:

- **Kaminski & Lo (2014)** show stop-loss rules add value only when returns have
  momentum/regime shifts; otherwise they are a cost. Their condition is the
  license for a stop that is armed only in weak short-term trends (the winner).
- **Clare, Seaton, Smith & Thomas (2013)** test breakout/re-entry stop rules on
  the S&P 500 (1988–2011) and find *no value in stop-loss rules*; whipsawing is
  not a problem only when the technical signal is long enough. That argues
  against minute-level re-entry signals — and is exactly what we observe.
- **Duarte (2022)** tests trailing stops with a **+3% re-entry rule** in European
  markets and finds mixed results: it beats buy-and-hold in some rising/falling
  scenarios, not all. Re-entry is not a free option.
- The practitioner VWAP-reclaim literature agrees on the *shape* of the rule
  (wait until at least 09:45/10:00, require a close above VWAP, confirm with
  volume or a retest, stop below VWAP/the reclaim candle) — see
  [Scanz](https://scanz.com/vwap-trading-strategy),
  [Section 32](https://section32collective.com/vwap-reclaim.html),
  [Tradezella](https://www.tradezella.com/blog/vwap-trading-strategy),
  [QuantCore](https://qntcore.ai/blog/vwap-trading-strategy-options). We tested
  those confirmations (1–3 bars, 5 bp buffer, 10:00 start, VWAP-failure stop).
- A large multiple-testing study of VWAP crossovers reports that **volume
  confirmation and multi-bar reversal filters do not create edge** after
  Bonferroni correction (EdgeTools, 427k tests:
  [TradingView](https://www.tradingview.com/chart/ES1!/tVJcD92K-Everyone-Uses-VWAP-Wrong/)).
  Our event study reaches the same conclusion on a different sample.
- On whipsaw filters, trend/ADX-style regime filters and partial position sizing
  are the standard tools; see
  [CapitalMEG](https://www.cmelitegroup.com/knowledge-hub/trend-following) and
  Faber (2007). The surviving candidate uses the simplest version: half size
  after a weak close, full size with a tighter stop after a recovered close.

## 2. Data, harness, and no look-ahead

- Local adjusted 1-minute QQQ / TQQQ / BIL under `data/intraday-hf/`, regular
  session only, 2016-01-04 → 2026-10-23 (1,057,023 bars, 2,718 sessions, 500
  calendar days of warm-up before the 2017 start). No new downloads.
- Harness: `research/bt.py`. Weights are target fractions set at bar *i* and
  filled at bar *i+1*'s open; slippage is charged on traded notional; long-only;
  weights sum to ≤ 1. BIL earns its own price return while out.
- Regime: QQQ **prior** daily close vs its 165-day SMA. Arm gate: QQQ first-minute
  close vs its 20-day SMA through the **prior** close. Stop: current bar's TQQQ
  close vs the current session's open. Weak-close block: current session's close
  vs its stop level, both known at 15:59. Tight-stop regime: known from the prior
  session's stop. Nothing uses a future bar.
- One subtlety: the winner re-enters at **09:31**, not 09:30, because the stop-day
  close leaves the weight at zero overnight and the first-minute weight fills one
  bar later. We preserve that convention throughout, including the 50% block.
- The candidate only needs QQQ/TQQQ opens and closes; no VWAP/high/low data is
  used in the final rules (VWAP/EMA are only in the rejected variants).

## 3. Baseline reproduction

The round-1 winner is reproduced exactly (same code path, then re-implemented in
`strategy.py`): **58.80% / 44.56%** (10y) and **49.88% / 33.49%** (5y) at 1 bp,
with 657 / 337 fills. That is the bar used everywhere below.

Winner drawdown episodes: 2018-03-13 → 2019-06-05 (44.56%) on 10y and
2026-06-22 → 2026-07-30 (33.49%) on 5y. The 2018–19 whipsaw, not COVID, is the
winner's worst 10-year episode.

## 4. What was tested

1. **Same-day re-entry** after the stop:
   - TQQQ close above session VWAP (1/2/3-bar confirm, 0/5 bp buffer, 10:00–
     15:00 window, VWAP-failure stop);
   - TQQQ close above the 5-minute EMA (span 9 and 20) and the 15-minute EMA
     (span 9), 1/3-bar confirm;
   - QQQ close above its prior-day 20-day SMA;
   - each with a fresh 2%/3% stop from the re-entry price, and at full/half size.
2. **Same-day close re-entry**: at 15:58/15:59 if the close is above the stop
   level, above VWAP, or above the open (hold overnight).
3. **Next-open conditional re-entry**: full block of the next session if the
   stop-day close is weak; partial blocks of 25/37.5/50/62.5/75%; with/without a
   tighter stop on the re-entry day; with/without chaining the tight regime.
4. **Tighter stop on the re-entry day** (1.5/2/2.5/3%) and the same-day fixed-time
   / cooldown re-entry variants (15–180 minutes after the stop).
5. **Ablations**: tight stop only, block only, combination, entry-anchored vs
   open-anchored stop, chained vs one-day tight regime.

## 5. Same-day re-entry: a clean negative

### 5.1 Full-strategy results (1 bp)

| Variant | 10y CAGR / DD | 5y CAGR / DD | Fills (10y) |
|---|---:|---:|---:|
| Winner (no re-entry) | **58.80 / 44.56** | **49.88 / 33.49** | 657 |
| VWAP reclaim, 1-bar, no fresh stop | 48.68 / 53.00 | 40.52 / 40.72 | 673 |
| VWAP reclaim + 2% stop | 53.25 / 47.00 | 40.53 / 41.23 | 769 |
| VWAP reclaim, 3-bar + 2% stop | 52.99 / 44.76 | 40.54 / 40.90 | 741 |
| VWAP reclaim + VWAP-failure stop | 56.96 / 48.55 | 50.47 / 34.36 | 905 |
| EMA5 reclaim + 2% stop | 44.02 / 47.16 | 37.53 / 42.67 | 917 |
| EMA15 reclaim + 2% stop | 49.58 / 53.60 | 41.36 / 41.08 | 849 |
| QQQ 20-day-MA reclaim | 58.58 / 45.58 | 49.39 / 33.49 | 661 |
| Re-enter 15:59 if close > stop level | 55.40 / 49.66 | 45.76 / 39.78 | 665 |
| Re-enter 15:59 if close > VWAP | 50.91 / 50.43 | 39.29 / 40.70 | 661 |
| Re-enter 15:59 if close > open | 57.62 / 50.12 | 50.75 / 33.49 | 657 |
| Full block of next day if weak close | 56.14 / 42.21 | 47.37 / 34.28 | 577 |

The best same-day variant (`close > open` at 15:59) adds 0.87 pp of 5-year CAGR
but gives up 5.6 pp of 10-year drawdown and 1.2 pp of 10-year CAGR. None passes.

### 5.2 Why: the event study

160 armed stop events in the full sample (153 in the 10-year test window). After
the trigger close:

| Measure | Mean | Median | Share < 0 |
|---|---:|---:|---:|
| Stop → same-day close | −0.387% | −0.329% | 55.0% |
| Stop → next open | −0.461% | −0.383% | 53.8% |

Reclaims are late and are followed by *more* weakness, measured from the fill at
the next bar's open:

| Reclaim | Events | Share | Median minute | To close | To next open |
|---|---:|---:|---:|---:|---:|
| TQQQ > session VWAP (3-bar confirm) | 67/160 | 41.9% | 214 | −0.236% | −0.813% |
| TQQQ > 5m EMA(9) | 149/160 | 93.1% | 169 | −0.507% | −0.544% |
| TQQQ > 15m EMA(9) | 129/160 | 80.6% | 238 | −0.373% | −0.517% |
| QQQ > prior 20-day SMA | 5/160 | 3.1% | 276 | +0.235% | −0.330% |

Only 5 of 160 stop days see QQQ reclaim its 20-day MA at all, so that branch is
a no-op. The VWAP/EMA branches are worse than doing nothing: the stop already
avoided the down-leg, and the reclaim buys the bounce *after* the mean-reversion
has happened.

Fixed-time re-entry is negative at every clock time (mean stop-to-close from
10:00: −0.450%; 10:30: −0.556%; 12:00: −0.357%; 14:00: −0.410%; 15:00: −0.198%;
15:30: −0.364%). A 15–180 minute cooldown is also negative on average.

### 5.3 The "re-enter only if the close recovers" condition is backwards

- 41.9% of stop days close above their stop level, 19.4% above VWAP, 5.6% above
  the open.
- The next session's open→close return is **+0.726%** after a *weak* close
  (n = 93) and **+0.481%** after a recovered close (n = 67). Blocking weak
  closes gives up the better half of the distribution.
- The overnight return (15:59 → next open) is **−0.329%** after a close above
  the stop level, **+0.009%** after a close below it; above VWAP it is **−1.30%**
  versus **+0.15%** below. Re-entering at the close "because it recovered" is
  the wrong side of short-term reversal.

That is why the binary "full block if weak / full re-entry if recovered" fails
(56.14 / 42.21 and 47.37 / 34.28). The surviving rule uses **half size** on the
weak-close session instead of a full block, and a **tighter stop** on the
recovered-close session instead of a full-size 4% stop.

## 6. The candidate: gradual re-entry with a tighter stop

### 6.1 Exact rules

For each session *d* (09:30–15:59 ET):

```
SMA165[d] = mean(QQQ daily close, d-165 … d-1)
MA20[d]   = mean(QQQ daily close, d-20  … d-1)
risk_on   = QQQ close[d-1] > SMA165[d]

if not risk_on:
    hold BIL for the whole session
else:
    # state from the previous session
    if previous session stopped and its close < its own stop level:
        hold 50% TQQQ / 50% BIL for the whole session
        (fills at 09:31; the 50% stays through the following night)
        next session: normal full-size logic
        continue

    armed  = QQQ 09:30 close < MA20[d] * 1.01
    stop   = 4%
    if previous session stopped:
        stop  = 2%          # tighter re-entry-day stop
        armed = True        # always protect the re-entry

    base = TQQQ open[d]
    state = TQQQ
    for each minute i:
        if state and armed and TQQQ close[i] < base * (1 - stop):
            state = BIL     # fills at open[i+1]; flat rest of session
        weight[i] = state
    # if a stop fired: out overnight; next session re-enters at 09:31
```

- The 2% stop is checked from the **first minute**, so a gap-down first minute
  cancels the re-entry entirely (this is a deliberate gap filter, and it is the
  main source of the 2024-08-05 whipsaw loss).
- The tight regime **chains**: after a 2% stop, the next session is also 2%
  (and is 50% if the prior close was weak). One clean session restores 100% / 4%.
- One position at a time, 100% TQQQ or BIL (50/50 on the weak-close re-entry
  session), no leverage, no shorts. BIL earns its carry while out.

### 6.2 Ablation (1 bp, 10y / 5y CAGR / DD)

| Variant | 10y | 5y |
|---|---:|---:|
| Winner | 58.80 / 44.56 | 49.88 / 33.49 |
| 2% re-entry-day stop only | 58.76 / 42.55 | 43.43 / 34.47 |
| 50% weak-close block only | 59.13 / 39.92 | 46.78 / 32.71 |
| **Both (candidate)** | **61.03 / 39.92** | **51.57 / 29.96** |
| Both, entry-anchored stop (no first-minute cancellation) | 59.67 / 39.92 | 49.40 / 29.96 |
| Both, no tight-regime chaining | 60.08 / 39.92 | 50.52 / 29.96 |

The interaction is the point: either rule alone gives up too much 5-year CAGR,
but half size on the vulnerable weak-close session plus a tight stop on the
full-size re-entry session keeps most of the 5-year return while cutting the
left tail. The entry-anchored version (which cannot cancel the re-entry on a weak
first minute) still lowers drawdown in both windows and is within 2 pp of the
winner's CAGR on both — i.e. it passes target #2 even without the gap filter.
The headline version passes target #1.

## 7. Results

### 7.1 Headline (1 bp, 1-minute marks)

| Metric | 10y candidate | 10y winner | 5y candidate | 5y winner |
|---|---:|---:|---:|---:|
| CAGR | **61.03%** | 58.80% | **51.57%** | 49.88% |
| Total return | 10,568% | 9,205% | 698% | 655% |
| Max drawdown (1m) | **39.92%** | 44.56% | **29.96%** | 33.49% |
| Max drawdown (daily) | **39.44%** | 41.62% | **28.13%** | 33.08% |
| Sharpe | **1.29** | 1.24 | **1.20** | 1.16 |
| Sortino | **1.82** | 1.74 | **1.71** | 1.64 |
| Volatility | **44.76%** | 46.12% | **42.14%** | 43.39% |
| Fills | 811 | 657 | 407 | 337 |
| Ending equity ($100k) | **$10.67M** | $9.30M | **$798k** | $755k |
| Max-DD peak → trough | 2020-02-19 → 2020-03-09 | 2018-03-13 → 2019-06-05 | 2024-07-10 → 2024-08-05 | 2026-06-22 → 2026-07-30 |
| TQQQ weight (time avg.) | 77.5% | 79.0% | 77.5% | 79.0% |

The worst 10-year episode moves from the 2018–19 whipsaw (44.56%) to COVID
(39.92%); the worst 5-year episode moves from 2026 (33.49%) to the 2024 yen-carry
unwind (29.96%). Both are lower than the winner's worst, and both are episodes
where the winner was fully exposed at some point.

### 7.2 Costs

| Costs | 10y candidate | 10y winner | 5y candidate | 5y winner |
|---|---:|---:|---:|---:|
| 1 bp | **61.03 / 39.92** | 58.80 / 44.56 | **51.57 / 29.96** | 49.88 / 33.49 |
| 5 bp | **57.02 / 40.68** | 54.60 / 47.08 | **47.65 / 30.38** | 45.89 / 34.13 |
| 10 bp | **52.15 / 43.63** | 49.50 / 50.06 | **42.90 / 30.90** | 41.05 / 34.93 |

The candidate trades more (811 vs 657 fills over 10 years, +23%) and still
dominates at 10 bp. The extra cost is roughly offset by the lower turnover on
the blocked days (the 50% target only resizes, it does not create a round trip).

### 7.3 Yearly returns (calendar year, 1 bp)

| Year | Candidate | Winner | TQQQ | Δ vs winner |
|---|---:|---:|---:|---:|
| 2017 | 114.35% | 118.76% | 114.54% | −4.41 pp |
| 2018 | **16.37%** | 0.47% | −20.76% | +15.90 pp |
| 2019 | 38.44% | 47.94% | 148.23% | −9.50 pp |
| 2020 | 182.65% | 183.91% | 104.14% | −1.25 pp |
| 2021 | 61.25% | 60.61% | 81.05% | +0.63 pp |
| 2022 | **−15.86%** | −17.99% | −79.39% | +2.13 pp |
| 2023 | **156.63%** | 149.04% | 192.05% | +7.60 pp |
| 2024 | 61.12% | 67.96% | 62.43% | −6.84 pp |
| 2025 | 43.05% | 43.29% | 32.10% | −0.24 pp |
| 2026 | **26.67%** | 16.76% | 22.62% | +9.91 pp |

The improvement is not one year: 2018, 2021, 2022, 2023 and 2026 are better;
2017, 2019, 2020, 2024 and 2025 are worse. 2019 (−9.5 pp) and 2024 (−6.8 pp) are
the honest costs of the tight stop in strong V-shaped rebound years. Monthly
positive share is 65.0% (winner 66.7%), mean month +4.64% (winner +4.57%); the
worst month is 2019-05 at −24.1% (winner −23.8%).

### 7.4 Sub-periods (1 bp, CAGR / DD)

| Period | Candidate | Winner |
|---|---:|---:|
| 2017–2019 | **52.11 / 38.21** | 49.07 / 44.56 |
| 2020–2022 | **58.06 / 39.92** | 56.74 / 41.50 |
| 2023–2026 | **70.03 / 29.96** | 67.74 / 33.49 |
| 2017–2021 | **75.51 / 39.92** | 73.42 / 44.56 |
| 2022–2026 | **46.88 / 29.96** | 44.54 / 33.49 |

CAGR is higher and drawdown lower in all five sub-periods. This is the strongest
evidence that the result is not a single-window artifact.

### 7.5 Rolling 3-year windows

Full 3-year windows starting at each quarter (27 windows, 2017-04 → 2023-10):

| | Candidate | Winner | TQQQ |
|---|---:|---:|---:|
| Median CAGR | **65.49%** | 64.99% | 47.34% |
| Median max DD | **35.06%** | 38.33% | 69.89% |
| Windows beating on both CAGR and DD | 17/27 vs winner | — | 23/27 vs TQQQ |
| Windows with lower DD | 19/27 | — | 27/27 |
| Windows with higher CAGR | 18/27 | — | 23/27 |

The 10 windows where it does not beat the winner on both are concentrated in
2018-04 → 2019-10 (7 windows: the 2018–19 whipsaw path is ~0.6 pp deeper from an
April-2018 start, while CAGR is 0.2–4.2 pp lower), 2020-01 (higher CAGR but
0.6 pp more DD), and 2023-01/2023-04 (5.6 pp less DD but 0.8–1.8 pp less CAGR).
That is a fair description of the trade: it gives up some upside in strong
rebounds, and it cuts the tail in the bad ones.

### 7.6 Attribution

Sum of daily log-return differences vs the winner, by year (pp):

```
2017 -2.04   2018 +14.69   2019 -6.64   2020 -0.44   2021 +0.39
2022 +2.56   2023  +3.00   2024 -4.16   2025 -1.85   2026 +8.15
```

The largest positive days are blocked weak-close days that were held 50%
overnight into a rebound: 2018-03-26 (+6.76 pp), 2026-07-17 (+5.43 pp),
2021-03-05 (+5.15 pp), 2018-02-09 (+4.84 pp), 2018-04-03 (+4.70 pp). The largest
negative days are the tight stop cancelling a re-entry on a gap-down reversal
day: 2024-08-05 (−8.37 pp), 2021-02-24 (−7.07 pp), 2019-10-03 (−5.55 pp).
This is the mechanism in one line: **half-size exposure through the rebound,
tight stop through the continuation.**

### 7.7 Statistical strength

Monthly log-return difference (candidate − winner), 117 months:

- mean +0.117%/month, t = 0.65;
- 5,000-draw iid bootstrap of the annualized difference: p05 −2.14 pp,
  median +1.32 pp, p95 +5.17 pp, P(>0) = 73.1%.

So the CAGR edge is positive but within noise. The drawdown reduction is more
consistent: lower in 19/27 rolling windows, all five sub-periods, and all 20
points of the parameter grid (10-year DD 39.6–41.7% vs 44.56%). The honest claim
is **"lower drawdown at similar-or-better CAGR"**, not "a significantly higher
CAGR".

## 8. Robustness

### 8.1 Parameter surface (1 bp; cells are CAGR / DD)

10-year:

| Block \ tight stop | 1.5% | 2.0% | 2.5% | 3.0% |
|---|---:|---:|---:|---:|
| 25.0% | 60.54 / 39.63 | 62.63 / 39.63 | 61.88 / 39.63 | 60.89 / 39.63 |
| 37.5% | 59.82 / 39.71 | 61.88 / 39.71 | 61.22 / 39.71 | 60.33 / 39.71 |
| **50.0%** | 58.99 / 40.33 | **61.03 / 39.92** | 60.45 / 39.92 | 59.66 / 39.92 |
| 62.5% | 58.06 / 40.99 | 60.08 / 40.29 | 59.58 / 40.29 | 58.89 / 40.29 |
| 75.0% | 57.12 / 41.65 | 59.11 / 40.50 | 58.70 / 40.50 | 58.10 / 40.85 |

5-year:

| Block \ tight stop | 1.5% | 2.0% | 2.5% | 3.0% |
|---|---:|---:|---:|---:|
| 25.0% | 49.87 / 33.70 | 51.54 / 33.70 | 50.41 / 33.70 | 49.24 / 33.70 |
| 37.5% | 49.93 / 31.84 | 51.57 / 31.84 | 50.59 / 31.84 | 49.42 / 31.84 |
| **50.0%** | 49.95 / 29.96 | **51.57 / 29.96** | 50.73 / 29.96 | 49.56 / 29.96 |
| 62.5% | 49.93 / 28.93 | 51.53 / 29.57 | 50.84 / 28.62 | 49.67 / 29.29 |
| 75.0% | 49.88 / 29.95 | 51.46 / 30.58 | 50.91 / 29.26 | 49.74 / 29.92 |

Every cell has a lower 10-year DD than the winner; 16 of 20 also have a lower
5-year DD (the four 25%-block cells at 33.70% are the exceptions). The 50%/2% choice is a
round-number center, not the peak: the 10-year CAGR peak is 25%/2% (62.63%,
but 5-year DD 33.70%), and the 5-year DD trough is 62.5%/2.5% (28.62%, but
10-year CAGR 59.58%). The surface is smooth in both directions.

### 8.2 Other ablations

- Entry-anchored tight stop (no first-minute cancellation): 59.67 / 39.92 (10y),
  49.40 / 29.96 (5y). Still lower DD in both windows; 5-year CAGR 0.5 pp below
  the winner. The gap filter is worth ~1.4 pp of 10-year CAGR but is not what
  makes the drawdown improvement.
- No tight-regime chaining: 60.08 / 39.92, 50.52 / 29.96. Chaining adds ~1 pp
  of 10-year CAGR; the result does not depend on it.
- Full block (100%) instead of 50%: 56.14 / 42.21, 47.37 / 34.28. Too much of
  the rebound is lost. Half size is the useful compromise.
- Block only (no tight stop) is 59.13 / 39.92 and 46.78 / 32.71; tight only is
  58.76 / 42.55 and 43.43 / 34.47. Both components are needed for the 5-year
  result.
- The half-size block does **not** depend on the overnight hold. Exiting the 50%
  at 15:59 (intraday only) gives 60.59 / 40.46 (10y) and 51.51 / 30.04 (5y),
  versus 61.03 / 39.92 and 51.57 / 29.96 when the half is held overnight. The
  overnight half contributes only ~0.4 pp of CAGR and ~0.5 pp of DD; the mechanism
  is the half-size session, not an overnight bet. (The overnight version is kept
  as the headline because it is the simpler state machine: one 50% target for the
  session and night, then restore 100%.)

### 8.3 Costs and capacity

At 10 bp the candidate still dominates the winner on both windows (52.15 / 43.63
vs 49.50 / 50.06; 42.90 / 30.90 vs 41.05 / 34.93) and beats TQQQ by a wide
margin. Fills are 811 over 10 years (~83/year), so the result is not
turnover-fragile. The tight-stop days add at most one round trip each (19 tight
stops in 10 years); the blocked days only resize.

## 9. Limitations and honest caveats

1. **The CAGR gain is not statistically significant.** The bootstrap interval
   straddles zero. The robust claim is the drawdown reduction.
2. **The 10-year gain is concentrated in 2018 and 2026.** 2018 contributes
   +14.7 pp of log difference and 2026 +8.2 pp; 2019 and 2024 give back −6.6 and
   −4.2 pp. If 2018-style whipsaw does not repeat, the CAGR edge shrinks toward
   the 5-year result (which is still positive).
3. **The 2018–19 rolling windows are slightly worse than the winner** (CAGR
   0.2–4.2 pp lower, DD ~0.6 pp higher from an April-2018 start). The headline
   10-year DD improvement comes from the March-2018 peak-to-trough path, not from
   every possible start date.
4. **The first-minute stop cancellation is a gap filter.** It is legitimate (the
   09:30 close is known before the 09:31 fill), but it is also why the strategy
   missed the 2024-08-05 and 2021-02-24 V-shaped reversals. The entry-anchored
   version avoids that specific failure but gives up some CAGR.
5. **The parameters were inspected after the fact.** The 50%/2% choice is a
   round-number center of a stable surface, not the grid peak, but it is still
   in-sample selection. Neighbours and the entry-anchored/no-chain ablations are
   reported so the reader can judge.
6. **Single instrument, single sample.** The result is specific to a 3× Nasdaq-100
   ETF over 2017–2026, a period with two large crashes and several violent
   V-reversals. No claim is made about other leveraged ETFs or other decades.
7. **1 bp is optimistic for a stop.** The harness fills at the next minute's
   open, which can be through the stop in a fast market; the 5/10 bp rows are the
   honest retail range. The conclusion survives both.
8. **No taxes.** ~83 fills/year is tax-inefficient in a taxable account; all
   results are pre-tax.
9. **Drawdown marks.** Headline DD is on 1-minute equity marks (the harness
   standard); daily-mark DD is also reported and is the comparable number to the
   README baseline.

## 10. Reproduction

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"

# final candidate + comparison to the winner, 1/5/10 bp
python research\agents2\stop-reentry-recovery\strategy.py

# full result.json (variants, costs, yearly, rolling, attribution, bootstrap)
python research\agents2\stop-reentry-recovery\final_run.py
python research\agents2\stop-reentry-recovery\patch_result.py

# negative results / event study / parameter grids
python research\agents2\stop-reentry-recovery\explore.py
python research\agents2\stop-reentry-recovery\explore2.py
python research\agents2\stop-reentry-recovery\explore3.py
python research\agents2\stop-reentry-recovery\sweep1.py
python research\agents2\stop-reentry-recovery\sweep5.py
```

Files: `strategy.py` (standalone final rules), `srlib.py` / `prep.py` (shared
helpers and cached panel), `result.json` (all metrics), `strategy_result.json`
(strategy.py output), `final_run.py` (result.json builder), and the exploratory
scripts. No core repository file was modified; the panel cache and all outputs
live under `research/agents2/stop-reentry-recovery/`.

## References

- Kaminski, K. M., & Lo, A. W. (2014). *When do stop-loss rules stop losses?*
  Journal of Financial Markets 18, 234–254.
  [doi:10.1016/j.finmar.2013.07.001](https://doi.org/10.1016/j.finmar.2013.07.001)
- Clare, A., Seaton, J., Smith, P. N., & Thomas, S. (2013). *Breaking into the
  blackbox: Trend following, stop losses and the frequency of trading — the case
  of the S&P500.* Journal of Asset Management 14, 182–194.
  [link](https://openaccess.city.ac.uk/id/eprint/17842)
- Duarte, E. (2022). *Trailing Stop-Loss and Re-Entry Strategies in Europe.*
  European Journal of Business and Management Research 7(3), 118–123.
  [link](https://eu-opensci.org/index.php/ejbmr/article/view/51426)
- EdgeTools. *Everyone Uses VWAP Wrong* (427,319 VWAP tests with Bonferroni
  correction; volume confirmation and multi-bar reversal filters add nothing).
  [TradingView](https://www.tradingview.com/chart/ES1!/tVJcD92K-Everyone-Uses-VWAP-Wrong/)
- Scanz. *VWAP Trading Strategy: How Intraday Traders Use It as a Benchmark.*
  [link](https://scanz.com/vwap-trading-strategy)
- Section 32. *How to Trade the VWAP Reclaim.*
  [link](https://section32collective.com/vwap-reclaim.html)
- Tradezella. *VWAP Trading Strategy: How to Trade VWAP (2026).*
  [link](https://www.tradezella.com/blog/vwap-trading-strategy)
- QuantCore.AI. *VWAP Trading Strategy for Options.*
  [link](https://qntcore.ai/blog/vwap-trading-strategy-options)
- CapitalMEG. *Trend Following Strategy: Entries, Exits, Sizing* (whipsaw and
  partial-sizing discussion). [link](https://www.cmelitegroup.com/knowledge-hub/trend-following)
- Faber, M. T. (2007). *A Quantitative Approach to Tactical Asset Allocation.*
  SSRN 962461. [link](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=962461)
- Lou, D., Polk, C., & Skouras, S. (2019). *A Tug of War: Overnight versus
  Intraday Expected Returns.* Journal of Financial Economics.
  [pdf](https://personal.lse.ac.uk/polk/research/TugOfWar.pdf)
- Gayed, M. (2016). *Leverage for the Long Run.* SSRN 2741701.
  [link](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2741701)
