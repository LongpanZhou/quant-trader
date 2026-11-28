# family-tqqq-decay — hypothesis and pre-registration

**Slug:** `family-tqqq-decay`
**Family:** TQQQ decay
**Development window:** 2016-01-04 .. 2023-12-29 only. 2024-2026 is not loaded
or inspected.
**Benchmark bar:** TQQQ 36.72% CAGR / 82.29% max DD / 0.82 Sharpe (published
1-minute-mark bar). TQQQ on this panel is 35.81% / 82.30% / 0.80.

## 1. Mechanism

A 3x daily-reset fund has an explicit compounding identity. In logs, a first-
order approximation is

```
log(TQQQ_t / TQQQ_{t-1}) = 3 * log(QQQ_t / QQQ_{t-1}) - 3 * sigma_Q^2 + noise
```

The difference `D_t = 3*r_Q,t - r_T,t` is the **realised decay** of the fund
against a 3x daily-reset QQQ synthetic. It is not a model: it uses the actual
TQQQ and QQQ closes and therefore also contains financing, fees and tracking
noise on top of the variance drag.

The hypothesis is that a dollar of TQQQ is cheap when its *current* decay is
below its own structural level. The structural level is the 252-session mean of
`D`. The fast 21-session mean measures what the fund is paying now. Their ratio

```
decay_ratio = mean(D, 21) / mean(D, 252) - 1
```

is the primary object:

* `decay_ratio < -0.10`: the fund is decaying at least 10% less than its own
  structural rate; the leverage is cheap relative to its history -> TQQQ.
* `-0.10 <= decay_ratio < 0.20`: normal-to-slightly-elevated decay; use
  unlevered QQQ.
* `decay_ratio >= 0.20`: decay is running at least 20% hotter than the
  structural rate; the 3x wrapper is expensive -> BIL.

This is a decay-flow signal, not the TQQQ/QQQ **price-ratio level** used by
`ratio-froth`/`relative-value-tqqq`. It is also not a volatility-target rule:
there is no `target_vol / realised_vol` position size; the state is set by the
realised fund-specific log-return shortfall relative to its own baseline.

## 2. Exact rules

All inputs use daily closes through session `t`; the target is set at that
close and executed at the first bar open of `t+1`.

1. `r_Q,t = log(QQQ_t / QQQ_{t-1})`, `r_T,t = log(TQQQ_t / TQQQ_{t-1})`.
2. `D_t = 3*r_Q,t - r_T,t`.
3. `fast = mean(D, 21 sessions)`, `slow = mean(D, 252 sessions)`.
4. `decay_ratio = fast / max(slow, 1e-5) - 1`.
5. State:
   * **TQQQ** if `decay_ratio < -0.10`;
   * **QQQ** if `decay_ratio < 0.20`;
   * **BIL** otherwise.
6. Weights are long-only, sum to 1, held through the next session.

Warm-up: `slow` needs 252 sessions, so 2016 is BIL. That year is included in
the reported CAGR and is not excluded.

## 3. Estimation window and decision clock

| Item | Choice |
|---|---|
| Fast decay window | 21 sessions |
| Structural decay window | 252 sessions |
| Decay definition | `3*r_QQQ - r_TQQQ`, log returns |
| Data | local adjusted 1-minute QQQ/TQQQ/BIL panel via `research/bt.py` |
| Decision | close of session `t` |
| Fill | first bar open of `t+1` |
| Costs | 1 bp headline; 5 bp and 10 bp reported |
| Band | 2% notional |

No 2024-2026 row is read by the development run.

## 4. Why this is not an existing family

* Not `ratio-froth`: no TQQQ/QQQ ratio level, no 200-day ratio mean, no
  165-day QQQ trend gate and no intraday stop.
* Not `relative-value-tqqq`: that uses 100-session ratio **momentum** plus a
  20-session absolute volatility scale. Here the object is the realised
  log-return shortfall `3*r_Q - r_T` and its ratio to its own 252-session mean.
* Not `vol-scaled-crash-stop`: no drawdown/capitulation trigger and no
  `target_vol` sizing. The state is a decay-rate threshold.
* The signal is fund-specific: it uses the actual TQQQ compounding path, not a
  generic QQQ volatility estimate.

## 5. Pre-registered 8-cell grid

| # | fast | slow | tqqq_threshold |
|---:|---:|---:|---:|
| 1 | 10 | 252 | -0.10 |
| 2 | **21** | **252** | **-0.10** (primary) |
| 3 | 42 | 252 | -0.10 |
| 4 | 21 | 189 | -0.10 |
| 5 | 21 | 252 | -0.20 |
| 6 | 21 | 252 | 0.00 |
| 7 | 10 | 252 | 0.00 |
| 8 | 42 | 252 | 0.00 |

`qqq_threshold = 0.20` is fixed in all cells. The primary is the 21/252 cell
with the -10% threshold, which is the mechanism's natural "decay below its
structural level" boundary.

## 6. Falsifiers (pre-registered)

1. 1 bp CAGR <= 36.72% or max DD >= 82.29%.
2. 10 bp CAGR <= 36.72%.
3. Circular-shift placebo CAGR percentile < 90%.
4. Correlation with any current winner > 0.95.
5. Fewer than 100 fills or fewer than 30 independent fill events.
6. Any subperiod (2016-2019, 2020-2021, 2022-2023) with negative CAGR.
7. Static average-weight book within 1 pp of the 1 bp CAGR.

## 7. Expected effect

| metric | expectation |
|---|---|
| CAGR (1 bp) | 40-48% |
| max DD | 35-50% |
| Sharpe | 1.05-1.20 |
| average TQQQ weight | 0.45-0.55 |
| correlation to winners | 0.55-0.80 |

Because `D` is approximately `3*sigma_Q^2`, this family is mechanically related
to variance timing. The honest test is whether the *relative-to-structural*
decay ratio and the actual TQQQ tracking path add anything beyond a plain
volatility state; the report gives the correlation to `vol-scaled-crash-stop`
and the static-blend comparison.
