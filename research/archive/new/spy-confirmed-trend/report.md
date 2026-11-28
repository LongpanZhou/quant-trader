# SPY-confirmed TQQQ trend ladder — development report

**Verdict: PASS on the development bar, with a large risk margin and an
honest caveat.** On 1-minute marks, 2016-01-04 → 2023-12-29, the primary
strategy earns **50.36% CAGR / 43.27% max DD / 1.20 Sharpe** at 1 bp, versus
TQQQ buy-and-hold **36.72% / 82.29% / 0.82** (lead-provided bar; the harness's
own 1-minute TQQQ benchmark is 36.15% / 82.29% / 0.80). The strategy is
**99.9% invested** — 72.3% average TQQQ, 25.4% BIL, 2.2% QQQ — with a **0.64
daily correlation** to TQQQ (beta 0.39, upside capture 58%, downside capture
53%).

The caveat is important: this is **risk-managed TQQQ beta, not a bull-market
TQQQ beater**. It matches TQQQ in 2017, 2020 and 2021, loses far less in 2018
and 2022, and gives up a lot of upside in 2019 and 2023. The literal mandate
centre — QQQ 100-day SMA, SPY 200-day SMA, 85% vol target, −10% brake — **fails
at 20.64% CAGR / 51.14% DD**. The delivered strategy moves to a 150-day QQQ SMA
and a −15% brake, the centre of a broad passing plateau. That deviation is
disclosed and tested in Section 3; it is not hidden.

---

## 1. What was built

A daily-refreshed, long-only QQQ/TQQQ/BIL ladder. At each session's 15:59
close:

```
qqq_up = QQQ > SMA_150(QQQ)
spy_up = SPY > SMA_200(SPY)
rv20   = annualised 20-session stdev of TQQQ daily returns
scale  = min(1, 0.85 / rv20)
dd     = TQQQ / max(TQQQ, last 20 sessions) - 1
```

A fresh breach `dd <= -15%` forces BIL for five sessions. The brake does not
re-arm until TQQQ recovers above −7.5% from the 20-day high, so a slow recovery
does not pin the book in BIL for months. Targets:

| State | Target |
|---|---|
| Brake lockout | BIL 100% |
| QQQ up and SPY up | TQQQ `scale`, remainder BIL |
| QQQ up only | QQQ 100% |
| Otherwise | BIL 100% |

Fills are at the next session's open with a 2% band. All indicators are
trailing; the panel ends 2023-12-29 and every daily Parquet read is sliced at
that date. SPY is signal-only and never held or marked.

---

## 2. Headline result

| Cost | CAGR | Max DD | Sharpe | Sortino | Exposure | Corr to TQQQ | Fills |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 bp | **50.36%** | **43.27%** | **1.20** | 1.69 | 99.9% | 0.64 | 222 |
| 5 bp | 49.17% | 43.96% | 1.19 | 1.66 | 99.9% | 0.64 | 222 |
| 10 bp | 47.70% | 44.81% | 1.16 | 1.63 | 99.9% | 0.64 | 222 |

| Reference | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| TQQQ buy & hold (lead bar) | 36.72% | 82.29% | 0.82 |
| TQQQ buy & hold (harness, 1-min) | 36.15% | 82.29% | 0.80 |
| QQQ buy & hold (daily closes) | 18.86% | 35.11% | 0.87 |
| QQQ 150-SMA → TQQQ/BIL, no SPY/brake/vol (daily) | 44.54% | 58.71% | 1.02 |
| **Primary** | **50.36%** | **43.27%** | **1.20** |

The max drawdown is **43.27% on 1-minute marks** (38.01% on daily 15:59
marks), peak **2021-11-22** to trough **2023-01-25**. It is the 2022 bear, not
a single-day crash.

---

## 3. Pre-registered grid and the plateau

The eight-cell grid was frozen before the final 1-minute run. A coarse
daily-mark scan was used only to locate the region; all eight cells are
reported.

