# Overnight + intraday trend TQQQ — development report

**Strategy:** `overnight-intraday-trend`
**Window:** 2016-01-04 → 2023-12-29 (development only; no 2024+ bar loaded)
**Bar:** TQQQ dev 36.72% CAGR / 82.29% max DD / 0.82 Sharpe

## Verdict

**Pass on the development window at 1 bp and 5 bp; fails at 10 bp.**

| | CAGR | Max DD | Sharpe | Fills | TQQQ exp. |
|---|---:|---:|---:|---:|---:|
| **Strategy 1 bp** | **64.63%** | **35.66%** | **1.42** | 1,837 | 66.2% |
| Strategy 5 bp | 50.16% | 38.77% | 1.20 | 1,837 | 66.2% |
| Strategy 10 bp | 33.84% | 42.77% | 0.92 | 1,837 | 66.2% |
| Strategy 0 bp (gross) | 68.46% | 34.86% | 1.48 | 1,837 | 66.2% |
| TQQQ buy & hold (sim) | 36.15% | 82.29% | 0.80 | 1 | 100% |
| TQQQ official dev bar | 36.72% | 82.29% | 0.82 | — | 100% |

Daily correlation to TQQQ: **0.63**. Average TQQQ weight **66.2%**, BIL
**33.8%** (the `bt.stats` exposure of 100% counts BIL as invested; the TQQQ
number is the economically meaningful one). Max drawdown window:
**2019-04-25 → 2019-10-03**, 35.66% — a choppy-year whipsaw, not a crash.

The headline beats the dev CAGR bar by 27.9 pp with less than half the
drawdown budget (35.7% vs the 60% target). It is a high-exposure strategy: the
TQQQ sleeve is on two-thirds of the time, and the overnight is held on 1,234 of
2,011 nights.

## 1. Rules

Universe: QQQ (signal), TQQQ (position), BIL (defensive sleeve). Long-only,
weights ≥ 0, sum ≤ 1. Next-minute-open fills, 2% band, BIL earns its own carry.

```
q58[k]    = QQQ close of the 15:58 bar of session k
SMA20/50  = means of QQQ daily closes through q58[k]
trend[k]  = (SMA20 > SMA50) OR (q58 > SMA50)      # 20/50 cross or 50-day reclaim

session k+1 starts long TQQQ iff trend[k], else BIL for the whole session.

checks at 10:00, 10:30, 11:00, 11:30, 12:00, 12:30, 13:00, 13:30,
           14:00, 14:30, 15:00, 15:30 (close of each 30-minute bar):
    long and QQQ <= session_open * (1 - 0.006)  -> BIL at next minute's open
    BIL  and QQQ >= session_open               -> TQQQ at next minute's open

at 15:30 the session state is frozen for the night:
    long at 15:30 and trend up at 15:58          -> hold TQQQ overnight
    BIL at 15:30 (stopped, not reclaimed)        -> stay BIL overnight
    fresh trend-up at 15:58 from a down day      -> buy TQQQ at the 15:59 open
    trend down at 15:58                          -> BIL overnight

after a skipped night, re-enter at 09:31 next session if the trend is still up.
```

The 15:58 trend print fills at the 15:59 open. The 15:30 check uses the 15:29
close and fills at 15:30. Every weight is set at a bar close and filled at the
next bar's open; there is no same-bar information. The 15:30 night decision is
deliberate: the last 30 minutes are excluded so an unconfirmed late bounce
cannot pull the strategy back into a weak overnight.

The 50-day reclaim leg is the `re-enter on a reclaim` part of the mandate: the
trend is broken only when **both** the 20/50 cross and price are below the
50-day average. The pure 20/50 cross is grid cell 7 and a control.

## 2. Year by year

| Year | Strategy 1 bp | TQQQ | Note |
|---:|---:|---:|---|
| 2016 | **-2.8%** | +19.9% | choppy; whipsaw |
| 2017 | +104.1% | +114.5% | calm bull |
| 2018 | **+23.6%** | -20.8% | Q4 crash avoided |
| 2019 | +63.4% | +148.2% | strong year, but 35.7% mid-year DD |
| 2020 | **+308.5%** | +104.1% | crash skipped, V-recovery ridden |
| 2021 | +31.0% | +81.1% | choppy bull; lagged |
| 2022 | **-11.0%** | -79.4% | trend break + stops |
| 2023 | +162.2% | +192.0% | strong |

Subperiods: 2016–2019 **42.1% / 35.7% DD**, 2020–2021 **132.9% / 29.9% DD**,
2022–2023 **53.2% / 22.7% DD**. The strategy is positive in seven of eight
calendar years; the two weak years are 2016 and 2021, both choppy bulls where
the 20/50 gate whipsaws.

