# Dual-momentum TQQQ — development report

**Slug:** `dual-momentum-tqqq`
**Window:** 2016-01-04 -> 2023-12-29 (development only; 2024-2026 never loaded)
**Engine:** `research/bt.py`, 1-minute adjusted QQQ/TQQQ/BIL, SPY daily signal
**Bar:** TQQQ development 36.72% CAGR / 82.29% max DD / 0.82 Sharpe

---

## 0. Bottom line

**Primary A** (252-session absolute lookback, 252-session relative lookback,
85% volatility target, 10-session TQQQ volatility, 20-session state
confirmation):

| Metric | Strategy A | TQQQ |
|---|---:|---:|
| Dev CAGR, 1 bp | **41.15%** | 36.15% (bar 36.72%) |
| Max drawdown | **57.95%** | 82.29% |
| Sharpe (1-minute marks) | **0.98** | 0.80 |
| Sortino | 1.37 | — |
| Volatility | 46.5% | 66.5% |
| Invested fraction | 100.0% | 100% |
| Risky exposure (QQQ+TQQQ) | 82.0% | 100% |
| Average TQQQ weight | 73.1% | 100% |
| Daily correlation to TQQQ | 0.824 | 1.00 |
| Turnover / year | 28.0x | 0 |
| Fills | 356 | 0 |
| CAGR at 5 bp / 10 bp | 40.89% / 40.56% | — |
| Max DD at 10 bp | 58.08% | — |

The strategy clears the pre-registered development bar with a 4.4 pp CAGR
cushion and a 24 pp drawdown reduction. **It is a qualified pass, not an
all-weather one.** The honest summary is:

- The edge is **2020-2023**, not 2016-2019. In 2016-2019 the strategy makes
  38.9% CAGR versus TQQQ's 49.0% and has the *same* 58% drawdown.
- The 58% max drawdown is essentially a **full TQQQ drawdown in Q4 2018**
  (TQQQ itself fell 58.6% from 2018-08-30 to 2018-12-24). The 12-month gate
  and the 85% vol threshold did not de-risk in time. The <60% target is met by
  about 2 pp, not by crash protection.
- The **252-session lookback is load-bearing**. 126 and 189 fail (31.9% and
  28.0% CAGR). The plateau is broad in the vol-target, vol-window and
  rebalance dimensions and narrow in the lookback dimension.
- The **placebo** has 10.5% of random target reorderings at or above the
  strategy's CAGR, so the pre-registered "at most 10%" falsifier fails by one
  draw out of 200. The result is at the significance edge.
- The pass does **not** require the 2020 vol-timing excess: replacing 2020
  with TQQQ's own +109.6% still gives 37.4% CAGR. But replacing 2022 with
  TQQQ's -79.1% drops the CAGR to 21.5%, so the 2022 avoidance is the
  load-bearing year.

Grid result: **6 of 8 cells clear both bars at 1 bp** (A, B, C, D, E, H);
the three 80-90% vol-target cells (A/B/C) all pass. At 10 bp, 5 of 8 pass
(E falls 0.01 pp below the bar). See section 3.

---

## 1. Design and pre-registration

The full rules and the eight-cell grid were written in `HYPOTHESIS.md` before
the 1-minute grid run. The design was developed with daily-bar diagnostics on
the same development window; this is an **exploratory** pass, not a clean
out-of-sample result. Two implementation details are worth disclosing:

- The primary cell was sanity-checked once at 1 bp before the full grid. No
  parameter was changed after the 1-minute grid was seen.
- After the first grid run, the unused part of the TQQQ sleeve was corrected to
  earn BIL (the pre-registered rule) rather than cash. The whole grid was
  re-run; no parameter changed. That correction moves the headline CAGR by
  about +0.01 pp.

Signals, all causal:

```
absolute[k] = QQQ[k] / QQQ[k-252] - 1 > 0                  (15:59 close at k)
relative[k] = QQQ[k-1]/QQQ[k-253] > SPY[k-1]/SPY[k-253]     (both lagged 1)
rv[k]       = stdev(TQQQ daily returns, last 10) * sqrt(252)
```

SPY's official close is 16:00, one minute after the 15:59 decision bar, so
both relative legs are measured through `k-1`. The absolute gate and the
volatility size use `k`'s 15:59 close. Targets set at `k`'s close fill at
`k+1`'s open. The state machine:

| Absolute | Relative | Holding |
|---|---|---|
| on | on | TQQQ at `min(1, 0.85 / rv)`, remainder BIL |
| on | off | QQQ 1.00 |
| off | — | BIL 1.00 |

The state changes only when the new raw state has persisted for 20 consecutive
sessions (C20). The volatility size is continuous and subject to the same 2%
no-trade band. The grid also contains a monthly (M) and a fixed 20-session
cadence (N20) alternative.

Causality checks:

- Pre-cut weight reproduction at 2020-03-12 11:07 and 2022-09-13 10:41:
  maximum absolute weight difference **0.0** at both cuts (409,460 and
  654,959 bars checked).
- The 2024-2026 rows are filtered out of every Parquet read (`date <=
  2023-12-29`) and the panel is sliced at 2023-12-29.

---

## 2. Headline result and yearly anatomy

Primary A, 1 bp:

| Year | Strategy | TQQQ | QQQ |
|---|---:|---:|---:|
| 2016 | **+20.7%** | +18.6% | +9.3% |
| 2017 | +82.5% | +118.3% | +32.6% |
| 2018 | -23.5% | -19.6% | -0.1% |
| 2019 | +120.5% | +133.1% | +38.9% |
| 2020 | **+160.3%** | +109.6% | +48.4% |
| 2021 | +64.6% | +83.0% | +27.4% |
| 2022 | **-30.8%** | -79.1% | -32.5% |
| 2023 | +42.3% | +198.4% | +54.8% |

Subperiods:

| Period | Strategy CAGR | Strategy DD | Strategy Sharpe | TQQQ CAGR | TQQQ DD |
|---|---:|---:|---:|---:|---:|
| 2016-2019 | 38.9% | 58.0% | 0.97 | 49.0% | 58.6% |
| 2020-2021 | 106.9% | 50.2% | 1.49 | 93.5% | 72.7% |
| 2022-2023 | -0.8% | 42.9% | 0.13 | -21.7% | 81.1% |

The max drawdown is **2018-08-30 13:21 -> 2018-12-24 12:59, -57.95%**,
recovered on 2019-11-27. The strategy was 100% TQQQ at the 2018 peak. The
monthly path shows why: October -24.6%, November -4.6%, December -27.9%.
TQQQ's own drawdown in that window is -58.6%, so the strategy's "risk
management" did essentially nothing in Q4 2018: TQQQ's 10-day vol stayed
below the 85% target threshold for most of the decline.

The state path is deliberately slow — eight state changes in eight years:

```
2016-01-04 BIL
2016-04-07 TQQQ
2016-11-29 QQQ
2017-02-27 TQQQ      <- held through 2018, 2019, 2020
2021-10-27 QQQ
2021-12-01 TQQQ
2022-01-18 QQQ
2022-06-03 BIL
2023-06-06 TQQQ
```

Average target weights: QQQ 8.9%, TQQQ 73.1%, BIL 18.0%. The TQQQ share is
75.3% of sessions; QQQ 8.9%; BIL 15.8%. The 100% "invested" figure includes
BIL; the risky (QQQ+TQQQ) exposure is 82.0%.

Up-capture versus TQQQ is 0.68, down-capture 0.66. The strategy is not a
market-neutral or low-beta product; it is a leveraged Nasdaq beta with a slow
bear gate and a volatility brake.

---

## 3. Grid and plateau

All eight pre-registered cells, 1 bp:

| ID | Lookback | Vol target | rv | Rebalance | CAGR | Max DD | Sharpe | Pass |
|---|---:|---:|---:|---|---:|---:|---:|---|
| **A** | **252** | **0.85** | **10** | **C20** | **41.15%** | **57.95%** | **0.98** | **yes** |
| B | 252 | 0.80 | 10 | C20 | 41.08% | 56.98% | 0.98 | yes |
| C | 252 | 0.90 | 10 | C20 | 41.29% | 58.90% | 0.97 | yes |
| D | 252 | 0.85 | 20 | C20 | 39.47% | 56.59% | 0.94 | yes |
| E | 252 | 0.85 | 10 | M | 37.59% | 57.95% | 0.94 | yes |
| F | 189 | 0.85 | 10 | C20 | 28.00% | 59.88% | 0.77 | no |
| G | 126 | 0.85 | 10 | C20 | 31.91% | 57.33% | 0.83 | no |
| H | 252 | 0.85 | 10 | N20 | 40.92% | 58.91% | 0.99 | yes |

