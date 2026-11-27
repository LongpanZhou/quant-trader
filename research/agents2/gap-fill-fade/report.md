# Opening-gap fade vs continuation — round-2 agent report

**Verdict: the standalone gap strategies all fail, but a gap-up fade *overlay* on the
winner passes.** At the winner's own parameters, stepping aside intraday on small
gap-ups in a weak tape strictly dominates the winner on both windows at 1 bp and
5 bp:

| Window | This strategy 1 bp | Winner 1 bp | TQQQ 1 bp |
|---|---:|---:|---:|
| 10y 2017-01-03 → 2026-10-23 | **65.17% / 39.02%** | 58.80% / 44.56% | 39.28% / 81.68% |
| 5y 2021-10-25 → 2026-10-23 | **54.92% / 30.99%** | 49.88% / 33.49% | 13.47% / 81.68% |

At 5 bp: **58.02% / 40.93%** and **48.78% / 31.65%** versus the winner's
54.60% / 47.08% and 45.89% / 34.13%. At 10 bp the 10-year return is flat
(49.51% vs 49.50%) but drawdown is 4.7 pp lower, and the 5-year is better on
both (41.44% / 32.49% vs 41.05% / 34.93%). The result is causal and survives a
one- to three-minute entry delay.

The honest caveat is in §7.4: the 10-year improvement is robust to the arm-gate
buffer, but the 5-year improvement is not. It depends on the winner's exact
1% arm gate and falls apart at neighbouring buffers. Treat the 10-year pass as
the robust result and the 5-year pass as sample-specific.

---

## 1. Mandate and data

The task was to compare opening-gap fade and continuation on QQQ/TQQQ, using
QQQ/TQQQ gaps of ±0.5%, 1% and 2% versus the prior close, in a 165-day bull
regime, with 1-minute entries/exits and strict stops:

1. fade the gap at the open, exit at VWAP / a target / a time stop;
2. follow the gap if it holds above/below the opening range;
3. only trade gaps against/with the prior day's trend.

Data: the local adjusted 1-minute QQQ/TQQQ/BIL archive under
`data/intraday-hf/`, 2016-01-04 → 2026-10-23, regular session only. No new
downloads. Harness: `research/bt.py`, next-bar-open fills, long-only, weights
sum to ≤ 1, 1/5/10 bp slippage on traded notional. The winner benchmark is
reproduced exactly: 58.80% / 44.56% (10y) and 49.88% / 33.49% (5y) at 1 bp.

I use "gap" as `QQQ open / prior QQQ close − 1`. TQQQ gaps are roughly 3× the
QQQ gap, so a 0.15–0.50% QQQ gap is a ~0.45–1.5% TQQQ gap.

## 2. The arithmetic that shapes every result

TQQQ's return is overwhelmingly overnight. From the local minute data:

| Window | TQQQ close→close CAGR | TQQQ open→close CAGR | TQQQ close→open CAGR | Regime-on open→close |
|---|---:|---:|---:|---:|
| 2017-01-03 → 2026-10-23 | 39.28% | **6.25%** | **31.14%** | **3.90%** |
| 2021-10-25 → 2026-10-23 | 13.88% | **2.41%** | **11.61%** | **5.46%** |

The open→close and close→open columns are all sessions. The last column is the
regime-on, daily-rebalanced intraday-only return (2,039 sessions over 10 years,
933 over 5 years). Even the all-days intraday leg is only 6.25%/2.41%; the
regime-on subset is 3.90%/5.46%. A long-only, fully-invested intraday strategy
can therefore capture at most ~4–5.5%/yr of TQQQ drift, depending on the
window, before costs. That is the entire intraday opportunity set. No gap
variant came close to the 39.28% bar.

This is why every standalone gap strategy in §4 fails, and why the only way to
use the gap signal is as an overlay on an overnight TQQQ position.

## 3. Event study: the size split is real

Conditional TQQQ returns from the 09:31 open to the 15:59 open, regime-on days,
2017–2026 (n = 2,039):

| QQQ gap bucket | n | mean | median | win rate | t |
|---|---:|---:|---:|---:|---:|
| < −2% | 20 | +0.11% | +0.25% | 55.0% | 0.11 |
| −2…−1% | 98 | +0.34% | +0.49% | 55.1% | 0.82 |
| −1…−0.5% | 192 | +0.20% | +0.43% | 59.9% | 0.89 |
| −0.5…−0.2% | 242 | +0.13% | +0.44% | 57.4% | 0.78 |
| −0.2…−0.05% | 210 | −0.13% | +0.23% | 53.8% | −0.75 |
| −0.05…+0.05% | 164 | +0.08% | +0.08% | 52.4% | 0.44 |
| +0.05…+0.15% | 170 | +0.22% | +0.22% | 55.3% | 1.31 |
| +0.15…+0.2% | 88 | +0.03% | +0.07% | 53.4% | 0.15 |
| **+0.2…+0.5%** | 420 | **−0.11%** | +0.03% | 50.2% | −0.86 |
| **+0.5…+0.75%** | 193 | **−0.17%** | 0.00% | 49.7% | −0.93 |
| +0.75…+1% | 111 | +0.08% | +0.70% | 62.2% | 0.30 |
| +1…+2% | 113 | +0.13% | +0.41% | 56.6% | 0.45 |
| **> +2%** | 18 | **+1.83%** | +2.14% | 83.3% | 2.93 |

