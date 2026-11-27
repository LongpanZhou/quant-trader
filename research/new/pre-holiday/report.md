# Pre-holiday TQQQ — report

**Dev window:** 2016-01-04 → 2023-12-29 (1-minute marks, next-open fills, 2% band)
**Bar:** TQQQ dev 36.72% CAGR / 82.29% max DD / 0.82 Sharpe. Recomputing the
same bar on this panel gives **36.15% / 82.29% / 0.80**, so the published
number is the slightly harder one and is used throughout.
**Primary:** G1 — hold TQQQ for the 3 sessions before every scheduled NYSE
holiday, BIL otherwise, TQQQ weight halved when 20-day realised vol is above
its trailing 252-day 75th percentile.

---

## Verdict

**FAIL — do not send to holdout.**

| | CAGR | max DD | Sharpe | TQQQ weight | corr to TQQQ |
|---|---:|---:|---:|---:|---:|
| Primary G1 | **4.23%** | 31.22% | 0.34 | 9.2% | 0.28 |
| TQQQ | 36.15% | 82.29% | 0.80 | 100% | 1.00 |
| **Gap** | **−31.9 pp** | +51.1 pp | −0.46 | | |

The pre-holiday window is **not statistically distinguishable from a random
window**: the 72 three-session windows average +0.49% (t = 0.52), which sits at
the **43.5th percentile** of a 4,000-draw random-window null and the **50.2nd
percentile** of a 500-draw strategy placebo. The best cell in the
pre-registered grid is 15.5 CAGR points short of the bar, and the whole 1–3
session family spans 1.5%–5.3% CAGR.

The reason is arithmetic, not bad luck: 10.7% of sessions cannot carry a
fully-invested 3× fund unless each window compounds ~3.5% (a 20× multiple of
what the sample delivered). Across the 12 window lengths scanned (1–25
sessions), nothing with DD below 60% gets above **21.2% CAGR** — no
calibration of this mandate closes the gap.

---

## 1. What was built

Rules, exactly as pre-registered in `HYPOTHESIS.md`:

* 73 scheduled NYSE holidays hardcoded for 2016–2023; `2018-12-05` (Bush day of
  mourning) excluded because an unscheduled closure is not knowable in advance.
  The list reproduces **every** weekday gap in the panel and contains no date
  that traded (`calendar_check` in `result.json`).
* `k` = last session strictly before the holiday. Long TQQQ for sessions
  `k−back+1 … k`, BIL otherwise. Entry at the 09:30 open; exit at the 09:30
  open of the first session after the holiday, so the position spans the
  closure — with next-open fills a daily strategy cannot leave at the close.
* Vol gate: TQQQ 20-session realised vol vs its trailing 252-session q75
  (gate computed through `k−1`, applied to `k`; no look-ahead). High vol →
  TQQQ weight × 0.5, BIL the rest.
* 72 usable windows (the 2016-01-01 window starts in the warm-up and is
  dropped), 216 held sessions = 10.7% of sessions.

Costs: 1 bp headline, 5 bp and 10 bp. Turnover is 279× total (35×/yr), so
costs matter: **4.23% → 2.92% → 1.29% CAGR** at 1/5/10 bp.

## 2. Pre-registered grid

| id | back | exit | half-days | vol gate | CAGR | DD | Sharpe | wTQQQ | 5bp | 10bp |
|---|---:|---|---|---|---:|---:|---:|---:|---:|---:|
| **G1** | 3 | hold_through | no | 0.5 @ q75 | **4.23** | 31.2 | 0.34 | 9.2 | 2.92 | 1.29 |
| G2 | 1 | hold_through | no | — | 1.52 | 31.1 | 0.19 | 3.4 | 0.07 | −1.73 |
| G3 | 2 | hold_through | no | — | 5.29 | 28.1 | 0.40 | 7.0 | 3.78 | 1.92 |
| G4 | 3 | hold_through | no | — | 2.38 | 41.0 | 0.22 | 10.6 | 0.91 | −0.90 |
| G5 | 3 | exit_1559 | no | — | 3.47 | 37.3 | 0.28 | 10.6 | 1.98 | 0.15 |
| G6 | 3 | hold_through | yes | — | 2.65 | 38.8 | 0.23 | 10.8 | 1.17 | −0.64 |
| G7 | 3 | hold_through | no | 0 @ q50 | 2.33 | 23.2 | 0.25 | 5.5 | 1.49 | 0.45 |
| G8 | 5 | hold_through | no | — | **21.21** | 42.3 | **0.88** | 17.5 | 19.61 | 17.64 |

