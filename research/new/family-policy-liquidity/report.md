# Policy liquidity / short-rate regime — development report

**Family:** `policy-liquidity`  
**Directory:** `research/new/family-policy-liquidity/`  
**Window:** 2016-01-04 .. 2023-12-29 (development only). No 2024-2026 data
enters any signal, result or robustness calculation; the BIL feature frame is
truncated at the development end before any feature is computed.  
**Headline marks:** 1-minute panel, next-session 09:30 open, 2% band, 1 bp
headline cost; 5 bp and 10 bp reported.  
**Pre-registration:** `HYPOTHESIS.md`.

## Verdict (short)

**Qualified pass on the TQQQ development bar, with material fragility.** At
1 bp the strategy earns **57.97% CAGR, 76.68% max drawdown and 1.118 Sharpe**
versus the bar of **36.72% / 82.29% / 0.82**. It has **361 fills**, 90 round
trips and 85.4% average TQQQ exposure. All 108 cells of the parameter grid
clear the bar, the circular-shift placebo is significant at 5% (p = 0.017),
and the correlation with the nine family winners is 0.53-0.84.

The pass is not clean. The 2022-2023 subperiod is **-2.99% CAGR** with a
**74.37% drawdown**; the max drawdown is only 5.6 pp better than TQQQ; 2020 and
2022 together contribute more than 100% of the net log excess; the 2020 P&L is
a single-event outcome; and the off-run hit rate is only 20% (the edge is a few
large crisis exits, not a consistent timing rule). The strategy is a
short-rate **liquidity-stress overlay**, not an all-weather policy-liquidity
regime. It should go to a one-shot holdout only as a crisis-alpha candidate,
not be promoted on development alone.

## 1. What was tested

BIL is a 1-3 month T-bill ETF. Its total-return path is the short rate net of
its expense ratio. The strategy infers the policy front end from BIL and trades
a long-only TQQQ/BIL book on a five-state machine:

| State | Condition | Target |
|---|---|---|
| `LOW` | `y60 < 1.00%` | 100% TQQQ |
| `HIGH` | `y60 >= 4.00%` | 100% TQQQ |
| `TIGHTENING` | `1.00% <= y60 < 4.00%` and `dy60 >= +0.40%` | 100% BIL |
| `STRESS` | `1.00% <= y60 < 4.00%` and `front >= +0.15%` | 100% BIL |
| `STABLE` | `1.00% <= y60 < 4.00%` otherwise | 100% TQQQ |

where, for BIL adjusted close `A_t`:

```
yN_t    = 100 * (ln A_t - ln A_{t-N}) / N * 252      N = 20, 60
dy60_t  = y60_t - y60_{t-60}
front_t = y20_t - y60_t
```

The decision is taken at each session's 15:59 close and filled at the next
session's 09:30 open. The weight is constant from the open to the close of
each session. The first session uses the last completed 2015 state. No 2024+
row enters any feature; the BIL frame is truncated at the panel's last session
before the features are computed.

The 20/60-session windows, the 1% low-rate gate, the 4% high-rate band, the
15 bp front threshold and the 40 bp 60-day slope are fixed round numbers. A
coarse exploration on the same development window preceded the centre; the
centre is a round-number cell, not the grid maximum, and the full 108-cell grid
and all ablations are reported in `robustness.json` so the reader can judge the
selection. The full family policy (no trend, vol target, drawdown event,
calendar, opening range, ML or relative strength) is in `HYPOTHESIS.md`.

## 2. BIL yield inference and validation

The daily BIL adjusted close is the total-return series (distributions
included). The 2017-11-30 1:2 reverse split is already reflected in Yahoo's
adjusted data; a check around the split shows no spurious jump. The inferred
year-end `y60` path over the development window is:

| Year-end | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `y60` (%) | -0.00 | 0.91 | 2.19 | 1.47 | -0.03 | -0.09 | 3.48 | 5.36 |

This matches the known Fed/Bill cycle: zero-bound through 2016, gradual
normalisation in 2017-2018, cuts in 2019, zero through 2020-2021, the 2022
hiking cycle and the 2023 high-rate plateau. It is a qualitative validation;
no external Treasury series is used.

**Quantisation.** BIL trades on a 1-cent grid around $91.5. One cent is 1.09 bp
of price; annualised over 20 sessions that is about 13.8 bp of yield estimate,
and over 60 sessions about 4.6 bp. Below 1% the error dominates the signal,
which is why `LOW` ignores the front-end noise. The cost of that gate is
discussed in section 10: it also blindfolds the strategy to the first ~100 bp
of a hiking cycle from zero, exactly the 2022 H1 case.

