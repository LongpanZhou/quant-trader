# Intraday seasonality on the 165-day QQQ regime — agent 22

**Verdict: one overlay survives, and it is not really "seasonality" — it is late-day
momentum.** On risk-on sessions where QQQ is down more than 1% at 15:00, the winner's
TQQQ position is moved to BIL for the last 30 minutes (sell 15:01, buy back 15:30). That
raises 10-year CAGR from 58.80% to **61.35%** and cuts max DD from 44.56% to **44.18%**;
5-year CAGR rises from 49.88% to **53.46%** with DD flat at 33.50%. It is worth
**+0.20 / +1.50 pp of CAGR at 5 bp** with slightly worse drawdown, and it **loses to the
winner at 10 bp**. It is a real, well-documented microstructure effect, but it only trades
about **10 times a year** after the winner's 4% stop has already removed the worst days,
and the strategy-level edge is therefore thin.

Every calendar family in the mandate (lunch hour, opening 5 minutes, day-of-week,
OpEx week, pre/post holiday) was tested and **rejected** — details in §5. The OpEx-week
variant is the only calendar rule that improves drawdown materially (10y DD 40.87%), but
it fires on ~60 days a year (~100 fills) and fails badly at 5 bp.

| Window | Final 1 bp | Winner 1 bp | TQQQ | Final 5 bp | Winner 5 bp | Final 10 bp | Winner 10 bp |
|---|---:|---:|---:|---:|---:|---:|---:|
| 10y CAGR | **61.35%** | 58.80% | 39.28% | **54.80%** | 54.60% | 46.99% | **49.50%** |
| 10y max DD | **44.18%** | 44.56% | 81.68% | 47.47% | **47.08%** | 51.32% | **50.06%** |
| 5y CAGR | **53.46%** | 49.88% | 13.47% | **47.39%** | 45.89% | 40.12% | **41.05%** |
| 5y max DD | 33.50% | **33.49%** | 81.68% | 34.29% | **34.13%** | 35.47% | **34.93%** |
| Sharpe 10y / 5y | 1.28 / 1.21 | 1.24 / 1.16 | 0.83 / 0.53 | 1.18 / 1.12 | — | 1.07 / 1.00 | — |

Pass/fail:

| test | result |
|---|---|
| beats TQQQ on CAGR **and** DD, both windows, 1 bp | **PASS** (+22.1 / +40.0 pp CAGR, −37.5 / −48.2 pp DD) |
| beats the winner, 10y, 1 bp | **PASS** (+2.55 pp CAGR, −0.38 pp DD) |
| beats the winner, 5y, 1 bp | **return PASS** (+3.58 pp), DD flat (+0.01 pp) — not strict dominance |
| beats the winner at 5 bp | **mixed** (+0.20 / +1.50 pp CAGR, +0.39 / +0.16 pp DD) |
| beats the winner at 10 bp | **FAIL** (−2.51 / −0.93 pp CAGR, +1.26 / +0.54 pp DD) |
| rolling 3-year consistency | **PASS** — 26/27 windows beat the winner's CAGR, 26/27 have lower DD |

---

## 1. The rule

Everything is the round-1 winner (`daily-regime-minute-entry`) plus one conditional
30-minute de-risk:

```
For each session d (09:30-15:59 ET):
  SMA165[d] = mean(QQQ daily close, d-165 ... d-1)
  risk_on   = QQQ close[d-1] > SMA165[d]

  if not risk_on:
      hold BIL all session
  else:
      hold TQQQ, with the winner's 4% stop:
        armed = QQQ first-minute price < MA20[d] * 1.01
        if armed and TQQQ close[i] < open[d] * 0.96: go to BIL for the
        rest of the session and the night

      NEW - late-day continuation carve:
        at 15:00, q_day = QQQ(15:00) / QQQ(09:30 open) - 1
        if q_day < -1.0%  and still long TQQQ:
            sell TQQQ at the 15:01 open, hold BIL
            buy  TQQQ back at the 15:30 open
```

- Signal is the **close of the 15:00 bar** (15:00:59); the sell fills at the **15:01
  open**, the buy at the **15:30 open**. Nothing after 15:00:59 is used.
- One position at a time, long only, 100% TQQQ or 100% BIL, no leverage beyond TQQQ.
- Effective parameters: threshold 1.0%, window 15:00-15:30. Both are round numbers and
  sit on a plateau (§7), not a spike.

