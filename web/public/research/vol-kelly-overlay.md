# Volatility ladder + crash throttle on the QQQ 165-day SMA

**Agent:** `vol-kelly-overlay`
**Dates:** 2017-01-03 → 2026-10-23 (10y), 2021-10-25 → 2026-10-23 (5y)
**Data:** adjusted 1-minute QQQ / TQQQ / BIL, regular session only
**Harness:** `research/bt.py`; next-bar-open fills; 1 bp primary, 5 bp sensitivity;
2% trade band; long only; weights sum to ≤ 1.

---

## Verdict

Against **TQQQ buy-and-hold**, the strategy passes on both windows with large margins:

| Window | Candidate CAGR | Candidate max DD | TQQQ CAGR | TQQQ max DD | Pass vs TQQQ |
|---|---:|---:|---:|---:|:---:|
| 10y | **47.53%** | **45.32%** | 39.28% | 81.68% | **PASS** |
| 5y | **34.59%** | **36.29%** | 13.47%* | 81.68% | **PASS** |

\* Stated README benchmark. The harness recomputes 13.88% for TQQQ over the same
5-year bars; the difference is a start-price detail. The candidate beats either
number by more than 20 pp.

Against the **daily 165-day 100% TQQQ baseline** (45.31% / 58.71% 10y,
34.61% / 36.86% 5y):

| Window | CAGR vs baseline | DD vs baseline | Result |
|---|---:|---:|---|
| 10y | +2.22 pp | −13.39 pp | **PASS** |
| 5y | −0.02 pp | −0.57 pp | **CAGR tie (fails by 2 bp), DD pass** |

The 5-year CAGR difference is far inside noise. A simpler binary variant
(100% QQQ when TQQQ 20-day realized vol ≥ 70%) nominally passes both baseline
tests: **46.15% / 45.30%** 10y and **34.77% / 36.33%** 5y.

The strategy is best described as **crisis risk management, not broad alpha**:
it matches the baseline's 5-year return with slightly less drawdown, and its
10-year edge over the baseline comes mostly from avoiding the February–March
2020 collapse. Details and caveats are below.

---

## 1. Idea

TQQQ is a daily-reset 3× fund. Its multi-day log return is approximately

```
log(LETF_T / LETF_0) ≈ k · log(QQQ_T / QQQ_0) − k(k−1)/2 · Σ r_t²
```

with `k = 3` (Cheng & Madhavan 2009; the ProShares prospectus gives the same
path-dependence warning). The drag term is
about `3σ²` per year. At QQQ vol 20% that is roughly 12%/yr before financing
and fees, and the fund's own prospectus warns that higher index volatility and
longer holding periods make returns worse than 3× the daily target (ProShares).

This creates a risk-management tradeoff:

- In a **low-volatility uptrend**, TQQQ's compounding is powerful; hold it.
- In a **high-volatility regime**, volatility drag and crash risk dominate;
  reduce the 3× exposure. QQQ is a better place for the risk budget than BIL
  because it keeps positive equity beta and participates in sharp rebounds;
  BIL is reserved for the trend-off regime and a mild crash throttle.

The academic case for volatility management is real but mixed. Moreira & Muir
(2017) show that scaling factor exposure by inverse realized variance raises
Sharpe ratios because volatility changes are not matched by proportional
changes in expected returns. Harvey et al. (2018) show that volatility targeting
improves Sharpe ratios for risk assets and, importantly for this strategy,
reduces the severity of left-tail events and maximum drawdowns. Cederburg et al.
(2020), however, find that many volatility-managed portfolios do not beat their
unmanaged counterparts out of sample because of estimation instability; they
recommend a tempered interpretation. We therefore use a **slow, broad** volatility
signal (20-day average of daily 1m realized variance), not a fast market-timing
signal, and we report the fragility explicitly.

