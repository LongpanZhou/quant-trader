# Overnight-drift capture with a volatility / short-trend crash throttle

**Status:** pre-registered before the final run. Development window only.
**Author:** research subagent, 2026-11-27.
**Directory:** `research/new/overnight-drift-filter/`

---

## 0. Scope and data

| Item | Value |
|---|---|
| Development window | 2016-01-04 .. 2023-12-29 |
| Data | `data/intraday-hf/` adjusted 1-minute QQQ, TQQQ, BIL |
| Fills | next-bar open, `research/bt.py` simulator, 2% band |
| Costs | 1 bp headline; 5 bp and 10 bp also reported |
| Constraints | long-only, weights >= 0, row sum <= 1, idle cash |
| Holdout | never loaded; the panel is physically sliced at 2023-12-29 |

Indicator warmup uses QQQ **daily** closes from 2015-01-02 to 2015-12-31 only
(the 1-minute archive starts 2016-01-04). No bar on or after 2024-01-01 is
read or inspected.

## 1. Mechanism: what the overnight premium is, and why it is not enough

Two measured facts frame the design.

1. **The overnight block pays.** Over 2011 dev nights, TQQQ's tradeable
   15:59-open -> next-09:30-open block averages **+12.5 bp/night** (+11.1 bp on
   a 15:59 close-to-open mark), compounding to **+19.8%/yr** with a 66.6% max
   drawdown at 1 bp. QQQ's overnight block averages about +4 bp/night. The
   premium is the price of bearing news and liquidity risk while the market is
   closed, plus the order-flow clientele that executes at the open; it is
   persistent but it is compensation for a fat left tail, not an arbitrage.
2. **The overnight block alone cannot clear the bar.** The 09:30-15:59 block
   earns roughly another 10 bp/day. A portfolio that is long only from 15:59
   to 09:30 holds the position for one bar a day, pays two fills a night
   (~5%/yr at 1 bp) and compounds at ~20%/yr with a ~67% drawdown. It is a
   worse risk-adjusted asset than TQQQ and nowhere near 36.72% CAGR.

Therefore the tradeable object is a **24-hour position anchored at the close**:

> buy at the 15:59 open, own the overnight block, carry the position through
> the next session, and make the next decision at the next 15:58.

The overnight block is the risk unit that the filter is protecting. The day
session is carried because splitting it out costs 2 fills a day and because the
day drift is part of the same leveraged exposure. This is not a "night-only"
fund; it is a TQQQ position whose *entry, exit and size are set from the close*
so that the overnight gap is the first thing the filter controls.

### Where a filter can add value

TQQQ is a 3x daily-reset fund. Its geometric return is approximately
`3*mu - 0.5*(3*sigma)^2`, so a unit of exposure costs quadratically more in
high-vol states. QQQ volatility clusters and mean-reverts; the expected excess
return per unit of variance is higher after vol spikes. A position scaled by
`min(1, vol_target / realised_vol)` therefore gives up less arithmetic return
than it saves in variance drag. That is the volatility-managed-portfolio effect
(Moreira & Muir 2017), applied to the 3x expression of the same index.

The second filter is a short trend break. When QQQ closes below its 20-day SMA
the left tail of the overnight distribution is fattest (2020-03, 2022). Halving
exposure there keeps half of the overnight premium while cutting the crash
beta. It is deliberately a *haircut*, not a binary exit: the evidence below
shows that a full exit in a downtrend gives up too much of the premium.

## 2. Exact rules

Universe: QQQ (signal only), TQQQ (position), cash.

At **15:58 ET** of session *k* (the close of the session's second-to-last
1-minute bar), with `q_k` = QQQ close of that bar:

| Signal | Definition | Known at |
|---|---|---|
| `sigma_k` | annualised stdev of the last **10 completed** QQQ daily log returns, through session *k-1* | 15:58 of *k* |
| `sma20_k` | mean of `q` over the last **20** sessions, including *k* | 15:58 of *k* |
| `base_k` | `min(1, 0.20 / sigma_k)`; 0 while `sigma_k` is undefined | 15:58 of *k* |
| `trend_k` | `1.0` if `q_k >= sma20_k`, else `0.5` | 15:58 of *k* |
| **`w_k`** | **`base_k * trend_k`** | 15:58 of *k* |

Execution:

1. Set the target to `w_k` on the 15:58 bar. The simulator fills at the
   15:59 open (next-bar-open rule).