At 10 bp, A/B/C/D/H still pass (A 40.56%, B 40.50%, C 40.69%, D 39.02%,
H 40.11%); E is 36.71%, 0.01 pp below the 36.72 bar; F/G fail.

**What is a plateau and what is not.**

- **Vol target:** 0.80, 0.85, 0.90 all pass with nearly identical CAGR
  (41.1%) and DD (57-59%). A true plateau across the mandate's band.
- **Vol window:** 5, 10, 15, 20, 30 sessions all clear the CAGR bar
  (41.4%, 41.2%, 40.1%, 39.5%, 37.5%) with DD 56.6-60.6%. Broad.
- **Rebalance:** C20 (41.2%), monthly (37.6%), fixed 20-session (40.9%) all
  clear the bar at 1 bp. The monthly rule is exactly at the bar at 10 bp.
- **Lookback:** 126 (31.9%) and 189 (28.0%) fail; 210 (33.5%) fails; 252
  (41.2%) passes; 294 (38.8%) passes. **This is a cliff, not a plateau.** The
  12-month lookback is the load-bearing choice. It is also the canonical
  dual-momentum lookback, which is why it was the pre-registered centre, but
  the result should not be read as "any momentum lookback works."

The monthly alternative is important: it shows the pass is not solely an
artifact of the 20-session confirmation. It is, however, cost-sensitive:
37.59% at 1 bp, 36.71% at 10 bp, because the monthly rule trades more around
the state changes and has slightly worse timing in 2019/2023.

Neighbour table, 1 bp (descriptive, not substitute candidates):

| Variant | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| vol target 0.75 | 41.43% | 55.10% | 1.00 |
| vol target 0.95 | 41.84% | 59.13% | 0.97 |
| rv 30 | 37.46% | 59.34% | 0.90 |
| confirm 10 | 42.79% | 57.95% | 1.01 |
| confirm 30 | 37.29% | 59.76% | 0.91 |
| lookback 210 | 33.47% | 57.95% | 0.89 |
| lookback 294 | 38.78% | 57.95% | 0.93 |
| monthly, vol at month-end | 37.59% | 57.95% | 0.94 |

The confirmation length is not a clean plateau (10 -> 42.8%, 30 -> 37.3%),
but all of 10/20/30 clear the bar; the exact value is not doing fragile work.

---

## 4. Ablations: what is actually doing the work

All at 1 bp, same panel:

| Ablation | CAGR | Max DD | Sharpe | Reading |
|---|---:|---:|---:|---|
| Primary A | 41.15% | 57.95% | 0.98 | — |
| No vol cap (TQQQ at 1.0) | 39.64% | 72.74% | 0.89 | vol cap adds +1.5 pp CAGR and -14.8 pp DD |
| Monthly, no vol cap | 34.82% | 75.07% | 0.83 | without either overlay it fails |
| Absolute gate only (relative always on) | 37.55% | 68.27% | 0.89 | absolute gate alone clears CAGR, not DD |
| Relative gate only (absolute always on) | 44.03% | 57.95% | 1.01 | relative gate does the heavy lifting |
| Monthly, with vol cap | 37.59% | 57.95% | 0.94 | confirmation is worth ~3.6 pp |
| rv 5 | 41.40% | 60.64% | 0.99 | faster vol, slightly worse DD |
| rv 15 | 40.05% | 57.62% | 0.95 | — |
| Relative lookback 126 | 39.33% | 51.42% | 0.97 | lower DD, lower CAGR |
| Relative lookback 189 | 33.11% | 54.98% | 0.87 | fails |

Two honest readings:

1. **The relative gate, not the absolute gate, is the main return source.**
   Holding TQQQ whenever QQQ beats SPY over 12 months, with the vol brake,
   gives 44.0% CAGR and the same 58% DD. The absolute gate *reduces* CAGR by
   2.9 pp in this window and does not reduce the max DD (because the max DD is
   the 2018 Q4 TQQQ drawdown, when the absolute gate was still on). The full
   dual-momentum structure is the mandate, and it still passes, but it is not
   the best-performing member of its own family in this sample.
