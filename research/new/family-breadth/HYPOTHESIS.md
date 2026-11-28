# family-breadth — hypothesis and pre-registration

**Slug:** `family-breadth`
**Family:** breadth (equal-weight vs cap-weight)
**Development window:** 2016-01-04 .. 2023-12-29 only. 2024-2026 is not
loaded or inspected by the development run.
**Benchmark bar:** TQQQ 36.72% CAGR / 82.29% max DD / 0.82 Sharpe (published
1-minute-mark bar). TQQQ on this panel is 36.15% / 82.29% / 0.80.

## 1. Mechanism

An index can rise while most of its constituents do not. The RSP/SPY ratio
measures that distinction directly: RSP is the equal-weight S&P 500, SPY is
the cap-weight S&P 500. When RSP keeps up with or beats SPY, the rally is
broad and the marginal stock is participating. When SPY pulls away from RSP,
the index is being carried by a small number of mega-caps and breadth is
narrowing.

Broad breadth is a risk-appetite state: more stocks are trending, drawdowns
are absorbed by rotation rather than by index-level de-risking, and a 3x
Nasdaq wrapper is better compensated. Narrow breadth is a fragile state: the
index can look strong while the median stock is weak, and the eventual
unwind is often index-level. The strategy therefore holds TQQQ when breadth is
broad, QQQ in the neutral band, and BIL when narrowing is severe.

The primary object is the **RSP/SPY relative return**, not the QQQ price trend
and not the QQQ/SPY relative-strength ratio used by the existing
`qqq-spy-relative` family. The 20-day leg captures a fresh rotation; the
60-day leg confirms a breadth regime. Both are z-scored against their own
trailing 252-session distributions.

## 2. Exact rules

All inputs use daily closes through session `t`. The target is set at the close
of `t` and executed at the first bar open of `t+1`. The shared 2% band applies.

Let `R_t = log(RSP_t) - log(SPY_t)`.

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
| Signal | RSP and SPY adjusted daily closes from `data/external/` |
| Execution | local 1-minute QQQ/TQQQ/BIL panel via `research/bt.py` |
| Session calendar | QQQ regular sessions; external series reindexed/ffilled |
| Decision | close of session `t` (RSP/SPY close 16:00 ET, same session close) |
| Fill | first bar open of `t+1` |
| Costs | 1 bp headline, 5 bp and 10 bp reported |
| Band | 2% notional |
| Lag | none for RSP/SPY: their official close is stamped at the same 16:00 ET close used for the decision, and the fill is the next open |

The development run uses a panel that ends 2023-12-29. The external loader
reindexes to that panel's sessions, so no 2024-2026 price enters the signal or
the performance. A future-value perturbation audit replaces every RSP/SPY
value after the decision date with garbage and confirms that the target at
that date does not change.

## 4. Why this is not an existing family

* Not `qqq-spy-relative`: that family uses QQQ vs SPY, a Nasdaq-vs-broad
  relative-strength ratio. Here the pair is RSP vs SPY, equal-weight vs
  cap-weight, which measures **breadth**, not Nasdaq leadership.
* Not `ratio-froth` or `relative-value-tqqq`: there is no TQQQ/QQQ ratio, no
  ratio momentum, and no QQQ moving-average gate.
* Not `family-sector-rotation`: that family uses XLK/XLU (growth vs
  defensive); this one uses RSP/SPY (equal-weight vs cap-weight).
* Not `family-beta-rotation`: no covariance or beta is estimated.
* Not a volatility target, drawdown event, calendar clock, opening-range
  signal, or ML model. The RSP/SPY ratio is the primary object, not a filter
  layered on a QQQ price trend.
* The 252-session window is only a standardization lookback for the 20/60-day
  relative return; it is not a 100-250 day price-trend gate.
* The ratio is an external cross-sectional series; QQQ is only the traded
  asset and the neutral state.

## 5. Pre-registered 8-cell sensitivity grid

The grid includes the primary, three threshold neighbours at the 20/60 blend,
and the two single-horizon alternatives at two settings.

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
| CAGR (1 bp) | 30-40% |
| max DD | 50-70% |
| Sharpe | 0.9-1.1 |
| average TQQQ weight | 0.20-0.30 |
| average QQQ weight | 0.35-0.50 |
| correlation to winners | 0.40-0.65 |

If the result is in these ranges with a positive placebo and a materially
worse static blend, the RSP/SPY object carries information. The main risk is
regime asymmetry: narrow breadth can persist for a long time in a mega-cap
rally (notably 2023), so the defensive state can be early and expensive. The
report states whether that risk materialised.
