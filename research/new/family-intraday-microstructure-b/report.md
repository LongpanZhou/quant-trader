# Opening-drive continuation, five-session hold — result

**Verdict: a fragile development-window pass at 1 bp, and a 5 bp CAGR pass
with drawdown slightly above the 60% soft target. It fails at 10 bp. The
parameter plateau is jagged, so this is not a robust family winner.**

On the 2016-01-04 -> 2023-12-29 development window, the frozen center
(09:45 ET, QQQ above session open and opening VWAP, fixed five-session hold,
BIL flat) earns:

| Cost | CAGR | Max DD (1-min) | Max DD (daily) | Sharpe (1-min) | Sharpe (daily) | Sortino | Vol | Ending equity |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **1 bp** | **46.59%** | **59.70%** | 58.84% | **0.97** | 0.97 | 1.39 | 54.85% | $2,119,032 |
| **5 bp** | **37.39%** | **61.65%** | 60.83% | **0.86** | 0.85 | 1.22 | 54.85% | $1,263,340 |
| **10 bp** | 26.71% | 64.40% | 63.39% | 0.71 | 0.71 | 1.01 | 54.88% | $661,834 |

TQQQ exposure is **79.6%** of minutes (BIL 20.4%); daily-return correlation
to TQQQ is **0.82**. The strategy makes 323 five-session entries (1,293
fills, 8,789x turnover at 1 bp).

Benchmarks on the same window and 1-minute marks:

| Asset | CAGR | Max DD | Sharpe | Vol |
|---|---:|---:|---:|---:|
| TQQQ buy-and-hold | 36.15% | 82.29% | 0.80 | 66.55% |
| QQQ buy-and-hold | 18.91% | 37.30% | 0.90 | 22.02% |
| BIL | 1.39% | 0.24% | 0.92 | 1.52% |
| **Strategy 1 bp** | **46.59%** | **59.70%** | **0.97** | 54.85% |

The brief quotes the TQQQ bar as 36.72% / 82.29% / 0.82; the harness computes
36.15% on these exact bars. The strategy clears both versions at 1 bp. At
5 bp it clears the CAGR bar (37.39%) and is 1.65 pp above the soft 60% DD
target but far below the hard 82.29% bar. At 10 bp it fails the CAGR bar.

**Pass/fail against the stated development target**

| Test | Result |
|---|---|
| 1 bp CAGR > 36.72% | **Pass** (46.59%) |
| 1 bp max DD < 60% | **Pass** (59.70%) |
| 1 bp Sharpe > 0.82 | **Pass** (0.97) |
| 5 bp CAGR > 36.72% | **Pass** (37.39%) |
| 5 bp max DD < 60% (soft) | **Fail** (61.65%); still below the 82.29% hard bar |
| 10 bp CAGR > 36.72% | **Fail** (26.71%) |

Calmar at 1 bp is 0.78 versus 0.44 for TQQQ. The strategy is a genuine
risk-adjusted improvement, but the 5 bp result is only 0.67 pp above the
brief's CAGR bar, and the parameter plateau is not smooth. Treat the pass as
provisional.

---

## 1. Exact rules

Full pre-registration: `HYPOTHESIS.md`.

1. **Signal at 09:45 ET.** `p` = QQQ close of the 09:45 bar; `open` = QQQ
   open of the 09:30 bar; `vwap` = volume-weighted typical price of QQQ over
   09:30..09:45. Signal is true iff `p > open` **and** `p > vwap`.
2. **Entry.** If flat and the signal is true, target 100% TQQQ on the 09:45
   bar close; fill at the 09:46 open.
3. **Hold.** Exactly five sessions (entry session = session 1), including
   overnight.
4. **Exit.** At the 15:58 close of the fifth session, target 100% BIL; fill
   at the 15:59 open. Flat overnight.
5. **Overlap.** Intermediate signals are ignored while a block is open. The
   next signal after the exit can start a new block.
6. **Costs.** 1 bp headline; 5/10 bp reported. 2% band, next-open fills.
7. **No stop, no vol target, no daily trend, no volatility/drawdown regime,
   no relative strength.** The only signal inputs are QQQ's opening price,
   its 09:45 price and the opening VWAP.

The implementation is in `strategy.py`; every fill is at the next bar's open
through `research/bt.py`. No 2024-2026 bar enters a signal, weight or metric.

