# FOMC + OpEx calendar TQQQ - development report

**Dev window:** 2016-01-04 -> 2023-12-29 (1-minute marks, next-open fills, 2% band)

**Bar:** TQQQ dev 36.72% CAGR / 82.29% max DD / 0.82 Sharpe. The same panel
recomputes TQQQ at **36.15% / 82.29% / 0.80**; the published 36.72% bar is the
harder one and is used for the pass/fail decision.

**Primary (pre-registered centre, G3):** FOMC decision +2..+15 sessions,
OpEx -1..+3 sessions, TQQQ at 100% inside the union, BIL otherwise, no
volatility gate.

**Family:** calendar/event. No trend SMA, drawdown circuit breaker or relative
strength is used.

---

## Verdict

**FAIL at the pre-registered centre. Do not send G3 to holdout.**

| | CAGR | max DD | Sharpe | TQQQ weight | corr to TQQQ | beta to TQQQ |
|---|---:|---:|---:|---:|---:|---:|
| **G3 primary, 1 bp** | **30.60%** | **51.70%** | **0.80** | **58.1%** | **0.70** | **0.48** |
| G3 primary, 5 bp | 27.93% | 52.54% | 0.76 | 58.1% | | |
| G3 primary, 10 bp | 24.66% | 53.57% | 0.71 | 58.1% | | |
| TQQQ, same 1-minute panel | 36.15% | 82.29% | 0.80 | 100% | 1.00 | 1.00 |
| Published TQQQ bar | 36.72% | 82.29% | 0.82 | 100% | | |
| **Gap (G3 vs published bar)** | **-6.12 pp** | **+30.59 pp** | **-0.02** | | | |

The calendar cuts the drawdown by 30.6 pp and matches TQQQ's Sharpe, but it
gives up 6.1 pp of CAGR. It is a risk-managed TQQQ beta, not a return edge.
The raw TQQQ return captured by the held blocks is **30.42% CAGR**, before BIL
yield and costs; the same windows would need **1.18x** that return to clear the
bar. Cash and costs cannot close a return gap that is already present in the
calendar itself.

The +20 FOMC edge cells (G5/G6) do clear the aggregate bar at 44.6%/45.0% CAGR
and 57.1%/51.0% DD, but they are the long end of the pre-registered grid, not
the centre. They are not promoted here: the mandate is to pick the centre, and
the robustness tests below show why the edge cells are fragile. A new
pre-registration and a one-shot holdout would be required before treating them
as a strategy.

---

## 1. What was built

Rules, exactly as pre-registered in `HYPOTHESIS.md`:

* Hardcoded **scheduled FOMC decision dates** and **monthly third-Friday OpEx
  dates** from 2015-12 through 2026-10-23.
* An event date is mapped to the first trading session on or after it. Offsets
  are trading sessions from that anchor.
* `held(k) = 1` if session `k` is in any FOMC or OpEx window. The target for
  session `k` is `held(k)` (no gate in G3). The strategy is long TQQQ at 100%
  inside the union and BIL otherwise.
* The target is decided at the close of session `k-1`; the shared `bt.py`
  simulator fills it at the next session's 09:30 open, with the 2% band and
  slippage on traded notional. Headline cost 1 bp; 5 bp and 10 bp reported.
* The primary has **no volatility filter**. The pre-registered risk variants
  G7 (soft gate, weight x0.5) and G8 (hard gate, weight 0) use TQQQ 20-session
  realised vol versus its trailing 252-session 75th percentile, shifted one
  session so only prior-close information is used. They are not selection
  candidates.

Calendar counts in the dev run:

| item | count | note |
|---|---:|---|
| FOMC dates listed | 86 | 1 pre-dev (2015-12-16), 63 dev, 22 future (2024-2026) |
| OpEx dates listed | 131 | 1 pre-dev (2015-12-18), 96 dev, 34 future (2024-2026) |
| FOMC windows in dev | 64 | includes the 2015-12-16 window that crosses into 2016 |
| OpEx windows in dev | 96 | monthly, 2016-2023 |
| held sessions (G3) | 1,170 / 2,012 | 58.15% of sessions, 104 contiguous blocks |

