> **Post-test note (2026-11-27):** this file is the pre-registration, not
> the result. The frozen development result is in `../SUMMARY.md`; the
> full 2016-2026 audit, the post-tune variants and the research-validity
> verdicts are in `../WHY_UNDERPERFORM.md`. The published website curve is
> the freeze named in `../SUMMARY.md`.

# `ratio-pairs` rebuild — leverage-cycle allocation

**Status:** pre-registered hypothesis + code; **not tested**. Backtests are paused
(2026-11-26). No `result.json` is written and the holdout has not been touched.
**Dev window:** 2016-01-04 .. 2023-12-29. **Original:** `research/agents2/ratio-pairs`.

---

## 1. Extracted idea

The original strategy was the round-1 winner plus an overlay. The new part was:

> The TQQQ/QQQ ratio is a leverage-cycle meter. `log(TQQQ/QQQ) = 2·log(QQQ) −
> 3·realised variance`, so a ratio far above its own trend is a low-volatility
> melt-up in which leveraged exposure compounded without paying drag; the next
> shock is amplified.

The original used that signal only to downgrade TQQQ to QQQ inside a QQQ
165-day trend position. That is the part this rebuild replaces.

## 2. Why the naive strip is not enough

Measured on the development window before the pause (exploratory, single run,
not audited; 1-minute marks, 1 bp):

| Rule (no 165-day gate) | CAGR | max DD | Sharpe | corr vs 165d base |
|---|---:|---:|---:|---:|
| 165-day baseline | 44.76% | 58.76% | 1.02 | 1.00 |
| QQQ buy & hold | 18.91% | 37.30% | 0.90 | 0.71 |
| TQQQ buy & hold | 36.15% | 82.29% | 0.80 | 0.71 |
| QQQ; `ext200>0.18` → BIL | 20.57% | 36.37% | 1.02 | 0.55 |
| QQQ; `ext200>0.20` → BIL; `ext200<−0.30` → 25% TQQQ kicker | 23.17% | 41.15% | 0.98 | 0.49 |
| 3-state `ext200` 0.18 / −0.25 → TQQQ / QQQ / BIL | 21.28% | 57.48% | 0.69 | 0.28 |
| TQQQ only when `ext200 < −0.25` and rising 5d, else BIL | −0.53% | 42.30% | 0.07 | 0.00 |

Three lessons:

1. A literal "remove the base" rebuild is a QQQ clone: the ratio adds ~1.7 pp
   of CAGR and no drawdown reduction versus QQQ.
2. Defaulting to TQQQ in the cheap tail is dangerous — the 3-state rule holds
   TQQQ through 2022 and draws down 57%.
3. A pure cheap-leverage entry has no standalone edge without a risk filter.

So the rebuild changes the **default asset**, the **number of states**, the
**sizing** and the **risk control**, not just the gate.

## 3. Hypothesis

The ratio is an oscillator with two actionable tails and an unremarkable
middle:

- **Froth** (ratio far above its own 200-session trend): expected TQQQ returns
  are poor and left-tail risk is high → hold **cash**.
- **Capitulation** (ratio far below trend and turning up): the variance spike
  has been paid; a 3x rebound is convex → hold a **bounded 40% TQQQ sleeve**.
- **Middle**: 3x drag is not compensated at this horizon → hold **QQQ**, not
  TQQQ.

A second, ratio-only state variable measures whether variance is expanding:

```
dv_t     = 3·log(QQQ_t/QQQ_{t−1}) − log(TQQQ_t/TQQQ_{t−1})   ≈ 3·r_t²  ≥ 0
stress_t = mean(dv, 20) / mean(dv, 60)
```

`dv` is the exact daily shortfall of TQQQ against a 3x QQQ log return. A
`stress` reading above 1.75 means the variance regime is expanding faster than
its own base rate: stand aside regardless of the ratio level.

This is **not** a price-trend gate. There is no QQQ/TQQQ/SPY/NDX moving average
in the strategy. The only moving average is the ratio's own 200-session
detrending mean, used as a cycle reference for the spread.

## 4. Universe and data

- **QQQ** — core holding (unleveraged Nasdaq-100 exposure).
- **TQQQ** — bounded satellite, maximum 40% of the book, only in the
  capitulation state.
- **BIL** — defensive asset; 100% in froth/variance shocks, 10% in the core
  state, 30% alongside the TQQQ sleeve.
- **SPY daily** — benchmark only. There is no SPY intraday history for the
  development window, so SPY cannot be a tradable asset here.

Local data limits: only QQQ/TQQQ/BIL have adjusted 1-minute history
(`data/intraday-hf/`). No sector, bond, gold or volatility-product intraday
data exists locally; the Dukascopy SPY cache covers only 2026-08-31..2026-11-20.
The rebuild is therefore role-diversified (core/satellite/cash), not
symbol-diversified. No new data was fetched.

## 5. Rules (exact)

All signals use the prior session's close and are applied from the next
session's first bar. The harness fills at the next bar's open (09:31) with a 2%
band.