The Kelly connection is the sizing logic. For excess mean `μ` and variance
`σ²`, the growth-optimal fraction is `f* = μ/σ²`. If the Sharpe ratio is roughly
constant, `f* ∝ 1/σ`. Full Kelly is too aggressive under parameter uncertainty;
fractional Kelly (Thorp 2006) is the practical choice. Our ladder is a discrete,
capped fractional-Kelly rule: 100% TQQQ when TQQQ vol is low, progressively
less TQQQ and more QQQ as vol rises, and a 5% cash cut in a high-vol market
drawdown.

---

## 2. Data and signal construction

This is a **daily-rebalanced** strategy: the 1-minute data enters through the
realized-variance estimator, not through intraday entry/exit timing. That is the
"daily regime + 1m risk sizing" design requested by the mandate. The only
minute-level information used is the within-day sum of squared 1m returns; the
regime, drawdown, and rebalance decisions are daily closes.

- **Daily bars:** `bt.panel(("QQQ","TQQQ","BIL"), start, end, "1D")`, including
  500 calendar days of warmup. The 165-day SMA is fully warmed before the first
  test date.
- **1-minute realized variance:** for each symbol and day, sum of squared
  within-day 1-minute log returns (overnight gaps excluded). This uses the full
  session through 15:59, which is known at the 16:00 close. Annualized:
  `sqrt(252 × mean of the last N daily RV values)`.
- **Signals:** computed from the close of day `i`; `bt.run` fills at the open of
  day `i+1`. No same-bar fills.
- **Costs:** 1 bp of traded notional primary; 5 bp sensitivity. The 2% trade
  band suppresses small rebalances but does not block full exits.

---

## 3. Exact rules

Let:

- `q_t` = QQQ close on day `t`
- `s_t` = 165-day SMA of QQQ close
- `v20_t` = annualized 20-day realized vol of TQQQ from 1m RV
- `v5_t` = annualized 5-day realized vol of TQQQ
- `dd_t` = `q_t / max(q_{t−19..t}) − 1`

**1. Regime.** If `q_t > s_t`, risk-on; otherwise 100% BIL.

**2. Volatility ladder (risk-on only).**

```
x_t = clip((v20_t − 0.65) / (0.95 − 0.65), 0, 1)
QQQ weight  = x_t
TQQQ weight = 1 − x_t
```

So: 100% TQQQ at `v20 ≤ 65%`; linear shift into QQQ between 65% and 95%;
100% QQQ at `v20 ≥ 95%`.

**3. Crash throttle.** If `dd_t ≤ −6%` **and** `v5_t ≥ 55%`, multiply the
QQQ+TQQQ sleeve by `0.95` (5% to BIL). This is a same-day de-risking rule, not
a stop that locks the strategy out; the next day is back to the ladder unless
the condition persists.

**4. Cash.** The remainder after QQQ and TQQQ is BIL. When the regime is off,
BIL = 100%.

### Parameters

| Parameter | Value |
|---|---:|
| SMA window | 165 trading days |
| Vol window | 20 trading days |
| Ladder start / end | 65% / 95% annualized TQQQ vol |
| Drawdown window | 20 trading days |
| Drawdown trigger | −6% from 20-day high |
| Drawdown vol trigger | 5-day TQQQ vol ≥ 55% |
| Drawdown cut | 5% of risky sleeve to BIL |
| Trade band | 2% |
| Slippage | 1 bp primary / 5 bp sensitivity |

These are round, economically motivated values rather than a single-cell
optimum; the sensitivity table in §6 shows the 10-year result is stable across
the ladder range and cut, while the 5-year pass/fail does flip within the
plateau. We report the surface rather than claiming a unique parameter set.

### 3.1 Variants tested

All variants below use the same 165-day regime, fills, band, and 1 bp cost.
The table is a representative sample of the grid, not the full search; the
final rule was chosen for the best balance of 10-year CAGR/DD and 5-year DD,
not for the single best cell.

