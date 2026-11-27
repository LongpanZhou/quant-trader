# Volume and order-flow proxies: a participation-armed crash stop

**Agent:** `volume-orderflow` (round 2, agent 23) · **Date:** 2026-11-25
**Question:** can 1-minute relative volume, VWAP deviation, signed volume / close
location, volume spikes, or volume-confirmed momentum improve the round-1 winner?

## Verdict

**Partly.** Almost every *directional* volume signal is dead after costs — that is
the bulk of this report (Section 7). But one *conditioning* use of volume survives
every robustness test I could throw at it: **a 4% intraday stop should only be
honoured when the session's volume is at least normal.**

Adding that single condition (plus a symmetric "high-volume days are always armed"
rule) to the round-1 winner gives:

| Window | 1 bp CAGR / DD | 5 bp CAGR / DD | 10 bp CAGR / DD |
|---|---:|---:|---:|
| 10y (2017-01-03..2026-10-23) | **65.90% / 42.49%** | 60.56% / 45.45% | 54.14% / 48.93% |
| 5y (2021-10-25..2026-10-23) | **53.17% / 28.64%** | 48.80% / 29.35% | 43.52% / 30.26% |

versus the round-1 winner (58.80/44.56 and 49.88/33.49 at 1 bp; 54.60/47.08 and
45.89/34.13 at 5 bp; 49.50/50.06 and 41.05/34.93 at 10 bp) and TQQQ buy-and-hold
(39.28/81.68 and 13.47/81.68). **It beats both the winner and TQQQ on CAGR *and*
max drawdown in both windows at all three cost levels.**

Two honest qualifications, both quantified below:

