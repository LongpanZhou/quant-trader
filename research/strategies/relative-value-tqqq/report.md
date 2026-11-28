# relative-value-tqqq — development report

**Window:** 2016-01-04 .. 2023-12-29 (1-minute marks, next-open fills, 2% band,
$100k start). 2024-2026 was never loaded.

**Verdict: numeric pass, with qualifications.** The pre-registered primary earns
**43.65% CAGR / 54.65% max DD / 1.01 Sharpe** at 1 bp, versus the TQQQ bar of
36.72% / 82.29% / 0.82. It beats the CAGR bar by 6.9 pp and cuts max drawdown by
27.6 pp. The eight-cell pre-registered grid is uniformly above the bar
(41.5-44.4% CAGR, 53.8-62.9% DD).

The qualification is important: **this is not a market-neutral relative-value
premium.** The TQQQ/QQQ ratio momentum is 99.7% explained by
`2 x QQQ trend - 3 x variance change` (measured below: b1 = 1.996, b2 = -3.225,
R2 = 0.9974). The strategy's return is TQQQ beta harvested in favourable
leverage-cycle states; its distinctive contribution is drawdown reduction. A
plain QQQ 100-day momentum gate with the same vol scale earns the same CAGR
(44.52%) but with 70.87% DD. The ratio signal is what cuts the left tail.

---

## 1. Headline results

| cost | CAGR | max DD | Sharpe | Sortino | vol | equity exposure | avg TQQQ weight | fills | turnover* | Calmar |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **1 bp** | **43.65%** | **54.65%** | **1.01** | 1.42 | 47.2% | 100.0% | 0.740 | 192 | 268x | 0.80 |
| 5 bp | 43.03% | 54.76% | 1.00 | 1.41 | 47.2% | 100.0% | 0.740 | 192 | 262x | 0.79 |
| 10 bp | 42.27% | 54.91% | 0.99 | 1.39 | 47.2% | 100.0% | 0.740 | 190 | 253x | 0.77 |

\* turnover is cumulative traded notional divided by the $100k starting equity;
the book grows 18x (mean equity 5.76x the start), so this is about 47x average
equity over eight years (~5.8x/year). The low fill count (192) is why 10 bp
costs only 1.4 pp of CAGR.

Benchmarks on the same 1-minute panel:

| | CAGR | max DD | Sharpe |
|---|---:|---:|---:|
| TQQQ (computed) | 36.15% | 82.29% | 0.80 |
| TQQQ (stated bar) | 36.72% | 82.29% | 0.82 |
| QQQ | 18.91% | 37.30% | 0.90 |
| **Strategy, 1 bp** | **43.65%** | **54.65%** | **1.01** |

The small difference between the computed and stated TQQQ CAGR (0.57 pp) is a
data-source/marking difference; the drawdown matches to the basis point. The
strategy is above both.

## 2. Yearly returns

| year | strategy | TQQQ | QQQ |
|---:|---:|---:|---:|
| 2016 | 18.7% | 18.6% | 9.3% |
| 2017 | 118.3% | 118.3% | 32.6% |
| 2018 | -9.3% | -19.6% | -0.1% |
| 2019 | 88.2% | 133.1% | 38.9% |
| 2020 | 72.9% | 109.6% | 48.4% |
| 2021 | 83.4% | 83.0% | 27.4% |
| 2022 | **-45.9%** | -79.1% | -32.5% |
| 2023 | 136.8% | 198.4% | 54.8% |

The shape is what the mechanism predicts: full TQQQ in 2017/2021, partial in
2019/2020/2023, and a large de-risk in 2022 (average TQQQ weight 5.6%). But
2022 is also the weak spot — see §6.

## 3. Is the edge just TQQQ beta?

| diagnostic | value |
|---|---:|
| correlation to TQQQ (daily) | 0.890 |
| beta to TQQQ (daily) | 0.630 |
| correlation to QQQ (daily) | 0.888 |
| beta to QQQ (daily) | 1.869 |
| up-capture of TQQQ days | 0.742 |
| down-capture of TQQQ days | 0.719 |
| average TQQQ weight | 0.740 |
| average gross leverage (TQQQ = 3x) | 2.48x |
| sessions with TQQQ > 0 | 1,509 / 2,012 (75.0%) |
| sessions with 100% TQQQ | 1,439 / 2,012 (71.5%) |

