# Ensemble signals: daily trend gate, volatility budget, and a 1-minute crash vote

**Verdict: PASS vs TQQQ on both windows, at 1 bp and 5 bp.** It also beats the
daily SMA-165 baseline on CAGR and drawdown on both windows, though the 5-year
drawdown margin is thin on 1-minute marks (1.9 pp) and comfortable on daily
closes (3.6 pp).

The strategy is long-only `TQQQ`/`BIL`, with `QQQ` as the tested de-lever
alternative. It uses five simple signals: a daily 165-day QQQ trend gate, a
20-day realised-volatility budget, and a same-session crash vote built from a
60-minute EMA, 30-minute momentum, and a 1-minute RSI(14) mean-reversion veto.
The daily signals decide the session's default position; the intraday vote can
only reduce risk for the rest of the session.

---

## 1. Headline results

All results use the shared `research/bt.py` harness, next-bar-open fills, a 2%
rebalance band, regular-session bars, and adjusted QQQ/TQQQ/BIL 1-minute data.
`DD (1m)` marks equity every minute; `DD (day)` marks it at daily closes, the
same convention as the README's daily baseline. The 1-minute mark is the more
conservative drawdown and is the one used for pass/fail.

| Window | Cost | CAGR | Max DD (1m) | Max DD (day) | Sharpe | Sortino | Vol | Fills | Turnover |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 10y 2017-01-03 → 2026-10-23 | 1 bp | **54.73%** | **39.91%** | 38.33% | **1.19** | 1.69 | 45.81% | 225 | 4,508x |
| 10y | 5 bp | **53.32%** | **40.48%** | 38.92% | **1.17** | 1.66 | 45.81% | 225 | 4,201x |
| 5y 2021-10-25 → 2026-10-23 | 1 bp | **40.79%** | **34.93%** | 33.24% | **0.99** | 1.40 | 45.26% | 89 | 292x |
| 5y | 5 bp | **39.79%** | **34.93%** | 33.24% | **0.97** | 1.38 | 45.26% | 89 | 286x |

Ending equity on $100,000: **$7.21M** (10y, 1 bp), **$6.59M** (10y, 5 bp),
**$552k** (5y, 1 bp), **$533k** (5y, 5 bp).

### Pass/fail vs TQQQ

The benchmark numbers requested are the README's daily TQQQ figures:
**39.28% CAGR / 81.68% max DD** over 10 years and **13.47% / 81.68%** over
5 years.

| Window | Strategy CAGR | TQQQ CAGR | Strategy max DD (1m) | TQQQ max DD | CAGR > TQQQ | DD < TQQQ | Pass |
|---|---:|---:|---:|---:|:---:|:---:|:---:|
| 10y | 54.73% | 39.28% | 39.91% | 81.68% | +15.45 pp | −41.77 pp | **PASS** |
| 5y | 40.79% | 13.47% | 34.93% | 81.68% | +27.32 pp | −46.75 pp | **PASS** |

At 5 bp the verdict is unchanged: 10y 53.32% / 40.48% and 5y 39.79% / 34.93%
against the same TQQQ bars.

### Comparison with the daily baseline

| Window | Strategy CAGR | Baseline CAGR | Δ CAGR | Strategy DD (1m / day) | Baseline DD | Δ DD (1m / day) |
|---|---:|---:|---:|---:|---:|---:|
| 10y | 54.73% | 45.31% | **+9.42 pp** | 39.91% / 38.33% | 58.71% | **−18.80 / −20.38 pp** |
| 5y | 40.79% | 34.61% | **+6.18 pp** | 34.93% / 33.24% | 36.86% | **−1.93 / −3.62 pp** |

The 5-year drawdown comparison is the closest call. On 1-minute equity marks,
the strategy's 2023 drawdown (34.93%) is only 1.93 pp below the baseline's 2024
drawdown (36.86%); on daily closes it is 3.62 pp below. The CAGR margin is
comfortable (6.18 pp).

---

## 2. Idea and literature