**Unscheduled FOMC actions are excluded.** 2020-03-03 and 2020-03-15 were
emergency decisions whose dates were not knowable in advance. The March 2020
scheduled meeting is also excluded: the actual decision was the 2020-03-15
emergency action, so anchoring a window to the scheduled 2020-03-18 date would
attach the rule to an event that did not happen then. This is why the dev FOMC
count is 63, not 64. The 2020-03-15 action is therefore not used to rescue the
calendar.

**OpEx Good Friday moves** are hardcoded: 2019-04-18, 2022-04-14 and
2025-04-17 (Thursday, because the third Friday was Good Friday). All other
months use the third Friday.

The 2015-12-16 FOMC is handled with a virtual anchor of -11 sessions: the
1-minute archive starts 2016-01-04, and Jan 4 is the 11th session after
Dec 16 (Dec 24 is a half session, Dec 25 closed). The +2..+15 window therefore
marks Jan 4-8 2016, exactly as it would with a full 2015 calendar.

## 2. Holdout-ready calendar, and the 2016-2023 invariance check

The 2024-2026 dates are **ex-ante schedule dates**, not price data. They are
hardcoded in `strategy.py` so a 2024-2026 run can call `build_weights` without
editing the calendar. They are inert in this development run because the panel
is truncated at 2023-12-29.

Evidence that adding them did not change the development result:

| calendar used | CAGR | max DD | Sharpe | TQQQ exposure |
|---|---:|---:|---:|---:|
| full list, 2015-12..2026-10-23 | 30.602% | 51.697% | 0.804 | 58.146% |
| dev-only list, <= 2023-12-29 | 30.602% | 51.697% | 0.804 | 58.146% |
| **delta** | **0.000** | **0.000** | **0.000** | **0.000** |

The maximum absolute weight difference between the two calendars over the dev
panel is **0.0e+00**. The price panel is asserted to end on 2023-12-29
15:59 ET; `no_2024_bars` is true. No 2024+ return enters the weights or the
simulation. The holdout run must supply its own bars, with enough pre-start
warm-up that the December 2023 FOMC +20 window (which extends into January
2024) is anchored correctly.

**Calendar validation:** every 2016-2023 FOMC date and every 2016-2023 OpEx
date is a trading session in the panel (`fomc_dates_not_sessions_in_dev: []`,
`opex_dates_not_sessions_in_dev: []`). The 2024-2026 dates are weekday schedule
dates and are not price-validated here, by design.

**Pre-cut causality:** rebuilding the weights on a panel truncated at
2020-03-12 11:07 gives a maximum absolute pre-cut weight difference of **0.0**
for G3 (calendar-only), G7 (soft gate) and G8 (hard gate). The primary uses no
price data at all; the gated variants use only prior closes.

## 3. Pre-registered grid and the plateau

The calendar grid is 3 FOMC lengths x 2 OpEx windows. G3 is the centre:
+15 is the median FOMC length and `-1..+3` is the OpEx window that contains
the expiration session. G7/G8 are risk variants, not selection candidates.

| id | FOMC | OpEx | gate | CAGR | max DD | Sharpe | wTQQQ | 5 bp | 10 bp | matched placebo pct |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| G1 | +2..+10 | -1..+3 | - | 19.87% | 66.10% | 0.64 | 47.3% | 17.09% | 13.70% | 50.6 |
| G2 | +2..+10 | +1..+4 | - | 17.17% | 62.22% | 0.59 | 42.7% | 14.29% | 10.79% | 43.4 |
| **G3** | **+2..+15** | **-1..+3** | **-** | **30.60%** | **51.70%** | **0.80** | **58.1%** | **27.93%** | **24.66%** | **77.0** |
| G4 | +2..+15 | +1..+4 | - | 31.60% | 46.22% | 0.83 | 55.4% | 28.86% | 25.50% | 78.0 |
| G5 | +2..+20 | -1..+3 | - | 44.61% | 57.06% | 0.98 | 69.6% | 42.19% | 39.22% | 96.2 |
| G6 | +2..+20 | +1..+4 | - | 45.05% | 50.99% | 0.99 | 68.0% | 42.54% | 39.45% | 96.4 |
| G7 | +2..+15 | -1..+3 | soft 0.5 | 31.13% | 44.31% | 0.90 | 51.5% | 28.61% | 25.57% | 77.6 |
| G8 | +2..+15 | -1..+3 | hard 0 | 28.54% | 43.70% | 0.90 | 44.9% | 26.26% | 23.47% | 74.0 |