A static blend at the strategy's **own average weights** (25.98% QQQ / 74.02%
TQQQ, rebalanced by the same 2% band) earns:

| | CAGR | max DD | Sharpe |
|---|---:|---:|---:|
| static blend, same average weights | 33.85% | 74.40% | 0.81 |
| timed strategy | **43.65%** | **54.65%** | **1.01** |

So the answer is **no, not constant TQQQ beta**: the timing adds +9.8 pp CAGR and
removes 19.8 pp of drawdown versus the same average exposure. But it is still
**beta timing**, not a market-neutral edge. The beta is 0.63, the correlation
0.89, and the return comes from being long TQQQ in the good states.

The signal decomposition makes the point explicitly. Regressing the 100-session
log ratio momentum on QQQ's 100-session momentum and the change in cumulative
squared daily returns:

```
rm100 = -0.016 + 1.996 * qm100 - 3.225 * dvar100,   R2 = 0.9974
```

The identity predicts coefficients of 2 and -3. The ratio momentum is the
leverage-cycle accounting identity, not an independent mispricing. Its value is
that it combines trend and variance into one causal state variable.

## 4. Pre-registered grid and plateau

All eight cells use `mom_min = -0.10`, `v_lo = v_hi - 0.10`, continuous vol
scaling and the QQQ fallback. 1 bp costs.

| n | vol band | CAGR | max DD | Sharpe | avg TQQQ | fills |
|---:|---|---:|---:|---:|---:|---:|
| 60 | 0.25-0.35 | 43.78% | 59.10% | 1.02 | 0.746 | 389 |
| 60 | 0.35-0.45 | 44.36% | 59.92% | 1.00 | 0.781 | 139 |
| 80 | 0.25-0.35 | 41.99% | 58.82% | 0.99 | 0.732 | 361 |
| 80 | 0.35-0.45 | 41.71% | 61.40% | 0.95 | 0.772 | 115 |
| 100 | 0.25-0.35 | 43.96% | 53.76% | 1.04 | 0.712 | 332 |
| **100** | **0.30-0.40** | **43.65%** | **54.65%** | **1.01** | **0.740** | **192** |
| 100 | 0.35-0.45 | 41.45% | 53.95% | 0.96 | 0.749 | 113 |
| 120 | 0.30-0.40 | 44.15% | 62.85% | 1.01 | 0.740 | 224 |

Every cell passes the bar. The CAGR range is 2.9 pp wide and the DD range is
9.1 pp; there is no knife-edge cell in the pre-registered grid. The 100-session
horizon has the best drawdown; n=120 gives most of it back. The high vol band
costs up to 2.5 pp of CAGR at n=100 but does not improve DD there.

**Finer neighbour probe (not part of the pre-registered grid):**

| n | vol band | CAGR | max DD | Sharpe |
|---:|---|---:|---:|---:|
| 90 | 0.30-0.40 | 38.58% | 59.33% | 0.92 |
| 110 | 0.30-0.40 | **35.67%** | 57.91% | 0.89 |
| 100 | 0.28-0.38 | 44.38% | 54.61% | 1.03 |
| 100 | 0.32-0.42 | 42.53% | 54.39% | 0.98 |

The ±10-session probe is **not monotone**: n=90 and especially n=110 are weaker,
and n=110 is below the CAGR bar. The primary sits on a local ridge. The vol
neighbours are smooth (42.5-44.4% CAGR, 54.4-54.6% DD). This is the honest
picture: the vol dimension is a plateau; the exact ratio lookback is path-
sensitive because a few sessions change which side of a 2022 rally the book is
on. The drawdown reduction survives all four probes.

## 5. Ablations: which component does the work?

1 bp, same panel and costs.

| variant | CAGR | max DD | Sharpe | avg TQQQ |
|---|---:|---:|---:|---:|
| **primary (ratio mom + continuous vol)** | **43.65%** | **54.65%** | **1.01** | 0.740 |
| no vol filter | 37.71% | 62.49% | 0.89 | 0.737 |
| binary vol filter | 41.04% | 53.06% | 0.95 | 0.740 |
| `mom_min = 0` | 37.90% | 51.64% | 0.95 | 0.688 |
| QQQ 100d momentum instead of ratio | 44.52% | 70.87% | 0.96 | 0.884 |
| QQQ momentum, no vol | 39.24% | 72.65% | 0.85 | 0.934 |

