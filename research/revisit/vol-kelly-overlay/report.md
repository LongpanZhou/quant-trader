> **Post-test note (2026-11-27):** this file is the pre-registration, not
> the result. The frozen development result is in `../SUMMARY.md`; the
> full 2016-2026 audit, the post-tune variants and the research-validity
> verdicts are in `../WHY_UNDERPERFORM.md`. The published website curve is
> the freeze named in `../SUMMARY.md`.

# Vol-spike reflation: a standalone 1-minute realized-volatility strategy

**Slug:** `vol-kelly-overlay`
**Status:** hypothesis + specification. Backtests are paused by the lead; this
file contains no results yet. `result.json` is intentionally not generated.
**Original:** `research/agents/vol-kelly-overlay`

---

## 1. What was actually new in the original

The original strategy had one genuinely new component: a **20-day realized
volatility ladder** built from within-day 1-minute returns, which shifted the
risky sleeve from TQQQ toward QQQ as TQQQ volatility rose, plus a small
**crash throttle**. Everything else — the direction, most of the return, and
most of the drawdown avoidance — came from the shared base:

> hold 100% TQQQ when QQQ closes above its 165-day SMA, otherwise 100% BIL.

That base is removed here. This rebuild keeps the 1-minute realized-volatility
measurement but changes the economic bet from *trend plus vol sizing* to
**volatility-spike mean reversion**. It is not a vol ladder with the trend gate
deleted, and it does not reuse the old `build_weights` or old base weights.

The old result (10y 47.53% / 45.32%, 5y 34.59% / 36.29%) is context only. The
new strategy is judged on its own development-period evidence.

---

## 2. Standalone hypothesis

**H1 (reflation).** After a sharp QQQ selloff accompanied by a fast 1-minute
realized-volatility spike, volatility mean-reverts. TQQQ's daily-reset
convexity then produces a positive 1-to-3-session rebound. A strategy that
waits in BIL and buys a volatility-scaled TQQQ position after the first
stabilization, exiting on volatility normalization, a short time stop, or a
price stop, earns a positive return stream that is not explained by the
165-day trend.

**H0 (null).** The rebound is indistinguishable from random high-volatility
beta: event returns have zero mean after 5/10 bp costs, are concentrated in a
single crash (most likely March-April 2020), or the strategy's returns are
mostly explained by the old 165-day base.

The economic mechanism is distinct from trend following:

- Realized volatility clusters and mean-reverts; a 5-day spike relative to a
  20-day baseline is a stress signal, not a trend signal.
- TQQQ is path-dependent: after a spike, the fund has de-levered and its
  convexity is high. A stabilization day can produce a large rebound that a
  slow trend gate misses because the price is still below its long moving
  average.
- The old base is usually in BIL at that moment, so the new strategy is long
  TQQQ exactly when the old base is flat. That is the source of both the
  independent return and the expected low correlation.

---

## 3. Universe and data constraints

**Universe:** QQQ, TQQQ, BIL (local 1-minute and daily data).

The brief allows SPY, sectors, bonds, gold and volatility products *where the
data supports it*. The local SPY archive (`data/cache/dukascopy/SPY`) contains
only 2026 daily `.bi5` files, not 2016-2023, and there is no local sector,
bond, gold or VIX history for the development period. The rebuild therefore
uses the three symbols with genuine 2016-2023 1-minute coverage. No new data is
downloaded while tests are paused.

**No shared base:** no 100-250-day moving average on QQQ, TQQQ, SPY or NDX is
used as a gate. The only price references are a 10-day rolling high for the
oversold condition, the prior close for the stabilization check, and the
entry-fill price for the stop. The 165-day SMA is computed **only** to measure
correlation with the old base, never to set a weight.

---

## 4. Signal specification

All signals use data through the close of day `i`; the resulting weight is
filled at the open of day `i+1`. No same-bar fills.

### 4.1 Realized volatility

For each session, compute TQQQ's within-day 1-minute realized variance:

```
RV_t = sum_{minutes in day t} r_{t,m}^2,   r = log(close_m / close_{m-1})
```

Overnight gaps are excluded. Annualize a trailing mean:

```
v5_t  = sqrt(252 * mean(RV_{t-4..t}))
v20_t = sqrt(252 * mean(RV_{t-19..t}))
```

`v20` is the volatility state; `v5/v20` is the short-term stress ratio.

### 4.2 Entry conditions

At the close of day `i`, all three must hold:

1. **Volatility spike:** `v5_i / v20_i >= 1.50`.
2. **Oversold:** `QQQ_i / max(QQQ_{i-9..i}) - 1 <= -5.0%`.
3. **Stabilization:** `QQQ_i > QQQ_{i-1}` (the first up-close after the
   selloff).