| Variant | 10y CAGR / DD | 5y CAGR / DD | Assessment |
|---|---:|---:|---|
| Daily baseline, 100% TQQQ | 45.31 / 58.71 | 34.61 / 36.86 | reference |
| V1: inverse-vol TQQQ, target 40% | 41.79 / 43.62 | 32.30 / 36.21 | lower DD, too much CAGR loss |
| V1: inverse-vol TQQQ, target 60% | 45.94 / 49.43 | 34.37 / 37.49 | 10y pass, 5y fail |
| V1: inverse-vol TQQQ, target 70% | 46.62 / 52.03 | 34.61 / 36.86 | near-baseline, no 5y DD gain |
| V2: QQQ/TQQQ ladder, target 45% | 42.52 / 46.29 | 32.45 / 38.01 | too much CAGR loss |
| V2: QQQ/TQQQ ladder, target 65% | 46.74 / 50.97 | 34.66 / 36.86 | 5y DD only equal |
| V3: strategy-equity DD throttle 10% | 23.23 / 37.04 | 13.23 / 37.04 | too much CAGR loss |
| V4: downside-vol target 50% | 46.38 / 53.23 | 34.61 / 36.86 | no 5y gain |
| **Final: smooth ladder + 5% cut** | **47.53 / 45.32** | **34.59 / 36.29** | best balance |

The plain inverse-vol target (V1) cuts 10-year drawdown but gives up too much
CAGR on the 5-year window; a strategy-equity drawdown throttle (V3) is much
worse because it sells after the drawdown has already happened and misses the
rebound. Replacing part of the TQQQ sleeve with QQQ (the ladder) preserves more
upside than going to BIL, and the small crash cut shaves the 2024 drawdown
without changing the regime.

---

## 4. Results

### 4.1 10-year and 5-year, 1 bp

| Window | Strategy | CAGR | Max DD | Sharpe | Vol | Fills | Turnover | Ending equity |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| **10y** | **Candidate** | **47.53%** | **45.32%** | **1.06** | 47.83% | 327 | 1013.7× | $4,522,330 |
| 10y | Daily baseline | 45.31% | 58.71% | 1.00 | 50.22% | 81 | 794.5× | $3,895,794 |
| 10y | TQQQ buy-and-hold | 39.28% | 81.68% | 0.83 | 67.94% | — | — | $2,571,529 |
| **5y** | **Candidate** | **34.59%** | **36.29%** | **0.88** | 46.27% | 85 | 87.4× | $440,748 |
| 5y | Daily baseline | 34.61% | 36.86% | 0.88 | 46.42% | 45 | 81.9× | $441,132 |
| 5y | TQQQ buy-and-hold | 13.88% | 81.68% | 0.53 | 68.90% | — | — | $191,401 |

Average exposures over the 10y window: QQQ 1.6%, TQQQ 80.9%, BIL 17.5%.
Over the 5y window: QQQ 0.1%, TQQQ 74.2%, BIL 25.7%. The QQQ sleeve is small on
average but becomes large exactly in the extreme-vol regimes where TQQQ's
compounding is most dangerous.

The 10-year maximum drawdown of 45.32% is **not** the 2020 crash: it is the
2018-08-29 → 2019-06-03 growth scare, recovered by 2020-01-09. The 2020
drawdown is 41.72%. The 5-year maximum drawdown is 2024-07-10 → 2024-09-06,
recovered 2024-12-16 (the July–September 2024 volatility episode).

### 4.2 5 bp sensitivity

| Window | Strategy | CAGR | Max DD | Sharpe |
|---|---|---:|---:|---:|
| 10y | Candidate | 46.96% | 45.85% | 1.05 |
| 10y | Daily baseline | 44.83% | 58.84% | 0.99 |
| 5y | Candidate | 34.09% | 36.39% | 0.87 |
| 5y | Daily baseline | 34.12% | 36.86% | 0.87 |

At 5 bp the candidate still beats the 5 bp baseline on 10y (+2.13 pp CAGR,
−12.99 pp DD) and is a 0.03 pp CAGR tie on 5y with lower DD. Versus the
baseline's **1 bp** numbers, the candidate's 5 bp 5y CAGR (34.09%) is 0.52 pp
below 34.61%; that is the honest cost of the extra turnover. The edge over
TQQQ remains enormous.