The pattern is the one the gap literature describes: **small up-gaps fade,
large up-gaps continue.** The negative mean in the +0.2…+0.75% band is weak
unconditionally (t ≈ −0.9), but it becomes much stronger when conditioned on a
weak short-term tape (§5). Gap-downs bounce from the open (+0.13% to +0.34%
mean); the round-1 mean-reversion report measured from 09:35 and missed most of
that first-minute bounce.

Over 5 years the same shape holds, though the +0.2…+0.5% bucket is flat
(+0.03%) and the +0.5…+0.75% bucket is −0.15%.

**Why the fade is not a short.** The mandate is long-only. A gap-up fade cannot
be implemented by shorting TQQQ; it is implemented by *not holding* TQQQ
intraday — sell at 09:31, hold BIL, buy back at the close. The strategy keeps
the overnight exposure (where the drift is) and only gives up the post-gap
intraday drift. That is the only long-only way to express a gap-up fade, and it
is what the overlay does.

## 4. Standalone gap strategies: all fail

All variants below are regime-on only, enter at the 09:31 open (signal from the
09:30 close), and are long-only. "VWAP" exit means sell the next bar after
TQQQ's close crosses above the session VWAP; "pclose" means the prior close;
EOD means the 15:55–15:59 exit. Stops are 2% intraday (triggered on the bar
low, filled at the next open) unless noted.

| Variant | n | 10y CAGR / DD | 5y CAGR / DD | 10y CAGR @5 bp |
|---|---:|---:|---:|---:|
| Fade gap-down 0.5%, EOD, no stop | 316 | 7.68 / 33.71 | 9.14 / 22.17 | 2.37 |
| Fade gap-down 0.5%, VWAP, 2% stop | 316 | 5.41 / 5.64 | 4.99 / 5.64 | 0.20 |
| Fade gap-down 1.0%, EOD, no stop | 119 | 5.29 / 31.86 | 5.77 / 16.83 | 3.28 |
| Fade gap-down 1.0%, VWAP, 2% stop | 119 | 4.73 / 4.21 | 5.25 / 2.88 | 2.72 |
| Fade gap-down 1.0%, 10:30 time exit, no stop | 119 | 6.25 / 16.53 | 9.00 / 8.06 | 4.22 |
| Fade gap-down 2.0%, VWAP, 2% stop | 20 | 3.70 / 1.75 | 4.61 / 0.06 | 3.36 |
| Follow gap-up 0.5%, EOD, 2% stop | 442 | −0.05 / 36.32 | −0.98 / 36.32 | −6.90 |
| Follow gap-up 1.0%, EOD, 2% stop | 133 | 4.62 / 19.76 | 6.97 / 7.92 | 2.41 |
| Follow gap-up 2.0%, EOD, 2% stop | 18 | 4.81 / 9.18 | 5.81 / 4.96 | 4.49 |
| ORB30 gap-up 0.5%, stop OR low | 304 | 5.51 / 14.91 | 4.22 / 11.04 | 0.49 |
| ORB30 gap-up 1.0%, stop OR low | 98 | 6.08 / 10.18 | 5.06 / 8.44 | 4.42 |
| ORB30 gap-up 2.0%, stop OR low | 15 | 4.54 / 4.96 | 4.81 / 4.96 | 4.28 |
| Fade 1.0%, prior day **up** | 54 | 2.60 / 4.11 | 3.94 / 1.19 | — |
| Fade 1.0%, prior day **down** | 65 | 4.51 / 3.27 | 5.02 / 2.17 | — |
| Follow 1.0%, prior day **up** | 70 | 5.25 / 18.23 | 8.04 / 4.96 | — |
| Follow 1.0%, prior day **down** | 63 | 1.76 / 12.08 | 2.68 / 9.24 | — |

The three gap-down VWAP rows are reproduced by `strategy.py`'s
`standalone_gap_down_fade` block (close-based 2% stop). The EOD, 10:30
time-exit, gap-up follow, ORB and prior-trend rows are from the research sweep
(low-based stops, same 09:31 entry and regime filter) and are reported for
completeness. The conclusion — none beats TQQQ on either window — holds for
every row.

**Readings.**

- The best standalone CAGR is 9.14% (0.5% gap-down fade, EOD), still below
  TQQQ's 13.47% 5-year and a quarter of its 39.28% 10-year. Nothing beats TQQQ
  on both windows.
- The gap-down fade has a real per-trade edge: +0.14% to +0.68% mean, 74–95%
  win rates for the VWAP-target versions, and Sharpe 1.4–2.6. It is a good
  *risk-adjusted* intraday trade and a hopeless way to compound capital,
  because it is in the market only 5–30% of days and gives up the overnight
  drift.