If all three hold, enter at the open of day `i+1`. Only one position at a time;
no pyramiding.

### 4.3 Position size

```
w_tqqq = clip(0.35 / v20_i, 0.25, 0.75)
w_bil   = 1 - w_tqqq
```

The 35% target is a TQQQ volatility budget: at `v20 = 70%` the weight is 50%,
at `v20 = 100%` it is 35%, and the floor/cap keep the position between 25% and
75%. The rest is BIL. Long only; no leverage beyond TQQQ's embedded 3x.

### 4.4 Exits

Evaluate at each close while in the position; exit at the next open if any
holds:

1. **Time stop:** the position has been held for 3 sessions including the
   entry session (`days >= 2` where `days = i - entry_i`).
2. **Volatility normalization:** `v5_i / v20_i < 1.00`.
3. **Price stop:** `QQQ_i <= entry_fill_qqq * 0.96` (a 4% QQQ stop from the
   actual next-open entry price, roughly a 12% TQQQ stop at 3x).

After an exit, the strategy is 100% BIL until the next valid entry. There is
no re-entry on the same signal day.

### 4.5 Default parameters and rationale

| Parameter | Default | Rationale | Neighbourhood to test |
|---|---:|---|---|
| Spike ratio `v5/v20` | 1.50 | A 50% short-term vol expansion is a clear stress spike | 1.40 / 1.50 / 1.60 |
| Drawdown window | 10 days | Fast enough to catch a selloff, slow enough not to be one bad day | 5 / 10 / 15 |
| Drawdown trigger | -5.0% | A meaningful 10-day pullback | -4% / -5% / -6% |
| Stabilization | close > prior close | First up-close; avoids buying a falling knife | 1-day up / 2-day up |
| TQQQ vol target | 35% | Caps event risk while keeping a meaningful position | 30% / 35% / 40% |
| Weight floor / cap | 0.25 / 0.75 | Avoids zero positions and overconcentration | 0.20-0.30 / 0.70-0.80 |
| Hold | 3 sessions | Rebound is short; limits exposure to a second leg down | 2 / 3 / 4 sessions |
| Price stop | -4% QQQ | Caps a failed rebound at roughly -12% TQQQ | -3% / -4% / -5% |
| Exit vol ratio | 1.00 | Exit when the spike has normalized | 0.90 / 1.00 / 1.10 |

The defaults are economically motivated round numbers, not fitted values. The
neighbourhood table is required before any parameter is called a plateau.

---

## 5. Holding period and risk

- **Holding period:** event-driven, 1-3 sessions. The strategy is in BIL most
  of the time; it is not a daily long-TQQQ strategy.
- **Risk:** one position at a time; maximum 75% TQQQ; the rest BIL. A 4% QQQ
  stop and a 3-session time stop limit a failed rebound. No overnight leverage
  beyond the TQQQ weight.
- **Turnover:** low by design (a few entries per year), so 5/10 bp costs should
  be small relative to the event return. The report will show all three costs.
- **Tail risk:** the strategy can lose on a failed rebound, especially in a
  sustained bear market (2022). The stop and time stop are the main defenses;
  the 2022-23 sub-period is a required falsification test.

---

## 6. Provenance: what inspired what

| Rule / claim | Source | Role | Evidence |
|---|---|---|---|
| Realized volatility is a useful state variable; vol clusters and mean-reverts | Moreira & Muir (2017), *Volatility-Managed Portfolios*, JF 72(4), https://doi.org/10.1111/jofi.12513 | inspired measurement | Inverse-variance scaling uses realized vol; the paper documents that vol changes are persistent and not matched by proportional expected-return changes. This rebuild uses vol as a stress state, not as a continuous target. |
| Volatility spikes concentrate left-tail risk; vol scaling can reduce tail events | Harvey et al. (2018), *The Impact of Volatility Targeting*, JPM 45(1), https://doi.org/10.3905/jpm.2018.45.1.014 | supports assumption | Vol targeting reduces the likelihood of extreme returns and max drawdowns for risk assets; this motivates treating a fast vol spike as a risk event rather than ignoring it. |
| TQQQ's daily-reset compounding is path-dependent and convex | Cheng & Madhavan (2009), *The Dynamics of Leveraged and Inverse Exchange-Traded Funds*, JOIM 7(4), https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1393995 | supports assumption | Derives the path-dependent compounding of daily-rebalanced leveraged funds; the convexity after a de-levered selloff is the mechanism behind the reflation trade. |
| TQQQ seeks 3x the daily return, not 3x over longer periods; high volatility hurts multi-day returns | ProShares, *TQQQ UltraPro QQQ Summary Prospectus*, https://www.proshares.com/globalassets/proshares/prospectuses/tqqq_summary_prospectus.pdf | supports assumption | The prospectus warns that higher index volatility and longer holding periods can make returns worse than the daily target; the 3-session hold is deliberately short. |
| Buy after a vol spike + oversold + first stabilization; exit on vol normalization | **Own hypothesis / no external source** | new idea | No paper in the reviewed set specifies this exact event. It is the testable hypothesis of this rebuild. |
| 10-day drawdown, 3-session hold, 4% QQQ stop, 35% TQQQ vol target | **Own design / no external source** | new idea | Round risk-control choices; the ±1-step neighbourhood and placebo tests are the evidence, not an external paper. |
| 165-day SMA baseline for correlation only | `research/README.md` | benchmark | The old base is computed only to measure daily-return correlation; it never enters the strategy weights. |
| Development period 2016-01-04..2023-12-29, 1/5/10 bp, 1-minute marks | `research/revisit/BRIEF.md` | evaluation rule | Non-negotiable evaluation protocol; holdout 2024-2026 is reserved for the lead. |

