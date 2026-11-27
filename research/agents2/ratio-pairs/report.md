# The TQQQ/QQQ leverage ratio as a froth gauge

**Agent:** `ratio-pairs` — **Date:** 2026-11-25
**Question:** does the trend or the mean reversion of the TQQQ/QQQ ratio predict TQQQ's
relative performance well enough to beat the round-1 winner?

## Verdict

**Yes — but with the sign inverted relative to the natural guess, and the mechanism is
crash avoidance, not alpha.**

The ratio's *trend* (price above its 20/60-day average) is a **contrarian** signal: buying
TQQQ because the ratio is above its own moving average loses 10–19 pp of CAGR. What works
is the opposite tail: when the ratio is far **above** its 200-day mean — a low-volatility,
strongly-trending melt-up in which leveraged exposure has compounded without paying drag —
TQQQ's next month is flat-to-negative and crash risk is elevated. Holding **QQQ instead of
TQQQ** during those sessions, while keeping the winner's 4% stop, strictly dominates the
round-1 winner on both windows.

| Window | Strategy CAGR / maxDD @1bp | @5bp | @10bp | Winner @1bp | TQQQ |
|---|---:|---:|---:|---:|---:|
| 10y (2017-01-03..2026-10-23) | **69.50% / 39.11%** | 63.46% / 41.75% | 56.22% / 45.03% | 58.80% / 44.56% | 39.28% / 81.68% |
| 5y (2021-10-25..2026-10-23) | **63.74% / 26.85%** | 58.00% / 27.72% | 51.12% / 28.80% | 49.88% / 33.49% | 13.47% / 81.68% |

- **Strict dominance** (higher CAGR *and* lower max DD than the winner) holds at 1 bp and
  5 bp on both windows. Against the winner's own 5 bp numbers (54.60% / 47.08% and
  45.89% / 34.13%) this strategy's 5 bp result is 63.46% / 41.75% and 58.00% / 27.72%.
  At 10 bp the 10-year drawdown is 0.47 pp *worse* than the winner
  (45.03% vs 44.56%) while CAGR is 6.7 pp higher; the 5-year window still dominates.
- **28/28 rolling 3-year windows** have a lower max drawdown than both the winner and TQQQ;
  **26/28** have a higher CAGR than both.
- The overlay fires on 21.5% of sessions (67 episodes in ten years), costs about 1.5 pp of
  CAGR per 1 bp of slippage, and leaves the winner's stop untouched.

Everything below is reproducible from `strategy.py` with the local adjusted 1-minute panel.

---

## 1. Idea

Three facts motivated the design.

