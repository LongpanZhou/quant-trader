# Failed gap-up fade, repaired — report

**Slug:** `gap-fill-fade-v2`
**Window:** 2016-01-04 .. 2023-12-29 (development only; the 2024-2026 holdout
and the 10y/5y windows were not loaded).
**Execution:** `research/bt.py`, 1-minute marks, next-open fills, 2% band,
short QQQ via a synthetic session-reset inverse asset, 1 bp headline; 5 bp and
10 bp also reported.
**Direction:** **short QQQ** on event days; BIL and flat overnight otherwise.
**Primary:** `b25_50_2x` — gap +0.25%..+0.50%, weak+stressed tape, no 10:00
confirmation, short at the 09:31 open, 1.5% stop, prior-close target, 15:58
exit, **2.0x gross short QQQ** on event days via short TQQQ (0.667 weight of
the 3x inverse).
**Verdict:** **the original is retired; the repair is a conditional pass as a
small, episodic, short-only satellite.** It is not a core return engine. It
beats BIL at 1/5/10 bp, has a statistically significant event edge (t = 2.73,
p = 0.007), and is nearly uncorrelated with QQQ, but 80% of the event P&L comes
from 2018 and 2022, the band is narrow, and the 10 bp alpha is only about
+0.7%/yr over BIL.

---

## 1. Headline

| book | CAGR | max DD | Sharpe | Sortino | vol | avg short notional | time in market | fills | turnover |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **original rebuild** | **1.43%** | **0.48%** | **0.94** | 1.33 | 1.54% | 0.043% | 0.07% | 101 | 57.2x |
| original, 1x size | 1.50% | 0.74% | 0.96 | 1.37 | 1.57% | 0.070% | 0.07% | 101 | 104.2x |
| **primary `b25_50_2x`** | **3.21%** | **4.69%** | **1.09** | 1.71 | 2.95% | 0.460% | 0.69% | 145 | 104.9x |
| `b20_60_2x` (broader band) | 3.03% | 7.50% | 0.83 | 1.27 | 3.67% | 0.863% | 1.29% | 257 | 183.6x |
| `b20_60_3x` | 3.81% | 11.06% | 0.74 | 1.14 | 5.25% | 1.294% | 1.29% | 257 | 280.0x |
| `b20_60_1x` | 1.98% | 4.01% | 0.89 | 1.32 | 2.24% | 1.294% | 1.29% | 257 | 266.7x |
| `b20_60_conf_2x` (confirmation) | 1.68% | 1.46% | 1.02 | 1.47 | 1.65% | 0.023% | 0.035% | 73 | 51.0x |
| **BIL only (the honest carry bar)** | **1.39%** | **0.24%** | **0.92** | — | 1.52% | 0 | 0% | 1 | 1.0x |
| QQQ buy & hold | 18.86% | 35.11% | 0.87 | — | 22.7% | — | — | — | — |
| TQQQ buy & hold | 35.98% | 81.68% | 0.80 | — | 67.7% | — | — | — | — |
| 165-day QQQ SMA baseline | 43.62% | 59.64% | 1.01 | 1.40 | 47.2% | — | — | 59 | 265.0x |

The original's 1.43% is **BIL carry** (1.39%) plus roughly **+0.04%/yr** of
short overlay. The repair's 3.21% is BIL plus **+1.82%/yr** at 1 bp; at 10 bp it
is BIL plus **+0.70%/yr**. That is the real, but modest, improvement.

### Size and direction, stated plainly

- On the 36 event days the primary is **short 2.0x QQQ notional**. It holds
  0.667 weight of the synthetic inverse TQQQ asset (3x QQQ) and 0.333 BIL; the
  economic short is 0.667 x 3 = 2.0x.
- Across the full development window (including the flat days) the average
  short notional is **0.46% of equity**, because the strategy is in the market
  only 0.69% of minutes (about 1.7 days per year).
- The long leg is **BIL only**: 1.0x when flat, 0.333x when the 2x short is on
  (0.667 inverse TQQQ + 0.333 BIL). There is no long QQQ or TQQQ position.
- The original was short about 0.55x QQQ on its 25 event days and 0.043% of
  equity on average. The repair is roughly 3.6x larger on event days and
  holds much longer (149.8 minutes vs 21.8 minutes).

---

## 2. Diagnosis of the old rebuild

### 2.1 Counts and exposure

| item | old rebuild |
|---|---:|
| confirmed events | 25 |
| fills | 101 |
| average short notional on event days | 0.55x |
| average short notional across all minutes | 0.043% |
| time in market | 0.07% of minutes |
| average hold | 21.8 minutes |
| exits | 18 target, 6 stop, 1 time |

