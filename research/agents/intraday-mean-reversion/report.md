# Agent 3 — Intraday mean reversion on QQQ/TQQQ

**Verdict: PASS vs TQQQ buy-and-hold on both windows, and also above the passing
daily SMA-165 baseline on both windows.** The pass does **not** come from a
tradable intraday mean-reversion signal — every RSI / Bollinger / VWAP dip-buy
variant I tested loses money after 1 bp. It comes from the one intraday
overreaction pattern that survives costs: a **≥3 % intraday drawdown in a bull
regime predicts a weak close and a negative overnight gap**, so a 5-minute stop
that steps aside for the rest of the session and buys back at the next open
cuts the drawdown tail. Mean reversion enters through the *re-entry*, not
through the entry.

| Window | Strategy CAGR | Strategy max DD | Sharpe | TQQQ CAGR | TQQQ max DD | Pass |
|---|---:|---:|---:|---:|---:|:--:|
| 10y 2017-01-03 → 2026-10-23 | **50.96 %** | **44.83 %** | 1.12 | 39.28 % | 81.68 % | ✅ |
| 5y 2021-10-25 → 2026-10-23 | **35.50 %** | **36.29 %** | 0.90 | 13.47 % | 81.68 % | ✅ |

Daily-marked (15:59) drawdowns, directly comparable to the published benchmark:
**43.38 %** (10y) and **36.16 %** (5y). The 5-minute marked numbers above are
slightly *worse* (stricter) because they include intraday marks; the benchmark's
81.68 % is a daily-close figure.

Baseline comparison (daily-marked, 1 bp):

| | 10y CAGR / DD | 5y CAGR / DD |
|---|---|---|
| daily SMA-165 baseline (reproduced) | 45.23 % / 58.91 % | 34.61 % / 36.86 % |
| this strategy | **50.96 % / 43.38 %** | **35.50 % / 36.16 %** |

The 5-year edge over the baseline is inside noise (0.9 pp CAGR, 0.7 pp DD); the
10-year edge is material. A neighbouring setting (2.75 % stop) gives
50.59 % / 47.06 % (10y) and 39.01 % / 34.09 % (5y).

---

## 1. What was tested

Mandate: intraday mean reversion on QQQ/TQQQ, 165-day SMA regime filter, strict
stops and time exits, long-only, signals at bar *i*, fills at open *i+1*.

Tested, in order:

1. **Pure 5-minute MR entries** — RSI(2) < 5 / < 10, RSI(5) < 20, Bollinger(20,2)
   lower band, VWAP deviation (price < intraday VWAP − 0.25 % / − 0.40 %),
   morning capitulation (QQQ < −1 % / −1.5 % from the open before 11:00),
   each with one trade per day, hold to the 15:55 exit or signal exit.
2. **Same-day MR re-entry** after a stop (RSI(2) < 2 / < 5, deeper capitulation,
   VWAP reclaim).
3. **Opening-gap fade** (the classic overnight-overreaction trade).
4. **Intraday stop overlay on the daily regime** — the surviving variant.

Signals were computed on 5-minute bars (1-minute bars for the final control run).
Everything is in `strategy.py` and the batch scripts under `scratch/`.

## 2. Data and harness

* `data/intraday-hf/` adjusted 1-minute QQQ/TQQQ/BIL, regular session only
  (09:30–15:59 ET), 2016-01-04 → 2026-10-23. 5-minute panel: 211,558 bars,
  2,718 sessions. No new downloads.
* `research/bt.py` for `panel` / `run` / `stats` / `benchmark` / `yearly`.
  Weights are set at bar *i* from data through bar *i*, filled at open *i+1*;
  1 bp slippage on traded notional (5/10/20 bp reported).
* My harness reproduces the published baseline to within 0.2 pp: no-stop SMA-165
  on daily closes gives **45.23 % / 58.91 %** (10y) and **34.61 % / 36.86 %** (5y),
  against the README's 45.31 % / 58.71 % and 34.61 % / 36.86 %. TQQQ buy-and-hold
  reproduces at 39.28 % CAGR / 81.68 % DD.

## 3. Result 1 — the intraday mean-reversion signal is not tradable (negative result)

### 3.1 Conditional forward returns (TQQQ, regime-on, 5-minute bars)

Signal at the close of bar *i*, enter at open *i+1*, horizon in 5-minute bars:

| prior 30-min QQQ move | n | next 30-min TQQQ | win | TQQQ to close |
|---|---:|---:|---:|---:|
| ≤ −2.00 % | 1,189 | **+0.101 %** | 52.1 % | +0.083 % |
| −1.00 % … −0.70 % | 1,627 | **−0.054 %** | 48.2 % | −0.187 % |
| −0.70 % … −0.50 % | 3,020 | **−0.042 %** | 50.9 % | −0.148 % |
| −0.50 % … −0.30 % | 7,782 | +0.006 % | 53.4 % | −0.061 % |
| −0.30 % … −0.20 % | 8,803 | +0.013 % | 52.5 % | −0.008 % |
| all regime-on bars | 152,684 | +0.004 % | 52.1 % | −0.003 % |

Large and moderate declines **continue** over the next 30 minutes (5 bp below the
unconditional drift for the −1…−0.5 % band) and are worse into the close, so
"buy the dip" is the wrong side. The pattern is non-monotonic: only the extreme
≤ −2 % band bounces (+10 bp), and those bars cluster inside a handful of crash
episodes, so the effective sample is far smaller than 1,189 — not something to
build a strategy on. Bollinger z-scores show the same shape (a mild +1.6 bp
excess for z ∈ [−2.5, −1.5), nothing at the extreme), and the intraday-VWAP
deviation is even tighter — the deviation buckets only span ±0.2 %, so a
−0.25 % VWAP deviation is already a rare tail event and still does not pay
(variant below).

### 3.2 Strategy variants (10y, 1 trade/day, hold to 15:55)

| variant | 0 bp CAGR | 0 bp DD | 1 bp CAGR | 1 bp DD | 5 bp CAGR |
|---|---:|---:|---:|---:|---:|
| RSI(2) < 10, exit RSI(2) > 60 | +5.87 % | 32.0 % | −2.43 % | 45.5 % | −29.61 % |
| RSI(5) < 20, exit RSI(5) > 60 | −2.20 % | 50.1 % | −8.06 % | 65.0 % | not needed |
| Bollinger(20,2) lower band, exit mid-band | −2.65 % | 51.5 % | −9.00 % | 71.5 % | not needed |
| VWAP < −0.40 %, exit at VWAP | +2.25 % | 38.9 % | −1.03 % | 44.9 % | −13.13 % |
| QQQ < −1 % from open before 11:00, exit at close | +5.08 % | 20.5 % | +4.40 % | 20.5 % | +1.72 % |