**Real-rate proxy.** Not attempted. The local panel has no CPI, inflation
expectations or TIPS series, and subtracting an invented inflation number
would violate the "do not invent external data" rule. This study is
nominal-only.

## 3. Headline development metrics

1-minute panel, next-session open, 2% band. `Exposure` in the table is TQQQ
exposure; the harness exposure is 100% because idle capital is BIL, not cash.

| Cost | CAGR | Max DD | Sharpe | Sortino | Vol | TQQQ exp. | Fills | Turnover | Ending equity |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 bp | **57.97%** | **76.68%** | **1.118** | 1.589 | 54.18% | 85.44% | **361** | 1413.9x | $3,850,201 |
| 5 bp | 55.14% | 76.68% | 1.085 | 1.541 | 54.18% | 85.44% | 361 | 1302.9x | $3,332,509 |
| 10 bp | 51.67% | 76.68% | 1.043 | 1.481 | 54.17% | 85.44% | 361 | 1179.5x | $2,782,155 |
| TQQQ B&H | 36.15% | 82.29% | 0.801 | 1.122 | 66.55% | 100% | 1 | 1.0x | $1,175,165 |
| **TQQQ dev bar** | **36.72%** | **82.29%** | **0.82** | — | — | — | — | — | — |

The strategy clears the stated bar on all three headline metrics. The 0 bp
gross result is 58.69% CAGR / 76.68% DD / 1.127 Sharpe; the 1 bp cost is
0.72 pp of CAGR, the 10 bp cost is 7.0 pp.

The daily-bar cross-check (same decision clock, one open/close per session) is
57.53% CAGR / 75.23% DD / 1.102 Sharpe / 361 fills. The 1-minute headline has
a slightly higher CAGR and a 1.45 pp deeper intraday drawdown. Both pass.

## 4. Activity and trade anatomy

| Item | Value |
|---|---|
| Full-window fills | **361** |
| TQQQ buys / sells | 91 / 90 |
| State entries / exits | 90 / 90 |
| Risk-on sessions | 1,719 (85.44%) |
| Risk-off sessions | 293 (14.56%) |
| Average holding period (fill-to-fill) | **24.2 calendar days** (mean); 3.5 days (median) |
| State run length | 18.9 sessions (mean); 2.0 sessions (median) |
| Longest hold | ~872 days (April 2020 - August 2022) |
| Turnover | 1,413.9x initial at 1 bp |

The activity floor is met by a wide margin. The average holding period is
dragged up by the long 2020-2022 risk-on run; the median hold is only 3.5 days
because most risk-off episodes are 1-3 sessions. The 2% band does not generate
extra rebalances with binary TQQQ/BIL weights; the 361 fills are 90 exits and
90 entries, each with a sell and a buy leg, plus the initial buy.

### Off-run hit rate

A risk-off run is "good" if TQQQ falls while the strategy is in BIL.

| Off-run length | n | Negative TQQQ | Hit rate | Mean TQQQ | Sum TQQQ |
|---|---:|---:|---:|---:|---:|
| >= 1 session | 90 | 18 | **20.0%** | -0.52% | -47.1% |
| >= 2 sessions | 36 | 18 | 50.0% | -1.31% | -47.1% |
| >= 3 sessions | 15 | 7 | 46.7% | -3.13% | -46.9% |
| >= 5 sessions | 4 | 3 | 75.0% | -15.98% | -63.9% |

This is the central caveat: the rule is not a high-hit-rate timing signal.
Most brief exits are noise or wrong; the full-window edge comes from a small
number of large down episodes.

### Major risk-off episodes

| Start | End | Sessions | TQQQ return | `y60` at start | `dy60` | `front` | Trigger at start |
|---|---|---|---:|---:|---:|---:|---|
| 2022-08-24 | 2023-02-15 | 121 | **-19.83%** | 1.06 | 0.88 | 1.10 | front + slope |
| 2020-03-02 | 2020-03-31 | 22 | **-45.46%** | 1.61 | -0.06 | 0.25 | front |
| 2018-04-11 | 2018-04-26 | 12 | +2.30% | 1.29 | 0.24 | 0.30 | front |
| 2019-01-15 | 2019-01-22 | 5 | -0.93% | 2.19 | 0.40 | 0.01 | slope |
| 2018-12-12 | 2018-12-17 | 4 | **-13.44%** | 1.99 | 0.11 | 0.31 | front |
| 2018-09-17 | 2018-09-20 | 4 | +5.39% | 1.88 | 0.33 | 0.16 | front |
| 2018-04-04 | 2018-04-09 | 4 | -4.11% | 1.29 | 0.19 | 0.16 | front |
| 2019-01-03 | 2019-01-07 | 3 | **+16.90%** | 2.14 | 0.27 | 0.47 | front |
| 2019-01-29 | 2019-01-31 | 3 | **+12.50%** | 2.24 | 0.43 | -0.17 | slope |

