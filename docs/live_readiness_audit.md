# Live-readiness audit

Scope: the paper-trading paths (`broker = "sim"` and Alpaca paper), the daily
Nasdaq strategy, and the gap between the backtest and what the live loop
actually does. Research was done before each change; sources are at the end.

Nothing here is real-money trading: the program has no live broker endpoint.
"Live" means a running paper session.

---

## 1. Summary

| # | Finding | Severity | Status |
|---|---|---|---|
| F1 | 5% rebalance band left the book **2.0% of equity off target on average, 12.4% worst** | P1 | **Fixed**: band 2% → 0.69% / 5.5%, same return and trade count |
| F2 | Per-leg band + cash cap can leave a buy unfunded ("low bucket") | P1 | **Mitigated**: warning logged; 1 material event at 2% band |
| F3 | A failed order was not retried until the next day | P1 | **Fixed**: up to 3 retries per bar on following polls |
| F4 | Closed-market polling could sleep through the open by 10 minutes | P1 | **Fixed**: 60-second polls while closed |
| F5 | Backtest fills at the official open; live fills seconds-to-a-minute later | P2 | **Measured & documented** |
| F6 | Alpaca paper does not credit dividends; BIL's ~4%/yr is missing | P1 | **Warned**: cannot be fixed client-side |
| F7 | Alpaca free feed is IEX only (~2-4% of volume) | P2 | **Warned** |
| F8 | Alpaca bars are split-adjusted, not total-return | P2 | **Warned** |
| F9 | Yahoo is an unofficial feed with no SLA | P2 | **Checked**: preflight reports quote age/delay |
| F10 | Whole-share rounding leaves a cash bucket | P3 | **Measured**: 0.16% at $100k |
| F11 | Partial fills / cancel-after-timeout on Alpaca | P2 | **Covered by retry + per-tick reconciliation** |
| F12 | No client-order-ID idempotency | P2 | **Documented** (see §6) |
| F13 | Restart re-evaluates the latest completed bar | P3 | **Documented** |
| F14 | No live post-trade weight report | P2 | **Backtest diagnostics added**; live cash-cap warning added |
| F15 | Bad-tick sanity check | P3 | **Documented** |

53 unit tests pass after the changes.

---

## 2. How the audit was done

1. Read the live path end to end: `engine.rs` (tick, decide, rebalance),
   `sim.rs`, `alpaca.rs`, `backend.rs`, `yahoo.rs`, `preflight.rs`.
2. Instrumented the backtester to measure **weight tracking error**, **signed
   gross exposure error**, **worst single-leg error** and **cash-limited buys**
   on every tested bar.
3. Swept the rebalance band (1/2/3/5/10%) and compared return, drawdown, trade
   count and tracking error.
4. Measured the open-to-+10-minute price move on real 5-minute data.
5. Checked live Yahoo quote metadata (delay and age) and the corporate-action
   feed.
6. Researched rebalancing rules, order-state handling, opening-auction
   liquidity, Yahoo freshness and Alpaca paper specifics.

---

## 3. Weight balancing (F1/F2/F10)

### 3.1 The measurement

Added to the backtest:

```
Weight tracking      : avg 2.04% of equity off target, worst 12.37% | gross -0.28% | worst single 6.26%
Cash-limited buys    : 3
```

`avg` is the sum over all three assets of `|actual weight - target weight|` on
every bar; `gross` is the signed error in total exposure (negative = the book
is under-invested); `worst single` is the largest one-asset error.

At the original 5% band the book was **2.0% of equity away from its target on
average**, one leg was **6.3%** off at worst, and the total was **12.4%** off.
That is not a rounding effect: for a 40%-vol-target strategy, a 6% swing in the
TQQQ leg is a material change in effective leverage.

### 3.2 What the research says