There is a small **gross** edge in some variants (2–6 %/yr) and it is
entirely consumed by 1 bp of slippage plus 1–4 fills per day. The morning
capitulation variant keeps a tiny net edge but only because it is in the market
~5 % of the time; at 100 % allocation it is a 4 %/yr strategy, far below TQQQ.
The same conclusion appears in the public work cited at the bottom: RSI(2) on
QQQ loses to buy-and-hold even before costs once the 2010s bull market is
included ([tradeinsight](https://tradeinsight.info/posts/rsi2-has-no-edge)).

### 3.3 Opening-gap fade — also absent

Gap = open / prior close − 1, entry at 09:35, regime-on days:

| gap | n | 09:35 → 10:30 | 09:35 → close |
|---|---:|---:|---:|
| −1.0 % … −0.7 % | 86 | −0.158 % | −0.224 % |
| −0.7 % … −0.5 % | 100 | +0.003 % | +0.162 % |
| −0.5 % … −0.3 % | 177 | +0.049 % | −0.009 % |
| +0.3 % … +0.5 % | 241 | +0.035 % | +0.005 % |
| +1.0 % … +5.0 % | 142 | +0.083 % | **+0.678 %** (69 % win) |

Gaps *continue* in both directions; there is no fade. This is consistent with
the intraday-momentum / overnight-reversal literature rather than with a
gap-fade story.

## 4. The surviving strategy — SMA-165 regime + 3 % 5-minute crash stop

### 4.1 Exact rules

1. **Regime (daily).** At each session close, `QQQ close > 165-day SMA(QQQ close)`
   → target 100 % TQQQ; otherwise 100 % BIL. Executed at the **next 09:30 open**.
2. **Intraday stop (5-minute closes).** While long TQQQ, if
   `QQQ / previous_daily_close − 1 ≤ −3.0 %` at any 5-minute close, sell to BIL
   at the **next 5-minute open** and stay in BIL for the rest of that session.
   At most one stop per session.
3. **Re-entry.** Next session's 09:30 open if the regime is still on. This is the
   mean-reversion leg: buy back after the capitulation.
4. No other exits; overnight exposure is held while the regime is on. Long-only,
   weights ∈ {0, 1}, no leverage beyond TQQQ itself.

### 4.2 Why this and not "buy the dip"

Event study over the 48 stop events in the 10-year window (TQQQ returns,
trigger fill → next open):

| | mean | win rate |
|---|---:|---:|
| QQQ drawdown at trigger | −3.25 % | — |
| rest of session after exit (forgone) | +0.13 % | 48 % |
| overnight gap after exit (avoided) | **−0.69 %** | 56 % |
| next session open→close (captured) | **+1.17 %** | 62 % |

The intraday decline does **not** revert before the close (+0.13 %, i.e. flat);
what follows is a negative overnight gap and then a positive next session. So
the tradable mean reversion is across the *overnight boundary*, not within the
session — the same reversal that Lou–Polk–Skouras document between overnight and
intraday returns. Holding through it costs −0.61 % per event on average; stepping
aside and buying the next open is worth +0.61 % per event (t = 0.62, so
**not statistically significant** — see §6.4).

## 5. Results

### 5.1 Headline

| | 10y | 5y |
|---|---:|---:|
| CAGR (1 bp) | **50.96 %** | **35.50 %** |
| max DD, 5-minute marks | **44.83 %** | **36.29 %** |
| max DD, daily marks | **43.38 %** | **36.16 %** |
| Sharpe (5-minute / daily) | 1.12 / 1.10 | 0.90 / 0.89 |
| Sortino (5-minute) | 1.58 | 1.28 |
| volatility | 46.7 % | 45.0 % |
| fills | 269 | 97 |
| turnover (× start equity) | 3,703.8 | 250.8 |
| ending equity on $100k | $5.66 M | $0.46 M |
| TQQQ CAGR / DD | 39.28 % / 81.68 % | 13.47 % / 81.68 % |
| **pass vs TQQQ** | **yes** | **yes** |

(On this data the 5-year TQQQ CAGR computes to 13.88 %; the README's 13.47 % is a
slightly different start alignment. Either way the pass margin is wide.)

A "fill" is one leg; switching BIL→TQQQ counts as two fills (sell BIL, buy TQQQ).
269 fills is ~134 position changes over 9.8 years (≈13.7 per year, ≈6.9 TQQQ round
trips). Turnover is cumulative traded notional / *starting* equity; because equity
grows 56×, a single 100 % switch in year 10 already trades ~50× the starting
equity, so 3,704× is not 3,704 one-way full-portfolio trades.

### 5.2 Cost sensitivity

| slippage | 10y CAGR / DD | 5y CAGR / DD |
|---|---:|---:|
| 0 bp | 51.34 % / 44.68 % | 35.76 % / 36.21 % |
| **1 bp** | **50.96 % / 44.83 %** | **35.50 % / 36.29 %** |
| 5 bp | 49.43 % / 45.44 % | 34.50 % / 36.59 % |
| 10 bp | 47.54 % / 46.20 % | 33.25 % / 36.97 % |
| 20 bp | 43.84 % / 47.69 % | 30.79 % / 37.72 % |

Low turnover means the result survives even 20 bp per side, which is the
relevant stress for stop orders filled during a crash.

### 5.3 Yearly returns (1 bp)

| year | strategy | TQQQ | note |
|---|---:|---:|---|
| 2017 | +109.6 % | +113.0 % | full bull |
| 2018 | +2.9 % | −20.3 % | stop + regime avoid Q4 crash |
| 2019 | +40.1 % | +145.6 % | lag: regime off during May/Jun pullback |
| 2020 | +180.1 % | +103.6 % | stop avoids part of the COVID crash, then full recovery |
| 2021 | +56.8 % | +81.6 % | lag |
| 2022 | −25.1 % | −79.5 % | regime exits late (Jan), still −25 % |
| 2023 | +118.5 % | +191.0 % | lag in melt-up |
| 2024 | +72.2 % | +63.5 % | stop avoids the Aug 5 unwind |
| 2025 | +27.8 % | +33.5 % | April tariff crash handled |
| 2026 YTD | +10.6 % | +23.2 % | lag |

The strategy wins 4 of 10 calendar years. Its advantage is not year-by-year
return but avoiding the −80 % years; the cost is visible in strong bull years.

### 5.4 Drawdown anatomy

Worst episodes (5-minute marks): 2018-08-30 → 2019-06-03 (−44.8 %, the SMA-165
whipsaw year), 2020-02-20 → 2020-04-22 (−38.5 %), 2021-02-16 → 2021-03-05
(−37.4 %), 2023-07-19 → 2023-10-26 (−34.8 %). The 2018–19 grind, not COVID, is
now the binding drawdown.

## 6. Robustness

### 6.1 Parameter stability (stop level)

| stop | events | 10y CAGR/DD 1 bp | 10y 5 bp | 5y CAGR/DD 1 bp | 5y 5 bp |
|---:|---:|---:|---:|---:|---:|
| 1.00 % | 500 | 48.54 / 43.67 | 37.16 / 45.79 | 27.83 / 43.67 | 18.17 / 45.79 |
| 1.50 % | 309 | 44.96 / 39.94 | 37.87 / 42.57 | 20.88 / 35.43 | 15.20 / 37.97 |
| 2.00 % | 172 | 47.51 / 45.80 | 43.26 / 47.17 | 25.11 / 44.67 | 21.82 / 46.24 |
| 2.25 % | 125 | 51.72 / 47.60 | 48.46 / 48.60 | 29.43 / 41.78 | 27.12 / 42.89 |
| 2.50 % | 100 | 46.79 / 50.80 | 44.20 / 51.86 | 34.08 / 36.89 | 32.48 / 37.29 |
| 2.75 % | 68 | 50.59 / 48.41 | 48.63 / 49.15 | 39.01 / 34.84 | 37.80 / 34.84 |
| **3.00 %** | **48** | **50.96 / 44.83** | **49.43 / 45.44** | **35.50 / 36.29** | **34.50 / 36.59** |
| 3.25 % | 40 | 48.08 / 46.03 | 46.75 / 46.64 | 33.39 / 37.68 | 32.53 / 37.98 |
| 3.50 % | 29 | 48.24 / 47.58 | 47.17 / 48.17 | 29.21 / 41.47 | 28.54 / 41.75 |
| 4.00 % | 18 | 45.22 / 48.68 | 44.44 / 49.18 | 30.27 / 41.49 | 29.72 / 41.68 |
| 5.00 % | 5 | 46.09 / 57.64 | 45.54 / 57.85 | 34.61 / 40.82 | 34.12 / 40.82 |
| none | 0 | 45.23 / 59.74 | 44.75 / 59.87 | 34.61 / 40.82 | 34.12 / 40.82 |

Every stop level from 1 % to 5 % passes vs TQQQ on both windows, and every level
from 1 % to 4 % cuts 10-year drawdown by 8–20 pp relative to no stop. CAGR is
noisy across the grid (45–52 %) — that noise is honest: the effect is
concentrated in a few crash episodes. The *median* stop setting is ~48 % CAGR /
~47 % DD, so I do not claim the 3.0 % row is more than a good representative of
a robust family.

### 6.2 1-minute vs 5-minute execution

| bars | 10y CAGR/DD | 5y CAGR/DD | fills |
|---|---:|---:|---:|
| 5-minute | 50.96 / 44.83 | 35.50 / 36.29 | 269 |
| 1-minute | 51.52 / 44.47 | 35.60 / 36.48 | 266 |

Finer granularity changes almost nothing, i.e. the result is not a
bar-timing artifact.

### 6.3 Walk-forward

| period | strategy CAGR / DD / Sharpe | TQQQ CAGR / DD |
|---|---:|---:|
| 2017-01 → 2019-12 | 45.42 % / 44.83 % / 1.14 | 59.94 % / 59.36 % |
| 2020-01 → 2022-12 | 50.45 % / 38.47 % / 1.07 | −7.06 % / 82.29 % |
| 2023-01 → 2026-10 | 55.03 % / 36.29 % / 1.14 | 72.63 % / 61.84 % |

Stable across all three sub-periods: it always gives up return in clean bull
runs and always wins by a wide margin when the market falls.

### 6.4 Statistical honesty

The stop's return contribution is **not statistically significant**. On the 48
event days the stop-vs-hold difference averages +0.61 % with a 6.7 % standard
deviation (t = 0.62). Across all 2,465 days the difference in daily returns has
a t-stat of 0.56. The eight worst days for the stop are −5 % to −10 % (whipsaws);
the eight best are +5 % to +21 % (crash days). So this is a **tail-risk overlay**:
it is paid for by a fat left tail, not by a stable per-trade edge. The drawdown
reduction is structural (you cannot be long during the −10 % session), while the
CAGR improvement is sample-dependent. Treat 50.96 % as "high-40s to low-50s".

## 7. Design notes — why the other variants failed

* **Costs dominate at 5-minute frequency.** One round trip per day is ~2,460
  round trips per decade. At 2 bp round-trip the simple drag is ~49 % of starting
  equity; at 10 bp round-trip it is ~250 % of starting equity, leaving only
  ~8 % of terminal wealth. Any edge smaller than ~10 bp per trade is
  uninvestable at that frequency.
* **The reversion that exists is ~1 bp of excess return over 30 minutes** (mild
  dips, §3.1), i.e. below the 2 bp round-trip cost at 1 bp/side; only the rare
  ≤ −2 %/30-min band shows ~10 bp, and it is not enough independent events to
  trust.
* **Large declines continue intraday.** The profitable direction of "panic"
  trades is to *avoid* the rest of the session, not to buy it.
* **Same-day re-entry after a stop does not help.** RSI(2) < 5 re-entry
  re-enters almost immediately (RSI is pinned at 0 after a −3 % move) and gives
  back most of the stop's benefit (47.98 % vs 49.79 % 10y). RSI(2) < 2 or a
  −4.5 % deeper-capitulation rule adds +3.8 pp / +0.7 pp on 10y but only
  +0.1 pp / +0.3 pp on 5y, on ~20 extra events — inside noise, so neither is in
  the shipped strategy.
* **Opening-gap fades do not work** on QQQ in this sample; gaps continue.

## 8. Reproduction

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
python research\agents\intraday-mean-reversion\strategy.py            # 5m, 3% stop, 1bp
python research\agents\intraday-mean-reversion\strategy.py --rule 1min
python research\agents\intraday-mean-reversion\scratch\make_result.py # rewrites result.json
```

Files: `strategy.py` (rules + runner), `result.json` (all metrics, grid,
walk-forward, event study), `scratch/` (exploration batches, validation,
significance tests). No core files were modified.

## 9. Sources

* Connors & Alvarez, *Short Term Trading Strategies That Work* — the RSI(2)
  mean-reversion rule; settings surveyed at
  <https://finabase.io/learn/strategies/rsi-mean-reversion> and
  <https://www.quantifiedstrategies.com/rsi-mean-reversion-trading-strategy/>.
* "RSI(2) on QQQ has no edge — and costs aren't the reason",
  <https://tradeinsight.info/posts/rsi2-has-no-edge> — gross Sharpe 0.72 vs
  buy-and-hold 0.94, 2010–2025.
* Lou, Polk & Skouras, "A Tug of War: Overnight versus Intraday Expected
  Returns", <http://www.econ.yale.edu/~shiller/behfin/2015-04-11/lou_polk_skouras.pdf>
  — overnight and intraday returns predict each other negatively.
* "The Overnight Drift", NY Fed Staff Report 917,
  <https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr917.pdf>
  — end-of-day price pressure and reversal overnight.
* Alpha Architect, "Why the Last Few Minutes of Trading Might Matter More Than
  You Think", <https://alphaarchitect.com/end-of-trading/> — close-to-open
  reversal after end-of-day moves.
* Gao, Han, Li & Zhou (2018) intraday momentum, and the follow-up on overnight
  return predicting the first half hour:
  <https://www.sciencedirect.com/science/article/abs/pii/S1062940826001294>.
* Leveraged-ETF decay: FinLab, "Leveraged ETF Decay: Volatility Drag and Costs
  in 14 Funds", <https://finlab.finance/en/blog/leveraged-etf-decay> (TQQQ
  −15.2 pts/yr volatility drag, −6.9 pts/yr fees/financing, 2016–2026);
  Cheng & Madhavan (2009) via
  <https://quantpedia.com/shorting-leveraged-etfs-the-role-of-borrowing-costs-and-rebalancing-in-volatility-decay-strategies/>.