| Cell | QQQ SMA | SPY SMA | Vol target | Brake | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|---:|---:|---:|---:|
| A `mandate_100_10` | 100 | 200 | 0.85 | 10% | **20.64%** | 51.14% | 0.69 |
| B `primary_150_15` | 150 | 200 | 0.85 | 15% | **50.36%** | 43.27% | 1.20 |
| C `qqq135` | 135 | 200 | 0.85 | 15% | 45.56% | 44.24% | 1.13 |
| D `qqq160` | 160 | 200 | 0.85 | 15% | 50.37% | 39.89% | 1.21 |
| E `spy180` | 150 | 180 | 0.85 | 15% | 46.87% | 46.91% | 1.15 |
| F `spy220` | 150 | 220 | 0.85 | 15% | 48.65% | 42.97% | 1.17 |
| G `vol70` | 150 | 200 | 0.70 | 15% | 49.47% | 43.00% | 1.21 |
| H `brake20` | 150 | 200 | 0.85 | 20% | 45.89% | 42.08% | 1.11 |

**Seven of eight cells clear the 36.72% bar. The only failure is the literal
mandate centre.** The plateau is not a single spike: moving the QQQ SMA by
±25 sessions, the SPY SMA by ±20, the vol target between 70% and 100%, or the
brake between 15% and 20% leaves CAGR in the mid-40s to low-50s with DD under
47%.

### 3.1 Neighbour surface (daily marks, post-hoc)

CAGR / max DD, QQQ SMA × brake, SPY SMA fixed at 200:

| QQQ SMA \ brake | 12% | 15% | 20% |
|---:|---:|---:|---:|
| 130 | 36.03 / 43.31 | 43.46 / 38.18 | 38.91 / 41.48 |
| 140 | 40.24 / 40.51 | **48.93 / 37.58** | 43.59 / 41.61 |
| 150 | 39.48 / 40.92 | **50.35 / 38.01** | 45.88 / 39.23 |
| 160 | 39.14 / 40.23 | **50.35 / 37.62** | 45.72 / 39.23 |
| 170 | 36.48 / 47.85 | 47.61 / 45.57 | 43.18 / 39.64 |

SPY SMA at 150/15: 180 → 46.86%, 200 → 50.35%, 220 → 48.64% (daily marks).
The 15% brake row is the plateau; 12% is the cliff edge (two of five cells fall
below 36.72%), and 20% is lower but still passing.

### 3.2 Why the literal mandate centre fails

The 100-day QQQ SMA and the −10% TQQQ brake are **too fast for a 3x ETF**:

- A 10% TQQQ drawdown is a routine ~3.3% QQQ pullback. The brake fires, sits
  in BIL for five sessions, and re-enters after the rebound has started. In
  2019 this repeatedly clipped May, August and October.
- The 100-day SMA exits on the same routine pullbacks. In 2019 it was in BIL
  during January's +30% TQQQ rebound and again during the June rebound; the
  year returned +18% instead of the strategy's +49% at the 150-day cell.
- The literal centre's 51.14% DD is not even a risk improvement: it is worse
  than the 150/15 cell's 43.27% while earning 30 pp less CAGR.

A −10% brake at the 150-day SMA is a knife-edge 36.99% CAGR (an extra
diagnostic, not one of the eight grid cells). The −15% threshold is the first
one that leaves the 2019/2021 whipsaws alone while still catching 2018-Q4 and
2022.

If the lead insists on the 100-day QQQ SMA, there is a mandate-adjacent
variant: a **2% tolerance band below the 100-day SMA** plus the 15% brake
reaches **42.81% CAGR / 53.37% DD / 1.08 Sharpe** on 1-minute marks. It passes,
but with 6.1 pp less CAGR margin and 10 pp more drawdown than the 150/15 cell.
The 150/15 cell is preferred because its holdout cushion is larger, not because
the 100-day length is unusable.

---

## 4. Component evidence: is the SPY confirmation doing anything?

All rows are the primary with one component changed, 1-minute marks, 1 bp:

| Variant | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| **Primary (QQQ 150 + SPY 200 + vol + brake)** | **50.36%** | **43.27%** | **1.20** |
| No SPY gate (QQQ 150 only) | 48.89% | 47.61% | 1.15 |
| SPY gate only (no QQQ gate) | 42.68% | 65.19% | 1.02 |
| No gates (TQQQ + vol + brake) | 40.04% | 78.60% | 0.89 |
| No brake | 44.85% | 52.02% | 1.06 |
| No vol target | 49.05% | 44.31% | 1.17 |
| No QQQ fallback (BIL instead) | 51.19% | 41.02% | 1.23 |
| Brake exits to QQQ, not BIL | 50.11% | 41.26% | 1.19 |
| Literal mandate 100/10 | 20.64% | 51.14% | 0.69 |
| 100/15 | 34.73% | 48.80% | 0.96 |

Daily-mark decomposition, which isolates the three ideas cleanly:

| Build | CAGR | Max DD |
|---|---:|---:|
| QQQ 150-SMA ladder (TQQQ/BIL only) | 44.54% | 58.71% |
| + 85% vol target + −15% brake | 48.91% | 43.94% |
| + SPY 200 confirmation | 50.35% | 38.01% |

**The SPY confirmation is real but secondary**: +1.5 pp CAGR and −4.3 pp DD on
1-minute marks (+1.4 pp / −5.9 pp on daily marks). The QQQ 150-day trend and
the brake do most of the work. The vol target is nearly inert: `scale` is 1.0
on 95.1% of TQQQ days, its mean is 0.996, and its minimum is 0.75. It binds
mostly in 2020 and 2022 and is worth only +1.3 pp CAGR / −1.0 pp DD.

The QQQ fallback is a small drag on CAGR (−0.8 pp) but improves DD by 2.3 pp.
It is retained because the mandate asks for it and because it is the mechanism
that makes the SPY confirmation economically meaningful.

---

## 5. Year by year, and the three stress episodes

Calendar-year returns, daily 15:59 marks (the headline uses 1-minute marks):

| Year | Strategy | TQQQ | Comment |
|---:|---:|---:|---|
| 2016 | +7.0% | +18.6% | Three whipsaw exits; missed the February rebound |
| 2017 | +113.0% | +113.0% | Fully invested all year |
| 2018 | +17.6% | −23.5% | Strong Jan-Sep, then out for most of Q4 |
| 2019 | +49.4% | +130.5% | Late re-entry after the Dec-2018 crash; May/August exits |
| 2020 | +100.4% | +99.8% | Exited the COVID crash late, missed most of the rebound, caught the summer |
| 2021 | +93.2% | +90.9% | Two short exits; largely fully invested |
| 2022 | **−28.0%** | **−79.7%** | Late January exit, then BIL; a few whipsaws |
| 2023 | +108.2% | +204.9% | Feb-Mar and Aug-Oct exits cost heavily |

Stress episodes on 1-minute marks:

| Episode | Strategy | TQQQ | Strategy max DD |
|---|---:|---:|---:|
| 2018-Q4 (Sep 20 → Dec 31) | −25.2% | −47.4% | −30.2% |
| 2018 full year | +21.8% | −20.8% | −30.4% |
| 2020 COVID (Feb 19 → Mar 23) | −34.8% | −69.5% | −36.0% |
| 2020 recovery (Mar 23 → Jun 30) | +30.3% | +162.1% | −18.9% |
| 2022 bear (Jan 3 → Oct 14) | −23.7% | −77.1% | −25.3% |
| 2022 full year | −26.9% | −79.3% | −29.1% |
| 2023 full year | +110.9% | +195.9% | −28.7% |

This is the honest core of the result:

- **2018 and 2022 are the wins.** The strategy is out of the worst of both.
  The full-year 2018 is positive because it was long TQQQ during the strong
  first three quarters, then stepped aside in October.
- **2020 is not a win in the crash.** It exited after TQQQ had already fallen
  ~19% from its 20-day high, re-entered three times during the crash (the
  five-session lockout is short), lost 34.8% peak-to-trough, and then missed
  most of the +162% rebound. It still ended the year at +100% because the
  summer and autumn trend was strong and it was fully invested for that.
- **2019 and 2023 are the costs.** The 150-day SMA re-enters late after a
  crash and exits on routine pullbacks. The strategy gives up 80 pp of 2019
  and 97 pp of 2023. Any holdout that is a smooth bull market will look more
  like 2019/2023 than like 2022.