The two big wins are the COVID crash (March 2020) and the 2022 tightening leg
(August 2022 - February 2023). The 2019 rows are the whipsaw: the signal
exited just before strong January rallies. The 2018 rows show a mix of good
and bad short exits; the 2018 exits collectively added about 23 pp relative to
TQQQ, but the path is noisy. The returns in the table are close-to-close over
the state run; fills are at the next open, so the realised avoided return
differs slightly.

## 5. Yearly and subperiod results

| Year | Strategy | TQQQ | Difference |
|---|---:|---:|---:|
| 2016 | +18.63% | +18.63% | 0.00 pp |
| 2017 | +119.99% | +112.96% | +7.03 pp |
| 2018 | **-0.07%** | -23.52% | **+23.45 pp** |
| 2019 | +77.36% | +130.48% | -53.12 pp |
| 2020 | **+309.94%** | +99.82% | **+210.12 pp** |
| 2021 | +90.88% | +90.88% | 0.00 pp |
| 2022 | **-58.78%** | -79.70% | **+20.92 pp** |
| 2023 | +128.43% | +204.89% | -76.46 pp |

| Subperiod | CAGR | Max DD | Sharpe | Total return |
|---|---:|---:|---:|---:|
| 2016-2019 | **49.60%** | 36.08% | 1.143 | +398.7% |
| 2020-2021 | **174.44%** | 35.98% | 1.882 | +650.1% |
| 2022-2023 | **-2.99%** | **74.37%** | 0.280 | -5.85% |

The strategy is a 2016-2021 compounder and a 2022-2023 flat-to-down book. The
2022-2023 subperiod is negative in absolute terms, although it is much better
than TQQQ (-38.1% cumulative, -21.3% CAGR). The 2023 miss is the
high-rate-bull problem: the major risk-off ends in mid-February 2023 and the
strategy is long for most of the remaining year, while TQQQ more than triples.

## 6. Parameter plateau

The pre-registered grid is `LO` x `HI` x `FRONT_T` x `SLOPE_T` = 3 x 3 x 4 x 3
= **108 cells**. Every cell is run on the 1-minute panel at 1 bp.

**Full grid:** CAGR 40.6%-69.6%, mean 55.5%, standard deviation 6.1%; Sharpe
0.906-1.256; max drawdown 76.68% in every cell; fills 141-549. **All 108 cells
clear the 36.72% / 82.29% / 0.82 bar.** The centre (1.00 / 4.00 / 0.15 / 0.40)
is at 57.97% CAGR, close to the grid median, not at the maximum. The drawdown
is identical across cells because the 2022 H1 trough precedes the first
BIL-based exit; no rate threshold in this grid avoids it.

**Slice at `LO=1.00`, `HI=4.00` — CAGR (top) and Sharpe (bottom):**

| `front` \ `slope` | 0.25 | 0.40 | 0.55 |
|---|---:|---:|---:|
| 0.10 | 62.8% | 62.8% | 64.0% |
| 0.15 | 58.7% | **58.0%** | 59.3% |
| 0.20 | 55.8% | 56.8% | 58.8% |
| 0.25 | 52.6% | 57.4% | 60.7% |

**Sharpe:**

| `front` \ `slope` | 0.25 | 0.40 | 0.55 |
|---|---:|---:|---:|
| 0.10 | 1.202 | 1.187 | 1.197 |
| 0.15 | 1.142 | **1.118** | 1.130 |
| 0.20 | 1.103 | 1.098 | 1.116 |
| 0.25 | 1.060 | 1.100 | 1.132 |

**Slice at `FRONT_T=0.15`, `SLOPE_T=0.40`:**

| `LO` \ `HI` | 3.50 | 4.00 | 4.50 |
|---|---:|---:|---:|
| 0.75 | 59.1% | 53.9% | 49.0% |
| 1.00 | 63.4% | **58.0%** | 53.0% |
| 1.25 | 55.7% | 50.6% | 45.8% |

The plateau is broad. The 2022 and 2023 state paths are actually invariant
across the 12-cell `LO=1/HI=4` slice: every cell loses -58.8% in 2022 and earns
+128.4% in 2023. The variation is in 2018 (-15.0% to +63.5%), 2019 (+50.1% to
+125.4%) and 2020 (+229.2% to +334.8%). The broad pass is therefore not a
knife-edge in the rate thresholds, but the crisis-year P&L is event-sensitive.

