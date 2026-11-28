# Hypothesis: volume-dispersion rotation (TQQQ / QQQ)

**Slug:** `family-vol-of-volume`
**Window:** development only, 2016-01-04 .. 2023-12-29, 1-minute marks.
**Bar:** TQQQ dev 36.72% CAGR / 82.29% max DD / 0.82 Sharpe (brief). The
panel's 1 bp TQQQ buy-and-hold is 36.15% / 82.29% / 0.80.
**Status:** pre-registered before the final `strategy.py` run. No 2024+ bar is
loaded anywhere in this directory.

## 1. Claim

Minute volume is not evenly distributed through a session. On a decisive,
trend-supporting day it clusters in a few minutes around the direction of the
move. On a diffuse, unstable day it is spread thinly across the session and
the move is more likely to be noise. The *shape* of the minute-volume
distribution therefore contains information about whether the current session's
move will persist into the next session.

The object is **dispersion / entropy of minute volume**, not the volume level
and not volume acceleration:

```
p_i = v_i / sum(v_i)          over the last 60 one-minute QQQ bars (15:00-15:59)
H   = -sum p_i log p_i / log(60)
rank_k = fraction of H in the prior 252 sessions that are <= H_k
```

A low rank means volume is more concentrated than usual: decisive
participation. A high rank means volume is more diffuse than usual: unstable
participation. The claim is:

> Low closing-hour volume entropy supports continuation of the current
> session's move; high entropy makes the next session fragile. Hold TQQQ when
> entropy rank is low, and QQQ when it is high.

QQQ, not BIL, is the defensive leg. It keeps full equity exposure and the
positive drift, while removing the 3x amplification exactly when participation
is diffuse. This is a rotation between two long equity assets, not a
volatility-target or a drawdown circuit breaker.

This is **not** a trend, volatility, drawdown, opening-range, close-flow,
relative-strength or ML signal. The only input is the dispersion of QQQ
minute volume over the closing hour, ranked against its own prior year.

## 2. Exact rules (centre)

For session `k` (a regular US session):

```
H_k     = entropy of QQQ 1-minute volume shares, 15:00-15:59 ET
rank_k  = mean( H_j <= H_k for j in k-252 .. k-1 )
target for session k+1:
    TQQQ 1.0                         if rank_k < 0.60
    QQQ  1.0                         if rank_k >= 0.60
    (first 60 sessions: QQQ, no signal)
```

- Decision clock: the 15:59 ET close of session `k`. The target is written on
  that bar and fills at the 09:30 open of `k+1`. The harness's next-open rule
  is used unchanged.
- The rank uses only sessions `k-252 .. k-1`; the current session's entropy is
  compared with, not included in, the reference set. No full-sample
  normalisation.
- Long only, weights >= 0, row sum = 1. The 2% rebalance band is the harness
  default. Headline cost 1 bp; 5 bp and 10 bp are reported.
- Idle asset is QQQ. There is no cash leg in the centre.

## 3. Pre-registered grid (8 cells)

The centre is entropy window 60 minutes and rank threshold 0.60. The grid
varies only the rank threshold, because the threshold is the only free
selection parameter. The entropy window and rank lookback are checked as
neighbours, not selected on the evaluation window.

| Cell | Window | Rank threshold |
|---:|---:|---:|
| 1 | 60 min | 0.40 |
| 2 | 60 min | 0.45 |
| 3 | 60 min | 0.50 |
| 4 | 60 min | 0.55 |
| 5 | 60 min | **0.60 (centre)** |
| 6 | 60 min | 0.65 |
| 7 | 60 min | 0.70 |
| 8 | 60 min | 0.75 |

Neighbour checks: entropy window 30/45/60/90/120 minutes; rank lookback
126/252/504 sessions; a continuous weight ramp from rank 0.40 (TQQQ 1.0) to
0.80 (TQQQ 0.0).

## 4. Falsifiers decided before the run

- 1 bp CAGR <= 36.72% or max DD >= 82.29%.
- Fewer than 100 full-window fills.
- Circular-shift placebo p-value > 0.10.
- The 5 bp result turns CAGR below the bar or DD above it.
- Sign flip in 2016-2019 or 2022-2023.
- Correlation with any current winner > 0.90.
- Neighbour windows are not all positive.

A negative result is reported as a negative result. The 10 bp result is
expected to be the weak point: 685 signal changes and two equity legs make the
strategy cost-sensitive.
