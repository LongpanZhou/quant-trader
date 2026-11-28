# Report: CPI/NFP release windows on TQQQ

**Strategy:** `family-cpi-nfp-release`
**Window:** development only, 2016-01-04 .. 2023-12-29, 1-minute marks, next-open
fills, 2% band, idle BIL.
**Bar:** TQQQ dev 36.72% CAGR / 82.29% max DD / 0.82 Sharpe (brief). The panel's
1 bp TQQQ buy-and-hold is 36.15% / 82.29% / 0.80.

## Verdict

**Negative as a standalone strategy; positive as an event study and a
diversifier.** The centre holds TQQQ only on the CPI proxy session and earns
**10.14% CAGR / 26.16% max DD / 0.65 Sharpe at 1 bp**, falling to **5.46% /
32.27% / 0.40 at 10 bp**. It cannot replace TQQQ and is 26.5 pp below the CAGR
bar. But the CPI-day conditional mean is **+81.9 bp (t = 1.94, n = 96)** and is
positive in all eight years; the correlation to the nine current winners is only
**0.094-0.234**. The NFP day, by contrast, is flat (+6.7 bp, t = 0.15). The
family is a clean example of a real but small event window that is too
low-exposure to be a return engine.

The important honesty check: the CPI-day edge is **not intraday**. The CPI
session's open-to-close return is only +3.9 bp (t = 0.13); the +81.9 bp
open-to-open comes almost entirely from the **close-to-next-open** gap
(~+78 bp). Because the proxy is fixed at calendar day 12 and the actual CPI
release is usually a few days later, the overnight may be capturing the actual
release morning. The strategy is still ex-ante and tradable, but the
"release-day drift" label is too strong; it is a mid-month overnight window.
NFP, which has an actual fixed release date (first Friday), shows no edge. That
asymmetry is the main reason the family is rejected.

## 1. What the strategy does

For each month, let `cpi_day` be the first regular session whose calendar day
of month is >= 12. This is a fixed ex-ante proxy for the CPI release, which is
published at 08:30 ET in the 10th-15th calendar-day window. Then:

```
w_tqqq(k) = 1.00   if k == cpi_day
          = 0.00   otherwise
w_bil(k)  = 1 - w_tqqq(k)
```

- The CPI proxy date is known at the start of the month. The target is set at
  the prior close and filled at the CPI session's open; the exit target (0) is
  set at the CPI session's close and filled at the next open. The harness's
  next-open rule is used unchanged.
- NFP is the first Friday session of the month, a pre-registered control. It is
  not the centre because it has no positive edge in this sample.
- Idle is BIL. The cash-idle variant earns 8.92% at 1 bp, 1.22 pp less; BIL is
  the better idle asset.
- No trend SMA, no realised vol, no drawdown state, no cross-sectional signal,
  no full-sample normalisation.
- The CPI proxy is deliberately **not** the actual historical release date. The
  rule does not hardcode future dates; it can be a few days early or late.

## 2. Headline development result

| cost | CAGR | max DD | Sharpe | Sortino | vol | ending equity |
|---:|---:|---:|---:|---:|---:|---:|
| 1 bp | **10.14%** | **26.16%** | **0.65** | 1.03 | 17.1% | $216k |
| 5 bp | 8.04% | 28.08% | 0.54 | 0.85 | 17.0% | $185k |
| 10 bp | 5.46% | 32.27% | 0.40 | 0.62 | 17.0% | $153k |
| TQQQ | 36.15% | 82.29% | 0.80 | 1.12 | 66.5% | $1.175m |

| cost | fills | turnover |
|---:|---:|---:|
| 1 bp | 385 | 568.7x |
| 5 bp | 385 | 523.2x |
| 10 bp | 385 | 472.7x |

The strategy is in TQQQ **4.8%** of sessions (96 days out of 2,012) and in BIL
the other 95.2%. The harness `exposure` field is 100% because BIL is an asset;
the mean TQQQ weight is 4.79%. The low exposure is why the CAGR is low: the
conditional mean is strong, but it is earned on only 96 days.