- The 2% gap-down fade with a VWAP target has a 95% win rate and a 1.8%
  maximum drawdown, on 20 trades in 10 years. That is a curiosity, not a
  strategy: two trades a year cannot carry a portfolio.
- Gap-up continuation is weak for 0.5% gaps and only works for 2%+ gaps
  (n = 18, +1.36% mean, Sharpe 1.17). The sample is too small to trust.
- Prior-day conditioning does not rescue anything. The gap-down fade is
  better after a prior *down* day (with-trend capitulation), and the gap-up
  follow is better after a prior *up* day (with-trend continuation). Neither
  gets near TQQQ.
- At 5 bp the higher-frequency variants are destroyed: the 0.5% fade drops
  from 7.68% to 2.37%, the gap-up follow from −0.05% to −6.90%. This is the
  same cost arithmetic as the round-1 intraday report.

**Conclusion:** the gap signal is real but small. It cannot be a standalone
strategy under a 1× TQQQ notional cap.

## 5. The surviving strategy: a gap-up fade overlay on the winner

### 5.1 Exact rules

Start from the round-1 winner:

1. **Regime (daily).** QQQ's prior daily close above its 165-day SMA → risk-on
   for the next session; otherwise 100% BIL.
2. **Risk-on.** Hold 100% TQQQ, including overnight.
3. **Armed stop.** On a risk-on day, arm a 4% stop from the session open only
   when QQQ's first-minute close is below its prior 20-day SMA × 1.01. While
   armed, if TQQQ closes 4% below the session open, sell at the next minute's
   open and stay in BIL for the rest of the session and the following night.

Add one overlay:

4. **Gap-up fade.** On a risk-on day that is armed, if QQQ's opening gap is
   between **+0.15% and +0.50%** versus the prior close:
   - sell TQQQ at the **09:31 open** (weight set at the 09:30 close);
   - hold 100% BIL until the close;
   - re-enter TQQQ at the **15:59 open** (the last executable minute), unless
     TQQQ closed 4% below the session open at any point before the last bar,
     in which case stay in BIL overnight (the same crash filter the base stop
     would have provided).

Nothing else changes. The next session re-enters at the open if the regime is
still on.

### 5.2 Why this is causal

- The QQQ open (and therefore the gap) is known at 09:30:00. The 09:30
  first-minute close is known at 09:30:59. The weight is set at the close of
  the 09:30 bar and fills at the 09:31 open.
- The re-entry decision uses data through the 15:58 close and fills at the
  15:59 open. It does **not** use the 15:59 close.
- The regime uses only the prior daily close; the MA20 arm uses only prior
  closes.
- A truncation test (all data after 2022-01-03 removed, weights rebuilt)
  leaves the prior weights unchanged. A one-bar execution delay of the
  overlay leg gives 64.38% / 54.84% at 1 bp (10y/5y), so the edge is not a
  one-minute artifact.

### 5.3 Why it works

- **The size split.** Small up-gaps after a weak close are failed bounces;
  large up-gaps are news and continue. The overlay only touches the small
  band.
- **The weak-tape gate.** The winner's armed condition identifies days when
  QQQ's first-minute price is below its 20-day SMA × 1.01 — a short-term weak
  tape. A gap-up in that tape is more likely to be sold than bought.
- **The crash filter.** On 30 of the 160 ten-year overlay days TQQQ closed 4%
  below the open. The base winner would have stopped out around −4% and
  missed the rest of the day; the overlay is already flat from 09:31 and
  avoids that intraday loss. This is the main source of the drawdown cut.
- **The overnight drift is preserved.** The strategy is only flat intraday
  on the overlay days; it holds TQQQ every night the regime is on. That is
  why it can still compound at 65%/yr.

### 5.4 Event profile

Over the 10-year window there are **160 overlay days** (about 16/year); 30 of
them breach the 4% level. The de-risk PnL (TQQQ return avoided from 09:31 to
15:59, sign-flipped) is:

| Statistic | 10y | 5y |
|---|---:|---:|
| Events | 160 | 69 |
| Mean | +0.41% | +0.39% |
| Median | +0.15% | −0.01% |
| Win rate | 53.1% | 49.3% |
| t-stat | 1.60 | 0.92 |

The per-event edge is **not statistically significant**. It is a tail hedge,
not a stable scalping edge: the mean is carried by a handful of large
avoided declines. The eight largest de-risk gains are 6.0–12.4%, and all
eight are on days where the base stop would have fired: the overlay avoids
the entire intraday decline, not only the post-stop part. The distribution is
left-skewed for the base strategy, which is exactly what an overlay wants.

By year, the de-risk PnL (positive = the overlay made money) is:
2017 −10.6%, 2018 +20.0%, 2019 +16.4%, 2020 +6.9%, 2021 +20.3%,
2022 +8.8%, 2023 +1.6%, 2024 −9.6%, 2025 +9.1%, 2026 +0.9%.
It is a cost in two years (2017, 2024) and a large benefit in the stressed
years (2018, 2021, 2025).