Two clear conclusions:

* The **vol filter is the CAGR contributor** on the ratio signal (+5.9 pp) and
  also improves DD (-7.8 pp). It is not cosmetic.
* The **ratio signal is the drawdown contributor**. Replacing it with plain QQQ
  momentum keeps the CAGR (44.52%) but gives back 16.2 pp of drawdown. The
  ratio's `-3 x variance` term exits earlier when volatility rises even while
  the price trend is still up.

## 6. Robustness

### Cut tests (1 bp)

| window | strategy CAGR / DD / Sharpe | TQQQ CAGR / DD / Sharpe |
|---|---|---:|
| 2016-2019 | 45.28% / 46.57% / 1.15 | 48.98% / 58.62% / 1.05 |
| 2020-2023 | 41.16% / 54.65% / 0.93 | 23.66% / 82.29% / 0.67 |
| 2016-2021 | 55.49% / 46.57% / 1.18 | 63.21% / 72.74% / 1.10 |
| 2022-2023 | 12.40% / 51.61% / 0.49 | -21.72% / 81.10% / 0.05 |

In the first half the strategy roughly matches TQQQ's CAGR with a much smaller
drawdown; the full-window CAGR edge is created in 2020-2023, mainly by 2022.

### Leave-one-year-out

Compounding the other seven years (7-year CAGR):

| removed year | 7-year CAGR |
|---|---:|
| 2016 | 47.43% |
| 2017 | **35.14%** |
| 2018 | 53.21% |
| 2019 | 38.04% |
| 2020 | 39.72% |
| 2021 | 38.54% |
| 2022 | 64.95% |
| 2023 | **33.58%** |

Removing either 2017 or 2023 pushes the CAGR below the 36.72% bar. The strategy
is not a one-year wonder — six of the eight leave-one-out cases are above the
bar — but it is a long-biased book whose margin comes from two very strong bull
years. This should be read together with the 2016-2019 cut, where it slightly
lags TQQQ on CAGR.

### Placebo: block-permuted weight path

The daily TQQQ-weight path was circularly block-shuffled in 20-session blocks,
preserving the weight histogram and local run lengths, then re-simulated on the
same 1-minute prices (10 seeds).

| | median | min | max |
|---|---:|---:|---:|
| CAGR | 35.93% | 29.15% | 46.06% |
| max DD | 73.78% | 62.96% | 84.51% |
| Sharpe | 0.82 | 0.73 | 0.97 |

The strategy (43.65% / 54.65%) is above the placebo median on CAGR and better
than **every** placebo run on drawdown. The CAGR is inside the placebo's upper
tail (one seed reaches 46.1%), so the return edge alone is not statistically
distinct from a lucky arrangement of the same exposure. The drawdown edge is
robust: no shuffled path gets below 62.96% DD, 8.3 pp worse than the strategy.

### Signal delay

Delaying the signal by one extra session (using the close of t-2 for session t)
earns 43.35% CAGR / 60.81% DD / 1.00 Sharpe. The result is not dependent on
same-day execution or on a one-day information leak.

### Worst drawdown episode

| | |
|---|---|
| peak | 2021-11-22 10:16 ET |
| trough | 2023-03-13 09:38 ET |
| depth | -54.65% |
| peak-to-trough | 327 sessions (about 15.5 months) |
| recovered | 2023-07-13 15:12 ET |

This is the 2021-2022 bear. The strategy was 99% TQQQ on average in 2021 and
5.6% in 2022, but it entered January 2022 with a full TQQQ book (the ratio
momentum was still positive at the 2021 close and QQQ vol was low). The first
two weeks of January 2022 did most of the damage; the book then moved to QQQ
and still lost with QQQ for the rest of the year. **2022 was worse than simply
holding QQQ** (-45.9% vs -32.5%), even though it was much better than TQQQ
(-79.1%). If 2022 had returned the QQQ return, the full-window CAGR would be
47.5%. The crash filter protects against 3x compounding, not against a 1x bear
market.