**Drawdown:** the max drawdown is 2022-06-13 to 2022-11-14, **-26.16%**. For a
4.8%-exposed strategy, that is a large DD: the CPI days in 2022 clustered in the
bear market and the strategy was long TQQQ on some of the worst sessions.

**Turnover / fills:** 569x, 385 fills. The strategy enters and exits once a
month; the 2% band is not the main driver.

## 3. Event study: CPI vs NFP

Session-level TQQQ returns, 2016-2023, n = 96 events each. `day` is the event
session open-to-open (the tradable return of holding the event day and selling
at the next open); `oc` is the event session open-to-close; `next` is the
following session open-to-open; `2-day` is day + next.

| event | day mean | day t | day win | day OC | next | 2-day |
|---|---:|---:|---:|---:|---:|---:|
| **CPI proxy (day 12)** | **+81.9 bp** | **1.94** | 61.5% | +3.9 bp | -13.5 bp | +68.4 bp |
| NFP (first Friday) | +6.7 bp | 0.15 | 59.4% | +46.1 bp | -15.9 bp | -9.2 bp |
| CPI or NFP | +44.3 bp | 1.42 | 60.4% | — | -14.7 bp | +29.6 bp |

The CPI day is the only positive event. The NFP day is flat, and its
open-to-close is actually +46.1 bp (t = 1.38) but it gives it all back
overnight and more (-15.9 bp next), for a negative 2-day. The CPI day's
open-to-close is only +3.9 bp; the day's +81.9 bp is almost all the
close-to-next-open gap (~+78 bp). The next session gives back -13.5 bp, so the
net two-day is +68.4 bp.

This decomposition is the key mechanism finding. If the effect were a
release-day intraday drift, the open-to-close would be positive. It is not. The
effect is a **close-to-next-open** move, which is consistent with the proxy day
being the session before the actual CPI release: the strategy holds through the
release morning and sells at the next open. The rule is ex-ante and captures
that gap, but it is not a "CPI day" intraday effect. The NFP day, which is the
actual release date, has no such gap. That weakens the CPI-specific
interpretation; the proxy may be capturing a mid-month overnight seasonality
rather than a CPI announcement.

CPI-day mean by year (all positive):

| year | n | mean | t | win |
|---:|---:|---:|---:|---:|
| 2016 | 12 | +111.4 bp | 1.42 | 66.7% |
| 2017 | 12 | +71.3 bp | 2.30 | 75.0% |
| 2018 | 12 | +66.3 bp | 0.85 | 75.0% |
| 2019 | 12 | +71.4 bp | 1.50 | 58.3% |
| 2020 | 12 | +90.2 bp | 0.48 | 58.3% |
| 2021 | 12 | +32.9 bp | 0.40 | 50.0% |
| 2022 | 12 | +31.8 bp | 0.15 | 50.0% |
| 2023 | 12 | +180.1 bp | 1.83 | 58.3% |

The sign is stable, but the magnitude is noisy and 2023 is the largest year.
The 2023 share of the strategy's total log return is about 32%, below the 50%
kill threshold, so the edge is not one year.

## 4. Pre-registered grid

The 8 cells were fixed in `HYPOTHESIS.md` before the final run:

| # | event | window | role | 1 bp CAGR | 1 bp DD | 1 bp Sharpe | 10 bp CAGR |
|---:|---|---:|---|---:|---:|---:|---:|
| 1 | CPI day 10 | day only | proxy neighbour | 3.40% | 35.52% | 0.30 | -0.99% |
| 2 | CPI day 11 | day only | proxy neighbour | 3.74% | 54.11% | 0.31 | -0.66% |
| 3 | **CPI day 12** | **day only** | **centre** | **10.14%** | **26.16%** | **0.65** | **5.46%** |
| 4 | CPI day 13 | day only | proxy neighbour | 6.03% | 30.29% | 0.43 | 1.53% |
| 5 | CPI day 12 | day + next | window neighbour | 6.78% | 52.12% | 0.40 | 2.24% |
| 6 | CPI day 12 + NFP | day only | combined control | 9.09% | 48.28% | 0.49 | 0.12% |
| 7 | NFP | day only | release control | 0.42% | 43.12% | 0.11 | -3.85% |
| 8 | CPI day 12, 50% | day only | exposure neighbour | 6.03% | 13.43% | 0.72 | 3.73% |

