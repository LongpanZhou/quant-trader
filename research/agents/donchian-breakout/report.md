# Donchian / Turtle breakout on QQQ 5-minute bars

**Agent:** donchian-breakout (research agent 6/10)
**Date:** 2026-11-25
**Data:** local adjusted 1-minute QQQ / TQQQ / BIL, 2017-01-03 → 2026-10-23
**Harness:** `research/bt.py` (`bt.panel` / `bt.run` / `bt.stats` / `bt.benchmark`), next-bar-open fills, 1 bp default slippage.

---

## Verdict

One variant passes the stated goal against TQQQ on **both** windows:

> **5-minute QQQ Donchian 55-bar breakout entry + daily QQQ > 165-day SMA regime exit, 100% TQQQ while long, 100% BIL otherwise.**

| Metric | 10y strategy | 10y TQQQ | 5y strategy | 5y TQQQ |
|---|---:|---:|---:|---:|
| CAGR | **46.36%** | 39.28% | **37.46%** | 13.47% |
| Max drawdown | **59.79%** | 81.68% | **40.82%** | 81.68% |
| Sharpe | **1.02** | 0.83 | **0.93** | 0.53 |
| Fills | 65 | — | 33 | — |
| Turnover (× initial equity) | 558.4× | — | 58.2× | — |
| TQQQ bar exposure | 82.2% | 100% | 73.8% | 100% |

Pass/fail vs TQQQ (README numbers): **PASS on 10y and 5y** for CAGR, max drawdown and Sharpe.
At 5 bp: 10y 45.97% / 59.91%, 5y 37.09% / 40.82% — still passes.

It **beats the daily baseline's CAGR** (45.31% 10y, 34.61% 5y) but has **slightly higher max drawdown** than the baseline (58.71% 10y, 36.86% 5y). It is therefore a genuine pass against TQQQ, but not a strict improvement over the existing daily baseline.

The central negative result: **classic Donchian/Turtle exits on minute bars do not work here.** They whipsaw and churn (4,999–10,183 fills over 10y) and collapse 10y CAGR to 4–17%. Only the daily regime exit survives.

---

## 1. Idea and sources

The Turtle system buys a break of the prior N-period high and exits on the opposite M-period low (System 1: 20/10; System 2: 55/20), with a 2N volatility stop. Donchian channels exclude the current bar from the channel, otherwise the current price can never break out. Dual Thrust is a sibling range-breakout: `range = max(HH-LC, HC-LL)` over the prior N days, buy above `open + k*range`.

I mapped those rules to the minute timeframe:

- **Entry:** QQQ 5-minute close above the highest high of the prior 55 five-minute bars (275 minutes, current bar excluded).
- **Regime filter:** QQQ daily close above its 165-day SMA. This is the same regime the daily baseline uses; it supplies the multi-day trend context that a 275-minute channel lacks.
- **Exit:** regime off only. The classic 10/20-bar Donchian exit was tested and rejected (see §5).
- **Asset:** TQQQ while long, BIL otherwise. No shorting, no leverage beyond TQQQ's own 3×.

Sources:

- Original Turtle Trading Rules (PDF), entries/exits/stops: <https://therobusttrader.com/wp-content/uploads/OriginalTurtle-Trading-Rules.pdf> and the Trading Blox mirror <https://www.tradingblox.com/originalturtles/originalturtlerules.htm>
- Turtle rule summary (System 1 20/10, System 2 55/20, 2N stop): <https://therighttrader.com/learn/trading-strategies/turtle-trading>
- Donchian construction, current bar excluded: <https://proea.app/en/blog/donchian-channel-strategy> (cites StockCharts: "Price Channels are based on prices prior to the current period")
- Dual Thrust definition: <https://www.quantconnect.com/research/15258/dual-thrust-trading-algorithm/>

---

## 2. Data and execution

- `bt.panel(("QQQ","TQQQ","BIL"), "2017-01-03", "2026-10-23", "5min")` with 500 calendar days of warmup.
- 211,558 five-minute bars, 2,718 sessions; 2,691 sessions have the full 78 bars. 27 sessions are early closes or have a few missing bars (e.g. 2020-03-09 is missing 09:35/09:40, so a 09:30 signal fills at 09:45).
- BIL's 1:2 reverse split (2017-11-30) is handled by the harness; all prices are adjusted.
- Fills: `weights[i]` is set at the close of bar `i` and executed at the open of bar `i+1`. Slippage is `slippage_bps` of traded notional. `band=0.02` is used, but with 0/1 targets it does not affect full entries/exits.
- Sharpe is annualised with `252 × 78` bars/year for 5-minute data and `252 × 390` for 1-minute data.

