# Robustness appendix — `family-tail-hedge-overlay`

All results are development-window only (2016-01-04..2023-12-29), 1-minute
marks, next-open fills, 2% band, 1 bp unless stated. Values are
CAGR / max DD / Sharpe unless the table says otherwise.

## 1. 8-cell plateau

| h | thr = −1.6% | thr = −1.8% | thr = −2.0% | thr = −2.2% |
|---:|---:|---:|---:|---:|
| 0.40 | 63.18 / 52.15 / 1.35 | 73.10 / 44.81 / 1.45 | 81.56 / 51.62 / 1.53 | 79.30 / 57.16 / 1.48 |
| 0.50 | 65.99 / 41.57 / 1.42 | 79.55 / 37.68 / 1.56 | **90.84 / 40.23 / 1.66** | 87.61 / 49.04 / 1.60 |

Fills: 4,651 / 4,241 / 3,869 / 3,649 (h = 0.40 row); 4,749 / 4,345 / 3,985 /
3,741 (h = 0.50 row). All 8 cells beat the 61.56% CAGR target. The h-profile is
monotonic; the primary sits at the 50% hedge cap.

## 2. Hedge-fraction profile (thr = −2.0%)

| h | CAGR | max DD | Sharpe | fills |
|---:|---:|---:|---:|---:|
| 0.10 | 48.24% | 76.23% | 0.96 | 3,005 |
| 0.20 | 60.25% | 69.30% | 1.15 | 3,305 |
| 0.30 | 71.27% | 60.93% | 1.35 | 3,625 |
| 0.40 | 81.56% | 51.62% | 1.53 | 3,869 |
| 0.50 | **90.84%** | **40.23%** | **1.66** | 3,985 |

Cash-control h-profile at the same trigger: 42.01 / 79.45 / 0.88 (h = 0.10),
48.13 / 76.52 / 0.96 (0.20), 53.92 / 73.15 / 1.05 (0.30), 59.76 / 69.63 /
1.14 (0.40), 65.41 / 65.81 / 1.24 (0.50). The inverse hedge dominates cash at
every hedge fraction.

## 3. Confirmation variants (thr = −2.0%, h = 0.50)

| variant | CAGR | max DD | Sharpe | fills |
|---|---:|---:|---:|---:|
| no confirmation (primary) | **90.84%** | **40.23%** | **1.66** | 3,985 |
| TQQQ < 3×QQQ | 67.38% | 62.46% | 1.31 | 3,381 |
| TQQQ < 3×QQQ − 10 bp | 47.90% | 69.99% | 0.98 | 1,335 |
| TQQQ < 3×QQQ − 20 bp | 37.99% | 76.88% | 0.84 | 535 |
| QQQ 3-session return < 0 | 31.48% | 79.80% | 0.78 | 2,123 |
| QQQ above 20-day SMA | 61.32% | 77.97% | 1.09 | 1,909 |
| QQQ 3d < 0 and 20d above SMA | 33.38% | 82.87% | 0.77 | 591 |

Every confirmation filter destroys the edge. The primary uses none.

## 4. Hedge budget (max episodes per calendar year)

| cap | CAGR | max DD | Sharpe | fills |
|---|---:|---:|---:|---:|
| 60 | 59.13% | 70.18% | 1.14 | 2,491 |
| 90 | 82.90% | 59.61% | 1.49 | 3,365 |
| 120 | 85.10% | 43.13% | 1.56 | 3,785 |
| 180 / none | **90.84%** | **40.23%** | **1.66** | 3,985 |

The actual trigger rate is ~93 sessions/year. A 120-episode budget costs 5.7 pp
CAGR and 2.9 pp DD. The primary uses no budget.

## 5. Overnight / exit variants

| variant | CAGR | max DD | Sharpe |
|---|---:|---:|---:|
| always hold overnight, exit next open (primary) | **90.84%** | **40.23%** | **1.66** |
| hold overnight only when close weak | 71.21% | 65.36% | 1.36 |
| exit at 15:59, no overnight | 69.29% | 75.51% | 1.23 |

The overnight leg contributes about 40% of the episode logdiff. Conditional
overnight holding removes the hedge on days that still gap down.

## 6. Synthetic-construction variants

| variant | CAGR | max DD | Sharpe | fills |
|---|---:|---:|---:|---:|
| minute-rebalanced inverse TQQQ (primary) | 90.84% | 40.23% | 1.66 | 3,985 |
| daily-reset, no intraday rebalance | 91.66% | 41.84% | 1.67 | 3,901 |
| inverse QQQ instead of inverse TQQQ | 73.38% | 58.88% | 1.39 | 3,337 |

Borrow/financing sensitivity (primary weights, 1 bp):

| cost | CAGR | max DD | Sharpe |
|---|---:|---:|---:|
| 0.0%/yr | 91.23% | 40.10% | 1.67 |
| 1.5%/yr | 90.84% | 40.23% | 1.66 |
| 5.0%/yr | 89.96% | 40.56% | 1.65 |
| 10.0%/yr | 88.75% | 41.12% | 1.64 |