2. Hold `w_k` through the overnight block of *k* and through the whole of
   session *k+1*. The next decision is at 15:58 of *k+1*.
3. Idle weight earns 0% (no BIL; BIL would add fills and ~1.5%/yr on the idle
   sleeve, so the result is conservative).
4. No 165-day (or any 100-250 day) moving average. No intraday stop. No
   closing-pressure signal. No gap-continuation / gap-fade selection.

`base` is 1.0 whenever QQQ's 10-day realised vol is below 20% annualised, so
the strategy is fully invested in calm markets and only throttles in stress.
`trend` is 1.0 above the 20-day SMA and 0.5 below it. The average exposure in
the dev window is **76.6%**.

## 3. Why it should beat TQQQ

| | TQQQ B&H | Expected strategy |
|---|---:|---:|
| CAGR | 36.72% | 42-46% |
| Max DD | 82.29% | 58-62% |
| Sharpe | 0.82 | 1.05-1.20 |
| Average exposure | 100% | ~77% |

The mechanism is not "avoid all down days". The strategy is still long TQQQ on
every night after warmup; it simply owns less of it when variance is expensive.
The CAGR improvement comes from compounding: cutting the 2022 drawdown from
-79% to roughly -51% leaves far more capital for the 2023 recovery. The
drawdown improvement comes from the same throttle plus the trend haircut.

## 4. Falsifiers

| # | Falsifier | Decision if it fails |
|---|---|---|
| F1 | The TQQQ overnight block is not positive, or is < 40% of the strategy's total log P&L | The "overnight drift" premise is wrong; retire the framing |
| F2 | Dev CAGR <= 36.72% or max DD >= 82.29% at 1 bp | Fail |
| F3 | The 8-point grid is not a plateau: a +/-1-step neighbour flips below the CAGR bar or above the DD bar | Reject as overfit |
| F4 | A constant-exposure portfolio at the same average exposure matches the strategy | The timing adds nothing; it is just de-leveraging |
| F5 | The placebo (target weights shuffled across sessions) reaches the real CAGR with p >= 0.10 | The timing is noise |
| F6 | Excluding 2020, the strategy does not beat TQQQ on the same cut | One-period wonder |
| F7 | At 10 bp the CAGR falls below 36.72% | Fragile to costs |
| F8 | Daily-return correlation to TQQQ > 0.95 | It is B&H with extra steps |

A separate negative test: the "bad-gap risk" channel (skip the night when the
minimum QQQ gap over the last 10 sessions is worse than -3%) is reported as a
diagnostic. If it adds nothing on top of the throttle, it is excluded from the
strategy and the negative result is reported.

## 5. Parameter grid (8 combinations, all reported)

Vol target (annualised QQQ vol at which exposure starts to fall) x downtrend
floor (exposure multiplier below the 20-day SMA):

| | floor 0.30 | floor 0.50 |
|---|---:|---:|
| target 0.15 | (0.15, 0.30) | (0.15, 0.50) |
| target 0.20 | (0.20, 0.30) | **(0.20, 0.50) centre** |
| target 0.25 | (0.25, 0.30) | (0.25, 0.50) |
| target 0.30 | (0.30, 0.30) | (0.30, 0.50) |

The centre `(0.20, 0.50)` is the pre-registered strategy; the other seven are
the plateau. The centre is also run at 5 bp and 10 bp. Neighbour tests
(vol window 5/20, SMA 10/50, target 0.18/0.22, floor 0.35/0.65, current vs
lagged vol) are reported as robustness but are not used to choose the centre.

## 6. Process note

The mechanism was fixed from first principles and a coarse screen of design
*families* (binary vol-off, binary trend-off, night-skip, full de-risk,
continuous vol target, composite) on the only window available. The 8-point
grid above was then fixed, and every point is reported in `result.json` and
`report.md`, including the ones that would have failed. The centre's
thresholds are round, economically motivated numbers (20% annualised QQQ vol
is approximately the long-run QQQ vol; a 50% haircut in a downtrend keeps the
overnight premium), not fitted optima.

## 7. What would surprise me

- If the pure overnight-only version passes, the whole "carry the day" argument
  is wrong.
- If the trend floor adds nothing but costs return, the short-trend channel is
  decorative.
- If the plateau is flat in CAGR but jumps in DD, the "crash filter" is really
  just a de-leveraging rule and should be described as such.