**Causality audit.** Rebuilding the weights on a panel truncated at
2020-06-30 reproduces the full-panel weights exactly before the cut (maximum
absolute difference 0.0). Scrambling every post-2021-01-01 QQQ OHLC value
leaves all pre-2021 weights unchanged (maximum absolute difference 0.0). The
audit is stored in `result.json` under `causality_audit`.

---

## 2. The lead's 43.65%: what reproduces and what does not

The lead's 10:00 daily entry/exit-at-close prototype was reported at 43.65%
at 1 bp and 20.3% at 5 bp. We could not reproduce 43.65% with a causal
10:00 -> 15:59 implementation:

| 10:00 variant (causal) | 1 bp CAGR | 5 bp CAGR | 10 bp CAGR | 1 bp max DD |
|---|---:|---:|---:|---:|
| One-session, 10:00 -> 15:59 | **6.60%** | **-11.33%** | **-29.57%** | 54.84% |
| Fixed five-session hold | **28.83%** | **20.73%** | — | 64.97% |
| 09:45 fixed five-session hold (frozen center) | **46.59%** | **37.39%** | **26.71%** | 59.70% |

The one-session 10:00 version is turnover-heavy: 4,744x turnover at 1 bp and
a 5 bp CAGR of -11.3%. A 43.65% figure for a 10:00 -> close strategy is not a
causal next-open result in this harness unless the hold is longer than one
session or the return attribution includes pre-signal prices.

The attribution confirms the gap:

- On the 919 signal days, mean TQQQ return from the **10:00 price to the
  close** is **+0.123%/day**.
- Mean TQQQ **close-to-close** on those same days is **+1.394%/day**. That
  includes the overnight gap and the 09:30-10:00 move, both of which happen
  before a 10:00 signal can be filled. Using it would be look-ahead.
- The unconditional 10:00-to-close mean is +0.029%/day, so the signal has a
  real but small one-session edge. The multi-session hold, not the single
  close, is what turns it into a TQQQ-beating return.

The 43.65% is therefore **not verified** as the stated 10:00 daily strategy.
The closest causal result is the 09:45 five-session variant at 46.59% (1 bp);
the 10:00 five-session variant is 28.83%. The decision time is load-bearing.

### 2.1 VWAP proxy robustness

The lead allowed the simple mean of QQQ closes from 09:30 to 10:00 as a VWAP
proxy. It does not rescue the 43.65% figure: the 10:00 one-session version
with the close-mean proxy earns 10.93% at 1 bp and -7.08% at 5 bp, still far
from 43.65%. But the proxy is a useful robustness check for the frozen
center. Applied to the 09:45 five-session strategy, the close-mean proxy
earns 47.19% / 54.42% / 1.00 at 1 bp and 38.18% / 55.85% / 0.88 at 5 bp
(10 bp: 27.69% / 58.11% / 0.73). The standard typical-price VWAP center is
46.59% / 59.70% / 0.97 and 37.39% / 61.65% / 0.86. The result is therefore
not sensitive to the VWAP definition; the close-mean proxy is slightly
better. It is reported in `result.json` as `close_mean_vwap_proxy`, not used
as the frozen center (the standard VWAP is the pre-registered definition).

An exploratory open-only signal (drop the VWAP condition; computed in the
same screen and not stored in `result.json`) earns 44.51% / 72.67% at 1 bp
and 34.97% / 74.49% at 5 bp: the open comparison carries most of the signal,
but the VWAP filter improves the drawdown materially.

---

## 3. Pre-registered 8-cell grid

All cells at 1 bp and 5 bp. The center is cell 1. The threshold-10 bp cell is
not in the grid; it appears in the sensitivity table as exploratory only.

| # | Cell | 1 bp CAGR | 1 bp DD | 1 bp Sharpe | 5 bp CAGR | 5 bp DD | TQQQ exp | Entries |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | **center: 09:45, 0 bp, N=5, fixed** | **46.59%** | **59.70%** | **0.97** | **37.39%** | **61.65%** | 79.6% | 323 |
| 2 | decision 10:00 | 28.83% | 64.97% | 0.74 | 20.73% | 67.25% | 79.2% | 324 |
| 3 | decision 10:30 | 0.12% | 79.20% | 0.29 | -6.26% | 81.83% | 78.9% | 328 |
| 4 | threshold 20 bp | 36.05% | 48.77% | 0.92 | 31.96% | 48.93% | 37.4% | 152 |
| 5 | threshold 50 bp | 1.12% | 42.65% | 0.15 | 0.87% | 43.02% | 3.0% | 12 |
| 6 | hold 2 | 11.53% | 58.72% | 0.47 | -1.56% | 64.98% | 60.5% | 623 |
| 7 | hold 3 | 17.97% | 63.14% | 0.58 | 7.28% | 67.26% | 69.5% | 474 |
| 8 | close-strength exit | 46.71% | 58.54% | 1.06 | 32.87% | 59.59% | 64.9% | 495 |