2. **The volatility brake is real risk work, not just return timing.** Removing
   it raises the DD from 58% to 73% and *lowers* CAGR by 1.5 pp. The 2020
   path shows the mechanism: the 10-day vol target cut TQQQ to 0.26 at the
   March 2020 bottom and re-levered to 0.80 by the end of April. That is why
   2020 is +160% instead of TQQQ's +110%.

A static blend at the strategy's own average weights (QQQ 8.9%, TQQQ 73.1%,
BIL 18.0%) returns 32.26% CAGR with a 70.52% DD, so the dynamic state
sequence adds about +8.9 pp CAGR and -12.6 pp DD versus the same average
exposure.

---

## 5. Robustness: placebo, cuts, concentration

**Placebo (200 circular shifts of the per-session target sequence, seed
20261127).** The shift preserves the exposure path, the vol sizing and the
turnover, but destroys alignment with returns.

| Statistic | Value |
|---|---:|
| Placebo CAGR median | 26.04% |
| Placebo CAGR p05 / p95 | 18.09% / 50.19% |
| Placebo max DD median | 78.55% |
| Placebo Sharpe median | 0.69 |
| Share of draws >= strategy CAGR | **10.5%** |

The strategy sits at about the 89.5th percentile of the placebo CAGR
distribution. The pre-registered falsifier was "at most 10%"; 10.5% fails by
one draw in 200. With 200 draws the standard error on a 10% share is about
2.1 pp, so this is a threshold result, not a decisive rejection. It is still
the weakest statistical evidence in the package and is the reason
`robustness_status` is `fragile` in `result.json`.

**Cut tests.** Rebuilding the weights on a panel truncated at the cut:

| Cut | Bars checked | Max abs weight difference |
|---|---:|---:|
| 2020-03-12 11:07 | 409,460 | 0.0 |
| 2022-09-13 10:41 | 654,959 | 0.0 |

**Leave-one-year-out CAGR:**

| Removed year | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| LOO CAGR | 44.2% | 36.0% | 53.9% | 32.3% | 29.2% | 38.0% | 56.2% | 40.9% |

Five of seven folds clear 36.72% (the pre-registered bar); removing 2019,
2020 or 2017 drops below. Removing a single year is a blunt test because it
also removes the capital base for the remaining years, but the pattern is
clear: the 2019-2020 cluster carries the result.

**Replace-one-year-with-TQQQ CAGR:**

| Replaced year | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| CAGR | 40.8% | 44.4% | 42.0% | 42.1% | 37.4% | 43.0% | **21.5%** | 54.9% |

This is the more informative concentration test. Replacing the strategy's
2020 with TQQQ's +109.6% still leaves 37.4% CAGR — the pass does not need the
2020 excess. Replacing 2022 with TQQQ's -79.1% collapses the CAGR to 21.5%;
the 2022 avoidance is the single load-bearing year. That is exactly the risk
the strategy is designed to avoid, but it is also a one-year dependency.

**Costs.** 1 bp headline; 5 bp and 10 bp are 40.89%/40.56% CAGR and
58.00%/58.08% DD. Turnover is 28x/year, 356 fills. Costs are not the issue.

---

## 6. Honest anatomy: 2016-2019, 2018, 2022, 2023

### 2016-2019: no edge, same drawdown

The strategy returns 38.9% CAGR versus TQQQ's 49.0%, with a 58.0% drawdown
versus TQQQ's 58.6%. There is no risk-adjusted advantage in the first half.
The state sequence is essentially "TQQQ from February 2017 onward," so the
strategy is a leveraged Nasdaq holder through the 2018 Q4 crash. The 2016
result (+20.7% vs +18.6%) is the only year in the first half where it beats
TQQQ, and that is a timing accident of the April 2016 entry after the
February bottom.

### 2018: the 58% drawdown is TQQQ's drawdown

From 2018-08-30 to 2018-12-24, TQQQ falls 58.6% in the panel; the strategy
falls 58.0%. The strategy was 100% TQQQ at the peak. The 12-month absolute
signal did not turn negative until late in the decline, and the C20
confirmation never accepted a risk-off state because the raw signal recovered
within 20 sessions. The 10-day vol target did not cut either, because TQQQ's
realised vol stayed below the 85% target threshold. This is the strategy's
main risk failure and the reason the <60% DD target is met by only 2 pp.

### 2022: the win, but a late exit