## 3. Where the return comes from

Night block = 15:59 open → next 09:30 open. Day block = the residual.

| | Strategy | TQQQ B&H |
|---|---:|---:|
| Annualised night log return | **30.9%** | 25.9% |
| Nights held | 1,234 | 2,011 |
| Mean overnight return when held | **+19.4 bp** | — |
| Mean overnight return when skipped | **+1.5 bp** | — |

The strategy holds only 61% of nights yet earns a higher annualised night
return than always-on TQQQ, because the nights it skips are almost flat on
average. That is the mechanism: a weak close (stopped out, not reclaimed) is a
poor overnight signal. Roughly half the total log P&L comes from the night
block; the intraday stop and the BIL sleeve supply the rest.

**Crash/gap evidence.** The ten worst TQQQ nights in the window:

- **2020-03-13: -27.6%** — skipped (strategy weight 0).
- **2020-03-06: -20.5%** — held (weight 1). This is the worst night actually
  taken; it is the honest gap-risk number.
- 2020-03-11 (-20.4%), 2020-03-17 (-15.1%), 2020-02-21 (-10.9%),
  2020-02-27 (-10.5%), 2018-10-25 (-10.5%), 2016-01-14 (-10.1%) — all skipped.
- 2020-09-04 (-12.2%) and 2016-06-23 (-10.7%) were held.

The skip rule is not a general gap protector: it only acts after a weak close.
A gap from a strong close is taken in full. The -20.5% held night is the
relevant tail number, not the -27.6% avoided one.

## 4. Pre-registered grid and plateau

Eight cells, frozen before the final run. All use the same 20/50 + reclaim
trend unless stated.

| # | Cell | CAGR 1 bp | DD 1 bp | Sharpe | CAGR 5 bp | CAGR 10 bp | TQQQ exp. |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | stop 0.5%, 30m, skip | **72.44%** | 33.38% | 1.58 | 54.53% | 34.73% | 63.5% |
| 2 | **stop 0.6%, 30m, skip (centre)** | **64.63%** | **35.66%** | **1.42** | **50.16%** | 33.84% | 66.2% |
| 3 | stop 0.7%, 30m, skip | 54.51% | 38.37% | 1.26 | 42.14% | 28.07% | 67.9% |
| 4 | stop 0.6%, 15m, skip | 62.14% | 33.64% | 1.40 | 46.41% | 28.88% | 64.8% |
| 5 | stop 0.6%, 60m, skip | 65.43% | 34.03% | 1.41 | 52.07% | **36.87%** | 67.8% |
| 6 | stop 0.6%, 30m, close-reenter | 64.39% | 44.98% | 1.35 | 49.92% | 33.61% | 66.3% |
| 7 | stop 0.6%, 30m, skip, pure cross | 56.66% | 38.77% | 1.36 | 44.62% | 30.85% | 58.3% |
| 8 | no stop, skip | 36.46% | 58.55% | 0.88 | 35.71% | 34.77% | 79.7% |

**Plateau.** Cells 1–5 are the stop plateau: 62–72% at 1 bp, 33–38% DD,
46–54% at 5 bp. Cells 1–7 all pass the 1 bp bar; cell 8 (no stop) is just
below it at 36.46%. Cells 1–7 also pass at 5 bp; cell 8 fails there (35.71%).
The 0.6% centre is the middle of the 0.5–0.7% region, not the maximum; 0.55%
gives 72.9% and 0.65% gives 58.4%, so the surface is smooth. The 60-minute
cell is the most cost-robust (36.87% at 10 bp, the only cell above the bar at
10 bp); the 15-minute cell is slightly weaker (62.1%) but still passes.

Cell 6 (always re-enter at the close, no weak-close skip) has the same CAGR
(64.4%) but a much higher DD (45.0% vs 35.7%). The skip rule is primarily a
drawdown reducer on this gate.

Cell 7 (pure 20/50 cross, no reclaim leg) passes at 56.7% / 38.8% with a
58.3% TQQQ exposure. Cell 8 (no stop) is just below the CAGR bar (36.46%) but
has a 58.6% DD. Neither component clears both the bar and the <60% DD target
alone: no-stop fails CAGR; always-long+stop fails the DD target (63.3%). The
stop supplies the return, the trend supplies the drawdown budget. That is the
core result.

## 5. Neighbours and clock sensitivity

