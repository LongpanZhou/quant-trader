# Hypothesis: dual-momentum QQQ/SPY gate on a volatility-targeted TQQQ sleeve

**Slug:** `dual-momentum-tqqq`
**Window:** 2016-01-04 -> 2023-12-29 (development only; 2024-2026 never loaded)
**Engine:** `research/bt.py`, 1-minute adjusted QQQ/TQQQ/BIL, SPY daily signal
**Bar:** TQQQ development 36.72% CAGR / 82.29% max DD / 0.82 Sharpe

## 1. Claim

A slow dual-momentum gate on QQQ versus cash and versus SPY, with TQQQ as the
risk-on vehicle sized to an 80-90% volatility target, can beat TQQQ's
development CAGR with a drawdown well below TQQQ's. The economic case is not
that TQQQ can be timed every month; it is that TQQQ's 2021-2022 drawdown
(-81%) dominates its full-window risk, and a 12-month absolute gate plus a
volatility brake removes most of that tail while keeping enough of the
2016-2021 and 2023 upside.

Prior, stated honestly: 12-month momentum is slow at turning points. It will
exit late in 2022 and re-enter late in 2023, and it whipsawed in 2016. The
strategy is expected to trail TQQQ badly in 2019 and to give back part of the
2023 rebound. The test is whether the 2022 avoidance plus the volatility brake
is enough to clear the CAGR bar after those costs.

## 2. Rules (fixed before the 1-minute grid run)

Universe: QQQ, TQQQ, BIL. SPY is a signal only and is never held.

Signals, one value per session, all causal:

- **Absolute momentum:** QQQ 12-month total return, `QQQ[k] / QQQ[k-L] - 1`,
  measured at the 15:59 close of session `k`, with `L` in {126, 189, 252}
  sessions. `> 0` is risk-on.
- **Relative momentum:** QQQ 12-month total return `>` SPY 12-month total
  return, with both legs measured through session `k-1`. SPY's official close
  is 16:00, one minute after the decision bar, so both legs are lagged one
  session to keep the windows aligned and avoid anticipating SPY's close.
- **Volatility:** annualised standard deviation of TQQQ daily total returns
  over the last `rv_n` sessions (10 or 20), measured at the 15:59 close of
  session `k`.

States and target weights:

| Absolute | Relative | Holding |
|---|---|---|
| on | on | TQQQ at `min(1, vol_target / rv)`; remainder BIL |
| on | off | QQQ 1.00 |
| off | don't care | BIL 1.00 |

The volatility size is a continuous overlay: it is recomputed every session
from the prior close and is subject to the same 2% no-trade band as the state.
The momentum state itself changes only under the chosen rebalance rule.

Rebalance rules (the two allowed by the mandate):

- **C20 (primary family):** a new state must persist for 20 consecutive
  sessions before it is accepted ("20-day confirmation"). This is a hysteresis
  filter: it prevents a one-month whipsaw from forcing a trade, at the cost of
  entering and exiting about 20 sessions after the raw signal flips.
- **M:** rebalance at the last session of each calendar month.
- **N20:** rebalance every 20th session of the panel (a fixed-cadence
  alternative; phase is arbitrary and is reported only as a neighbour).

Execution: the target set at session `k`'s close fills at session `k+1`'s
open. Long-only, weights >= 0, sum <= 1. Headline costs 1 bp one-way on traded
notional; 5 bp and 10 bp are reported.

## 3. Pre-registered grid (8 cells)

| ID | Lookback | Vol target | rv window | Rebalance | Role |
|---|---:|---:|---:|---|---|
| **A** | **252** | **0.85** | **10** | **C20** | **primary** |
| B | 252 | 0.80 | 10 | C20 | vol-target neighbour |
| C | 252 | 0.90 | 10 | C20 | vol-target neighbour |
| D | 252 | 0.85 | 20 | C20 | vol-window neighbour |
| E | 252 | 0.85 | 10 | M | monthly alternative |
| F | 189 | 0.85 | 10 | C20 | lookback neighbour |
| G | 126 | 0.85 | 10 | C20 | lookback neighbour |
| H | 252 | 0.85 | 10 | N20 | 20-session cadence |

A is the canonical 12-month / mid-band / confirmation cell. The grid is a
plateau probe: no cell is substituted for A after the run.

## 4. Falsifiers (fixed before the grid run)

The strategy is reported as a pass only if A has:

1. dev 1 bp CAGR > 36.72%;
2. dev 1 bp max drawdown < 60% (the hard bar is 82.29%);
3. all three vol-target cells A/B/C clear both bars (the mandate's 80-90%
   band is the primary robustness dimension).

Secondary diagnostics, reported but not used to promote A:

- at least 3 of 8 grid cells clear both bars;
- 10 bp CAGR still above 36.72%;
- placebo (circular shift of the target sequence, 200 draws) has at most 10%
  of draws at or above A's CAGR;
- pre-cut weight reproduction at 2020-03-12 11:07 and 2022-09-13 10:41 is
  exact;
- leave-one-year-out CAGR above 36.72% in at least 5 of 7 folds.

## 5. What would make this a negative result

- A's CAGR below 36.72%, even if the drawdown is excellent.
- A passes only because of one year, or only at 1 bp.
- The vol-target band does not form a plateau (for example A passes but B and
  C fail).
- The placebo distribution shows the result is indistinguishable from a
  random reordering of the same exposure path.

## 6. Disclosures

- The design was developed with daily-bar diagnostics on the same 2016-2023
  window. The 1-minute grid was frozen after those diagnostics; the primary
  cell was sanity-checked once at 1 bp before the full grid and was not
  changed afterwards.
- The 20-session confirmation and the 10-session volatility window are the
  two choices most likely to be doing the work. The report shows neighbours
  at 10/15/20/30-session confirmation, 5/10/15/20/30/60-session volatility,
  and 126/189/210/252/294-session lookbacks to expose how narrow the plateau
  is.
- 2016-2019 and 2022 are reported year by year, not hidden inside the CAGR.
- The 2024-2026 holdout is physically excluded from every Parquet read and
  from the panel slice.