1. The **CAGR** gain is broad — 21 of 28 rolling 3-year windows have a higher CAGR
   than the winner — and comes from the intended mechanism: arming the stop on
   high-volume days catches the February–March 2020 crash before the 165-day
   regime flips (2020: +267.9% vs the winner's +183.9%).
2. The **5-year drawdown** gain is **one event**. Restoring a single stop that the
   volume floor suppressed (2026-06-24, a −4% break on 0.87× normal volume) takes the
   5y drawdown from 28.64% back to 34.16% — worse than the winner. Section 8.2 shows
   this explicitly. On 10y the drawdown gain survives every value of the new volume
   parameters and of the arming MA; on 5y it does not.

So: a genuine improvement in the 10-year risk-adjusted profile, a likely-but-not-
proven improvement in the 5-year one, and a large, clean set of negative results
for 1-minute order-flow trading.

## 1. Idea

The round-1 winner is a 165-day QQQ regime plus a 4% TQQQ intraday stop that is
*armed* only when QQQ is at/below its 20-day MA. Two facts motivated this agent:

1. **Volume is the classic confirmation variable for a breakdown.** If a 4% drop
   happens on ordinary or heavy participation it is information; if it happens on
   no volume it is a liquidity air pocket that mean-reverts. The volume literature
   is consistent with this: Gao, Han, Li & Zhou (2018) find intraday momentum is
   *stronger on higher volume days*, and Lee & Swaminathan (2000) show low-volume
   price moves are the persistent ones while high-volume moves are late-stage and
   reverse. If either is true here, the stop's *arming* should depend on volume.
2. **Order-flow proxies should be able to time intraday turns.** Cont–Kukanov–Stoikov
   (2014) show order-flow imbalance explains short-horizon price changes with an
   average R² of 65% at the event level; Chordia & Subrahmanyam (2004) find order
   imbalance predicts daily returns; and intraday work on Chinese exchanges finds
   imbalance predicts 1–90 minute returns. If any of that survives at 1-minute ETF
   resolution and after costs, a VWAP/flow overlay should add.

I tested both. The first worked, the second did not.

## 2. Data, harness and no-look-ahead

- Local adjusted 1-minute QQQ / TQQQ / BIL from `data/intraday-hf`, regular session
  only, via `research/bt.py` (`bt.load_1m`, 500 calendar days of warm-up).
  1,057,023 bars, 2,718 sessions (2016-01-04 → 2026-10-23). Test windows start
  2017-01-03 and 2021-10-25.
- `bt.panel` returns only opens and closes, so `vlib.py` repeats its alignment for
  **high, low and volume** on the same QQQ minute grid (a cached copy of the
  parquet, nothing new is downloaded). Volume is zero-filled where a symbol did not
  print; QQQ and TQQQ have 0.0% and 0.5% missing minutes respectively.
- Weights are target fractions set at bar *i* and filled at bar *i+1*'s open;
  slippage is charged on traded notional; long-only; weights sum to ≤ 1; band 2%.
- **Every signal uses bars ≤ *i*.** The regime uses the prior daily close vs its
  165-day SMA; the MA20 arming gate uses closes through the prior session;
  `rvol(i)` is cumulative volume **through bar i** divided by the mean of the same
  cumulative quantity over the **prior 20 sessions** at the **same minute of day**
  (`rolling(20).mean().shift(1)`). No same-day future information enters.
- `fastsim.py` re-implements `bt.simulate` exactly (only bars where the target
  vector changes can trade, because a 100%-of-book target is self-consistent). It
  reproduces `bt.run` on the round-1 winner to **0.0 equity difference, 657 fills,
  identical CAGR/DD**, and runs ~300× faster, which made the parameter grids
  affordable. Headline numbers in `result.json` come from the same code path;
  `strategy.py` uses `fastsim`.

## 3. Exact rules

```
For each session d (09:30–15:59 ET), with minute index i:
  SMA165[d] = mean(QQQ daily close, d-165 … d-1)          # prior closes only
  MA20[d]   = mean(QQQ daily close, d-20  … d-1)
  risk_on   = QQQ close[d-1] > SMA165[d]

  if not risk_on:
      hold BIL all session
  else:
      rvol(i) = cumQQQvol(09:30..i) / mean_prior20(cumQQQvol at the same minute)
      armed(i) = ( QQQ@09:30 < MA20[d] * 1.01   OR   rvol(i) > 1.5 )
                 AND rvol(i) > 1.0

      state = TQQQ
      for each minute i:
          if armed(i) and state and TQQQ close[i] < TQQQ open[d] * 0.96:
              state = BIL        # order fills at open[i+1], i.e. next minute
          weight[i] = state
      # after a stop the position stays in BIL through the close and the night;
      # next session restarts in TQQQ if the regime is still on.
```

- One position at a time, 100% TQQQ or 100% BIL. No leverage, no shorts.
- Parameters: stop 4% (inherited from the winner, not tuned), MA20 + 1% buffer
  (inherited), rvol high-volume threshold **1.5**, rvol floor **1.0**. Both new
  volume parameters are shown as surfaces in Section 6, as is the arming MA.
- Economic reading of the two volume clauses:
  - `rvol > 1.0` — *do not honour a stop on a below-average-volume day*: a −4% move
    without participation is a liquidity air pocket, not a trend.
  - `rvol > 1.5` — *do honour it on a high-volume day even in a strong short-term
    uptrend*: heavy participation confirms the breakdown, and the MA20 gate should
    not be allowed to veto the stop there.
- Half-days: the rule uses the last valid bar of the session, so a 13:00 close works
  unchanged. 195 stop events in the full sample (4–30 per year in the test window);
  at 110 of them `rvol` was above 1.5, and at 46 of those the MA20 gate was not
  armed at all — i.e. volume alone armed the stop.

## 4. Results

### 4.1 Headline

| Metric (1 bp, 1-minute marks) | 10y final | 10y winner | 5y final | 5y winner |
|---|---:|---:|---:|---:|
| CAGR | **65.90%** | 58.80% | **53.17%** | 49.88% |
| Total return | 14,186% | 9,205% | 741% | 655% |
| Max drawdown (1m marks) | **42.49%** | 44.56% | **28.64%** | 33.49% |
| Max drawdown (daily marks) | 39.43% | 41.62% | 28.20% | 33.08% |
| Sharpe (1m) | **1.35** | 1.24 | **1.21** | 1.16 |
| Sortino | 1.92 | 1.74 | 1.72 | 1.64 |
| Volatility | 45.19% | 46.12% | 43.26% | 43.39% |
| Fills | 801 | 657 | 361 | 337 |
| Ending equity on $100k | $14.29M | $9.30M | $841.0k | $754.8k |
| Max-DD peak → trough | 2018-03-13 → 2019-06-05 | same | 2026-06-22 → 2026-07-30 | same |

The drawdown *episodes* are identical to the winner's; only their depth changes.
Both strategies spend ~78% of test bars in TQQQ (final 78.1%, winner 79.0% on 10y;
70.2% vs 70.6% on 5y), so this is a stop rule, not a market-timing system.

### 4.2 Cost sensitivity

| Costs | 10y CAGR | 10y DD | 10y Sharpe | 5y CAGR | 5y DD | 5y Sharpe |
|---|---:|---:|---:|---:|---:|---:|
| 1 bp | **65.90%** | 42.49% | 1.35 | **53.17%** | 28.64% | 1.21 |
| 5 bp | 60.56% | 45.45% | 1.28 | 48.80% | 29.35% | 1.14 |
| 10 bp | 54.14% | 48.93% | 1.19 | 43.52% | 30.26% | 1.06 |
| winner, 5 bp | 54.60% | 47.08% | 1.18 | 45.89% | 34.13% | 1.09 |
| winner, 10 bp | 49.50% | 50.06% | 1.11 | 41.05% | 34.93% | 1.01 |

At **5 bp** the final still beats the winner on both metrics in both windows
(10y 60.56 vs 54.60 CAGR, 45.45 vs 47.08 DD; 5y 48.80 vs 45.89, 29.35 vs 34.13).
At **10 bp** it still does (54.14 vs 49.50, 48.93 vs 50.06; 43.52 vs 41.05,
30.26 vs 34.93). It passes at 10 bp, which the mandate asks for.

Caveat: the 5 bp 10y drawdown (45.45%) is *worse* than the 1 bp one (42.49%)
because the extra stop events concentrate in the 2018–19 whipsaw, while the 5y
drawdown barely moves (28.64% → 29.35%). Both still beat the winner.

### 4.3 Yearly returns (1 bp, calendar year)

| Year | Final | Winner | TQQQ |
|---|---:|---:|---:|
| 2017 | **143.19%** | 118.76% | 114.54% |
| 2018 | −1.94% | **0.47%** | −20.76% |
| 2019 | **57.20%** | 47.94% | 148.23% |
| 2020 | **267.85%** | 183.91% | 104.14% |
| 2021 | 44.35% | **60.61%** | 81.05% |
| 2022 | −17.99% | −17.99% | −79.39% |
| 2023 | 146.30% | **149.04%** | 192.05% |
| 2024 | 66.88% | **67.96%** | 62.43% |
| 2025 | **56.52%** | 43.29% | 32.10% |
| 2026 | **24.40%** | 16.76% | 22.62% |

- Beats TQQQ in 6 of 10 years and the winner in 5 of 10.
- The gain is concentrated exactly where it should be for a crash-arming rule:
  **2020 (+83.9 pp vs the winner)** and **2017 (+24.4 pp)**. It gives back
  **2021 (−16.3 pp)** and small amounts in 2018/2023/2024.
- 2022 is unchanged at −17.99% because the regime left risk-on before the stops
  mattered.

### 4.4 Rolling 3-year windows (28 overlapping, quarterly steps, 1 bp)

Summary: **26/28** windows beat TQQQ CAGR, **28/28** have lower drawdown than TQQQ,
**21/28** beat the *winner's* CAGR, **14/28** have a lower drawdown than the winner.

| Window | Final CAGR/DD | Winner CAGR/DD | TQQQ CAGR/DD |
|---|---:|---:|---:|
| 2017-01..2020-01 | 56.9 / 42.5 | 49.7 / 44.6 | 59.9 / 59.4 |
| 2017-10..2020-10 | 72.0 / 42.5 | 62.1 / 44.6 | 48.8 / 72.7 |
| 2018-07..2021-07 | 78.1 / 41.6 | 62.2 / 41.5 | 62.8 / 72.7 |
| 2019-07..2022-07 | 87.3 / 41.6 | 76.0 / 41.5 | 14.3 / 76.7 |
| 2020-01..2023-01 | 65.4 / 41.6 | 57.2 / 41.5 | −6.8 / 82.3 |
| 2021-01..2024-01 | 40.3 / 41.6 | **46.0** / 41.5 | 1.7 / 82.3 |
| 2022-01..2025-01 | 47.4 / 28.6 | 48.3 / 29.4 | −0.5 / 81.1 |
| 2023-10..2026-10 | 76.4 / 28.6 | 68.1 / **33.5** | 67.2 / 62.2 |

(Full 28-row table in `result.json` → `rolling_3y`.)

The pattern is clear: the final wins the **early** windows (2017–2020 starts) by
5–16 pp of CAGR because of 2020 and loses slightly in the 2021-start windows
(44.35% vs 60.61% in 2021 hurts). Its drawdown advantage over the winner appears in
the windows starting 2017-01 to 2018-01 (2020 crash) and again from 2021-10 onward
(July 2026); in the 14 windows starting 2018-04 to 2021-07 the two are within 0.1 pp.
That is the honest shape of the result.

## 5. Comparison against the targets

| Criterion | 10y | 5y | Verdict |
|---|---|---|---|
| Beat TQQQ CAGR **and** DD | 65.90 > 39.28, 42.49 < 81.68 ✅ | 53.17 > 13.47, 28.64 < 81.68 ✅ | **pass** |
| Strict dominance over the winner (higher CAGR, lower DD) | +7.10 pp, −2.07 pp ✅ | +3.28 pp, −4.85 pp ✅ | **pass on headline numbers** |
| Lower DD with CAGR within 2 pp | −2.07 pp DD, +7.10 pp CAGR ✅ | −4.85 pp DD, +3.28 pp CAGR ✅ | **pass** |
| Better rolling 3-year consistency | 21/28 higher CAGR than the winner, 14/28 lower DD | — | partial |
| Survives 10 bp | 54.14 / 48.93 vs 49.50 / 50.06 ✅ | 43.52 / 30.26 vs 41.05 / 34.93 ✅ | **pass** |

The headline table passes criterion 1. Section 8.2 shows that the 5y leg of that
pass depends on one stop event, so I would call this "10y pass, 5y conditional".

## 6. Robustness surfaces

All numbers are 10y CAGR/DD | 5y CAGR/DD. Baseline winner is 58.80/44.56 |
49.88/33.49.

**rvol floor** (high-volume re-arm at 1.5): every level from 0.90 to 1.10 beats the
winner on both windows.

| floor | 10y | 5y |
|---|---:|---:|
| 0.90 | 66.14/42.46 | 53.55/28.86 |
| 0.95 | 65.01/43.06 | 51.82/30.35 |
| **1.00** | **65.90/42.49** | **53.17/28.64** |
| 1.05 | 65.79/42.88 | 54.21/29.21 |
| 1.10 | 68.98/42.78 | 56.77/27.77 |

**High-volume re-arm threshold** (floor 1.0): every level 1.2–2.0 improves CAGR and
drawdown in both windows; the effect is weakest at 1.2, where the 5y CAGR is
unchanged (49.90% vs 49.88%).

| hi | 10y | 5y | stops |
|---|---:|---:|---:|
| 1.2 | 63.65/44.12 | 49.90/29.10 | 228 |
| 1.4 | 66.23/43.48 | 52.43/28.64 | 202 |
| **1.5** | **65.90/42.49** | **53.17/28.64** | 195 |
| 1.8 | 66.66/41.58 | 50.85/29.31 | 177 |
| 2.0 | 63.24/41.81 | 51.09/29.91 | 166 |

**Arming MA** (10/15/20/30/50): all improve 10y CAGR and lower 10y DD; 5y CAGR is
worse only at MA10. **Arm buffer** 0.00–0.03: all improve 10y; 5y is flat-to-better
except at 0.00–0.005.

**Stop distance** — the one parameter that is *not* smooth:

| stop | 10y | 5y |
|---|---:|---:|
| 3.0% | 63.52/48.37 | 50.90/35.22 |
| 3.5% | 65.32/45.35 | 51.56/29.00 |
| **4.0%** | **65.90/42.49** | **53.17/28.64** |
| 4.5% | 59.80/39.81 | 43.24/39.81 |
| 5.0% | 54.45/42.05 | 40.93/41.55 |

The 4% level is inherited from the round-1 winner and is not re-optimised here; the
3.5–4.0% region works and 4.5%+ collapses the 5y. This is a real sensitivity, not
a hidden parameter choice, but the reader should treat it as inherited, not proven.

**Ablation** — which clause does the work:

| Variant | 10y | 5y | stops |
|---|---:|---:|---:|
| round-1 winner | 58.80/44.56 | 49.88/33.49 | 160 |
| volume floor only (`rvol>1.0`, no re-arm) | 57.70/42.86 | 51.79/29.91 | 149 |
| high-volume re-arm only (`rvol>1.5`, no floor) | 67.06/44.21 | 51.25/33.49 | 206 |
| **both** | **65.90/42.49** | **53.17/28.64** | 195 |

Reads cleanly: the **floor** buys drawdown (both windows), the **re-arm** buys
CAGR (10y), and they are complementary.

## 7. What did NOT work (the negative battery)

This is most of the work. Each line is a measured result on this data, 1 bp unless
stated, risk-on days only, next-bar fills.

### 7.1 1-minute order-flow proxies have no forward power

| Feature (QQQ) | horizon | n | corr with forward TQQQ return |
|---|---|---:|---:|
| cumulative CLV-signed volume `F = Σ(v·CLV)/Σv` | 30 min | 155,273 | **−0.010** |
| VWAP deviation `close/VWAP − 1` | 30 min | 155,273 | **−0.009** |
| cumulative same-time RVOL | 30 min | 155,273 | **−0.047** |
| 1-bar RVOL | 30 min | 155,273 | +0.007 |
| 5m cumulative flow | 30 min | 129,128 | +0.001 |
| 5m VWAP deviation | 30 min | 129,223 | +0.007 |
| 5m cumulative RVOL | 30 min | 129,223 | +0.006 |

The cumulative-RVOL coefficient (−0.047) is the largest, but its bucket profile is
non-monotone: the bottom quintile predicts **+35 bp** over the next 30 minutes and
the top quintile **−52 bp**, i.e. it says "extreme flow is contrarian", not
"momentum confirmed". Spread across 30 bp at 1-minute resolution with ~2 bp of
round-trip cost is not a tradable edge, and it does not reproduce by era
(2017–19 r≈0.00, 2020–21 +0.03, 2022–26 +0.04).

This is not surprising in hindsight. VWAP is an *execution* benchmark — the
literature is about tracking it, not forecasting from it (Konishi 2002; Frei &
Westray 2015) — and the one recent paper that proposes a VWAP-deviation
mean-reversion strategy explicitly leaves the backtest "to future work"
(Bhatti 2026). On this data, deviation from VWAP carries no forward information at
1-minute or 5-minute resolution.

### 7.2 Volume-confirmed momentum / intraday momentum

Gao et al. (2018) report that the first half-hour return predicts the last half-hour
return, *more strongly on high-volume days*. On QQQ 2017–2026 that effect is absent
at this resolution:

| Signal | corr with TQQQ last-30-min return | top-minus-bottom quintile |
|---|---:|---:|
| QQQ first-30-min return | +0.022 | +4 bp |
| same, low-RVOL days | −0.050 | −9 bp |
| same, high-RVOL days | +0.043 | +23 bp |

The high-volume cell has the right sign and roughly the published magnitude, but
the effect is 20–40 bp *per day* only in the top quintile of a noisy sort, it
vanishes when I condition on the sign of the first half hour, and at 2 bp round-trip
it is marginal. A direct volume-confirmed 5m momentum trade — go long TQQQ for 30
minutes when the last 5m return is positive and 5m RVOL > 1.2 — earns **−1.06 bp**
per trade before cost and −3.06 bp after. Dead.

### 7.3 Overnight volume gating (the promising one that failed)

High-relative-volume days are followed by bad nights in the pooled sample
(rvol>1.5 & down: −74.9 bp mean overnight; rvol>1.5 & up: −124.4 bp; rvol≤1.5:
+25 to +35 bp; pooled corr −0.19, and it is *not* explained by 20-day volatility,
whose correlation with the next overnight is −0.001). So "go to BIL overnight after
a high-volume session" looked strong.

It is not robust:

| Era | n (rvol>1.5) | overnight mean, high rvol | overnight mean, rest | spread |
|---|---:|---:|---:|---:|
| 2017–2019 | 75 | +0.16% | +0.21% | −0.05% |
| 2020–2021 | 68 | +0.03% | +0.26% | −0.23% |
| 2022–2026 | 54 | +0.21% | +0.15% | **+0.06%** |

In the 5y window high-volume nights were *better* than normal ones (+0.236% vs
+0.155%). Applied to the winner, the gate improves 10y drawdown slightly and
destroys the 5y:

| Gate on the winner | 10y | 5y |
|---|---:|---:|
| none (winner) | 58.80/44.56 | 49.88/33.49 |
| rvol > 1.5, full exit | 57.35/44.52 | 41.08/36.14 |
| rvol > 1.8, full exit | 58.15/42.98 | 44.76/35.84 |
| rvol > 2.0, full exit | 61.15/43.45 | 47.24/35.84 |
| rvol > 1.5 & QQQ<MA20, full exit | 48.54/44.70 | 38.91/36.14 |

The pooled average is a 2020 artifact. Rejected.

### 7.4 Other failures

- **Volume-confirmed regime exit** (leave risk-on only on a high-volume break below
  the 165-day SMA): 51.18/52.30 at rvol>0.9, 43.78/57.07 at 1.1 — better return,
  worse drawdown. Rejected.
- **Distribution-day counting** (IBD-style: count days down >0.2% on rising volume
  in a 20–30 session window, de-risk at 4–6): keeps you out of the market 43–95% of
  the time and returns 3–37% CAGR. Hopeless at this horizon. Rejected.
- **VWAP / OBV / A-D as the regime instead of the SMA**: 165-day VWAP 47.08/58.03
  (10y) and 30.49/44.94 (5y) vs SMA 46.63/58.76 and 36.14/42.17. Adding an
  OBV>MA165 filter: 28.24/61.09. Nothing improves.
- **Continuous volume-scaled stop** `stop_i = 4%·(1 + c·(1 − rvol_i))`: best point
  (S=3.5%, c=0.3) 61.77/47.68 | 53.54/32.84 — better 5y, worse 10y. Rejected in
  favour of the discrete arming rule.
- **Volume at the stop bar as a crash/wick classifier**: the post-stop drift is not
  monotone in rvol at the trigger. Quartile means of stop→next-open: −1.61%,
  −0.76%, +0.49%, −0.08%. The lowest-rvol stops were the *worst* ones (n=29 per
  bucket). Except for the floor rule used above, volume does not tell you whether a
  stop was right.
- **Volume spike reversal** (QQQ 1m return < −0.5% with 1m RVOL > 10): only 6 events
  in 10 years, +228 bp over the next 30 minutes. Too rare to build on, and the
  threshold was chosen after seeing the data.
- **5m momentum × RVOL grid** (8 cells): only "rvol>2.0 and down" is positive after
  2 bp (+5.7 bp, n=1,992); the other seven are negative. Noise, and not actionable
  in a long-only book.

## 8. Honest caveats

### 8.1 The 10y gain is a 2020 gain

2020 contributes +83.9 pp of calendar return versus the winner. Without 2020 the
10y CAGR advantage is roughly +2 pp. This is the same structural caveat the round-1
report makes about its own edge — it is a tail overlay, not broad alpha. The
mechanism is nonetheless the intended one: the volume re-arm fires the stop on
**2020-02-20 and 2020-02-21** — the day after QQQ's February 2020 all-time high, with
the MA20 gate not armed — and on 14 further 2020 sessions, i.e. it buys crash
insurance exactly where the slow regime is blind.

### 8.2 The 5y drawdown gain is one event

The final rule suppresses a stop on **2026-06-24** that the winner takes. That day
TQQQ broke −4% from the open at 14:31 on **0.87× normal cumulative volume** — a
below-average-volume break — so the floor declined to honour it. Suppressing it moves
the subsequent entry/exit schedule, and by 2026-07-30 the strategy is 5.5 pp less
deep in drawdown than the winner. There is no economic reason to expect that specific
outcome to repeat: the rule simply happened to skip a stop on a quiet day near a
local low, and the resulting path was better.

| Variant | 10y | 5y |
|---|---:|---:|
| final (stop suppressed) | 65.90/42.49 | 53.17/**28.64** |
| re-enable that one stop | 64.54/42.49 | 50.72/**34.16** |

So the 5y drawdown improvement — and most of the 5y CAGR improvement (2.45 of the
3.28 pp) — is a single observation. The rule did not "know" it was a bottom; it only
knew volume was below normal. Eleven stops differ in the other direction (the winner
takes them, the final does not); re-enabling them individually moves 5y CAGR between
−2.5 and +1.2 pp and, excluding 2026-06-24, moves the 5y drawdown by at most 0.75 pp.
So the rest of the difference is benign — but the 5y drawdown leg rests on one event,
and I would not claim it as an edge.

The 10y drawdown improvement (−2.07 pp) survives every value of the two new volume
parameters (floor 0.90–1.10, re-arm 1.2–2.0) and of the arming MA (10–50), so that
leg is real; it does *not* survive shortening the inherited stop to 3.0–3.5% (10y DD
48.4% / 45.4%), which is the one place where the result is parameter-sensitive.

### 8.3 Other

1. **Inherited parameters.** The 4% stop, MA20 and the 1% buffer are the round-1
   winner's, not re-optimised here. Only the two volume parameters are new, and both
   are shown as surfaces rather than single points.
2. **The quiet-day rule is a hard threshold** at rvol = 1.0. It has a natural
   interpretation ("participation at least normal") but it is a threshold; the
   surface 0.90–1.10 is flat, which is the relevant robustness check.
3. **1 bp is optimistic** for a stop that fills at the next minute's open in a fast
   market. The 5 bp and 10 bp rows are the honest range and both still pass.
4. **Turnover**: 801 fills over 10 years (~82/yr vs the winner's 67/yr). Tax-
   inefficient in a taxable account; all results are pre-tax.
5. **No shorting, no intraday leverage**, single instrument family (3× Nasdaq-100).
6. **Drawdown marks** are 1-minute equity marks (harness standard); daily-mark DDs
   are 39.43% / 28.20%.
7. **Benchmark**: TQQQ buy-and-hold on 1-minute marks is 39.38/82.29 (10y) and
   14.29/82.29 (5y); the README's daily figures are 39.28/81.68 and 13.47/81.68.
   The pass/fail conclusion is identical either way.
8. **Half-day volume alignment**: the same-time-of-day volume baseline treats a
   prior half-day's truncated cumulative volume as if it were the full-day value at
   late minutes, which biases `rvol` up by ~5% on the day after a half-day. Immaterial
   for a 1.0/1.5 threshold, but it is a known approximation.

## 9. Reproduction

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
python research\agents2\volume-orderflow\strategy.py        # writes result.json
python research\agents2\volume-orderflow\robustness.py      # parameter surfaces + 5m tests
python research\agents2\volume-orderflow\final_numbers.py   # yearly / rolling / DD points
python research\agents2\volume-orderflow\event_sensitivity.py  # 8.2 single-event test
```

Supporting files, all inside this folder: `vlib.py` (panel + volume cache),
`engine.py` (data/features/weights/metrics), `fastsim.py` (exact fast simulator),
`explore1..9.py` (the negative battery), `variants1..10.py`, `arming_grid.py`
(vectorised arming grid). No core repository file was modified.

## References

**Volume and momentum**
- Lee, C. M. C., & Swaminathan, B. (2000). *Price momentum and trading volume.*
  Journal of Finance 55(5), 2017–2069. High-volume winners reverse faster; low-volume
  moves persist. [doi](https://doi.org/10.1111/0022-1082.00280)
- Gao, L., Han, Y., Li, S. Z., & Zhou, G. (2018). *Market intraday momentum.*
  Journal of Financial Economics 129(2), 394–414 — first half-hour return predicts
  the last half-hour, **stronger on higher-volume days**.
  [doi](https://doi.org/10.1016/j.jfineco.2018.05.009),
  [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2552752)
- Gervais, S., Kaniel, R., & Mingelgrin, D. H. (2001). *The high-volume return
  premium.* Journal of Finance 56(3), 877–919; international replication:
  [JFE 2012](https://www.sciencedirect.com/science/article/abs/pii/S0304405X11001954)
- Bornholt, G., Dou, P., & Malin, M. (2015). *Trading volume and momentum: the
  international evidence* — volume-based momentum beats pure momentum in 34/37
  countries. [pdf](https://sites.uwasa.fi/mfjuva/wp-content/blogs.dir/4/files/sites/231/2025/02/MJ0p1a4fk7lfg1h65i61du41mm5lt14.pdf)
- *Persistence or reversal? The effects of abnormal trading volume on stock returns*
  (2024), European Journal of Finance — abnormal volume predicts positively at short
  horizons and reverses over the long run.
  [link](https://www.tandfonline.com/doi/full/10.1080/1351847X.2024.2303092)
- Counter-evidence for the practitioner version of the rule: *Volume-confirmed
  momentum on US stocks, 2001–2025* — 7.92% CAGR vs 8.59% for SPY, −61% max DD.
  [link](https://blog.tradingstudio.finance/volume-confirmed-momentum-us-stocks-backtest/)

**Order flow / VWAP**
- Cont, R., Kukanov, A., & Stoikov, S. (2014). *The price impact of order book
  events.* Journal of Financial Econometrics 12(1), 47–88 — OFI explains short-horizon
  price changes, average R² 65%. [doi](https://doi.org/10.1093/jjfinec/nbt003),
  [arXiv](https://arxiv.org/abs/1011.6402)
- Chordia, T., Roll, R., & Subrahmanyam, A. (2002) / Chordia & Subrahmanyam (2004).
  *Order imbalance and individual stock returns.* JFE 72(3), 485–518.
  [link](https://www.sciencedirect.com/science/article/abs/pii/S0304405X03001752)
- Intraday order-imbalance predictability at 1–90 minute horizons (Chinese market):
  [JBF 2015](https://www.sciencedirect.com/science/article/pii/S0927538X15300056)
- Negative result for imbalance-based intraday technical rules (Tokyo Stock
  Exchange; Reality Check / SPA tests, rules underperform buy-and-hold):
  [JBF 2012](https://www.sciencedirect.com/science/article/pii/S0378426612001756)
- Konishi, H. (2002). *Optimal slice of a VWAP trade.* Journal of Financial Markets
  5(2), 197–221 — VWAP as an execution benchmark, not a forecast.
  [link](https://www.sciencedirect.com/science/article/abs/pii/S1386418101000234)
- Frei, C., & Westray, N. (2015). *Optimal execution of a VWAP order: a stochastic
  control approach.* Mathematical Finance 25(3), 612–639.
  [pdf](https://www.math.ualberta.ca/~cfrei/CFNW2015.pdf)
- Bhatti, A. (2026). *Momentum exhaustion and fair value reversion: an ADX-conditioned
  VWAP strategy* — proposes VWAP-deviation reversion, "formal backtesting … left to
  future work". [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6454659)

**Stops and the inherited base**
- Kaminski, K. M., & Lo, A. W. (2014). *When do stop-loss rules stop losses?*
  Journal of Financial Markets 18, 234–254.
  [doi](https://doi.org/10.1016/j.finmar.2013.07.001)
- Lou, D., Polk, C., & Skouras, S. (2019). *A tug of war: overnight versus intraday
  expected returns.* JFE. [pdf](https://personal.lse.ac.uk/polk/research/TugOfWar.pdf)
- Round-1 winner: `research/agents/daily-regime-minute-entry/report.md`