## 7. Slippage sensitivity (primary)

| cost | CAGR | max DD | Sharpe | ending equity |
|---|---:|---:|---:|---:|
| 0 bp | 94.58% | 38.95% | 1.71 | $20,336,170 |
| 1 bp | 90.84% | 40.23% | 1.66 | $17,413,571 |
| 2 bp | 87.24% | 41.70% | 1.62 | $14,958,161 |
| 5 bp | 76.94% | 46.43% | 1.50 | $9,520,569 |
| 10 bp | 61.35% | 53.57% | 1.29 | $4,559,504 |
| 20 bp | 33.64% | 65.33% | 0.87 | — |

## 8. Subperiods

| period | primary | cash control | ratio-froth |
|---|---:|---:|---:|
| 2016-2019 | 75.76 / 34.75 / 1.68 | 62.95 / 44.50 / 1.39 | 37.07 / 39.11 / 1.13 |
| 2020-2021 | 170.73 / 29.26 / 2.28 | 143.01 / 51.51 / 1.79 | 146.51 / 31.40 / 2.06 |
| 2022-2023 | 58.18 / 38.23 / 1.13 | 15.50 / 62.80 / 0.54 | 45.40 / 24.17 / 1.32 |

## 9. Placebo (250 draws each, seeded 2026)

| placebo | mean CAGR | sd | p95 | max | p(real ≤ placebo) |
|---|---:|---:|---:|---:|---:|
| random sessions, real bar offsets | 23.89% | 12.14 | 45.44% | 74.84% | 0.00 |
| shifted sessions | 23.84% | 12.05 | 44.60% | 76.84% | 0.00 |
| random sessions at 10:30 | 25.78% | 14.45 | 49.13% | 82.95% | 0.00 |

Real CAGR = 90.84%. The real result is above all 750 draws. The same-session
random-bar placebo is not causal (it selects sessions using a future trigger)
and is not used.

## 10. Correlations (daily returns, 2,011 dev sessions)

| strategy | correlation |
|---|---:|
| `ratio-froth` | 0.596 |
| `vol-scaled-crash-stop` | 0.846 |
| `relative-value-tqqq` | 0.692 |
| `fomc-opex-window` | 0.585 |
| `family-session-timing` | 0.602 |
| `family-short-reversal` | 0.601 |
| `family-rebalance-flow` | 0.709 |
| `family-intraday-microstructure-day` | 0.652 |
| `family-ml-microstructure` | 0.673 |

## 11. Episode tail anatomy

740 episodes. Mean TQQQ over the hedge period −0.280%; mean 50/50 portfolio
−0.024%; mean logdiff +0.364%; total logdiff +2.695. Negative episodes 379
(51.2%). Top 1 / 5 / 10 / 20 episode logdiff shares: 10% / 37% / 63% / 109%.

| year | n | mean TQQQ | mean 50/50 | sum logdiff |
|---|---:|---:|---:|---:|
| 2016 | 68 | −0.070% | −0.016% | +0.078 |
| 2017 | 41 | +0.156% | +0.005% | −0.048 |
| 2018 | 100 | −0.689% | +0.000% | +0.800 |
| 2019 | 68 | +0.200% | −0.019% | −0.124 |
| 2020 | 118 | −0.409% | −0.116% | +0.625 |
| 2021 | 96 | +0.114% | −0.011% | −0.062 |
| 2022 | 156 | −0.819% | −0.005% | +1.501 |
| 2023 | 93 | +0.124% | −0.004% | −0.076 |

Worst full-hedge-period TQQQ episodes:

| date | bar | TQQQ | 50/50 | logdiff |
|---|---:|---:|---:|---:|
| 2020-03-11 | 73 | −23.13% | +0.59% | +0.269 |
| 2022-02-23 | 24 | −17.15% | +1.12% | +0.199 |
| 2020-03-13 | 6 | −20.95% | −3.57% | +0.199 |
| 2020-02-27 | 53 | −15.17% | +0.51% | +0.170 |
| 2020-03-20 | 9 | −14.55% | +0.46% | +0.162 |
| 2018-12-04 | 154 | −13.35% | +0.69% | +0.150 |
| 2018-11-19 | 23 | −12.81% | +0.55% | +0.143 |
| 2016-02-05 | 12 | −12.57% | +0.60% | +0.140 |
| 2020-02-21 | 15 | −12.88% | +0.21% | +0.140 |
| 2020-03-06 | 319 | −13.84% | −1.32% | +0.136 |

## 12. Pre-cut causality

Truncate at **2020-03-12 11:07 ET** and rebuild:

- bars compared: **409,376**
- max abs weight diff (inverse column): **0.0**
- max abs synthetic-NAV diff: **0.0**

The synthetic NAV is recursive and uses only bars up to `t`; the 11:07
mid-session cut cannot change any prior target.
