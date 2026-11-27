# Overnight / first-hour TQQQ with a volatility crash filter

**Agent:** `overnight-crash-filter` (round 2, agent 17) · **Date:** 2026-11-25
**Mandate:** overnight-only and first-hour variants, 165-day regime, crash filter,
low turnover. Target: lower drawdown with CAGR within 2 pp of the winner, or
strict dominance, net of 1/5/10 bp costs.

## Verdict

**The pure overnight family fails; the first-hour extension wins on the 10-year
window at every cost level and is a near-tie on the 5-year.**

| | 10y (2017-01-03 to 2026-10-23) | 5y (2021-10-25 to 2026-10-23) |
|---|---:|---:|
| **Recommended (R), 1 bp** | **67.47% CAGR / 36.52% DD / 1.37 Sharpe** | **51.55% / 35.92% / 1.17** |
| R, 5 bp | 61.40% / 38.67% | 46.69% / 36.32% |
| R, 10 bp | 54.12% / 41.25% | 40.83% / 36.83% |
| Winner (round-1), 1 bp | 58.80% / 44.56% / 1.24 | 49.88% / 33.49% / 1.16 |
| Winner, 5 bp | 54.60% / 47.08% | 45.89% / 34.13% |
| Winner, 10 bp | 49.50% / 50.06% | 41.05% / 34.93% |
| TQQQ buy & hold | 39.28% / 81.68% | 13.47% / 81.68% |

- **vs the winner, 10y: strict dominance at 1, 5 and 10 bp** — higher CAGR by
  +8.7 / +6.8 / +4.6 pp with drawdown lower by 8.0 / 8.4 / 8.8 pp.
- **vs the winner, 5y: higher CAGR at 1 and 5 bp (+1.7 / +0.8 pp), 2.4 / 2.2 pp
  higher max DD.** At 10 bp it is a tie (40.83 vs 41.05 CAGR, 36.83 vs 34.93 DD).
  It does **not** achieve strict dominance on both windows at any cost level.
- **Consistency is materially better.** On 27 rolling three-year windows the
  strategy beats TQQQ on CAGR in 26/27 (winner 24/27) and on drawdown in 27/27,
  has a *minimum* 3y CAGR of 41.7% (winner 31.2%) and a maximum 3y drawdown of
  35.4% (winner 41.6%). Head-to-head it beats the winner on CAGR in 21/27
  windows, on drawdown in 21/27, and on both in 15/27.
- **The pure overnight variants fail the mandate.** Overnight-only (15:59 to
  09:30) with the crash filter makes 40.84% / 31.19% (10y) and 26.41% / 30.64%
  (5y) at 1 bp, falls to 19.26% / 8.68% at 5 bp and goes *negative* at 10 bp
  (-3.12% / -10.03%). Adding the first 30 minutes lifts it to 51.30% / 33.18%
  and 31.42% / 33.18% at 1 bp — lower DD than the winner, but 7.5 pp / 18.5 pp
  less CAGR, and it collapses at 5 bp (28.11% / 12.97%). Two round trips a day
  cost 25-30 pp of CAGR at 5 bp.

So: the answer to "can an overnight-only strategy with a crash filter beat the
winner?" is **no**, and the reason is structural (turnover, not signal). The
answer to "can a first-hour variant with a crash filter and a 4% stop beat it?"
is **yes on the 10-year window at all costs, and nearly on the 5-year**.

## 1. Idea and the evidence behind it

Three documented regularities and one mechanical fact:

1. **The US equity premium is earned overnight.** Cliff, Cooper & Gulen (2008)
   decompose the premium into open-to-close and close-to-open and find the
   overnight leg carries essentially all of it, for indices, futures and
   individual stocks ([SSRN 1004081](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1004081)).
   Lou, Polk & Skouras (2019, *JFE*) model the two blocks as separate
   clienteles and show momentum-type premia accrue overnight
   ([pdf](http://www.econ.yale.edu/~shiller/behfin/2015-04-11/lou_polk_skouras.pdf)).
   Haghani, Ragulin & Dewey (2022, *JOIM* 2024) call it the "grandmother of all
   anomalies" ([SSRN 4139328](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4139328),
   [Elm Wealth pdf](https://elmwealth.com/wp-content/uploads/2026/04/Elm-Night-Moves-Overnight-Drift.pdf)).
   Liquidnet's tick-data study puts the overnight share at ~65% of total return
   for Nasdaq-100 constituents ([pdf](https://liquidnet-dev.squarespace.com/s/PriceDiscovery-TacticsToTimeTrading-20210714-final.pdf)).
2. **A 3x fund inherits the overnight gap at roughly 3x, and the daily reset adds
   mechanical end-of-day flows** ([Cheng & Madhavan 2009](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1393995);
   [ETF.com on TQQQ's 2018 rebalancing](https://www.etf.com/sections/equity/one-bad-day-levered-qqq-etf-case-study)).
   On the local data TQQQ's overnight block compounds at **+29.9%/yr**
   (13.68 bp/day, t = 2.81) versus QQQ's +12.9%/yr, against **+7.1%/yr** for the
   TQQQ session (8.15 bp/day, t = 1.29) — and in-regime overnight is **+47.4%/yr**
   (17.78 bp/day, t = 3.81).
3. **The first hour is the second-best block, and high volatility is where the
   leverage decay lives.** The first 60 minutes adds +9.4%/yr gross (t = 1.53).
   FinLab's decay study finds that days opening with QQQ 20-day volatility above
   25% are 22.5% of sessions but carry 52.7% of TQQQ's volatility decay
   ([link](https://finlab.finance/en/blog/leveraged-etf-decay)) — the direct
   motivation for a 20-day-vol crash filter that *skips the overnight* when vol
   is extreme.
4. **Leveraged ETFs cannot be hedged through a gap.** A 3x fund resets at the
   close, so an overnight gap is realised at 3x with no intraday stop able to
   touch it. That is why this family needs an *ex-ante* filter (vol) rather than
   only an intraday stop.

Two things I expected to work and which the data rejects — both are reported in
section 7: exiting after a gap-down, and gating on the overnight gap.

## 2. Data, harness and look-ahead

- Local adjusted 1-minute QQQ / TQQQ / BIL from `data/intraday-hf`, regular
  session only, via `research/bt.py` (`bt.panel(..., "1min")`, 500 calendar days
  of warm-up). 1,057,023 bars, 2,718 sessions (2016-01-04 to 2026-10-23);
  the 10y window has 2,466 sessions, 2,034 of them regime-on.
- Weights are positions held during bar *i*, converted to the harness convention
  (`weights[i]` is executed at the open of bar *i+1*); slippage is charged on
  traded notional; long-only; weights sum to <= 1.
- **No-look-ahead audit.** Every signal is a function of bars <= *i*:
  the regime uses QQQ daily closes through *d-1*; the 20-day vol uses returns
  through *d-1*; the overnight entry is decided on the 15:58 bar and filled at
  the 15:59 open; the afternoon signal is the QQQ 10:29 close and fills at the
  10:30 open; the stop uses the current bar's close and fills at the next open.
  A truncation test (`verify.py`) rebuilds the entire weight path from panels
  cut at six different dates (2017-03, 2019-03, 2021-07, 2023-07, 2025-02,
  2026-05) and gets **bit-identical weights** every time.
- `fast_sim` (in `lab.py`) replicates `bt.simulate` exactly (max relative equity
  difference 0.0e+00 on every test weight set, 1 bp and 5 bp), which is what
  makes the 160+ variant grids affordable. The round-1 winner re-runs at
  **58.80 / 44.56 / 49.88 / 33.49** at 1 bp — identical to its report.

## 3. Exact rules (recommended strategy R)

```
For each session d:
  S  = 165-day SMA of QQQ daily closes through d-1
  C  = QQQ close of d-1
  regime ON  if C > 1.02*S ; OFF if C < 0.98*S ; else unchanged

  vol20 = annualised stdev of QQQ daily log returns, 20 days through d-1
  night_ok = regime ON and vol20 <= 35%

  # overnight + first hour
  if night_ok:  buy TQQQ at the 15:59 open (decision bar 15:58)
  hold through the next session's first hour, to the 10:30 open
  # (the position is only held past 09:30 if last night's night_ok was true)

  # crash filter inside each held block
  while long in the morning, if TQQQ < session_open * 0.96 -> sell at the next
  minute's open; the afternoon is then only re-entered at 10:30 if the
  first-hour signal below is on
  while long in the afternoon, the same 4% stop from the session open applies
  and the position stays out for the rest of the session

  # afternoon
  r60 = QQQ(10:29) / QQQ(09:30) - 1
  if regime ON and r60 >= -0.5%:  hold TQQQ 10:30 -> 15:59
  else:                            cash

  # risk-off
  if regime OFF: 100% BIL
  # overnight leg is re-entered at 15:59 whenever night_ok
```

- One position at a time, 100% TQQQ or 100% BIL, no leverage beyond TQQQ, no
  shorts. Band 2% on the regime, 4% stop from the session open.
- Parameters: SMA 165 (repo reference), band 2% (round-1 time-of-day), 60-minute
  morning block (round-1 intraday-momentum), stop 4% (the winner's), vol 20 days
  and 35% annualised (approximately the 95th percentile of the sample), threshold
  -0.5%. Every one of these is a round number inherited from prior work or a
  standard risk measure; the one chosen here is the -0.5% threshold (section 8.4
  shows the surface and why it is the cost-robust choice).
- Turnover: **905 fills over 10 years (91/yr), 39,538x start equity**; the
  position is in TQQQ on 66.9% of bars and BIL on 22.0%.

## 4. Results

### 4.1 Headline and cost sensitivity

| Costs | 10y CAGR | 10y max DD | 10y Sharpe | 5y CAGR | 5y max DD | 5y Sharpe |
|---|---:|---:|---:|---:|---:|---:|
| 0 bp | 69.03% | 35.97% | 1.39 | 52.79% | 35.81% | 1.18 |
| **1 bp** | **67.47%** | **36.52%** | **1.37** | **51.55%** | **35.92%** | **1.17** |
| 5 bp | 61.40% | 38.67% | 1.29 | 46.69% | 36.32% | 1.09 |
| 10 bp | 54.12% | 41.25% | 1.19 | 40.83% | 36.83% | 1.00 |

- Total return 156.7x (10y) and 7.0x (5y); $100k grows to $15.67M / $797.6k.
- Annualised vol 45.2% / 44.3%; exposure (bar-weighted) 88.1% / 88.4%.
- Max-DD window: **2020-02-19 to 2020-05-15** (10y, 36.52%) and
  **2024-07-15 to 2024-08-05** (5y, 35.92%, the yen-carry unwind).
- On **daily marks** the drawdowns are 35.40% (10y) and 31.28% (5y); the winner's
  are 41.62% and 33.08%. On daily marks R therefore has the lower 5y drawdown;
  the 4.6 pp gap between minute and daily marks on the 5y is an intraday trough
  in the August 2024 crash that recovered by the close.
- Cost drag is only -1.6 pp at 1 bp, -7.6 pp at 5 bp and -14.9 pp at 10 bp over
  the 10 years. The pure overnight variants lose 28-30 pp at 5 bp; this is the
  "low turnover" requirement actually being met.

### 4.2 Yearly returns (1 bp)

| Year | R | Winner | TQQQ |
|---|---:|---:|---:|
| 2017 | **+140.9%** | +118.8% | +114.5% |
| 2018 | **+44.3%** | +0.5% | -20.8% |
| 2019 | **+61.9%** | +47.9% | +148.2% |
| 2020 | +134.8% | **+183.9%** | +104.1% |
| 2021 | **+70.3%** | +60.6% | +81.1% |
| 2022 | -22.6% | **-18.0%** | -79.4% |
| 2023 | **+209.5%** | +149.0% | +192.0% |
| 2024 | **+81.6%** | +68.0% | +62.4% |
| 2025 | +41.6% | **+43.3%** | +32.1% |
| 2026 YTD | +3.4% | **+16.8%** | +22.6% |

Six wins, four losses against the winner. Every year is positive except 2022.
The losses are informative: **2020** (the winner's stop-out-and-stay-out rule
caught the March gap nights better than the vol filter), **2022** (the January
leg before the regime flipped), **2025** (a near-tie) and **2026** (the
April-June rebound was earned intraday, and the first-hour rule kept the
strategy out of part of it). That last one is the family's core risk: if the
drift migrates from night to day, this strategy underperforms.

### 4.3 Rolling three-year windows

Quarterly-start, 3-year windows with full data (`rolling3` in `lab.py`):

| | R 10y | Winner 10y | R 5y | Winner 5y |
|---|---:|---:|---:|---:|
| Windows | 27 | 27 | 8 | 8 |
| CAGR range | 41.7 - 100.2% | 31.2 - 87.4% | 54.4 - 100.2% | 49.2 - 87.4% |
| Max 3y drawdown | **35.4%** | 41.6% | **31.3%** | 33.1% |
| Beats TQQQ CAGR | **26/27** | 24/27 | 8/8 | 8/8 |
| Lower DD than TQQQ | 27/27 | 27/27 | 8/8 | 8/8 |
| Head-to-head vs winner | 21/27 CAGR, 21/27 DD, 15/27 both | - | - | - |

There is no 3-year window in which R makes less than 41.7% a year. The weakest
head-to-head windows are all 2019-2020 starts (the winner's stop shines in the
COVID crash); the strongest are 2021-2024 starts (R's first-hour rule avoids the
2022 afternoon continuation).

### 4.4 Sub-periods (1 bp)

| Period | R CAGR / DD | Winner CAGR / DD |
|---|---:|---:|
| 2017-01-03 to 2019-12-31 | **78.9% / 36.1%** | 48.9% / 44.6% |
| 2020-01-01 to 2022-12-31 | 47.1% / 36.5% | **56.7% / 41.5%** |
| 2023-01-01 to 2026-10-23 | **75.2% / 35.9%** | 67.5% / **33.5%** |
| first half (2017 to 2021-10-22) | **86.6% / 36.5%** | 69.3% / 44.6% |
| second half (2021-10-25 to 2026) | **51.6% / 35.9%** | 49.7% / **33.5%** |

The improvement is present in two of three sub-periods and in both halves. The
2020-2022 block is the one place the winner is clearly better, and it is the
COVID crash.

## 5. The pure overnight family: an honest negative

Same regime machinery, no conditional afternoon — just TQQQ overnight, or
overnight plus the first 30 minutes, plus the crash filter. 2% band on the
165-day SMA, 20-day vol filter at 35% (or 95th percentile where marked).

| Variant | 10y 1 bp | 10y 5 bp | 10y 10 bp | 5y 1 bp | 5y 5 bp | 5y 10 bp |
|---|---:|---:|---:|---:|---:|---:|
| P1 overnight only, band 2%, vol<35% | 40.84 / 31.19 | 19.26 / 32.96 | -3.12 / 51.58 | 26.41 / 30.64 | 8.68 / 32.96 | -10.03 / 47.68 |
| P1 without the vol filter | 39.79 / 46.08 | 18.37 / 46.81 | -3.86 / 52.43 | 26.41 / 30.64 | 8.68 / 32.96 | -10.03 / 47.68 |
| P2 overnight + first 30m, band 2%, vol pct<95% | 51.30 / 33.18 | 28.11 / 35.39 | 4.05 / 43.61 | 31.42 / 33.18 | 12.97 / 35.39 | -6.49 / 43.61 |
| P2 without the vol filter | 49.56 / 47.01 | 26.63 / 47.56 | 2.84 / 48.36 | 30.79 / 33.18 | 12.43 / 35.39 | -6.94 / 44.95 |
| Winner (reference) | 58.80 / 44.56 | 54.60 / 47.08 | 49.50 / 50.06 | 49.88 / 33.49 | 45.89 / 34.13 | 41.05 / 34.93 |

What this says:

- **The drawdown goal is easy; the return goal is not.** P1 and P2 both have
  lower DD than the winner on both windows at 1 bp (31-33% vs 44.6% / 33.5%).
  The mandate's "lower DD with CAGR within 2 pp" fails on CAGR by 7.5-18.5 pp.
- **Costs kill the family.** Two fills a day (about 4,100 fills over 10 years,
  41,000-80,000x turnover) costs 25-30 pp of CAGR at 5 bp. P1 and P2 are
  negative at 10 bp. No amount of crash filtering fixes this: the cost is
  proportional to the number of round trips, and an overnight-only strategy has
  ~250 round trips a year.
- **The 30 minutes are worth a lot.** Overnight alone is 40.8%; adding the first
  30 minutes is 51.3% (+10.5 pp) for +2 pp of DD. The first-hour block
  (09:30 to 10:30) is the best intraday block in the sample (+9.4%/yr gross).
- **The vol filter is a 2020 tail hedge, not a general risk reducer.** It skips
  23 regime-on nights in 10 years — *all of them between March and October 2020*
  — and it is completely inert from 2021 to 2026 (see section 7.1). Its entire
  DD benefit comes from four nights (2020-03-05, 2020-03-06, 2020-04-30,
  2020-10-01) worth -47.4% compounded. Without it P1's 10y DD is 46.08% instead
  of 31.19%.

## 6. Where the return and the risk come from

Ablation of the recommended strategy, 1 bp:

| Variant | 10y CAGR / DD | 5y CAGR / DD |
|---|---:|---:|
| Regime only (100% TQQQ / BIL, minute fills) | 45.47 / 59.64 | 35.59 / 42.17 |
| Overnight + first hour + conditional afternoon (base) | 62.40 / 47.78 | 41.15 / 36.93 |
| base + 4% stop | 69.54 / 47.85 | 51.55 / 35.92 |
| base + 20-day vol crash filter | 60.42 / 38.06 | 41.15 / 36.93 |
| base + both (= **R**) | 67.47 / 36.52 | 51.55 / 35.92 |

Read carefully: the **stop is the return engine** (+7.1 pp of 10y CAGR and
+10.4 pp on the 5y, at unchanged drawdown) and the **vol filter is the drawdown
engine** (-9.7 pp of 10y DD for 2 pp of CAGR). The two contributions are close
to additive (62.40 + 7.1 - 2.0 is about 67.5). On the 5y the vol filter is inert,
which is why the fourth and fifth rows are identical there — the 5y result is
the strategy *without* the crash filter.

Why: TQQQ's overnight drift (+29.9%/yr) and first-hour drift (+9.4%/yr) are the
gross return; the 165-day regime removes the bear-market nights (-52.8% in 2022
for the unconditional overnight block vs -7.6% for P1); the first-hour rule
removes the negative afternoons (the session block is -46.3% in 2018 and -50.2%
in 2022); the stop catches the crash days the regime is blind to; and the vol
filter is a cheap, one-episode hedge against the 2020-style gap cluster.

## 7. Crash filters: what works and what does not

### 7.1 20-day volatility filter — works, but only on 2020

Applied to the overnight entry (skip the night when QQQ 20-day vol > threshold,
through the prior close):

| vol threshold | 10y CAGR / DD | 5y CAGR / DD | regime-on nights skipped (10y) | of which 2020 |
|---:|---:|---:|---:|---:|
| none | 69.54 / 47.85 | 51.55 / 35.92 | 0 | 0 |
| 28% | 58.24 / 38.72 | 50.74 / 35.92 | 137 | 69 |
| 30% | 64.38 / 42.42 | 50.48 / 35.92 | 77 | 47 |
| 32% | 68.48 / 37.11 | 53.86 / 35.92 | 47 | 37 |
| **35%** | **67.47 / 36.52** | **51.55 / 35.92** | **23** | **23** |
| 40% | 67.50 / 47.85 | 51.55 / 35.92 | 12 | 12 |

The 10y DD is a step function of the threshold because it depends on whether the
filter is active on 2020-03-05/06 (vol 0.37-0.38). At 40% it is not, and the DD
reverts to 47.85%. **Treat the 36.5% 10y drawdown as conditional on a 2020-type
gap cluster, not as a general property.** The 5y row is unaffected by
construction, which is reassuring: the 5y result is the strategy *without* the
crash filter.

### 7.2 Gap-down exit — clearly harmful

The mandate suggested "exit if the overnight gap is below a threshold". Tested
as: at the 09:30 open, if the QQQ gap is below -X%, sell TQQQ at the 09:31 open
and stay out.

| Variant | 10y CAGR / DD | 5y CAGR / DD |
|---|---:|---:|
| R (no gap rule) | **67.47 / 36.52** | **51.55 / 35.92** |
| R + gap exit at -1% | 63.22 / 36.92 | 43.99 / 36.92 |
| R + gap exit at -2% | 62.85 / 36.92 | 45.95 / 36.46 |
| R + gap exit at -3% | 64.21 / 36.85 | 47.91 / 35.92 |

It costs 3-8 pp of CAGR and does not reduce drawdown. The reason is in the data:
after a QQQ gap below -2% in a regime-on market, the next **60 minutes** of TQQQ
average **+223 bp** (t = 3.61, n = 20); the next 30 minutes average +204 bp
(t = 4.23, n = 21). Gap-downs in this sample *bounce* in the first hour — the
same pattern the Concretum intraday study documents for SPY
([link](https://concretumgroup.com/backtesting-7-years-of-free-data-beat-the-market-an-effective-intraday-momentum-strategy-for-the-sp500-etf-spy)).
Selling the gap is selling the bottom.

### 7.3 Other filters tested and rejected

| Filter | Result (10y / 5y, 1 bp) | Comment |
|---|---|---|
| QQQ close > 20-day MA (short-term trend gate, overnight base) | 22.20 / 28.03 and 9.73 / 28.03 | Cuts DD to 28% but destroys CAGR; too slow to re-enter |
| Fast gate "skip night after QQQ -2% day" | 56.54 / 43.11 and 52.37 / 34.52 | Worse than its 62.98 / 35.65 and 51.90 / 35.23 base; an earlier version looked great but used the same-day close (a 1-minute look-ahead) — see section 9 |
| 10-day drawdown gate "skip if QQQ 4% below 10d high" | 54.15 / 43.15 and 42.09 / 36.25 | Worse on both |
| 4% stop armed only below the 20-day MA (winner's arming) | 64.00 / 36.59 and 47.99 / 35.92 | Arming costs 3.5 pp of CAGR here |
| 3% stop from the session open instead of 4% | 68.11 / 37.74 and 52.13 / 34.26 | Fine; 3% is slightly better on the 5y |

(The last two rows and the two gates are measured on the `thr = 0` base, whose
reference is 62.98 / 35.65 (10y) and 51.90 / 35.23 (5y); the overnight-base row
uses `P1`'s machinery.)

## 8. Robustness

All rows 1 bp, next-open fills, same harness.

### 8.1 Morning-block length

| m (minutes past the open) | 10y CAGR / DD | 5y CAGR / DD |
|---:|---:|---:|
| 30 | **69.64 / 38.43** | 51.83 / 36.59 |
| 45 | 64.02 / 41.03 | 44.38 / 37.71 |
| **60** | 67.47 / 36.52 | 51.55 / 35.92 |
| 75 | 65.63 / 39.20 | 52.80 / 36.17 |
| 90 | 62.09 / 40.17 | 47.20 / 36.90 |

A plateau from 30 to 75 minutes; 90 minutes decays. The "first hour" label is a
convenience, not a knife-edge. m=30 is marginally better on the 10y and m=75
marginally better on the 5y.

### 8.2 Stop level

| Stop from session open | 10y CAGR / DD | 5y CAGR / DD |
|---:|---:|---:|
| 3.0% | 68.11 / 37.74 | 52.13 / **34.26** |
| 3.5% | **68.42 / 38.65** | **53.53 / 34.80** |
| **4.0%** | 67.47 / **36.52** | 51.55 / 35.92 |
| 4.5% | 63.85 / 38.46 | 49.39 / 35.76 |
| 5.0% | 62.94 / 39.90 | 48.49 / 36.90 |

Flat 3-5%. 4% is inherited from the winner, not fitted here.

### 8.3 Regime band

| band | 10y CAGR / DD | 5y CAGR / DD |
|---:|---:|---:|
| 0% | 63.93 / 43.71 | 50.35 / 35.92 |
| 1% | 64.90 / 44.98 | 53.46 / 35.92 |
| **2%** | **67.47 / 36.52** | 51.55 / 35.92 |
| 3% | 65.16 / 36.52 | 47.63 / 35.92 |

The 10y DD step between 1% and 2% is a single 2020 episode (the band decides
whether the regime is still on when the vol filter can fire). The band's *sign*
is stable, its exact level is not.

### 8.4 Afternoon threshold (the one fitted choice)

| Trigger the afternoon exit if r60 < | 10y CAGR / DD | 5y CAGR / DD | fills (10y) |
|---:|---:|---:|---:|
| -1.0% | 58.69 / 40.37 | 37.66 / 40.37 | 663 |
| -0.75% | 57.69 / 39.17 | 40.71 / 38.43 | 727 |
| **-0.5%** | **67.47 / 36.52** | **51.55 / 35.92** | **905** |
| -0.25% | 65.80 / 36.15 | 55.17 / 36.15 | 1,309 |
| 0.0% | 62.98 / 35.65 | 51.90 / 35.23 | 2,073 |
| +0.25% | 47.83 / 41.60 | 33.29 / 40.34 | 2,983 |

This is the least comfortable parameter. Negative thresholds hold the afternoon
more often (fewer trades, more beta); 0% is round-1's ex-ante choice and gives
the lowest DD in this table at 1 bp but 2.3x the fills and a bad 5 bp result
(R0 below). I chose -0.5% because it is the point where the strategy keeps a
5-10 bp edge (section 4.1); the surface is smooth enough that the choice is not
a knife-edge, but it is a choice.

Two alternatives for the reader who prefers different trade-offs:

| | 10y 1 bp | 10y 5 bp | 10y 10 bp | 5y 1 bp | 5y 5 bp | 5y 10 bp |
|---|---:|---:|---:|---:|---:|---:|
| **R** (thr -0.5%, band 2%) | **67.47 / 36.52** | **61.40 / 38.67** | **54.12 / 41.25** | 51.55 / 35.92 | 46.69 / 36.32 | 40.83 / 36.83 |
| R0 (thr 0, band 0) — strict dominance at 1 bp | 61.18 / 39.43 | 47.81 / 42.54 | 32.64 / 46.21 | **50.90 / 31.12** | 39.72 / 32.78 | 26.90 / 35.09 |
| R_vol32 (vol 32%, thr -0.5%) | 68.48 / 37.11 | 61.91 / 39.38 | 54.05 / 42.11 | **53.86 / 35.92** | **48.76 / 36.32** | **42.62 / 36.83** |

R0 dominates the winner on both windows at 1 bp (61.18/39.43 vs 58.80/44.56 and
50.90/31.12 vs 49.88/33.49) but is a pure low-cost strategy: 2,123 fills, -28 pp
of CAGR at 10 bp. It is the same failure mode as the round-1 time-of-day
strategy, which is why it is not the recommendation.

### 8.5 Walk-forward

Two parameters were chosen with the full sample in view: the -0.5% afternoon
threshold and the 35% vol threshold. Everything else is inherited (SMA 165,
band 2%, 60-minute block, 4% stop). A fixed-parameter walk-forward (all
parameters frozen, evaluate 2017-2021 then 2022-2026) gives 86.6% / 36.5% and
51.6% / 35.9%; the winner gives 69.3% / 44.6% and 49.7% / 33.5%. No refitting is
involved in either half — but the two thresholds above remain the main
overfitting risk.

## 9. Overfitting risk and caveats

1. **The crash filter is a one-episode hedge.** It skips 23 nights in 10 years,
   all in 2020, and never fires in the 5-year window. Its DD benefit hinges on
   four nights. If the next crash has a different vol signature (a slow bleed
   rather than a VIX spike), the filter will not help. The honest description is
   "a cheap 2020-style gap-cluster hedge", not "a general crash filter".
2. **The -0.5% afternoon threshold is fitted.** Section 8.4 shows the surface;
   0% gives lower 1 bp DD but dies at 5 bp. This is the parameter most likely to
   be revised out of sample.
3. **The 5-year drawdown is 2.2-2.4 pp worse than the winner's.** The episode is
   the 2024-07-15 to 2024-08-05 yen-carry unwind, which is a pure overnight-gap
   event: the stop cannot see it and the vol filter (20-day) reacts too late. Any
   strategy that holds TQQQ overnight has this exposure. On daily marks the 5y
   DD is 31.28%, below the winner's 33.08%, but the minute-mark comparison is the
   harness standard and there the winner is better.
4. **One earlier "great" result was a look-ahead bug, and I report it.** Adding a
   "skip the night after a -2% QQQ day" filter appeared to give 77.6% / 43.3% on
   the 10y. It used the same-day close to decide both the overnight and the
   afternoon (a 1-minute look-ahead on the night and a 6-hour look-ahead on the
   afternoon). Re-run causally, the same filter *loses* 3-8 pp. This is the
   single most useful negative in the file: fast "crash" gates are exactly where
   look-ahead sneaks in, because the gate is correlated with the outcome.
5. **The first-hour rule is the round-1 intraday-momentum idea.** R = E2 +
   20-day vol filter + 4% stop + a -0.5% threshold. E2 alone (band 2%, no filter,
   no stop) is 66.59 / 49.15 (10y) and 34.69 / 37.69 (5y) at 1 bp. The additions
   are worth -12.6 pp of DD on the 10y and +16.9 pp of CAGR on the 5y. Readers
   should treat this as a blend of families, not a new standalone signal.
6. **2026 is weak (+3.4% vs the winner's +16.8%).** The April-June 2026 rebound
   was earned intraday and the first-hour rule sat out part of it. The strategy
   is structurally exposed to a migration of drift from night to day.
7. **Taxes and borrow are ignored.** 91 fills a year is tax-inefficient in a
   taxable account. BIL earns its own small yield; no extra cash yield is added.
8. **Single instrument, single sample.** TQQQ has no survivorship gap over the
   window, but the result is one 3x Nasdaq-100 ETF over a period with two large
   crashes and one long bull market.

## 10. Pass / fail against the round-2 targets

| Test | 1 bp | 5 bp | 10 bp |
|---|---|---|---|
| Max DD < winner, 10y (44.56%) | **PASS** 36.52% | **PASS** 38.67% | **PASS** 41.25% |
| Max DD < winner, 5y (33.49%) | FAIL 35.92% | FAIL 36.32% | FAIL 36.83% |
| CAGR > winner, 10y (58.80 / 54.60 / 49.50) | **PASS** 67.47% | **PASS** 61.40% | **PASS** 54.12% |
| CAGR > winner, 5y (49.88 / 45.89 / 41.05) | **PASS** 51.55% | **PASS** 46.69% | FAIL 40.83% |
| Strict dominance both windows | fail (5y DD) | fail (5y DD) | fail (5y DD) |
| Lower DD both windows, CAGR within 2 pp | fail (5y DD) | fail (5y DD) | fail (5y DD) |
| Better rolling 3y consistency | **PASS** 26/27 vs 24/27, min CAGR 41.7% vs 31.2%, max DD 35.4% vs 41.6% | - | - |
| Beats TQQQ on CAGR and DD, both windows | **PASS** | **PASS** | **PASS** |

**Overall: a qualified pass.** It dominates the winner on the 10-year window at
10 bp, and its rolling 3-year consistency is better. It does not dominate on the
5-year window because of one three-week overnight-gap drawdown in August 2024;
that is a real, structural weakness of holding a 3x ETF overnight, not a fitting
artefact.

## 11. Files and reproduction

| file | purpose |
|---|---|
| `strategy.py` | clean standalone implementation of R (explicit rules, asserted equal to `lab.build_weights`), prints 0/1/5/10 bp for both windows |
| `lab.py` | panel cache loader, daily arrays, indicators, weight builder, exact fast simulator (validated against `bt.simulate`), rolling-3y helper |
| `check_sim.py` | simulator validation and the round-1 winner / reference re-runs |
| `explore.py` | block anatomy: overnight / first 30m / first 60m / session, conditional on vol, gap, regime; yearly block returns |
| `grid1.py` ... `grid9.py` | variant grids quoted in sections 5-8 (bases, vol filters, gap filters, stop surface, threshold surface, vol surface) |
| `final.py` | builds every reported variant and writes `result.json` |
| `tables.py` | pulls the report tables out of `result.json` |
| `verify.py` | truncation (no-look-ahead) test, exposure and filter diagnostics |
| `result.json` | machine-readable metrics: 0/1/5/10 bp, yearly, rolling 3y, ablations, diagnostics |

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
python research\agents2\overnight-crash-filter\strategy.py   # headline
python research\agents2\overnight-crash-filter\final.py      # -> result.json
python research\agents2\overnight-crash-filter\verify.py     # look-ahead audit
```

No core repository file was modified. `panel_cache.npz` is a local copy of the
1-minute panel so the grids do not re-parse parquet; delete it and `lab.py`
rebuilds it from `data/intraday-hf`.

## References

- Cliff, M., Cooper, M., & Gulen, H. (2008). *Return Differences between Trading
  and Non-Trading Hours: Like Night and Day.* SSRN 1004081.
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1004081
- Lou, D., Polk, C., & Skouras, S. (2019). *A Tug of War: Overnight versus
  Intraday Expected Returns.* Journal of Financial Economics 134(1), 192-213.
  http://www.econ.yale.edu/~shiller/behfin/2015-04-11/lou_polk_skouras.pdf
- Haghani, V., Ragulin, V., & Dewey, R. (2022). *Night Moves: Is the Overnight
  Drift the Grandmother of All Market Anomalies?* Journal of Investment
  Management 22(2), 2024. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4139328
  - https://elmwealth.com/wp-content/uploads/2026/04/Elm-Night-Moves-Overnight-Drift.pdf
- Bondarenko, O., & Muravyev, D. (2021). *Market Return Around the Clock: A
  Puzzle.* NY Fed Staff Report 917.
  https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr917.pdf
- Liquidnet (2021). *Price Discovery and Tactics to Time Trading* — overnight
  share of return by index (NASDAQ-100 about 65%).
  https://liquidnet-dev.squarespace.com/s/PriceDiscovery-TacticsToTimeTrading-20210714-final.pdf
- Cheng, M., & Madhavan, A. (2009). *The Dynamics of Leveraged and Inverse
  Exchange-Traded Funds.* Journal of Investment Management 7(4).
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1393995
- FinLab. *Leveraged ETF Decay: Volatility Drag and Costs in 14 Funds* — high
  QQQ 20-day vol days carry 52.7% of TQQQ's decay.
  https://finlab.finance/en/blog/leveraged-etf-decay
- ETF.com. *One Bad Day: A Levered-QQQ ETF Case Study* — TQQQ end-of-day
  rebalancing flows. https://www.etf.com/sections/equity/one-bad-day-levered-qqq-etf-case-study
- Concretum Group. *Beat the Market: An Effective Intraday Momentum Strategy for
  SPY* — overnight gaps revert within the first 30 minutes.
  https://concretumgroup.com/backtesting-7-years-of-free-data-beat-the-market-an-effective-intraday-momentum-strategy-for-the-sp500-etf-spy
- Gao, L., Han, Y., Li, S. Z., & Zhou, G. (2018). *Market Intraday Momentum.*
  Journal of Financial Economics 129(2), 394-414.
  https://doi.org/10.1016/j.jfineco.2018.05.009
- Kaminski, K. M., & Lo, A. W. (2014). *When Do Stop-Loss Rules Stop Losses?*
  Journal of Financial Markets 18, 234-254.
  https://doi.org/10.1016/j.finmar.2013.07.001