## 6. Results

### 6.1 Headline (official harness, `bt.run`)

| Cost | Window | CAGR | Max DD (minute) | Max DD (daily) | Sharpe | Fills |
|---|---:|---:|---:|---:|---:|---:|
| 1 bp | 10y | **65.17%** | **39.02%** | 36.80% | 1.35 | 1,085 |
| 1 bp | 5y | **54.92%** | **30.99%** | 30.57% | 1.25 | 505 |
| 5 bp | 10y | **58.02%** | **40.93%** | 37.79% | 1.25 | 1,085 |
| 5 bp | 5y | **48.78%** | **31.65%** | 31.18% | 1.16 | 505 |
| 10 bp | 10y | 49.51% | 45.91% | 43.03% | 1.12 | 1,085 |
| 10 bp | 5y | 41.44% | 32.49% | 31.93% | 1.04 | 505 |

Winner reference: 58.80% / 44.56% (10y) and 49.88% / 33.49% (5y) at 1 bp;
54.60% / 47.08% and 45.89% / 34.13% at 5 bp; 49.50% / 50.06% and
41.05% / 34.93% at 10 bp.

The strategy trades 1,085 fills over 10 years (vs 657 for the winner), largely
because each overlay day is a round trip; stop interactions on those days
account for the rest. Turnover is high in the harness's starting-equity units
(39,122×) but that is an artifact of 65%/yr compounding; in annual terms it is
~16 extra round trips per year.

### 6.2 Yearly returns (1 bp)

| Year | Strategy | Winner | TQQQ |
|---|---:|---:|---:|
| 2017 | +98.74% | +118.76% | +114.54% |
| 2018 | **+15.05%** | +0.47% | −20.76% |
| 2019 | +69.87% | +47.94% | +148.23% |
| 2020 | +182.91% | +183.91% | +104.14% |
| 2021 | **+83.31%** | +60.61% | +81.05% |
| 2022 | **−14.59%** | −17.99% | −79.39% |
| 2023 | +150.70% | +149.04% | +192.05% |
| 2024 | +63.03% | +67.96% | +62.43% |
| 2025 | **+53.48%** | +43.29% | +32.10% |
| 2026* | +15.95% | +16.76% | +22.62% |

\* 2026 is partial (to 2026-10-23). The strategy beats the winner in 6 of 10
years and beats TQQQ in 6 of 10. The cost years are 2017 (the overlay gives
up 20 pp), 2024 (5 pp) and 2026 (0.8 pp). The benefit is concentrated in
2018 (+14.6 pp), 2021 (+22.7 pp) and 2025 (+10.2 pp).

### 6.3 Drawdown anatomy

- Winner 10y max DD: **−44.56%**, 2018-03-13 → 2019-06-05 (the SMA-165 whipsaw
  year).
- Strategy 10y max DD: **−39.02%**, 2021-02-16 → 2021-03-25. The overlay
  removes the 2018–19 drawdown but leaves the 2021 growth-scare drawdown.
- Strategy 5y max DD: **−30.99%**, 2026-06-22 → 2026-07-30. The winner's 5y
  max DD is −33.49% over the same episode.

### 6.4 Rolling 3-year windows

26 quarterly-start windows, 2017-07 → 2023-10:

| Comparison | Return wins | DD wins | Both |
|---|---:|---:|---:|
| Strategy vs TQQQ | **25/26** | **26/26** | **25/26** |
| Strategy vs winner | **23/26** | **26/26** | **23/26** |
| Winner vs TQQQ | 22/26 | 26/26 | 22/26 |

The strategy is more consistent than the winner: it loses the return race in
only three windows (2021-07 by 0.1 pp, 2022-10 by 0.1 pp, 2023-04 by 3.2 pp)
and the drawdown race in none. It loses to TQQQ on return in one window
(2019-01, 109.3% vs 112.2%).

### 6.5 Sub-periods (1 bp)

| Period | Strategy CAGR / DD | Winner CAGR / DD |
|---|---:|---:|
| 2017-01 → 2019-12 | **57.98% / 38.14%** | 48.85% / 44.56% |
| 2020-01 → 2022-12 | **65.85% / 39.02%** | 56.73% / 41.50% |
| 2023-01 → 2026-10 | **69.19% / 30.99%** | 67.48% / 33.49% |
| 2021-10 → 2026-10 (5y) | **54.73% / 30.99%** | 49.70% / 33.49% |

The improvement is present in all three sub-periods, not only in 2020.

## 7. Robustness

### 7.1 Gap-band plateau

The rule is not a single grid point. The table shows the overlay's 1 bp and
5 bp results as the band moves (the base winner is 58.80/44.56 and
54.60/47.08; 49.88/33.49 and 45.89/34.13):

