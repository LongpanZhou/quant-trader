# Time-of-day and seasonality on TQQQ — agent 9/10

**Verdict: PASS on the stated benchmark, with a caveat that matters.** The recommended
variant (V2) clears TQQQ buy-and-hold on both windows — higher CAGR *and* lower max
drawdown — but it only does so at ≤2 bp of cost. At 5 bp it fails the CAGR test on both
windows. The edge is a genuine, well-documented time-of-day effect (almost all of a
3x Nasdaq ETF's return accrues outside the cash session), not a curve-fit, but the
strategy trades twice a day, so cost sensitivity is the binding constraint.

| | 10y (2017-01-03 → 2026-10-23) | 5y (2021-10-25 → 2026-10-23) |
|---|---|---|
| **V2 recommended, 1 bp** | **49.23% CAGR / 42.66% max DD / 1.35 Sharpe** | **28.89% CAGR / 34.54% max DD / 0.94 Sharpe** |
| TQQQ buy-and-hold (README) | 39.28% / 81.68% / 0.83 | 13.47% / 81.68% / 0.53 |
| Daily baseline (README) | 45.31% / 58.71% / 1.00 | 34.61% / 36.86% / 0.88 |
| V2 at 5 bp | 26.40% / 43.26% | 10.85% / 36.73% |

Pass/fail vs TQQQ: **10y PASS** (CAGR +9.95 pp, DD −39.0 pp), **5y PASS**
(CAGR +15.42 pp, DD −47.1 pp). At 5 bp: **fail** on CAGR both windows, DD still much
better than TQQQ.

---

## 1. Idea and where it comes from

The strategy only ever holds TQQQ in one window of the day: from the last minute of the
session (15:59 ET) to the end of the first half hour of the next session (10:01 ET).
Everything else is cash. A daily QQQ 165-day SMA regime switches the whole thing off in
downtrends.

That is the tradable form of three well-documented regularities:

1. **The overnight/non-trading-hours drift.** Cliff, Cooper & Gulen (2008) show that
   essentially all of the U.S. equity premium since 1993 is earned overnight, with
   intraday returns roughly flat. Lou, Polk & Skouras (2019, *JFE*) model the
   overnight and intraday blocks as separate clienteles and show the spread is priced.
2. **The first half hour is special.** Gao, Han, Li & Zhou (2018, *JFE*, "Market
   intraday momentum") document that the first half-hour return is large, positive and
   predictive of the last half hour; the opening auction/half-hour carries
   information-driven order flow (also NY Fed Staff Report 917 on the open).
3. **The last half hour is not.** In this sample the TQQQ 15:30→16:00 block has a
   *negative* CAGR. The strategy therefore holds the open and avoids the close.

I deliberately did **not** put the seasonality overlays in the recommended strategy —
see §7, where they are tested and rejected as unstable.

Links (checked 2026-11-25):

- Cliff, Cooper & Gulen, *Return Differences between Trading and Non-Trading Hours:
  Like Night and Day* — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1004081
- Lou, Polk & Skouras, *A Tug of War: Overnight versus Intraday Expected Returns* —
  https://ifr.hkust.edu.hk/uploads/upload/files/20250212/445bce5ab83ffca69c4fe4b56c8055e1.pdf
- Gao, Han, Li & Zhou, *Market Intraday Momentum* —
  https://doi.org/10.1016/j.jfineco.2018.05.009
- NY Fed Staff Report 917, *The Opening Hours of European Markets and U.S. Equity
  Returns* — https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr917.pdf
- Overnight-vs-intraday ETF decomposition (SPY/QQQ, 1999-2026) —
  https://tideline.jbpscapital.com/learn/overnight-vs-intraday
- McConnell & Xu, *Equity Returns at the Turn of the Month*, FAJ 64(2), 2008 —
  https://business.purdue.edu/faculty/mcconnell/publications/Equity-Returns-at-the-Turn-of-the-Month.pdf
- Lakonishok & Smidt (1988), *Are Seasonal Anomalies Real?*, RFS 1(4)

Data: local adjusted 1-minute QQQ/TQQQ/BIL (`data/intraday-hf/`), 2016-01-04 →
2026-10-23, 1,057,023 regular-session bars, 2,718 trading days. Harness: `research/bt.py`.
All signals use data through the close of bar *i* and fill at the **open of bar i+1**.
Long-only, no shorting, no leverage beyond TQQQ itself.

---

## 2. What the minute data actually says

The block decomposition is the whole thesis. Each row is a block held alone (gross, no
costs, no regime filter), annualised from daily compounding, 2016-01-04 → 2026-10-23:

| block | full | 2017-2021 | 2022-2026 | note |
|---|---:|---:|---:|---|
| TQQQ close→open (overnight) | **+31.41%** | +56.7% | +9.47% | 78.4% of TQQQ's total log return |
| TQQQ open→close (session) | +6.25% | +10.8% | +1.77% | |
| TQQQ 09:30→10:00 (first 30m) | +8.09% | +5.34% | −0.26% | 26.3% in 2019-21 only |
| TQQQ 15:30→16:00 (last 30m) | **−5.74%** | | | −1.48 bp/day |
| QQQ close→open | +12.43% | | | 65.3% of QQQ's log return |
| QQQ open→close | +6.43% | | | |

Correlation between the overnight and intraday blocks is 0.01 (QQQ) / 0.01 (TQQQ), so
they are effectively separate assets. The overnight block alone has 28.4% CAGR over the
full panel with a 67% drawdown, versus 81.7% for buy-and-hold.

Per calendar year the TQQQ overnight block is positive in **10 of 11 years**
(only 2022 is negative, −58.0%), while the session block is negative in 3 of 11
(2018 −46.3%, 2022 −50.2%, 2024 −18.0%). This is the source of the strategy's
drawdown protection, and it is also why the strategy gives up return in strong
up-years: it is only in the market for ~17 hours a day, and it is flat during the
session rallies (2023 +147% session, 2026-04 +52.6% in one month).

---

## 3. Exact rules

Recommended strategy **V2**:

```
state = OFF, prev = NaN
for each 1-minute bar i (regular session only):
    # regime, evaluated daily, strictly causal
    sma165 = mean(QQQ daily close, last 165 days, through day d-1)
    if QQQ close(d-1) > sma165 * 1.02:  state = ON
    elif QQQ close(d-1) < sma165 * 0.98: state = OFF     # 2% hysteresis band
    (state persists inside the band)

    # entries/exits only at two decision points
    at the second-to-last bar of day d (signal bar 15:58):
        target = 100% TQQQ if state == ON else 0
    at the bar before 10:01 of day d+1 (signal bar 10:00):
        target = 0                       # back to cash
```

Fills are at the open of the *next* bar, i.e. 15:59:00 for the entry and 10:01:00 for
the exit. So the position is `TQQQ[15:59 → 09:30 next day]` plus the first 31 minutes,
i.e. 15:59:00 → 10:01:00 the next morning. Everything else is cash (0% — BIL was
tested and is *worse*, because holding BIL forces a second round-trip per day that costs
more than the yield it earns).

Parameters: SMA 165 days (the README's reference value, not fitted here), hysteresis
band 2%, morning exit 10:01 ET. Nothing uses future information: the regime at day *d*
uses only closes through *d−1*, and the band state is a causal recursion.

Regime behaviour: ON 78.0% of days, **11 switches in 10.7 years**, i.e. the strategy is
out of the market in exactly five episodes:

| flat period | what it avoided |
|---|---|
| 2018-10-25 → 2019-03-12 | Q4-2018 crash |
| 2020-03-10 → 2020-04-14 | COVID crash |
| 2022-01-21 → 2023-01-26 | the 2022 bear market |
| 2025-03-11 → 2025-05-12 | the 2025 tariff crash |
| 2026-03-23 → 2026-04-13 | spring-2026 drawdown |

Without the 2% band the same SMA generates **41** switches and the strategy churns in
the 2018 Q4 whipsaw; that alone costs ~8 pp of CAGR (§6).

---

## 4. Results

### 4.1 Headline (1 bp slippage)

| metric | V2 10y | V2 5y | TQQQ 10y | TQQQ 5y |
|---|---:|---:|---:|---:|
| CAGR | **49.23%** | **28.89%** | 39.28% | 13.47% |
| max drawdown | **42.66%** | **34.54%** | 81.68% | 81.68% |
| Sharpe (daily-sampled) | **1.35** | **0.94** | 0.83 | 0.53 |
| Sharpe (minute bars, as harness) | 1.31 | 0.92 | 0.84 | 0.54 |
| Sortino | 1.85 | 1.31 | — | — |
| annualised vol | 35.70% | 33.89% | — | — |
| fills | 4,069 | 1,883 | 1 | 1 |
| turnover (traded notional / start equity) | 71,725× | 4,298× | — | — |
| ending equity on $100k | $5,060,444 | $355,276 | $2.60M | $188,000 |
| max-DD window | 2020-02-19 → 2020-03-09 | 2025-01-22 → 2025-05-23 | | |

Measured on this 1-minute panel, TQQQ buy-and-hold is 39.38% / 82.29% (10y) and
14.29% / 82.29% (5y), i.e. within 0.1-0.8 pp of the README's daily numbers; pass/fail
below uses the README's 39.28% / 81.68% and 13.47% / 81.68% as instructed.

Time in market: long TQQQ ~17 h per day on 78% of days ≈ **54% of calendar time**.
The harness "exposure" statistic (6.8%) is bar-weighted and misleading here — the
overnight block is 32 of 390 bars but 17 of 24 hours.

### 4.2 Yearly returns vs TQQQ (1 bp)

| year | V2 | V3 (V2+TOM) | V4 (24h ref) | TQQQ | V2 vs TQQQ |
|---|---:|---:|---:|---:|---|
| 2017 | +52.5% | +53.5% | +114.5% | +114.5% | lose |
| 2018 | +54.8% | +61.8% | +9.3% | −20.8% | **win** |
| 2019 | +60.5% | +49.6% | +61.0% | +148.2% | lose |
| 2020 | +161.9% | +233.4% | +127.3% | +104.1% | **win** |
| 2021 | +60.4% | +34.7% | +81.1% | +81.1% | lose |
| 2022 | −8.2% | −16.2% | −28.2% | −79.4% | **win** |
| 2023 | +59.7% | +109.7% | +129.4% | +192.0% | lose |
| 2024 | +56.8% | +46.3% | +62.4% | +62.4% | lose |
| 2025 | +32.2% | +50.6% | +18.0% | +32.1% | **win** |
| 2026 YTD | −4.4% | +5.9% | +6.8% | +22.6% | lose |

5 wins / 5 losses, and every win is a year when TQQQ lost or barely made money. The
strategy never had a losing year worse than −8.2% while TQQQ had −79.4%. 2026 is the
ugliest recent stretch: the regime re-entered on 2026-04-14 and the overnight-only
exposure then missed a +52.6% April and +33.1% May in TQQQ (the rebound came intraday).

### 4.3 Cost sensitivity — the real constraint

| slippage | 10y CAGR | 10y DD | 5y CAGR | 5y DD | passes? |
|---|---:|---:|---:|---:|---|
| 0 bp | 55.56% | 42.52% | 33.85% | 34.00% | yes |
| **1 bp** | **49.23%** | **42.66%** | **28.89%** | **34.54%** | **yes** |
| 2 bp | 43.16% | 42.81% | 24.13% | 35.08% | yes |
| 3 bp | 37.34% | 42.96% | 19.53% | 35.61% | **no** |
| 5 bp | 26.40% | 43.26% | 10.85% | 36.73% | **no** |

Each round trip costs 2 bp at 1 bp/side; with ~1.5 round trips per trading day the drag
is ≈6.3 pp/yr at 1 bp and ≈29 pp/yr at 5 bp. **The strategy survives 1 bp and 2 bp and
fails at 3 bp and above.** Anyone implementing this needs sub-1 bp execution on TQQQ
(tight spreads, no meaningful market impact at retail size) or it is not worth doing.
The daily baseline, by contrast, is essentially cost-free (11 fills).

---

## 5. Robustness

### 5.1 Neighbouring parameters (all 1 bp, all long-only)

**SMA length** (band 2%, exit 10:01):

| SMA | 10y CAGR | 10y DD | 5y CAGR | 5y DD | pass |
|---|---:|---:|---:|---:|---|
| 100 | 41.51% | 42.66% | 28.68% | 34.10% | yes |
| 125 | 42.77% | 42.66% | 18.55% | 36.24% | yes |
| 150 | 44.52% | 42.66% | 20.77% | 33.48% | yes |
| **165** | **49.23%** | 42.66% | 28.89% | 34.54% | yes |
| 200 | 43.31% | 50.97% | 25.31% | 34.54% | yes |
| 250 | 41.68% | 53.71% | 22.68% | 40.85% | yes |

**Hysteresis band** (SMA 165, exit 10:01):

| band | 10y CAGR | 10y DD | 5y CAGR | 5y DD | pass |
|---|---:|---:|---:|---:|---|
| 0% | 41.51% | 50.97% | 23.28% | 34.12% | yes |
| 1% | 44.38% | 50.97% | 27.24% | 30.90% | yes |
| **2%** | **49.23%** | 42.66% | 28.89% | 34.54% | yes |
| 3% | 48.32% | 42.66% | 27.39% | 34.80% | yes |
| 5% | 44.94% | 53.71% | 26.98% | 31.67% | yes |

**Morning exit** (SMA 165, band 2%):

| exit | 10y CAGR | 10y DD | 5y CAGR | 5y DD | pass |
|---|---:|---:|---:|---:|---|
| 09:31 (pure overnight) | 40.19% | 43.49% | 24.05% | 31.77% | yes |
| **10:01** | **49.23%** | 42.66% | 28.89% | 34.54% | yes |
| 10:31 | 48.81% | 43.52% | 24.65% | 33.75% | yes |
| 11:01 | 39.57% | 40.34% | 15.85% | 40.34% | yes |
| 11:31 | 47.28% | 43.60% | 25.35% | 36.74% | yes |
| 12:01 | 50.22% | 41.95% | 30.06% | 41.95% | yes |

**Regime lag** (how stale the signal is; lag 1 is the recommended, strictly causal one):

| lag | 10y CAGR | 10y DD | 5y CAGR | 5y DD | pass |
|---|---:|---:|---:|---:|---|
| 0 (uses today's 15:58 price) | 46.62% | 44.84% | 29.12% | 34.11% | yes |
| **1 (uses yesterday's close)** | **49.23%** | 42.66% | 28.89% | 34.54% | yes |
| 2 | 45.95% | 42.66% | 27.65% | 32.76% | yes |
| 3 | 41.95% | 53.71% | 25.33% | 35.40% | yes |

Every one of the 21 neighbouring settings passes. That is the strongest evidence that
the result is not a single lucky parameter draw. It is also true that the *spread* is
wide (41-50% on 10y), so the exact headline number should be read as ~45±5%, not 49.2%.

### 5.2 Walk-forward (parameters chosen in-sample, evaluated out-of-sample)

Rank every (exit, band) combination on 2017-2021, then look at 2022-2026:

| variant | 2017-2021 CAGR / DD | 2022-2026 CAGR / DD |
|---|---:|---:|
| 10:01, band 2% (best IS) | 76.06% / 42.7% | **25.21% / 34.5%** |
| 10:01, band 3% | 76.02% / 42.7% | 23.69% / 34.8% |
| 10:01, band 5% | 68.78% / 53.7% | 23.27% / 30.8% |
| 10:01, band 1% | 67.15% / 51.0% | 23.54% / 30.9% |
| 10:01, band 0% | 65.85% / 51.0% | 19.55% / 30.1% |
| 09:31, band 2% | 60.01% / 43.5% | 21.86% / 31.8% |
| 09:31, band 0% (worst IS) | 50.72% / 51.7% | 18.26% / 29.0% |

Rank correlation between in-sample and out-of-sample CAGR: **0.83**. The in-sample
winner is also the out-of-sample winner, and every configuration still beats TQQQ's
10.9% CAGR over 2022-2026. This is the cleanest evidence of stability I have.

Sub-periods for V2: 2017-2021 **58.38% CAGR / 42.66% DD**, 2022-2026 **25.21% / 34.5%**
(TQQQ: 10.88% / 81.1% over the same 2022-2026 stretch).

### 5.3 What the other variants do

| variant | description | 10y CAGR | 10y DD | 5y CAGR | 5y DD | 1 bp | 5 bp |
|---|---|---:|---:|---:|---:|---|---|
| V1 | overnight 15:59→**09:31**, band 2% | 40.19% | 43.49% | 24.05% | 31.77% | pass | fail |
| V1b | overnight 15:59→09:31, **band 0** | 34.00% | 51.70% | 20.53% | 32.11% | **fail** | fail |
| **V2** | overnight 15:59→**10:01**, band 2% | **49.23%** | **42.66%** | **28.89%** | **34.54%** | **pass** | fail |
| V2b | overnight 15:59→10:01, band 0 | 41.51% | 50.97% | 23.28% | 34.12% | pass | fail |
| V3 | V2 + turn-of-month 24h overlay | 55.29% | 34.25% | 35.63% | 31.60% | pass | fail |
| V4 | 24h TQQQ, same regime (reference) | 51.11% | 48.55% | 32.37% | 42.17% | pass | pass |

Notes:

- V1 (pure overnight, no first 30 minutes) *just* clears the 10y bar (40.19% vs 39.28%)
  and only because of the 2% band; with band 0 it fails at 34.00%. So the "first 30
  minutes" add-on is doing real work in the headline, and §2 shows that block is the
  least stable of the three (5.3% / 26.3% / −0.3% by era). This is a genuine weakness —
  see §8.
- V4 (the daily baseline, executed at the 15:59 print instead of the next open, 11
  fills) is a *very* strong and almost cost-free competitor: 51.11% / 48.55% at 10y.
  V2 beats it on drawdown (42.66 vs 48.55) and Sharpe (1.35 vs 1.08) but not on CAGR,
  and V4 is immune to slippage. If you only care about CAGR and can stomach a 48% DD,
  the daily strategy is the better trade.
- V3 is the best backtest but I do not recommend it (§7).

---

## 6. Where the P&L comes from

- Gross V2 at 0 bp is 55.56% (10y) / 33.85% (5y). At 1 bp it is 49.23% / 28.89%.
  **Cost is 6.3 pp of CAGR for ~1.5 round trips a day.**
- Turnover is 71,725× start equity over 10y, 4,298× over the 5y window.
- 4,069 fills in 10y ≈ 1.5/day: an entry into TQQQ every regime-on evening, an exit
  every regime-on morning, plus occasional rebalances when the position drifts >2% of
  book inside the block.
- BIL instead of cash while out of the market makes things *worse*
  (46.71% / 36.18% vs 50.23% / 42.66% on 10y) because the BIL leg doubles the daily
  round trips.

---

## 7. Seasonality: tested, and rejected as unstable

The mandate asked for day-of-week, month and turn-of-month effects. They are present in
the sample but **none of them survives a stability screen**, so the recommended strategy
does not use them.

**Turn of month (last 1 + first 3 trading days, McConnell-Xu).** The effect is
concentrated in the *session* block, not the overnight:

| | mean bp/day, session | mean bp/day, overnight | mean bp/day, close-to-close |
|---|---:|---:|---:|
| TOM days (n=519) | **+27.5** | +2.3 | +29.5 |
| other days (n=2,198) | +3.6 | +15.9 | +19.6 |

TOM day-sessions beat non-TOM day-sessions in **7 of 11 calendar years**, and the
per-year t-stats on the close-to-close difference are mostly < 2 (max 1.98 in 2017).
Adding a "hold the whole session on TOM days" overlay to V2 gives
**55.29% / 34.25% (10y) and 35.63% / 31.60% (5y)** at 1 bp — better than V2 on every
metric, and it *reduces* fills from 4,069 to 3,293 because TOM days avoid a round trip.

But the width sweep shows why I do not trust it:

| TOM window (days) | 0 | 4 | 5 | 6 | 7 | 8 | 9 | 11 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 10y CAGR | 49.2% | 47.4% | 50.6% | **55.3%** | 52.4% | 56.2% | 56.9% | 58.8% |

The curve rises monotonically toward *wider* windows, i.e. toward "hold TQQQ more
often". A genuine calendar anomaly should peak at a narrow window and decay; this does
not. The overlay's gain cannot be separated from simply taking more market beta in a
bull decade, so it is reported but **not recommended**.

**Day of week.** Monday is the strongest close-to-close day in both eras (33.4 bp/day in
2017-2021, 56.7 bp in 2022-2026), and Monday's gain is almost entirely the *session*
(+21.9 then +56.6 bp/day). But the overnight component rotates: Tuesday/Wednesday nights
averaged +44.1/+32.1 bp in 2017-2021 and +1.5/+27.4 bp in 2022-2026, and Thursday went
from +14.0 bp session to −24.6 bp. Not stable, not used.

**Month of year.** September is the only month negative in both eras
(−33.1% and −21.8% total TQQQ return). Screening September out of the strategy *reduced*
CAGR (49.23% → 46.39%) because the overnight block in September is fine; the damage is
intraday. Not used.

---

## 8. Overfitting risk — read this before believing the number

Honest list of what is fitted and what could be luck:

1. **The headline is a plateau, not a spike, but the plateau is 41-50% wide.** All 21
   neighbouring (SMA × band × exit × lag) settings pass, and the walk-forward rank
   correlation is 0.83, which is genuinely reassuring. But the *level* moves ±5 pp with
   innocuous choices, so treat 49% as "mid-40s", not as a precise estimate.
2. **The first-30-minutes add-on is era-dependent.** Its standalone CAGR is +5.3%
   (2016-18), +26.3% (2019-21), −0.3% (2022-26). Dropping it (V1, exit 09:31) still
   passes at 1 bp but with a 0.9 pp margin on the 10y CAGR. If you want the most
   defensible version, use V1: 40.19% / 43.49% (10y), 24.05% / 31.77% (5y).
   If you want the best expected return, use V2.
3. **The 2% hysteresis band is worth ~8 pp of CAGR** and turns 41 regime switches into
   11. That is a small number of discrete timing decisions (five flat episodes), so a
   meaningful part of the improvement is which side of the 2018-Q4 / 2020-03 / 2022
   whipsaws the band happened to land on. The band's *sign* is consistent across 1-5%,
   which is the reassuring part; its magnitude is not.
4. **The strategy is flat during session rallies.** 2023 (+192% TQQQ, +60% strategy),
   2017 (+114% vs +52%), 2026 (+22.6% vs −4.4%). Any decade where the drift migrates
   intraday kills this strategy. The overnight/session split is a documented but
   *time-varying* phenomenon (Lou-Polk-Skouras show it is clientele-driven and can
   invert).
5. **Data caveat.** The 1-minute closes sit up to ~1% (TQQQ) away from the official
   16:00 close on some days (mean absolute difference in QQQ daily returns vs Yahoo
   adjclose: 2.6 bp, max 96 bp). The strategy's P&L uses only *opens* of 1-minute bars,
   so this does not create a bias, but it does mean the measured block returns carry
   microstructure noise. There is no dividend or split artefact: both the overnight
   and intraday blocks reconcile to close-to-close within 0.2 pp.
6. **No shorting, no leverage, no borrow.** Weights are 0 or 1 in TQQQ; the only
   "leverage" is TQQQ's own 3x daily reset. Cash earns 0%.

---

## 9. Verification performed

- **Independent simulator.** A hand-written next-open, no-band simulator reproduces
  `bt.simulate` to 1.0000× on the equity multiple for both V1-style and V3-style weight
  arrays.
- **Block-return reconstruction.** Rebuilding equity from only two atoms
  (`P(10:01 open, d+1)/P(15:59 open, d)` and the TOM session add-on) matches the harness
  to within **0.17 pp of CAGR**.
- **Baseline reproduction.** The README's daily baseline re-run on daily bars gives
  44.46% / 58.71% (10y) and **34.61% / 36.86% (5y, exact)** — my harness usage matches
  the reference within ~1 pp.
- **No look-ahead.** The regime at day *d* uses closes through *d−1* only; the band state
  is a causal recursion; entries fill at the 15:59:00 open, exits at 10:01:00; the
  turn-of-month calendar is published in advance.
- **Turnover/fills** are reported from the harness, not estimated.

---

## 10. Bottom line

| question | answer |
|---|---|
| Beats TQQQ on CAGR and DD, both windows, 1 bp? | **Yes** — 49.23%/42.66% and 28.89%/34.54% |
| Beats the daily baseline? | 10y CAGR yes (49.23 vs 45.31), both DDs yes, **5y CAGR no** (28.89 vs 34.61) |
| Survives 5 bp? | **No** — 26.40% and 10.85%, fails the CAGR bar |
| Survives 2 bp? | Yes (43.16% / 24.13%) |
| Robust to parameter choice? | Yes in sign (21/21 neighbours pass), ±5 pp in level |
| Robust out of sample? | Yes — walk-forward rank correlation 0.83, best-IS is best-OOS |
| Main risk | cost (needs ≤2 bp) and the possibility that the overnight drift migrates intraday |

The cleanest statement of the edge: **holding a 3x Nasdaq ETF only from 15:59 to 10:01,
gated by a 165-day SMA, delivered the same or better CAGR as buy-and-hold with roughly
half the maximum drawdown, because 78% of TQQQ's log return accrues outside the cash
session and the last 30 minutes of the session are outright negative.** That is a
time-of-day effect, not a seasonality effect; the seasonality overlays I tested add
return in this sample but do not survive a stability screen.

---

## 11. Files

| file | purpose |
|---|---|
| `strategy.py` | panel loader (cached), regime, weight builders, evaluation; `python strategy.py` runs the main grid |
| `explore.py` | block anatomy: overnight vs intraday, first/last 30 min, weekday, TOM, month |
| `seasonality.py`, `blocks.py` | stability of TOM / day-of-week / month, per-era block returns |
| `final.py` | 15-variant grid, yearly, walk-forward, writes `result.json` |
| `tables.py` | cost-sensitivity table, yearly table, final markdown numbers |
| `sensitivity.py`, `sweep2.py`, `sweep3.py`, `detail.py` | parameter sweeps and per-variant detail |
| `check.py` | independent simulator, block reconstruction, data audit |
| `baseline.py` | reproduces the README daily baseline |
| `result.json` | machine-readable metrics for every variant |

Reproduce:

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
python research\agents\time-of-day\strategy.py     # main grid
python research\agents\time-of-day\tables.py       # headline tables
python research\agents\time-of-day\check.py        # verification
```