---

## 6. Whipsaw and late exits

- **79 state switches** (about 10/year), **29 brake triggers**, **135 brake
  days**, 222 fills.
- Median state run is **5 sessions**; mean 25 sessions. The book is either
  fully TQQQ or fully BIL 97% of the time; QQQ is held on only 45 sessions.
- **2016 is the worst whipsaw year**: +7.0% with eight switches, including
  three brake exits between April and July.
- **January 2022 is the late-exit case.** The brake exited on 2022-01-07 at
  TQQQ −17.0% from its 20-day high, re-entered on 2022-01-14, exited again on
  2022-01-18 at −23.2%, then stayed in BIL for most of the year. The 2022 loss
  is mostly the January drawdown, not the post-exit period.
- **March 2020 is the re-entry case.** After the 2020-02-24 exit at −19.1%,
  the five-session lockout re-entered on 2020-03-02 at a 0.86 TQQQ weight,
  exited again on 03-03, re-entered on 03-04 at 0.78, exited on 03-05, and
  finally stayed in BIL from 03-09. The whipsaw cost several percentage points
  on top of the initial crash loss.
- **The brake is a tail control, not the main 2022 hedge.** The 150-day QQQ
  trend is what keeps 2022 from being a −50% year; removing the brake changes
  2022 from −28% to −29%. The brake's value is concentrated in 2020 (+100% vs
  +63% without it) and 2023 (+108% vs +96%). It is a five-session circuit
  breaker, not a regime model.

---

## 7. Robustness

### 7.1 Costs and execution delay

| Cost | CAGR | DD |
|---:|---:|---:|
| 1 bp | 50.36% | 43.27% |
| 5 bp | 49.17% | 43.96% |
| 10 bp | 47.70% | 44.81% |

The 10 bp result still clears the bar by 11 pp. Execution delay on daily marks:

| Extra sessions of delay | CAGR | DD |
|---:|---:|---:|
| 0 | 50.35% | 38.01% |
| 1 | 47.56% | 40.52% |
| 2 | 46.97% | 47.55% |
| 3 | 42.35% | 54.74% |
| 5 | 56.44% | 38.63% |

The lag curve is **non-monotone**: a five-session delay earns more. That is
timing luck, not robustness. The honest read is that the strategy survives one
to three sessions of delay but the exact signal timing matters.

### 7.2 Placebo tests (200 draws, daily marks)

| Placebo | Actual CAGR | Median | 5th pct | 95th pct | Actual rank |
|---|---:|---:|---:|---:|---:|
| Block-shuffle targets, 20-day blocks | 50.35% | 24.82% | 5.58% | 47.41% | **0.965** |
| Circular SPY-gate shift | 50.35% | 39.87% | 31.30% | 48.32% | **0.965** |

The timing is not a random artifact: the actual is at the 96.5th percentile of
both placebos. But the margin over the 95th percentile of the block shuffle is
only 2.9 pp; the edge is real, not enormous.

### 7.3 Cut tests (daily marks)

| Cut | Strategy CAGR | TQQQ CAGR |
|---|---:|---:|
| Drop 2016 | 57.87% | 38.66% |
| Drop 2017 | 42.54% | 27.06% |
| Drop 2018 | 54.64% | 46.60% |
| Drop 2019 | 50.54% | 25.90% |
| Drop 2020 | 43.38% | 27.84% |
| Drop 2021 | 45.97% | 30.34% |
| Drop 2022 | 66.36% | 77.75% |
| Drop 2023 | 43.49% | 21.49% |
| Drop best 10 days | 34.93% | 22.90% |
| Drop best 20 days | 23.95% | 12.18% |

Every drop-year cut is above 42%. **No single year is essential.** But dropping
the best 10 days takes the absolute CAGR below the bar (34.93%), and dropping
the best 20 takes it to 23.95%. The strategy still beats TQQQ under those cuts
by 12 pp, but it is a concentrated, high-volatility return stream — as any 3x
strategy is. The top 10 days account for 26.6% of total log return; the best day
is +11.9% and the worst is −15.4%.

### 7.4 Subperiods (1-minute marks)

