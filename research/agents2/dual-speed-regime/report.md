# Dual-speed regime: 165-day slow gate + armed 60-minute EMA(40) fast filter

**Agent:** `dual-speed-regime` (round 2, agent 13) · **Date:** 2026-11-25
**Mandate:** keep the 165-day QQQ SMA as the slow gate, add a faster 20/50-day MA or
60-minute EMA filter to exit earlier in drawdowns and re-enter on a reclaim; test 2–4
variants and the optional 4% minute stop; report 1/5/10 bp, yearly and rolling 3-year
windows; beat TQQQ (39.28/81.68 10y, 13.47/81.68 5y) and, if possible, the round-1 winner
(58.80/44.56 10y, 49.88/33.49 5y at 1 bp).

## Verdict

**Strict dominance over the round-1 winner on both windows, at 1 bp, 5 bp and 10 bp.**
The winning design is not a faster *daily* gate — those were disastrous (Section 5). It is a
60-minute QQQ EMA(40) filter that is allowed to act **only on sessions that are already
short-term weak** (QQQ's first minute below its prior 20-day SMA × 1.01, the winner's own
arming rule), and only on a **fresh 60-minute cross**. The 165-day gate still owns the
overnight position; the fast filter manages the intraday session and re-enters on a reclaim.
The 4% stop is retained for gap protection.

| Window | Strategy 1 bp | Strategy 5 bp | Strategy 10 bp | Winner 1 bp | TQQQ |
|---|---:|---:|---:|---:|---:|
| 10y CAGR / max DD | **70.11% / 42.91%** | **61.44% / 44.25%** | **51.23% / 49.25%** | 58.80% / 44.56% | 39.28% / 81.68% |
| 5y CAGR / max DD | **61.78% / 25.88%** | **53.93% / 26.81%** | **44.65% / 28.57%** | 49.88% / 33.49% | 13.47% / 81.68% |
| 10y Sharpe (1 bp) | 1.42 | 1.30 | 1.15 | 1.24 | 0.84 |

- **vs TQQQ:** higher CAGR and less than two-thirds of the drawdown on both windows, at every
  cost level. Pass.
- **vs the winner:** higher CAGR *and* lower max drawdown on both windows at 1 bp and 5 bp.
  At 10 bp the 10-year margin is thin (51.23% vs 49.50% CAGR; 49.25% vs 50.06% DD) but still
  a pass. Target option 1 (strict dominance) is met; option 2 is met trivially as well.
- **Rolling 3-year consistency:** 25 of 27 quarterly windows beat TQQQ on both CAGR and DD
  (winner: 23/27). The worst 3-year CAGR is 47.6% (winner 28.9%) and the worst 3-year max DD
  is 42.9% (winner 44.6%).

The honest caveat is in Section 8: the improvement is not uniform. 2022 is identical to the
winner, 2024 is slightly worse, and most of the extra CAGR comes from 2019, 2023 and 2026.
The 60-minute filter is a real, economically motivated overlay, but it is also a new
parameter selected on this sample. Treat the 10 bp 10-year row as the realistic margin.

## 1. Idea and prior work

The starting point is the round-1 result: a 165-day QQQ regime plus a 4% minute stop cut
TQQQ's −81.7% drawdown to −44.6% and raised CAGR from 39.3% to 58.8%. Its weakness is that
the slow gate is blind to a fast decline: QQQ can fall 15% before the 165-day average turns,
and the stop only fires after TQQQ is already 4% below the session open. A faster filter
should exit earlier and re-enter on a reclaim.

The literature is unusually clear about the trade-off:

1. **Slow trend filters reduce risk, not necessarily return.** Faber's 10-month/200-day rule
   cuts drawdown roughly in half but gives up return in long bull markets, and its cost is
   paid through whipsaws in choppy markets
   ([Faber 2007/2013](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=962461),
   [MarketHeist](https://marketheist.io/portfolio/learn/trend-filter),
   [Quantum Bias](https://quantum-bias.com/blog/10-month-moving-average-nasdaq-100)).
2. **A 12-month absolute-momentum filter cannot react to a crash inside a single month.**
   A 29-year dual-momentum replication finds the trend filter does all the risk work, but
   the worst drawdown was 2020, and the suggested fix is a second, faster 1–3 month trend
   check — accepting more whipsaw in exchange
   ([AlgoStrategyLab, 2026](https://algostrategylab.github.io/dual-momentum/)).
3. **Faster trend models truncate the left tail but cost Sharpe after costs.** Man AHL's
   speed study shows the fastest model has the best skewness and the worst after-cost
   Sharpe; turnover falls roughly linearly with slower speeds
   ([Man AHL, 2023](https://www.man.com/documents/download/2739e-f3a21-bb8ce-f81f3/Man_Perspective_The_Need_for_Speed_in_Trend-Following_Strategies_English_04-01-2023.pdf?type=view),
   [Graham Capital, 2018](https://www.grahamcapital.com/wp-content/uploads/2023/08/The-Speed-of-Trend_Graham-Research_March-2018-1-1.pdf)).
4. **Daily checks of a slow average whipsaw far more than monthly checks.** In a 49-year
   SPY/QQQ study, 78% of daily 200-day switches reversed within a month; a 3% band or a
   month-end check restored most of the return
   ([BestFolio, 2026](https://bestfolio.app/blog/trend-filter-start-dates)). False-signal
   rates for simple price-vs-MA rules run 57–76%
   ([QuantifiedStrategies, 2025](https://www.quantifiedstrategies.com/how-likely-is-a-false-signal-in-moving-average-trading/)),
   and smoothing the trigger with a 50-day average raises the win rate but changes the timing
   rather than eliminating whipsaw
   ([StockCharts SystemTrader](https://articles.stockcharts.com/article/articles-arthurhill-2016-11-systemtrader---how-to-become-a-smooth-operator-with-moving-averages---backtesting-different-moving-average-pairs/)).

That suggested three design constraints:

- **Do not replace the slow gate with a fast one.** A fast daily gate holds BIL overnight,
  and essentially all of TQQQ's drift is overnight (round-1 decomposition: overnight +1,355%
  vs intraday +81% over 2017–2026; see
  [Lou, Polk & Skouras 2019](https://personal.lse.ac.uk/polk/research/TugOfWar.pdf)). Being
  out of a whole session is expensive.
- **Arm the fast filter.** Only act when the short-term trend is already weak (QQQ below its
  20-day MA), so the fast filter does not spend 2019/2021/2023 selling every 3-day dip.
- **Trade the fast filter intraday, on crosses, and re-enter on a reclaim.** This keeps the
  overnight position with the slow gate, uses the fast filter where the information is
  (intraday weakness), and avoids the daily whipsaw documented above.

The 4% stop from the winner is retained. Kaminski & Lo's condition — stops add value when
returns have momentum/regime shifts — is the license for keeping it
([Kaminski & Lo 2014](https://doi.org/10.1016/j.finmar.2013.07.001)).

## 2. Data, harness, no-look-ahead

- Data: adjusted 1-minute QQQ / TQQQ / BIL from `data/intraday-hf`, regular session only,
  loaded with `bt.panel(("QQQ","TQQQ","BIL"), "2017-01-03", "2026-10-23", "1min")`
  (500 calendar days of warm-up). 1,057,023 bars, 2,718 sessions, 2016-01-04 → 2026-10-23.
- `weights[i]` is the target set from the close of bar *i* and fills at bar *i+1*'s open
  (`research/bt.py`). Slippage is charged on traded notional; `band=0.02`; long-only; weights
  sum to ≤ 1. Headline cost 1 bp one-way; 5 bp and 10 bp reported.
- Daily gate: QQQ's **prior** session close vs the 165-day SMA through that close. No same-day
  daily information is used.
- Fast filter: session-aligned 60-minute bars (09:30–10:29, 10:30–11:29, …, 14:30–15:29,
  15:30–15:59). A bar's signal is known at its last minute and is applied from the following
  minute; the fill is the next minute's open (one minute later than the earliest possible
  fill, i.e. conservative).
- Arming: QQQ's 09:30 first-minute close vs the prior session's 20-day SMA × 1.01. The first
  minute is known before the first 60-minute decision.
- Stop: TQQQ's current minute close vs the session open; fill next minute.
- No shorts, no leverage beyond 100% TQQQ, one position at a time. BIL earns its own carry
  while out; no separate cash yield is added.

## 3. Exact rules (headline C4-40)

```
For each session d (09:30-15:59 ET):
  SMA165[d] = mean(QQQ daily close, d-165 ... d-1)
  MA20[d]   = mean(QQQ daily close, d-20  ... d-1)
  slow_on   = QQQ close[d-1] > SMA165[d]

  if not slow_on:
      hold BIL for the whole session and overnight
  else:
      armed = QQQ 09:30 close < MA20[d] * 1.01
      state = TQQQ                       # session resets long at the open
      base  = TQQQ open of session d
      for each minute i:
          # fast filter: only on a fresh 60m cross, only when armed
          if armed and 60m_state[i] != 60m_state[i-1]:
              if state == TQQQ and 60m_state[i] == down: state = BIL
              elif state == BIL and 60m_state[i] == up:  state = TQQQ
          # crash stop
          if armed and state == TQQQ and TQQQ close[i] < base * 0.96:
              state = BIL
          weight[i] = state              # fills at open[i+1]
      # the 14:30-15:29 bar's state carries into the close/overnight;
      # the 15:30-15:59 bar only seeds the next session's first-hour cross
```

`60m_state` is `QQQ 60-minute close > EMA(40) of 60-minute closes`. EMA span 40 bars ≈ 6.2
sessions. The fast filter acts on **crosses**, not on the level: a session that opens with
the filter already below its EMA is not sold immediately; only a fresh deterioration triggers
an exit. This is deliberate — it avoids selling gap-down opens that mean-revert, and it is
the difference between the profitable crossover variant and the much weaker "level" variant
(Section 5).

- Effective parameters: slow SMA 165 (given), fast EMA 40 bars (≈6.2 sessions), stop 4%
  (inherited), arm MA20 +1% (inherited). The only new parameter is the EMA span.
- One position at a time: 100% TQQQ or 100% BIL. No partial sizing in the headline variant.

## 4. Results

### 4.1 Headline (1 bp, 1-minute marks)

| Metric | 10y | 5y |
|---|---:|---:|
| CAGR | **70.11%** | **61.78%** |
| Max drawdown (1m marks) | **42.91%** | **25.88%** |
| Sharpe (annualized, 1m) | **1.42** | **1.36** |
| Fills | 1,281 | 621 |
| Max-DD peak → trough | 2021-02-16 → 2021-03-25 | 2024-07 (≈25.9%) |
| Fill rate | ~65 round trips/yr | ~62 round trips/yr |

The 10-year max drawdown is now the **2021 growth correction**, not 2018–19: the fast filter
cut the 2018–19 episode from 44.56% to 39.89%. The 2020 COVID episode is 33.03% (peak
2020-02-19 → trough 2020-02-28), and the September 2020 air pocket is 31.05%. The 5-year
worst is 25.88%, about 7.6 pp below the winner's 33.49%.

### 4.2 Cost sensitivity

| Costs | 10y CAGR | 10y DD | 10y Sharpe | 5y CAGR | 5y DD | 5y Sharpe |
|---|---:|---:|---:|---:|---:|---:|
| 1 bp | **70.11%** | 42.91% | 1.42 | **61.78%** | 25.88% | 1.36 |
| 5 bp | 61.44% | 44.25% | 1.30 | 53.93% | 26.81% | 1.24 |
| 10 bp | 51.23% | 49.25% | 1.15 | 44.65% | 28.57% | 1.09 |

Each extra basis point costs about 2.1 pp of 10-year CAGR — twice the winner's ~1.0 pp/bp,
because the fast filter roughly doubles the fill count (1,281 vs 657). Even so, the 5 bp and
10 bp rows dominate the winner's corresponding rows. At 10 bp the 10-year drawdown margin is
only 0.8 pp; that row should be read as a marginal pass, not a comfortable one.

### 4.3 Yearly returns (calendar year, 1 bp)

| Year | Strategy | TQQQ | Winner | Strategy − winner |
|---|---:|---:|---:|---:|
| 2017 | **124.7%** | 114.5% | 118.8% | +5.9 pp |
| 2018 | **1.9%** | −20.8% | 0.5% | +1.4 pp |
| 2019 | **89.6%** | 148.2% | 47.9% | +41.7 pp |
| 2020 | **184.1%** | 104.1% | 183.9% | +0.2 pp |
| 2021 | 69.6% | 81.1% | 60.6% | +9.0 pp |
| 2022 | **−18.0%** | −79.4% | −18.0% | 0.0 pp |
| 2023 | **173.4%** | 192.0% | 149.0% | +24.4 pp |
| 2024 | 66.9% | 62.4% | 68.0% | −1.1 pp |
| 2025 | **43.8%** | 32.1% | 43.3% | +0.5 pp |
| 2026 | **48.5%** | 22.6% | 16.8% | +31.7 pp |

- Beats TQQQ in **7 of 10** calendar years; beats the winner in 8 of 10 and ties 2022.
- 2022 is identical because the slow gate and the stop do all the work in a slow bear; the
  fast filter has little to add when the 165-day gate is already off.
- 2024 is the one year materially behind the winner (−1.1 pp): the fast filter exited during
  the July–August 2024 yen-carry unwind and re-entered late relative to simply holding.
- The large gains in 2019, 2023 and 2026 are the fast filter's contribution: it exits the
  weak intraday stretches inside otherwise strong years and re-enters on the reclaim.
- The worst months are approximately 2018-03 (−18.9%), 2018-04 (−11.6%), 2018-10
  (−16.1%), 2019-05 (−18.5%), 2021-02 (−16.5%), 2021-03 (−11.2%) and 2026-07 (−18.6%).
  The winner lost 20.2%, 19.9%, 23.8% and 23.8% in 2018-03, 2018-10, 2019-05 and 2026-07;
  the fast filter cuts each of those tail months.

### 4.4 Drawdown anatomy (10y, 1 bp)

| Depth | Peak | Trough | Recovered |
|---:|---|---|---|
| 42.91% | 2021-02-16 10:37 | 2021-03-25 11:25 | 2021-07-13 10:03 |
| 39.89% | 2018-03-13 09:47 | 2019-06-05 10:52 | 2019-10-28 09:30 |
| 33.03% | 2020-02-19 14:44 | 2020-02-28 10:04 | 2020-05-21 09:39 |
| 31.05% | 2020-09-02 15:49 | 2020-09-21 10:40 | 2020-10-12 09:30 |

The 2018–19 episode is still the longest (recovery took until late 2019), but it is no longer
the deepest. The 2020 crash is cut to −33.0% and recovered by late May, versus the winner's
−39.3% into 2020-03-09. The 5-year max (25.88%) is about three-quarters of the winner's 33.49%.

### 4.5 Rolling 3-year windows (quarterly starts, 1 bp)

| | Strategy | Winner |
|---|---:|---:|
| 3-year windows | 27 | 27 |
| Beat TQQQ on both CAGR and DD | **25 / 27** | 23 / 27 |
| Worst 3-year CAGR | **47.6%** | 28.9% |
| Worst 3-year max DD | **42.9%** | 44.6% |

This is the strongest consistency evidence: even the worst 3-year window returned 47.6% a
year, and the worst 3-year drawdown was slightly shallower than the winner's. The two windows
that do not beat TQQQ on both dimensions are windows where TQQQ's CAGR is enormous and the
strategy's drawdown is not lower (the fast filter does not help in a pure melt-up). The 5y
window has only nine quarterly 3-year windows and is not tabulated separately.

## 5. What did not work

This is the more useful part of the round-2 mandate. **Every faster daily gate failed, and
the unarmed 60-minute filters failed.** The fast filter only adds when it is armed and only
in crossover form.

### 5.1 Faster daily MA gates (whole-session TQQQ/BIL, 1 bp)

| Variant | 10y CAGR | 10y DD | 5y CAGR | 5y DD |
|---|---:|---:|---:|---:|
| Control: 165-day gate only | 46.63% | 58.76% | 36.14% | 42.17% |
| 165 + QQQ > MA20 | 26.30% | 46.06% | 11.85% | 46.06% |
| 165 + QQQ > MA50 | 30.51% | 46.70% | 25.98% | 40.92% |
| 165 + QQQ > MA100 | 24.31% | 61.72% | 20.82% | 49.37% |
| 165 + MA20 + 4% stop | 28.62% | 46.08% | 16.50% | 40.50% |
| 165 + MA50 + 4% stop | 35.80% | 43.20% | 30.62% | 42.56% |
| 165 + MA100 + 4% stop | 38.97% | 54.10% | 35.97% | 36.30% |

A 20/50/100-day daily gate loses 16–28 pp of CAGR against the 165-day control. The reason is
the overnight drift: the gate forces whole nights in BIL, and the whipsaw cost is paid in the
strong years. Adding the 4% stop recovers some of it but never comes close to the winner.
**A faster daily MA is the wrong place to add speed on this instrument.**

### 5.2 60-minute filters without arming

| Variant | 10y CAGR | 10y DD | 5y CAGR | 5y DD |
|---|---:|---:|---:|---:|
| Continuous 60m EMA(20), overnight included | 32.54% | 43.44% | 20.53% | 29.05% |
| Continuous 60m EMA(50), overnight included | 35.28% | 34.30% | 24.97% | 30.15% |
| Intraday-only 60m EMA(50), re-enter at next open | 31.70% | 43.14% | 22.33% | 32.06% |
| Armed 60m EMA(40) **level** (exit whenever below) | 47.77% | 36.66% | 39.93% | 31.00% |
| Armed 60m EMA(40) **crossover**, no stop | 67.23% | 55.44% | — | — |
| **Armed 60m EMA(40) crossover + 4% stop (headline)** | **70.11%** | **42.91%** | **61.78%** | **25.88%** |

- Continuous 60-minute filters have low drawdowns but give up 35–38 pp of CAGR. They trade
  too often and are out of the market on too many up days.
- The "level" version — the most literal "hold only while the 60-minute close is above its
  EMA" — is much safer (36.66% DD) but also gives up 22 pp of CAGR. It exits on every down
  bar, including gap-down opens that mean-revert.
- Without the 4% stop, the crossover version has a 55.44% 10-year drawdown: the fast filter
  handles slow bleeds, but only the stop handles the 2020-style gap crash. The two overlays
  are complementary, not substitutes.

### 5.3 Forced close re-entry (aggressive variant)

Forcing the position back to TQQQ at every session close (so the overnight is always held
when the slow gate is on) gives **72.72% / 42.02%** at 10y and **62.11% / 27.25%** at 5y
(1 bp). It is a legitimate "slow gate owns the overnight, fast filter owns the session"
architecture and it has the best 10-year CAGR. I did not make it the headline because it
removes the stop's overnight gap protection: after a 4% stop you buy back at the close and
take the gap. In a future 2020-style event that is the wrong tail to be exposed to, and the
5-year drawdown is slightly worse than the headline (27.25% vs 25.88%). It is reported as a
neighbour, not promoted.

## 6. Robustness

### 6.1 EMA span surface (1 bp, stop 4%, arm MA20×1.01)

| Span (60m bars) | ≈ sessions | 10y CAGR | 10y DD | 5y CAGR | 5y DD |
|---:|---:|---:|---:|---:|---:|
| 25 | 3.8 | 65.40% | 46.08% | 53.99% | 29.73% |
| 30 | 4.6 | 67.91% | 46.86% | 59.15% | 30.68% |
| 35 | 5.4 | 68.88% | 44.43% | 59.68% | 29.43% |
| **40** | **6.2** | **70.11%** | **42.91%** | **61.78%** | **25.88%** |
| 45 | 6.9 | 63.15% | 44.17% | 56.14% | 29.40% |
| 50 | 7.7 | 61.23% | 46.10% | 55.71% | 31.14% |

The dominance region is spans **35–45**: all three have higher CAGR and lower DD than the
winner on both windows. Spans 30 and 50 still beat the winner on CAGR but not on the 10-year
drawdown (46.86% and 46.10% vs 44.56%). Span 40 is the middle of the plateau, not a lone
peak; but the plateau is only three grid points wide, and 40 was chosen after looking at the
surface. This is in-sample parameter selection and should be discounted accordingly.

### 6.2 Stop surface (span 40, 1 bp)

| Stop | 10y CAGR | 10y DD | 5y CAGR | 5y DD |
|---:|---:|---:|---:|---:|
| 3.0% | 63.76% | 43.84% | 56.59% | 28.41% |
| 3.5% | 69.10% | 44.27% | 64.39% | 25.61% |
| **4.0%** | **70.11%** | **42.91%** | **61.78%** | **25.88%** |
| 4.5% | 67.96% | 40.65% | 56.58% | 37.12% |
| 5.0% | 65.44% | 41.97% | 56.69% | 38.76% |

Stops 3.0–4.0 dominate the winner on both windows. At 4.5–5.0 the 10-year drawdown is lower
still, but the 5-year drawdown jumps to 37–39% — worse than the winner's 33.49% — because the
stop stops firing in the 2026 summer slide. The 4.0% choice (inherited from the winner, not
tuned here) sits on the safe side of that cliff. This is a genuine fragility: the 5-year
result depends on the stop being tight enough to catch the 2026 episode.

### 6.3 Arming buffer (span 40, stop 4%, 1 bp)

| Arm condition | 10y CAGR | 10y DD | 5y CAGR | 5y DD |
|---|---:|---:|---:|---:|
| always armed (0%) | 67.41% | 42.31% | 51.26% | 29.71% |
| QQQ < MA20 × 1.005 | 68.96% | 40.10% | 55.88% | 26.90% |
| **QQQ < MA20 × 1.01** | **70.11%** | **42.91%** | **61.78%** | **25.88%** |
| QQQ < MA20 × 1.02 | 62.84% | 44.61% | 53.62% | 28.78% |
| QQQ < MA20 × 1.03 | 58.83% | 49.62% | 49.82% | 29.24% |
| QQQ < MA50 | 61.36% | 40.57% | 51.56% | 32.51% |

The +0.5% and +1% arms both dominate the winner on both windows; wider arms (2–3%) and MA50
give up too much CAGR. The arm is doing real work: it keeps the fast filter out of the way in
strong uptrends. The +1% value is inherited from the winner's stop gate, so it is not a new
tuned parameter.

### 6.4 Signal instrument and timing convention

- Using **TQQQ's** 60-minute EMA instead of QQQ's gives 67.92% / 43.43% at 10y — still
  dominant, but weaker. QQQ is the better signal, as expected: TQQQ's 3× noise makes its own
  EMA cross more often.
- Applying the bar signal at the bar's last minute (the earliest honest fill) rather than one
  minute later gives 70.48% / 42.43% at 10y and 62.22% / 25.81% at 5y; letting the 15:30–15:59
  bar also set the overnight gives 70.64% / 42.43% and 62.75% / 25.81%. The headline is the
  conservative one-minute-late implementation; the differences are ~0.4 pp CAGR and <0.1 pp
  DD, so the result is not a timing artifact.

## 7. Why it works

- **The slow gate supplies the beta.** TQQQ is held on the majority of sessions including
  overnight, where essentially all of its drift is earned. The fast filter never changes the
  overnight position on a normal day; it only manages the session.
- **The fast filter is armed only when the short-term trend is already weak.** 871 of 2,718
  sessions (32%) are armed. In strong uptrends the filter is off and the strategy behaves like
  the winner; that is why 2022 and 2024 are close to the winner rather than worse.
- **Crosses, not levels.** The filter exits on a fresh 60-minute down-cross and re-enters on a
  fresh up-cross. A session that opens below the EMA is not sold immediately; that avoids the
  gap-down whipsaw that makes the level version give up 22 pp of CAGR.
- **The two overlays are complementary.** The fast filter handles slow intraday bleeds; the
  4% stop handles the gap crash. Removing the stop takes the 10-year drawdown from 42.91% to
  55.44%. Removing the fast filter (the winner) takes CAGR from 70.11% to 58.80%.
- **The mechanism is plausible, not just a backtest artifact.** In weak short-term regimes,
  intraday momentum is negative more often, and the 60-minute EMA is a cheap way to be out
  for the weak part of the session while keeping the overnight rebound. The 60-minute span
  (~6 sessions) is between the 20/50-day daily gates (too slow to re-enter) and the 4% stop
  (too coarse to catch a slow bleed). The daily evidence in Section 5 shows that the same
  idea applied at daily granularity destroys the overnight drift; applied intraday, it adds.

## 8. Limitations and honest caveats

1. **In-sample parameter selection.** The EMA span 40 was chosen after seeing the surface.
   Spans 35–45 dominate, but 30 and 50 do not, so the plateau is real but narrow. The arm
   (+1%) and stop (4%) are inherited from the winner, which reduces (but does not eliminate)
   the selection concern.
2. **Return concentration.** The extra CAGR is concentrated in 2019 (+41.7 pp vs the winner),
   2023 (+24.4 pp) and 2026 (+31.7 pp). 2022 is identical and 2024 is slightly worse. This is
   not a uniform improvement; it is a filter that pays in specific choppy/weak-intraday
   regimes. A future bull market with few weak intraday days would look more like 2024.
3. **The 10 bp 10-year row is marginal.** 51.23% vs 49.50% CAGR and 49.25% vs 50.06% DD. The
   5 bp row is comfortable; the 10 bp row is within noise. Do not treat 10 bp dominance as
   robust.
4. **Turnover and taxes.** 1,281 fills over 10 years (~65 round trips/yr), roughly twice the
   winner. At 1 bp per fill the cost is already 2× the winner's per-bp drag; in a taxable
   account the short-term gains would be a further drag not modeled here.
5. **Stop-level cliff.** At stop 4.5–5.0% the 5-year drawdown jumps to 37–39%, worse than the
   winner. The headline's 5-year result depends on the 4% stop firing in the 2026 summer
   slide. This is the least robust part of the result.
6. **60-minute bar convention.** Bars are aligned to 09:30; the last bar is 30 minutes and
   does not set the overnight position. A 30-minute shift of the bar boundaries was not
   tested (budget), and could change the 2026/2024 episodes.
7. **Single instrument, single sample.** TQQQ exists for the whole window, so there is no
   survivorship gap, but the result is specific to a 3× Nasdaq-100 ETF in a period with two
   large crashes (2020, 2022) and two sharp corrections (2018, 2024, 2026). The 3× daily-reset
   decay is inside the adjusted price data; the strategy does not model borrow, taxes or
   market impact.
8. **No shorting, no partial sizing.** The headline is binary TQQQ/BIL. A partial de-risk
   version might reduce the 10 bp drag, but it was not tested.
9. **BIL carry.** BIL earns its small daily return while out; no separate cash yield is added.
10. **The 5-year rolling set is small.** Nine quarterly 3-year windows; the 27-window 10-year
    set is the meaningful consistency test.

## 9. Reproduction

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
python research\agents2\dual-speed-regime\strategy.py
```

`strategy.py` rebuilds the 1-minute panel with `bt.panel`, applies the rules above, runs the
1/5/10 bp cases, the winner comparison, the rolling 3-year analysis, the neighbour surface and
the daily-gate negative controls, and writes `result.json`. The exploratory scripts in this
folder (`explore1.py` … `explore8.py`, `core.py`) document every variant quoted above. No core
repository file was modified.

## References

- Faber, M. T. (2007, updated 2013). *A Quantitative Approach to Tactical Asset Allocation.*
  SSRN 962461. [link](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=962461)
- Man Group / Man AHL (2023). *The Need for Speed in Trend-Following Strategies.*
  [pdf](https://www.man.com/documents/download/2739e-f3a21-bb8ce-f81f3/Man_Perspective_The_Need_for_Speed_in_Trend-Following_Strategies_English_04-01-2023.pdf?type=view)
- Graham Capital (2018). *The Speed of Trend-Following.*
  [pdf](https://www.grahamcapital.com/wp-content/uploads/2023/08/The-Speed-of-Trend_Graham-Research_March-2018-1-1.pdf)
- AlgoStrategyLab (2026-10-22). *I Backtested Dual Momentum for 29 Years.*
  [link](https://algostrategylab.github.io/dual-momentum/)
- BestFolio (2026-11-10). *The best trend filter depends on the year you start.*
  [link](https://bestfolio.app/blog/trend-filter-start-dates)
- QuantifiedStrategies (2025-06-02). *How Likely Is a False Signal in Moving Average
  Trading?* [link](https://www.quantifiedstrategies.com/how-likely-is-a-false-signal-in-moving-average-trading/)
- StockCharts SystemTrader (2016-11). *How to become a Smooth Operator with Moving
  Averages.* [link](https://articles.stockcharts.com/article/articles-arthurhill-2016-11-systemtrader---how-to-become-a-smooth-operator-with-moving-averages---backtesting-different-moving-average-pairs/)
- MarketHeist (2026-10-31). *The 10-month trend filter: how it works, what it costs,
  whipsaws.* [link](https://marketheist.io/portfolio/learn/trend-filter)
- Quantum Bias. *Moving Average Strategy Tested: The 10-Month Rule on the Nasdaq.*
  [link](https://quantum-bias.com/blog/10-month-moving-average-nasdaq-100)
- Kaminski, K. M., & Lo, A. W. (2014). *When do stop-loss rules stop losses?* Journal of
  Financial Markets 18, 234–254. [doi](https://doi.org/10.1016/j.finmar.2013.07.001)
- Lou, D., Polk, C., & Skouras, S. (2019). *A Tug of War: Overnight versus Intraday Expected
  Returns.* Journal of Financial Economics.
  [pdf](https://personal.lse.ac.uk/polk/research/TugOfWar.pdf)
- Round-1 winner: `research/agents/daily-regime-minute-entry/report.md`.
- FinLab. *TQQQ 200-day moving average strategy.*
  [link](https://finlab.finance/en/blog/leveraged-etf-timing-backtest)
- Exent. *TQQQ and the 200-Day Moving Average: An Exit Rule, Tested.*
  [link](https://www.exent.ai/resources/leveraged-etf-200-day-rule)