## 7. Placebo / circular shift

The state path is circularly shifted by a random offset (60..N-60) and
re-aligned with the same returns. This preserves the number of risk-off runs,
their lengths and the activity, but destroys the alignment with the rate
history. 300 daily shifts and 50 one-minute shifts were run.

| Placebo | Mean CAGR | Median | p90 | p95 | Max | p-value (CAGR) |
|---|---:|---:|---:|---:|---:|---:|
| 300 daily shifts | 31.0% | 29.4% | 46.5% | 52.3% | 62.8% | **0.0167** |
| 50 one-minute shifts | 30.2% | — | — | 55.4% | 71.3% | — |

The actual daily CAGR (57.5%) is above the 95th percentile; 5 of 300 placebos
beat it. The Sharpe p-value is 0.0033. The timing skill is significant at the
5% level, not at 1%, and the placebo distribution has a fat right tail (max
62.8%). This is consistent with a crisis-timing edge rather than a
high-Sharpe, every-year signal.

## 8. Correlation with current family winners

Daily returns on the common 2016-2023 dates. `beta` is the strategy's beta to
the winner. The winner curves are the repo's `research/new/curves/*.json`
daily equity exports, sliced to the development window.

| Winner | Correlation | Beta |
|---|---:|---:|
| ratio-froth | 0.629 | 0.913 |
| vol-scaled-crash-stop | 0.759 | 1.103 |
| relative-value-tqqq | **0.840** | 0.971 |
| fomc-opex-window | 0.613 | 0.858 |
| family-session-timing | 0.629 | 0.899 |
| family-short-reversal | 0.673 | 0.618 |
| family-rebalance-flow | **0.824** | 1.020 |
| family-intraday-microstructure-day | **0.531** | 0.737 |
| family-ml-microstructure | 0.791 | 1.032 |
| TQQQ daily | 0.819 | — |

Range **0.531-0.840**, mean about 0.70. The strategy is not a clone of any one
winner, but it is a TQQQ timing overlay: 85% TQQQ exposure and 0.819
correlation to TQQQ. It is most correlated with `relative-value-tqqq` (0.840)
and `family-rebalance-flow` (0.824), both of which are also long-TQQQ books
with a timing overlay.

## 9. Ablations and clock variants

| Variant | CAGR | Max DD | Sharpe | Fills |
|---|---:|---:|---:|---:|
| Centre | 57.97% | 76.68% | 1.118 | 361 |
| No high band (`HI=999`) | 52.44% | 76.68% | 1.070 | 443 |
| No low band (`LO=-999`) | 45.86% | 71.02% | 1.014 | 913 |
| Front-only (`SLOPE_T=999`) | 63.12% | 76.68% | 1.158 | 357 |
| Slope-only (`FRONT_T=999`) | 40.72% | 76.68% | 0.874 | 165 |
| TQQQ buy & hold | 36.15% | 82.29% | 0.801 | 1 |

| Clock | CAGR | Max DD | Sharpe | Fills |
|---|---:|---:|---:|---:|
| Daily (centre) | 57.97% | 76.68% | 1.118 | 361 |
| Weekly | 42.03% | 76.68% | 0.920 | 89 |
| Monthly | 25.70% | 76.68% | 0.687 | 21 |

The front-end stress (`front`) is the main driver; the slow tightening state
(`dy60`) costs about 5 pp of CAGR at the centre. It flattens 2018 but also cuts
2019, so its net effect is a robustness trade rather than a clear improvement.
The high band adds about 5.5 pp by keeping the book long in 2023. The low gate
adds about 12 pp; without it the variant has 913 fills because the 1-cent BIL
grid becomes a noise generator. Weekly and monthly clocks cut the CAGR to
42.0% and 25.7%; the signal decays in days, so the daily clock is the only one
that meets both the return and activity requirements.

## 10. Attribution and honest limitations

**The pass is crisis-dependent.** The log excess over TQQQ by year is roughly:

| Year | Log excess |
|---|---:|
| 2016 | 0.00 |
| 2017 | +0.03 |
| 2018 | +0.27 |
| 2019 | -0.26 |
| 2020 | **+0.72** |
| 2021 | 0.00 |
| 2022 | **+0.71** |
| 2023 | -0.29 |

2020 and 2022 each contribute about 60% of the net log excess; together they
contribute more than 100%, offset by 2019 and 2023. Ex-2020 CAGR is **35.3%**
versus TQQQ's **26.8%** over the same seven years. The strategy adds about
8.5 pp/year ex-2020, but its ex-2020 absolute CAGR is below the 36.72% bar.