| Period | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| 2016-2019 | 44.10% | 33.97% | 1.18 |
| 2020-2023 | 56.32% | 43.27% | 1.22 |
| 2016-2020 | 55.38% | 37.04% | 1.28 |
| 2021-2023 | 42.45% | 43.27% | 1.08 |

Both halves clear the bar. The second half is stronger because 2022 is the
crash-avoidance payoff; the first half is still 44.1%.

---

## 8. Exposure, correlation and capture

| Metric | Value |
|---|---:|
| Average TQQQ weight | 72.3% |
| Average QQQ weight | 2.2% |
| Average BIL weight | 25.4% |
| Invested exposure (incl. BIL) | 99.9% |
| Daily correlation to TQQQ | 0.64 |
| Beta to TQQQ | 0.39 |
| Upside capture (TQQQ up days) | 58.0% |
| Downside capture (TQQQ down days) | 52.7% |
| TQQQ days | 1,462 / 2,012 |
| QQQ days | 45 |
| BIL / brake days | 505 |
| Mean TQQQ scale on TQQQ days | 0.996 |
| Scale binding (<0.99) on TQQQ days | 4.9% |

The low beta explains the profile: the strategy is not trying to match TQQQ
day for day. It holds TQQQ about 73% of the time, sits in BIL about 25%, and
uses QQQ only at the SPY-confirmation margin.

---

## 9. Honest verdict and holdout risk

**What works.** The combination clears the development bar by 13.6 pp of CAGR
with half the drawdown, on a broad plateau, at 10 bp, and with a 96.5th
percentile placebo rank. The 2018-Q4 and 2022 protection is real: −25% and
−27% versus −47% and −79% for TQQQ. The SPY confirmation adds a modest but
genuine risk reduction, and the brake is worth about 5.5 pp of CAGR and 9 pp
of DD.

**What does not work.** The literal mandate is not the delivered strategy. The
100-day QQQ SMA and −10% brake fail (20.64% CAGR), and even 100/15 is only
34.73%. The 150-day QQQ SMA is close to the old 165-day base that the program
deliberately avoids; the SPY confirmation, the vol target and the brake are
what make this a different strategy, but the trend core is similar. The vol
target is nearly inert. The strategy is a low-beta crash-avoidance overlay on
a slow QQQ trend, not a new source of alpha.

**Holdout risk.** The development edge is concentrated in crash avoidance. A
2024-2026 holdout that is a smooth bull market with no 2022-style bear will
look like 2019 or 2023: the strategy will lag TQQQ badly. The full-window bar
is still likely to be cleared because the development cushion is large. A
simple sensitivity, using **no holdout data**, shows the full-window CAGR for
a hypothetical holdout return:

| Hypothetical 2024-26 CAGR | Full 2016-26 CAGR |
|---:|---:|
| −10% | 31.61% |
| −5% | 33.47% |
| 0% | 35.25% |
| +5% | 36.98% |
| +10% | 38.64% |
| +20% | 41.81% |
| +30% | 44.79% |
| +40% | 47.60% |

The strategy needs only about **+6% CAGR in the holdout** to clear 37.54%. That
is a low bar, but it is not free: a flat or negative holdout fails. The main
scenario that hurts is a repeat of 2020's V-shaped crash — a late exit, a
short five-session lockout, and a missed rebound — followed by a weak bull.

**Recommendation.** Submit this to the one-shot holdout as a risk-managed
candidate, not as a TQQQ replacement. If the lead requires the literal 100/10
mandate, this strategy does not satisfy it; the honest result for that exact
rule is a fail at 20.64%.

---

## 10. Reproduction

From the repo root:

```powershell
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
$env:BT_THREADS = "1"
python research/new/spy-confirmed-trend/strategy.py
```

`build_weights(ts, o, c)` returns the (n, 3) QQQ/TQQQ/BIL target matrix.
`main()` writes `result.json`. The development panel is requested with
`end=2023-12-29`; the holdout guard raises if a 2024+ bar is passed and the
lead's runner lifts it explicitly. No 2024-2026 observation was used for
signal construction, grid selection or evaluation; every strategy data read is
filtered at 2023-12-29.