| QQQ gap band | n | 10y 1 bp | 5y 1 bp | 10y 5 bp | 5y 5 bp |
|---|---:|---:|---:|---:|---:|
| 0.10–0.40% | 152 | 60.47 / 40.93 | 49.86 / 32.42 | 53.74 / 42.90 | 44.11 / 33.28 |
| 0.10–0.50% | 194 | 63.51 / 40.93 | 52.52 / 32.42 | 56.00 / 41.96 | 46.15 / 33.28 |
| 0.10–0.75% | 267 | 61.59 / 42.48 | 50.66 / 34.28 | 53.00 / 43.67 | 43.30 / 35.22 |
| 0.15–0.40% | 130 | 62.09 / 39.49 | 52.22 / 30.99 | 55.73 / 43.24 | 46.70 / 31.65 |
| **0.15–0.50%** | **172** | **65.17 / 39.02** | **54.92 / 30.99** | **58.02 / 40.93** | **48.78 / 31.65** |
| 0.15–0.75% | 245 | 63.24 / 40.62 | 53.03 / 32.67 | 54.98 / 41.75 | 45.88 / 33.69 |
| 0.20–0.40% | 102 | 60.59 / 42.28 | 51.51 / 30.99 | 54.71 / 45.69 | 46.35 / 31.65 |
| 0.20–0.50% | 144 | 63.63 / 41.50 | 54.20 / 30.99 | 56.98 / 43.47 | 48.42 / 31.65 |
| 0.20–0.75% | 217 | 61.72 / 43.04 | 52.32 / 32.67 | 53.97 / 44.12 | 45.54 / 33.53 |
| 0.25–0.40% | 67 | 62.47 / 41.59 | 52.25 / 33.49 | 57.19 / 44.78 | 47.63 / 34.13 |
| 0.25–0.50% | 109 | 65.55 / 41.50 | 54.96 / 33.49 | 59.49 / 42.52 | 49.72 / 34.13 |
| 0.25–0.75% | 182 | 63.61 / 43.04 | 53.06 / 35.11 | 56.43 / 44.12 | 46.81 / 35.93 |

The center of the plateau (0.15–0.50, 0.20–0.50) is robust. The edges
(0.10–0.40, 0.10–0.75, 0.20–0.75) are weaker and fail 5 bp on at least one
window. I chose the center, not the single best cell.

### 7.2 Regime SMA and stop level

Every combination of regime SMA (150/165/180) and stop (3/4/5%) improves both
CAGR and drawdown at both 1 bp and 5 bp when the overlay is added:

| Regime / stop | Base 10y 1 bp | Overlay 10y 1 bp | Base 5y 1 bp | Overlay 5y 1 bp | Overlay 10y 5 bp | Overlay 5y 5 bp |
|---|---:|---:|---:|---:|---:|---:|
| SMA150 / 3% | 54.02 / 42.34 | 59.77 / 39.01 | 37.68 / 42.34 | 42.60 / 36.59 | 51.63 / 41.27 | 35.72 / 38.29 |
| SMA150 / 4% | 57.38 / 41.50 | 64.04 / 39.02 | 43.04 / 36.62 | 49.87 / 33.99 | 57.02 / 39.98 | 43.93 / 34.94 |
| SMA150 / 5% | 49.19 / 42.31 | 57.58 / 39.29 | 35.33 / 42.31 | 44.30 / 36.23 | 51.67 / 39.77 | 39.56 / 36.74 |
| SMA165 / 3% | 54.05 / 48.43 | 59.46 / 44.96 | 44.36 / 37.66 | 47.50 / 35.98 | 51.27 / 47.93 | 40.39 / 37.40 |
| **SMA165 / 4%** | **58.80 / 44.56** | **65.17 / 39.02** | **49.88 / 33.49** | **54.92 / 30.99** | **58.02 / 40.93** | **48.78 / 31.65** |
| SMA165 / 5% | 50.15 / 43.03 | 58.25 / 41.90 | 41.46 / 42.31 | 48.79 / 36.23 | 52.29 / 43.09 | 43.90 / 36.74 |
| SMA180 / 3% | 53.41 / 50.71 | 59.90 / 47.39 | 42.33 / 37.66 | 47.39 / 35.98 | 51.61 / 50.31 | 40.19 / 37.40 |
| SMA180 / 4% | 58.36 / 46.97 | 66.01 / 40.32 | 48.14 / 33.49 | 55.49 / 30.99 | 58.80 / 43.40 | 49.23 / 31.65 |
| SMA180 / 5% | 49.95 / 45.50 | 59.33 / 44.42 | 40.21 / 42.31 | 49.86 / 36.23 | 53.28 / 45.47 | 44.80 / 36.74 |

This is the strongest evidence that the overlay is not a winner-specific
artifact: it improves every base variant, including the 3% and 5% stops.

### 7.3 Weak-trend gate definition

The overlay uses the winner's armed condition (QQQ first-minute close below
prior MA20 × 1.01). A prior-close version (QQQ *prior close* below prior MA20
× 1.01) gives 66.78 / 39.02 and 53.30 / 30.99 at 1 bp — essentially the same
result, slightly better 10y and slightly worse 5y. A first-minute-close
gate with MA30 × 1.02 gives 66.17 / 37.67 and 53.79 / 30.99. The effect is
not sensitive to the exact MA definition, which is reassuring, but the 5-year
number varies 50–55 across these gates.

