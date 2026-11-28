# Report: quarter-end rebalancing flow — the 2+2 session window

**Strategy:** `family-quarter-end-flow`
**Window:** development only, 2016-01-04 .. 2023-12-29, 1-minute marks, next-open
fills, 2% band, idle BIL.
**Bar:** TQQQ dev 36.72% CAGR / 82.29% max DD / 0.82 Sharpe (brief). The panel's
1 bp TQQQ buy-and-hold is 36.15% / 82.29% / 0.80.

## Verdict

**Negative — the family is rejected.** The centre (50% TQQQ base, 100% in the
last two sessions of a quarter plus the first two sessions of the next quarter)
earns **25.86% CAGR / 53.81% max DD / 0.82 Sharpe at 1 bp** and **24.72% /
54.16% / 0.80 at 10 bp**. It is 10.9 pp below the CAGR bar. More importantly,
the **shifted +5-session placebo beats it**: 30.07% / 61.01% / 0.92 at 1 bp,
28.87% at 10 bp. A window one week later is better than the real quarter-end
window, so the "quarter-end flow" clock is not identified. The window-only
version earns 4.29% and is below the repo's 5% viability floor. The constant
53.2%-TQQQ control earns 25.54% with a 55.75% DD — almost exactly the centre —
so the window tilt adds only **+0.32 pp CAGR and -1.94 pp DD**. The 2+2 window
is not a special clock; the result is a generic 50/50 risk profile.

## 1. What the strategy does

For each calendar quarter, the window is:

- the last two regular sessions of March, June, September and December;
- plus the first two regular sessions of January, April, July and October.

For each session:

```
w_tqqq(k) = 1.00   if k is in the 2+2 quarter-end window
          = 0.50   otherwise
w_bil(k)  = 1 - w_tqqq(k)
```

- The window is known from the calendar at the prior close. The target for the
  first window session is set at the previous close and filled at the next
  open; the exit target (0.50) is set at the last window session's close and
  filled at the next open. The harness's next-open rule is used unchanged.
- Idle is BIL. The cash-idle version is not reported separately because the
  turnover is low (258x) and BIL is the natural idle asset.
- No trend SMA, no realised vol, no drawdown state, no cross-sectional signal,
  no quarter-return conditioning in the centre. The centre is deliberately
  **unconditional**: the claim is that the calendar window itself has a
  positive flow, not that a strong quarter predicts the next one.

## 2. Headline development result

| cost | CAGR | max DD | Sharpe | Sortino | vol | ending equity |
|---:|---:|---:|---:|---:|---:|---:|
| 1 bp | **25.86%** | **53.81%** | **0.82** | 1.15 | 35.9% | $628k |
| 5 bp | 25.36% | 53.88% | 0.81 | 1.13 | 35.9% | $608k |
| 10 bp | 24.72% | 54.16% | 0.80 | 1.11 | 35.9% | $583k |
| TQQQ | 36.15% | 82.29% | 0.80 | 1.12 | 66.5% | $1.175m |

| cost | fills | turnover |
|---:|---:|---:|
| 1 bp | 1,025 | 258.0x |
| 5 bp | 1,023 | 252.5x |
| 10 bp | 1,027 | 246.2x |

The centre fails the CAGR bar by 10.9 pp. It does cut max DD by 28.5 pp and
roughly matches TQQQ's Sharpe, but that is a lower-risk allocation, not an
above-TQQQ winner. The cost drag is small (-1.14 pp from 1 bp to 10 bp) because
turnover is only 258x.

**Exposure:** mean TQQQ weight **53.2%**; 6.4% of sessions at 100% (the 128
window sessions), 93.6% at 50%. The harness `exposure` field is 100% because
BIL is an asset; the TQQQ weight is the relevant number.

**Drawdown:** 2021-11-22 to 2022-10-13, **-53.81%**. The 50% base halves the
TQQQ drawdown but does not eliminate it.

