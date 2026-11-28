# Autocorrelation regime — `family-autocorrelation-regime`

**Family:** time-varying short-horizon serial dependence. The primary signal is
a rolling lag-1 autocorrelation of QQQ daily returns. It is not a moving
average, volatility level, drawdown state, calendar window, opening-range
signal, relative-strength signal or ML classifier.

**Window:** 2016-01-04 → 2023-12-29, development only. The 2024-2026 holdout is
never loaded or inspected. Pre-2016 daily closes (2015) are used only to warm
up the autocorrelation estimate; no 2024+ value enters any signal or weight.

**Status of this file:** written after exploratory development-window
diagnostics and **before the final reported 1-minute run**. The mechanism,
primary and 12-cell grid below are fixed at this point. The exploratory work
included daily-return approximations and a coarse first 1-minute pass on the
same development window, so this is a **dev-window pre-registration, not a
blind one**. The prior exposure is disclosed in §6.

---

## 1. Mechanism

Daily equity returns are not independently distributed. Their lag-1
autocorrelation is itself time-varying: it clusters in negative territory when
the market is choppy and dealer inventories are being recycled, and it can be
positive when a trend is being fed by persistent flow. If that variation is
real and measurable in real time, it should tell us which of two very
different short-horizon payoffs is currently available:

- **Positive autocorrelation → continuation.** An up day is more likely to be
  followed by another up day. Hold TQQQ while the positive regime lasts.
- **Negative autocorrelation → reversal.** A down day is more likely to be
  retraced. Buy TQQQ after the down day and hold the retracement.
- **Near-zero autocorrelation → no edge.** Sit in BIL rather than pay 3x
  daily-reset decay for a coin flip.

The economic channel is flow persistence versus flow absorption: the same
3x product that is a great instrument in a persistent tape is a terrible one
in a mean-reverting tape because its daily reset bleeds in both directions.
The autocorrelation estimate is the switch between those two states. TQQQ is
the instrument because the reversal/continuation move is leveraged; BIL is the
neutral asset because the strategy is long-only and cannot fade up days.

The **known failure mode** is a falling knife: in a crash, every down day
triggers the reversal leg, the sleeve stays fully invested, and the 3x fund
compounds down. The 2020 drawdown in the report is the honest measure of that
risk. No stop, no trend gate and no volatility target is part of the primary.

---

## 2. Exact rules and decision clock

All inputs are known at the **15:59 ET close of session d**. The target is
written on that close and fills at the **09:30 ET open of session d+1**.

```
qret[d]  = QQQ_close[d] / QQQ_close[d-1] - 1          (close-to-close)
rho[d]   = corr(qret[d-L+1..d-1], qret[d-L+2..d])      (rolling lag-1)
cont[d]  = rho[d] >= theta_cont
rev[d]   = rho[d] <= -theta_rev  AND  qret[d] < 0
held[d]  = rev[d] OR rev[d-1] OR ... OR rev[d-hold+1]

target[d+1] = TQQQ weight 1.0   if cont[d] or held[d]
            = BIL  weight 1.0   otherwise
```

- The `held` term is a rolling hold: every reversal signal keeps the sleeve in
  TQQQ for `hold` sessions; a new signal during the hold extends it. This is
  the only state machine in the strategy and it is causal.
- The confidence thresholds `theta_cont` and `theta_rev` are the anti-churn
  device. They are fixed constants, not percentile ranks or full-sample
  normalisations.
- No trade is taken in the first `L+1` sessions of available history. The
  warmup uses 2015 QQQ daily closes from the local Yahoo daily parquet, then
  the 1-minute panel's 15:59 closes from 2016-01-04. The two series are on the
  same adjusted scale (the 1-minute loader applies the same daily factor).
- Execution: `research/bt.py`, 1-minute marks, next-open fills, 2% band,
  long-only, weights ≥ 0, row sum ≤ 1. Headline 1 bp; 5 bp and 10 bp reported.
  Flat is BIL, not cash, so the idle sleeve earns the T-bill return.

**Primary:** `L=120`, `lag=1`, `theta_cont=0.03`, `theta_rev=0.05`,
`hold=3`, daily decision clock. The primary is the centre of the grid
(L=120 is the middle window; 0.03 is the middle positive threshold; hold=3 is
the middle hold), not a boundary cell.

---

## 3. Pre-registered grid (12 cells)

The grid varies one dimension at a time around the primary. It is deliberately
small enough to report every cell.

