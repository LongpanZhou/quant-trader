# Opening-range breakout (ORB) on QQQ/TQQQ — agent report

**Verdict: PASS vs TQQQ on both windows with the *swing* ORB variant.** The
pure intraday ORB, which is the strategy most of the literature describes,
**fails decisively** on both windows. The passing strategy is an ORB entry
with an overnight swing hold gated by the QQQ 165-day SMA.

| Window | Strategy CAGR | TQQQ CAGR | Strategy max DD | TQQQ max DD | Sharpe (daily) | TQQQ Sharpe | Pass |
|---|---:|---:|---:|---:|---:|---:|---|
| 10y 2017-01-03 → 2026-10-23 | **48.98%** | 39.28% | **48.55%** | 81.68% | 1.06 | 0.83 | **PASS** |
| 5y 2021-10-25 → 2026-10-23 | **34.08%** | 13.47% | **42.17%** | 81.68% | 0.87 | 0.53 | **PASS** |

All figures use the shared harness (`research/bt.py`), next-bar-open fills,
1 bp slippage, `band=0.02`. 5 bp results are in §6 and still pass. The
drawdown column is the harness's minute-close max DD; on daily closes it is
48.14% (10y) and 37.18% (5y).

The strategy does **not** beat the passing daily baseline on the 5y window
(34.08% / 42.17% minute-DD vs 34.61% / 36.86% daily-DD) — it roughly matches
it. On 10y it beats the baseline on both CAGR and DD (48.98% / 48.14% daily-DD
vs 45.31% / 58.71%).

---

## 1. The arithmetic that shapes every ORB result here

TQQQ's return is overwhelmingly an **overnight** phenomenon. From the local
1-minute data (regular session, adjusted):

| Window | TQQQ close→close CAGR | TQQQ open→close CAGR | TQQQ close→open CAGR |
|---|---:|---:|---:|
| 2017-01-03 → 2026-10-23 | 39.28% | **6.25%** | **31.14%** |
| 2021-10-25 → 2026-10-23 | 13.88% | **2.41%** | **11.61%** |

A long-only, fully-invested **intraday-only** strategy can therefore capture
at most ~6.25%/yr of TQQQ drift over 10 years before costs, and ~2.4%/yr over
5 years. That is the entire intraday opportunity set; perfect timing could
multiply it, but no ORB variant came close to the 39.28% bar. This is the
single most important result of this agent: **a day-trading ORB on TQQQ
cannot beat TQQQ buy-and-hold under this harness's 1× notional cap**, no
matter how good the intraday signal is.

The literature's TQQQ numbers are not comparable: Zarattini & Aziz size each
trade to risk 1% of the account with a **4× intraday leverage cap**, so their
TQQQ position can be ~2–4× notional (6–12× QQQ beta). The harness here caps
the weight vector at 1.0, i.e. 1× TQQQ = 3× QQQ beta.

The only way to reach the target is to hold TQQQ overnight during bull
regimes. The daily baseline already does that. The question this agent then
asks is: **can the ORB improve the entries/exits of the overnight strategy?**
The answer is yes, modestly, on 10y, and roughly neutral on 5y.

## 2. Sources

