# family-sector-rotation — hypothesis and pre-registration

**Slug:** `family-sector-rotation`
**Family:** sector rotation (growth vs defensive leadership)
**Development window:** 2016-01-04 .. 2023-12-29 only. 2024-2026 is not
loaded or inspected by the development run.
**Benchmark bar:** TQQQ 36.72% CAGR / 82.29% max DD / 0.82 Sharpe (published
1-minute-mark bar). TQQQ on this panel is 36.15% / 82.29% / 0.80.

## 1. Mechanism

TQQQ is a constant 3x wrapper on QQQ, so its return is dominated by the
Nasdaq-100 trend. But the composition of that trend matters. When technology
(XLK) is leading utilities (XLU), the market is paying for growth and
duration; the risk appetite that supports a 3x Nasdaq position is broad and
persistent. When utilities are leading technology, investors are moving toward
defensive cash flows and rate-sensitive safety; that is a risk-off state in
which a 3x daily-reset wrapper is poorly compensated.

The primary object is therefore the **XLK/XLU relative return**, not a QQQ
price trend, a volatility estimate, or a calendar clock. The 20-day leg
captures an emerging rotation; the 60-day leg confirms that it is a regime
rather than a one-week sector squall. Both legs are z-scored against their own
trailing 252-session distributions so the two horizons are comparable.

The mapping is long-only:

* strong tech leadership (`score >= +0.50`) -> **TQQQ**;
* strong defensive leadership (`score <= -0.50`) -> **BIL**;
* otherwise -> **QQQ**.

QQQ is the neutral asset because the question is whether to add 3x Nasdaq
beta, hold the Nasdaq 1x, or step aside into T-bills. It is not a relative
value trade between QQQ and TQQQ.

## 2. Exact rules

All inputs use daily closes through session `t`. The target is set at the close
of `t` and executed at the first bar open of `t+1`. The shared 2% band applies.

Let `R_t = log(XLK_t) - log(XLU_t)`.

1. `m20_t = R_t - R_{t-20}` and `m60_t = R_t - R_{t-60}`.
2. `z20_t` is the z-score of `m20_t` against its trailing 252 observations
   (minimum 120); `z60_t` is the same for `m60_t`.
3. `score_t = (z20_t + z60_t) / 2`.
4. State:
   * **TQQQ** if `score_t >= +0.50`;
   * **BIL** if `score_t <= -0.50`;
   * **QQQ** otherwise.
5. During the z-score warm-up (score not finite), hold **QQQ**, never TQQQ.
6. Weights are long-only fractions of equity and sum to 1.

## 3. Data, decision clock, and causality

| Item | Choice |
|---|---|
| Signal | XLK and XLU adjusted daily closes from `data/external/` |
| Execution | local 1-minute QQQ/TQQQ/BIL panel via `research/bt.py` |
| Session calendar | QQQ regular sessions; external series reindexed/ffilled |
| Decision | close of session `t` (XLK/XLU close 16:00 ET, same session close) |
| Fill | first bar open of `t+1` |
| Costs | 1 bp headline, 5 bp and 10 bp reported |
| Band | 2% notional |
| Lag | none for XLK/XLU: their official close is stamped at the same 16:00 ET close used for the decision, and the fill is the next open |

The development run uses a panel that ends 2023-12-29. The external loader
reindexes to that panel's sessions, so no 2024-2026 price enters the signal or
the performance. A future-value perturbation audit replaces every XLK/XLU
value after the decision date with garbage and confirms that the target at
that date does not change.

## 4. Why this is not an existing family

* Not `ratio-froth` or `relative-value-tqqq`: there is no TQQQ/QQQ ratio, no
  ratio momentum, and no QQQ moving-average gate.
* Not `qqq-spy-relative`: that family ranks QQQ against SPY. Here the signal
  is a **sector** pair, XLK against XLU, and the position is TQQQ/BIL/QQQ.
* Not `family-beta-rotation`: beta is a covariance object. This family never
  estimates a covariance or an up/down beta; it uses the relative price path
  of two sectors.
* Not a volatility target, drawdown event, calendar clock, opening-range
  signal, or ML model. The XLK/XLU ratio is the primary object, not a filter
  layered on a QQQ price trend.
* The 252-session window is only a standardization lookback for the 20/60-day
  relative return; it is not a 100-250 day price-trend gate.
* The ratio is an external cross-sectional series; QQQ is only the traded
  asset and the neutral state.

## 5. Pre-registered 8-cell sensitivity grid

The grid is deliberately not a single 2 x 2 x 2: it includes the primary, three
threshold neighbours at the 20/60 blend, and the two single-horizon
alternatives at two settings. This exposes whether the blend or one horizon is
doing the work.

| Cell | Windows | TQQQ z | BIL z |
|---:|---|---:|---:|
| **1 (primary)** | **20/60 blend** | **+0.50** | **-0.50** |
| 2 | 20/60 blend | +0.50 | -0.75 |
| 3 | 20/60 blend | +0.75 | -0.50 |
| 4 | 20/60 blend | +0.75 | -0.75 |
| 5 | 20 only | +0.50 | -0.50 |
| 6 | 20 only | +0.75 | -0.75 |
| 7 | 60 only | +0.50 | -0.50 |
| 8 | 60 only | +0.75 | -0.75 |

Fixed: 252-session z-window, 120 minimum observations, QQQ as the neutral
state, BIL as the defensive state. The primary is the centre of the mechanism,
not the best cell in the grid.

## 6. Falsifiers (pre-registered)

The family is killed if any of the following holds on the development window:

1. 1 bp CAGR <= 36.72% or 1 bp max DD >= 82.29% (the published TQQQ bar).
2. 10 bp CAGR <= 36.72% (the edge is a cost artefact).
3. The circular-shift placebo CAGR percentile is below 90%.
4. Daily-return correlation with any current family winner is above 0.95.
5. Fewer than 100 fills or fewer than 30 independent fill events.
6. Any of the three subperiods (2016-2019, 2020-2021, 2022-2023) has a
   negative CAGR.
7. A static book at the strategy's average weights matches the 1 bp CAGR
   within 1 percentage point (the timing adds nothing).
8. The future-value perturbation audit fails on any sampled date, or the
   close-to-next-open mapping audit fails (a causality bug).

The verdict is `dev_pass` only if all eight checks pass. A marginal 1 bp pass
with a 10 bp fail is still a fail: the family is not an above-TQQQ winner.

## 7. Expected effect

| metric | expectation |
|---|---|
| CAGR (1 bp) | 30-42% |
| max DD | 40-55% |
| Sharpe | 0.9-1.2 |
| average TQQQ weight | 0.25-0.35 |
| average QQQ weight | 0.40-0.55 |
| correlation to winners | 0.40-0.70 |

If the result is in these ranges with a positive placebo and a materially
worse static blend, the XLK/XLU object carries information. The main risks are
(a) the 20-day leg is noisy and generates turnover, (b) 2021-2022 sector
leadership whipsawed, and (c) the signal may partly proxy a QQQ momentum
switch. The report states these plainly.
