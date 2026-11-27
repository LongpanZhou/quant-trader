# Hypothesis — `ratio-pairs` rebuild: leverage-cycle allocation

**Status:** pre-registered, awaiting the lead's test authorization.
**Written:** 2026-11-26. **Dev window only:** 2016-01-04 .. 2023-12-29.
**No holdout data was loaded or inspected.**

---

## 1. What is actually new in the original

The original `ratio-pairs` strategy was the round-1 winner plus one overlay:

> hold 100% TQQQ while QQQ's prior close is above its 165-day SMA, else BIL;
> inside the risk-on days, if `log(TQQQ/QQQ / its 200-day MA)` > 0.18, hold QQQ instead of TQQQ.

The genuinely new part is **not** the trend gate. It is the claim that the
**TQQQ/QQQ ratio is a leverage-cycle meter**:

> `log(TQQQ/QQQ) = 2·log(QQQ) − 3·realised variance + financing/tracking noise`

so the ratio's position relative to its own trend separates *how far the market
has run* from *how little volatility it took to get there*. A ratio far above
its trend is a low-volatility melt-up in which leveraged exposure compounded
without paying drag; the next shock is amplified.

The original only used this idea to downgrade TQQQ to QQQ inside an existing
TQQQ trend position. In the development sample that overlay (a) fired on 25% of
sessions and (b) was worth about +1.7 pp of CAGR over simply holding QQQ, with
a similar drawdown. It was a filter on the old base more than a strategy.

## 2. Why the naive strip fails (measured before the pause)

These numbers were produced with `explore.py`/`explore2.py` before the
2026-11-26 test pause. They are exploratory, single-run, and not audited; they
are recorded here so the new design is not a blind guess.

Development window, 1-minute marks, 1 bp:

| Rule (no 165-day gate) | CAGR | max DD | Sharpe | corr vs 165d base |
|---|---:|---:|---:|---:|
| 165-day baseline | 44.76% | 58.76% | 1.02 | 1.00 |
| QQQ buy & hold | 18.91% | 37.30% | 0.90 | 0.71 |
| TQQQ buy & hold | 36.15% | 82.29% | 0.80 | 0.71 |
| QQQ; `ext200>0.18` → BIL | 20.57% | 36.37% | 1.02 | 0.55 |
| QQQ; `ext200>0.20` → BIL; `ext200<−0.30` → 25% TQQQ kicker | 23.17% | 41.15% | 0.98 | 0.49 |
| 3-state `ext200` 0.18 / −0.25 → TQQQ / QQQ / BIL | 21.28% | 57.48% | 0.69 | 0.28 |
| TQQQ only when `ext200 < −0.25` and rising 5d, else BIL | −0.53% | 42.30% | 0.07 | 0.00 |

What this says:

1. **The literal strip is a QQQ clone.** Always-invested `ext200` allocation
   gives a 0.55 correlation but only QQQ-like returns; the ratio's timing adds
   ~1.7 pp of CAGR and no drawdown reduction versus QQQ.
2. **Defaulting to TQQQ at the cheap tail is dangerous.** The 3-state rule
   spends 2022 in TQQQ and produces a 57% drawdown.
3. **A pure cheap-leverage entry has no standalone edge.** Buying after a ratio
   decline without a risk filter is flat-to-negative.
4. Therefore a genuine rebuild needs a **different default asset, bounded
   leverage, and an explicit variance/crash state** — not a relabelled version
   of "TQQQ unless the ratio says otherwise".

## 3. The standalone hypothesis

**Thesis.** The leverage ratio is a cycle oscillator, not a trend signal. The
strategy should be **unleveraged by default** and pay for 3x leverage only in
the two states where the leverage cycle is favourable:

- **Froth (ratio far above its own trend):** the melt-up has been financed by
  low realised variance and crowded leverage; expected TQQQ returns are poor
  and left-tail risk is high. Hold **cash**, not QQQ and not TQQQ.
- **Capitulation (ratio far below its trend, ratio turning up):** the
  variance spike has already been paid; the rebound in a 3x fund is convex.
  Hold a **bounded TQQQ sleeve** (40%), with QQQ and cash.
- **Everything else:** hold **QQQ**, not TQQQ. At the average state of the
  cycle, 3x drag is not compensated; QQQ is the core asset.

The second state variable is the **ratio-implied variance drag**, which is
computable from the pair alone:

```
dv_t = 3·log(QQQ_t/QQQ_{t−1}) − log(TQQQ_t/TQQQ_{t−1})   ≈ 3·r_t²  ≥ 0
```

`dv` is the exact daily shortfall of TQQQ against a 3x QQQ log return. Its
20-day mean divided by its 60-day mean is a variance-cycle state. A reading
above 1.75 means the variance regime is expanding faster than its own base
rate: stand aside regardless of the ratio level.

This is deliberately **not** a price-trend gate. There is no QQQ/TQQQ/SPY/NDX
moving average anywhere. The only moving average is the ratio's own 200-day
detrending mean, used as a cycle reference for the spread, not as a market
gate.

## 4. Universe, holding period, sizing, risk