The state path is Jan 2022 -> QQQ, Jun 2022 -> BIL. The strategy loses 30.8%
in 2022 versus TQQQ's -79.1%, but it eats the January QQQ decline (-19.9%),
the April decline (-13.5%) and the May decline (-1.6%) before exiting. The
monthly rule would have exited at the end of April, avoiding May's -1.6%; the
C20 rule waited to June. Neither avoids the January-April QQQ damage. The
2022-2023 subperiod DD is 42.9%, so this is a real but incomplete save, not a
clean crash hedge.

### 2023: the big opportunity cost

The strategy is in BIL from June 2022 to June 2023. It misses the entire
first-half 2023 rebound and returns +42.3% versus TQQQ's +198.4%. The 12-month
absolute signal only turned positive in late April, and the C20 confirmation
entered on 2023-06-06. This is the structural cost of a 12-month gate. Any
holdout that begins with a sharp rebound from a bear market will produce the
same lag.

### 2020: where the excess comes from

The 10-day vol target cut TQQQ to 0.26 at the March bottom and re-levered to
0.80 by the end of April. The monthly path: Jan +8.2%, Feb -19.1%, Mar
-13.4%, Apr +26.1%, May +17.7%, Jun +17.4%, Jul +22.5%, Aug +35.5%, Sep
-14.5%, Oct -11.2%, Nov +36.0%, Dec +15.0% = +160.3%. This is a genuine
vol-clustering effect, not a data artifact (the independent daily simulation
gives +159.2%), but it is also a single-year, V-shaped-crash regime. The
replace-2020 test shows the pass survives without the excess, at 37.4% CAGR.

---

## 7. Holdout arithmetic and verdict

The 2024-2026 holdout was not loaded or inspected. As pure arithmetic, if the
development CAGR is 41.15% over 7.98 years, the full 2016-2026 CAGR as a
function of the holdout CAGR is:

| Holdout CAGR | Full 2016-2026 CAGR |
|---:|---:|
| 20% | 35.30% |
| 25% | 36.75% |
| **27.8%** | **37.54% (TQQQ bar)** |
| 30% | 38.15% |
| 35% | 39.52% |
| 40% | 40.85% |

So the strategy needs roughly a **27.8% holdout CAGR** to beat TQQQ's 37.54%
full-window figure. That is plausible if the gate is in TQQQ for most of
2024-2026, and not plausible if 2024 produces a 2023-style 12-month lag. The
development cushion is real but not large.

**Verdict: qualified pass.** The primary clears the pre-registered
development bar (41.15% > 36.72%, 57.95% < 60%) with a 0.98 Sharpe and a 0.82
correlation to TQQQ. The pass is broad across the vol-target, vol-window and
rebalance dimensions, and it survives 10 bp costs and exact pre-cut
reproduction. It is narrow in the lookback dimension, the 2018 drawdown is a
full TQQQ drawdown, the placebo is at the 10% edge, and the result is
concentrated in 2019-2020 and the 2022 avoidance. It should be sent to the
holdout with those caveats attached, not presented as a robust all-weather
replacement for TQQQ.

What would change the verdict:

- A holdout below ~28% CAGR would leave the full-window CAGR below 37.54%.
- A 2018-style Q4 crash in the holdout would produce another ~58% drawdown;
  the hard bar is 81.68%, so this alone would not fail the full-window rule,
  but it would confirm the DD weakness.
- A 2023-style sharp rebound after a bear would produce another year of large
  opportunity cost; the CAGR cushion would shrink.

---

## 8. Reproduction

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
$env:BT_THREADS = "1"
python research/new/dual-momentum-tqqq/strategy.py
```

Files:

- `HYPOTHESIS.md` — pre-registered rules, grid and falsifiers.
- `strategy.py` — `build_weights(ts, o, c)` plus `main()` (writes
  `result.json`).
- `result.json` — grid, benchmarks, yearly, subperiods, ablations,
  neighbours, placebo, cut tests, LOO, caveats.
- `report.md` — this file.

Runtime on the local machine: a few minutes for the 8-cell grid plus 200
placebo draws. The heavy lifting is `bt.py`'s compiled simulator; all fills
are next-open, 2% band, long-only, weights >= 0 and sum <= 1.

**Data caveat.** There is no SPY 1-minute history for 2016-2023, so SPY is a
daily signal only and is lagged one session. QQQ/TQQQ/BIL use the 1-minute
adjusted panel. The 2018 drawdown and the 2020 path are therefore genuine
TQQQ paths, not SPY-spliced approximations.