1. **A leveraged ETF's ratio to its underlying is a decay meter.** Avellaneda & Zhang
   (2010) give the exact path-dependence formula

   ```
   L_t / L_0 = (S_t / S_0)^b * exp( (b - b^2)/2 * V_t + financing terms ),   V_t = realized variance
   ```

   For b = 3 this is `log L = 3 log S - 3 V`, so the log TQQQ/QQQ ratio is
   `2 log(S_t/S_0) - 3 V_t` ([SIAM](https://epubs.siam.org/doi/10.1137/090760805);
   [Avellaneda–Zhang PDF](https://math.nyu.edu/inmemoriam/avellaneda/LETFRISKPROF.pdf)).
   The ratio therefore records *both* how far QQQ has run and how cheap the leverage was
   on the way. That is a different object from QQQ's own trend, and it is the object this
   mandate is about.
2. **The drag is `≈ ½·L·(L-1)·σ² = 3σ²` for 3x.** An empirical decomposition of six LETF
   pairs puts the volatility break-even near 14% realized vol for 3x funds: below it
   leverage beats the naive multiple most of the time, above it leverage loses by 19–52
   points ([Adjusted Close](https://adjustedclose.com/leveraged-etf-decay)). TQQQ's
   realised financing + fee gap is ~7.2%/yr on top of the path effect. So periods with
   *low* realised variance are exactly when the ratio can run far above its own trend.
3. **Low-volatility melt-ups are when leverage and crowding build up, and the next shock
   is amplified.** This is the "volatility paradox" of Brunnermeier & Sannikov (2014,
   [AER](https://www.aeaweb.org/articles?id=10.1257%2Faer.104.2.379)): low VaR → low
   margins → higher leverage → more fragile system. The NY Fed's plain-English version
   notes that "low volatility in itself can be a catalyst for high future volatility"
   ([Liberty Street Economics](https://libertystreeteconomics.newyorkfed.org/2017/11/the-low-volatility-puzzle-are-investors-complacent/)).
   A ratio that is extended relative to its own 200-day mean is a direct, price-only
   read on that build-up.

The natural guess — "ratio in an uptrend, so hold TQQQ" — turns out to be the wrong sign.
Section 5 documents that negative result in detail.

### 1.1 What the ratio extension actually contains

A regression on the 10-year daily sample:

```
ext200  =  -0.106  +  2.067 * qqq_ext200  +  1.342 * (-(200d realized variance - its 400d mean))
R^2 = 0.978
```

The slope on QQQ's own extension is **2.07** — exactly the theoretical 2.0 — and the
residual is a variance term. So the ratio adds one genuinely new ingredient to a QQQ trend
signal: **how little volatility it took to get here.** On froth days the ratio's realised
20-day vol averages 1.9%/day versus 2.7%/day otherwise.

A 2×2 sort on prior-close extensions makes the incremental information explicit
(next-session open-to-open TQQQ return, 2017–2026):

| prior-close state | n | TQQQ mean | QQQ mean | hit rate |
|---|---:|---:|---:|---:|
| QQQ ext > 0.09 **and ratio ext > 0.18** | 584 | **−0.155%/day** | −0.044% | 53.6% |
| QQQ ext > 0.09 and ratio ext ≤ 0.18 | 677 | +0.251%/day | +0.092% | 56.1% |
| QQQ ext ≤ 0.09 | 1204 | +0.385%/day | +0.142% | 56.5% |
| QQQ ext ≤ 0.09 and ratio ext > 0.18 | 0 | — | — | — |

Within the *same* QQQ-extension bucket, the ratio split moves the next-day TQQQ mean by
**40 bp/day**. That is the incremental content of the ratio. Matched-frequency controls
confirm it: `QQQ ext200 > 0.12` fires on 649 days (similar to 584) and returns
55.48% / 39.11% versus the ratio rule's 69.50% / 39.11%.

Over a one-month horizon the same state is flat-to-negative: forward 20-day TQQQ return
after a froth close averages **−1.51%** (median +0.36%, 52.2% hit rate) versus +5.86% in
all other states; above 0.22 the mean is −4.89%.

The difference in means is −0.49%/day (t = −2.87), but the hit rates differ by only
2.6 pp: this is not a "win more often" edge, it is a **fat left tail**. The five worst
froth days sum to −67.9% in arithmetic TQQQ return. The overlay is a crash hedge that
happens to have paid for itself in this sample.

## 2. Data, harness, no look-ahead

- Data: adjusted 1-minute QQQ / TQQQ / BIL from `data/intraday-hf`, regular session only,
  via `research/bt.py` (`bt.panel`, 500 calendar days of warm-up before 2017-01-03).
  No other data was used.
- Fills: `bt.run(..., band=0.02, slippage_bps=...)`; every weight set from bar *i* is
  executed at bar *i+1*'s open, long only, weights sum to ≤ 1. Slippage is charged on
  traded notional.
- The daily ratio uses the **prior session's close** only. The overlay's threshold is
  evaluated on `ext200.shift(1)`; the session's positions are set from that value before
  the first minute.
- The 4% stop is a *minute* rule and fills at the next minute's open, exactly as in the
  round-1 winner.

## 3. Rules

Base (round-1 winner, unchanged):

1. Risk-on when QQQ's prior close is above its 165-day SMA; otherwise 100% BIL.
2. On risk-on sessions, arm a 4% stop from the session open only when QQQ's first-minute
   price is below its prior 20-day SMA × 1.01. If armed and TQQQ closes 4% below the open,
   sell at the next minute's open and stay in BIL for the rest of the session and the
   night. Re-enter next session if the regime is still on.

Ratio overlay (new):

3. At each close compute `ext = log(ratio / 200-day MA of ratio)`, where
   `ratio = TQQQ close / QQQ close`.
4. If the **prior** close's `ext > 0.18` (ratio ≥ 19.7% above its 200-day MA), hold **QQQ**
   instead of TQQQ for the next session, including overnight. The 4% stop still applies:
   if TQQQ (the 3x proxy) falls 4% intraday while the stop is armed, the book goes to BIL.
5. Nothing else: no shorts, no leverage beyond 100%, no intraday overlay in the headline.

Both assets in the pair are used; BIL is the cash leg. The stop fires on 160 days over ten
years, 26 of them on froth days (froth days are 27.5% of risk-on days, so the stop is
*less* active there — froth sessions are calmer).

## 4. Results

### 4.1 Headline

| | 10y CAGR | 10y maxDD | 10y Sharpe | 5y CAGR | 5y maxDD | 5y Sharpe |
|---|---:|---:|---:|---:|---:|---:|
| **This strategy @1bp** | **69.50%** | **39.11%** | **1.51** | **63.74%** | **26.85%** | **1.47** |
| Round-1 winner | 58.80% | 44.56% | 1.24 | 49.88% | 33.49% | 1.16 |
| TQQQ buy & hold | 39.28% | 81.68% | 0.84 | 13.47% | 81.68% | 0.54 |
| QQQ buy & hold | 20.67% | 37.30% | 0.96 | 14.10% | 37.30% | 0.71 |
| BIL | 2.37% | 0.24% | 1.60 | 3.72% | 0.05% | 2.46 |

Sortino 2.15 (10y) / 2.11 (5y); 889 fills over ten years (≈ 91/yr, mostly the 67 in/out
QQQ swaps on top of the winner's stop); ending equity $17.6m from $100k.

The drawdowns:

- 10y: peak 2018-08-30, trough 2019-06-05, **39.11%** on minute marks (36.65% on daily
  marks). This is the 2018–19 chop that also produced the winner's worst drawdown.
- 5y: peak 2026-06-22, trough 2026-07-30, **26.85%** (26.50% daily).

### 4.2 Costs

| slippage | 10y CAGR / DD | 5y CAGR / DD |
|---|---:|---:|
| 0 bp | 71.05% / 38.74% | 65.20% / 26.63% |
| **1 bp** | **69.50% / 39.11%** | **63.74% / 26.85%** |
| 5 bp | 63.46% / 41.75% | 58.00% / 27.72% |
| 10 bp | 56.22% / 45.03% | 51.12% / 28.80% |

~1.5 pp of CAGR per bp of one-way slippage, because a 100% position is turned over about
90 times a year. At 10 bp the 10-year result still beats the winner on CAGR by 6.7 pp but
is 0.5 pp worse on drawdown.

### 4.3 Yearly returns (1 bp)

| Year | Strategy | Winner | TQQQ |
|---|---:|---:|---:|
| 2017 | 115.91% | 118.76% | 114.54% |
| 2018 | 1.30% | 0.47% | −20.76% |
| 2019 | 52.33% | 47.94% | 148.23% |
| 2020 | 225.47% | 183.91% | 104.14% |
| 2021 | 81.45% | 60.61% | 81.05% |
| 2022 | −17.99% | −17.99% | −79.39% |
| 2023 | 154.95% | 149.04% | 192.05% |
| 2024 | 87.71% | 67.96% | 62.43% |
| 2025 | 75.37% | 43.29% | 32.10% |
| 2026 | 17.82% | 16.76% | 22.62% |

The overlay loses slightly in 2017 (the one clean low-vol grind where TQQQ's compounding
was a tailwind), ties 2022, and wins the other eight years — including 2026, where the
July drawdown is cushioned.

### 4.4 Rolling 3-year windows (quarterly starts)

| start | strategy CAGR / DD | winner CAGR / DD | TQQQ CAGR / DD |
|---|---:|---:|---:|
| 2017-01-01 | 50.3% / 39.1% | 49.1% / 44.6% | 59.3% / 59.4% |
| 2017-04-01 | 28.6% / 39.1% | 28.9% / 44.6% | 17.6% / 72.7% |
| 2017-07-01 | 45.8% / 39.1% | 46.3% / 44.6% | 43.4% / 72.7% |
| 2017-10-01 | 76.2% / 39.1% | 64.4% / 44.6% | 50.9% / 72.7% |
| 2018-01-01 | 72.9% / 39.1% | 63.1% / 44.6% | 57.1% / 72.7% |
| 2018-04-01 | 61.6% / 39.1% | 48.3% / 41.5% | 57.6% / 72.7% |
| 2018-07-01 | 76.8% / 39.1% | 63.5% / 41.5% | 64.1% / 72.7% |
| 2018-10-01 | 63.2% / 38.7% | 52.6% / 41.5% | 51.0% / 72.7% |
| 2019-01-01 | 110.3% / 32.0% | 91.5% / 41.5% | 112.2% / 72.7% |
| 2019-04-01 | 94.7% / 32.0% | 77.3% / 41.5% | 58.5% / 72.7% |
| 2019-07-01 | 93.0% / 31.4% | 75.8% / 41.5% | 13.5% / 76.7% |
| 2019-10-01 | 92.6% / 31.4% | 75.4% / 41.5% | 7.3% / 78.9% |
| 2020-01-01 | 70.5% / 31.4% | 56.7% / 41.5% | −7.9% / 82.3% |
| 2020-04-01 | 100.0% / 28.1% | 79.5% / 41.5% | 37.6% / 82.3% |
| 2020-07-01 | 85.6% / 28.1% | 70.9% / 41.5% | 19.3% / 82.3% |
| 2020-10-01 | 47.9% / 28.1% | 41.3% / 41.5% | 2.1% / 82.3% |
| 2021-01-01 | 57.2% / 28.1% | 49.7% / 41.5% | 4.2% / 82.3% |
| 2021-04-01 | 83.2% / 25.1% | 72.1% / 26.6% | 10.1% / 82.3% |
| 2021-07-01 | 75.0% / 25.1% | 64.6% / 26.6% | 7.5% / 82.3% |
| 2021-10-01 | 76.6% / 25.1% | 63.7% / 29.4% | 6.0% / 82.3% |
| 2022-01-01 | 57.5% / 24.2% | 49.6% / 29.4% | −0.9% / 81.1% |
| 2022-04-01 | 62.3% / 22.8% | 54.3% / 29.4% | 0.6% / 73.7% |
| 2022-07-01 | 75.2% / 22.8% | 66.5% / 29.4% | 53.7% / 62.2% |
| 2022-10-01 | 89.7% / 22.8% | 80.3% / 29.4% | 76.4% / 62.2% |
| 2023-01-01 | 104.1% / 22.8% | 81.3% / 29.4% | 84.0% / 62.2% |
| 2023-04-01 | 81.1% / 22.0% | 60.9% / 29.4% | 46.3% / 62.2% |
| 2023-07-01 | 94.6% / 22.0% | 68.3% / 29.4% | 59.9% / 62.2% |
| 2023-10-01 | 85.9% / 26.8% | 66.6% / 33.5% | 65.6% / 62.2% |

**28/28 windows have a lower drawdown than the winner and than TQQQ. 26/28 have a higher
CAGR than both.** The two CAGR losses are the 2017-04 and 2017-07 windows, by 0.3 and 0.5 pp
— both are the 2017 low-volatility grind, which is the known cost of the rule.

Median window CAGR: **76.4%** vs 64.1% (winner) and 44.9% (TQQQ).

### 4.5 Ablations

| variant | 10y CAGR / DD | 5y CAGR / DD |
|---|---:|---:|
| **Full: froth → QQQ + winner stop** | **69.50% / 39.11%** | **63.74% / 26.85%** |
| Froth overlay, no stop | 60.15% / 53.31% | 52.01% / 35.55% |
| Winner, no overlay (control) | 58.80% / 44.56% | 49.88% / 33.49% |
| Froth → BIL instead of QQQ | 73.26% / 39.11% | 69.72% / 26.00% |

Both halves of the design are load-bearing. The overlay alone (without the minute stop)
adds 1.4 pp of CAGR but 8.8 pp of drawdown; the stop alone (the round-1 winner) is 10.7 pp
of CAGR and 5.5 pp of drawdown behind. The combination is what dominates.

**BIL beats QQQ in-sample** by 3.8 pp (10y) and 6.0 pp (5y) because froth-day QQQ returns
are slightly negative (−4.4 bp/day). I did **not** make that the headline: it is a bet that
melt-ups reverse, and it would be badly wrong in a melt-up that continues. QQQ keeps 1x
exposure and still dominates the winner, so it is the defensible version.

### 4.6 Where the drawdown reduction comes from

67 de-risking episodes; the summed TQQQ return skipped is −90.2% (arithmetic). The ten
worst:

| episode | days | TQQQ skipped | QQQ skipped |
|---|---:|---:|---:|
| 2020-07-21 → 07-23 | 3 | −15.9% | −5.4% |
| 2020-09-16 | 1 | −12.8% | −4.4% |
| 2025-11-11 → 11-13 | 3 | −10.2% | −3.4% |
| 2021-11-30 → 12-01 | 2 | −9.6% | −3.3% |
| 2018-01-04 → 02-05 | 22 | −8.7% | −2.7% |
| 2026-06-09 | 1 | −8.7% | −2.9% |
| 2023-08-24 | 1 | −8.4% | −2.8% |
| 2025-10-27 → 11-06 | 9 | −8.2% | −2.6% |
| 2021-12-13 | 1 | −8.0% | −2.7% |
| 2020-11-05 → 11-10 | 4 | −7.2% | −2.5% |

The cost side is real too: the five most expensive episodes are 2020-11-12 → 2021-02-25
(71 days, +25.8% missed), 2020-01-03 → 2020-02-24 (+14.9%), 2024-06-11 → 2024-07-18
(+9.3%), 2026-05-07 → 2026-06-05 (+7.6%) and 2021-11-01 → 2021-11-26 (+7.1%).

## 5. The three mandated tests — all negative

The mandate listed three specific uses of the ratio. None of them works as stated; the
sign is inverted.

### 5.1 (a) Hold TQQQ while the ratio is above its 20/60-day MA

No QQQ regime, no stop, 10 years, 1 bp:

| Rule | CAGR | maxDD | fills |
|---|---:|---:|---:|
| ratio > MA20 → TQQQ, else QQQ | 36.08% | 64.50% | 501 |
| ratio > MA20 → TQQQ, else BIL | 27.10% | 56.64% | 501 |
| ratio > MA60 → TQQQ, else QQQ | 36.04% | 67.40% | 291 |
| ratio > MA60 → TQQQ, else BIL | 27.12% | 65.80% | 291 |
| TQQQ buy & hold | 39.28% | 81.68% | 1 |

Every version loses to buy-and-hold on CAGR. The reason is in the information
coefficients (Spearman, signal at close *t* vs forward return from the next open):

| signal | IC vs TQQQ 5d | IC vs TQQQ 60d |
|---|---:|---:|
| log(ratio/MA20) | −0.026 | −0.089 |
| log(ratio/MA60) | −0.036 | −0.189 |
| log(ratio/MA200) | −0.097 | −0.258 |
| 20-day ratio momentum | −0.024 | −0.111 |

The ratio's trend is **contrarian at 5–60 days**. A ratio that has risen relative to its
own past predicts *lower*, not higher, TQQQ returns.

### 5.2 (b) Fade extreme 1-minute / 5-minute ratio deviations

Define the 3x tracking deviation inside a session as

```
dev_t = log(TQQQ_t / TQQQ_prevclose) - 3 * log(QQQ_t / QQQ_prevclose)
```

(using 2 instead of 3 is a common error — it produces a series dominated by QQQ's own
return, not by tracking error). At the close `dev` has mean −8.7 bp and sd 20.3 bp: the
drag and the tracking error.

There is very strong mean reversion in this deviation: `corr(d_t, d_{t+5}) = −0.41`, and
fading the 5-minute change produced a 72.7% hit rate over 670 events with |Δdev| > 20 bp
(+9.6 bp per event before costs).

**It does not survive execution.** The event study uses the signal bar's close; the harness
fills at the next bar's open. Running the actual overlay on top of the full strategy:

| overlay | 10y CAGR / DD | fills |
|---|---:|---:|
| none (headline) | 69.50% / 39.11% | 889 |
| fade 60 bp, hold 5 min | 69.43% / 39.12% | 921 |
| fade 60 bp, hold 15 min | 69.84% / 38.96% | 921 |
| fade 100 bp, hold 5 min | 69.41% / 39.11% | 897 |
| fade 150 bp, hold 10 min | 69.50% / 39.11% | 889 |

The apparent edge is a one-bar microstructure artifact (the deviation is measured at a
timestamp you cannot trade). It is also small in absolute terms — 670 events × ~10 bp is
about 6%/yr gross if every event were traded at full equity, before the two fills per
event. **Not included.**

A daily version of the same idea — fade a 1-, 3- or 5-day ratio move — has no signal at
all: the next-day TQQQ-minus-3xQQQ excess is −2 to −6 bp in every decile of past ratio
change, with no monotonic pattern.

### 5.3 (c) Ratio momentum as a filter on the 165-day regime

No stop, 10 years:

| Rule | CAGR | maxDD |
|---|---:|---:|
| QQQ > 165d SMA only (control) | 46.63% | 58.76% |
| + ratio > MA20 | 26.11% | 45.11% |
| + ratio > MA60 | 32.80% | 46.74% |

Adding the ratio-trend condition costs 14–20 pp of CAGR for a 12–14 pp drawdown
improvement — a bad exchange when the base rule already cuts the drawdown from 82%. Reject.

## 6. Robustness

### 6.1 Parameter surface

10-year CAGR / maxDD, `ext{MA} > theta → QQQ`, grid run in full (35 points; all in
`surface.json`):

| MA \ theta | 0.14 | 0.16 | **0.18** | 0.20 | 0.22 |
|---|---:|---:|---:|---:|---:|
| 150 | 59.4 / 36.1 | 64.4 / 41.1 | 71.2 / 43.0 | 70.7 / 44.6 | 64.1 / 44.6 |
| **200** | 57.0 / 38.7 | 63.9 / 38.7 | **69.5 / 39.1** | 72.2 / 40.5 | 68.7 / 43.0 |
| 250 | 48.2 / 35.4 | 54.1 / 39.1 | 66.5 / 38.7 | 63.5 / 39.3 | 68.8 / 39.1 |

The winner's 58.80 / 44.56 sits below most of the surface. Every MA-150/200 cell with
theta ≥ 0.16 beats the winner on CAGR, and all but two also have a lower drawdown.
200/0.18 is not a spike: 150/0.18 is slightly better on the 10-year and worse on the
5-year (57.2% / 26.9%), 200/0.20 is better on CAGR and slightly worse on DD. 250 days is
weaker at low thresholds because it fires too often.

5-year at 200/0.18 is 63.74% / 26.85%; at 0.16 it is 56.39% / 24.46%; at 0.20, 62.67% / 26.85%.

### 6.2 Episode jackknife

Turning the overlay off during the *N* worst avoided episodes:

| dropped | 10y CAGR / DD |
|---|---:|
| 0 | 69.50% / 39.11% |
| 1 (2020-07) | 67.53% / 39.11% |
| 2 | 67.05% / 39.11% |
| 3 | 66.38% / 39.11% |
| 5 | 65.81% / 39.11% |

The result is not carried by a handful of days. Dropping the five best crash avoidances
still leaves 7 pp of CAGR over the winner.

### 6.3 Subsamples

| period | winner | this strategy |
|---|---:|---:|
| 2017-01-03 .. 2021-12-31 | 74.16% / 44.56% | 84.06% / 39.11% |
| 2022-01-01 .. 2026-10-23 | 44.35% / 33.49% | 55.70% / 26.85% |

Consistent in both halves.

### 6.4 Permutation test

At the daily level (TQQQ, except QQQ on masked days, open-to-open, no costs), 2000 random
masks with the same number of de-risk days in each calendar year:

- actual CAGR 53.34%; random p50 28.53%, p95 40.03%; **0.1% of random masks beat it**.
- actual max DD 80.85%; random p50 81.39% — the mask alone does *not* fix the drawdown.
  That is why the 165-day regime and the stop are still needed.

### 6.5 Look-ahead shift test

| signal timing | 10y CAGR / DD |
|---|---:|
| `ext200` at *t−1* (causal, used) | 69.50% / 39.11% |
| `ext200` at *t* (one day of look-ahead) | 34.98% / 40.47% |
| `ext200` at *t−2* | 63.93% / 39.11% |
| `ext200` at *t−3* | 69.91% / 39.11% |

Using *more* recent information is much worse, and the reason is instructive: `ext200` at
*t* already contains the crash day. The look-ahead version therefore sells *after* the drop
and re-enters *after* the rebound — the opposite of the causal rule. The causal rule works
because it is positioned *before* the shock. Lagging by one or two extra days changes
little, so the result is not a knife-edge alignment with a particular day.

## 7. Why it might not work

This is a 10-year sample with roughly 8–10 independent melt-up episodes; the t-stat on the
froth-day mean is −2.87, but the effective sample is much smaller than 584 days. Three
specific risks:

1. **Melt-ups can continue.** The rule gives up 3x exposure for months at a time. In
   2020-11 → 2021-02 it missed +25.8% of TQQQ over 71 sessions. If the next episode is a
   1999-style blow-off that runs another 12 months, the overlay will lag badly. The QQQ leg
   (rather than BIL) is the hedge against this, and it is why I did not headline the BIL
   variant.
2. **The threshold is a level, not a valuation.** `ext200` has no anchor; it can go higher
   than 0.18 for a long time. In this sample the maximum is 0.40 (2020-09). A regime with
   structurally lower volatility (e.g. a permanently lower VIX) would keep the signal on
   most of the time and turn the strategy into a QQQ-holder.
3. **It is a crash hedge, not alpha.** The mean advantage is concentrated in the left tail
   (hit rates 53.6% vs 56.4%). A sample without a Feb-2018, a Mar-2020, a Nov-2025 and a
   Jul-2026 would show the overlay costing money. The drawdown control is the part I would
   expect to persist; the +10.7 pp of CAGR is not something to underwrite.

I also tested and rejected: froth **plus** a short-term breakdown trigger (ext20 < 0,
5-day ratio return < 0, etc.). Those versions fire only 1–6% of the time and give back most
of the edge (57–62% CAGR, 42–45% DD). The level rule, not the turn, is what carries the
information.

## 8. Related literature

- **Avellaneda & Zhang (2010)**, *Path-Dependence of Leveraged ETF Returns*, SIAM J.
  Financial Mathematics — exact `(S_t/S_0)^b exp((b−b²)/2 V_t)` identity used above.
  <https://epubs.siam.org/doi/10.1137/090760805>
- **Cheng & Madhavan (2009)**, *The Dynamics of Leveraged and Inverse Exchange-Traded
  Funds* — daily re-leveraging, path-dependent value destruction, convexity vs decay.
  <https://www.researchgate.net/publication/228231757>
- **Trainor (2025)**, *Beyond Volatility Decay*, JRFM 19(1):20 — corrects the standard
  LETF expected-return arithmetic; the drag is state-dependent, not a constant fee.
  <https://www.mdpi.com/1911-8074/19/1/20>
- **Adjusted Close**, *Leveraged ETF "Decay" Is Not What You Think It Is* — six LETF pairs
  through 2026; drag ≈ 3σ²; the volatility break-even is ~14% realized for 3x funds;
  TQQQ's financing + fee gap ≈ 7.2%/yr. <https://adjustedclose.com/leveraged-etf-decay>
- **Brunnermeier & Sannikov (2014)**, *A Macroeconomic Model with a Financial Sector*, AER
  104(2) — the volatility paradox: low measured risk → higher leverage → more fragile
  system. <https://www.aeaweb.org/articles?id=10.1257%2Faer.104.2.379>
- **NY Fed, Liberty Street Economics (2017)**, *The Low Volatility Puzzle* — plain-English
  statement that low volatility can be a catalyst for high future volatility.
  <https://libertystreeteconomics.newyorkfed.org/2017/11/the-low-volatility-puzzle-are-investors-complacent/>
- **Hessel, Nam, Wang, Cunyu & Zhang (2017)**, *Shorting Leveraged ETF Pairs* — long/short
  LETF pair spreads mean-revert, and the profit is a bet on index mean reversion that dies
  in trends. Related evidence that the *pair* carries information beyond the index.
  <https://www.cxoadvisory.com/volatility-effects/monthly-rebalanced-shorting-of-leveraged-etf-pairs/>
- **FinLab (2026)**, *TQQQ 200-Day Moving Average Strategy* — the 200-day rule on TQQQ:
  45.1% CAGR, −60.9% DD, 2017–2026; 6 of 8 exits saw TQQQ rise while out. Benchmark
  context for the base strategy. <https://finlab.finance/en/blog/leveraged-etf-timing-backtest>
- **Exent (2026)**, *TQQQ and the 200-Day Moving Average: An Exit Rule, Tested* — 46.4%
  vs 42.5% CAGR, −54.8% vs −81.6% DD, 34 switches. <https://www.exent.ai/resources/leveraged-etf-200-day-rule>

## 9. Reproduction

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
python research/agents2/ratio-pairs/strategy.py
```

`strategy.py` rebuilds the panel from `data/intraday-hf`, runs the headline strategy and
the ablations, writes `result.json`, and prints the 10y/5y, cost, ablation and rolling
numbers above. `explore.py` (IC and quintiles), `cond_check.py` (conditional means),
`qqq_control.py` (QQQ-extension control + permutation), `robust.py` (parameter surface,
rolling windows, jackknife) and `fade_overlay.py` (intraday fade) are the analysis scripts.