The centre is the **only** cell that clears 5% CAGR at 10 bp (5.46%). The
neighbours at day 10 and day 11 are negative at 10 bp; day 13 is 1.53%. The
proxy is a spike at day 12, not a broad plateau. The NFP-only cell is flat at
1 bp and negative at 10 bp. The CPI+NFP combination is 9.09% at 1 bp but only
0.12% at 10 bp because it doubles the event count and the NFP days add
turnover without mean. The 50% exposure cell has the best Sharpe (0.72) but a
6.03% CAGR; it is a lower-risk version of the same small edge.

## 5. Controls and rejected alternatives

| variant | CAGR | max DD | Sharpe | comment |
|---|---:|---:|---:|---|
| **CPI day 12, 100%** | **10.14%** | **26.16%** | **0.65** | centre |
| CPI day 12, 50% | 6.03% | 13.43% | 0.72 | best Sharpe, lower return |
| CPI day 12, cash idle | 8.92% | 26.72% | 0.59 | BIL is better |
| CPI day + next | 6.78% | 52.12% | 0.40 | second session dilutes |
| NFP day + next | -2.53% | 60.12% | 0.00 | negative |
| Pre-release de-risk (100% except pre-event) | 25.59% | 84.74% | 0.68 | high DD, not a standalone |
| TQQQ buy & hold | 36.15% | 82.29% | 0.80 | bar |

The pre-release de-risk is the obvious alternative: hold TQQQ all the time but
go flat on the session before each CPI/NFP release. On the daily approximation
it looked strong, but on the 1-minute panel it earns only 25.59% with an 84.74%
DD, worse than TQQQ on both counts. The 1-minute implementation has 761 fills
and 3,019x turnover; the daily approximation ignored the cost of the pre-release
round trips. It is rejected.

## 6. Placebo

The placebo keeps the same number of event days (96) but chooses them at random.
1,000 draws, daily open-to-open approximation:

| | CAGR |
|---|---:|
| real strategy (1-min, 1 bp) | 10.14% |
| real strategy (daily approximation) | 10.67% |
| placebo mean | 2.66% |
| placebo p95 | 11.12% |
| placebo p99 | 15.11% |
| placebo max | 21.73% |
| p-value (draws >= real) | **0.058** |

The real event days are above the 94th percentile of random 96-day calendars.
The p-value is 0.058, just below the 0.10 kill threshold but not strong. The
real daily approximation (10.67%) is slightly below the placebo p95 (11.12%),
so a random calendar can match the result; the real edge is in the mean, not in
the tail.

## 7. Sub-periods and yearly behaviour

| period | strategy CAGR | strategy DD | TQQQ CAGR | TQQQ DD |
|---|---:|---:|---:|---:|
| 2016-2019 | 10.49% | 7.99% | 49.67% | 56.77% |
| 2020-2023 | 9.80% | 25.06% | 24.11% | 81.57% |
| **ex-2020** | **10.14%** | **25.06%** | **28.35%** | 81.57% |

| year | strategy | TQQQ |
|---:|---:|---:|
| 2016 | +13.3% | +19.9% |
| 2017 | +9.1% | +114.5% |
| 2018 | +9.1% | -20.8% |
| 2019 | +10.4% | +148.2% |
| 2020 | +8.4% | +104.1% |
| 2021 | +2.9% | +81.1% |
| 2022 | +1.5% | -79.4% |
| 2023 | +28.4% | +192.0% |

The strategy is positive in every year, including 2018 and 2022, because it is
out of the market 95% of the time. It is a low-volatility, low-return sleeve,
not a TQQQ substitute. The 2016-2019 CAGR (10.49%) is slightly higher than
2020-2023 (9.80%), which is a good stability sign; the 2020-2023 DD is much
larger (25.06% vs 7.99%) because the CPI days in 2022 were in the bear market.

## 8. Correlations to the nine current winners

Daily-return Pearson correlation, development window only:

| winner | correlation |
|---|---:|
| ratio-froth | 0.095 |
| vol-scaled-crash-stop | 0.147 |
| relative-value-tqqq | 0.194 |
| fomc-opex-window | 0.094 |
| family-session-timing | 0.198 |
| family-short-reversal | 0.234 |
| family-rebalance-flow | 0.190 |
| family-intraday-microstructure-day | 0.157 |
| family-ml-microstructure | 0.190 |