`matched placebo pct` is the fraction of 500 exposure-matched random calendars
with a lower CAGR (Section 5). G7/G8 have lower exposure because of the gate;
their percentile is still measured against the 58.15%-exposure null, so the
comparison is conservative for them.

**The plateau is not a plateau.** The FOMC-length dimension is a monotonic
exposure ramp: 19.9% -> 30.6% -> 44.6% for +10/+15/+20 (centred OpEx). The
OpEx dimension is almost flat on the aggregate (G3 vs G4 +1.0 pp; G5 vs G6
+0.4 pp), which hides a severe year-by-year instability:

| pair | 2016 | 2020 | 2021 | 2022 | 2023 |
|---|---:|---:|---:|---:|---:|
| G3 (-1..+3) | 33.1% | 137.0% | 42.5% | -27.6% | 45.0% |
| G4 (+1..+4) | 11.0% | 49.4% | 73.6% | +0.3% | 40.9% |
| G5 (-1..+3) | 35.6% | 163.0% | 42.1% | -24.1% | 88.7% |
| G6 (+1..+4) | 16.8% | 96.4% | 97.0% | -8.4% | 69.8% |

A two-session shift in the OpEx window changes 2020 by 87.6 pp (G3 vs G4) and
2022 by 27.9 pp; at the +20 length it changes 2022 by 15.7 pp (G5 vs G6). The
aggregate CAGR is flat by coincidence, not because the OpEx flow is stable.
That is the opposite of a robust calendar plateau.

## 4. Why the centre fails: exposure arithmetic

The primary holds TQQQ for 1,170 of 2,012 sessions (58.15%), in 104 blocks.
The raw TQQQ open-to-open log return of those blocks is 2.1206, which is
**30.42% CAGR** before BIL and costs. The TQQQ bar requires 2.4972 log, i.e.
**36.72% CAGR**. The windows would need to deliver **1.178x** their observed
return:

| item | value |
|---|---:|
| held sessions / share | 1,170 / 58.15% |
| held blocks | 104 |
| raw TQQQ window log | 2.1206 |
| raw TQQQ window CAGR | 30.42% |
| log per held session | 0.1812% |
| bar log required | 2.4972 |
| **multiple of window return needed** | **1.178x** |
| shortfall log | 0.3767 |

This is the binding result. A calendar that is out of the market 42% of the
time must earn a higher per-session return than buy-and-hold; the observed
windows do not. The primary's 30.60% is only 0.18 pp above the raw window
capture because BIL yield offsets costs. There is no cash or cost treatment of
this calendar that reaches 36.72%.

## 5. Robustness

### 5.1 Event study: neither leg is special

Per-window open-to-open TQQQ returns, with a 4,000-draw same-length
random-window null:

| leg | n | mean | median | t | positive | null mean | null p95 | percentile of null |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| FOMC +2..+15 | 64 | +3.35% | +4.51% | 2.43 | 65.6% | +2.85% | +5.65% | **61.1** |
| OpEx -1..+3 | 96 | +1.39% | +1.64% | 1.61 | 58.3% | +1.00% | +2.41% | **66.9** |

The t-stats look positive, but the windows overlap and are serially
correlated, and the correct random-window null puts the observed means at only
the 61st and 67th percentiles. A random 14-session window has almost the same
average return. The FOMC leg is stronger than the OpEx leg, but neither is
statistically special.

### 5.2 Shift test: the peak is not at zero

Every FOMC and OpEx anchor shifted by N sessions, same lengths, no gate:

| shift | 0 | +1 | +2 | +3 | +4 | +5 | +9 | +10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| CAGR | 30.6% | 28.9% | 42.9% | **43.5%** | 30.4% | 23.6% | **43.5%** | 37.3% |