1. Zarattini, C. & Aziz, A., *Can Day Trading Really Be Profitable? Evidence
   of Sustainable Long-term Profits from Opening Range Breakout (ORB) Day
   Trading Strategy vs. Benchmark in the US Stock Market*, SSRN 4416622
   (2023, rev. 2025). 5-minute ORB on QQQ: enter at 09:35 if the first
   5-minute candle closed up, stop at the first candle's low, target 10R or
   the close, 1% risk/trade, 4× leverage cap. 1,795 trades, 24% win rate,
   0.13R/trade, 675% total vs 169% for QQQ, 2016–Feb 2023; TQQQ variant
   1,484% total. <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4416622>
   (summary: <https://concretumgroup.com/can-day-trading-really-be-profitable/>)
2. Zarattini, C., Barbon, A. & Aziz, A., *A Profitable Day Trading Strategy
   For The U.S. Equity Market*, SSRN 4729284 (2024). 7,000+ US stocks,
   5/15/30/60-minute opening ranges, "stocks in play"; top-20 portfolio
   +1,600% net, Sharpe 2.81, 36% annualised alpha.
   <https://concretumgroup.com/a-profitable-day-trading-strategy-for-the-u-s-equity-market/>
3. mericck, *QQQ-Opening-Range-Breakout* (GitHub, 2026). Independent
   out-of-sample test, 2023–Sep 2026: 15-minute range, close-confirmed
   entry, next-open fill, stop at the other side of the range, 2R target,
   15:00 exit. +0.074R/trade before costs, +0.054R at 4¢/share round trip,
   +0.022R at 10¢; 2026 was negative.
   <https://github.com/mericck/QQQ-Opening-Range-Breakout>
4. OrderBlock.net, *Does the QQQ Opening Range Breakout Work Out of Sample?*
   (22 Oct 2026). Summarises the paper and the independent OOS decay; notes
   that the paper's best TQQQ variant (5% of 14-day ATR stop) implies a
   ~$0.08 stop and is not realistic.
   <https://orderblock.net/blog/qqq-opening-range-breakout-out-of-sample>

The OOS work is the reason this report does not stop at "the paper says
TQQQ ORB made 1,484%". The intraday edge is small after costs and decays out
of sample; our own 10y/5y intraday results agree with that (best 10.27% CAGR,
Sharpe 0.66).

## 3. Exact rules of the passing strategy (primary)

Universe: adjusted 1-minute QQQ/TQQQ/BIL, regular session 09:30–16:00 ET.
Long only. Weights are fractions of equity; flat = 100% BIL.

1. **Opening range (30 min):** `or_hi = max(TQQQ high, 09:30–09:59)`,
   `or_lo = min(TQQQ low, 09:30–09:59)`.
2. **Daily regime:** at the prior session's close, `regime = QQQ close >
   SMA165(QQQ daily close)`. `regime` is known before the next open. If
   `regime` is off, no entries that day and any open position is closed.
3. **Entry:** on the first 1-minute bar at/after 10:00 whose **close >
   or_hi**, set the weight to 100% TQQQ at that bar's close. The harness
   fills at the **next bar's open** (≈ the signal price, one tick later).
   No entries after 15:00. One position at a time; re-entry is allowed after
   a stop on a new breakout.
4. **Stop:** `or_lo` of the entry day. Checked on every subsequent 1-minute
   **low**; if breached, the exit signal is set on that bar's close and
   filled at the next open. No target; winners run.
5. **Regime exit:** on the first bar of a session whose prior-session regime
   is off, exit at the next open.
6. **Overnight:** the position is **held overnight** while the regime is on.
   This is the source of most of the return and the reason the strategy
   passes. There is no end-of-day flattening in the passing variant; the
   intraday variant (end-of-day exit) is tested and fails in §5.
7. Costs: 1 bp per fill on traded notional (5 bp sensitivity in §6).

No look-ahead: the OR window ends at 09:59 and entries start at 10:00; the
regime uses only the prior daily close; every fill is at the next bar's
open; stops use the bar's low and fill at the next open, which is
conservative (the realized stop loss can gap through the level).

## 4. Primary results (1 bp)

| Metric | 10y | 5y |
|---|---:|---:|
| CAGR | **48.98%** | **34.08%** |
| Total return | +4,879% | +333% |
| Max DD (minute closes) | 48.55% | 42.17% |
| Max DD (daily closes) | 48.14% | 37.18% |
| Sharpe (minute bars, harness) | 1.06 | 0.87 |
| Sharpe (daily equity) | 1.06 | 0.86 |
| Sortino | 1.49 | 1.23 |
| Volatility (annualised) | 49.2% | 46.2% |
| Fills | 129 | 61 |
| Turnover (× starting equity) | 1,248× | 96× |
| Round trips | 33 | 16 |
| Ending equity on $100k | $4.98M | $433k |
| TQQQ exposure | ~81% of minutes | ~74% of minutes |

The harness "exposure" field reads ~100% because BIL is an asset; TQQQ is
held ~77% of all minutes in the full sample (~81% over the 10y window, ~74%
over the 5y window; 100% in 2017 and 2021, 4.7% in 2022, ~79–82% in
2018/2019/2025, ~90–98% in 2020/2023/2024).

**Trade profile (10y, 33 reconstructed round trips):** win rate ~24%,
average trade +20.7%, median −1.5%, average hold 88 calendar days, longest
646 days. This is a trend-following payoff: many small stop-outs at −0.5%
to −1% and a handful of very large winners (e.g. Apr 2020 → Jan 2022 +338%,
Oct 2023 → Aug 2024 +70%, Sep 2024 → Mar 2025 +14.5%). The stop is tight
relative to TQQQ's daily vol (median TQQQ OR range ≈ 1.7%), so most attempts
die quickly. The low-ish win rate is expected and is not a defect.

**Drawdown episodes:** the 10y max DD is the COVID crash, 2020-02-19 →
2020-03-09 (−48.1% on daily closes). The 5y max DD is the July–September
2024 growth scare (−37.2% on daily closes, −42.2% on minute closes). The
165-day SMA exits late in both; an overnight gap through the stop is the
main tail risk.

## 5. Variants tested (1 bp, same harness)

`swing` = hold overnight while regime on; `intraday` = flat at 15:55.
All use the 165-day QQQ SMA regime unless noted. P = passes vs TQQQ on both
windows.

| Variant | 10y CAGR / DD | 5y CAGR / DD | Sharpe 10y/5y | Verdict |
|---|---:|---:|---:|---|
| **swing OR30 (primary)** | **48.98 / 48.55** | **34.08 / 42.17** | 1.06 / 0.87 | **PASS** |
| swing OR45 | 49.82 / 48.55 | 32.73 / 42.17 | 1.07 / 0.85 | PASS |
| swing OR60 | 49.65 / 48.55 | 32.21 / 42.17 | 1.07 / 0.84 | PASS |
| swing OR15 | 48.41 / 48.55 | 32.09 / 42.17 | 1.05 / 0.84 | PASS |
| swing OR5 | 48.33 / 48.55 | 31.44 / 42.17 | 1.05 / 0.83 | PASS |
| swing OR30, fixed 2% stop | 49.74 / 48.55 | 33.65 / 42.17 | 1.07 / 0.86 | PASS |
| swing OR30, fixed 3% stop | 48.50 / 48.69 | 33.69 / 42.17 | 1.05 / 0.86 | PASS |
| swing OR30, fixed 5% stop | 47.53 / 49.41 | 35.04 / 42.17 | 1.04 / 0.88 | PASS |
| swing OR30, 3×ATR trailing | 38.52 / 47.40 | 26.38 / 37.86 | 0.98 / 0.78 | fail 10y CAGR |
| swing OR30, 4×ATR trailing | 38.49 / 47.40 | 22.04 / 41.02 | 0.96 / 0.69 | fail 10y CAGR |
| swing OR30, 5R target | 35.37 / 40.92 | 18.26 / 38.20 | 0.96 / 0.64 | fail 10y CAGR |
| regime hold + ORB intraday stop | 30.26 / 39.69 | 21.81 / 39.69 | 0.95 / 0.79 | fail 10y CAGR |
| **intraday OR5, EOD exit** | 2.06 / 40.06 | 7.18 / 24.57 | 0.20 / 0.42 | **FAIL** |
| **intraday OR15, EOD exit** | 5.61 / 35.19 | 12.73 / 22.25 | 0.36 / 0.67 | **FAIL** |
| **intraday OR30, EOD exit** | 2.10 / 44.13 | 6.36 / 24.02 | 0.20 / 0.41 | **FAIL** |
| intraday OR15, first-candle entry, 10R | 10.27 / 26.57 | 13.15 / 16.85 | 0.66 / 0.86 | fail 10y CAGR |

Key readings:

- **The intraday ORB is a real but small edge.** The best intraday variant
  (OR15, first 15-minute candle direction as in the paper, 10R target, EOD
  exit) makes 10.27%/yr on 10y with a 26.6% DD and a 0.66 Sharpe, and
  13.15%/yr on 5y with a 16.9% DD and a 0.86 Sharpe. It is a *good*
  risk-adjusted day-trading strategy and a *terrible* way to beat TQQQ
  buy-and-hold, because it gives up the overnight drift and pays ~4,000
  fills. This is fully consistent with the OOS literature.
- **The swing hold is what makes it pass.** Holding overnight raises the
  10y CAGR from 2–10% to 48–50%, because that is where TQQQ's return is.
- **The OR window is not fragile.** OR5/15/30/45/60 all pass; 10y CAGR spans
  48.3–49.8% and 5y spans 31.4–34.1%. The 30-minute choice is the middle of
  a plateau, not a spike.
- **Stop choice is not fragile either.** OR-low, fixed 2%, 3%, 5% all pass.
  A trailing ATR stop or a profit target hurts the CAGR enough to fail 10y;
  the edge needs the fat right tail.
- **The regime filter is the load-bearing component.** With a 100-day SMA
  instead of 165, 10y CAGR collapses to 20.5% (whipsaw); with 200 days it is
  50.9%. 165 and 200 are a stable plateau, 100 is not. This is a genuine
  regime risk, not a free parameter. The 165-day choice is the one specified
  by the task and the daily baseline.
- **Max-hold variants were rejected as overfit.** Forcing an exit every 63
  sessions produced 53.2%/48.8% (10y) and 32.4%/36.8% (5y) with the QQQ
  signal, which looks better on 5y DD — but the neighbouring values are
  unstable (84 sessions: 36.3% 10y, fails; 21 sessions: 44.0% 10y, 21.1%
  5y). A 63-session spike is not a robust rule, so it is not the primary.

## 6. Cost sensitivity (5 bp)

| Metric | 10y | 5y |
|---|---:|---:|
| CAGR | **48.20%** | **33.43%** |
| Max DD (minute) | 48.55% | 42.17% |
| Sharpe (daily) | 1.05 | 0.85 |
| Fills / turnover | 129 / 1,201× | 61 / 94× |
| Pass vs TQQQ | **PASS** | **PASS** |

Costs barely matter because the strategy trades ~13 times a year. At 5 bp
the 10y CAGR drops 0.78 pp and the 5y drops 0.65 pp. This is one of the few
ORB designs where 5 bp is not fatal; the intraday variants, by contrast,
have 6,000–9,500 fills and are much more cost-sensitive.

## 7. Yearly returns (1 bp) vs TQQQ buy-and-hold

| Year | Strategy | TQQQ B&H | Note |
|---|---:|---:|---|
| 2017 | +114.52% | +114.54% | 100% TQQQ all year |
| 2018 | +10.11% | −20.76% | regime + stops avoided Q4 |
| 2019 | +43.85% | +148.23% | repeated stop-outs, 81% exposure |
| 2020 | +106.09% | +104.14% | COVID DD −48%, then rebound |
| 2021 | +81.05% | +81.05% | 100% TQQQ all year |
| 2022 | −22.86% | −79.39% | regime exit was late (Jan), mostly BIL |
| 2023 | +113.07% | +192.05% | 92% exposure, entered after Jan breakout |
| 2024 | +38.40% | +62.43% | Jul–Sep DD, 97.5% exposure |
| 2025 | +30.82% | +32.10% | 80% exposure |
| 2026* | +20.69% | +22.62% | to 2026-10-23 |

\* 2026 is a partial year (Jan 2 – Oct 23).

Nine of ten calendar years are positive; the only negative year is 2022,
and it is −22.9% against −79.4% for TQQQ. The strategy matches or beats
TQQQ in 2017, 2018, 2020, 2021, 2025 and 2026, and gives up upside in the
strongest melt-up years (2019, 2023, 2024) because it is not always fully
invested and gets stopped out of early attempts.

5y window detail (2021 starts 2021-10-25): 2021 +16.05%, 2022 −22.86%,
2023 +113.07%, 2024 +38.40%, 2025 +30.82%, 2026 +20.69%.

## 8. Pass/fail, explicitly

Against TQQQ buy-and-hold (official numbers from `research/README.md`):

- **10y:** CAGR 48.98% > 39.28% ✅; max DD 48.55% < 81.68% ✅; Sharpe 1.06 >
  0.83 ✅. **PASS.**
- **5y:** CAGR 34.08% > 13.47% ✅; max DD 42.17% < 81.68% ✅; Sharpe 0.87 >
  0.53 ✅. **PASS.**
- At 5 bp: 10y 48.20%/48.55%/1.05 and 5y 33.43%/42.17%/0.85 — **PASS**
  on both.

Against the daily baseline (45.31%/58.71% 10y; 34.61%/36.86% 5y):

- 10y: better CAGR (48.98 vs 45.31) and better daily-close DD (48.14 vs
  58.71). **Beats the baseline.**
- 5y: slightly lower CAGR (34.08 vs 34.61) and slightly worse daily-close
  DD (37.18 vs 36.86). **Does not beat the baseline on 5y; roughly matches
  it.** The passing claim is against TQQQ, not against the baseline.

## 9. Honest caveats

1. **This is not a day-trading strategy.** The passing variant holds
   overnight for weeks/months. The intraday-only ORB — the strategy the
   papers describe — fails to beat TQQQ by a wide margin (2–10% CAGR).
2. **The ORB entry is a timing filter, not the source of the return.** Most
   of the CAGR is TQQQ's overnight drift during regime-on periods. The ORB
   contributes by entering on strength after a regime flip, stopping out of
   failed attempts at ~−0.5%, and getting out before some (not all) of the
   worst days. 33 round trips in 10 years is a low activity level.
3. **Fat tails.** The 10y result depends on a few huge winners (2020–2022
   +338%, 2023–2024 +70%). The win rate is ~24%; a run of stop-outs is
   normal and the strategy can underperform for a year (2019, 2024).
4. **Regime risk.** The 165-day SMA is slow: the COVID DD was 48% and the
   2024 DD 37% before the exit. A faster 100-day filter is much worse
   (20.5% CAGR), so there is no easy fix. Overnight gaps through the stop
   are unhedged.
5. **5y is the weak window.** 34.08% is close to the baseline's 34.61% but
   the DD is 1–5 pp worse. The strategy's advantage is concentrated in the
   2018 and 2020 drawdowns, which are outside the 5y window.
6. **No leverage beyond 1× TQQQ.** The paper's TQQQ variant uses 2–4×
   notional; this harness caps weights at 1.0. The comparison to the
   paper's headline TQQQ return is therefore not apples-to-apples.
7. **Costs.** 1 bp is realistic for TQQQ at the open; 5 bp is the stress
   case and still passes. The intraday variants are far more cost-sensitive
   (6,000–9,500 fills) and are not viable at 5 bp.
8. **Data.** Local adjusted 1-minute QQQ/TQQQ/BIL only; no new downloads.
   BIL is used as the flat asset, as in the daily baseline.

## 10. Files

- `strategy.py` — self-contained, runnable: loads the local data, builds the
  weights, prints the 10y/5y metrics at 1 bp and 5 bp, and writes
  `result.json`.
- `result.json` — machine-readable metrics: windows × {1bp, 5bp}, yearly
  returns, pass flags, and the variant table.
- `report.md` — this file.
- Scratch/research scripts (not part of the deliverable, kept for
  reproducibility): `orb_core.py`, `bench.py`–`bench5.py`, `explore*.py`,
  `diagnose.py`, `trades.py`, `final_table.py`, `final_eval.py`.

Run:

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
python research/agents/opening-range-breakout/strategy.py
```