**Not used / rejected for this rebuild:** the old 20-day TQQQ→QQQ ladder with a
165-day gate, the old 5% crash throttle, Kelly/fractional-Kelly sizing, and the
old base weights. The original report's 10y/5y numbers are not reused.

---

## 7. Falsifiers (pre-registered)

The hypothesis is rejected or retired if any of the following holds on the
development period:

1. **Too few events:** fewer than 15 valid entries over 2016-2023. The test is
   underpowered; report the count and do not claim an edge.
2. **No net expectancy:** mean event return <= 0 at 5 bp or 10 bp.
3. **Not statistically distinguishable from zero:** bootstrap p-value > 0.10
   for the mean event return (10,000 resamples).
4. **Single-event dependence:** removing the best event, or removing all 2020
   events, turns the total P&L negative or the CAGR below BIL.
5. **High correlation:** daily-return correlation with the 165-day baseline
   >= 0.60.
6. **Placebo match:** random entry days with the same holding-period
   distribution and the same weights match or beat the strategy's mean event
   return (placebo p > 0.10).
7. **Sub-period failure:** the 2022-23 sub-period is negative or the strategy
   underperforms BIL there after costs.
8. **Stabilization adds nothing:** entering on the spike day (without the
   first-up-close condition) is as good or better; the edge is just beta, not
   timing.
9. **The edge is only an overlay:** the event strategy only works when combined
   with the old 165-day base; standalone it has no positive expectancy. In that
   case mark `retired_overlay_only`.

If the pure event strategy has too few events but the effect is visible, a
secondary variant may hold a vol-targeted QQQ core when no event is active.
That variant is not the headline and must be reported separately; it will have
a higher correlation with the old base.

---

## 8. Planned evaluation (when the lead authorizes tests)

- **Development only:** 2016-01-04 → 2023-12-29. Do not load or inspect
  2024-2026.
- **Costs:** 1 bp headline, 5 bp and 10 bp sensitivity.
- **Marks:** 1-minute equity marks via `research/minute_marks.py:to_minutes`,
  with the 2% band and next-open fills.
- **Benchmarks:** TQQQ, QQQ, BIL, and the original 165-day baseline result.
- **Headline metrics:** CAGR, max drawdown, Sharpe, fills, turnover, exposure,
  event count, mean event return, hit rate.
- **Correlation:** daily-return correlation with the 165-day baseline and with
  TQQQ/QQQ.
- **Sub-periods:** 2016-19, 2020-21, 2022-23.
- **Overfitting controls:** ±1-step neighbourhood table, placebo entries,
  bootstrap p-value, top-event contribution, and the two variants (pure event;
  QQQ core + event).
- **Result format:** `result.json` per the brief, with `windows.dev`,
  `windows.holdout` left for the lead, and `windows.10y`/`5y` left for the lead
  because they overlap the holdout.

---

## 9. Expected correlation and status

**Expected correlation with the old 165-day base:** 0.0-0.3. The strategy is in
BIL during calm uptrends when the old base is long TQQQ, and it is long TQQQ
after spikes when the old base is usually in BIL. The hard requirement is
< 0.60; if the measured correlation is higher, the design fails the diversity
test and will be revised or rejected.

**Status:** pending test. No result is claimed. The code is written but has not
been run. The next step is the lead's authorization to run the development
backtest, then an independent audit of look-ahead, spec-vs-code, reproduction,
harness, correlation and overfitting.