```
R_k    = TQQQ_close_k / QQQ_close_k
x_k    = log(R_k)
ext_k  = x_k − mean(x_{k−199..k})
dv_k   = max(0, 3·log(QQQ_k/QQQ_{k−1}) − log(TQQQ_k/TQQQ_{k−1}))
v20_k  = mean(dv_{k−19..k})
v60_k  = mean(dv_{k−59..k})
stress_k = v20_k / v60_k
turn_k   = ext_k − ext_{k−20}
```

Target for session `k+1`, evaluated in order:

1. `ext_k > 0.20` **or** `stress_k > 1.75` → **BIL 100%**
2. `ext_k < −0.30` **and** `turn_k > 0` → **TQQQ 40%, QQQ 30%, BIL 30%**
3. otherwise → **QQQ 90%, BIL 10%**

Long only, gross ≤ 1, no shorting, no intraday stop, no reused base weights.
`build_weights(ts, opens, closes, params)` returns the `(n, 3)` matrix and an
info dict; `main()` runs the dev windows and writes `result.json` when the lead
authorises the test.

## 6. Parameters and overfitting plan

| parameter | value | ±1 step |
|---|---:|---|
| `ext_ma` | 200 | 150, 250 |
| `froth` | 0.20 | 0.17, 0.23 |
| `deep` | −0.30 | −0.27, −0.33 |
| `stress_hi` | 1.75 | 1.50, 2.00 |
| `turn_look` | 20 | 10, 30 |
| `tqqq_deep` | 0.40 | 0.30, 0.50 |
| core QQQ/cash | 90/10 | 100/0, 80/20 |

Values are round numbers anchored to the exploratory dev buckets
(`ext200 > 0.25` → −4.7% forward 20-day TQQQ; `< −0.30` → +8.2%; `0..0.15` →
+7.4%; `−0.30..−0.15` → −2.8%). They were **not** fitted on the holdout.

Planned controls, all to be reported after the run:

1. **Variants tried:** the 7-parameter neighbourhood (3×3×3 for the three main
   thresholds, plus the sizing steps) and the ablations below; count them.
2. **Plateau:** the chosen point must sit inside a region of the same sign, not
   a single cell.
3. **Sub-periods:** 2016–19, 2020–21, 2022–23.
4. **Ablations:** (a) always QQQ 90/BIL 10; (b) no TQQQ sleeve; (c) no stress
   rule; (d) froth → QQQ instead of BIL.
5. **Placebo:** random BIL days with the same per-year count as the real
   risk-off state; 1,000 draws. Report the share with CAGR ≥ the real rule.
6. **Event count:** the capitulation state is expected to be rare; if it has
   fewer than 100 sessions, report the count and a bootstrap p-value on the
   sleeve's contribution.

## 7. Results

**Not run.** Backtests are paused until the lead authorises them. This section
will be replaced by the audited dev table (1/5/10 bp, minute marks), the
neighbourhood, the sub-periods and the ablations. Nothing here is a result.

Placeholders to fill:

- dev 1/5/10 bp CAGR, max DD, Sharpe, fills, turnover;
- 2016–19 / 2020–21 / 2022–23;
- ablation table;
- placebo distribution;
- `corr_vs_165d_baseline` and `max_corr_vs_other_rebuilds`.

## 8. Correlation

Target: **< 0.60** daily-return correlation with the 165-day baseline on dev.
Expected range from the exploratory QQQ/froth and QQQ/froth/kicker runs:
**0.45–0.58**. The mechanism is that the strategy is in cash (or 70% cash) on
the froth and variance-shock sessions when the baseline is long TQQQ, and holds
QQQ rather than TQQQ on the core sessions.

No correlation is claimed until it is measured on the frozen code.

## 9. Falsifiers and decision rule

The rebuild is **rejected** if any of these hold on dev:

1. correlation with the 165-day baseline ≥ 0.60;
2. Sharpe ≤ QQQ buy-and-hold (0.90);
3. always-QQQ-90/BIL-10 beats the full rule on Sharpe or drawdown;
4. the placebo distribution's median CAGR ≥ the real rule's;
5. the ±1-step neighbourhood flips the sign of the edge;
6. the 2022–23 drawdown exceeds QQQ's 37%;
7. the capitulation sleeve has < 10 entries or loses money in aggregate.

If (1) holds the strategy is **retired_overlay_only**. If any other gate fails
the design is **rejected** and the report says which gate.

## 10. Provenance

See `PROVENANCE.md`. The core identity is Avellaneda & Zhang (2010); the
volatility-paradox mechanism is Brunnermeier & Sannikov (2014); the drag
arithmetic is from Cheng & Madhavan (2009) and the Adjusted Close empirical
decomposition; the variance-state risk control is informed by Moreira & Muir
(2017) with the Cederburg et al. (2020) counter-evidence explicitly noted.

## 11. Next steps

1. Lead authorises the dev test; run `strategy.py` (not before).
2. Fill section 7 and freeze with a commit hash.
3. Independent audit: look-ahead cuts at 2020-03-12 11:07 and 2022-09-13
   10:41, spec-vs-code, reproduction, harness, correlations.
4. Lead runs the holdout once and fills `windows.holdout`, `windows.10y`,
   `windows.5y`.