**2022 H1 is structurally invisible.** The `LOW` gate treats `y60 < 1%` as
abundant liquidity. The Fed hiked from zero in March 2022 while the 60-day
bill yield was still below 1%; the strategy stayed long through the H1 crash
and only de-risked in late August 2022, when `y60` crossed 1% and the front
end spiked. The 2022 loss is -58.8% and the max drawdown is 76.68%, only 5.6 pp
better than TQQQ. Removing the low gate (`LO=-999`) cuts the drawdown to
71.0% but also cuts the CAGR to 45.9% and raises fills to 913 because the
1-cent BIL grid becomes a noise generator. This is the central trade-off of
the family and the main reason not to oversell it.

**2023 is a high-rate bull the strategy partly misses.** It is long only from
mid-February 2023 and earns +128.4% versus TQQQ's +204.9%. The high band and
the slow tightening filter are designed to avoid fighting the 2022 hikes, but
they also delay the 2023 re-risk. A 2024-2026 holdout that resembles 2023
would likely underperform TQQQ.

**The hit rate is low.** Only 20% of the 90 risk-off runs are followed by a
negative TQQQ return; the mean TQQQ return during those runs is -0.52%, but
that mean is dominated by two large episodes. The full window is carried by
those episodes. This is a crisis-alpha distribution, not a consistent timing
edge.

**The 2020 result is a single event.** In the 12-cell `LO=1/HI=4` slice, 2020
ranges from +229% to +335% depending on the exit threshold. The exact COVID
P&L is sensitive to whether the exit lands before or after the 2 March 2020
bounce. The broad grid passes, but the event-level attribution should not be
read as a repeatable 200 pp annual edge.

**No real-rate test.** The local data cannot support a real-rate proxy without
inventing inflation data. The strategy is nominal-only, so it cannot
distinguish a restrictive real rate from a restrictive nominal rate with
falling inflation. That is a genuine gap in the mechanism.

**Correlation and beta.** 0.819 daily correlation to TQQQ and 0.53-0.84 to the
winners. This is a TQQQ timing overlay, not independent alpha. The family is
new in signal, not in exposure.

## 11. Kill criteria and verdict

| # | Kill criterion | Result | Pass? |
|---|---|---|---|
| 1 | 1 bp CAGR <= 36.72%, Sharpe <= 0.82, or DD >= 82.29% | 57.97% / 1.118 / 76.68% | **pass** |
| 2 | < 100 fills or < 30 entries | 361 fills / 91 buys | **pass** |
| 3 | < 6 of 8 neighbouring cells above the bar | 108/108 cells above | **pass** |
| 4 | Placebo p > 0.10 | p = 0.0167 | **pass** |
| 5 | Correlation > 0.90 with any winner | max 0.840 | **pass** |
| 6 | Ex-2020 CAGR < 25% | 35.3% | **pass** |
| 7 | 10 bp CAGR < 25% | 51.67% | **pass** |
| 8 | 2022-2023 subperiod CAGR < -10% | -2.99% | **pass** |

All eight pre-registered kill criteria pass. The fragility flags, however, are
serious:

- 2022-2023 subperiod CAGR is negative (-2.99%) and the drawdown is 74.37%.
- Max drawdown is 76.68%, only 5.6 pp better than TQQQ.
- 2020 and 2022 together contribute more than 100% of the net log excess.
- Ex-2020 CAGR (35.3%) is below the headline bar.
- 2023 underperforms TQQQ by 76.5 pp.
- Off-run hit rate is 20%; the edge is two large episodes.
- Daily correlation to TQQQ is 0.819.

**Verdict:** a **qualified pass** at the development bar. The mechanism is
coherent, the plateau is unusually broad (all 108 cells pass), the placebo is
significant at 5%, and the activity floor is met. But the result is a
crisis-timing overlay, not an all-weather policy-liquidity regime. It is worth
a one-shot 2024-2026 holdout **only** as a crisis-alpha candidate; it should
not be promoted on development alone, and a holdout with no 2018/2020/2022-type
liquidity stress would likely see it lag TQQQ in a high-rate bull.

## 12. Reproduction

```powershell
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
$env:BT_THREADS = "1"
python research/new/family-policy-liquidity/strategy.py
python research/new/family-policy-liquidity/robustness.py
```

Files:

- `HYPOTHESIS.md` — pre-registration, mechanism, exact rules, falsifiers.
- `strategy.py` — runnable; regenerates `result.json`.
- `result.json` — headline metrics, yearly, subperiods, trade anatomy.
- `robustness.py` — grid, placebo, correlations, ablations, clocks.
- `robustness.json` — full robustness output.
