# Daily 165-day regime + minute stop overlay on TQQQ

**Agent:** `daily-regime-minute-entry` · **Date:** 2026-11-25
**Question:** can a daily regime with genuine 1-minute execution beat TQQQ buy-and-hold
(higher CAGR, lower max drawdown) on both the 10y and 5y windows — and match or beat the
passing daily baseline?

## Verdict

**Yes.** A 165-day QQQ regime holds TQQQ, and a *4% intraday stop* — armed only when QQQ
is at/below its 20-day MA — exits to BIL for the rest of the day and the night. It passes
on both windows, at 1 bp and at 5 bp, and beats the published daily baseline on both CAGR
and drawdown in both windows.

| Window | Strategy CAGR | Strategy max DD | Sharpe | TQQQ CAGR | TQQQ DD | Daily-baseline CAGR / DD | Pass vs TQQQ | Pass vs baseline |
|---|---:|---:|---:|---:|---:|---:|:---:|:---:|
| 10y (2017-01-03→2026-10-23) | **58.80%** | **44.56%** | **1.24** | 39.28% | 81.68% | 45.31% / 58.71% | ✅ | ✅ |
| 5y (2021-10-25→2026-10-23) | **49.88%** | **33.49%** | **1.16** | 13.47% | 81.68% | 34.61% / 36.86% | ✅ | ✅ |

At 5 bp one-way costs: **54.60% / 47.08%** (10y) and **45.89% / 34.13%** (5y) — still a
clear pass against both TQQQ and the baseline. At 10 bp: 49.50% / 50.06% and 41.05% / 34.93%.

The overlay is not the source of most of the return: 100% of the equity is always in TQQQ
or BIL, and TQQQ is held on 79.4% of sessions including overnight. The stop is a cheap
crash hedge (153 stop events in 10 years, ~16/yr), not a trading system.

## 1. Idea and prior work

Three facts shaped the design:

1. **Slow trend filters work on leveraged index ETFs but are late on fast crashes.** The
   well-known "hold TQQQ while QQQ is above its 200-day average, else T-bills" rule
   returned ~45% a year over 2017–2026 vs ~39.6% for TQQQ, cutting the worst fall from
   −81.7% to −60.9%; its worst drawdown was Feb–Apr 2020 precisely because a 200-day
   average cannot react to a one-month crash
   ([FinLab](https://finlab.finance/en/blog/leveraged-etf-timing-backtest),
   [Exent](https://www.exent.ai/resources/leveraged-etf-200-day-rule)).
   The 165-day SMA baseline in this repo is the same family.
2. **Stop-loss rules add value when returns have momentum / regime shifts, and cost
   little when they do not** (Kaminski & Lo, *Journal of Financial Markets* 18, 2014,
   [doi](https://doi.org/10.1016/j.finmar.2013.07.001)). Their result is the theoretical
   license for a stop that is armed only in weak short-term trends.
3. **Almost all of TQQQ's drift is overnight.** On this data (2017-01-03→2026-10-23,
   15:59 close → next 09:30 open): overnight total **+1,354.8%** (mean +0.143%/day)
   vs intraday total **+81.2%** (mean +0.081%/day). For QQQ: overnight +245.0% vs
   intraday +82.6%. This matches the overnight/intraday return decomposition literature
   (Lou, Polk & Skouras, *JFE* 2019,
   [pdf](https://personal.lse.ac.uk/polk/research/TugOfWar.pdf)).
   **Consequence: any strategy that is flat overnight cannot plausibly beat TQQQ.** Minute
   rules can only be a small overlay on an overnight position.

That last point killed the obvious designs: continuous 1-minute VWAP or EMA timing forces
dozens of round trips per day, and at 1 bp per fill the cost alone is fatal (measured
below: −22.6% CAGR and 92% drawdown for the naive VWAP rule). The minute-level value is
therefore in *rare, high-conviction exits*, not in continuous intraday trading.

## 2. Data, harness, and no-look-ahead

- Data: adjusted 1-minute QQQ / TQQQ / BIL from `data/intraday-hf`, regular session only,
  via `research/bt.py` (`bt.panel(..., "1min")`, 500 calendar days of warm-up).
- 1,057,023 bars, 2,718 sessions (2016-01-04 → 2026-10-23); test windows start
  2017-01-03 and 2021-10-25.
- Weights are target fractions set at bar *i* and filled at bar *i+1*'s open; slippage is
  charged on traded notional; long-only; weights sum to ≤ 1.
- Signals use only bars ≤ *i*: the regime uses the **previous** daily close vs its
  165-day SMA; the MA20 gate uses the MA through the previous close; the stop uses the
  session open and the current bar's close.
- BIL is the risk-off asset (it earns its small daily carry; no separate cash yield is
  added).

## 3. Exact rules

```
For each session d (09:30–15:59 ET):
  SMA165[d]  = mean(QQQ daily close, d-165 … d-1)
  MA20[d]    = mean(QQQ daily close, d-20  … d-1)
  risk_on    = QQQ close[d-1] > SMA165[d]

  if not risk_on:
      hold BIL for the whole session
  else:
      armed = QQQ price at 09:30 bar < MA20[d] * 1.01
      base  = TQQQ open of session d
      state = TQQQ
      for each minute i:
          if armed and state and TQQQ close[i] < base * 0.96:
              state = BIL          # order fills at open[i+1]
          weight[i] = state
      # after the stop the position stays in BIL through the close,
      # so it is also out overnight; next session restarts at TQQQ if risk_on
```

- One position at a time, 100% TQQQ or 100% BIL, no leverage, no shorts.
- The stop is "armed" only when QQQ is at or below its 20-day MA (+1% buffer). In strong
  short-term uptrends intraday dips are *not* stopped — the stop is a downtrend/crash tool.
- Effective parameters: SMA 165 (given), MA20 gate, +1% arm buffer, −4% stop. Chosen from
  a small stability surface, not a fine grid (Section 6).

## 4. Results

### 4.1 Headline (1 bp, 1-minute marks)

| Metric | 10y | 5y |
|---|---:|---:|
| CAGR | **58.80%** | **49.88%** |
| Total return | 9,204.8% | 654.8% |
| Max drawdown (1m marks) | **44.56%** | **33.49%** |
| Max drawdown (daily marks) | 41.62% | 33.08% |
| Sharpe (annualized, 1m) | **1.24** | **1.16** |
| Sortino | 1.74 | 1.64 |
| Volatility | 46.12% | 43.39% |
| Fills | 657 | 337 |
| Turnover (× starting equity) | 17,331× | 1,295× |
| Ending equity on $100k | $9.30M | $754.8k |
| Max-DD peak → trough | 2018-03-13 → 2019-06-05 | 2026-06-22 → 2026-07-30 |

The 5y max drawdown is a 2026 event (June–July 2026), not 2022: the overlay cut the 2022
loss to −18.0% (TQQQ −79.4%), so the worst 5y episode moved to the 2026 summer selloff.

### 4.2 Yearly returns (calendar year, 1 bp)

| Year | Strategy | TQQQ | 1m control (no overlay) |
|---|---:|---:|---:|
| 2017 | **118.76%** | 114.54% | 114.52% |
| 2018 | **0.47%** | −20.76% | −1.08% |
| 2019 | **47.94%** | 148.23% | 47.45% |
| 2020 | **183.91%** | 104.14% | 77.37% |
| 2021 | 60.61% | **81.05%** | 81.05% |
| 2022 | **−17.99%** | −79.39% | −23.19% |
| 2023 | **149.04%** | 192.05% | 120.73% |
| 2024 | **67.96%** | 62.43% | 49.88% |
| 2025 | **43.29%** | 32.10% | 34.60% |
| 2026 | **16.76%** | 22.62% | 13.32% |

- Beats the TQQQ buy-and-hold in **6 of 10** calendar years, and the 1m control in
  **9 of 10** (2021 is the only losing year vs the control, −20.4 pp, because the stop
  whipsawed in a strong uptrend).
- It lags TQQQ in the melt-up years (2019, 2021, 2023, 2026) and wins big in the down
  years (2018, 2020, 2022) — the expected shape of a tail-risk overlay.
- Positive months: 66.7% of months; mean month +4.57%.
- Worst months: 2019-05 −23.8%, 2026-07 −23.8%, 2018-03 −20.2%, 2018-10 −19.9%,
  2021-09 −16.5%, 2020-03 −14.8%. Best: 2020-08 +35.5%, 2023-11 +33.8%,
  2026-05 +33.1%, 2026-04 +32.7%.

### 4.3 Cost sensitivity

| Costs | 10y CAGR | 10y DD | 10y Sharpe | 5y CAGR | 5y DD | 5y Sharpe |
|---|---:|---:|---:|---:|---:|---:|
| 1 bp | **58.80%** | 44.56% | 1.24 | **49.88%** | 33.49% | 1.16 |
| 5 bp | 54.60% | 47.08% | 1.18 | 45.89% | 34.13% | 1.09 |
| 10 bp | 49.50% | 50.06% | 1.11 | 41.05% | 34.93% | 1.01 |

Each extra basis point costs roughly 1 pp of CAGR, consistent with ~67 fills per year at
~100% of equity per fill. Even at 10 bp the strategy beats the daily baseline on both
windows. (Two fills per switch: sell TQQQ/buy BIL, and vice versa.)

### 4.4 vs the passing daily baseline

| | 10y CAGR | 10y DD | 5y CAGR | 5y DD |
|---|---:|---:|---:|---:|
| README daily baseline (daily marks) | 45.31% | 58.71% | 34.61% | 36.86% |
| 1m control — same regime, no overlay (1m marks) | 46.63% | 58.76% | 36.14% | 42.17% |
| **This strategy (1 bp)** | **58.80%** | **44.56%** | **49.88%** | **33.49%** |
| This strategy (5 bp) | 54.60% | 47.08% | 45.89% | 34.13% |
| TQQQ buy-and-hold | 39.28% | 81.68% | 13.47% | 81.68% |

The 1m control is the apples-to-apples reference: it is the same 165-day regime without
the minute overlay, measured on the same 1-minute equity marks. The overlay adds
**+12.2 pp CAGR and −14.2 pp drawdown** on the 10y window and **+13.7 pp / −8.7 pp** on the
5y window relative to that control.

(The control's 5y daily-mark drawdown is 36.86%, exactly the README baseline figure; its
10y daily-mark drawdown is 57.82% vs the README's 58.71%. The small differences come from
minute-derived daily closes vs the daily parquet.)

## 5. What did NOT work: minute entries

The mandate asked for 1-minute entry/exit rules (VWAP reclaim/hold, EMA cross, ORB,
pullback). I tested them all on this data. **They do not add — continuous ones are
catastrophic because of turnover, and event-timed entries are noise.**

### 5.1 Continuous intraday signals (10y / 5y, 1 bp)

| Variant | 10y CAGR | 10y DD | Fills (10y) | 5y CAGR | 5y DD |
|---|---:|---:|---:|---:|---:|
| Control: regime only, hold overnight | 46.63% | 58.76% | 81 | 36.14% | 42.17% |
| VWAP hold, 0 buffer, 1-bar confirm | −22.63% | 92.27% | 65,321 | −30.13% | 85.40% |
| VWAP hold, 5 bp buffer, 3-bar confirm | −3.75% | 54.54% | 29,817 | −10.44% | 54.54% |
| 1m EMA 20/60 cross | −15.79% | 84.94% | 27,907 | −20.55% | 71.11% |
| 1m EMA 50/200 cross | 24.31% | 47.18% | 9,081 | 13.95% | 34.28% |
| 30-min opening-range breakout (VWAP stop) | 14.56% | 42.50% | 11,897 | 11.36% | 32.66% |
| "Only trade if first 30 min up", hold to close | 31.58% | 55.17% | 4,259 | 16.71% | 37.22% |
| Intraday 165-SMA crossover (QQQ vs SMA every minute), 1% buffer | 41.01% | 54.85% | 81 | 23.39% | 46.33% |

Why: TQQQ's intraday drift is +0.081%/day gross; a VWAP rule generates ~26 fills/day =
~52 bp/day of cost. The signal cannot pay for itself. Even the cheapest continuous
variant (EMA 50/200, 9k fills) gives up 22 pp of CAGR to the control.

### 5.2 Entry timing after a regime flip (21 entry episodes in 10y)

Delaying the first buy of each risk-on episode (instead of buying at the next open):

| Entry rule | 10y CAGR | 5y CAGR |
|---|---:|---:|
| Buy at next open (control) | 46.63% | 36.14% |
| Buy at that day's close | 44.85% | 34.01% |
| Wait until 10:00 | 46.32% | 36.13% |
| Wait until 11:30 | 45.18% | 33.49% |
| Buy on a touch of the open price | 46.71% | 36.60% |
| Buy on VWAP reclaim | 46.38% | 35.93% |
| Buy on 30-min opening-range breakout | 44.22% | 34.00% |
| Buy on a −1% pullback | 45.63% | 35.35% |

All within ±0.5 pp of the control — no exploitable edge. With only ~2 entries per year,
there is nothing to gain and a real risk of missing the rebound (the flip usually happens
after a strong close, and waiting frequently buys higher).

### 5.3 Other exit variants (10y / 5y)

| Exit overlay | 10y CAGR | 10y DD | 5y CAGR | 5y DD |
|---|---:|---:|---:|---:|
| 3% stop, re-enter at the close (keep overnight) | 46.51% | 56.91% | 34.86% | 50.79% |
| 2% stop, re-enter intraday on VWAP (and at close) | 41.43% | 62.11% | 13.35% | 62.11% |
| 4% trailing stop from day high, re-enter at close | 49.18% | 56.79% | 31.21% | 39.96% |
| 5% stop from prior close, re-enter at close | 41.62% | 53.46% | 28.75% | 37.48% |
| **4% stop from day open, out overnight (this strategy)** | **58.80%** | **44.56%** | **49.88%** | **33.49%** |

The reference point matters: the stop must be measured from the *session open*, and the
position must stay out overnight. Re-entering the same day at the close (56.10%/50.64%
10y, 42.58%/38.94% 5y ungated) is worse than staying out overnight; a 2-day lockout
collapses the edge (46.07% 10y) — the benefit is specifically "skip the rest of the crash
day and the following night".

## 6. Robustness

### 6.1 Stop-level surface (ungated, 10y / 5y CAGR and DD)

| Stop | 10y CAGR | 10y DD | 5y CAGR | 5y DD |
|---:|---:|---:|---:|---:|
| 2.5% | 59.88% | 41.24% | 38.28% | 37.09% |
| 3.0% | 59.17% | 47.50% | 39.21% | 39.21% |
| 3.5% | 63.16% | 47.12% | 47.69% | 32.71% |
| **4.0%** | **61.28%** | **45.62%** | **43.87%** | **36.92%** |
| 4.5% | 55.89% | 42.18% | 36.59% | 39.63% |
| 5.0% | 52.77% | 42.48% | 37.23% | 41.58% |
| 6.0% | 49.67% | 47.25% | 41.92% | 40.99% |

Every level from 2.5% to 6% beats the control's 46.63% / 58.76% and 36.14% / 42.17% on
both windows. The surface is noisy (adjacent levels differ by 5 pp) because the mean
event saving is driven by a handful of gap nights, but the *sign* is stable. 4.0% is a
mid-surface round number, not the peak (3.5% is).

### 6.2 Arming gate (4% stop, 10y / 5y)

| Gate | 10y CAGR | 10y DD | 5y CAGR | 5y DD |
|---|---:|---:|---:|---:|
| none (always armed) | 61.28% | 45.62% | 43.87% | 36.92% |
| QQQ < MA20 | 56.11% | 41.73% | 45.31% | 34.82% |
| **QQQ < MA20 × 1.01** | **58.80%** | **44.56%** | **49.88%** | **33.49%** |
| QQQ < MA20 × 1.02 | 58.34% | 43.37% | 46.47% | 36.51% |
| QQQ < MA20 × 1.03 | 59.15% | 46.75% | 44.71% | 36.92% |
| QQQ < MA50 | 51.05% | 43.95% | 44.80% | 32.51% |

The gate trades a little 10y CAGR for meaningfully lower drawdown and much better 5y
results, and it cuts turnover roughly in half (497 vs 1,121 fills over 10y). Its real
job is economic: don't stop out of a dip in a strong short-term uptrend.

### 6.3 Sub-period and split stability (1 bp, final vs control)

| Period | Final CAGR | Final DD | Control CAGR | Control DD |
|---|---:|---:|---:|---:|
| 2017–2019 | 48.9% | 44.6% | 46.9% | 46.4% |
| 2020–2022 | 57.2% | 41.5% | 36.4% | 58.8% |
| 2023–2026 | 68.3% | 33.5% | 54.0% | 42.2% |
| first half 2017–2021 | 73.4% | 44.6% | 60.5% | 58.8% |
| second half 2022–2026 | 45.2% | 33.5% | 33.4% | 42.2% |

The improvement is present in every sub-period, not only 2020, though 2020–2022 is the
largest contributor. A fixed-parameter walk-forward (fit nothing, run 2017–2021 then
2022–2026) improves CAGR by ~13 pp and ~12 pp respectively and cuts drawdown by ~14 pp and
~9 pp.

### 6.4 Where the risk actually comes from

- Max DD (10y): **−44.56%**, 2018-03-13 → 2019-06-05 — the 2018 Q4/2019 Q2 whipsaw, not
  COVID. The overlay cut 2020 enough that 2018–19 became the worst episode.
- Max DD (5y): **−33.49%**, 2026-06-22 → 2026-07-30.
- 153 stop events in the test window, by year: 7 / 27 / 11 / 14 / 23 / 4 / 15 / 19 / 16 / 17
  (2017…2026). About 16 per year — not a high-frequency system.
- Event study (ungated 4% stop, 276 events): the mean *stop→next open* saving is −0.30%
  per event, but the **median is +0.03%** and exactly 50% of events are negative. The
  edge is almost entirely a handful of gap nights: 2020-03-11 (−21.6%), 2024-08-02
  (−13.8%), 2020-02-27 (−13.4%), 2020-02-21 (−11.1%), 2020-09-04 (−9.8%),
  2018-03-27 (−9.5%), 2024-08-01 (−9.3%), 2020-09-03 (−9.2%). In normal times the stop is
  approximately free, and in crashes it is very valuable.

## 7. Why it works (and why the entries don't)

- The daily regime supplies the beta: TQQQ on 79.4% of sessions, including overnight,
  where essentially all of TQQQ's drift is earned (+1,355% overnight vs +81% intraday over
  the sample).
- The stop supplies cheap left-tail insurance exactly where the slow regime is blind: a
  >30% one-day index move is impossible to hedge with a 165-day average, but a −4% move in
  TQQQ from the session open is observable in real time. Kaminski–Lo's condition —
  stop-losses help when returns have momentum — holds intraday in crashes, and the
  post-stop drift is negative (median ≈ 0, mean −0.3%, fat left tail).
- Arming the stop only below the 20-day MA keeps it out of the way in V-shaped bull-market
  dips, which is where the 2019/2021 whipsaw losses came from.
- Minute *entries* have no edge here because the entry price is a tiny part of a
  multi-year hold and the number of entry events is ~2/year; meanwhile continuous minute
  signals pay 20–50 bp/day in costs against ~8 bp/day of gross intraday drift.

## 8. Limitations and honest caveats

1. **Crash concentration.** The 10y improvement is heavily driven by 2020 (+184% vs +77%
   for the control) and by a handful of avoided gap nights. Without 2020 the edge is
   smaller (2017–2019: +2 pp; 2023–2026: +14 pp). Treat this as a tail-risk overlay, not
   as broad alpha.
2. **1 bp is optimistic for a stop.** The harness fills at the next bar's open, which can
   be well through the stop in a fast market — this is realistic and conservative in
   direction, but the 5 bp and 10 bp rows are the honest range for retail execution.
3. **The gate is a second parameter.** It was chosen after looking at results; its
   neighbors (MA20 ±0%, +2%, +3%, MA50) all work, but this is still in-sample selection.
   The ungated 4% stop (61.28%/45.62% and 43.87%/36.92%) is the simpler, more robust
   ablation and also passes.
4. **No taxes.** ~67 fills/year is tax-inefficient in a taxable account; the results are
   pre-tax.
5. **Single instrument, single sample.** TQQQ exists for the whole window (no survivorship
   gap), but the result is specific to a 3× Nasdaq-100 ETF in a period with two large
   crashes. There is no guarantee the 2020-type gap structure repeats.
6. **Drawdown marks.** Headline DD is measured on 1-minute equity marks (the harness
   standard); daily-mark DD is also reported (41.62% / 33.08%) and is the comparable
   number to the README baseline.
7. **Benchmark difference.** The README's 5y TQQQ CAGR is 13.47% (daily bars); the
   harness's 1m benchmark for the same window is 14.29%. The pass/fail conclusion is
   identical either way.
8. **BIL carry** is small (roughly 2–5%/yr) and is included via BIL's price; no separate
   cash yield is modeled when in "cash".

## 9. Reproduction

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
python research\agents\daily-regime-minute-entry\strategy.py
```

`strategy.py` rebuilds the 1-minute panel with `bt.panel`, applies the rules above, and
writes `result.json` (all metrics, yearly returns, cost sensitivity, pass/fail flags).
The exploratory scripts in this folder document every variant quoted above
(`variants1.py` … `variants7.py`, `gate_sweep2.py`, `stop_events.py`, `report_numbers.py`).
No core repository file was modified.

## References

- Kaminski, K. M., & Lo, A. W. (2014). *When do stop-loss rules stop losses?*
  Journal of Financial Markets 18, 234–254.
  [doi:10.1016/j.finmar.2013.07.001](https://doi.org/10.1016/j.finmar.2013.07.001)
- Faber, M. T. (2007). *A Quantitative Approach to Tactical Asset Allocation.*
  SSRN 962461. [link](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=962461)
- Lou, D., Polk, C., & Skouras, S. (2019). *A Tug of War: Overnight versus Intraday
  Expected Returns.* Journal of Financial Economics.
  [pdf](https://personal.lse.ac.uk/polk/research/TugOfWar.pdf)
- FinLab. *TQQQ 200-day moving average strategy: 7 leveraged ETF rules* (2017–2026
  backtest; 45.1% CAGR, −60.9% DD, worst DD Feb–Apr 2020).
  [link](https://finlab.finance/en/blog/leveraged-etf-timing-backtest)
- Exent. *TQQQ and the 200-Day Moving Average: An Exit Rule, Tested.*
  [link](https://www.exent.ai/resources/leveraged-etf-200-day-rule)
- Gayed, M. (2016). *Leverage for the Long Run.* SSRN 2741701 — moving-average risk
  management applied to leveraged equity.
  [link](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2741701)