**The plateau does not exist.** Adjacent window lengths swing by 8–13 CAGR
points (1.5 → 5.3 → 2.4 → 14.9 → 21.2 → 13.6 → 8.4 for back 1…7). One standard
error on the CAGR from window selection alone is **±8.8 points**
(`sampling_error`), larger than the entire 1–3 session range. Any statement of
the form "the pre-holiday strategy made X%" is inside the noise.

G1 is the mechanism-faithful cell, not the best cell: it was fixed in
`HYPOTHESIS.md` before the final run, and the grid is a plateau test rather
than a menu. A coarse scan of window length, exit mode and filter settings was
run first and is what told us the plausible ranges — that is disclosed here and
in §5 of the pre-registration.

The mandated volatility filter is **a risk dial, not an alpha source**: it
lifts G1 above G4 (4.23 vs 2.38% CAGR) and cuts DD from 41.0 to 31.2, and the
hard gate G7 cuts DD to 23.2% at 2.33% CAGR. Every setting buys drawdown with
return; there is no vol state in which the pre-holiday premium becomes large.

## 3. Is the effect real?

Per-window TQQQ return, exact fill-to-fill, 72 windows:

| measure | mean | median | sd | t | hit rate | sum log | CAGR if only these days |
|---|---:|---:|---:|---:|---:|---:|---:|
| hold_through (open→open) | +0.490% | +1.172% | 7.96% | **0.52** | 59.7% | +12.15% | 1.53% |
| session only (open→close) | +0.576% | +1.290% | 7.16% | **0.68** | 58.3% | +23.12% | 2.94% |

Random-window null (4,000 draws of 72 random 3-session open→open windows):
mean of means **+0.618%**, sd 0.794%. The pre-holiday mean is at the **43.5th
percentile** — i.e. *below* a random calendar of the same shape.

Decomposition inside the windows: intraday log **+15.6%**, overnight log
**−3.5%**. Over all sessions TQQQ earns 36.5% of its log return intraday and
63.5% overnight (`decomposition_all_sessions`), so the pre-holiday premium, to
the extent it exists, is a *session* phenomenon — consistent with the
literature — and the windows happened to miss the overnight drift.

That is the honest reading: the point estimate is positive and of the size the
literature reports (≈+12 bp/session on the index, amplified to ≈+35 bp on
TQQQ), but it is nowhere near significant at 72 observations, and it is roughly
an order of magnitude short of what the mandate needs.

Concentration (the effect is not a broad-based premium):

| cut | CAGR | max DD | Sharpe |
|---|---:|---:|---:|
| primary | 4.23 | 31.2 | 0.34 |
| drop best 1 window | 2.71 | 34.0 | 0.25 |
| drop best 3 windows | **−0.89** | 37.0 | 0.03 |
| drop best 5 windows | **−3.05** | 47.1 | −0.11 |

Five of 72 windows (7%) contribute **+0.79 of log return**; the other 67 sum to
**−0.67**. Removing the best three turns the strategy negative.

## 4. Placebo and neighbour tests

**Random-day placebo** (500 draws, 72 random 3-session blocks, same length):