### Regime timing (no look-ahead)

The daily close is only known at the end of the day, so the regime state is applied as follows:

- for every bar of day `d` **except its last 5-minute bar (15:55)**, use the regime through `d-1`;
- at the **15:55 bar of day `d`** use the regime through `d` (the 15:55 bar's close is the 16:00 print);
- the weight set at 15:55 fills at the next session's **09:30 open**.

This is the standard "decide after the close, execute at the next open" convention. It does not use any future data. A 1-day execution lag is tested in §6.

---

## 3. Exact primary rules

```
every 5-minute bar i (QQQ):
    upper[i] = max(QQQ.high[i-55 : i])          # prior 55 bars, current excluded

daily:
    sma165[d] = mean(QQQ.daily_close[d-164 : d+1])
    regime[d] = QQQ.daily_close[d] > sma165[d]

entry at bar i if:
    regime[i] and QQQ.close[i] > upper[i]
    -> target TQQQ = 1.0 at bar i, fill at open i+1

exit at bar i if:
    not regime[i]
    -> target BIL = 1.0 at bar i, fill at open i+1

otherwise:
    if in position: TQQQ = 1.0
    else:           BIL  = 1.0
```

Parameters: entry lookback 55 bars, regime 165 days, no Donchian exit, no ATR stop, no time exit, no session exit in the primary. All are deliberately canonical (Turtle System 2 uses 55) rather than optimised. §6 shows the entry-N plateau.

---

## 4. Results

### 4.1 Headline metrics (1 bp)

| Window | CAGR | Max DD | Vol | Sharpe | Sortino | Ending equity | Fills | Turnover | TQQQ exposure |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 10y (2017-01-03 → 2026-10-23) | 46.36% | 59.79% | 49.60% | 1.02 | 1.42 | $4,181,657 | 65 | 558.4× | 82.2% |
| 5y (2021-10-25 → 2026-10-23) | 37.46% | 40.82% | 45.91% | 0.93 | 1.30 | $489,880 | 33 | 58.2× | 73.8% |

Starting equity is $100,000. "Turnover" is cumulative traded notional divided by **initial** equity; because equity compounds ~42×, it overstates the annual cost. The 5 bp test below is the cleaner cost measure.

Local 5-minute-marked TQQQ buy-and-hold for reference: 10y 39.33% / 82.29% / 0.84; 5y 14.22% / 82.29% / 0.53. The README's daily benchmark (39.28% / 81.68%, 13.47% / 81.68%) is used for pass/fail.

### 4.2 Pass/fail vs TQQQ

| Criterion | 10y | 5y |
|---|---|---|
| CAGR > TQQQ | 46.36% > 39.28% ✅ | 37.46% > 13.47% ✅ |
| Max DD < TQQQ | 59.79% < 81.68% ✅ | 40.82% < 81.68% ✅ |
| Sharpe > TQQQ | 1.02 > 0.83 ✅ | 0.93 > 0.53 ✅ |
| **Pass** | **YES** | **YES** |

### 4.3 vs the daily baseline

| Metric | Primary 10y | Baseline 10y | Primary 5y | Baseline 5y |
|---|---:|---:|---:|---:|
| CAGR | 46.36% | 45.31% | 37.46% | 34.61% |
| Max DD | 59.79% | 58.71% | 40.82% | 36.86% |
| Sharpe | 1.02 | 1.00 | 0.93 | 0.88 |

The primary adds **+1.05 pp** 10y CAGR and **+2.85 pp** 5y CAGR, but runs **+1.08 pp more** 10y DD and **+3.96 pp more** 5y DD. It is a CAGR-for-drawdown trade, not a free improvement.

Note on reproducibility: `bt.panel(..., "1D")` (minute-resampled daily) reproduces the baseline at 51.85% / 49.90% (10y) and 37.32% / 36.86% (5y), noticeably different from the README's 45.31% / 58.71%. Rebuilding the baseline from the Yahoo daily parquet (signal on adjusted close, fill next adjusted open) gives 44.29% / 58.59% and 32.80% / 36.87%, i.e. the README baseline is a Yahoo-daily implementation. The README figures are used for the comparison above; the discrepancy is a data-frequency/close-print effect, not a strategy difference.

### 4.4 Cost sensitivity

| Cost | 10y CAGR | 10y DD | 10y Sharpe | 5y CAGR | 5y DD | 5y Sharpe |
|---|---:|---:|---:|---:|---:|---:|
| 1 bp | 46.36% | 59.79% | 1.02 | 37.46% | 40.82% | 0.93 |
| 5 bp | 45.97% | 59.91% | 1.02 | 37.09% | 40.82% | 0.92 |

The strategy trades 65 times in 10 years (≈6.5 fills/year). At 5 bp the CAGR cost is only 0.39 pp and 0.36 pp. Costs are not the binding constraint for this variant.

### 4.5 Yearly returns (1 bp)

| Year | Strategy | TQQQ | Delta |
|---|---:|---:|---:|
| 2017 | +113.57% | +113.75% | −0.18 pp |
| 2018 | −3.32% | −20.34% | +17.02 pp |
| 2019 | +46.01% | +145.64% | −99.63 pp |
| 2020 | +72.12% | +103.59% | −31.47 pp |
| 2021 | +81.61% | +81.61% | 0.00 pp |
| 2022 | −23.27% | −79.51% | +56.24 pp |
| 2023 | +117.20% | +191.04% | −73.84 pp |
| 2024 | +48.31% | +63.54% | −15.23 pp |
| 2025 | +39.85% | +33.45% | +6.40 pp |
| 2026 (to 10-23) | +19.95% | +23.19% | −3.24 pp |

5y window: 2021 (partial) +15.62% vs +15.65%; 2022 −23.27% vs −79.51%; 2023 +117.20% vs +191.04%; 2024 +48.31% vs +63.54%; 2025 +39.85% vs +33.45%; 2026 +19.95% vs +23.19%.

The profile is classic trend-following: it lags in strong bull years (2019, 2023) and wins decisively in bear years (2018, 2022). 2022 is the only meaningfully negative calendar year. The 5y CAGR advantage comes almost entirely from avoiding 2022 (−23% vs −80%).

### 4.6 Drawdown episodes

| Window | Peak | Trough | Depth | Driver |
|---|---|---|---|---|
| 10y | 2020-02-19 14:40 | 2020-04-21 11:40 | −59.79% | COVID crash; the 165-day SMA was far below the February price, so the regime did not turn off until 2020-03-09. QQQ then closed at 196.42 on 2020-03-10 vs SMA 194.39, triggering a one-day re-entry that reversed −13% on 2020-03-11/12. |
| 5y | 2024-07-10 15:50 | 2024-08-05 09:30 | −40.82% | August 2024 yen-carry unwind; TQQQ gapped −14% at the 2024-08-05 open. |

The 10y drawdown is roughly the same as the daily baseline's 58.71% and is the price of staying long through a fast crash. The 5y drawdown is 4 pp worse than the baseline's 36.86% because the strategy's pre-crash equity peak was higher.

---

## 5. Variants tested

All variants use the same close-based 165-day regime and next-open fills. 1 bp costs. "Pass" is vs TQQQ (CAGR > 39.28%/13.47%, DD < 81.68%).

| Variant | Entry | Exit | 10y CAGR | 10y DD | 5y CAGR | 5y DD | Fills 10y | Pass? |
|---|---|---|---:|---:|---:|---:|---:|---|
| **Primary** | 5m 55-bar high | regime off | **46.36%** | **59.79%** | **37.46%** | **40.82%** | 65 | **YES** |
| Turtle 20/10 | 5m 20-bar high | 5m 10-bar low | 4.28% | 40.38% | 9.48% | 40.38% | 10,183 | no (CAGR) |
| Turtle 55/20 | 5m 55-bar high | 5m 20-bar low | 17.11% | 40.85% | 19.38% | 40.85% | 4,999 | no (CAGR) |
| Symmetric 55/55 | 5m 55-bar high | 5m 55-bar low | 37.74% | 39.53% | 33.98% | 28.02% | 3,033 | no (10y CAGR) |
| Slow 390/156 | 5m 390-bar high (5d) | 5m 156-bar low (2d) | 31.70% | 30.48% | 24.31% | 28.25% | 841 | no (10y CAGR) |
| Dual Thrust swing k=0.3 | prior-day range, open+0.3R | regime off | 48.40% | 49.88% | 34.18% | 40.82% | 65 | **YES** |
| Dual Thrust swing k=0.5 | open+0.5R | regime off | 45.34% | 50.81% | 30.18% | 42.44% | 65 | **YES** |
| Dual Thrust day trade k=0.5 | open+0.5R | 15:55 + 3×ATR | 6.74% | 34.19% | 6.21% | 24.16% | 3,513 | no (CAGR) |
| Primary + 3×5m ATR stop | 5m 55-bar high | regime or stop | 49.00% | 48.51% | 32.70% | 40.82% | 109 | yes, but 5y CAGR < primary |
| Primary + 5-day time exit | 5m 55-bar high | regime or 5d | 32.30% | 58.75% | 21.18% | 42.96% | 1,433 | no (CAGR) |
| Primary flat overnight | 5m 55-bar high | regime or 15:55 | −3.56% | 62.39% | −0.20% | 50.71% | 6,051 | no (CAGR) |
| Primary 1m entry 55 | 1m 55-bar high | regime off | 45.23% | 55.84% | 33.59% | 42.17% | 81 | yes, but weaker 5y |

### What the variants say

1. **Donchian exits are the problem, not the entry.** Fast exits (20/10, 55/20) sell the first pullback, then require a new high to re-enter. On 5-minute bars this happens constantly: 4,999–10,183 fills over 10y. At 1 bp the cost is tolerable but the *timing* loss is not — CAGR collapses to 4–17%. The symmetric 55/55 variant is the best of the Donchian-exit family at 37.74% (10y), still below TQQQ's 39.28%.
2. **Slow channels cut drawdown but also cut CAGR.** The 5-day/2-day channel (390/156) has the best risk profile in the study — 30.48% 10y DD, 1.22 Sharpe — but only 31.70% CAGR, failing the 10y CAGR test. There is no free lunch in widening the exit; you give up the upside.
3. **Dual Thrust works as a swing entry.** Holding the dual-thrust breakout until the regime turns off scores 48.40% / 49.88% (10y) and 34.18% / 40.82% (5y), passing vs TQQQ. It is a legitimate alternative to the Donchian entry, but its 5y CAGR is 3.3 pp below the primary's and its 10y DD is 10 pp lower. The **day-trade** version (flat at 15:55) collapses to 6.7% — see point 5.
4. **An initial ATR stop is not a robust improvement.** A 3×5m-ATR initial stop (≈1.8% on TQQQ) lifts 10y to 49.00% / 48.51% by cutting the COVID entry, but cuts 5y CAGR to 32.70%. A 2× stop gives 49.98% / 48.51% (10y) and 33.67% / 40.82% (5y). The stop helps one episode and hurts the other; it is not a free risk reduction.
5. **Overnight exposure is essential.** Forcing the strategy flat at 15:55 produces −3.56% (10y) and −0.20% (5y). TQQQ's return is overwhelmingly overnight; a pure intraday breakout cannot capture it. This is the single most important design finding: any passing TQQQ strategy must hold overnight.
6. **1-minute vs 5-minute.** The 1-minute 55-bar entry (55 minutes) gives 45.23% / 55.84% (10y) and 33.59% / 42.17% (5y): slightly lower CAGR, lower 10y DD, more fills. The 5-minute series is the better trade-off and is the primary.

---

## 6. Robustness

### 6.1 Entry-lookback stability (5m, regime exit, 1 bp)

| Entry N | 10y CAGR | 10y DD | 5y CAGR | 5y DD | Fills 10y |
|---:|---:|---:|---:|---:|---:|
| 20 | 46.13% | 59.79% | 36.92% | 40.82% | 73 |
| 30 | 46.60% | 59.79% | 38.17% | 40.82% | 69 |
| 40 | 46.27% | 59.79% | 38.17% | 40.82% | 69 |
| **55** | **46.36%** | **59.79%** | **37.46%** | **40.82%** | 65 |
| 70 | 47.34% | 59.79% | 36.06% | 40.82% | 57 |
| 100 | 47.28% | 59.79% | 36.06% | 40.82% | 57 |
| 200 | 50.96% | 48.51% | 34.73% | 40.82% | 53 |

The CAGR plateau is wide (46–51% 10y, 34.7–38.2% 5y) and the 10y DD is stable at 59.79% for N=20–100. The N=200 row's 48.51% DD is not a safer strategy: the longer lookback delays the 2020 re-entry and changes the pre-COVID equity peak. It is path-dependence, not risk reduction. 55 is the canonical Turtle System 2 number and sits in the middle of the plateau.

### 6.2 Execution lag

Weights shifted later by 1 bar, 2 bars and 1 day (78 bars):

| Lag | 10y CAGR | 10y DD | 5y CAGR | 5y DD |
|---|---:|---:|---:|---:|
| 0 (primary) | 46.36% | 59.79% | 37.46% | 40.82% |
| 1 bar (5 min) | 45.69% | 60.87% | 37.09% | 40.82% |
| 2 bars (10 min) | 44.82% | 61.31% | 36.76% | 40.82% |
| 1 day | 51.42% | 50.17% | 37.03% | 40.82% |

The edge degrades gracefully with 5–10 minutes of extra latency. The 1-day lag *improves* the 10y numbers because it sidesteps the one-day 2020-03-10 regime whipsaw; that is a single-episode artifact and is not claimed as an edge.

### 6.3 Costs and data

- 5 bp costs: 45.97% / 59.91% (10y), 37.09% / 40.82% (5y). Still passes.
- 27 of 2,718 sessions have missing/early-close bars. The only material one is 2020-03-09 (missing 09:35/09:40), which makes a 09:30 signal fill at 09:45. The regime exit is decided on the 15:55 bar and fills at the next 09:30 open, so it is unaffected by that gap.
- All signals use only data through the signal bar; fills are strictly next-bar opens. No look-ahead.

---

## 7. Why it works, and what it is not

The strategy is best understood as **the existing daily 165-SMA baseline with a momentum-confirmed entry**. The daily regime does the heavy lifting: it keeps the strategy in TQQQ for the 2019–2021 and 2023–2026 uptrends and out of the 2018 Q4 and 2022 bears. The 55-bar Donchian entry adds a small amount of entry discipline — it avoids buying the first weak bounce after a regime flip — which is worth about +1 pp 10y and +3 pp 5y CAGR versus the README baseline.

It is **not** a minute-level exit strategy. Every attempt to use the Donchian low, an intraday SMA breach, a trailing ATR stop or a time exit as the primary risk control either churned or gave up too much CAGR. The only robust exit is the slow daily regime.

This is a useful negative result: on liquid, strongly trending 3× ETFs, minute breakout *entries* have a small amount of value, but minute breakout *exits* are dominated by the daily trend filter. The cost of being whipsawed out of a 3× position is larger than the benefit of cutting a pullback early.

---

## 8. Limitations

- **Not a strict improvement over the daily baseline.** It wins on CAGR (both windows) but loses on max drawdown (both windows). A user who wants lower drawdown should prefer the baseline; a user who wants higher CAGR and still-acceptable drawdown can prefer this.
- **The 10y drawdown is high (59.79%).** It is a COVID crash plus a one-day regime whipsaw (2020-03-10/11). The strategy does not have a crash brake; a portfolio-level drawdown stop or a faster risk overlay could reduce it, but those are outside this mandate and were not tested here.
- **The 5y drawdown (40.82%) is driven by the August 2024 gap.** A gap cannot be stopped; the strategy was long TQQQ into the −14% open. The daily baseline had 36.86% in the same episode.
- **Long-only, no shorting.** The strategy holds BIL when out; it does not profit from bear markets beyond avoiding them.
- **Single instrument, single regime.** No cross-asset confirmation, no volatility targeting, no position sizing beyond 0/1.
- **Data gaps.** A handful of 5-minute bars are missing on high-volatility days; the exact fill on 2020-03-09/10 is sensitive to that. The 1-day-lag test shows the result is not dependent on a single fill, but the 10y drawdown number should be treated as ±1–2 pp of execution noise.
- **Parameter choice.** 55 is canonical, not optimised. The plateau (20–200) supports it, but the 10y DD is path-dependent and varies from 48.5% to 59.8% across the plateau.

---

## 9. Reproduction

```powershell
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
cd C:\Users\27175\Desktop\quant-trader-research
python research\agents\donchian-breakout\strategy.py
```

`strategy.py` loads the local 1-minute data, builds the 5-minute panel and daily regime, runs the primary plus all variants, writes `result.json`, and prints the summary above. Runtime is roughly 4–6 minutes on this machine (the 1-minute cross-check dominates).

Files:

- `strategy.py` — self-contained implementation and result generator
- `result.json` — machine-readable metrics (primary, cost sensitivity, yearly, variants, robustness, benchmarks, pass/fail)

---

## 10. Sources

1. Original Turtle Trading Rules, System 1 (20/10), System 2 (55/20), 2N stop: <https://therobusttrader.com/wp-content/uploads/OriginalTurtle-Trading-Rules.pdf>; mirror <https://www.tradingblox.com/originalturtles/originalturtlerules.htm>
2. Turtle rules summary and the entry/exit/stop table: <https://therighttrader.com/learn/trading-strategies/turtle-trading>
3. Donchian channel construction and the "prior N bars, current excluded" convention: <https://proea.app/en/blog/donchian-channel-strategy>; also <https://research.titanfx.com/technical-analysis/other-indicators/what-is-donchian-channel>
4. Dual Thrust rules (`range = max(HH-LC, HC-LL)`, `open + k*range`): <https://www.quantconnect.com/research/15258/dual-thrust-trading-algorithm/>
5. Harness and baseline definitions: `research/README.md`, `research/bt.py`.
