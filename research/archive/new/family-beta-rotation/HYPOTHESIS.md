# family-beta-rotation — hypothesis and pre-registration

**Slug:** `family-beta-rotation`
**Family:** beta rotation
**Development window:** 2016-01-04 .. 2023-12-29 only. 2024-2026 is not loaded
or inspected by the development run.
**Benchmark bar:** TQQQ 36.72% CAGR / 82.29% max DD / 0.82 Sharpe (published
1-minute-mark bar). TQQQ on this panel is 35.81% / 82.30% / 0.80.

## 1. Mechanism

TQQQ is a constant 3x wrapper on QQQ, but QQQ's sensitivity to the equity
market is not constant. The rolling QQQ-vs-SPY beta measures how much of QQQ's
move is broad-market beta rather than a Nasdaq-specific trend:

* **Beta compression** (beta low in its own one-year range) means QQQ is moving
  on a low-stress, relatively idiosyncratic trend. A 3x daily-reset wrapper
  compounds well when the underlying path is smooth and the market factor is
  not dominating: there are fewer high-correlation gap-down days and the 3x
  reset is paid for by the trend rather than by two-sided variance.
* **Beta expansion** means the market factor is taking over. In that state QQQ
  and TQQQ drawdowns become market-wide and correlated; the 3x wrapper is
  dangerous even if the Nasdaq trend still looks intact.
* **Upside/downside beta asymmetry** separates a healthy high-beta tape from a
  stressed one. `beta_up - beta_down` is high when QQQ captures more of SPY's
  up moves than its down moves. Very high asymmetry is not a buy signal: the
  leverage has already been paid for, and forward TQQQ returns are weaker.

The primary object is the beta vector (level percentile plus up/down
asymmetry), not relative-strength momentum, a moving-average trend gate, or a
volatility target.

## 2. Exact rules

All inputs use daily closes through session `t`. The target is set at the close
of `t` and executed at the first bar open of `t+1` (the shared 2% band applies).

Let `r_Q` and `r_S` be daily log returns of QQQ and SPY.

1. `beta_42` and `beta_63` are rolling OLS betas of `r_Q` on `r_S` over 42 and
   63 sessions. `beta = (beta_42 + beta_63) / 2`.
2. `pct` is the fraction of the prior **252** `beta` observations (excluding
   the current one) that are below today's `beta`. Missing warm-up values
   default to 0.5.
3. `beta_up` / `beta_down` are OLS betas over the prior **126** sessions using
   only SPY-up days and only SPY-down days. `asym = beta_up - beta_down`.
4. State:
   * **TQQQ** if `pct < 0.60` **and** `asym < 0.00`;
   * **QQQ** if `pct < 0.80` **or** `asym < 0.15` (and the TQQQ condition did
     not fire);
   * **BIL** otherwise.

The state is held through the next session. Weights are long-only, sum to 1,
and are fractions of equity.

## 3. Estimation window and decision clock

| Item | Choice |
|---|---|
| Beta windows | 42 and 63 sessions, averaged |
| Beta percentile window | 252 sessions, current observation excluded |
| Up/down beta window | 126 sessions |
| Data | local adjusted 1-minute QQQ/TQQQ/BIL panel via `research/bt.py`; local SPY daily adjusted closes for the beta regressor |
| Decision | close of session `t` |
| Fill | first bar open of `t+1` |
| Costs | 1 bp headline, 5 bp and 10 bp reported |
| Band | 2% notional |

SPY is read from `data/round3/yahoo/SPY-1d-yahoo.parquet` and filtered to the
requested panel's last date before any use. During the development run that
drops every 2024-2026 row before it is inspected.

## 4. Why this is not an existing family

* Not `ratio-froth` / `relative-value-tqqq`: there is no TQQQ/QQQ ratio, no
  ratio momentum and no QQQ moving-average trend gate.
* Not `qqq-spy-relative`: that family uses relative strength of QQQ versus SPY.
  Here the object is the *covariance* (beta) and its up/down asymmetry; the
  strategy never ranks QQQ and SPY returns against each other.
* Not a volatility target: no position is sized by `target_vol / realised_vol`.
  The state is driven by the beta percentile and the asymmetry sign.

## 5. Pre-registered 8-cell grid

The grid is 2 x 2 x 2: beta estimate (blend 42/63 vs single 63), compression
threshold (0.50 vs 0.60), asymmetry threshold (0.00 vs 0.05). Fixed:
`pct_qqq = 0.80`, `asym_qqq = 0.15`.

The primary cell is the blend with `pct_tqqq = 0.60` and `asym_tqqq = 0.00`.
It is the centre of the mechanism, not the best cell in the grid.

## 6. Falsifiers (pre-registered)

The family is killed if any of the following holds on the development window:

1. 1 bp CAGR <= 36.72% or max DD >= 82.29% (the published TQQQ bar).
2. 10 bp CAGR <= 36.72% (the edge is a cost artefact).
3. The circular-shift placebo CAGR percentile is below 90%.
4. Daily-return correlation with any current family winner is above 0.95.
5. Fewer than 100 fills or fewer than 30 independent fill events.
6. Any of the three subperiods (2016-2019, 2020-2021, 2022-2023) has a
   negative CAGR.
7. A static book at the strategy's average weights matches the 1 bp CAGR
   within 1 percentage point (then the timing adds nothing).

## 7. Expected effect

| metric | expectation |
|---|---|
| CAGR (1 bp) | 38-45% |
| max DD | 45-55% |
| Sharpe | 1.0-1.2 |
| average TQQQ weight | 0.25-0.35 |
| correlation to winners | 0.55-0.80 |

If the result is in these ranges with a positive placebo and a materially
worse static blend, the beta object carries information. The report states the
2022 loss and the fast-beta sensitivity plainly.
