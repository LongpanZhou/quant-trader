# family-crypto-risk-appetite — hypothesis and pre-registration

**Slug:** `family-crypto-risk-appetite`
**Family:** crypto risk appetite (BTC trend as an external switch)
**Development window:** 2016-01-04 .. 2023-12-29 only. 2024-2026 is not
loaded or inspected by the development run.
**Benchmark bar:** TQQQ 36.72% CAGR / 82.29% max DD / 0.82 Sharpe (published
1-minute-mark bar). TQQQ on this panel is 36.15% / 82.29% / 0.80.

## 1. Mechanism

Bitcoin is a 24/7, high-beta risk asset with a much faster and more
unconditional risk cycle than US equities. Its trend is not a QQQ price trend:
BTC can rally through an equity drawdown, and it can crash while QQQ is flat.
That makes BTC daily momentum a candidate external **risk-appetite** series.

When BTC's 20/60-day trend is positive, global risk appetite is expanding and
a 3x Nasdaq position is better compensated. When BTC's trend is negative,
risk appetite is contracting; the strategy holds T-bills rather than trying to
distinguish an equity-only pullback from a broader de-risking. The strategy
never trades crypto and never holds a crypto position. BTC is a signal series
only.

The primary object is **BTC-USD's 20/60-day price momentum**, not a QQQ moving
average, a volatility estimate, or a calendar clock. The 20-day leg captures
the fast risk pulse; the 60-day leg confirms the trend. Both are z-scored
against their own trailing 252-session distributions.

## 2. Exact rules

All inputs use BTC daily closes through session `t-1`. The target is set at the
close of session `t` and executed at the first bar open of `t+1`. The shared
2% band applies.

Let `b_t = log(BTC_t)`, and let `b_{t-1}` be the BTC close aligned to the prior
QQQ session.

1. `m20_t = b_{t-1} - b_{t-21}` and `m60_t = b_{t-1} - b_{t-61}`.
2. `z20_t` is the z-score of `m20_t` against its trailing 252 sessions
   (minimum 120); `z60_t` is the same for `m60_t`.
3. `score_t = (z20_t + z60_t) / 2`.
4. State:
   * **TQQQ** if `score_t > 0`;
   * **BIL** if `score_t <= 0`;
   * **QQQ** only during the warm-up, when the score is not finite.
5. Weights are long-only fractions of equity and sum to 1.

## 3. Data, decision clock, and causality

| Item | Choice |
|---|---|
| Signal | BTC-USD adjusted daily closes from `data/external/` |
| Execution | local 1-minute QQQ/TQQQ/BIL panel via `research/bt.py` |
| Session calendar | QQQ regular sessions; BTC reindexed/ffilled |
| Decision | close of session `t` |
| BTC lag | **one QQQ session**: the signal at `t` uses BTC closes through `t-1` |
| Fill | first bar open of `t+1` |
| Costs | 1 bp headline, 5 bp and 10 bp reported |
| Band | 2% notional |
| Crypto trading | none |

The one-session lag is not a tuning parameter; it is a timestamp correction.
Yahoo's BTC-USD daily bar for date `d` closes at 00:00 UTC of `d+1`, which is
19:00/20:00 ET on `d` and therefore **after** the 16:00 ET US equity close. At
the close of session `t`, the last completed BTC daily bar is `t-1`. Using the
BTC bar dated `t` at the equity close would be look-ahead. The strategy uses
`t-1` and is therefore causal. A future-value perturbation audit that replaces
every BTC value from session `t` onward with garbage confirms that the target
at `t` does not change.

The development run uses a panel that ends 2023-12-29. The external loader
reindexes to that panel's sessions, so no 2024-2026 price enters the signal or
the performance.

## 4. Why this is not an existing family

* Not a QQQ/TQQQ price trend: the signal is BTC's trend, a different asset
  with a different risk cycle. A same-map QQQ 20/60 momentum control is
  reported alongside the result; it earns materially less and is only
  moderately correlated.
* Not `ratio-froth` or `relative-value-tqqq`: there is no TQQQ/QQQ ratio, no
  ratio momentum, and no QQQ moving-average gate.
* Not `qqq-spy-relative`, `family-sector-rotation`, or `family-breadth`: no
  equity cross-section is used.
* Not a volatility target or a drawdown event: the position is a binary
  risk-on/risk-off state driven by the BTC momentum sign, not by realised
  volatility or a peak-to-trough trigger.
* Not a calendar clock, opening-range signal, or ML model.
* The 252-session window is only a standardization lookback for the 20/60-day
  momentum; it is not a 100-250 day price-trend gate.

## 5. Pre-registered 8-cell sensitivity grid

The grid includes the primary, three threshold neighbours at the 20/60 blend,
and the two single-horizon alternatives at two settings.

| Cell | Windows | TQQQ z | BIL z |
|---:|---|---:|---:|
| **1 (primary)** | **20/60 blend** | **0.00** | **0.00** |
| 2 | 20/60 blend | 0.00 | -0.25 |
| 3 | 20/60 blend | +0.25 | 0.00 |
| 4 | 20/60 blend | +0.25 | -0.25 |
| 5 | 20 only | 0.00 | 0.00 |
| 6 | 20 only | +0.25 | -0.25 |
| 7 | 60 only | 0.00 | 0.00 |
| 8 | 60 only | +0.25 | -0.25 |

Fixed: 252-session z-window, 120 minimum observations, one-session BTC lag,
BIL as the defensive state. The primary is the centre of the mechanism, not
the best cell in the grid. With `tqqq_z = bil_z = 0`, there is no neutral QQQ
state after warm-up: the strategy is a pure risk-on/risk-off switch.

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

The verdict is `dev_pass` only if all eight checks pass.

## 7. Expected effect

| metric | expectation |
|---|---|
| CAGR (1 bp) | 35-55% |
| max DD | 45-60% |
| Sharpe | 1.0-1.4 |
| average TQQQ weight | 0.40-0.55 |
| average BIL weight | 0.35-0.50 |
| correlation to winners | 0.40-0.70 |

If the result is in these ranges with a positive placebo and a materially
worse static blend, the BTC risk-appetite object carries information. The main
risks are (a) BTC-specific crashes that are not equity risk-off, (b) whipsaw
in bear-market rallies, and (c) the fast 20-day leg carrying most of the edge
while the 60-day-only variant is weak. The report states all three.