| # | L | theta_cont | theta_rev | hold | role |
|---:|---:|---:|---:|---:|---|
| 1 | 120 | 0.00 | 0.05 | 3 | weak positive state |
| 2 | 120 | 0.03 | 0.05 | 3 | **primary** |
| 3 | 120 | 0.05 | 0.05 | 3 | strong positive state |
| 4 | 120 | 0.03 | 0.10 | 3 | stronger reversal gate |
| 5 | 120 | 0.03 | 0.15 | 3 | strong reversal gate |
| 6 | 120 | 0.00 | 0.10 | 3 | weak cont, strong rev |
| 7 | 120 | 0.05 | 0.10 | 3 | strong cont, strong rev |
| 8 | 120 | 0.00 | 0.15 | 3 | weak cont, deepest rev |
| 9 | 120 | 0.05 | 0.15 | 3 | strong cont, deepest rev |
| 10 | 120 | 0.03 | 0.05 | 1 | one-session reversal |
| 11 | 120 | 0.03 | 0.05 | 2 | two-session reversal |
| 12 | 120 | 0.03 | 0.05 | 5 | five-session reversal |

Two out-of-grid window checks are also reported: `L=60` and `L=250` at the
primary thresholds and hold. They are robustness checks, not grid cells.

A weekly decision clock is tested separately (Friday 15:59 decision, next
Monday open fill, one-week hold) using weekly returns and a rolling weekly
autocorrelation, and also using the daily autocorrelation sampled at Friday
close. It is a required exploration, not the primary.

---

## 4. Falsifiers

The family claim is rejected, or downgraded to "numerical pass, not a new
family", if any of these hold on the development window:

1. **Continuation falsifier.** The positive-autocorrelation leg, run alone
   (no reversal leg), must have a positive standalone CAGR and Sharpe. If it
   is flat or negative, the "positive AC → continuation" half of the
   hypothesis is false.
2. **Gate falsifier.** The reversal leg with the AC gate must beat the same
   reversal without the gate on CAGR per unit of exposure. If the gate only
   changes the number of trades and not the per-exposure return, the
   autocorrelation is cosmetic.
3. **Bar falsifier.** The primary must beat 36.72% CAGR with max DD below
   82.29% at 1 bp, and must stay above the CAGR bar at 5 bp and 10 bp.
4. **Plateau falsifier.** At least 8 of the 12 grid cells must clear the
   CAGR bar, and the passing cells must not all sit at one value of a single
   parameter. If only the weakest reversal threshold passes, the result is a
   corner, not a plateau.
5. **Placebo falsifier.** The true CAGR must exceed the 95th percentile of
   circular-shift placebos that preserve the signal's holding pattern but
   destroy its alignment with returns. One-sided p < 0.05.
6. **Family falsifier.** Daily-return correlation with `family-short-reversal`
   must be below 0.70. At or above 0.70 the strategy is a short-reversal
   variant with an autocorrelation overlay, not a new family.
7. **Subperiod falsifier.** At least two of the three subperiods
   (2016-2019, 2020-2021, 2022-2023) must have positive CAGR, and no single
   subperiod may contribute more than 70% of the total compounded log return.

---

## 5. Why this is not an existing family

| Existing family | Its primary signal | Difference here |
|---|---|---|
| 100-250 day MA trend | price vs moving average | no moving average; the state is a serial-dependence estimate |
| vol targeting | realised volatility level | the position is binary; volatility is not an input |
| drawdown recovery | drawdown depth / recovery event | no drawdown or recovery state |
| calendar | date/event window | no calendar condition |
| opening range / close flow | intraday range or flow | the decision uses daily closes only |
| ML classifier | fitted feature→label model | no fitted model, no labels |
| short reversal | down-day trigger | down day is only the direction; the AC gate decides whether the reversal state is on, and the positive-AC leg holds without a down day |

The distance from `family-short-reversal` is the one that matters in practice;
the correlation test in falsifier 6 is the arbiter.

---

## 6. Disclosure of development-window exploration

Before this file was frozen I ran development-window diagnostics: rolling AC
distributions, conditional forward TQQQ returns by AC bucket and return sign,
weekly-clock variants, hold-length variants, a coarse daily parameter scan and
a first coarse 1-minute grid. Those diagnostics are why the grid is centred on
L=120 and why the primary uses an asymmetric pair of thresholds; the centre
cell also happened to be the strongest cell in the coarse 1-minute pass, which
is a selection risk the plateau and placebo are meant to expose. They are
**development-window** diagnostics; the holdout was never touched. The final
numbers in `result.json` come from the final 1-minute backtester, not from the
daily approximation, and the daily approximation is not used for any reported
metric.

The exploratory screen found that the positive-AC continuation leg is weak and
that the negative-AC reversal leg carries most of the edge. That is a
falsification of half the mechanism, and it is reported as such rather than
hidden by re-labelling the strategy.