Negative shifts are mostly worse (e.g. -1 7.8%, -2 9.3%, -3 11.9%), but the
forward surface has two high points at +3 and +9 and the peak is **not at 0**.
A genuine event-window effect should peak on the true anchor. Adjacent shifts
overlap heavily (14-19 session windows), so this is not a decisive rejection
on its own, but it is not the clean confirmation the hypothesis needs. It is
consistent with the result being a broad exposure/timing effect rather than a
sharp FOMC or OpEx window.

### 5.3 Random-calendar placebo: good defence, ordinary return

500 draws. Each draw replaces the event anchors with random session starts,
keeping the number and lengths of the FOMC and OpEx windows. The **matched**
null then adds/removes random sessions so it holds exactly the primary's 1,170
sessions (58.15% exposure). This is the headline placebo: it asks whether the
calendar *timing* adds anything beyond the same TQQQ exposure.

| null | median CAGR | p95 CAGR | primary CAGR pct | primary DD pct | primary Sharpe pct | joint CAGR>=G3 and DD<=G3 |
|---|---:|---:|---:|---:|---:|---:|
| unmatched random windows (median exposure 49.3%) | 18.0% | 42.7% | 80.8 | 95.4 | 80.0 | - |
| **exposure-matched random calendar (58.15%)** | **19.5%** | **43.4%** | **77.0** | **98.6** | **78.4** | **1.4%** |

The primary beats 77% of random 58%-exposure calendars on CAGR; 23% beat it.
Its drawdown is better than 98.6% of them, and its Sharpe better than 78.4%.
So the calendar is a genuinely defensive overlay: it avoids a lot of the
drawdown. But the return is only moderately above a random calendar with the
same exposure, and the joint CAGR/DD hit rate is 1.4%. That is a
risk-management result, not a CAGR edge.

The +20 edge cells are at the 96.2/96.4th percentile of the matched null. They
are not pure noise, but they are also the two most exposed cells and the
extreme end of the grid; Section 3 shows their year-by-year OpEx sensitivity.

### 5.4 Decomposition: the OpEx leg is weak

| sleeve | CAGR | max DD | Sharpe | wTQQQ |
|---|---:|---:|---:|---:|
| FOMC only (+2..+15) | 24.96% | 39.80% | 0.76 | 43.8% |
| OpEx only (-1..+3) | 13.72% | 50.09% | 0.57 | 23.9% |
| Union (G3) | 30.60% | 51.70% | 0.80 | 58.1% |

The FOMC leg carries most of the return; the OpEx leg adds 5.6 pp of CAGR but
14.3 pp of exposure, and on its own is a low-Sharpe 0.57 sleeve. Combined with
the G3/G4 year-by-year swing, the "OpEx flow" part of the hypothesis is not
supported. The result is mostly a FOMC post-decision exposure story.

### 5.5 Cuts, concentration and the missing bull years

| period | G3 CAGR | G3 max DD | G3 Sharpe |
|---|---:|---:|---:|
| 2016-2019 | 22.0% | 51.7% | 0.70 |
| 2020-2021 | 84.9% | 42.1% | 1.50 |
| 2022-2023 | 3.6% | 45.0% | 0.35 |

| year | G3 | TQQQ |
|---|---:|---:|
| 2016 | +33.1% | +19.9% |
| 2017 | +56.3% | +114.5% |
| 2018 | -23.9% | -20.8% |
| 2019 | +43.9% | +148.2% |
| 2020 | +137.0% | +104.1% |
| 2021 | +42.5% | +81.1% |
| 2022 | -27.6% | -79.4% |
| 2023 | +45.0% | +192.0% |

The strategy wins in 2016, 2020 and 2022 and loses badly in the strong bull
years 2017, 2019, 2021 and 2023. That is why the full-period CAGR is below
TQQQ despite a much smaller drawdown. 2023 is the clearest failure: +45.0% vs
TQQQ +192.0%.

Leave-one-year-out: excluding 2020 drops CAGR to 19.2%; excluding 2022 raises
it to 41.5%; the other years leave 26.7%-40.5%. The pass/fail therefore depends
on the 2020 recovery and the 2022 crash avoidance, not on a steady calendar
premium.