The old book was a 10% vol target: `clip(0.10 / 20-day vol, 0.10, 1.00)`. On
the 25 events the average size was 0.549x. The strategy was flat 99.93% of the
time, so the 1.43% CAGR is essentially the T-bill yield on BIL.

### 2.2 The event edge was not significant

The old event study: 25 events, mean **+0.056%** gross per event, t = 1.01,
bootstrap p = 0.15, 76% win rate, 95% interval including zero. Our exact
replication gives 25 events, mean +0.075% gross, sized net +0.023% per event,
t = 0.76, p = 0.22. Either way, the confirmed overlay is statistically
indistinguishable from zero.

### 2.3 The raw gap-fade is negative at the low end and positive only in a band

Short QQQ from the 09:31 open to the close, all sessions, 2016-2023, by gap
bucket and weak+stress condition:

| gap bucket | n | short return 09:31→close | t |
|---|---:|---:|---:|
| +0.10-0.25% | 17 | -0.00% | -0.03 |
| +0.20-0.45% | 43 | +0.13% | 1.89 |
| +0.25-0.50% | 38 | +0.18% | 2.42 |
| +0.30-0.55% | 37 | +0.11% | 1.24 |
| +0.35-0.60% | 39 | +0.13% | 1.17 |
| +0.20-0.60% | 66 | +0.09% | 1.26 |
| +0.10-0.75% | 95 | +0.05% | 0.68 |

The original band's low end is negative. The positive region is about
**0.20-0.50%**, with the peak at 0.25-0.50%. The old 10:00 confirmation is a
late, adverse-selection filter: it keeps the events where the first 30 minutes
have already moved, leaving the smallest remaining gap. The confirmation
version has 18 events and a 50% win rate; dropping it gives 36 events and an
80.6% win rate in the primary band.

---

## 3. What the repair changed

1. **No 10:00 confirmation.** Enter at the 09:31 open, one minute after the
   gap is known. The gap, the 10-day SMA, the 5-day return, the 20-day vol and
   the 1-year median vol are all known before the open. No future information.
2. **Stricter gap band.** +0.25% to +0.50% for the primary (the 0.20-0.45 and
  0.20-0.60 neighbours are in the plateau table). The old +0.10-0.75% band is
   diluted by a negative low bucket and a weak high bucket.
3. **Fixed 2x short instead of a 10% vol target.** The old sizing left the
   short at ~0.55x on event days and ~0.04% of equity on average. The repair
   holds 2.0x gross short QQQ on event days.
4. **Hold to 15:58 instead of 11:30.** The fade continues after 11:30; the old
   time stop cut it off. The repair's average hold is 149.8 minutes, and it is
   flat overnight.
5. **Keep the target and the stop.** Target the prior close (full gap fill);
   stop at +1.5% on QQQ (a 4.5% loss on the 3x inverse, about -3.0% of equity
   at the 0.667 weight). One short at a time.

The repair does not change the mechanism: it is still a short of a small
gap-up in a weak, stressed tape, targeting the prior close. It changes the
timing, the band and the size.

---

## 4. Primary event study and attribution

Primary `b25_50_2x`, 36 events:

| statistic | value |
|---|---:|
| events | 36 |
| gross per unit of inverse TQQQ (3x QQQ) | +0.643% |
| gross per 1x QQQ equivalent | +0.214% |
| sized net per event (2x sleeve, 1 bp) | +0.416% |
| median gross | +1.156% |
| win rate | 80.6% |
| t-stat | 2.73 |
| bootstrap p (mean ≤ 0) | 0.0069 |
| bootstrap 95% CI | +0.098% .. +0.689% |
| average hold | 149.8 minutes |
| exits | 27 target, 8 time, 1 stop |
| average size | 0.667 (2.0x gross QQQ) |

The one stop was 2020-10-29, gross -4.48% on the 3x inverse (QQQ +1.49%),
sized -2.99% of equity.

### Event P&L by year (arithmetic sum of sized gross returns, percentage points)

| year | events | sized P&L | win rate |
|---|---:|---:|---:|
| 2016 | 1 | -0.78 | 0% |
| 2017 | 10 | +0.28 | 60% |
| 2018 | 10 | **+8.02** | 90% |
| 2019 | 2 | +1.56 | 100% |
| 2020 | 7 | +1.57 | 86% |
| 2021 | 1 | +0.46 | 100% |
| 2022 | 5 | **+4.33** | 100% |
| 2023 | 0 | 0.00 | — |
| **total** | **36** | **+15.45** | 80.6% |

**2018 and 2022 contribute 80% of the event P&L.** This is a crisis-alpha
sleeve: the stress filter selects the high-volatility, weak-tape regimes, and
those are exactly the years when the short pays. It is not a steady
year-in, year-out return stream.