## 2. Why this is the family that worked

The mandate listed six families. Five are calendar effects; one — last-hour momentum —
is a time-of-day effect. The data says the calendar effects are not stable in 2017-2026,
and the time-of-day effect is.

The mechanism is not a mood; it is arithmetic. A daily-reset 3x fund must trade

```
dE = L (L - 1) * r * NAV  =  6% of NAV per 1% of index return
```

at the close, in the same direction as the day's move (Cheng & Madhavan 2009). On a −1%
QQQ day TQQQ has to *sell* roughly 6% of its net assets in the closing window; on a −3%
day it is closer to a fifth of the fund. That flow is price-insensitive and predictable,
and it lands in the last hour. The empirical literature documents exactly this:

- **Mathis & Moerke (2022)**, *Liquidity Provision to Leveraged ETFs and Equity Options
  Rebalancing Flows* — "leveraged ETFs contribute to a basket-wide momentum effect" and
  "leveraged ETF swap counterparties are required to establish the target exposure of the
  fund at the close". They also find the effect **"significantly decreasing"** over time,
  which matches the attenuation I see in 2024-2026.
  <https://wp.lancs.ac.uk/fofi2022/files/2022/08/FoFI-2022-027-Mathis-Moerke.pdf>
- **Lenkey (2024)**, *The market impact of leveraged ETFs: a survey*, Quantitative
  Finance and Economics 8(4) — surveys the late-day price-pressure literature.
  <https://doi.org/10.3934/QFE.2024031>
- **Gao, Han, Li & Zhou (2018)**, *Market intraday momentum*, JFE 129(2) — the
  first-half-hour return predicts the last-half-hour return, stronger on volatile days.
  My signal is a cousin (the whole day-so-far instead of the first 30 minutes), and it is
  much stronger in this sample than the literal first-30-min version.
  <https://doi.org/10.1016/j.jfineco.2018.05.009>
- ETF.com's *One Bad Day* case study walks through a real TQQQ/SQQQ rebalance into a
  close and the size of the forced sell.
  <https://www.etf.com/sections/equity/one-bad-day-levered-qqq-etf-case-study>
- Strasmore, *Leveraged ETF Rebalancing Into the Close* — the reset arithmetic and the
  closing-auction execution.
  <https://www.strasmore.com/blog/leveraged-etf-rebalancing-and-the-close>

The reason the winner does not already capture this: its stop needs QQQ **below its 20-day
MA** *and* a 4% TQQQ drop from the open. On a −1% QQQ day in an uptrend neither condition
holds, so the book is still long into the close. Of 317 signal sessions, **218 are
preempted** (115 by the stop firing earlier that day, 103 by the risk-off regime) and
**99 actually trade**.

## 3. Data, harness and no-look-ahead

- Local adjusted 1-minute QQQ / TQQQ / BIL only (`data/intraday-hf/`), regular session,
  2016-01-04 to 2026-10-23, 1,057,023 bars, 2,718 sessions (500 calendar days of warm-up).
- Test windows: 10y 2017-01-03 to 2026-10-23, 5y 2021-10-25 to 2026-10-23.
- Signals use bars <= i; every fill is at the **open of bar i+1**. Slippage is charged on
  traded notional; weights sum to <= 1; long only.
- I wrote a fast exact replica of `bt.simulate` (`lib.simulate`, ~0.5 s per run instead of
  15 s) and validated it against the harness: base winner 58.796% / 44.5647% vs harness
  58.7979% / 44.5647%; final 61.3506% / 44.1768% vs 61.35% / 44.18%. Differences are
  O(slip^2) residual cash.
- Causal checks: the 15:00 bar itself contributes **−0.16 bp** to the measured effect, so
  nothing leaks through the signal bar; the 15:59-16:00 minute contributes **+1.8 to
  +4.2 bp** depending on the threshold and is held by both base and variant, so it is not
  the source of the edge. Replacing the 1-minute 15:59 close with the official daily close
  leaves the effect intact (−17.9 bp vs −19.7 bp on the last hour), so it is not a
  bad-print artifact.

## 4. The evidence for the effect

Gain per event = −(TQQQ return from the 15:01 open to the 15:30 open), i.e. what the
carve earns. Risk-on days only, 2017+.