Drop-best event windows:

| dropped | CAGR | max DD | excluded events |
|---|---:|---:|---|
| best 1 | 29.9% | 51.7% | 2020-04-29 |
| best 3 | 26.9% | 51.7% | 2020-04-29, 2022-06-15, 2022-11-02 |
| best 5 | 20.4% | 58.4% | + 2021-03-17, 2022-07-15 |

The top five windows contribute about 10 pp of CAGR. The result is not
uniformly spread across the sample; the 2022 bear-market rallies and the 2020
recovery matter.

### 5.6 Costs and turnover

G3 trades 413 times, **201.7x turnover per year** (1,610x total). The 2% band
does not help full TQQQ/BIL switches. Cost sensitivity:

| cost | CAGR | max DD | Sharpe |
|---|---:|---:|---:|
| 1 bp | 30.60% | 51.70% | 0.80 |
| 5 bp | 27.93% | 52.54% | 0.76 |
| 10 bp | 24.66% | 53.57% | 0.71 |

At 10 bp the centre is 12.1 pp below the bar. The +20 cells survive 10 bp
(39.22%/39.45%), but again they are not the centre.

### 5.7 Volatility overlay: risk help, not return help

| variant | CAGR | max DD | Sharpe | wTQQQ |
|---|---:|---:|---:|---:|
| G3 no gate | 30.60% | 51.70% | 0.80 | 58.1% |
| G7 soft gate (x0.5 above q75) | 31.13% | 44.31% | 0.90 | 51.5% |
| G8 hard gate (0 above q75) | 28.54% | 43.70% | 0.90 | 44.9% |

The soft gate is the best risk-adjusted variant: +0.53 pp CAGR and -7.4 pp DD,
Sharpe 0.90. The gate is shut on 22.7% of the held sessions. It improves the
defensive profile, but it still misses the CAGR bar by 5.6 pp. The hard gate
cuts too much return. A volatility overlay cannot fix a calendar that is
already 6 pp short before the overlay.

## 6. Honest verdict

**The FOMC + OpEx calendar family does not beat the development bar at its
pre-registered centre.** G3 earns 30.60% CAGR with 51.70% DD and 0.80 Sharpe
at 1 bp, versus the 36.72% / 82.29% / 0.82 bar. The drawdown is much better
and the Sharpe is equal, but the CAGR is 6.1 pp short. The raw TQQQ capture of
the held blocks is 30.42% CAGR; the same windows would need 1.18x their return,
so this is not a cost or cash-management problem.

The grid contains two aggregate passers, G5 and G6 at the +20 FOMC edge
(44.61%/45.05% CAGR, 57.06%/50.99% DD). They are **not** the centre. Promoting
them would be selecting the best cell after seeing the result, which the
mandate forbids. They are also fragile: the two OpEx variants differ by
15.7 pp in 2022, the FOMC-length dimension is an exposure ramp rather than a
plateau, the shift test peaks at +3/+9 rather than 0, and the event-study means
sit at only the 61st/67th percentile of a random-window null. If the lead
wants a +20 variant, it should be written as a new pre-registered hypothesis
("hold TQQQ through most of the FOMC cycle, with a post-expiry OpEx add") and
given its own one-shot holdout; it should not be presented as the same
calendar strategy.

The result is consistent with the repo's common finding: calendar and event
overlays can cut TQQQ's drawdown, but their full-period CAGR edge comes from
avoiding 2020/2022 and is paid for by missing the strong bull years (2017,
2019, 2021, 2023). There is no evidence here of an independent, all-weather
calendar alpha.

No 2024-2026 price bar enters the panel, weights or simulation; the panel is
asserted to end on 2023-12-29. No website, existing strategy, commit or push
was touched. Do not send G3 to holdout.

## 7. Reproduction

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
$env:BT_THREADS = "1"
python research/new/family-calendar-event/strategy.py --draws 500
```

Files: `HYPOTHESIS.md` (pre-registration), `strategy.py` (`build_weights` +
`main`), `result.json` (primary, grid, event study, shift, placebo, cuts,
calendar replay), `report.md` (this file).