**What the grid says**

- The 09:45 decision is load-bearing: 10:00 is 17.8 pp lower at 1 bp, and
  10:30 is essentially zero. The opening drive must be acted on early.
- The 20 bp threshold cuts exposure to 37% and DD to 48.8%, but also cuts the
  5 bp CAGR to 31.96% (below the bar). It is the low-risk variant, not the
  center.
- Hold length is the most unstable dimension: N=2 and N=3 are far below
  N=5. The N=5 result is a local peak, not a smooth plateau (see section 4).
- The close-strength exit has the best 1 bp Sharpe (1.06) and a lower 1 bp
  DD than the center (58.54% vs 59.70%), but at 5 bp it earns 32.87%, below
  the bar. The fixed hold is the cost-robust choice.
- The center is **not** the best 1 bp cell (cell 8 is 0.12 pp higher); it is
  chosen for the 5 bp result and simplicity, not for the highest single
  number.

---

## 4. Sensitivity and the plateau

### 4.1 Hold length (09:45, 0 bp, fixed exit)

| Hold | 1 bp CAGR | 1 bp DD | 5 bp CAGR | 5 bp DD |
|---:|---:|---:|---:|---:|
| 2 | 11.53% | 58.72% | -1.56% | 64.98% |
| 3 | 17.97% | 63.14% | 7.28% | 67.26% |
| 4 | 16.58% | 69.68% | 7.82% | 72.19% |
| **5** | **46.59%** | **59.70%** | **37.39%** | **61.65%** |
| 6 | 28.66% | 69.00% | 21.72% | 70.63% |
| 7 | 44.82% | 70.96% | 37.89% | 72.07% |

The curve is **jagged**: 5 and 7 are peaks, 4 and 6 are troughs. A smooth
holding-period effect would rise or fall monotonically; this does not. The
five-session result is therefore a path-dependent selection, not a stable
plateau. This is the single biggest reason to treat the pass as fragile.

### 4.2 Decision time (0 bp, N=5, fixed exit)

| Decision | 1 bp CAGR | 1 bp DD |
|---|---:|---:|
| 09:40 | 25.60% | 85.19% |
| **09:45** | **46.59%** | **59.70%** |
| 09:50 | 37.54% | 72.51% |
| 10:00 | 28.83% | 64.97% |
| 10:30 | 0.12% | 79.20% |

