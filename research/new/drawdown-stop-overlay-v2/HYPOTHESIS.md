# Failed-breakdown spring, repaired — `drawdown-stop-overlay-v2`

**Status:** pre-registered development test. Window **2016-01-04 .. 2023-12-29**
only. The 2024-2026 holdout has not been loaded or inspected.
**Original:** `research/revisit/drawdown-stop-overlay` (rebuild of
`research/agents/drawdown-stop-overlay`).
**Harness:** `research/bt.py`, 1-minute marks, next-open fills, 2% band,
long-only (TQQQ + BIL), 1 bp headline with 5/10 bp sensitivity.

---

## 1. What the old rebuild did, and why it lost money

The old rebuild buys TQQQ at the next open after QQQ undercuts its prior
20-session low intraday, closes back above that low, and closes in the upper
half of the day's range. It holds up to five sessions and exits on a new
10-day QQQ high, an 8% TQQQ close stop, or time.

The dev result was **41 signal days / 38 entries / 153 fills, -9.25% CAGR,
63.1% max DD, -0.27 Sharpe at 1 bp** (100% TQQQ per event, 7.36% of minutes in
TQQQ, 3.9-session average hold).

The diagnosis in this file is computed *before* the confirmatory grid in
section 4; it is derived only from the development window.

### 1.1 The signal has a one-day pop and no five-day edge

Forward TQQQ return from the next open after a signal, 2016-2023:

| horizon | signal mean | unconditional mean | signal hit rate | bootstrap p (signal >= random) |
|---|---:|---:|---:|---:|
| 1 day | +0.47% | +0.10% | 61.0% | 0.23 |
| 3 days | +0.39% | +0.50% | 51.2% | 0.54 |
| 5 days | +0.93% | +0.91% | 58.5% | 0.51 |
| 10 days | +0.71% | +1.93% | 63.4% | 0.74 |

The 1-day number is the only positive gap versus the unconditional base, and
it is not statistically strong. At 5 and 10 days the signal is
indistinguishable from, or worse than, simply being long TQQQ. So the five-day
holding period has no return driver; it only adds crash exposure.

### 1.2 The tight stop and the next-open exit destroy the little drift

Of 38 trades, 15 exited on the 8% TQQQ stop, 4 on the 10-day-high recovery and
19 on time. The average trade was **-1.75%**; 25 of 38 lost. The worst trades:

| signal | entry | exit | trade return | why |
|---|---|---|---:|---|
| 2020-02-28 | 2020-03-02 | 2020-03-09 | **-22.4%** | 8% stop could not fill; weekend/COVID gap |
| 2022-05-02 | 2022-05-03 | 2022-05-09 | -14.7% | stop through a fast decline |
| 2018-10-08 | 2018-10-09 | 2018-10-11 | -13.6% | stop through a fast decline |
| 2022-04-18 | 2022-04-19 | 2022-04-25 | -12.7% | stop through a fast decline |
| 2018-02-06 | 2018-02-07 | 2018-02-09 | -11.7% | stop through a fast decline |

The 8% TQQQ stop is only about 2.7% on QQQ. At TQQQ's 3x daily volatility it is
hit by ordinary path noise; when it is hit in a gap the fill is far below the
stop. Separately, the "exit at the fifth session close" was implemented as
"decide at the 15:59 close and fill at the next open", which adds an overnight
gap. The 2020-03-09 exit alone accounts for roughly -20% of the trade.

### 1.3 No trend or volatility filter

The signal fires in every regime. The 2022 cluster (12 of 41 signals) produced
**-39.8%** compounded; 2020 produced -24.4%. A failed breakdown in a bear or
crisis tape is usually a continuation, not a spring.

---

## 2. Repair hypothesis

The spring mechanism is kept exactly: QQQ undercuts a prior 20-session low,
closes back above it, and closes in the upper half of the day's range. What
changes is the context, the horizon and the exit:

1. **Trend filter.** Take the spring only when QQQ's close is above its
   200-session SMA. A failed breakdown in an uptrend is a stop run; the same
   pattern below the 200-day line is a downtrend continuation.
2. **Volatility filter.** Take the spring only when QQQ's 20-session realised
   volatility is below 30% annualised. This removes the 2020/2022 crisis
   clusters where TQQQ gaps through any stop.