**Turnover / fills:** 258x, 1,025 fills. Most of the fills are 2%-band
rebalances of the 50/50 book; the window itself adds only 32 round trips.

## 3. The window is not special

Session-level TQQQ open-to-open returns, 2016-2023:

| window | n | mean | t | win rate |
|---|---:|---:|---:|---:|
| 2+2 quarter-end window | 128 | **+25.7 bp** | **0.84** | 50.8% |
| outside the window | 1,884 | +20.7 bp | 2.15 | 56.0% |
| last 1 session | 32 | +59.0 bp | 0.89 | 56.3% |
| first 1 session | 32 | +28.2 bp | 0.42 | 53.1% |
| last 2 sessions | 64 | +48.5 bp | 1.20 | 54.7% |
| first 2 sessions | 64 | +2.9 bp | 0.06 | 46.9% |
| last 3 sessions | 96 | +18.8 bp | 0.51 | 54.2% |
| first 3 sessions | 96 | +43.6 bp | 1.06 | 53.1% |
| last 4 sessions | 128 | +49.9 bp | 1.52 | 56.3% |
| first 4 sessions | 128 | +67.1 bp | 1.79 | 54.7% |
| **shift +5 sessions** | 127 | **+70.3 bp** | **2.18** | 59.1% |
| shift -5 sessions | 127 | +13.4 bp | 0.38 | 47.2% |

The 2+2 window's mean (+25.7 bp) is only 5.0 bp above the outside mean
(+20.7 bp), and its t-stat is 0.84. The shifted +5-session window is much
stronger: +70.3 bp, t = 2.18. The first two sessions of the new quarter are
flat (+2.9 bp, t = 0.06); the last two are positive but weak (+48.5 bp,
t = 1.20). The positive window mean is not a quarter-end flow; it is a
generic mid-month effect that happens to be stronger one week later.

The quarter breakdown is worse:

| quarter | window mean | t |
|---:|---:|---:|
| Q1 (Mar/Apr) | +47.2 bp | 0.71 |
| Q2 (Jun/Jul) | +121.0 bp | 2.07 |
| Q3 (Sep/Oct) | -18.7 bp | -0.31 |
| Q4 (Dec/Jan) | -46.7 bp | -0.86 |

The full-window mean is carried by Q2; Q3 and Q4 are negative. This is not a
stable quarterly flow.

## 4. Pre-registered grid and placebo

The 8 cells were fixed in `HYPOTHESIS.md` before the final run:

| # | base | window | role | 1 bp CAGR | 1 bp DD | 1 bp Sharpe | 10 bp CAGR |
|---:|---:|---|---|---:|---:|---:|---:|
| 1 | 30% | last 2 + first 2 | base neighbour | 18.17% | 38.37% | 0.80 | 16.81% |
| 2 | **50%** | **last 2 + first 2** | **centre** | **25.86%** | **53.81%** | **0.82** | **24.72%** |
| 3 | 70% | last 2 + first 2 | base neighbour | 31.77% | 67.83% | 0.82 | 31.02% |
| 4 | 90% | last 2 + first 2 | base neighbour | 35.47% | 77.87% | 0.81 | 35.23% |
| 5 | 50% | last 2 only | window neighbour | 26.01% | 58.11% | 0.84 | 24.83% |
| 6 | 50% | first 2 only | window neighbour | 24.03% | 49.09% | 0.80 | 22.91% |
| 7 | 50% | last 2 + first 2, shifted +5 | **placebo** | **30.07%** | **61.01%** | **0.92** | **28.87%** |
| 8 | 0% | last 2 + first 2 | window only | 4.29% | 20.85% | 0.35 | 2.79% |

Every base cell fails the 36.72% CAGR bar; the 90% base is the closest at
35.47% (1.25 pp short of the brief bar, 0.68 pp short of the panel TQQQ) but
has a 77.87% DD. The window-only cell is 4.29%,
below the 5% viability floor. The shifted +5 placebo is the highest-Sharpe
cell in the grid (0.92) and beats the centre on CAGR, DD and Sharpe. This is
the decisive negative result.