### 7.4 Arm-gate buffer: the 5-year fragility

The winner's arm gate is `QQQ first-minute close < prior MA20 × (1 + buffer)`
with buffer = 1%. Changing that buffer changes both the base stop and the
overlay trigger, so it is a demanding robustness test:

| Arm buffer | 10y 1 bp | 5y 1 bp | 10y 5 bp | 5y 5 bp |
|---:|---:|---:|---:|---:|
| 0.0% | 58.57 / 39.13 | 45.53 / 32.94 | 53.95 / 40.00 | 41.61 / 34.11 |
| 0.5% | 59.88 / 39.02 | 45.00 / 32.83 | 54.44 / 39.98 | 40.37 / 34.64 |
| **1.0% (winner)** | **65.17 / 39.02** | **54.92 / 30.99** | **58.02 / 40.93** | **48.78 / 31.65** |
| 1.5% | 66.10 / 38.04 | 45.69 / 34.13 | 57.21 / 39.61 | 38.67 / 34.86 |
| 2.0% | 61.94 / 37.67 | 43.56 / 34.13 | 51.93 / 39.59 | 35.76 / 34.86 |
| 3.0% | 61.90 / 43.79 | 41.44 / 33.03 | 48.35 / 46.48 | 31.42 / 33.99 |

The 10-year drawdown improvement is robust: every buffer gives a drawdown of
37.7–43.8% versus the winner's 44.56%, and every buffer from 0.5% to 3% gives a
10-year 1 bp CAGR of 59.9–66.1% versus 58.80% (buffer 0.0 is 58.57%, essentially
equal). At 5 bp only the 1.0–1.5% buffers clear the winner's 54.60%. The
5-year pass is **not** robust: it is strong only at the winner's exact 1.0%
gate and falls to 41–46% at neighbouring buffers. This is a genuine limitation,
not a rounding issue. I report it prominently because the README asks not to
sacrifice the 5-year result.

### 7.5 Entry delay

Delaying only the overlay's sell (signal one, two or three bars later, fill
the next open) leaves the result intact:

| Delay | 10y 1 bp | 5y 1 bp |
|---|---:|---:|
| 0 bars (09:31) | 65.17 / 39.02 | 54.92 / 30.99 |
| 1 bar (09:32) | 64.38 / 39.09 | 54.84 / 31.02 |
| 2 bars (09:33) | 64.89 / 39.37 | 56.21 / 30.13 |
| 3 bars (09:34) | 64.59 / 39.55 | 55.59 / 29.95 |

The edge is not a one-minute microstructure artifact; it survives a few
minutes of execution lag.

### 7.6 Prior-day-trend variant

Restricting the overlay to days after a prior **up** day and widening the
band to 0.15–0.75% gives the strongest headline numbers:

| Variant | n | 10y 1 bp | 5y 1 bp | 10y 5 bp | 5y 5 bp |
|---|---:|---:|---:|---:|---:|
| 0.15–0.75%, prior up | 106 | 67.55 / 40.62 | 63.86 / 30.71 | 61.29 / 41.75 | 57.97 / 31.37 |
| 0.15–0.50%, prior up | 78 | 65.67 / 39.99 | 60.76 / 33.49 | 59.90 / 42.92 | 55.43 / 34.13 |

The 0.15–0.75% prior-up variant has higher CAGR but a slightly *worse* 10y
drawdown (40.62% vs 39.02%) and two more parameters. Its 5-year edge is also
concentrated in the 2025 events (2025-02-27 and 2025-03-03, both gap-up days
outside the 0.15–0.50% band). I did not make it primary. It is the direct
answer to the "trade gaps with the prior day's trend" branch, and it is
stronger on CAGR, but it is more selected.

## 8. Pass/fail, explicitly

Against TQQQ buy-and-hold (10y 39.28% / 81.68%; 5y 13.47% / 81.68%) at 1 bp:

- 10y: CAGR 65.17% > 39.28% ✅; max DD 39.02% < 81.68% ✅. **PASS.**
- 5y: CAGR 54.92% > 13.47% ✅; max DD 30.99% < 81.68% ✅. **PASS.**
- 5 bp: 58.02% / 40.93% and 48.78% / 31.65%. **PASS.**
- 10 bp: 49.51% / 45.91% and 41.44% / 32.49%. **PASS** (CAGR still far above
  TQQQ).

Against the winner at 1 bp (10y 58.80% / 44.56%; 5y 49.88% / 33.49%):

- 10y: CAGR +6.37 pp ✅; max DD −5.54 pp ✅. **Strict dominance.**
- 5y: CAGR +5.04 pp ✅; max DD −2.50 pp ✅. **Strict dominance.**

Against the winner at 5 bp (10y 54.60% / 47.08%; 5y 45.89% / 34.13%):

- 10y: CAGR +3.42 pp ✅; max DD −6.15 pp ✅. **Strict dominance.**
- 5y: CAGR +2.89 pp ✅; max DD −2.48 pp ✅. **Strict dominance.**