| | median | p90 | p95 | p99 | max | primary pct |
|---|---:|---:|---:|---:|---:|---:|
| CAGR | 4.13% | 13.97% | 16.03% | 19.89% | 25.54% | **50.2%** |
| max DD | 42.97% | — | — | — | — | 85.6% (better) |
| Sharpe | 0.30 | — | 0.87 (p95) | — | 1.37 | 54.4% |

The primary's CAGR is exactly the median of a random calendar. 13.4% of random
draws beat it on *both* CAGR and DD. The **exposure-matched phase placebo**
(27 phases of ~73 non-overlapping 3-session blocks, ~11% exposure) has median
CAGR 5.96% and puts the primary at the **44.4th percentile**.

**Holiday-shift test** (move every anchor by N sessions, same 3-session hold):

```
shift  -10   -9   -8   -7   -6   -5   -4   -3   -2   -1    0   +1   +2   +3   +4   +5   +6
CAGR   +4.5 +11.0 +15.7 +4.7 -6.2 -16.1 -7.4 +9.3 +16.7 +14.3 +2.4 +10.7 +6.6 +17.6 +16.1 +17.0 +4.7
```

The genuine anchor (0) is at the **bottom** of the profile; +3 and +5 sessions
give 17.6% and 17.0%. A real pre-holiday premium would peak at 0. This is the
single most damaging result for the hypothesis: the return in "pre-holiday"
backtests comes from days that are *not* pre-holiday.

Other neighbours: `exit_1559` (no holiday gap) beats `hold_through` at 3
sessions (3.47% vs 2.38%); adding the 15 shortened sessions changes almost
nothing (2.65%); including the unscheduled 2018-12-05 closure gives 3.52%.

## 5. Cut tests

| period | CAGR | DD | Sharpe | wTQQQ |
|---|---:|---:|---:|---:|
| 2016–2019 | 1.73 | 20.5 | 0.19 | 9.2 |
| 2020–2021 | 5.50 | 31.2 | 0.38 | 9.2 |
| 2022–2023 | 6.80 | 21.1 | 0.45 | 9.2 |

| year | strategy | TQQQ |
|---|---:|---:|
| 2016 | +0.2 | +19.9 |
| 2017 | +3.1 | +114.5 |
| 2018 | −0.3 | −20.8 |
| 2019 | +3.8 | +148.2 |
| 2020 | −7.9 | +104.1 |
| 2021 | +19.2 | +81.1 |
| 2022 | −13.8 | −79.4 |
| 2023 | +28.9 | +192.0 |

Leave-one-year-out CAGR: ex-2023 **0.74%**, ex-2021 **2.03%**, ex-2022 7.09%,
ex-2020 5.72% — the result is a 2021/2023 artifact.

**The 31% max DD is one window.** Peak 2020-07-08 → trough 2020-11-23; the
3-session window ending 2020-09-04 (Labour Day) lost **−28.8%** of equity on its
own. A sparse strategy on a 3× fund is not a low-risk strategy: it is a
sequence of 100%-TQQQ bets, and one bad three-day window can erase three years
of premium.

## 6. Why the mandate cannot work

| | value |
|---|---:|
| TQQQ log return required over 7.98y (36.72% CAGR) | 2.497 |
| log return delivered by the 72 windows (unfiltered) | 0.122 |
| **multiple of window return needed** | **20.5×** |
| required log return per 3-session window | 3.47% |
| observed log return per window | 0.17% |
| required arithmetic return per window | 3.78% |
| observed arithmetic return per window | 0.49% |

Holding 10.7% of sessions, each 3-session window would have to compound
**+3.5%** (≈+1.16% per session on TQQQ, i.e. ≈+0.39% per session on QQQ after
3× amplification and decay). No documented pre-holiday effect is within an
order of magnitude of that; ours is +0.17% log per window.

The only cells that clear the *published* bar are those with ≥60% of sessions
held, which are not pre-holiday strategies at all:

| back | CAGR | DD | Sharpe | sessions held |
|---:|---:|---:|---:|---:|
| 12 | 23.44 | 73.2 | 0.74 | 39.2% |
| 15 | 26.59 | 74.9 | 0.76 | 47.6% |
| **20** | **42.64** | **75.1** | 0.94 | 60.8% |
| 25 | 30.27 | 78.9 | 0.75 | 71.4% |

back=20 "passes" only by holding 61% of sessions; its neighbours give 26.6% and
30.3%, there is no plateau, and its 75% DD is barely better than TQQQ's 82%.
It is a diluted beta position with a holiday-shaped mask, not a new strategy,
and it must not be sent to holdout.

## 7. Honest assessment of the family's best cell

G8 (5 sessions, no filter): **21.21% CAGR / 42.3% DD / 0.88 Sharpe**, 17.5%
TQQQ weight, cost-robust (19.6% at 5 bp, 17.6% at 10 bp). That is a better
Calmar than TQQQ (0.50 vs 0.44) and a much better Sharpe, but it is **15.5
points short of the CAGR bar**, it is outside the 1–3 session mandate, its
neighbour at 4 sessions gives 14.9% and at 6 sessions 13.6% (no plateau), and
the shift test says the return is not holiday-specific.

If the lead wants a risk-adjusted diversifier, G8 is the only defensible
output of this study — and it is not a TQQQ beater. It should be reported as a
risk-adjusted result, not a pass.

## 8. What was ruled out

* The pre-holiday premium is not a large, stable, holiday-specific effect in
  TQQQ 2016–2023. Point estimate +0.49%/window, t = 0.52, below a random
  calendar.
* It is not a vol-regime effect: gating on trailing vol at q50/q75 is a pure
  exposure dial (q50 hard gate: 2.33% CAGR / 23.2% DD; q75 half gate: 4.23% /
  31.2%); the best Sharpe in the family is G8 at 0.88 with no gate.
* It is not an intraday-only effect either: `exit_1559` (pure session, no
  holiday gap) gives 3.47%, better than holding the gap, but still 33 points
  short.
* It is not a "few holidays" effect: grouping the slots by holiday, the three
  biggest are mixed (July 4, n=8, +2.2%; Christmas, n=8, −1.2%; Thanksgiving,
  n=8, +0.4%), and no holiday group exceeds 2.2% per window.
* It is not a data artifact: the holiday list reproduces the panel calendar
  exactly, and the result is stable to including the unscheduled 2018-12-05
  closure.

## 9. Recommendation

Do not advance this mandate. The strategy family cannot beat TQQQ, and the
mechanism it tests is too small to matter for a 3× fund. The only way a
calendar-sparse rule can clear a 36.72% CAGR bar is by holding most sessions,
at which point it is beta with extra steps.

The useful by-products for the programme:

1. **A negative result with a number.** Any future "event window" mandate
   should be checked against the exposure arithmetic in §6 before it is built:
   with `f` of sessions held, the required per-session log return is
   `ln(1+bar) / (f × 252)`. For f < 0.25 the bar is unreachable.
2. **The overnight/intraday split** (63.5% / 36.5% of log return) is a much
   larger and more robust effect than the pre-holiday premium and already has
   its own mandate (`overnight-drift-filter`).
3. **±8.8 CAGR points of sampling error** on 72 events. Event-window mandates
   with ~70 observations cannot resolve differences smaller than ~18 points at
   2σ; the grid in this study is therefore a plateau test only.

## 10. Files and reproduction

```
research/new/pre-holiday/HYPOTHESIS.md   pre-registration (grid, rules, tests)
research/new/pre-holiday/strategy.py     build_weights(ts,o,c) + main()
research/new/pre-holiday/result.json     all numbers quoted above
research/new/pre-holiday/report.md       this file
```

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
$env:BT_THREADS = "1"
python research/new/pre-holiday/strategy.py
```

Runtime ~40 s on the cached 1-minute panel. No 2024+ row is read:
`bt.panel(..., end="2023-12-29")` and the cache key includes the end date.
