# Intraday momentum — first-hour signal, overnight drift, 165-day SMA regime

**Agent:** 4/10 (`intraday-momentum`)
**Date:** 2026-11-25
**Data:** local adjusted 1-minute QQQ/TQQQ/BIL, 2016-01-04 → 2026-10-23 (regular session only)
**Harness:** `research/bt.py`; long-only; weights set at bar *i*, filled at the open of bar *i+1*; 1 bp per side primary, 5 bp sensitivity; 2% band.

## Verdict

| | 10y (2017-01-03 → 2026-10-23) | 5y (2021-10-25 → 2026-10-23) |
|---|---:|---:|
| **TQQQ buy & hold** | 39.28% CAGR / 81.68% DD / 0.83 Sharpe | 13.47% CAGR / 81.68% DD / 0.53 Sharpe |
| **Daily baseline** (QQQ > 165d SMA → TQQQ, else BIL) | 45.31% / 58.71% / 1.00 | 34.61% / 36.86% / 0.88 |
| **This strategy (1 bp)** | **55.63% / 44.89% / 1.24** | **46.36% / 32.64% / 1.14** |
| This strategy (5 bp) | 43.46% / 46.90% / 1.05 | 35.80% / 34.50% / 0.96 |
| **Pass vs TQQQ?** | **YES** (1 bp and 5 bp) | **YES** (1 bp and 5 bp) |
| **Pass vs daily baseline?** | YES at 1 bp; at 5 bp CAGR 43.46% < 45.31% | YES at 1 bp and 5 bp |

**The honest headline:** *pure* intraday momentum does **not** work here. A first-30m or first-60m signal with a flat overnight position earns 9–13% CAGR on the 10y window, far below TQQQ, because TQQQ's return is overwhelmingly earned overnight (30.2%/yr overnight vs 5.9%/yr intraday). What does pass is a **hybrid**: keep the daily 165-day SMA regime and the overnight drift, and use the first-hour return only to decide whether to hold the *afternoon*. That hybrid beats TQQQ on CAGR and drawdown in both windows, and beats the daily baseline on all four primary metrics at 1 bp.

## 1. Idea and literature

Three strands motivate the tests:

1. **Market intraday momentum.** Gao, Han, Li & Zhou (2018, *JFE* 129(2), 394–414) show that the first half-hour return on SPY predicts the last half-hour return, especially on volatile, high-volume, recession and macro-news days. [DOI](https://doi.org/10.1016/j.jfineco.2018.05.009) · [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2552752)
2. **Gamma-hedging demand.** Baltussen, Da, Lammers & Martens (2021, *JFE* 142(1), 377–403) find the return during the last 30 minutes is predicted by the rest of the day across 60+ futures, and link it to hedging demand from option dealers and **leveraged ETFs**. [DOI](https://doi.org/10.1016/j.jfineco.2021.04.029) · [open PDF](https://academicweb.nd.edu/~zda/intramom.pdf)
3. **Overnight vs intraday.** Lou, Polk & Skouras (2019, *JFE* 134(1), 192–213) show strategy premia accrue either entirely overnight or entirely intraday; momentum-type strategies earn their premia overnight. [DOI](https://doi.org/10.1016/j.jfineco.2019.03.011)
4. TQQQ mechanics: Cheng & Madhavan (2009), *The Dynamics of Leveraged and Inverse ETFs*, show daily re-leveraging creates path dependence and end-of-day rebalancing flows. [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1393995)

The last point matters twice: TQQQ's daily reset makes the overnight/intraday decomposition extreme, and leveraged-ETF rebalancing is itself a candidate driver of late-day momentum.

## 2. What the data actually says (2016–2026, QQQ/TQQQ)

### 2.1 Overnight earns the return, intraday does not

| Component (all days) | Mean bp/day | t-stat | Compounded annual |
|---|---:|---:|---:|
| TQQQ overnight (close → open) | 13.83 | 2.81 | **30.22%** |
| TQQQ intraday (open → close) | 7.73 | 1.22 | **5.93%** |
| QQQ overnight | 5.22 | 3.16 | 13.00% |
| QQQ intraday | 2.93 | 1.38 | 6.03% |

This is the single most important fact for the mandate: an intraday-only strategy starts with a ~6%/yr tailwind, not a ~39%/yr one. The 30/60-minute timing tests below cannot close that gap on the 10y window.

### 2.2 First-30m and first-60m predictability

TQQQ return over the rest of the session, sorted by the sign of the **QQQ** formation-window return:

| Signal | Window | Positive signal | Negative signal | Spread |
|---|---|---:|---:|---:|
| first 30m → TQQQ 10:00–16:00 | 10y | +15.67 bp/day (t=1.92, n=1310) | −9.90 bp (t=−1.09, n=1156) | 25.6 bp |
| first 60m → TQQQ 10:30–16:00, regime on | 10y | +9.70 bp (t=1.45, n=1066) | −6.27 bp (t=−0.79, n=973) | 16.0 bp |
| first 60m → TQQQ 10:30–16:00, regime on | 5y | +21.65 bp (t=2.29, n=481) | −11.00 bp (t=−0.98, n=452) | 32.7 bp |

The 30-minute signal is stronger over the full 10 years; the 60-minute signal is stronger over the last 5. The 60-minute version is the one used below because it is the more balanced of the two across windows.

### 2.3 The published "last half-hour" effect is absent

For QQQ/TQQQ 2016–2026, the Gao et al. (2018) last-half-hour pattern does **not** replicate:

- TQQQ last 30 minutes (15:30–16:00) after a positive first 30m: **−1.60 bp/day** on the 10y window, **−2.43 bp** on the 5y window.
- The predictability shows up earlier: the TQQQ 10:00–15:30 (midday) return after a positive first 30m is **+17.13 bp/day** on the 10y window (t=2.27).

So the tradeable version in this sample is "first hour → afternoon", not "first half-hour → last half-hour". This is a genuine negative replication of the most famous version of the effect, and it is why the strategy holds through the afternoon rather than only the close.

## 3. Strategy rules (exact)

Universe: QQQ (signal), TQQQ (risk asset), BIL (risk-off asset). Long-only, weights ≤ 100%.

1. **Regime (daily).** If QQQ close on day *d−1* > 165-day SMA of QQQ closes through *d−1* → risk-on; otherwise 100% BIL for the whole day. No look-ahead: the regime for day *d* uses only data through *d−1*.
2. **Overnight.** On a risk-on day, buy TQQQ at the **15:59 open** (decision made on the 15:58 QQQ close vs the SMA through the prior day) and hold through the next **09:31 open**. This captures the close-to-open drift.
3. **First hour.** Hold TQQQ from the 09:31 open through the 10:30 open (continuing the overnight position when one exists).
4. **First-hour signal.** `r60 = QQQ close(10:29) / QQQ open(09:30) − 1`.
   - `r60 ≥ 0`: hold TQQQ from the **10:30 open** to the **15:59 open**.
   - `r60 < 0`: sell at the 10:30 open, hold **cash** until the 15:59 open (then re-enter for the overnight).
5. **Risk-off.** 100% BIL, no overnight TQQQ.
6. **Fills.** Every weight is set at the close of bar *i* and filled at the open of bar *i+1*. Costs: 1 bp per side on traded notional; 5 bp sensitivity. Band = 2%.

**No-lookahead audit.** The only borderline timestamp is the overnight decision: it uses the QQQ 15:58 close and fills at the 15:59 open, i.e. one minute later; no 16:00 data is used. The first-hour signal uses the 10:29 close and fills at 10:30. The regime for day *d* uses only closes through *d−1*. All three use data at or before the decision bar.

Why cash (not BIL) for the afternoon exit: it halves the number of fills (one sell, one buy instead of two each way) and the forgone T-bill yield over ~6 hours on ~125 days/year is small relative to the 1–5 bp cost of the extra BIL legs. Empirically it is worth +2.9 pp CAGR at 1 bp and +13 pp at 5 bp.

The signal is the **sign of the first hour** with no fitted threshold. The only other parameter is the 165-day SMA, inherited from the daily baseline. That is deliberate: zero free parameters beyond the literature's round numbers.

## 4. Primary results

Minute-mark statistics from `bt.stats` (daily-mark statistics in parentheses for comparability with the daily baseline):

| | 10y, 1 bp | 10y, 5 bp | 5y, 1 bp | 5y, 5 bp |
|---|---:|---:|---:|---:|
| CAGR | **55.63%** (55.63%) | 43.46% (43.45%) | **46.36%** (45.99%) | 35.80% (35.44%) |
| Max drawdown | **44.89%** (44.59%) | 46.90% (45.48%) | **32.64%** (30.37%) | 34.50% (32.26%) |
| Sharpe | **1.24** (1.24) | 1.05 (1.05) | **1.14** (1.12) | 0.96 (0.94) |
| Volatility | 43.73% | 43.73% | 41.13% | 41.13% |
| Fills | 1,995 | 1,995 | 935 | 935 |
| Turnover | 41,225× | 22,153× | 3,241× | 2,537× |
| Ending equity | $7,636,281 | $3,438,072 | $670,290 | $461,144 |

- About **100 round trips per year** (2,000 fills over 10 years), i.e. one exit/re-entry on each negative-first-hour day.
- TQQQ is the target on **49.5% of regular-session minutes** over the 10y window (43.9% over the 5y window); the regime is risk-on on **83% of 10y days** (74% of the 5y window), and those days carry the overnight position.
- Turnover is cumulative traded notional divided by starting equity, so 41,225× over 10 years.
- Max drawdown episode: **2020-02-19 → 2020-04-13, −44.6%** (COVID). The 5y max drawdown is **2021-12-10 → 2023-03-01, −30.4%**, i.e. the 2022 bear market.

*Harness note:* `bt.benchmark` on minute closes reports TQQQ 5y at 14.29% (10y 39.38%), slightly above the README's daily-close 13.47%/39.28%. The pass/fail table uses the README numbers; using the higher harness number changes nothing.

### 4.1 Yearly returns (1 bp)

| Year | Strategy | TQQQ | Daily baseline |
|---|---:|---:|---:|
| 2017 | +97.4% | +114.5% | +112.1% |
| 2018 | **+16.8%** | −20.8% | −7.6% |
| 2019 | +50.9% | +148.2% | +47.1% |
| 2020 | **+103.0%** | +104.1% | +70.0% |
| 2021 | +71.6% | +81.1% | +90.9% |
| 2022 | **−18.9%** | −79.4% | −24.3% |
| 2023 | +123.4% | +192.0% | +118.5% |
| 2024 | **+80.9%** | +62.4% | +53.9% |
| 2025 | **+57.3%** | +32.1% | +35.8% |
| 2026 YTD | +11.7% | +22.6% | +18.1% |

9 of 10 years positive; the only losing year is 2022 (−18.9% vs TQQQ −79.4%). It beats the daily baseline in **7 of 10 years** (2018, 2019, 2020, 2022, 2023, 2024, 2025) and loses in 2017, 2021 and 2026 — all strong bull years where giving up afternoon exposure costs more than the drawdown protection is worth.

At 5 bp the yearly returns are: 2017 +79.0, 2018 +8.2, 2019 +37.7, 2020 +87.1, 2021 +55.9, 2022 −19.6, 2023 +103.6, 2024 +63.6, 2025 +45.3, 2026 +3.9. Same shape, roughly 15–20 pp lower in the big years.

### 4.2 Sub-period stability

| Period | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| 2017-01-03 → 2021-10-22 (first ~5y) | 65.23% | 44.59% | 1.34 |
| 2021-10-25 → 2026-10-23 (last 5y) | 46.36% | 32.64% | 1.14 |

Both halves are strong. The strategy is not carried by a single crash-avoidance episode.

## 5. Variants and ablations (1 bp)

All rows: minute marks, next-open fills, same harness, except the TQQQ B&H and official daily-baseline rows, which are the README's daily-close figures.

| Variant | Rules | 10y CAGR | 10y DD | 10y Sharpe | 5y CAGR | 5y DD | 5y Sharpe | Verdict |
|---|---|---:|---:|---:|---:|---:|---:|---|
| **TQQQ B&H** | — | 39.28% | 81.68% | 0.83 | 13.47% | 81.68% | 0.53 | benchmark |
| **Daily baseline** | QQQ>165SMA → TQQQ else BIL | 45.31% | 58.71% | 1.00 | 34.61% | 36.86% | 0.88 | passes |
| P1 pure 30m | long 10:00–15:59 if QQQ first30>0; flat overnight | 12.89% | 51.19% | 0.53 | 10.80% | 49.01% | 0.47 | **fails** CAGR |
| P2 pure 60m | long 10:30–15:59 if QQQ first60>0; flat overnight | 8.96% | 65.18% | 0.44 | 32.26% | 31.65% | 1.10 | **fails 10y** |
| P3 30m + regime | P1 gated by 165SMA | 10.33% | 31.06% | 0.52 | 6.96% | 28.70% | 0.41 | **fails** |
| P4 overnight + regime | overnight only, 165SMA | 27.66% | 47.18% | 0.95 | 14.42% | 34.69% | 0.61 | **fails 10y** CAGR |
| P5 overnight, no regime | overnight only, always | 25.11% | 63.56% | 0.75 | 6.40% | 55.64% | 0.36 | fails |
| D0 daily baseline, minute fills | continuous hold | 44.73% | 56.50% | 1.00 | 33.23% | 42.17% | 0.85 | passes vs TQQQ |
| **E2 primary** | regime + overnight + first-hour afternoon | **55.63%** | **44.89%** | **1.24** | **46.36%** | **32.64%** | **1.14** | **passes** |
| E3 threshold −0.3% | E2, exit only if r60 < −0.3% | 56.71% | 51.49% | 1.21 | 46.24% | 37.66% | 1.10 | passes vs TQQQ, not baseline DD |
| E5 no regime | E2 without 165SMA | 59.77% | 74.11% | 1.10 | 45.18% | 66.74% | 0.93 | high DD |

Reading the table:

- **Pure intraday momentum fails** on the 10y window no matter whether the formation window is 30 or 60 minutes. P1 makes 12.89%/yr; P2 makes 8.96%/yr. Both are below the daily baseline and far below TQQQ.
- **Overnight-only is not enough either.** P4 makes 27.66%/yr on 10y with a 47.18% DD — a good risk-adjusted profile, but the CAGR is 11.6 pp below TQQQ because it gives up the positive afternoons.
- **The pieces are complementary.** Overnight + regime (P4, 27.66%) is a good base; adding the first-hour-conditioned morning/afternoon exposure takes the full strategy to 55.63%. The regime filter is what buys the drawdown reduction: E5 (same intraday rule, no regime) makes 59.77% but with a 74.11% DD.
- **Turnover is the Achilles heel at 5 bp.** P4's 5 bp result is **−8.46%/yr** on 10y; a strategy that does a full 100%-notional round trip every day (~250/year) pays 25%/yr at 5 bp. E2 survives because it uses cash (one side each way) and only ~100 round trips a year.

## 6. Robustness

### 6.1 SMA length (E2, 1 bp)

| SMA | 10y CAGR | 10y DD | 5y CAGR | 5y DD |
|---|---:|---:|---:|---:|
| 120 | 43.55% | 53.78% | 40.56% | 48.99% |
| 150 | 55.52% | 44.89% | 43.03% | 41.58% |
| **165** | **55.63%** | **44.89%** | **46.36%** | **32.64%** |
| 180 | 56.16% | 45.78% | 48.09% | 34.23% |
| 200 | 50.17% | 52.92% | 41.63% | 48.00% |
| 250 | 45.01% | 55.98% | 35.44% | 55.98% |

The 150–180 plateau is broad; 165 is not a knife-edge. All six lengths still beat TQQQ on both windows (CAGR > 39.28/13.47, DD < 81.68), but only 165–180 beat the daily baseline on all four metrics (SMA 150 has a 41.58% 5y drawdown vs the baseline's 36.86%).

### 6.2 First-hour threshold (E2, 1 bp)

| Exit if r60 < | 10y CAGR | 10y DD | 5y CAGR | 5y DD |
|---|---:|---:|---:|---:|
| −0.5% | 54.35% | 55.84% | 40.03% | 36.17% |
| −0.3% | 56.71% | 51.49% | 46.24% | 37.66% |
| −0.1% | 60.31% | 51.49% | 51.88% | 34.57% |
| **0.0%** | **55.63%** | **44.89%** | **46.36%** | **32.64%** |
| +0.1% | 50.94% | 44.89% | 36.15% | 33.84% |
| +0.3% | 47.06% | 49.64% | 26.83% | 41.01% |

The surface is flat-to-down as the threshold rises; 0.0% sits inside a stable region and is not the peak (the best 10y CAGR is at −0.1%). The zero threshold was chosen ex ante for simplicity, not fitted.

### 6.3 Costs

| | 1 bp | 5 bp | Δ |
|---|---:|---:|---:|
| 10y CAGR | 55.63% | 43.46% | −12.2 pp |
| 5y CAGR | 46.36% | 35.80% | −10.6 pp |

At 5 bp the strategy still passes vs TQQQ (43.46% > 39.28% with 46.90% DD; 35.80% > 13.47% with 34.50% DD) and still beats the daily baseline on the 5y window. On the 10y window, 5 bp puts CAGR at 43.46% — 1.85 pp below the daily baseline's 45.31% — while keeping a 12 pp lower drawdown and a higher Sharpe (1.05 vs 1.00). The cost sensitivity is the main reason I would not call this a clean win over the daily baseline at realistic costs.

## 7. Pass / fail against the mandate

| Test | 10y | 5y |
|---|---|---|
| CAGR > TQQQ (39.28% / 13.47%) | **PASS** 55.63% | **PASS** 46.36% |
| Max DD < TQQQ (81.68%) | **PASS** 44.89% | **PASS** 32.64% |
| Sharpe > TQQQ (0.83 / 0.53) | **PASS** 1.24 | **PASS** 1.14 |
| CAGR > daily baseline (45.31% / 34.61%) | **PASS** 55.63% | **PASS** 46.36% |
| Max DD < daily baseline (58.71% / 36.86%) | **PASS** 44.89% | **PASS** 32.64% |
| 5 bp still beats TQQQ | **PASS** 43.46% | **PASS** 35.80% |
| 5 bp still beats daily baseline | FAIL CAGR (43.46 < 45.31) | **PASS** 35.80% / 34.50% |

**Overall: PASS at 1 bp on both windows, against both TQQQ and the daily baseline. PASS at 5 bp against TQQQ on both windows. At 5 bp against the daily baseline, 5y passes and 10y fails on CAGR only (drawdown and Sharpe are better).**

## 8. Caveats

1. **The pure idea fails.** Anyone reading this should take away that 30/60-minute intraday momentum alone cannot beat TQQQ in this sample: the intraday drift is ~6%/yr and daily round-trip costs are 2.5–5%/yr at 1 bp. The passing result depends on keeping the overnight leg.
2. **The first-hour signal is statistically weak.** t-stats are 1.4–2.3, not 4+. The 10y conditional spread is 16 bp/day on TQQQ; the 5y spread is 33 bp. Yearly consistency is good but not uniform: the strategy gave up 15–19 pp vs the daily baseline in 2017 and 2021, both strong bull years, because the first-hour signal kept it out of some strong afternoons.
3. **The 2020 drawdown is a real 44.6% loss.** The intraday signal cannot hedge an overnight gap; the regime filter only reacts after the damage. The strategy is not a tail-risk hedge.
4. **TQQQ path dependence.** TQQQ is a 3x daily-reset product. The backtest uses its actual adjusted prices, so the reset is embedded, but the 2017–2026 sample includes an unusually strong Nasdaq bull market and a single −79% bear (2022). Cheng & Madhavan (2009) show leveraged-ETF rebalancing flows can amplify late-day moves; that both helps and hurts this strategy.
5. **The 10y 5 bp result does not beat the daily baseline.** If realistic costs are closer to 5 bp than 1 bp, the honest ranking is: E2 has a much better drawdown and Sharpe, but the daily baseline has a slightly higher CAGR over 2017–2026.
6. **No shorting, no margin.** Weights are ≤ 100% TQQQ; the strategy cannot exploit negative first hours beyond going to cash.
7. **Data caveat.** The panel starts 2016-01-04, so the 165-day SMA is only warm by late August 2016; the 10y window starts 2017-01-03, by which point the SMA is fully populated. The 5y window is a subset of the same data.

## 9. Files and reproduction

- `strategy.py` — clean implementation of the primary strategy, prints both windows at 1 bp and 5 bp, yearly returns, daily-mark statistics and the pass/fail check.
- `result.json` — machine-readable metrics, variants, sensitivities and pass/fail.

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
python research\agents\intraday-momentum\strategy.py
```

The earlier exploratory variants (P1–P5, D0, E3, E5) are documented in the report; the primary is E2.

## References

- Gao, L., Han, Y., Li, S. Z., & Zhou, G. (2018). Market intraday momentum. *Journal of Financial Economics*, 129(2), 394–414. https://doi.org/10.1016/j.jfineco.2018.05.009
- Baltussen, G., Da, Z., Lammers, S., & Martens, M. (2021). Hedging demand and market intraday momentum. *Journal of Financial Economics*, 142(1), 377–403. https://doi.org/10.1016/j.jfineco.2021.04.029 (open PDF: https://academicweb.nd.edu/~zda/intramom.pdf)
- Lou, D., Polk, C., & Skouras, S. (2019). A tug of war: Overnight versus intraday expected returns. *Journal of Financial Economics*, 134(1), 192–213. https://doi.org/10.1016/j.jfineco.2019.03.011
- Cheng, M., & Madhavan, A. (2009). The dynamics of leveraged and inverse exchange-traded funds. *Journal of Investment Management*, 7(4). https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1393995