The design follows one central empirical fact: **trend following works on slow
horizons, while mean reversion works on fast ones.** A 2017 study of technical
rules on high-frequency commodity ETFs finds that trend-following rules lose
predictive power as sampling frequency rises, while mean-reversion rules
improve (Marshall, Nguyen & Visaltanachoti, *Finance Research Letters*,
[link](https://www.sciencedirect.com/science/article/abs/pii/S1544612316303026)).
That is exactly the split used here:

- **Slow layer:** the 165-day QQQ trend gate and a 20-day volatility budget.
  These decide whether the portfolio owns 3x Nasdaq, 1x Nasdaq, or T-bills.
- **Fast layer:** a same-session crash vote. It does not try to earn alpha from
  1-minute trend following. It only decides whether a sharp intraday decline
  is a genuine risk-off event or a panic low that should be held through.

The slow layer descends from Faber's 10-month moving-average rule
([SSRN 962461](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=962461)) and
Gayed & Bilello's leveraged-trend work
([SSRN 2741701](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2741701)).
The volatility budget follows Moreira & Muir's volatility-managed portfolios
([SSRN 2659431](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2659431))
and the leveraged-trend literature's point that volatility is the enemy of a
daily-reset 3x fund. Zarattini & Antonacci's century of industry trends
([SSRN 4857230](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4857230))
is the closest template for trend plus volatility sizing; Massaad et al.
([arXiv 2412.14361](https://arxiv.org/abs/2412.14361)) is the caution that
published trend results degrade under robust walk-forward testing.

The fast layer is deliberately a **veto ensemble**, not a return forecast.
The KTH thesis *Ensemble Models for Trend Investing*
([PDF](https://www.diva-portal.org/smash/get/diva2:1663269/FULLTEXT01.pdf))
finds that combining trend signals improves risk-adjusted returns and
drawdowns but does not beat a simple 9-month momentum rule on return; that is
consistent with using the fast signals for risk control rather than as a
standalone alpha engine. Connors & Alvarez's RSI(2) work
([book](https://www.amazon.com/Short-Term-Trading-Strategies-That-Work/dp/0071609174))
is the ancestor of the oversold veto.

### What did not work

Standalone 1-minute trend and momentum had essentially no directional edge in
this sample. On QQQ, forward 30-minute returns were:

| Condition | Observations | Mean forward 30m | Win rate |
|---|---:|---:|---:|
| QQQ > 60-minute EMA | 528,791 | +0.0053% | 52.8% |
| QQQ < 60-minute EMA | 430,124 | +0.0078% | 53.0% |
| 30-minute momentum > 0 | 506,881 | +0.0057% | 52.6% |
| 30-minute momentum < 0 | 447,088 | +0.0073% | 53.1% |

The "down" states were marginally *better* than the "up" states, i.e. the
1-minute data show mild mean reversion, not 1-minute trend. A strategy that
traded these signals directly would pay costs for no edge. They are therefore
used only as confirmations of a crash, and the report is explicit that the
RSI veto is the part of the fast layer that actually changes decisions. In
this sample, at every −3% intraday trigger QQQ was already below its 60-minute
EMA and its 30-minute momentum was negative, so the two trend votes are usually
redundant; the oversold veto is what sometimes keeps the position on.

---

## 3. Exact rules

Signals are evaluated on QQQ. The portfolio holds at most one of QQQ, TQQQ, or
BIL at a time; weights are 0/1 and sum to 1.

### Daily layer (after the close, applied to the next session)

| # | Signal | Rule | Effect |
|---|---|---|---|
| 1 | Trend gate | QQQ close > 165-day SMA | If false: 100% BIL for the session |
| 2 | Volatility budget | 20-day annualised QQQ realised vol ≤ 1/3 | If false (and trend true): 100% BIL for the session |
|  |  |  | If both true: default 100% TQQQ |

The primary configuration uses **BIL** as the high-volatility fallback. A
QQQ fallback was also tested; it is slightly weaker (section 6) but still
passes. The daily layer is evaluated on the prior completed daily close at the
start of each session, and on the current 15:59 close at the last bar to set
the next session's open. This is the same one-bar lag as the daily baseline.

### Intraday layer (only while the session default is TQQQ)

Three votes are computed every minute:

| # | Signal | Risk-off vote when | Risk-on vote when |
|---|---|---|---|
| 3 | 1-minute trend | QQQ < 60-minute EMA | QQQ ≥ 60-minute EMA |
| 4 | 1-minute momentum | 30-minute return < 0 | 30-minute return ≥ 0 |
| 5 | Mean reversion | RSI(14) ≥ 30 | RSI(14) < 30 (oversold) |

The crash condition is:

```
QQQ intraday return from prior close <= -3%
AND (trend vote + momentum vote + mean-reversion vote) <= -2
```

When triggered, sell TQQQ to BIL at the **next minute's open** and stay BIL for
the rest of the session. At the last bar of the session, the next open is set
from that day's completed close (trend gate and volatility budget), so the
strategy re-enters the next session only if the daily layer still allows it.
The next session's open is not part of the crashed session.

No look-ahead: the trigger uses bar `i`'s close; the fill is bar `i+1`'s open.
The daily signals use only completed daily closes. The 15:59 bar is treated as
the daily close, which is the same convention as the daily panel.

### Position timeline

For a day `D`:

1. At 09:30, the default position comes from `D-1`'s close (SMA-165 and 20-day
   vol).
2. During the session, a crash vote may move TQQQ → BIL.
3. At 15:59, the position for `D+1`'s open is set from `D`'s close. If a crash
   was triggered earlier but `D` closes with the trend gate on and vol ≤ 1/3,
   the strategy re-enters TQQQ at `D+1`'s open.

---

## 4. Parameters

| Parameter | Value | Why |
|---|---:|---|
| Trend SMA | 165 trading days | The README/live baseline; also the centre of a 150–180 plateau |
| Vol lookback | 20 trading days | Standard; 15/20/30 all work |
| Vol threshold | 1/3 (33.3%) annualised | Round number; 30–40% plateau |
| Crash threshold | 3.0% intraday | Round number; 2.5–3.0% plateau, 3.5%+ degrades 5y |
| RSI period | 14 minutes | Standard |
| RSI oversold veto | 30 | 20/30/40 all work |
| High-vol asset | BIL | Tested vs QQQ; BIL better on both windows |
| Rebalance band | 2% | Harness default; irrelevant for 0/1 weights because fully invested positions have zero drift versus book |

Five parameters matter: SMA length (inherited), vol lookback, vol threshold,
crash threshold, and RSI floor. The rest are standard constants.

---

## 5. Results in detail

### 5.1 Yearly returns

Strategy at 1 bp, TQQQ buy-and-hold, and the README daily baseline:

| Year | Strategy | TQQQ | Daily baseline | Strategy − baseline |
|---|---:|---:|---:|---:|
| 2017 | +115.1% | +114.5% | +112.1% | +3.0 pp |
| 2018 | +16.8% | −20.8% | −7.6% | +24.4 pp |
| 2019 | +40.4% | +148.2% | +47.1% | −6.7 pp |
| 2020 | +183.1% | +104.1% | +70.0% | +113.1 pp |
| 2021 | +44.1% | +81.1% | +90.9% | −46.8 pp |
| 2022 | −21.8% | −79.4% | −24.3% | +2.5 pp |
| 2023 | +118.5% | +192.0% | +118.5% | 0.0 pp |
| 2024 | +74.6% | +62.4% | +53.9% | +20.7 pp |
| 2025 | +26.7% | +32.1% | +35.8% | −9.1 pp |
| 2026* | +21.2% | +22.6% | +18.1% | +3.1 pp |

\* 2026 is through 2026-10-23.

The 5-year window starts 2021-10-25, so its 2021 figure is the partial
+16.1% (TQQQ +16.0%, baseline +11.9%), not the full-year +44.1%.

The strategy is positive in **9 of 10 calendar years**; the only losing year is
2022 (−21.8%), which is also TQQQ's worst year (−79.4%). It beats the daily
baseline in 6 of 10 years (2017, 2018, 2020, 2022, 2024, 2026), ties 2023, and
loses in the strong melt-up years 2019, 2021 and 2025, when the volatility
budget holds BIL instead of TQQQ. That is the expected cost of the risk
overlay, not a hidden return forecast.

### 5.2 Drawdowns

- **10y, 1-minute marks:** 39.91%, 2018-08-30 → 2019-06-03. The 2018 Q4
  whipsaw is the worst episode after the overlays; the COVID drawdown is
  smaller because the crash vote and vol budget cut exposure early.
- **10y, daily closes:** 38.33%, 2018-08-29 → 2019-06-03.
- **5y, 1-minute marks:** 34.93%, 2023-07-19 → 2023-10-26.
- **5y, daily closes:** 33.24%, 2023-07-18 → 2023-10-26.

The 2024 July–August drawdown that dominates the daily baseline (36.86%) is
substantially reduced: the volatility budget moves to BIL before the worst of
the 3x decline, and the crash vote handles the gap-down days. The 2023
July–October drawdown becomes the 5-year maximum instead.

### 5.3 Exposure and turnover

| Window | TQQQ bars | QQQ bars | BIL bars | Fills | Turnover |
|---|---:|---:|---:|---:|---:|
| 10y | 80.1% | 0.0% | 19.9% | 225 | 4,508x |
| 5y | 73.5% | 0.0% | 26.5% | 89 | 292x |

`Turnover` is traded notional divided by starting equity, so it compounds with
the equity curve; the fill count is the more intuitive activity measure (about
23 fills a year over 10 years, 18 a year over 5 years). At 5 bp the cost drag
is about 1.4 pp/yr over 10 years and 1.0 pp/yr over 5 years.

---

## 6. Ablations

All at 1 bp, 1-minute marks. `daily_trend_only` is the same minute-aligned
SMA-165 rule without the vol budget or crash vote; its 5y 1-minute DD (42.17%)
is higher than the README daily-close baseline (36.86%) because it marks the
2024-08-05 09:30 low rather than the daily close. The README baseline remains
the reference for pass/fail.

| Variant | 10y CAGR | 10y DD | 5y CAGR | 5y DD |
|---|---:|---:|---:|---:|
| Daily SMA-165 only (minute-aligned) | 45.47% | 59.64% | 35.59% | 42.17% |
| + volatility budget (no crash vote) | 51.93% | 43.71% | 38.53% | 42.17% |
| + crash vote (no vol budget) | 54.46% | 44.48% | 37.80% | 36.30% |
| **Full ensemble (BIL fallback)** | **54.73%** | **39.91%** | **40.79%** | **34.93%** |
| Full minus RSI veto | 52.78% | 39.89% | 39.66% | 34.93% |
| Full with QQQ high-vol fallback | 52.89% | 41.48% | 39.80% | 34.93% |

Reading the table: relative to trend-only, the volatility budget adds about
6.5 pp of 10-year CAGR and cuts the 10-year DD by 16 pp; the crash vote alone
adds about 9.0 pp of 10-year CAGR and cuts the 5-year DD by 5.9 pp. Together
they add 9.3 pp of 10-year CAGR and cut the 10-year DD by 19.7 pp. Incrementally,
adding the crash vote on top of the vol budget adds 2.8 pp of 10-year CAGR and
3.8 pp of 10-year DD; adding the vol budget on top of the crash vote adds only
0.3 pp of CAGR but 4.6 pp of DD. The RSI veto adds about 2.0 pp of 10-year CAGR
and 1.1 pp of 5-year CAGR at the same drawdown. The BIL fallback beats the QQQ
fallback by 1.8 pp of 10-year CAGR and 1.0 pp of 5-year CAGR, with a 1.6 pp
lower 10-year DD.

---

## 7. Parameter stability

### 7.1 Volatility threshold × crash threshold

Cells are **10y CAGR / 10y max DD | 5y CAGR / 5y max DD**, all at 1 bp.

| Vol max \ crash | 2.5% | 3.0% | 3.5% | 4.0% |
|---|---:|---:|---:|---:|
| 30% | 48.6/48.3 \| 36.3/35.4 | 50.8/39.9 \| 35.5/36.0 | 48.6/46.4 \| 29.5/46.4 | 48.4/46.4 \| 31.2/46.4 |
| **33.3%** | 52.1/46.4 \| 41.6/35.4 | **54.7/39.9 \| 40.8/34.9** | 52.4/42.8 \| 34.6/42.2 | 52.2/42.5 \| 36.4/42.2 |
| 36% | 49.3/50.5 \| 38.6/36.5 | 52.0/44.5 \| 37.8/36.3 | 49.1/47.2 \| 31.7/42.2 | 49.8/46.8 \| 33.5/42.2 |
| 40% | 50.9/50.5 \| 38.6/36.5 | 53.1/44.5 \| 37.8/36.3 | 49.5/47.2 \| 31.7/42.2 | 48.8/46.8 \| 33.5/42.2 |

Every cell passes vs TQQQ. The chosen cell is a local peak, but it is not a
single lucky cell: at **X = 3.0%**, every volatility threshold from 30% to 40%
beats the daily baseline on 10-year CAGR (50.8–54.7%), 5-year CAGR (35.5–40.8%)
and 5-year DD (≤ 36.3%). The crash threshold is the more sensitive parameter:
3.5% and 4.0% degrade the 5-year results because the 2024 and 2026 exits arrive
too late. 2.5% works too (41.6% 5y CAGR, 35.4% 5y DD) but gives a worse 10-year
DD (46.4%). 3.0% is the centre of the usable 2.5–3.0% region.

### 7.2 Other parameters

| Change | 10y CAGR | 10y DD | 5y CAGR | 5y DD |
|---|---:|---:|---:|---:|
| SMA 150 | 55.0% | 38.3% | 35.7% | 38.3% |
| **SMA 165** | **54.7%** | **39.9%** | **40.8%** | **34.9%** |
| SMA 180 | 54.1% | 41.5% | 40.5% | 34.9% |
| Vol lookback 15 | 55.2% | 39.9% | 39.1% | 34.9% |
| **Vol lookback 20** | **54.7%** | **39.9%** | **40.8%** | **34.9%** |
| Vol lookback 30 | 51.8% | 44.5% | 38.5% | 36.3% |
| RSI floor 20 | 53.8% | 39.9% | 40.8% | 34.9% |
| **RSI floor 30** | **54.7%** | **39.9%** | **40.8%** | **34.9%** |
| RSI floor 40 | 53.8% | 40.5% | 41.2% | 34.9% |

The 10-year result is remarkably flat across these choices (51.8–55.2%). The
5-year result is stable except for SMA 150 (DD 38.3%) and vol lookback 30
(DD 36.3%), both still close to the baseline. 165 and 180 are the stable
region.

---

## 8. Robustness and honest caveats

1. **Costs.** The required 5 bp case passes on both windows: 10y 53.32% /
   40.48%, 5y 39.79% / 34.93%. Turnover is high in notional terms because each
   switch moves 100% of equity; at 5 bp the drag is ~1.4 pp/yr over 10 years
   and ~1.0 pp/yr over 5 years. The edge is not a 1 bp artifact.
2. **Drawdown convention.** The headline `DD (1m)` is measured on 1-minute
   equity marks. The README baseline's 58.71%/36.86% are daily-close marks. On
   the same daily-close convention the strategy is 38.33%/33.24%, so the
   comparison to the baseline is 20.4 pp / 3.6 pp better, not 18.8 pp / 1.9 pp.
   Both conventions pass vs TQQQ.
3. **First-session convention.** The minute strategy can act at the first
   session's open using the prior day's completed daily signal. The daily
   baseline's first weight is set at the first session's close. In the 5-year
   window this gives the minute strategy one extra session (2021-10-25) and
   about +1 pp of CAGR relative to the daily convention. A conservative reading
   of the 5-year result is therefore ~40% CAGR, still well above the 34.61%
   baseline. This is a convention difference, not look-ahead: the prior close
   is known before the first open.
4. **2021, 2019 and 2025 underperform the baseline.** These are strong,
   low-volatility melt-up years. The volatility budget moves to BIL when
   realised vol exceeds 1/3, and the crash vote sometimes exits on a −3% day
   that mean-reverts. The strategy is a risk-managed trend follower, not a
   constant 3x holder; it gives up some upside in the best years.
5. **The 5-year window is kind to the volatility filter.** 2022 was a clean
   high-vol bear market and 2023–2024 a strong recovery. A future high-vol
   melt-up (vol > 1/3 while QQQ rises) would see the strategy in BIL and lag.
   The 10-year window contains 2018 and 2020, which is some protection against
   a single-regime story, but it is still one asset complex.
6. **TQQQ is a daily-reset 3x fund.** The strategy can hold it for months.
   Daily reset, gap risk, and a −20% overnight gap are real. The crash vote
   reduces but does not eliminate gap risk: on 2020-03-12 and 2025-04-04 the
   gap happened before the first minute's trigger.
7. **No taxes, financing, borrow, or market impact.** About 23 fills a year
   create short-term gains and wash-sale exposure in a taxable account. A
   several-pp/yr tax drag would reduce the 10-year margin, though the 5-year
   margin is large.
8. **Data and corporate actions.** The harness adjusts QQQ/TQQQ/BIL for splits
   and dividends and handles BIL's 2017 reverse split. The 2026 year is
   partial (through 2026-10-23). The 1-minute data are adjusted with a daily
   factor, a small approximation.
9. **No shorting, no leverage beyond TQQQ.** The strategy is long-only and
   fully invested in one of TQQQ, QQQ, or BIL. It does not model margin or
   borrow.
10. **This is research, not financial advice.** The last five years contain one
    crash and one exceptional AI-led recovery; the forward expectation should
    be lower than the backtest.

---

## 9. Reproduce

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
python research\agents\ensemble-signals\strategy.py
```

`strategy.py` writes `result.json` with all metrics, yearly returns, ablations,
and the stability grid. The core function is `build_weights`; the harness call
is `bt.run(ts, opens, closes, weights, start, band=0.02, slippage_bps=...)`.

Files:

- `research/agents/ensemble-signals/strategy.py`
- `research/agents/ensemble-signals/result.json`
- `research/agents/ensemble-signals/report.md`

---

## 10. Sources

- Faber (2007), *A Quantitative Approach to Tactical Asset Allocation* —
  [SSRN 962461](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=962461)
- Gayed & Bilello (2016), *Leverage for the Long Run* —
  [SSRN 2741701](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2741701)
- Moreira & Muir (2017), *Volatility-Managed Portfolios* —
  [SSRN 2659431](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2659431)
- Zarattini & Antonacci (2024), *A Century of Profitable Industry Trends* —
  [SSRN 4857230](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4857230)
- Marshall, Nguyen & Visaltanachoti (2017), *Sampling frequency and the
  performance of different types of technical trading rules* —
  [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S1544612316303026)
- Book & Gnem (2021), *Ensemble Models for Trend Investing* —
  [KTH PDF](https://www.diva-portal.org/smash/get/diva2:1663269/FULLTEXT01.pdf)
- Massaad et al. (2024), *Refining and Robust Backtesting of A Century of
  Profitable Industry Trends* —
  [arXiv 2412.14361](https://arxiv.org/abs/2412.14361)
- Moskowitz, Ooi & Pedersen (2012), *Time Series Momentum* —
  [DOI](https://doi.org/10.1016/j.jfineco.2011.11.003)
- Connors & Alvarez (2008), *Short Term Trading Strategies That Work* —
  [book](https://www.amazon.com/Short-Term-Trading-Strategies-That-Work/dp/0071609174)