Against the winner at 10 bp (10y 49.50% / 50.06%; 5y 41.05% / 34.93%):

- 10y: CAGR +0.01 pp ✅; max DD −4.70 pp ✅. **Strict dominance**, though the
  CAGR margin is only 0.01 pp.
- 5y: CAGR +0.39 pp ✅; max DD −2.44 pp ✅. **Strict dominance.**

The formal targets are met at all three cost levels. The honest qualification
is §7.4: the 5-year strict dominance is not robust to the arm-gate buffer.

## 9. Statistical honesty and mechanism

- **The per-event edge is not significant.** Mean +0.41% per overlay event,
  t = 1.60 over 10 years and t = 0.92 over 5 years. The improvement is a
  tail-risk effect: the overlay avoids a handful of large intraday declines
  (the eight biggest gains are 6.0–12.4%, all eight on stop days). The
  drawdown reduction is structural — you cannot be long during the avoided
  session — while the CAGR improvement is sample-dependent.
- **The 10-year result is a crash-hedge result.** 2018 contributes +20.0% of
  de-risk PnL, 2021 +20.3%, 2025 +9.1%. Excluding those years, the overlay is
  roughly neutral. Treat 65% as "high-50s to mid-60s", not a guaranteed 65%.
- **The 5-year result is concentrated.** 69 events, t = 0.92, and the arm-gate
  fragility in §7.4. The 5y CAGR improvement is real at the specified
  parameters but is not a broad-based edge.
- **Costs matter.** The overlay adds ~16 round trips per year. At 10 bp the
  10-year CAGR falls from 65.17% to 49.51%, a 15.7 pp cost. At 5 bp it is
  still profitable because the per-event gross edge (about +0.4%) clears the
  10 bp round-trip cost on average, but the margin is thin.
- **No shorting.** The strategy never shorts TQQQ. On a faded gap-up day it
  holds BIL, so it gives up the intraday upside if the gap continues. That is
  the cost of the long-only constraint.

## 10. Caveats

1. **The 5-year pass is fragile to the arm gate** (§7.4). The 10-year pass at
   1 bp is robust across SMA, stop, gap band and arm buffer; the 5-year is not.
2. **The gap band was chosen from the same sample.** The plateau in §7.1
   mitigates but does not eliminate selection risk. The economic story
   (small gaps fill, large gaps continue) is supported by the external
   literature, which is some independent confirmation, but the exact
   0.15–0.50% bounds are sample-specific.
3. **The effect is concentrated in stressed years.** 2017 and 2024 are cost
   years; 2018, 2021 and 2025 carry the benefit. A future calm bull market
   would make the overlay a drag.
4. **The 15:59 re-entry is one minute before the close.** The harness cannot
   fill at the official 16:00 close. The last-minute PnL is small but not
   zero.
5. **The per-event edge is not statistically significant** (t = 1.60 / 0.92).
   The drawdown cut is the robust part; the CAGR improvement is not.
6. **Sample.** The 1-minute data starts in 2016; there is no 2000 or 2008
   minute data. The 10-year window includes one major crash (2020) and one
   severe whipsaw (2018), but not a 2000-style multi-year bear.
7. **Fat tails.** The base winner can lose 33–45% from peak to trough. The
   overlay cuts that to 31–39%, but this is still a high-risk 3× ETF strategy.
8. **No leverage beyond 1× TQQQ.** The weights sum to ≤ 1; the strategy cannot
   add TQQQ on gap-downs or short gap-ups. A levered version would have a
   different (and riskier) return profile.

## 11. Sources

The size split — small gaps fill, large gaps continue — is well documented:

1. MPM Markets, *Testing the "Gaps Always Fill" Myth Across Six Futures
   Markets* (2026). Small gaps fill quickly; large gaps persist for several
   sessions; no reliable edge after costs.
   <https://mpmmarkets.com/research/gaps-always-fill-myth-futures-markets>
2. Steady Turtle, *How often does the gap fill? NQ & ES, six years of data*
   (2026). NQ same-session fill 60.3%; sub-10-point gaps 96.4%, 80-point+
   gaps 38.1%. "Big gaps are continuation, not fade."
   <https://steady-turtle.com/statistics/gap-fill-probability>
3. Open Market Journal, *Does the S&P 500 Fill Its Gaps? It Depends on Size*
   (2026). Gaps under 0.25× ATR fill 94%; over 2× ATR fill 9%.
   <https://openmarketjournal.com/research/sp500-gap-fill-probability>
4. thetrading.tools, *Gap Analysis: Do Gaps Always Fill? SPY & QQQ*
   (updated 2026-11-23). 2%+ up-gaps fill same-day 27% of the time; 1%+
   up-gaps have a positive average open→close drift and a ~60% up-day rate.
   <https://www.thetrading.tools/gap-analysis>
5. Aiche, Cohen & Griskin, *Stocks Opening Price Gaps and Adjustments to New
   Information*, Computational Economics 63, 877–891 (2024). Positive gaps
   drift in the gap direction; negative gaps are larger and adjust faster.
   <https://link.springer.com/article/10.1007/s10614-023-10363-w>