| signal at 15:00 | n | mean gain | t | win rate |
|---|---:|---:|---:|---:|
| QQQ down > 0% | 901 | +6.76 bp | 3.06 | 52.3% |
| QQQ down > 0.5% | 432 | +13.73 bp | 3.53 | 53.4% |
| **QQQ down > 1.0%** | **195** | **+19.99 bp** | **3.02** | **57.6%** |
| QQQ down > 1.0%, IS 2017-2021 | 106 | +16.20 bp | 1.63 | 55.7% |
| QQQ down > 1.0%, OOS 2022-2026 | 89 | +24.49 bp | 2.93 | 59.6% |

The effect is monotone in the size of the day's decline, and it is **stronger out of
sample** than in sample for the 30-minute window. Per year (n = signal days):

| year | n | mean gain | t | win |
|---|---:|---:|---:|---:|
| 2017 | 10 | −16.1 bp | −0.67 | 60% |
| 2018 | 27 | +19.3 bp | 1.04 | 59% |
| 2019 | 12 | −10.0 bp | −0.50 | 50% |
| 2020 | 34 | +10.3 bp | 0.55 | 50% |
| 2021 | 23 | +49.0 bp | 1.93 | 61% |
| 2022 | 3 | +15.7 bp | 0.25 | 67% |
| 2023 | 21 | +51.6 bp | 3.71 | 81% |
| 2024 | 23 | +17.6 bp | 1.01 | 57% |
| 2025 | 21 | +42.2 bp | 2.16 | 71% |
| 2026 | 21 | −11.5 bp | −0.84 | 29% |

Seven of ten years positive; the two bad years (2017, 2019) are strong melt-up years in
which down days were bought aggressively into the close, and 2026 is a warning sign.

**Where in the afternoon the effect lives** (TQQQ, risk-on, signal at 14:30 < −1%):

| block | IS | OOS | all (t) |
|---|---:|---:|---:|
| 14:30 to 15:00 | +6.97 bp | −0.02 bp | +3.82 (0.53) |
| 15:00 to 15:30 | −17.76 bp | −25.85 bp | −21.41 (−3.17) |
| 15:30 to 15:59 | −11.54 bp | −9.05 bp | −10.42 (−1.11) |

This is why the carve starts at **15:00, not 14:30**: 14:30-15:00 is *positive*. A grid
search prefers a 14:30 start (10y CAGR 62.94% at −0.5%), but that is compounding luck, not
economics, so I did not use it.

## 5. The calendar families: tested and rejected

All of these are applied on top of the same winner and measured at 1 bp (10y / 5y CAGR /
DD). None is recommended.

| family | test | 10y | 5y | why rejected |
|---|---|---:|---:|---|
| lunch 12:00-14:00 | carve lunch on OpEx weeks | 54.31 / 45.52 | 46.51 / 32.18 | unconditional lunch mean flips: −2.9 bp IS, +3.8 bp OOS |
| lunch | carve when morning > +1.5% | 61.27 / 45.78 | 50.47 / 33.49 | tiny sample (63 days), DD worse |
| lunch | carve when morning < −1.5% | 58.23 / 44.56 | 49.94 / 33.49 | no effect |
| opening 5 min | sell 09:31-09:35 if gap < −1.5% | 57.61 / 45.66 | 49.28 / 33.05 | reversal is +2.8 bp IS, −5.7 bp OOS |
| opening 5 min | sell 09:31-09:35 if gap > +1.5% | 58.90 / 44.25 | 50.84 / 33.17 | same sign flip; ~no effect |
| day of week | carve 15:00-15:30 on Wednesdays | 57.18 / 45.21 | 50.84 / 33.91 | Wednesday's negative block is 15:30-15:59, not 15:00-15:30 |
| OpEx week | carve 15:00-15:30 all OpEx days | **60.20 / 40.87** | **50.90 / 31.99** | best DD result, but ~100 fills/yr: 5 bp gives 44.95 / 47.81 and 37.77 / 33.07 |
| pre-holiday | carve 15:00-15:30 | 58.44 / 44.47 | 49.75 / 33.49 | pre-holiday overnight +9.0 bp IS, −26.5 bp OOS |
| holiday | disarm stop on pre-holiday | 59.49 / 43.54 | 50.43 / 32.26 | rests on **4** stop events in 10 years |
| holiday | disarm stop on post-holiday | 60.45 / 44.48 | 52.91 / 33.49 | rests on **5** stop events |
| OpEx week | disarm stop on OpEx week | 52.30 / 42.94 | 43.18 / 33.74 | stops are *more* valuable on OpEx (n=31, +113 bp each) |
| day of week | disarm stop on Fridays | 61.76 / 41.27 | 50.51 / **39.29** | 5y DD blows out by 5.8 pp |