### 4.3 Yearly returns

| Year | Candidate | Daily baseline | TQQQ |
|---:|---:|---:|---:|
| 2017 | 112.1% | 112.1% | 113.0% |
| 2018 | −10.3% | −7.6% | −23.5% |
| 2019 | 46.2% | 47.1% | 130.5% |
| 2020 | **108.4%** | 70.0% | 99.8% |
| 2021 | 87.1% | 90.9% | 90.9% |
| 2022 | **−24.1%** | −24.3% | −79.7% |
| 2023 | 118.5% | 118.5% | 204.9% |
| 2024 | 55.0% | 53.9% | 66.7% |
| 2025 | 35.0% | 35.8% | 35.2% |
| 2026 | 17.5% | 18.1% | 27.4% |

The 5-year window contributes 2021 (partial, 11.9% vs TQQQ 14.0%), then the
same 2022–2026 rows. The strategy lags TQQQ badly in strong bull years (2019,
2023, 2024, 2026) and wins by avoiding the catastrophic years (2018, 2020,
2022). That is the intended shape of a risk-managed leveraged strategy.

### 4.4 Half-period stability

| Period | Candidate CAGR / DD | Baseline CAGR / DD |
|---|---:|---:|
| 2017-01-03 → 2021-12-31 | 63.06% / 45.32% | 58.24% / 58.71% |
| 2022-01-03 → 2026-10-23 | 32.08% / 36.29% | 32.11% / 36.86% |

The entire 10-year CAGR edge over the baseline is pre-2022, and most of it is
2020. In the recent four-plus years the strategy is a **tie on CAGR with lower
drawdown** — a classic risk-reduction tradeoff, not alpha.

### 4.5 No-lookahead / stale-signal check

If every signal is shifted one day (strictly stale: at the close of day `i` we
use data through `i−1`), the results are:

- 10y: 51.39% CAGR / 46.96% DD / 1.10 Sharpe
- 5y: 37.64% CAGR / 35.98% DD / 0.92 Sharpe

The strategy does not depend on same-close timing; the stale version is, if
anything, better in this sample (path luck). This is a useful check that the
1-minute RV is not leaking future information.

---

## 5. Alternative: binary 70% QQQ switch

Same regime and same 5% crash throttle, but replace the smooth ladder with:

- TQQQ 20-day vol < 70% → 100% TQQQ
- TQQQ 20-day vol ≥ 70% → 100% QQQ

| Window | CAGR | Max DD | Sharpe | Fills | Turnover |
|---|---:|---:|---:|---:|---:|
| 10y, 1 bp | 46.15% | 45.30% | 1.05 | 190 | 942.8× |
| 5y, 1 bp | **34.77%** | **36.33%** | 0.88 | 71 | 86.1× |
| 10y, 5 bp | 45.51% | 46.08% | 1.04 | 190 | 912.4× |
| 5y, 5 bp | 34.28% | 36.43% | 0.87 | 71 | 85.1× |

This variant nominally clears the daily baseline on **both** windows at 1 bp
(10y +0.84 pp CAGR, −13.41 pp DD; 5y +0.16 pp CAGR, −0.53 pp DD) and at 5 bp
versus the 5 bp baseline. But the 5-year CAGR cushion is only 0.16 pp, and the
result is threshold-sensitive: moving the QQQ switch from 70% to 71% drops the
5y CAGR to 34.38%, below the baseline. Treat the 5y pass as a tie, not a
statistically established edge. The smooth ladder is the more defensible
primary implementation because it has no single-threshold cliff.

---

## 6. Parameter stability

10y and 5y results (CAGR% / max DD%) at 1 bp:

| Variant | 10y | 5y |
|---|---:|---:|
| Ladder 60–90%, cut 5% | 46.24 / 44.50 | 34.08 / 37.62 |
| Ladder 60–95%, cut 5% | 46.38 / 44.56 | 34.13 / 37.44 |
| Ladder 65–90%, cut 5% | 47.51 / 45.10 | 34.55 / 36.44 |
| **Ladder 65–95%, cut 5% (primary)** | **47.53 / 45.32** | **34.59 / 36.29** |
| Ladder 70–90%, cut 5% | 48.15 / 45.48 | 34.47 / 36.33 |
| Ladder 70–95%, cut 5% | 48.00 / 45.67 | 34.47 / 36.33 |
| Cut 0% | 47.92 / 45.50 | 34.68 / 36.86 |
| Cut 2% | 47.75 / 45.44 | 34.80 / 36.64 |
| Cut 5% | 47.53 / 45.32 | 34.59 / 36.29 |
| Cut 10% | 47.21 / 45.14 | 34.50 / 35.70 |
| Vol window 10d | 47.05 / 43.84 | 33.61 / 39.11 |
| Vol window 20d | 47.53 / 45.32 | 34.59 / 36.29 |
| Vol window 60d | 40.27 / 55.57 | 32.67 / 36.33 |
| Band 0.02 | 47.53 / 45.32 | 34.59 / 36.29 |
| Band 0.05 | 47.55 / 45.32 | 35.02 / 36.07 |
| Band 0.10 | 47.57 / 45.35 | 34.71 / 36.86 |

The 10-year result is stable across the ladder range and cut. The 5-year
result is **on the same frontier as the baseline**: depending on the cut or
ladder range, the CAGR is 34.1–34.8% and the DD is 35.7–37.6%. The one
parameter that clearly matters is the 20-day RV window: 10 days is too fast
(whipsaws, 33.61% / 39.11%) and 60 days is too slow (misses the 2020 spike,
32.67% / 36.33%). A one-month volatility estimate is standard in the
volatility-targeting literature (Harvey et al. use a 20-day half-life), so this
is an economic choice rather than a fitted one.

A wider 5% rebalance band reduces fills from 327 to 250 and lifts the 5y CAGR
to 35.02% in this sample, but the gain is path-dependent (0.04 band gives
34.50%); we keep the harness-default 0.02 band for comparability with the
baseline.

Using QQQ's own 20-day RV for the ladder instead of TQQQ's (20–32% QQQ vol,
with the 5-day cut threshold rescaled to 16% QQQ vol) gives 10y 46.47% /
45.01% and 5y 34.06% / 37.27% — no better. TQQQ's own realized variance is the
more relevant state variable because it captures the 3× daily-reset drag and
financing, not just index vol.

---

## 7. Pass/fail summary

**Versus TQQQ buy-and-hold (the stated benchmark):**

- 10y: **PASS** — CAGR 47.53% > 39.28%, max DD 45.32% < 81.68%.
- 5y: **PASS** — CAGR 34.59% > 13.88% (README 13.47%), max DD 36.29% < 81.68%.
- 5 bp: still passes by a wide margin on both windows.

**Versus the daily 165-day 100% TQQQ baseline:**

- 10y: **PASS** — CAGR +2.22 pp, DD −13.39 pp.
- 5y: **CAGR tie/fail by 0.02 pp** (34.59% vs 34.61%), **DD pass**
  (36.29% vs 36.86%). The difference is inside noise; the 2022–2026 half is
  32.08% vs 32.11%.
- The binary 70% variant **nominally passes both** (46.15/45.30 and
  34.77/36.33), but its 5y margin is also inside noise.

---

## 8. Caveats and honest assessment

1. **The 10-year edge is crisis-concentrated.** 2020 contributes +108.4% vs
   the baseline's +70.0%; the 2022–2026 half is a tie. The strategy is a
   crisis hedge, not a broad alpha generator. A sample without a 2020-style
   crash would show a much smaller advantage over the baseline.
2. **The 5-year result does not establish a baseline-beating edge.** The
   primary's CAGR is 2 bp below the baseline; the binary's is 16 bp above.
   Both are inside the noise of a five-year sample. The robust claim is
   "matches the baseline's 5y return with slightly lower drawdown," not
   "beats it."