The 09:45-09:50 region is positive, but 09:40 and 10:00 are much weaker.
The exact 09:45 minute is a local peak. The economic story ("act on the
first 15-minute drive") is plausible, but the minute-level sensitivity is a
selection risk.

### 4.3 Confirmation threshold (09:45, N=5, fixed exit)

| Threshold | 1 bp CAGR | 1 bp DD | 5 bp CAGR | 5 bp DD | TQQQ exp |
|---:|---:|---:|---:|---:|---:|
| 0 bp | 46.59% | 59.70% | 37.39% | 61.65% | 79.6% |
| 10 bp (exploratory) | **64.23%** | **52.18%** | **56.01%** | **52.33%** | 63.1% |
| 20 bp (pre-registered) | 36.05% | 48.77% | 31.96% | 48.93% | 37.4% |
| 50 bp (pre-registered) | 1.12% | 42.65% | 0.87% | 43.02% | 3.0% |

The 10 bp cell is spectacular at both 1 bp and 5 bp, and even at 10 bp it
earns 46.31% / 52.55% / 1.01. But it is **not in the pre-registered grid**
and the response is non-monotonic (0 -> 10 -> 20 -> 50 bp: 46.6 -> 64.2 ->
36.1 -> 1.1). It is almost certainly an overfit spike. It is reported only
so the selection risk is visible; it is not the frozen strategy. The
pre-registered 20 bp cell is a genuine lower-risk variant with a 5 bp CAGR
below the bar.

---

## 5. Cost ladder and trading profile

| Cost | CAGR | DD | Sharpe | Fills | Turnover | Ending equity |
|---:|---:|---:|---:|---:|---:|---:|
| 1 bp | 46.59% | 59.70% | 0.97 | 1,293 | 8,789x | $2,119,032 |
| 5 bp | 37.39% | 61.65% | 0.86 | 1,293 | 6,053x | $1,263,340 |
| 10 bp | 26.71% | 64.40% | 0.71 | 1,293 | 3,873x | $661,834 |

- 323 entries, all exactly five sessions; average and median hold 5.0
  sessions.
- Turnover is high in absolute terms (8,789x starting equity at 1 bp). The
  center makes 323 round trips over 8 years (about 40/year), fewer than the
  919 one-session 10:00 entries (about 115/year), but total traded notional
  is higher than the one-session version (8,789x vs 4,744x) because each
  switch trades both the TQQQ and BIL legs and the strategy is in TQQQ 80% of
  the time.
- The 1 bp -> 5 bp cost drag is 9.2 pp of CAGR; the 5 bp -> 10 bp drag is
  another 10.7 pp. The one-session 10:00 version has a larger 1 bp -> 5 bp
  drag (17.9 pp, 6.60% to -11.33%) because its gross return is too small to
  absorb the switches. The five-session hold is therefore more cost-robust in
  CAGR terms even though its total turnover is higher.
- At 5 bp the strategy still beats TQQQ's ending equity ($1.26M vs $1.18M)
  with a 20.6 pp lower max DD. At 10 bp it lags ($0.66M vs $1.18M).

The 5 bp result is the important one for investability: it clears the CAGR
bar by 0.67 pp over the brief's 36.72% and 1.24 pp over the harness's 36.15%.
That is a thin margin, not a comfortable one.

---

## 6. Yearly returns, cuts and placebo

### 6.1 Yearly returns (1 bp)

| Year | Strategy | TQQQ | Comment |
|---|---:|---:|---|
| 2016 | +8.13% | +19.86% | lagged the 2016 bull |
| 2017 | +38.03% | +114.54% | captured some, far below TQQQ |
| 2018 | **-2.47%** | -20.76% | strong relative year; small loss |
| 2019 | +105.66% | +148.23% | strong |
| 2020 | +162.75% | +104.14% | beat TQQQ |
| 2021 | +143.18% | +81.05% | beat TQQQ |
| 2022 | **-53.49%** | -79.39% | severe absolute loss, better than TQQQ |
| 2023 | +119.75% | +192.05% | lagged the melt-up |

The profile is not a consistent TQQQ substitute. It beats TQQQ in 2018,
2020, 2021 and 2022 (relative), and lags in the strong bull years 2016,
2017, 2019 and 2023.
The two negative years are 2018 (-2.5%) and 2022 (-53.5%). A -53.5% year is
a real risk, even if it is better than TQQQ's -79.4%.

### 6.2 Cut tests

| Window | CAGR | Max DD | Sessions |
|---|---:|---:|---:|
| 2016-2019 | 32.68% | 52.28% | 1,006 |
| 2020-2023 | 60.09% | 58.84% | 1,006 |

The first half is below the 36.72% bar; the second half is far above it. The
full-window pass therefore relies on the second half. This is consistent with
the strategy being a high-beta TQQQ product that does well in the 2020-2021
liquidity boom and the 2023 recovery, and less well in the 2016-2019 period.

### 6.3 Shuffled-signal placebo

We shuffle the 09:45 signal days (preserving the number of signal days) and
rerun the exact fixed-five-session state machine 300 times.

| Test | Observed | Placebo mean | Placebo p95 | p-value |
|---|---:|---:|---:|---:|
| 1 bp CAGR | 46.59% | 21.18% | 41.35% | **0.020** |
| 5 bp CAGR | 37.39% | 13.59% | 32.63% | **0.020** |
| 5 bp max DD | 61.65% | 77.80% | — | — |

The observed result is above the 95th percentile of the placebo at both cost
levels. The signal's **day selection** matters: this is not just "hold TQQQ
80% of the time." The placebo does not test the 09:45 minute specifically;
the decision-time table in section 4.2 is the relevant test for that, and it
shows a local peak at 09:45.

---

## 7. Falsifiers and overlays

| Test | 1 bp CAGR | 1 bp DD | 5 bp CAGR | 5 bp DD | Verdict |
|---|---:|---:|---:|---:|---|
| **Center (no stop)** | **46.59%** | **59.70%** | **37.39%** | **61.65%** | frozen |
| Entry-day-VWAP stop | 28.13% | 54.89% | 17.74% | 57.14% | **rejected**: cuts CAGR too much |
| Hard stop 15% | 46.24% | 64.84% | 37.04% | 67.07% | rejected: more DD, less CAGR |
| Hard stop 20% | 46.57% | 59.74% | 37.38% | 61.68% | never triggers; not load-bearing |
| Trailing stop 20% | 46.57% | 59.74% | 37.38% | 61.68% | never triggers; not load-bearing |
| Close-strength exit | 46.71% | 58.54% | 32.87% | 59.59% | better 1 bp DD/Sharpe, fails 5 bp CAGR |
| Threshold 10 bp (exploratory) | 64.23% | 52.18% | 56.01% | 52.33% | unregistered spike; not used |
| Decision 09:40 | 25.60% | 85.19% | — | — | worse |
| Decision 09:50 | 37.54% | 72.51% | — | — | worse |
| Hold 4 | 16.58% | 69.68% | 7.82% | 72.19% | worse |
| Hold 6 | 28.66% | 69.00% | 21.72% | 70.63% | worse |

Falsifier scorecard:

- **F1 (5 bp CAGR <= 36.72%)**: not triggered; 37.39% passes, but by only
  0.67 pp.
- **F2 (10 bp CAGR <= 36.72%)**: triggered; 26.71% fails. The strategy is a
  1-5 bp strategy.
- **F3 (placebo p > 0.10)**: not triggered; p = 0.020.
- **F4 (hold neighbors not positive)**: partially triggered. N=4 and N=6 are
  positive but far below N=5 (16.6% and 28.7% vs 46.6%). The N=5 peak is a
  local spike, not a plateau.
- **F5 (10:00/10:30 do not beat the bar)**: triggered. The 10:00 cell is
  28.8%, the 10:30 cell is 0.1%. The 09:45 minute is load-bearing and local.
- **F6 (entry-day-VWAP stop improves)**: not triggered; the stop cuts CAGR to
  28.1%. The fixed hold is the better risk control.
- **F7 (hard/trailing stop improves)**: not triggered; 15% stops add DD, 20%+
  stops never trigger.
- **F8 (a half is below the bar)**: partially triggered; 2016-2019 is 32.68%,
  below 36.72%, while 2020-2023 is 60.09%.

The honest reading: the center is a real, cost-robust dev result through
5 bp, but it is not robust to the hold-length, decision-time or threshold
choice. It is a fragile pass, not a clean family winner.

### 7.1 Mandate variant tests

The mandate lists first-hour momentum, close-auction strength and a failed
opening-drive reversal. All use the same fixed-five-session hold and
next-open fills; the failed/reclaim variants enter at 10:31 after the 10:30
check.

| Variant | 1 bp CAGR | 1 bp DD | 1 bp Sharpe | 5 bp CAGR | 5 bp DD | TQQQ exp |
|---|---:|---:|---:|---:|---:|---:|
| First-hour momentum (10:30 continuation) | 0.12% | 79.20% | 0.29 | -6.26% | 81.83% | 78.9% |
| Close-auction strength (cell 8) | 46.71% | 58.54% | 1.06 | 32.87% | 59.59% | 64.9% |
| Inverse opening drive (below both at 09:45) | 19.93% | 71.23% | 0.61 | 12.88% | 73.27% | 74.3% |
| Failed drive: above at 09:45, below at 10:30 | 21.87% | 47.40% | 0.73 | 18.31% | 48.81% | 35.4% |
| Reclaim: below at 09:45, above at 10:30 | 10.38% | 57.00% | 0.45 | 7.36% | 57.82% | 33.2% |

The continuation direction is the right one. The inverse and both
failed-drive reversals have positive returns but fail the CAGR bar; the
failed-drive 10:30 variant has a much lower DD (47.4%) but only 21.9% CAGR.
The first-hour momentum variant (10:30 continuation) is essentially zero.
The close-auction strength variant is the best risk-adjusted alternative at
1 bp (Sharpe 1.06, DD 58.54%) but fails the 5 bp CAGR bar. None of the
variants beats the frozen center on the 5 bp objective.

---

## 8. Why it might be fragile

1. **The hold-length curve is jagged.** N=5 (46.6%) is a local peak between
   N=4 (16.6%) and N=6 (28.7%), with N=7 (44.8%) another peak. A genuine
   five-session effect should not collapse at four or six sessions. The
   most likely explanation is path dependence: a handful of 2020-2022 blocks
   happen to align with the five-session grid. This is the main overfitting
   concern.
2. **The 09:45 minute is a local peak.** 09:40 is 25.6%, 09:45 is 46.6%,
   09:50 is 37.5%, 10:00 is 28.8%. The opening-drive story is plausible, but
   the exact minute matters more than a robust mechanism should.
3. **The threshold response is non-monotonic.** 0 bp 46.6%, 10 bp 64.2%
   (unregistered), 20 bp 36.1%, 50 bp 1.1%. The 10 bp spike is almost
   certainly overfit. The pre-registered 20 bp cell is a lower-risk but
   below-bar variant.
4. **It is still a high-beta TQQQ product.** TQQQ exposure 79.6%, daily
   correlation 0.82, 2022 -53.5%. The drawdown reduction comes from being in
   BIL 20% of the time and from the day selection, not from a market-neutral
   or low-beta mechanism.
5. **The 5 bp margin is thin.** 37.39% vs 36.72% is 0.67 pp. A different
   fill convention, a slightly wider band, or a higher market-impact
   assumption could push it below the bar. The 10 bp result (26.71%) shows
   how quickly the edge decays.
6. **The first half is below the bar.** 2016-2019 CAGR is 32.68%; the
   full-window pass relies on 2020-2023. The strategy is not consistently
   above the bar in both halves.
7. **The lead's 43.65% does not reproduce causally.** The 10:00 -> close
   one-session version is 6.60% at 1 bp and -11.33% at 5 bp. If the lead's
   prototype used close-to-close attribution or a longer hold, the reported
   number is not comparable to this frozen strategy. The 09:45 five-session
   version is the causal variant that gets close to 46.6%.

---

## 9. Family purity and distinctness

- **Family:** intraday-microstructure. The primary signal is the opening
  drive: QQQ at 09:45 versus the 09:30 opening auction and the 09:30-09:45
  VWAP. It is not a daily trend, volatility, drawdown or relative-strength
  signal.
- **No daily SMA, no volatility/drawdown regime, no relative strength.** The
  exit is a fixed five-session count, not a regime switch. The BIL allocation
  is the mandated flat asset.
- **Distinct from `orb-tqqq-volume`:** that strategy uses a 30-minute opening
  range, volume/ATR confirmation, an ATR stop and a one-session hold. This
  one uses price vs open/VWAP, no volume/ATR filter, no stop, and a
  five-session hold.
- **Distinct from `intraday-close-momentum`:** the decision is at 09:45, not
  the close.
- **Distinct from the daily SMA baseline:** no moving average or daily trend
  state. The only reason the strategy holds overnight is the five-session
  block, not an overnight trend filter.
- **No shorting, no leverage beyond TQQQ's own 3x, weights sum to 1.** The
  BIL leg is explicit, not hidden cash.

---

## 10. Reproduction and files

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
$env:BT_THREADS = "1"
python research\new\family-intraday-microstructure-b\strategy.py
```

Files:

- `research/new/family-intraday-microstructure-b/HYPOTHESIS.md`
- `research/new/family-intraday-microstructure-b/strategy.py`
- `research/new/family-intraday-microstructure-b/result.json`
- `research/new/family-intraday-microstructure-b/report.md`

`strategy.py` writes `result.json` and prints the 1/5/10 bp headline, the
8-cell grid at 1 bp and 5 bp, yearly returns and the placebo. The 2024-2026
holdout is not loaded, inspected or used.

---

## 11. Bottom line

- **Frozen dev result (09:45, 0 bp, fixed five-session hold):**
  **46.59% CAGR / 59.70% max DD / 0.97 Sharpe at 1 bp**;
  **37.39% / 61.65% / 0.86 at 5 bp**;
  **26.71% / 64.40% / 0.71 at 10 bp**.
- **TQQQ exposure 79.6%, BIL 20.4%, daily correlation to TQQQ 0.82.**
- **1 bp: clean pass** against CAGR > 36.72% and DD < 60%.
- **5 bp: CAGR pass** (37.39%) with DD 61.65%, slightly above the 60% soft
  target but below the 82.29% hard bar.
- **10 bp: fail** (26.71%).
- The placebo is significant (p = 0.020 at 1 bp and 5 bp), so the day
  selection is not noise. But the hold-length, decision-time and threshold
  plateaus are jagged; N=5 and 09:45 are local peaks, and the 10 bp
  threshold is an unregistered spike.
- **Recommendation:** treat this as a fragile, cost-robust-through-5 bp dev
  pass, not a robust family winner. If a holdout is run, run it once with
  this frozen center and do not re-tune after seeing it. If the lead wants a
  more robust strategy, the next step is to replace the fixed five-session
  count with an economic holding rule (e.g., a close-strength or VWAP-based
  exit) and accept the lower 5 bp return; the current N=5 result should not
  be presented as a stable plateau.