### Yearly strategy returns (including BIL carry)

| year | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| primary | -0.7% | +0.6% | +9.8% | +3.6% | +1.7% | +0.3% | +5.7% | +5.0% |

2023 has **no events**; its +5.0% is the BIL/T-bill yield, not event alpha. The
strategy's positive years are BIL plus episodic event P&L.

| sub-period | primary CAGR | total return |
|---|---:|---:|
| 2016-2019 | +3.27% | +13.67% |
| 2020-2021 | +1.02% | +2.06% |
| 2022-2023 | +5.35% | +10.95% |

All three sub-periods are positive, but the 2020-21 sub-period is essentially
BIL (1.02% vs 1.39% BIL CAGR) and the 2016-19/2022-23 periods are carried by
2018 and 2022.

### Correlation

Daily-return correlation: **-0.058 to QQQ, -0.058 to TQQQ, -0.055 to the
165-day baseline.** The near-zero/negative correlation is the main portfolio
argument for the sleeve: it pays in stressed tapes when a long TQQQ book is
hurting.

---

## 5. Cost ladder

Primary `b25_50_2x`:

| cost | CAGR | max DD | Sharpe | Sortino | vol | turnover |
|---|---:|---:|---:|---:|---:|---:|
| **1 bp** | **3.21%** | **4.69%** | **1.09** | 1.71 | 2.95% | 104.9x |
| 5 bp | 2.71% | 4.85% | 0.93 | 1.44 | 2.95% | 102.8x |
| 10 bp | 2.09% | 5.10% | 0.72 | 1.10 | 2.96% | 100.3x |

The BIL-only bar is 1.39% CAGR / 0.24% DD. The primary clears it at all three
cost levels, but the 10 bp excess is only **+0.70%/yr**. The original clears
BIL at 1 bp by +0.04%/yr and is below BIL at 10 bp (0.79% vs 1.39%).

---

## 6. Grid and plateau

### 6.1 Pre-registered grid (1 bp)

| variant | gap band | confirmation | entry | size / asset | signals | events | CAGR | max DD | Sharpe | 5 bp CAGR | 10 bp CAGR |
|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| `orig` | 0.10-0.75% | yes | 10:01 | 10% vol / QQQ inv | 25 | 25 | 1.43% | 0.48% | 0.94 | 1.15% | 0.79% |
| `orig_size1` | 0.10-0.75% | yes | 10:01 | 1.0x / QQQ inv | 25 | 25 | 1.50% | 0.74% | 0.96 | 0.99% | 0.35% |
| `all_nc_1x` | 0.10-0.75% | no | 09:31 | 1.0x / QQQ inv | 95 | 92 | 1.73% | 6.54% | 0.67 | -0.13% | -2.42% |
| `b20_60_1x` | 0.20-0.60% | no | 09:31 | 1.0x / QQQ inv | 66 | 64 | 1.98% | 4.01% | 0.89 | 0.68% | -0.93% |
| `b20_60_2x` | 0.20-0.60% | no | 09:31 | 2.0x / TQQQ inv | 66 | 64 | 3.03% | 7.50% | 0.83 | 2.15% | 1.05% |
| `b20_60_3x` | 0.20-0.60% | no | 09:31 | 3.0x / TQQQ inv | 66 | 64 | 3.81% | 11.06% | 0.74 | 2.48% | 0.85% |
| **`b25_50_2x`** | **0.25-0.50%** | **no** | **09:31** | **2.0x / TQQQ inv** | **38** | **36** | **3.21%** | **4.69%** | **1.09** | **2.71%** | **2.09%** |
| `b20_60_conf_2x` | 0.20-0.60% | yes | 10:01 | 2.0x / TQQQ inv | 18 | 18 | 1.68% | 1.46% | 1.02 | 1.43% | 1.12% |

### 6.2 Gap-band plateau (2x short, 09:31, no confirmation)

| gap band | events | CAGR | max DD | Sharpe | 10 bp CAGR | 10 bp Sharpe | event gross (3x) | t |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.20-0.45% | 41 | 3.02% | 4.77% | 1.01 | 1.74% | 0.59 | +0.515% | 2.28 |
| **0.25-0.50%** | **36** | **3.21%** | **4.69%** | **1.09** | **2.09%** | **0.72** | **+0.643%** | **2.73** |
| 0.30-0.55% | 36 | 2.50% | 6.78% | 0.83 | 1.38% | 0.47 | +0.415% | 1.42 |
| 0.35-0.60% | 39 | 2.46% | 7.50% | 0.80 | 1.25% | 0.42 | +0.377% | 1.12 |
| 0.20-0.60% | 64 | 3.03% | 7.50% | 0.83 | 1.05% | 0.30 | +0.355% | 1.48 |
| 0.10-0.75% | 92 | 2.73% | 12.15% | 0.62 | -0.08% | 0.00 | +0.225% | 1.04 |

