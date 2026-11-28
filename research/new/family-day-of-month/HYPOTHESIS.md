# Hypothesis: month-end five-session TQQQ overweight

**Slug:** `family-day-of-month`
**Window:** development only, 2016-01-04 .. 2023-12-29, 1-minute marks.
**Bar:** TQQQ dev 36.72% CAGR / 82.29% max DD / 0.82 Sharpe (brief). The
panel's 1 bp TQQQ buy-and-hold is 36.15% / 82.29% / 0.80.
**Status:** pre-registered before the final `strategy.py` run. No 2024+ bar is
loaded anywhere in this directory.

## 1. Claim

The last few sessions of a calendar month are a predictable flow window.
Pension and mutual-fund rebalancing, index and model-portfolio adjustments,
and payroll/401(k) contributions cluster near month-end. The flow is
predominantly into large-cap equity, so the last five sessions should carry a
higher TQQQ drift than the rest of the month.

The object is the **session rank inside the calendar month**, not weekday,
month-of-year, FOMC, OpEx, trend, volatility, drawdown, opening range, close
flow, ML or relative strength. The rule is a core-plus-overweight, not a pure
event trade:

```
core:   TQQQ 60%, BIL 40%          for sessions 1 .. n-5
event:  TQQQ 100%, BIL 0%          for the last 5 sessions of the month
```

A pure event book (100% TQQQ only in the last five sessions, BIL otherwise) is
reported as a control: it earns only 27.52% CAGR because it is out of the
market 76% of the time. The harvestable object is the *overweight* on top of a
core equity position, not a standalone five-day trade.

## 2. Exact rules (centre)

For session `k` (a regular US session):

```
rank_k  = 1 + number of earlier sessions in the same calendar month
n_k     = number of sessions in that month
target_k = 1.00  if rank_k > n_k - 5
         = 0.60  otherwise
w_tqqq(k) = target_k
w_bil(k)  = 1 - target_k
```

- The calendar rank and month length are known in advance. The target for
  session `k` is written on the 15:59 bar of `k-1` and fills at the 09:30 open
  of `k`. The harness's next-open rule is used unchanged.
- Long only, weights >= 0, row sum = 1. The 2% rebalance band is the harness
  default. Headline cost 1 bp; 5 bp and 10 bp are reported.
- Idle weight is BIL, not cash.
- No trend, volatility, drawdown, opening-range, close-flow, relative-strength
  or ML input. The only input is the position of the session inside its month.

## 3. Pre-registered grid (8 cells)

The centre is core 60%, event 100%, last five sessions. The grid varies the
core weight, because the core is the risk-budget parameter. The event-window
length is checked as a neighbour, not selected on the evaluation window.

| Cell | Core TQQQ | Event TQQQ | Event window |
|---:|---:|---:|---:|
| 1 | 45% | 100% | last 5 |
| 2 | 50% | 100% | last 5 |
| 3 | 55% | 100% | last 5 |
| 4 | **60%** | **100%** | **last 5** |
| 5 | 65% | 100% | last 5 |
| 6 | 70% | 100% | last 5 |
| 7 | 75% | 100% | last 5 |
| 8 | 80% | 100% | last 5 |

Neighbour checks: event window 3, 4, 5, 6 and 7 sessions at the 60% core.
Placebos: first five sessions of the month (same length, wrong clock); shifted
event windows at −10, −5, +5, +10 sessions; 300 random five-session-equivalent
blocks with the same event count.

## 4. Falsifiers decided before the run

- 1 bp CAGR <= 36.72% or max DD >= 82.29%.
- Fewer than 100 full-window fills.
- Shifted-day or random-block placebo matches the real result.
- The 5 bp result turns CAGR below the bar.
- Sign flip in 2016-2019 or 2022-2023.
- Correlation with any current winner > 0.90.
- Event-window neighbours 3-7 sessions are not all positive.

A negative result is reported as a negative result. The main overfit risk is
the five-session window: 3-4 sessions are close, 6-7 are weaker.