6. *Filling Open Price Gap on Intraday Timeframe: A Case Study for DJIA Index
   Stocks*, IOSR Journal of Economics and Finance (2019). 68.2% of small up
   gaps close same-session; only 12.1% of +2%+ up gaps close; 50% of up gaps
   close by 09:52, down gaps by 11:08.
   <https://www.iosrjournals.org/iosr-jef/papers/Vol10-Issue5/Series-2/C1005021418.pdf>
7. *Price gap anomaly in the US stock market: The whole story*,
   Journal of Behavioral and Experimental Finance (2020). 1928–2018: prices
   tend to move in the gap direction on the gap day; the momentum effect is
   temporary; contradicts the "gaps always fill" myth.
   <https://www.sciencedirect.com/science/article/pii/S1062940820300747>
8. Grant, Wolf & Yu, *Intraday price reversals in the US stock index futures
   market: A 15-year study*, Journal of Banking & Finance 29(5) (2005).
   Significant intraday reversals after large opening changes, stronger after
   large positive changes; profits shrink after bid–ask costs.
   <https://www.sciencedirect.com/science/article/pii/S0378426604000949>

Opening auction and overnight-information evidence:

9. *Price Discovery in Auction Markets: A Look Inside the Black Box*,
   Review of Financial Studies 13(3) (2000). The opening auction aggregates
   overnight information; the opening trade can reflect stabilization and
   non-information factors.
   <https://academic.oup.com/rfs/article-abstract/13/3/627/1576835>
10. Gross, *Price Discovery in Opening Procedures* (2003). NYSE/Nasdaq
    openings after delayed openings; overnight information is incorporated
    in the opening procedure.
    <https://leeds-faculty.colorado.edu/grossd/Research/Price%20Discovery%20in%20Opening%20Procedures%202003-11.pdf>
11. *The interaction between opening call auctions and ongoing trade:
    Evidence from the NYSE*, Journal of Financial Markets (2004). Opening
    volume predicts daytime volume; opening trade price reversals; the
    opening process handles information efficiently.
    <https://www.sciencedirect.com/science/article/abs/pii/S1058330004000023>

Overnight-to-intraday reversal:

12. *Does overnight return predict the first half-hour return for U.S. market
    indices?* (2026). High overnight returns negatively predict the first
    half-hour return; the reversal strengthens in stress and weakened after
    the 2010s.
    <https://www.sciencedirect.com/science/article/pii/S1062940826001294>
13. Gao, Han, Li & Zhou, *Market intraday momentum*, Journal of Financial
    Economics 129(3) (2018). The first half-hour return predicts the last
    half-hour return; stronger on volatile days and macro-news days.
    <https://www.sciencedirect.com/science/article/pii/S0304405X18301351>
14. Rosa, *Understanding intraday momentum strategies*, Journal of Futures
    Markets (2022). The overnight→last-half-hour predictability disappears
    out of sample; threshold strategies help. A caution on overnight-gap
    predictors.
    <https://onlinelibrary.wiley.com/doi/full/10.1002/fut.22375>

Cost caution:

15. Loomi, *Gap Fill Strategy: NQ Opening Gap Statistics* (2026). 3,236 NQ
    gap-fade trades, 2010–2026: three of four gap-size buckets lose after
    1 point of costs; small gaps are the worst; only 0.6–1.0% gaps are
    positive and only after 2020.
    <https://www.loomiai.io/learn/opening-gap-fill-strategy-nasdaq>
16. *Another look at trading costs and short-term reversal profits*, Journal
    of Banking & Finance (2012). Reversal profits can survive costs with
    better portfolio construction; conventional cost estimates can be
    misleading.
    <https://www.sciencedirect.com/science/article/pii/S0378426611002263>

The negative standalone results in §4 are consistent with sources 1, 2, 3,
4 and 15: the gap signal is real but small, and costs eat most of it. The
overlay works because it pays the cost only on ~16 selected days per year
and keeps the overnight drift.

## 12. Files and reproduction

- `strategy.py` — self-contained: loads the local 1-minute panel, builds the
  weights, runs the official harness at 1/5/10 bp for both windows, computes
  the yearly, rolling-3-year, plateau and prior-up tables, and writes
  `result.json`.
- `result.json` — machine-readable metrics: windows × {1, 5, 10 bp}, winner
  and TQQQ references, pass flags, yearly, rolling 3-year, gap-band plateau,
  prior-up variant, gap buckets and the standalone gap-down fade.
- `report.md` — this file.

Run:

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
python research\agents2\gap-fill-fade\strategy.py
```

The shipped code reproduces the headline exactly with `research/bt.py`:
65.17% / 39.02% and 54.92% / 30.99% at 1 bp; 58.02% / 40.93% and
48.78% / 31.65% at 5 bp; 49.51% / 45.91% and 41.44% / 32.49% at 10 bp.

No core files were modified. All work is under
`research/agents2/gap-fill-fade/`; the research scratch is outside the repo.