3. **Parameter sensitivity is real.** The 20-day RV window is important; 10d
   and 60d are worse. The 5y pass/fail flips with the cut size and ladder
   range. We report the full surface rather than the best cell.
4. **Turnover and costs.** 1013.7× over 10 years (~103×/yr) is high. At 5 bp
   the 10y CAGR falls from 47.53% to 46.96%; the 5y CAGR falls from 34.59% to
   34.09%. Taxes, borrow costs, and market impact beyond slippage are not
   modeled. TQQQ's expense ratio is embedded in the adjusted price data.
5. **Out-of-sample caution.** Cederburg et al. (2020) show that volatility-
   managed portfolios often fail out of sample because of estimation
   instability. Our sample contains one COVID crash and one 2022 bear market;
   the strategy could lag in a high-volatility, sharply trending bull market.
   2023 is the warning: the candidate returned 118.5% while TQQQ returned
   204.9%, an 86 pp shortfall.
6. **Long-only, no extra leverage.** The maximum equity exposure is 100%;
   the only leverage is TQQQ's embedded 3×. No shorting, options, or margin
   is modeled. Weights sum to ≤ 1.
7. **5y TQQQ benchmark discrepancy.** The README quotes 13.47%; the harness
   computes 13.88% from the same close series. The candidate beats both by
   more than 20 pp, so the conclusion is unaffected.
8. **1-minute RV noise.** One-minute realized variance is subject to bid-ask
   bounce and other microstructure noise. The 20-day averaging and the broad
   65–95% ladder are intended to make the signal robust to it; we did not
   separately test 5-minute RV as the input.

---

## 9. Reproduce

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:/Users/27175/AppData/Local/Temp/opencode/pylibs"
python research/agents/vol-kelly-overlay/strategy.py
```

`strategy.py` computes the 1-minute realized variance on the fly if the cached
`rv1m.parquet` is absent, then writes `result.json` and prints the 10y/5y
summary. All fills are next-bar open; the only data used are the local QQQ,
TQQQ, and BIL 1-minute bars.

---

## Sources

- Moreira, A. & Muir, T. (2017). "Volatility-Managed Portfolios." *Journal of
  Finance* 72(4), 1611–1644. https://doi.org/10.1111/jofi.12513
- Harvey, C. R., Hoyle, E., Korgaonkar, R., Rattray, S., Sargaison, M. &
  Van Hemert, O. (2018). "The Impact of Volatility Targeting." *Journal of
  Portfolio Management* 45(1), 14–33.
  https://doi.org/10.3905/jpm.2018.45.1.014
- Cederburg, S., O'Doherty, M. S., Wang, F. & Yan, X. S. (2020). "On the
  performance of volatility-managed portfolios." *Journal of Financial
  Economics* 138(1), 95–117.
  https://doi.org/10.1016/j.jfineco.2020.04.015
- Thorp, E. O. (2006/2007). "The Kelly Criterion in Blackjack, Sports Betting,
  and the Stock Market." In *Handbook of Asset and Liability Management*.
  https://www.bjrnet.com/thorp/Thorp_KellyCriterion.pdf
- Cheng, M. & Madhavan, A. (2009). "The Dynamics of Leveraged and Inverse
  Exchange-Traded Funds." *Journal of Investment Management* 7(4).
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1393995
- ProShares. *TQQQ UltraPro QQQ Summary Prospectus* (daily 3× objective and
  holding-period risk).
  https://www.proshares.com/globalassets/proshares/prospectuses/tqqq_summary_prospectus.pdf
- Downside-risk extension tested but not used in the final rule:
  "Downside risk and the performance of volatility-managed portfolios"
  (2021), https://www.sciencedirect.com/science/article/abs/pii/S0378426621001576

---

## Files

- `strategy.py` — runnable implementation and metrics.
- `result.json` — machine-readable 10y/5y metrics, yearly returns, 5 bp
  sensitivity, binary alternative, and half-period stats.