- **Universe:** QQQ (core), TQQQ (bounded satellite), BIL (defensive). SPY
  daily is used only for the benchmark; there is no SPY intraday history for
  the development window, so it cannot be a tradable asset here.
- **Holding period:** state-based, decided at each session close and held for
  as long as the state persists — typically weeks. The 2% band suppresses
  small resizes. Expected turnover is far below the original's 91 fills/year.
- **Sizing:** QQQ 90% / BIL 10% default; froth or variance shock → BIL 100%;
  capitulation → TQQQ 40% / QQQ 30% / BIL 30%. TQQQ is never more than 40% of
  the book.
- **Risk:** two kill switches (froth level, variance expansion), a maximum 40%
  TQQQ sleeve, no shorting, no intraday stop, gross exposure always ≤ 1.

## 5. Exact rules (pre-registered)

All signals use the prior session's close and are applied from the next
session's first bar (the harness fills at 09:31).

```
R_k    = TQQQ_close_k / QQQ_close_k
x_k    = log(R_k)
ext_k  = x_k − mean(x_{k−199..k})            # 200-session ratio detrend
dv_k   = max(0, 3·log(QQQ_k/QQQ_{k−1}) − log(TQQQ_k/TQQQ_{k−1}))
v20_k  = mean(dv_{k−19..k})
v60_k  = mean(dv_{k−59..k})
stress_k = v20_k / v60_k
turn_k   = ext_k − ext_{k−20}
```

Target for session `k+1`, in order:

1. `ext_k > 0.20` **or** `stress_k > 1.75` → **BIL 100%**
2. `ext_k < −0.30` **and** `turn_k > 0` → **TQQQ 40%, QQQ 30%, BIL 30%**
3. otherwise → **QQQ 90%, BIL 10%**

Parameters (chosen from round numbers and the exploratory plateau, not fitted):

| parameter | value | ±1 step neighbourhood |
|---|---:|---|
| `ext_ma` | 200 | 150, 250 |
| `froth` | 0.20 | 0.17, 0.23 |
| `deep` | −0.30 | −0.27, −0.33 |
| `stress_hi` | 1.75 | 1.50, 2.00 |
| `turn_look` | 20 | 10, 30 |
| `tqqq_deep` | 0.40 | 0.30, 0.50 |
| core QQQ/cash | 90/10 | 100/0, 80/20 |

## 6. What is expected

- Development CAGR **15–21%**, max DD **26–33%**, Sharpe **1.0–1.15**.
- Correlation with the 165-day baseline **0.45–0.58** (the hard limit is 0.60).
- The strategy should **not** beat the 165-day baseline on CAGR; the point is a
  different return driver and a materially lower drawdown, not a higher
  headline return. It should beat QQQ on Sharpe (QQQ's dev Sharpe is 0.90) or
  the rebuild has failed its own test.
- Most of the value should come from (a) cash in froth and variance shocks and
  (b) the bounded capitulation sleeve. The QQQ core is expected to supply the
  bulk of the return.

These are expectations, not results. If the realized numbers are outside these
bands the design is wrong; the report will say so.

## 7. Falsifiers (what would prove the idea wrong)

1. **Correlation ≥ 0.60** with the 165-day baseline on the development period
   → fails the hard rule; retire or change direction.
2. **Sharpe ≤ QQQ buy-and-hold (0.90)** → the ratio adds nothing risk-adjusted;
   mark `retired_overlay_only`.
3. **Always-QQQ-80/BIL-20 beats the full rule** on Sharpe or drawdown → the
   ratio states are noise; retire.
4. **Placebo control:** random BIL days with the same per-year count produce a
   CAGR ≥ the real rule (re-run under audit) → timing is luck.
5. **Neighbourhood sign flip:** the edge disappears at `froth` 0.17/0.23 or
   `deep` −0.27/−0.33 → overfit to one threshold.
6. **2022–23 sub-period drawdown > QQQ's 37%** → the risk control fails where
   it matters most.
7. **The capitulation sleeve loses money in aggregate over dev** (or has fewer
   than 10 entries) → drop it; the idea reduces to the froth/cash rule.

## 8. Test plan (for the lead, when authorized)

1. Run `strategy.py` on the dev panel (2016-01-04..2023-12-29) at 1/5/10 bp
   with 1-minute marks and a 2% band.
2. Produce the 165-day baseline on the same panel and compute the daily-return
   correlation.
3. Run the ±1-step neighbourhood, the three sub-periods (2016–19, 2020–21,
   2022–23), the always-QQQ control, the no-kicker ablation, and the placebo.
4. Freeze, audit, then the lead runs the holdout once and fills
   `windows.holdout`, `windows.10y`, `windows.5y`.

## 9. Data and constraints

- QQQ/TQQQ/BIL 1-minute, adjusted, `data/intraday-hf/` via `research/bt.py`.
- SPY daily only, `data/round3/yahoo/SPY-1d-yahoo.parquet`, benchmark-only.
- No sector, bond, gold or volatility-product intraday history exists locally;
  the Dukascopy SPY cache covers only 2026-08-31..2026-11-20. The universe is
  therefore role-differentiated rather than symbol-diversified.
- No shorting: `bt.simulate` rejects negative weights.