Supporting descriptive detail:

- **Lunch.** The unconditional 12:00-14:00 TQQQ mean is −2.92 bp in 2017-2021 and +3.78 bp
  in 2022-2026 — a sign flip. The one stable pattern is *continuation* after a >3% morning
  (+24.4 bp lunch IS, +24.2 bp OOS, n ~ 100 each), but the winner is already long, so there
  is nothing to trade. The "lunch reversal" story (Quantpedia/SSRN, Vojtko & Dujava 2024,
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4934614>) does not show up as a
  tradeable overlay here.
- **Opening 5 minutes.** Gap < −2%: the 09:31-to-09:35 TQQQ return is +2.8 bp in 2017-2021
  but −5.7 bp in 2022-2026. Gap > +2%: +1.4 bp then −3.5 bp. There is no stable
  opening reversal in this sample, consistent with the recent literature finding that the
  overnight-to-first-half-hour reversal weakened after the 2010s
  (<https://www.sciencedirect.com/science/article/abs/pii/S1062940826001294>).
- **Day of week.** Monday's *session* is the only consistently positive weekday block
  (+22.7 bp IS, +56.6 bp OOS), but Monday's overnight is +41.8 bp IS and −20.9 bp OOS.
  Tuesday's overnight is +42.5 bp IS and +1.5 bp OOS. Wednesday 15:30-15:59 is −17.9 /
  −7.3 bp (consistent) but carving it loses 1.6 pp of 10y CAGR — the block is small and
  the four-fill-per-week cost eats it.
- **OpEx week.** The week's session return is +16.7 bp IS and −18.7 bp OOS (unstable), but
  its **15:00-15:30 block is negative in both halves** (−3.28 / −6.63 bp). That is the one
  calendar effect that survives the split, and the carve does cut 10y DD to 40.87%. It
  simply cannot pay ~100 fills a year. The academic OpEx-week effect (Stivers & Sun 2013,
  <https://doi.org/10.1016/j.jbankfin.2013.07.007>) is a *positive* weekly drift; the
  modern out-of-sample evidence says it is gone
  (<https://chartinglens.com/blog/options-expiration-week-stock-returns>), which matches
  what I see.
- **Pre/post holiday.** Pre-holiday overnight is +9.0 bp IS and −26.5 bp OOS; post-holiday
  overnight is +46.0 bp IS and −81.8 bp OOS. This is exactly the decay documented for the
  pre-holiday premium in large caps (Ariel 1990 replication, Critical Finance Review 2024,
  <https://cfr.ivo-welch.org/forthcoming/papers/ko2021pre.pdf>; Kim & Park 1994,
  <https://doi.org/10.2307/2331196>).

## 6. Results

### 6.1 Headline, 1 bp

| metric | final 10y | winner 10y | final 5y | winner 5y |
|---|---:|---:|---:|---:|
| CAGR | **61.35%** | 58.80% | **53.46%** | 49.88% |
| max DD (1-min marks) | **44.18%** | 44.56% | 33.50% | 33.49% |
| max DD (daily marks) | 41.21% | 41.62% | 33.10% | 33.08% |
| Sharpe | 1.28 | 1.24 | 1.21 | 1.16 |
| Sortino | 1.79 | 1.74 | 1.72 | 1.64 |
| annualised vol | 46.03% | 46.12% | 43.33% | 43.39% |
| ending equity on $100k | $10.88M | $9.30M | $849k | $755k |
| trade bars / turnover | 524 / 1,047x | 344 / 687x | — | — |
| max-DD window | 2018-03-12 to 2019-06-05 | same | 2026-06-15 to 2026-07-29 | same |

The 5-year drawdown is untouched because it is the 2026 summer selloff, where the signal
fired only a handful of times and the effect was weak.

### 6.2 Cost sensitivity

| costs | 10y CAGR | 10y DD | 10y Sharpe | 5y CAGR | 5y DD | 5y Sharpe |
|---|---:|---:|---:|---:|---:|---:|
| 0 bp | 63.03% | 43.32% | 1.30 | 55.02% | 33.31% | 1.24 |
| **1 bp** | **61.35%** | **44.18%** | **1.28** | **53.46%** | **33.50%** | **1.21** |
| 5 bp | 54.80% | 47.47% | 1.18 | 47.39% | 34.29% | 1.12 |
| 10 bp | 46.99% | 51.32% | 1.07 | 40.12% | 35.47% | 1.00 |

Each extra basis point costs about 1.3 pp of CAGR, consistent with ~20 extra round trips
per year on 100% of equity. **The overlay is a 1-2 bp idea.** At 5 bp it is a coin flip
against the winner; at 10 bp it is value-destroying.

### 6.3 Yearly returns (1 bp)

| year | final | winner | TQQQ | final − winner |
|---|---:|---:|---:|---:|
| 2017 | 117.01% | 118.74% | 114.54% | −1.73 |
| 2018 | 1.04% | 0.47% | −20.76% | +0.57 |
| 2019 | 48.24% | 47.94% | 148.23% | +0.30 |
| 2020 | 193.24% | 183.91% | 104.14% | +9.33 |
| 2021 | 62.62% | 60.61% | 81.05% | +2.01 |
| 2022 | −18.89% | −17.99% | −79.39% | −0.90 |
| 2023 | 163.37% | 149.04% | 192.05% | +14.33 |
| 2024 | 77.75% | 67.96% | 62.43% | +9.79 |
| 2025 | 47.75% | 43.29% | 32.10% | +4.46 |
| 2026 | 14.39% | 16.76% | 22.62% | −2.37 |

Seven wins / three losses. The gain is concentrated in 2020 (+9.3 pp), 2023 (+14.3 pp) and
2024 (+9.8 pp); 2026 is a clear loss and 2017/2022 are small losses.

### 6.4 In-sample vs out-of-sample

| period | final CAGR / DD | winner CAGR / DD |
|---|---:|---:|
| IS 2017-2021 | **74.97% / 44.18%** | 73.42% / 44.56% |
| OOS 2022-2026 | **47.94% / 33.50%** | 44.54% / 33.49% |
| 2017-2019 | 49.06% / 44.18% | 49.07% / 44.56% |
| 2020-2022 | 58.51% / 40.95% | 56.74% / 41.50% |
| 2023-2026 | 73.24% / 33.50% | 67.74% / 33.49% |

The improvement exists in every sub-period, but it is tiny in 2017-2019 and large in
2023-2026. That is the opposite of a decaying anomaly and is the main reason I am willing
to report it at all.

### 6.5 Rolling 3-year windows (27 quarterly starts, 2017-04 to 2023-10)

| | count |
|---|---:|
| windows where final beats the winner's CAGR | **26 / 27** |
| windows where final has lower DD than the winner | **26 / 27** |
| windows where final beats TQQQ's CAGR | **25 / 27** |
| windows where final has lower DD than TQQQ | **27 / 27** |

The one CAGR miss is the 2017-07 window (46.3% vs 46.3%, a tie to one decimal). The two
windows where the final loses to TQQQ on CAGR are 2018-04 (50.7% vs 57.6%) and 2019-01
(94.5% vs 112.2%) — the expected shape: the overlay gives up a little in melt-ups.

### 6.6 Walk-forward threshold selection

The threshold is the one free parameter, so I tested the *selection procedure*: for each
year from 2019 to 2026, pick the threshold that maximised CAGR over all prior years, then
apply it to the next year.

| year | threshold picked | final | winner |
|---|---:|---:|---:|
| 2019 | −0.75% | 44.99% | 47.96% |
| 2020 | −1.00% | 201.10% | 191.52% |
| 2021 | −0.75% | 63.99% | 62.31% |
| 2022 | −0.25% | −15.75% | −16.70% |
| 2023 | −0.25% | 188.33% | 149.06% |
| 2024 | −0.25% | 63.60% | 63.61% |
| 2025 | −0.25% | 43.48% | 45.73% |
| 2026 | −0.50% | 19.24% | 20.46% |

**Walk-forward 2019-2026: 62.52% vs 59.42% for the winner, +1.95 pp.** The procedure loses
in 3 of 8 years but wins the period. Every fixed threshold in the grid also beats the
winner over the same block (61.1% to 65.7% vs 59.4%), so the *family* is robust even though
the exact threshold is not.

## 7. Robustness

### 7.1 Threshold x window surface (1 bp)

| threshold | 15:00-15:30 | 15:00-15:59 | 15:30-15:59 |
|---:|---:|---:|---:|
| 0.00% | 60.73 / 43.16 | 60.89 / 46.31 | 54.48 / 46.56 |
| −0.50% | **62.75 / 44.44** | 61.56 / 46.15 | 59.98 / 44.32 |
| −0.75% | 61.75 / 43.73 | 61.42 / 43.69 | 58.66 / 45.14 |
| **−1.00%** | **61.35 / 44.18** | 60.72 / 45.46 | 60.00 / 44.82 |
| −1.25% | 61.41 / 43.74 | 60.85 / 45.15 | 59.39 / 44.89 |
| −1.50% | 60.32 / 44.78 | 60.01 / 44.83 | 59.11 / 44.85 |
| −2.00% | 59.79 / 44.78 | 59.38 / 44.83 | 58.55 / 44.83 |

(10y CAGR / max DD; winner = 58.80 / 44.56. 5y numbers are in `result.json`.)

The surface is a plateau, not a spike: on the two 15:00-start windows every threshold from
0% to −2% beats the winner's 10y CAGR at 1 bp, and the 15:30-15:59 window only fails at the
extreme 0% setting (54.48%). The 15:00-15:30 window with 0% has the best DD (43.16%) but
fires on 1,221 days and needs 1,944 trade bars; the 15:00-15:59 window with 0% is the worst
of the family (46.31% DD) because it is out of the market for a full hour on half of all
days. From −0.5% to −1.25% the 15:00-15:30 window is equal or better than the winner on
both CAGR and DD.

The 5-year picture is what stops this from being a clean win:

| threshold | 5y, 15:00-15:30 |
|---:|---:|
| 0.00% | 51.26 / 32.64 |
| −0.50% | 54.61 / 31.68 |
| −0.75% | 52.73 / 32.16 |
| −1.00% | 53.46 / 33.50 |
| −1.25% | 52.81 / 33.50 |

Only the looser thresholds improve the 5y drawdown; the return-maximising threshold
(−0.5%) is also the 5y DD winner.

### 7.2 Cost surface (10y CAGR)

| threshold | 1 bp | 5 bp | 10 bp |
|---:|---:|---:|---:|
| 0.00% | 60.73 | 38.09 | 14.20 |
| −0.50% | 62.75 | 50.74 | 36.95 |
| −0.75% | 61.75 | 53.02 | 42.77 |
| −1.00% | 61.35 | 54.80 | 46.99 |
| −1.25% | 61.41 | **55.62** | 48.67 |
| −1.50% | 60.32 | 55.11 | 48.82 |
| −2.00% | 59.79 | 55.10 | **49.42** |

The cost-optimal threshold moves tighter as costs rise (−1.25% at 5 bp, −2.00% at 10 bp),
which is exactly what a decaying per-event edge predicts. That instability is a warning,
not a feature: at 10 bp no threshold clearly beats the winner (49.48 / 50.07).

### 7.3 Gates and alternatives

| variant | 10y | 5y | note |
|---|---:|---:|---|
| no gate (chosen) | 61.35 / 44.18 | 53.46 / 33.50 | 99 executed events |
| + QQQ < MA20 at 15:00 | 59.63 / 44.79 | 50.70 / 33.39 | 218 signal days, no better |
| + QQQ > MA20 at 15:00 | 60.51 / 43.95 | 52.62 / 33.59 | 95 signal days — effect is not trend-dependent |
| + OpEx week AND QQQ < −1% | 59.61 / 43.57 | 50.96 / 33.59 | 28 executed events, too thin |
| 15:00-15:59 window | 60.72 / 45.46 | 53.70 / 33.39 | more time out, worse DD |
| TQQQ day move < −3% instead of QQQ < −1% | 59.52 / 44.92 | 50.58 / 34.03 | noisier signal |

### 7.4 Event economics

| | value |
|---|---:|
| signal sessions (full panel) | 317 |
| executed (still long TQQQ at 15:00) | **99** (~10/yr) |
| preempted by the 4% stop that day | 115 |
| preempted by the risk-off regime | 103 |
| mean gain per executed event | +15.90 bp |
| median gain | +10.23 bp |
| t-stat | 1.97 |
| win rate | 57.6% |

This is the honest weak point. The *cross-sectional* effect is strong (t ~ 3 over 195
signal days), but the *strategy-level* sample is 99 trades, and a t of 1.97 is not
overwhelming. Ten trades a year is also easy to second-guess in real time.

## 8. What could kill it

1. **Only ~10 trades a year.** The t-stat on executed events is 1.97. A run of bad years
   is entirely possible; the 2026 sample (−11.5 bp/event on 21 signal days) is one.
2. **The 2026 loss.** The overlay lost 2.4 pp in 2026 and its per-event edge was negative.
   If leveraged-ETF rebalancing pressure is now arbitraged (the Mathis-Moerke paper says
   the effect is "significantly decreasing"), 2024-2026 is the guide, not 2021-2023.
3. **The threshold is not stable.** IS prefers 0% / −0.5%, OOS prefers −1.0%, the 5 bp
   cost surface prefers −1.25%, and the 10 bp surface prefers −2%. I chose −1.0% because
   it is a round number on the plateau and survives 5 bp; that is a judgement call.
4. **Drawdown is barely improved.** 44.18% vs 44.56% on 10y, 33.50% vs 33.49% on 5y. If
   the goal is lower DD, the OpEx-week carve (40.87% / 31.99%) is better but fails at 5 bp.
5. **1 bp is optimistic.** The strategy needs to trade at the 15:01 and 15:30 opens in
   size. TQQQ is liquid, but the 15:30 print is not the closing auction; a 5 bp assumption
   is the honest retail case, and there the edge is ~zero.
6. **The 5-year result is not a drawdown win.** The 2026 max-DD window is untouched.
7. **Data caveat.** The 1-minute 15:59 close can differ from the official close by up to
   ~1% on some days; I re-ran the conditional means with official daily closes and the
   effect survives, so this is noise rather than bias. All fills use 1-minute opens.

## 9. Files

| file | purpose |
|---|---|
| `strategy.py` | final strategy, cost/yearly/sub-period/rolling/walk-forward tables, writes `result.json` |
| `lib.py` | panel cache, fast exact simulator, winner baseline, calendar masks, carve helper |
| `validate.py` | fast simulator vs `bt.simulate`, winner reproduction |
| `explore.py` | first-pass block means: overnight, half-hours, day-of-week, OpEx, holidays |
| `study2.py` | 30-minute profile, predictive regressions, calendar effects conditional on regime |
| `study3.py` | late-day weakness to last 30 min and overnight, calendar groups |
| `study4.py` | last-hour continuation: exact carve window, official-close check, per-year |
| `study5.py` | afternoon term structure, VWAP/MA gates, stop-event calendar attribution |
| `grid.py`, `grid2.py` | threshold x window x gate surfaces, cost curves |
| `variants.py`, `combo.py`, `cost2.py` | overlay grids and cost sweeps |
| `events.py`, `stability.py` | executed-event economics, per-year block stability |
| `walkforward.py` | year-by-year threshold selection |
| `diag.py` | carve P&L attribution debugging |
| `result.json` | machine-readable metrics for everything above |

Reproduce:

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
python research\agents2\intraday-seasonality\validate.py    # simulator check + winner
python research\agents2\intraday-seasonality\strategy.py    # final tables + result.json
python research\agents2\intraday-seasonality\study4.py      # the effect itself
```

## 10. Bottom line

The only intraday-seasonality overlay that survives a 2017-2021 / 2022-2026 split on this
data is **not a calendar effect**. It is the documented tendency of a leveraged Nasdaq ETF
to keep sliding into the close on a down day, because the fund itself has to sell into the
close. Selling TQQQ for the last 30 minutes when QQQ is down more than 1% at 15:00 adds
**+2.6 pp of 10-year CAGR and +3.6 pp of 5-year CAGR at 1 bp**, keeps drawdown roughly
unchanged, and improves 26 of 27 rolling 3-year windows against the winner. At 5 bp the
gain is +0.2 / +1.5 pp with slightly worse drawdown; at 10 bp it is a loss. That is a
useful, cheap overlay for someone already running the winner with sub-2 bp execution — not
a replacement for it, and not a drawdown fix.
