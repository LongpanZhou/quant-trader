# Hypothesis: CPI/NFP release windows — the CPI release-day drift

**Slug:** `family-cpi-nfp-release`
**Window:** development only, 2016-01-04 .. 2023-12-29, 1-minute marks.
**Bar:** TQQQ dev 36.72% CAGR / 82.29% max DD / 0.82 Sharpe (brief). The
panel's 1 bp TQQQ buy-and-hold is 36.29% / 81.57% / 0.80.
**Status:** pre-registered before the final `strategy.py` run. No 2024+ bar is
loaded anywhere in this directory.

## 1. Claim

Scheduled macro releases are an ex-ante clock. The market prices the release
before the print and then trades the surprise. Two releases dominate the
monthly cycle:

- **NFP** (Employment Situation) is released at 08:30 ET on the first Friday
  of the month (with rare holiday exceptions). The print is before the open,
  so the release-day session contains the full reaction.
- **CPI** is released at 08:30 ET in the 10th-15th calendar-day window. The
  exact date is published in advance but is not fixed; we use a **fixed
  ex-ante proxy**: the first regular session on or after the 12th calendar day
  of the month. The 12th is the midpoint of the official release window. The
  proxy can be a few days early or late; it is deliberately not the actual
  historical release date, so the rule does not hardcode future dates.

The claim is that the **CPI release-day session** has a positive drift: the
pre-release risk premium is paid, the print clears uncertainty, and the index
tends to close higher on the day. The NFP release day is expected to be
weaker: the payroll print is noisier and the reaction is more often a
reversal. The strategy therefore holds TQQQ only on the CPI proxy session,
and uses NFP as a pre-registered control. Both clocks are tested; the family
is not allowed to pick the better one after the fact without disclosure.

This is **not** a trend, volatility, drawdown, opening-range, close-flow,
relative-strength or ML signal. The only inputs are the calendar release
proxies. The decision is known at the prior close.

## 2. Exact rules (centre)

Universe: QQQ (not used), TQQQ (position), BIL (idle).

For each month, let `cpi_day` be the first regular session whose calendar day
of month is >= 12. (If the month has no such session, which cannot happen for
a regular month, the month is skipped.) Then, for session `k`:

```
w_tqqq(k) = 1.00   if k == cpi_day
          = 0.00   otherwise
w_bil(k)  = 1 - w_tqqq(k)
```

- The CPI proxy date is known at the start of the month. The target is set at
  the prior close and filled at the CPI session's open; the exit target (0) is
  set at the CPI session's close and filled at the next open. The harness's
  next-open rule is used unchanged.
- Idle weight is BIL, not cash.
- The 2% rebalance band is the harness default. Headline cost is 1 bp; 5 bp
  and 10 bp are reported.
- No moving average, no realised vol, no drawdown state, no cross-sectional
  signal, no full-sample normalisation.

## 3. Pre-registered grid (8 cells)

The centre is **CPI proxy day, day-only, 100% TQQQ**. The grid is a local
neighbourhood around it, fixed before the final run:

| # | event | window | role |
|---:|---|---|---|
| 1 | CPI, first session on/after day 10 | day only | proxy neighbour |
| 2 | CPI, first session on/after day 11 | day only | proxy neighbour |
| 3 | **CPI, first session on/after day 12** | **day only** | **centre** |
| 4 | CPI, first session on/after day 13 | day only | proxy neighbour |
| 5 | CPI, first session on/after day 12 | day + next | window neighbour |
| 6 | NFP, first Friday | day only | release control |
| 7 | CPI day 12 + NFP day | day only | combined control |
| 8 | CPI day 12, 50% TQQQ | day only | exposure neighbour |

Every cell is reported, including the failures. No cell is selected on the
holdout.

## 4. Pilot scan disclosure

A coarse scan of the dev window was run before fixing the grid. It covered:

- NFP day, NFP-1, NFP+1;
- CPI proxies: first session on/after calendar days 8, 10, 11, 12, 13, 14;
- the 11th trading session of the month and the second Wednesday;
- release-day, next-session and two-session windows;
- day-only vs a base position with a release overlay.

It showed that the **CPI day-12 proxy** has the strongest release-day mean
(+79.5 bp, t = 1.88, n = 96) and a positive two-session window (+131.5 bp,
t = 2.54). The **NFP day is flat** (+6.1 bp, t = 0.13) and the NFP day+next
window is slightly negative. The combined CPI+NFP window is diluted by NFP.
The CPI day+next window has a lower Sharpe than the day-only version because
the second session adds volatility without adding mean. The centre was fixed
at the day-12 midpoint and day-only before the final run; the other proxies
and NFP are reported as grid cells. The pilot also produced two rejected
ideas reported in `report.md`:

1. **De-risk the pre-release session**: 44.8% gross at 1 bp, but the pre-day
   mean is only -14 bp (t ~ -0.4), it is 2020-tail-driven, and it is not
   "release day/next session only." It is not the delivered centre.
2. **CPI day + next session**: 6.8% at 1 bp, below the day-only centre. The
   second session does not pay for its extra exposure.

## 5. Falsification criteria

The hypothesis is rejected as a standalone strategy if any of the following
holds on the dev window:

1. Centre 10 bp CAGR <= 36.72% (the family is expected to fail this; the
   point of the study is the event window, not a TQQQ replacement).
2. The CPI release-day mean is not positive at t >= 1.5.
3. The CPI day is not better than the NFP day on 1 bp CAGR and conditional
   mean.
4. The random-event placebo beats the centre with p > 0.10 (daily
   approximation).
5. The entire CPI effect is one year: 2023 contributes more than 50% of the
   total log return.
6. The CPI day-12 proxy is a spike: the day-11 and day-13 neighbours both
   have negative conditional means.

Criterion 2 is the event-study test. Criterion 1 is the return test. The
family can pass the event study and fail the return test; that is a valid
negative result, and it must be reported that way.

## 6. What would make this a real holdout candidate

The strategy is in TQQQ only about 4.8% of sessions, so it cannot replace
TQQQ. Its value is as a **diversifier**: a low-correlation, positive-mean
event sleeve that can be layered on a core book. It is a candidate for the
one-shot holdout only as an event sleeve, not as a standalone return engine.
If the CPI-day mean is not stable across sub-periods or the random-event
placebo is as good, the honest verdict is "no event edge."