3. **Horizon.** Hold **one session**, because the only positive horizon is the
   one-day pop. The five-day hold has no edge.
4. **Exit.** Exit at the **15:59 open of the exit session** (decision at 15:58)
   so the strategy is flat overnight, instead of deciding at 15:59 and filling
   at the next open. The stop, when used, is intraday and fills at the next
   bar's open.
5. **Stop.** Test no stop, an 8% intraday TQQQ stop and a 12% close stop. The
   old 8% close stop is too tight and is not expected to survive.

The primary is **`h1_trend_vol_nostop_close`**: one-session hold, QQQ > 200-day
SMA, 20-day vol < 30%, no stop, flat at the close. The stop neighbour is
`h1_trend_vol_stop8_close`.

This is not a new signal and it does not use the old 165-day base. The 165-day
baseline is computed only as a benchmark/correlation reference.

---

## 3. What would falsify the repair

1. **Still no edge.** The repaired primary's dev Sharpe is below 0.5, or its
   CAGR is below a static TQQQ/BIL mix with the same average TQQQ exposure.
2. **Drawdown not controlled.** Max DD stays above 20% at 1 bp.
3. **Filter dependence.** Removing the trend filter or the vol filter flips the
   sign or doubles the drawdown, i.e. the result is one filter cell.
4. **Costs.** 10 bp costs turn the CAGR negative or below BIL.
5. **Concentration.** One year or one trade explains the result; the
   sub-periods do not have a consistent sign.
6. **Event study.** The one-day forward edge is not present in the filtered
   sample.

If (1) or (2) fails, the honest status is **retired as a standalone** even if
the filters improve the old -9.25%. The original overlay can remain an overlay
on the 165-day base; the spring is not an independent return source.

---

## 4. Pre-registered grid (8 variants, one at a time)

All variants use the same 20-day lookback, 0.50 range confirmation, TQQQ
execution, 100% notional per event and one position at a time.

| # | name | hold | trend | vol cap | stop | exit |
|---|---|---:|---|---:|---|
| 1 | `orig` | 5 | none | none | 8% close | next open |
| 2 | `h5_trend_vol_stop12_close` | 5 | 200d | 30% | 12% close | close |
| 3 | `h5_trend_vol_stop8_close` | 5 | 200d | 30% | 8% close | close |
| 4 | **`h1_trend_vol_nostop_close`** | **1** | **200d** | **30%** | **none** | **close** |
| 5 | `h1_trend_vol_stop8_close` | 1 | 200d | 30% | 8% intraday | close |
| 6 | `h3_trend_vol_stop8_close` | 3 | 200d | 30% | 8% intraday | close |
| 7 | `h1_vol_stop8_close` | 1 | none | 30% | 8% intraday | close |
| 8 | `h1_trend_stop8_close` | 1 | 200d | none | 8% intraday | close |

`variants_tried = 8`. The primary is #4. #5 is the stop neighbour; #7 and #8
are the filter ablations; #1 is the old rebuild for direct comparison.

The plateau is read across hold (1/3/5), filters (on/off) and stop (none/8%).
No holdout, no 10y/5y windows.

---

## 5. Rules and accounting

- **Signal:** at the 15:59 close, `low_t < min(low_{t-20..t-1})` and
  `close_t > min(low_{t-20..t-1})` and
  `(close_t-low_t)/(high_t-low_t) >= 0.50`.
- **Entry:** next session's 09:30 open, 100% TQQQ.
- **Exit:** recovery at the prior 10-day QQQ high, stop (variant), or the time
  exit; all fills are next-open fills on the 1-minute panel. The "close" exit
  sets the target at the 15:58 bar, so the fill is the 15:59 open and the
  position is flat overnight.
- **Cash:** BIL when flat.
- **Costs:** 1 bp headline; 5 and 10 bp reported for every variant.
- **Marks:** 1-minute equity.

---

## 6. Expected result (stated before the confirmatory run)

The repair should cut the drawdown from 63% to roughly 20-25% and lift the
CAGR from -9% to about +2-3%. It is **not** expected to beat a static
TQQQ/BIL mix with the same average exposure on Sharpe; the point of the test is
to establish whether the spring has a standalone edge at all. If the primary is
below the static mix, the strategy is retired as a standalone.