## 7. Falsifier checklist

| # | falsifier | outcome |
|---:|---|---|
| 1 | CAGR ≤ 36.72% or DD ≥ 82.29% | **not triggered**: 43.65% / 54.65% |
| 2 | edge dies at 5-10 bp | **not triggered**: 43.03% / 42.27% |
| 3 | static blend matches | **not triggered**: 33.85% / 74.40% |
| 4 | block placebo matches | **partly triggered on CAGR** (placebo max 46.1%), **not on DD** (placebo min 62.96%) |
| 5 | concentrated in one year/cut | **partly**: 2017 and 2023 each carry the margin; 2016-2019 lags TQQQ on CAGR |
| 6 | plain QQQ trend gate is equivalent | **equivalent on CAGR** (44.52%), **not on DD** (70.87%) |

The honest reading: the CAGR pass is real but fragile at the year/parameter
level; the drawdown and Sharpe improvement is the robust part.

## 8. How this differs from existing work

* `research/agents2/ratio-pairs` and `research/strategies/ratio-pairs` use the
  **level** of `log(TQQQ/QQQ)` versus a 200-day mean (froth/discount), a
  `v20/v60` stress ratio, and a capped 40% TQQQ sleeve only after a deep
  discount turns up. They hold QQQ by default and earn 18.96% dev CAGR. This
  strategy uses ratio **momentum** (a 100-session change), an absolute QQQ
  volatility scale, and a full TQQQ sleeve in the favourable state. There is no
  froth threshold, no discount threshold, no stress ratio and no 40% cap.
* `ratio-froth` (the original) is the old 165-day QQQ SMA plus a 4% armed stop
  plus a ratio-level overlay. This file contains **no QQQ moving average, no
  price stop, and no ratio level**. The only trend input is the ratio change.
* `research/strategies/fast-trend-vol`, `cross-asset-momentum`, `vol-of-vol-timing`
  and the other new agents use price trend, cross-asset momentum or vol-of-vol.
  This one is driven by the leveraged-fund ratio, a TQQQ-specific quantity.
* The audit's `ratio-pairs` deep read found that 97.8% of ratio extension is
  QQQ extension plus variance. The decomposition here confirms that at the
  momentum level (R2 = 0.9974). This strategy does not claim otherwise; it uses
  the identity as a risk-state meter.

## 9. Limitations

1. **In-sample design.** A daily-bar screen on the development window chose the
   mechanism family and the grid centre. This is not a clean out-of-sample test.
   The holdout has not been run and must be run once, frozen, by the lead.
2. **Local parameter ridge.** The pre-registered grid is a plateau, but the
   ±10-session probe is not monotone (n=110 = 35.67%). The strategy should not
   be re-tuned on the holdout; if the lead wants a smoother centre, n=60 or
   n=120 are the pre-registered alternatives (43.8-44.4% CAGR, 59-63% DD).
3. **2022 is worse than QQQ.** The filter avoids 3x compounding, not the
   underlying bear market. A future bear with a slow vol rise and a fast price
   fall will hurt before the ratio momentum turns.
4. **Long-biased, always invested.** There is no cash timing; the book is 100%
   QQQ or TQQQ. In a lost decade for the Nasdaq the strategy will lose, just
   less than TQQQ.
5. **The "relative value" label is mechanistic, not a mispricing.** The ratio
   momentum is the accounting identity of a 3x daily-reset fund. The edge is
   risk-state timing, not a market-neutral spread.
6. **Turnover is low but the book grows.** 192 fills over eight years; at 10 bp
   the CAGR is 42.27%, still above the bar.

## 10. Reproduction

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
$env:BT_THREADS = "1"
python research\strategies\relative-value-tqqq\strategy.py
```

`strategy.py` loads the 1-minute QQQ/TQQQ/BIL panel through `research/bt.py`,
warms the signals with pre-2016 Yahoo adjusted daily closes (warmup only),
simulates at 1/5/10 bp with next-open fills and a 2% band, and writes
`result.json` including the grid, neighbours, ablations, placebo, cuts,
yearly returns, correlation, beta and the static-blend attribution.