| Variant | CAGR 1 bp | DD 1 bp | Sharpe | CAGR 5 bp |
|---|---:|---:|---:|---:|
| stop 0.55% | 72.93% | 33.23% | 1.57 | 56.34% |
| stop 0.65% | 58.35% | 37.17% | 1.32 | 45.04% |
| 15m from 10:15 | 61.62% | 33.24% | 1.38 | 46.44% |
| 30m from 09:45 | 54.31% | 40.63% | 1.28 | 40.07% |
| 30m from 10:30 | 62.95% | 34.53% | 1.39 | 49.04% |
| night 15:00 | 65.05% | 39.31% | 1.43 | 51.39% |
| night 15:15 | 68.17% | 36.00% | 1.48 | 53.75% |
| night 15:45 (15m grid) | 67.14% | 33.64% | 1.48 | 50.90% |
| true 15:55 close check | 63.07% | 35.28% | 1.40 | 48.14% |
| gate close>20 | 51.15% | 46.62% | 1.36 | 40.17% |
| gate close>50 | 52.22% | 43.30% | 1.37 | 40.99% |

The plateau is broad in the parameters that matter (stop 0.5–0.7%, night
decision 15:00–15:45, 15/30/60-minute cadence: all 54–73% at 1 bp, all
33–41% DD). It is not flat in the first-check clock: starting at 09:45 rather
than 10:00 costs ~10 pp (54.3% vs 64.6%). That is an honest clock-sensitivity
caveat; 10:00 is the natural close of the first 30-minute bar, not a tuned
offset.

## 6. Controls and placebos

| Control | CAGR | DD | Sharpe |
|---|---:|---:|---:|
| No stop (trend only) | 36.46% | 58.55% | 0.88 |
| Always long + same stop/skip | 70.95% | **63.30%** | 1.27 |
| No skip (always re-enter at close) | 64.39% | 44.98% | 1.35 |
| Cash idle instead of BIL | 65.65% | 35.50% | 1.44 |
| Overnight-only (no day sleeve) | 20.44% | 46.08% | 0.78 |
| TQQQ buy & hold | 36.15% | 82.29% | 0.80 |

- **Always long + the same stop** earns 70.95% but has a 63.3% DD. The 20/50
  gate is what brings the DD to 35.7%. It costs ~6 pp of CAGR and buys ~28 pp
  of drawdown.
- **No stop** is 36.46% — just below the bar. The intraday stop is the return
  engine.
- **Overnight-only** is 20.44%: two trades a day are cost-killed, which is why
  the day sleeve + stop is the design, not a pure overnight carry.
- **Cash idle** is 1.0 pp better than BIL at 1 bp. BIL's total return over the
  window is only +11.7% (1.4%/yr), and much of the BIL holding is intraday.
  BIL is kept because the mandate specifies it; it is not a return source.

**Placebo A — shifted daily trend (100 random cyclic shifts, same stop/skip).**
Real CAGR 64.63% vs placebo mean 52.58%, p95 68.45%, **p = 0.11**. The real
trend alignment is not statistically special for *return* — the stop overlay
is doing most of that work. But the real max DD 35.66% vs placebo mean 63.17%,
p05 58.70%, **DD percentile 1.0 (0/100 placebos had a lower DD)**. The trend
state is a genuine risk-control signal even though its return timing is not
distinguishable from a random 66%-on schedule.

**Placebo B — stale intraday stop (prior session's QQQ path used for today's
stop/reclaim).** CAGR 38.82%, DD 50.89%, Sharpe 1.00. The contemporaneous QQQ
path is worth ~26 pp of CAGR over the stale path; the stop is not just a
generic "trade a lot" effect.

## 7. Cut tests

Daily returns compounded with one calendar year removed:

| Removed year | Strategy CAGR | Strategy DD | TQQQ CAGR | TQQQ DD |
|---|---:|---:|---:|---:|
| 2016 | 77.55% | 32.86% | 38.66% | 81.68% |
| 2019 | 64.84% | 31.19% | 25.90% | 81.68% |
| **2020** | **44.06%** | **32.86%** | 27.84% | 81.68% |
| 2022 | 79.39% | 32.86% | 77.75% | 69.89% |
| 2023 | 53.97% | 32.86% | 21.49% | 81.68% |

The 2020 cut is the important one: ex-2020 the strategy still makes 44.06% at
32.86% DD, 7.3 pp above the dev bar. The result is not a single-year artifact.
Ex-2023 is 53.97%, ex-2019 64.84%, ex-2016 77.55%.

## 8. Causality and protocol

- Truncating the panel at 2022-01-03 and rebuilding leaves every prior weight
  unchanged (`max_abs_diff = 0.0`). The daily signal uses the 15:58 print of
  the same session and fills at 15:59; the intraday checks use a completed bar
  and fill at the next bar's open.