The plateau is positive across 0.20-0.60% at 1 bp, but the **cost-robust**
region is 0.20-0.50%: the 0.20-0.45 and 0.25-0.50 bands clear the 1.39% BIL
bar at 10 bp; the 0.30-0.55 and wider bands do not. The 0.25-0.50% primary is
the in-sample peak, not a lone cell: its immediate lower neighbour (0.20-0.45%)
has a similar 10 bp result. Still, the band was chosen after the diagnosis,
so it carries selection risk.

---

## 7. Verdict

**Original: retired.** The 1.43% headline was BIL carry; the confirmed short
overlay added about +0.04%/yr and had a t-stat of 0.76-1.01. It is a rounding
error, exactly as the brief said.

**Repair: conditional pass as a small, episodic, short-only satellite.**

What is honest about it:

- It keeps the mechanism (fade a small gap-up in a weak, stressed tape) and
  fixes the two measured problems: the late 10:00 confirmation and the 10% vol
  target.
- The event edge is statistically significant: 36 events, 80.6% win, t = 2.73,
  bootstrap p = 0.0069, 95% CI entirely above zero.
- It beats the honest BIL bar at 1/5/10 bp: 3.21%/2.71%/2.09% vs 1.39%.
- It is nearly uncorrelated with QQQ/TQQQ and with the 165-day base, so it is
  a genuine diversifier rather than a repackaged long.
- The 0.20-0.45% neighbour has a similar 10 bp result, so the edge is a band,
  not a single point.

What is not honest to overstate:

- It is **small**: 3.21% CAGR, 4.69% DD, and only +1.82%/yr over BIL at 1 bp;
  +0.70%/yr at 10 bp. It is a satellite, not a core return engine.
- It is **episodic**: 2018 and 2022 contribute 80% of the event P&L; 2023 has
  no events at all and its +5.0% is BIL yield. The effective sample is two
  stress episodes, not eight independent years.
- It is **short-only and tail-risky**: a gap-up that continues squeezes the
  short; the 1.5% QQQ stop caps the loss at about -3% of equity on the 2x
  sleeve, but the fill can be worse.
- The **2x implementation** uses short TQQQ (3x inverse) at 0.667 weight. The
  intraday equivalence to 2x QQQ is exact within a session, and the strategy is
  flat overnight, but TQQQ borrow/tracking and the 3x daily reset are real
  implementation risks. The result should be re-checked with actual TQQQ
  borrow costs and fills.
- The **0.25-0.50% band** was selected after inspecting the dev data. The
  0.20-0.45% neighbour supports it, but an independent holdout is required
  before promotion. The broader 0.20-0.60% band fails the 10 bp BIL bar
  (1.05% vs 1.39%), which is the main reason not to call this a robust
  standalone.

**Recommendation:** keep as a research candidate / small satellite, capped at
2x gross short and sized so its 5% drawdown is acceptable to the book. Do not
promote to the core. Run the frozen version on the 2024-2026 holdout once,
after the independent audit, and retire it if the event mean or the 10 bp
excess over BIL is not positive.

---

## 8. Reproduction and caveats

```
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
python research/new/gap-fill-fade-v2/strategy.py
```

- Development only; `bt.panel` is called with `end=2023-12-29`. The 2024-2026
  panel is never sliced.
- 1-minute marks, next-open fills, 2% band. The short is a synthetic,
  session-reset inverse asset; the 2x variants hold 0.667 of the inverse TQQQ
  asset (3x QQQ), which is 2.0x gross short QQQ.
- Borrow is 0.5%/yr, prorated per minute. A 5%/yr borrow sensitivity changes
  the total return by less than 0.3 percentage points over the eight years
  because the holding period is intraday.
- The 09:31 entry uses only information known at the 09:30 open/close: the
  gap, the prior 10-day SMA, the prior 5-day return, and the prior 20-day and
  1-year volatility. The 10:00-confirmed variants use the 10:00 close and fill
  at 10:01.
- The target is the prior close; the stop is +1.5% on QQQ (or the opening-range
  high for the old/confirmation variants, floored at +0.2% and capped at
  +1.5%). Stop wins if both stop and target are touched in the same bar. The
  time exit is 15:58, filled at the 15:59 open, so the position is flat
  overnight.
- The 165-day baseline is a benchmark/correlation reference only; no old base
  weights are used by the signal.
- The weak-tape and stress definitions (10-day SMA, 5-day return, 20-day vol
  vs 1-year median) are the original rebuild's; they are not re-optimised
  here. The gap band, entry time, size and time stop are the repair.