- Threshold rebalancing with drift bands captures most of the risk control of
  frequent rebalancing at a fraction of the turnover; 5-point bands are the
  common default for a 60/40 portfolio ([Quant Decoded](https://quantdecoded.com/en/rebalancing-frequency-optimal-tradeoff-costs-vs-drift)).
- A flat 5-point band is wrong for small sleeves: a 5% position can double
  before it triggers. The standard fix is the **5/25 rule** — rebalance at the
  tighter of 5 percentage points or **25% of the sleeve's target**
  ([Guardfolio](https://www.guardfolio.ai/portfolio-rebalancing-guide),
  [Kitces/Daryanani](https://www.kitces.com/blog/best-opportunistic-rebalancing-frequency-time-horizons-vs-tolerance-band-thresholds)).
- Bands are checked more often than they trade; the drift when a band triggers
  can overshoot the band on a gap day ([RiskHub](https://riskhub.org/blogs/calendar-based-vs-threshold-based-rebalancing)).

### 3.3 The sweep

Same strategy, same data, only `rebalance_band` changed:

| Band | CAGR | Excess | Max DD | Closed trades | Avg drift | Worst drift | Worst single | Cash-limited buys |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1% | 26.44% | +16.94 | 29.24% | 55 | 0.46% | 4.10% | 2.23% | 10 |
| **2%** | **26.40%** | **+16.91** | **29.35%** | **54** | **0.69%** | **5.48%** | **2.77%** | **1** |
| 3% | 26.22% | +16.73 | 29.35% | 55 | 1.09% | 7.77% | 3.93% | 1 |
| 5% | 26.32% | +16.83 | 28.67% | 54 | 2.04% | 12.38% | 6.26% | 3 |
| 10% | 26.30% | +16.81 | 28.58% | 54 | 4.17% | 20.72% | 10.45% | 3 |

The key result: **tightening the band costs nothing in return or trade count**
(the number of closed trades is 54-55 at every setting) but cuts tracking error
by 3-4×. The strategy's trades are dominated by regime entries/exits; the band
only controls resizing.

**Decision: 2%** is the sweet spot. 1% tracks slightly better but creates 10
cash-limited buys (the funding problem in F2); 2% has one.

### 3.4 The "low bucket" / cash-capped buy

The rebalance is per-leg: sells are only made when a position is more than its
band over target, while buys are capped by available cash. If the funding leg
is inside its band but the buy leg is outside, the buy is starved. That is the
"low bucket" risk.

It is now measured (`cash_limited_buys`) and **logged live**:

```
WARN TQQQ: buy limited by cash, wanted $4820, can spend $1310
```

At the 2% band it happened once in five years (materially), so it is a
monitoring item rather than a reason to add a funding pass. If the band is
tightened to 1%, it becomes 10 events and a funding pass would be the next fix.

### 3.5 Whole-share cash bucket

The live replay ends with **$156.92 cash on $100,000 (0.16%)** after buying
1,090 BIL. At $1,000 the same rounding would be ~16% of the account, so the
$100k default matters. There is no fractional-share support; document a minimum
account size of roughly $10k for this preset.

---

## 4. Order handling (F3/F11/F12)

### 4.1 Research

Live order handling needs three separate concepts: the **intent** (the
strategy decision), the **broker order**, and the **attempt** (a network
call). A retry must not turn one intent into two orders; ambiguous submissions
must be resolved by querying the broker, and state must be reconciled after
restarts ([Agentic Trading Index](https://fx-tech.ai/blog/designing-idempotency-and-retries-for-live-order-placement),
[pythonparatrading](https://pythonparatrading.com/en/python-trading-course/level-4/fault-tolerance-idempotency-and-reconciliation/)).

### 4.2 What was wrong

`rebalance` was only called when a **new bar** completed. If an order failed
(API error, rejected order, partial fill timing out), the engine logged a
warning and did nothing until the next day. A failed sell could therefore
block the corresponding buy for a full session.

### 4.3 Fix

`rebalance` now returns `(acted, failed)` and the engine retries up to **3
times per bar**, on the following polls, before giving up:

```
WARN 1 order(s) failed; retrying the rebalance on the next poll (1/3)
```

Safety against duplicates: before every retry, `tick()` re-fetches positions
from the broker. If the first order actually filled but its response was lost,
the position already matches the target and the retry's shortfall check skips
it. This is a reconciliation-by-position approach, not a formal idempotency
key; see §6.

### 4.4 Alpaca partial fills

`Alpaca::submit` polls the order for ~7 seconds, then cancels and returns an
error if it has not filled. A partial fill that is later cancelled is not
recorded by the local position map, but the map is rebuilt from the broker
every tick, so the next retry sees the true position. Liquid ETFs fill in
milliseconds; this is an edge case, not the normal path.

---

## 5. Execution timing (F4/F5)

### 5.1 The sleep bug

`run()` slept `poll_seconds` (600s) unconditionally. If the loop checked the
market at 9:29 and saw it closed, it woke at 9:39 — **ten minutes after the
open**. The strategy decides once a day, so that is the whole execution
window.

### 5.2 The price cost

Real 5-minute data, 35 sessions:

| Symbol | Open→+10 min absolute move | median | p90 | max |
|---|---:|---:|---:|---:|
| QQQ | 0.29% | 0.26% | 0.90% | 1.04% |
| TQQQ | **0.87%** | 0.63% | **2.38%** | **3.69%** |

The backtest assumes the official open and 1bp of slippage. A ten-minute delay
is therefore **2-3 orders of magnitude larger** than the assumed cost for
TQQQ.

### 5.3 Fix

While the market is closed, the loop now wakes at least every **60 seconds**,
so the first in-market poll is within a minute of the open. Unit-tested:

```
test engine::tests::closed_market_polls_at_least_every_minute ... ok
```

### 5.4 Residual: auction vs continuous

The research is unambiguous that the **opening auction is the least liquid
window** of the day and has higher price impact than the closing auction
([Goyal, Jegadeesh & Wu, JFQA 2026](https://www.cambridge.org/core/services/aop-cambridge-core/content/view/0F72910A79C5B42CF6E85F55164CE846/S0022109026102592a.pdf/price-impact-in-closing-auctions-opening-auctions-and-continuous-markets-a-benchmark-for-cost-of-trading-on-anomalies.pdf)).
A $100k order in QQQ/TQQQ is far too small to move the auction, but the
official open print is not necessarily attainable. The backtest's next-open
fill is a timing convention, not a price guarantee. This is documented, not
"fixed": changing to a closing-auction execution would add a full day of delay
and change the strategy.

---

## 6. Data and broker specifics

### 6.1 Yahoo Finance (sim broker)

- US Nasdaq/NYSE quotes are listed as **real-time** in Yahoo's own coverage
  table; the chart endpoint's `meta.exchangeDataDelayedBy` was empty for QQQ
  and `regularMarketTime` matched the 16:00 close ([Yahoo coverage](https://help.yahoo.com/kb/finance-for-web/exchanges-data-providers-yahoo-finance-sln2310.html)).
- It is still an **unofficial endpoint with no SLA**; retries exist (3 attempts
  with backoff), but a long outage means a missed daily signal.
- `preflight` now prints quote age and exchange delay, and fails if the market
  is open with a quote older than 15 minutes or a reported delay.

### 6.2 Alpaca paper (optional broker)

- **IEX vs SIP**: the free feed is one exchange, ~2-4% of consolidated volume.
  A 166-session test found QQQ's 15-minute close differed from SIP by a median
  2.4bp, with occasional much larger gaps; price-based daily signals are fine,
  but IEX is not the tape for execution benchmarks
  ([Alpaca FAQ](https://docs.alpaca.markets/us/docs/market-data-faq),
  [IEX vs SIP test](https://www.reddit.com/r/algotrading/comments/1w86sxp/worth_paying_alpaca_for_realtime_data_i_tested)).
- **Dividends**: Alpaca's paper environment explicitly does **not** account
  for dividends ([paper trading docs](https://alpaca.markets/docs/trading/paper-trading/)).
  A BIL-heavy strategy therefore loses ~4%/yr of safe-asset return in paper.
  `preflight` warns; the sim broker credits dividends correctly.
- **Bars**: `adjustment=split`, not `all`. The signal is scale-invariant, but
  the live series is not total-return; this is another reason the sim broker is
  the more faithful test for this strategy.

### 6.3 Corporate actions

Already fixed in the previous iteration: splits and dividends are applied to
the sim ledger from Yahoo events, verified against TQQQ's 2025 2:1 split. The
Alpaca path relies on Alpaca's own position accounting and does not need the
local adjustment.

---

## 7. Other findings

### F12. Client-order-ID idempotency (not implemented)

Alpaca accepts a `client_order_id` for de-duplication. The engine does not
send one. The retry in §4.3 is safe in practice because positions are
reconciled before each retry, but a formal intent ID would be the correct
design for real money. Recommended: derive the ID from
`strategy + bar_ts + symbol + side`, persist the intent, and reuse it on every
attempt.

### F13. Restart behaviour

`last_bar` is not persisted. A restart re-evaluates the latest completed bar;
the 2% band limits the extra turnover, but a restart mid-session can produce a
small resize. Persisting `last_bar` and the pending-intent record would remove
this.

### F14. Live weight report

The backtest now reports tracking error; the live log reports cash-limited
buys but not the post-trade weights. Recommended: log the target and actual
weights once per rebalance at INFO level (they are already computed).

### F15. Bad-tick guard

A single bad Yahoo print (10× price) could trigger a trade in the sim. The
corporate-action path handles splits, and `fresh()` handles staleness, but
there is no magnitude check. Recommended: reject a price more than ±50% from
the previous completed close for these ETFs (TQQQ's worst day is ~-35%).

### F16. Settlement and account type

The sim assumes instant settlement and no margin interest unless
`margin_rate_pct` is set. Alpaca paper is margin-enabled. A real **cash**
account would face T+1 settlement and free-riding rules; this preset sells and
buys on the same day, which is fine in a margin/paper account but not
necessarily in a cash account.

### F17. Taxes

Not modelled: wash sales, short-term gains, and the tax cost of daily regime
switches. Paper results are pre-tax.

---

## 8. What changed in the strategy numbers

The 2% band is now the preset. Live-parity results:

| | 5 years | 10 years | 20 years (synthetic 3x) |
|---|---:|---:|---:|
| Strategy | 26.4%/yr | 37.4%/yr | 26.5%/yr |
| QQQ | 9.5% | 18.6% | 15.0% |
| Excess | **+16.9pp** | **+18.8pp** | **+11.5pp** |
| Max DD | 29.4% | 38.3% | 44.9% |
| Avg weight drift | **0.69%** | **0.61%** | **0.66%** |

The 2x QLD 20-year version is +7.3pp with 40.1% DD. The conclusion is unchanged:
3x is required to clear the +10pp bar.

---

## 9. Pre-live checklist (revised)

1. `cargo build --release && cargo test` — 53 tests.
2. `preflight --config configs\nasdaq_leveraged_trend.toml` — require PASS;
   read the quote-age line and any Alpaca warnings.
3. `replay` — confirm the order matches the target and the residual cash is
   small.
4. Start `run` **before 9:25 ET**; the loop now wakes every minute while
   closed, so the first decision lands at the open.
5. Watch for `WARN ... buy limited by cash` and `WARN ... retrying the
   rebalance`. More than a handful of either means the account is too small or
   the broker is rejecting orders.
6. `status` and `trades.csv` are the audit trail; the daily decision is in the
   log as a BUY/SELL with a reason.

## 10. Sources

- Rebalancing bands / 5-25 rule: Quant Decoded (threshold study), Guardfolio
  (5/25), Kitces & Daryanani (20% relative), RiskHub (band overshoot).
- Order state, retries, idempotency, reconciliation: Agentic Trading Index,
  pythonparatrading (fault tolerance), NautilusTrader execution policies.
- Opening vs closing auction: Goyal, Jegadeesh & Wu, *JFQA* 2026.
- Yahoo data coverage/delays: Yahoo Finance help, ReefAPI measurement.
- Alpaca paper: market-data FAQ (IEX vs SIP), paper-trading docs (no
  dividends), 166-session IEX/SIP comparison.

*Paper-trading research, not financial advice.*