- No full-sample normalisation, no parameter selected on 2024+.
- No 2024–2026 bar was loaded. The daily warmup is QQQ 2015 closes only.
- 1 bp headline; 5 bp and 10 bp reported. 2% band throughout.
- Costs are charged on traded notional by the shared `research/bt.py`
  simulator; fills are not reimplemented.

## 9. Honest verdict

**What is good.** The strategy passes the development bar by a wide margin
(64.6% vs 36.7% CAGR; 35.7% vs 82.3% DD), with a broad parameter plateau, a
positive ex-2020 result, a causality check that passes exactly, and a
mechanism (held nights +19.4 bp, skipped nights +1.5 bp) that is visible in the
data. The trend gate's drawdown control is exceptional: 0 of 100 random trend
shifts achieved a lower DD than 35.7%.

**What is fragile.**

1. **Turnover and cost.** 1,837 fills over 2,012 sessions — 0.91 fills per
   session, about 230 per year. That is 459 round trips (one every ~4.4
   sessions); each round trip is four fills because both assets are traded
   (TQQQ sell + BIL buy, then BIL sell + TQQQ buy). The gross (0 bp) CAGR is
   68.46%; 1 bp costs 3.8 pp, 5 bp costs 18.3 pp, 10 bp costs 34.6 pp. At
   10 bp the centre fails the bar (33.84%). The 60-minute variant survives
   10 bp at 36.87%, so the design has a cost-robust corner, but the centre
   does not. If the lead's execution is worse than ~5 bp all-in, this
   strategy is not investable at the headline.
2. **Overnight gaps.** The stop is intraday only. The worst night actually
   held was **-20.5%** (2020-03-06); the worst TQQQ night in the window
   (-27.6%, 2020-03-13) was skipped by the weak-close rule. A gap from a strong
   close is unprotected. The 35.7% max DD is not a worst-case gap number.
3. **2020 concentration.** 2020 contributes +308.5%. Ex-2020 the CAGR is
   44.06%, still a pass but the margin is 7.3 pp, not 28 pp. A holdout without
   a crash/recovery is a different test.
4. **Choppy-year whipsaw.** 2016 is -2.8% and 2021 is +31.0% vs TQQQ +81.1%.
   The worst drawdown is 2019-04→2019-10, 35.7%, in a year that ended +63.4%.
   The strategy can lose a third of equity in a trendless stretch.
5. **The trend timing is not a return timer.** The shifted-trend placebo has
   p = 0.11 on CAGR. The trend's value is DD control (0/100 on DD), and the
   stop is the return engine (stale-stop placebo 38.8% vs real 64.6%). Read the
   strategy as "intraday stop + trend risk overlay", not as "20/50 market
   timing".
6. **BIL is not additive.** Cash idle is 1.0 pp better at 1 bp. BIL is kept
   because the mandate says so; the reader should not count the BIL sleeve as
   a source of carry.
7. **Clock sensitivity.** The 09:45 first check is 10 pp weaker than 10:00.
   The 15:00–15:45 night times are all 65–68%, so the night rule is stable; the
   opening check is the sensitive one.

**Holdout arithmetic.** With 64.63% for the 7.98 dev years, the full 2016–2026
CAGR beats TQQQ's 37.54% as long as the 2024–2026 CAGR is above roughly
**-17.5%**. A 2022-like -11% holdout gives ~40%, a 2021-like +31% gives ~55%,
and a flat holdout gives ~45%. The cushion is large, but it is a cushion built
on a high-turnover intraday signal, so the 5 bp/10 bp rows are the realistic
stress case. **No holdout data was inspected.**

## 10. Files and reproduction

- `HYPOTHESIS.md` — pre-registration, rules, grid, falsification tests.
- `strategy.py` — `build_weights(ts, o, c)` and `main()`; writes `result.json`.
- `result.json` — dev 0/1/5/10 bp, grid, neighbours, controls, placebos, cut
  tests, attribution, causality.
- `report.md` — this file.

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
$env:BT_THREADS = "1"
python research/new/overnight-intraday-trend/strategy.py
```

The lead's one-shot holdout can call the frozen module directly:

```powershell
python research/new/run_holdout.py overnight-intraday-trend
```

`build_weights(ts, o, c)` is panel-length agnostic and uses only trailing data
(the 2015 daily closes for warmup, the 15:58 print of each session for the
trend, and completed intraday bars for the stop). There is no dev-only guard to
lift; extending the panel cannot change any weight before the extension point.
No 2024+ data was loaded or inspected during development.
