# Intraday-close momentum with a volatility-gated weakness exit

**Status:** pre-registered before the final grid run.
**Window:** 2016-01-04 .. 2023-12-29 only. Nothing on or after 2024-01-01 is
loaded by `strategy.py`.

## Hypothesis

TQQQ's return is concentrated in a high-exposure, close-anchored position:
the equity premium and the overnight drift are earned by holding through the
close and the next session. The risk is that a *weak close in an already
volatile tape* is a continuation signal, not a dip. So:

- stay at a volatility-targeted full weight while the tape is calm;
- when realised volatility is at or above the target **and** the full intraday
  return into the close is negative, exit to cash for the next 24 hours;
- re-enter at the next close if the weakness has cleared.

This is a high-exposure, long-only TQQQ timing rule. The close-momentum leg is
a crash/weakness filter; the return engine is the continuous vol-targeted
TQQQ exposure. The claim to test is that the filter cuts the left tail enough
to turn a ~70% drawdown vol-targeted position into a sub-60% one without giving
up the CAGR bar.

## Rules (exact)

Decision at the close of the **15:29 ET one-minute bar** (i.e. 15:30), filled
at the **15:30 open**. One decision per session.

```
r_k      = QQQ close(15:29) / QQQ open(09:30) - 1        # full intraday return
sigma_k  = annualised stdev of the last 10 completed QQQ daily log returns
           through session k-1 (daily adjusted closes; lagged one session)
base_k   = min(1, 0.20 / sigma_k)
w_k      = 0                         if r_k <= 0 and sigma_k >= 0.20
         = base_k                    otherwise
```

`w_k` is held from the 15:30 open of session k to the 15:30 open of session
k+1, then re-decided. No intraday stop, no BIL sleeve, no moving average, no
overnight-gap selection, no 15:58/10:01 time-of-day block. Idle weight is cash
at 0%.

The 0.20 number is used twice: as the volatility target and as the "elevated
vol" line. That is deliberate — one number, not two.

Warmup uses QQQ daily closes from 2015-01-02..2015-12-31 only, so the rule is
live on 2016-01-04. The daily parquet is truncated at 2023-12-29 before any
rolling statistic is computed.

## Pre-registered grid (8 cells)

The two knobs are the common volatility number (`line`) and the vol window.
The signal is always the full intraday QQQ return; the exit is always
`r <= 0 and sigma >= line`.

| # | line | vol window |
|---:|---:|---:|
| 1 | 0.20 | 10 (centre) |
| 2 | 0.18 | 10 |
| 3 | 0.22 | 10 |
| 4 | 0.20 | 5 |
| 5 | 0.20 | 15 |
| 6 | 0.20 | 20 |
| 7 | 0.18 | 20 |
| 8 | 0.22 | 20 |

The centre is the standard fast-vol choice (10 days), not the best cell. The
report must show the whole surface, including cells that fail.

## Pass criteria

- Dev CAGR > 36.72% and max DD < 82.29% at 1 bp.
- Target: CAGR > 36.72% with max DD < 60%.
- Must be reported at 1/5/10 bp. Turnover and fills must be disclosed.
- A cell that only passes at 1 bp is a fail for the programme's purposes.

## Falsifiers

- The close-exit leg adds nothing over the vol-only control (same CAGR, same
  DD).
- The result is a single year (2020 or 2022); cut tests should show it.
- The placebo (random exit days with the same count inside the high-vol
  window) matches the real CAGR.
- Turnover makes the edge disappear at 5 bp.
- Truncating the panel changes prior weights (look-ahead).

## What this is not

- Not a market-neutral or diversifying strategy: correlation to TQQQ will be
  high.
- Not a claim that down closes are bad on average. The unconditional next-24h
  return after a down close is positive in this sample. The claim is
  conditional: down close **and** elevated vol is the bad state.
- Not a re-tune of the 20-day-SMA overnight-drift filter: the signal here is
  one day's intraday return, the exit is conditional on the vol regime, and the
  holding is a continuous 24h position.