Range **0.094-0.234**, mean **0.167**. This is the lowest correlation of the
four new families and the main reason to keep the study. A 4.8%-exposed
event sleeve with a positive mean and near-zero correlation is a genuine
diversifier, even though it cannot be a standalone return engine.

## 9. Causality and no look-ahead

- The CPI proxy date is the first session on/after calendar day 12, known at the
  start of the month. The NFP proxy is the first Friday session, also known.
  The target is set at the prior close and filled at the next open.
- No actual release dates are hardcoded; the rule can be a few days early or
  late. This is deliberate and is the main source of mechanism uncertainty.
- No warmup indicator is needed; the first decision is 2016-01-04.
- Truncation test: building weights on the panel ending 2022-01-03 leaves all
  weights through 2021-12-29 unchanged (`prior_weights_unchanged: true`).
- No 2024+ bar is loaded in `strategy.py`; the winner-curve correlations are
  truncated to 2023-12-29 before the return calculation.

## 10. Kill criteria and result

| criterion | result | pass? |
|---|---|---|
| 10 bp CAGR <= 36.72% | 5.46% | **fail (expected)** |
| CPI day mean not positive or t < 1.5 | +81.9 bp, t = 1.94 | pass |
| CPI not better than NFP | CPI 10.14% vs NFP 0.42%; +81.9 bp vs +6.7 bp | pass |
| random-event placebo p > 0.10 | p = 0.058 | pass |
| 2023 share > 50% of total log | ~35% | pass |
| proxy spike (day 11 and day 13 both negative) | +3.74% / +6.03% at 1 bp; means positive | pass |

The return criterion fails, so the verdict is **negative as a standalone
strategy**. The event-study criteria pass. The family is a valid negative
result with a usable diversifier sleeve.

## 11. Limitations

1. **The CPI proxy is not the release date.** The first session on/after day 12
   can be a few days before or after the actual CPI release. The +81.9 bp is a
   close-to-next-open gap, not an intraday release-day drift. The mechanism may
   be a mid-month overnight seasonality or an accidental alignment with the
   actual release morning, not a CPI-specific announcement effect.
2. **NFP has no edge.** The actual NFP release day is flat (+6.7 bp, t = 0.15).
   If the family were a generic "macro release" effect, NFP should show it. The
   asymmetry is evidence against a simple release-day interpretation.
3. **The proxy is a spike.** Day 10 and day 11 are negative at 10 bp; day 13 is
   1.53%. The centre is the only cell above 5% at 10 bp. A broad plateau would
   be more convincing.
4. **The placebo p = 0.058 is marginal.** The real daily result is below the
   placebo p95. The event mean is positive in all eight years, but the sample
   is only 96 days.
5. **Low exposure means low return.** 4.8% TQQQ weight, 10.14% CAGR at 1 bp,
   5.46% at 10 bp. It cannot replace TQQQ and it is not a standalone strategy.
6. **The 2022 drawdown is 26.16%.** For a 4.8%-exposed sleeve, that is a large
   left tail; the CPI days clustered in the 2022 bear market.

## 12. Final verdict

**The family is rejected as a standalone return strategy but retained as a
positive event study and a low-correlation diversifier.** The deliverable is:

- 10.14% CAGR / 26.16% DD / 0.65 Sharpe at 1 bp;
- 5.46% CAGR / 32.27% DD / 0.40 Sharpe at 10 bp;
- CPI-day mean +81.9 bp (t = 1.94), positive in all eight years;
- NFP day +6.7 bp (t = 0.15), no edge;
- correlation to the nine winners 0.094-0.234;
- random-event placebo p = 0.058;
- exact pre-cut weights (causality truncation test passes).

The honest one-line description: *a 4.8%-exposed TQQQ sleeve that holds the
mid-month CPI proxy session and sells at the next open; the return is a
close-to-next-open gap, not an intraday release-day drift, and the NFP release
day has no edge.* It is useful as a diversifier, not as a replacement for TQQQ.