## 5. Controls

| variant | CAGR | max DD | Sharpe | comment |
|---|---:|---:|---:|---|
| TQQQ buy & hold | 36.15% | 82.29% | 0.80 | bar |
| constant 53.2% TQQQ | 25.54% | 55.75% | 0.82 | same mean weight |
| **centre** | **25.86%** | **53.81%** | **0.82** | window tilt |
| shift -5 sessions | 24.37% | 49.87% | 0.78 | opposite shift |
| de-risk last 2 sessions | 31.60% | 79.69% | 0.75 | negative-flow direction |
| de-risk first 2 after up quarter | 35.01% | 81.70% | 0.79 | conditional momentum |

The constant-exposure control at the same mean weight earns 25.54% with a
55.75% DD. The window tilt adds **+0.32 pp CAGR and -1.94 pp DD**. That is
within noise; the window is not doing meaningful work.

The two rejected alternatives are informative:

1. **De-risk the last two sessions** (the pension-selling direction): 31.60%
   CAGR but a 79.69% DD and 0.75 Sharpe. The data rejects the negative-flow
   direction; quarter-end returns are positive on average, so de-risking them
   costs return and does not reduce the drawdown enough.
2. **De-risk the first two sessions after an up quarter** (a conditional
   momentum/rebalancing rule): 35.01% CAGR, 81.70% DD, 0.79 Sharpe. It is close
   to TQQQ but still below, and it has a much worse DD. It is a momentum
   condition, not the unconditional flow claim, and it is not the centre.

## 6. Placebo

### 6.1 Shifted window (deterministic)

| window | 1 bp CAGR | 1 bp DD | 1 bp Sharpe | 10 bp CAGR |
|---|---:|---:|---:|---:|
| real 2+2 | 25.86% | 53.81% | 0.82 | 24.72% |
| shifted +5 sessions | **30.07%** | 61.01% | **0.92** | **28.87%** |
| shifted -5 sessions | 24.37% | 49.87% | 0.78 | — |

The +5 shift beats the real window by 4.21 pp CAGR and 0.10 Sharpe. The -5
shift is slightly worse. The real window is not the best calendar window in its
own neighbourhood.

### 6.2 Random 4-session windows

32 random 4-session windows, 1,000 draws, same 50% base:

| | CAGR |
|---|---:|
| real (daily approximation) | 25.84% |
| placebo mean | 24.99% |
| placebo p95 | 30.57% |
| placebo p99 | 32.12% |
| placebo max | 35.00% |
| p-value (draws >= real) | **0.418** |

The real window is at the 58th percentile of random 4-session windows. There is
no evidence that the quarter-end dates are special.

## 7. Sub-periods and yearly behaviour

| period | strategy CAGR | strategy DD | TQQQ CAGR | TQQQ DD |
|---|---:|---:|---:|---:|
| 2016-2019 | 26.47% | 32.39% | 49.67% | 56.77% |
| 2020-2023 | 23.50% | 52.00% | 24.11% | 81.57% |
| **ex-2020** | **25.70%** | **52.00%** | **28.35%** | 81.57% |

| year | strategy | TQQQ |
|---:|---:|---:|
| 2016 | +10.0% | +19.9% |
| 2017 | +48.9% | +114.5% |
| 2018 | -0.1% | -20.8% |
| 2019 | +57.6% | +148.2% |
| 2020 | +76.9% | +104.1% |
| 2021 | +42.6% | +81.1% |
| 2022 | -47.3% | -79.4% |
| 2023 | +83.0% | +192.0% |

The strategy lags TQQQ in every up year and loses less in 2018 and 2022. That
is the expected profile of a 53% TQQQ book, not evidence of a quarter-end flow.
The ex-2020 CAGR (25.70%) is below the TQQQ ex-2020 bar (28.35%).

## 8. Correlations to the nine current winners

Daily-return Pearson correlation, development window only:

| winner | correlation |
|---|---:|
| ratio-froth | 0.607 |
| vol-scaled-crash-stop | 0.778 |
| relative-value-tqqq | 0.873 |
| fomc-opex-window | 0.672 |
| family-session-timing | 0.717 |
| family-short-reversal | 0.871 |
| family-rebalance-flow | 0.854 |
| family-intraday-microstructure-day | 0.592 |
| family-ml-microstructure | 0.849 |

Range **0.592-0.873**, mean **0.757**. This is TQQQ beta with a 50% risk
budget; it is not a diversifier and not an independent clock.

## 9. Causality and no look-ahead

- The quarter-end window is known from the calendar at the prior close. The
  target for the first window session is set at the previous close and filled
  at the next open.
- No quarter-return conditioning, no same-day information, no actual
  rebalancing-flow data.
- No warmup indicator is needed; the first decision is 2016-01-04.
- Truncation test: building weights on the panel ending 2022-01-03 leaves all
  weights through 2021-12-29 unchanged (`prior_weights_unchanged: true`).
- No 2024+ bar is loaded in `strategy.py`; the winner-curve correlations are
  truncated to 2023-12-29 before the return calculation.

## 10. Kill criteria and result

| criterion | result | pass? |
|---|---|---|
| 10 bp CAGR <= 36.72% | 24.72% | **fail** |
| shifted +5 placebo beats the real window | 30.07% vs 25.86% | **fail** |
| window-only CAGR < 5% | 4.29% | **fail** |
| window mean t < 1.0 | t = 0.84 | **fail** |
| real below constant exposure | 25.86% vs 25.54% | pass (barely above) |
| drop best quarter below constant | yes | **fail** |

Five of six criteria fail. The verdict is **negative**. The only criterion
that passes is the constant-exposure comparison, and the margin is +0.32 pp
CAGR with a 1.94 pp DD improvement — not a meaningful edge.

## 11. Limitations

1. **The window is not special.** The +5-session shift is better on CAGR, DD and
   Sharpe. The real window's mean is only 5.0 bp above the outside mean, with
   t = 0.84. The Q3 and Q4 windows are negative.
2. **The window-only strategy is dead.** 4.29% CAGR at 1 bp, 2.79% at 10 bp,
   below the repo's 5% viability floor. The family only survives as a 50% base
   allocation, which is a generic risk profile.
3. **The constant-exposure control is almost identical.** 25.54% vs 25.86% CAGR;
   the tilt adds 0.32 pp. A reader who wants a 50/50 TQQQ/BIL book can get the
   same result without the quarter-end trades.
4. **The conditional momentum alternative is not the claim.** De-risking the
   first two sessions after an up quarter earns 35.01% but has an 81.70% DD and
   is a momentum condition, not an unconditional flow.
5. **The 2+2 definition is a choice.** The grid shows last-2-only (26.01%) and
   first-2-only (24.03%) are similar to the combined window; no component is
   significant.
6. **One cycle.** 32 quarter windows, 128 sessions. The sample is small and the
   quarter-level t-stats are all below 2.1.

## 12. Final verdict

**The family is rejected.** The deliverable is:

- 25.86% CAGR / 53.81% DD / 0.82 Sharpe at 1 bp;
- 24.72% CAGR / 54.16% DD / 0.80 Sharpe at 10 bp;
- 10.9 pp below the CAGR bar;
- shifted +5-session placebo 30.07% / 61.01% / 0.92, better than the real window;
- constant 53.2% TQQQ control 25.54% / 55.75% / 0.82, almost identical;
- window-only 4.29%, below the 5% viability floor;
- random 4-session placebo p = 0.418;
- exact pre-cut weights (causality truncation test passes).

The honest one-line description: *a 50/50 TQQQ/BIL book that doubles TQQQ
exposure for the last two sessions of a quarter and the first two of the next;
the quarter-end window is not distinguishable from a window one week later, and
the tilt adds almost nothing over constant exposure.* It is a valid negative
result, not a winner.
