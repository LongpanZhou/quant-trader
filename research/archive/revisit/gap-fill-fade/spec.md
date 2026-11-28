# Spec — gap-fill-fade (round-3 rebuild)

Status: **design only; backtests paused.** This is the exact specification the
code implements. No performance numbers have been produced for this rebuild.

## 1. Universe and data

- **Short instrument:** QQQ.
- **Cash:** BIL.
- **Sizing/benchmark data:** QQQ 1-minute opens, closes, highs, lows and volume;
  TQQQ and BIL only as benchmarks and correlation references.
- **Data source:** local adjusted 1-minute archive `data/intraday-hf/`.
- **Development period:** 2016-01-04 → 2023-12-29.
- **Holdout:** 2024-01-02 → 2026-10-23. **Not inspected by this agent.** The
  lead runs it once after freeze.
- **Sessions:** session starts are the first bar of each date; session ends are
  the last bar of each date. Index by bar, not by clock time. Half-days end at
  13:00. Skip a session if it has no 10:00 close bar (f+30 > l) or no 10:01
  entry bar (f+31 > l).

## 2. Signal (all inputs known by the 10:00:59 close)

For session k with first bar `f` and last bar `l`:

1. **Prior close:** `pc = QQQ_close[l_{k-1}]`.
2. **Opening gap:** `gap = QQQ_open[f] / pc − 1`.
   - Require `+0.0010 ≤ gap ≤ +0.0075` (i.e. +0.10% to +0.75%).
3. **Weak short-term tape** (both known at the prior close):
   - `sma10_prior = mean(QQQ_close[l_{k-10..k-1}])`; require `pc < sma10_prior`.
   - `ret5_prior = QQQ_close[l_{k-1}] / QQQ_close[l_{k-6}] − 1`; require
     `ret5_prior < 0`.
4. **Stressed volatility** (known at the prior close):
   - `vol20_prior = std(QQQ daily returns over the prior 20 sessions, ddof=0)
     × sqrt(252)`.
   - `vol_median = median(vol20_prior over the prior 252 sessions)`.
   - Require `vol20_prior > vol_median`. Skip if either is NaN or fewer than
     60 prior observations exist.
5. **First-30-minute confirmation** (known at the 10:00 close, bar `f+30`):
   - `r30 = QQQ_close[f+30] / QQQ_open[f] − 1`.
   - Require `r30 < 0` **and** `QQQ_close[f+30] < QQQ_open[f]`.
   - Require the gap is **still open**: `QQQ_close[f+30] > pc`. If the gap has
     already filled by 10:00, skip the session; there is nothing left to fade.
6. **Signal:** all of the above are true.

The signal is evaluated once per session at the 10:00 close. There is no
intraday re-entry and at most one short per session.

## 3. Position and sizing

- **Entry:** set the target at the 10:00 close (bar `f+30`); the fill is the
  10:01 open (bar `f+31`). No entry after 10:00.
- **Short expression:** a synthetic inverse-QQQ asset held long in the
  long-only engine. Its price is session-reset so that its value at the 10:01
  open is 1.0 and, for every later bar `t` in the session,
  `inv_open[t] = 1 − (QQQ_open[t] / QQQ_open[f+31] − 1)` and
  `inv_close[t] = 1 − (QQQ_close[t] / QQQ_open[f+31] − 1)`.
  The return from entry to exit is therefore the exact linear short QQQ
  return, not a compounded inverse-ETF return. The asset is an implementation
  device for a short; it is not a tradable product.
- **Borrow cost:** 0.5%/yr on the short notional, pro-rated by elapsed session
  fraction and embedded as a small decay in the inverse price. This satisfies
  the brief's ≥0.5%/yr borrow requirement.
- **Size:** `size = clip(0.10 / vol20_prior, 0.10, 1.00)`. The target is 10%
  annualised volatility; the position is at most 100% short and at least 10%.
  The remainder is BIL. Gross exposure is `size ≤ 1.0`, within the 2× limit.
- **No leverage beyond 1× short QQQ.** No TQQQ, no long QQQ, no overnight
  equity exposure.

## 4. Exit

For the entry session, with `entry_px = QQQ_open[f+31]`:

1. **Stop:** `or_high = max(QQQ high over 09:30–09:59)`. The stop is
   `stop_px = min(max(or_high, entry_px × 1.002), entry_px × 1.015)`: the
   opening-range high, with a +0.2% floor and a +1.5% cap. If any bar's high is
   `≥ stop_px`, set the exit at that bar and fill at the next bar's open. A
   fixed 1.0% stop is kept as a control, not the primary.
2. **Target:** `target_px = pc` (the prior close, i.e. the full gap fill). If
   any bar's low is `≤ target_px`, set the exit at that bar and fill at the
   next bar's open.
3. **Time stop:** at the first bar whose clock time is `≥ 11:30`, set the exit
   at that bar and fill at the next bar's open.
4. **End of day:** if none of the above fires, exit at the 15:58 close (bar
   `l−1`); fill at the 15:59 open. The strategy is flat overnight.
5. **Priority:** if a bar's high hits the stop and its low hits the target, the
   stop is assumed to fire first (conservative). The exit fill is always the
   next bar's open.

The holding period is therefore 10:01 → exit, with a maximum of about 90
minutes plus one fill bar. The modal trade is much shorter if the gap fills
early.

## 5. Costs and fills

- **Fills:** weights set at bar `i`'s close fill at bar `i+1`'s open, 2% band,
  exactly as `research/bt.py`.
- **Headline cost:** 1 bp one-way on traded notional.
- **Stress:** 5 bp and 10 bp.
- **Borrow:** 0.5%/yr on the short notional.
- **No separate commission or market impact.** The 1/5/10 bp slippage is the
  cost model.

## 6. Evaluation plan (when authorized)

### 6.1 Windows

- **Dev:** 2016-01-04 → 2023-12-29 (the only window this agent may inspect).
- **10y and 5y:** reported for comparison with the original, but they overlap
  the holdout; label them clearly. The code loads only the dev panel by
  default; the 10y/5y windows require `REVISIT_ALLOW_OVERLAP=1`, which is the
  lead's call, not the subagent's.
- **Holdout:** the lead runs it once after freeze. This agent does not run it.

### 6.2 Metrics

- CAGR, max drawdown on 1-minute marks, Sharpe, Sortino, volatility, fills,
  turnover, exposure.
- Event study: number of shorts, mean/median net PnL per event (per unit
  short, before the vol-size multiplier), win rate, t-stat, bootstrap 95% CI
  and p-value (10,000 resamples), average holding minutes, exit-reason counts
  (stop/target/time/EOD).
- Sub-periods: 2016–2019, 2020–2021, 2022–2023.
- Yearly returns.

### 6.3 ±1-step neighbourhood (choose from a plateau, not a single cell)

| Parameter | Primary | −1 step | +1 step |
|---|---:|---:|---:|
| Gap band low | 0.10% | 0.05% | 0.15% |
| Gap band high | 0.75% | 0.60% | 0.90% |
| Weak-tape SMA | 10 | 5 | 20 |
| Stress filter | vol20 > 1.0× median | none (0.0×) | 1.25× median |
| Confirmation | r30 < 0 | r30 < −0.10% | none |
| Stop | OR high, 0.2% floor / 1.5% cap | OR high, 0.1% floor / 1.0% cap | OR high, 0.3% floor / 2.0% cap; plus fixed 1.0% control |
| Time stop | 11:30 | 11:00 | 12:00 |
| Vol target | 10% | 8% | 12% |

The primary is the centre of the table. A parameter is accepted only if the
neighbouring cells have the same sign and a comparable magnitude. If the edge
exists only at the primary, it is a knife-edge and the strategy is rejected.

### 6.4 Placebo / random controls

1. **No-confirmation placebo:** enter at 10:01 on all weak-tape, stressed,
   small-gap days without the `r30 < 0` confirmation.
2. **Random-minute placebo:** enter at a random minute between 10:01 and 11:00
   on the same signal days, with the same target/stop/time rules.
3. **Gap-label shuffle:** keep the weak/stress/confirmation days but shuffle
   the gap values across sessions; if the gap band does not matter, the
   strategy is just a short-vol/weak-tape bet.
4. **Constant-short control:** short QQQ at 10:01 on every weak-tape, stressed
   day regardless of the gap; compare.

The confirmed signal must beat all four controls, not just zero.

### 6.5 Correlations

- Daily returns of the strategy vs the **165-day baseline** (long TQQQ when
  QQQ's prior close is above its 165-day SMA, else BIL). This baseline is a
  benchmark only; it is not used in `build_weights`. The comparison is
  computed by the lead's `correlations.json` pipeline, not by the strategy
  code. Target `< 0.60`.
- Daily returns vs every other rebuilt strategy (the lead's
  `correlations.json`). Target `< 0.70`.
- Daily returns vs TQQQ and QQQ buy-and-hold, for context.

### 6.6 Look-ahead and harness checks

- Rebuild the weights after truncating all data at 2020-03-12 11:07 and
  2022-09-13 10:41; the weights before each cut must be identical.
- Verify the 10:00 signal uses only bars `≤ f+30` and the 10:01 fill uses
  `f+31`.
- Verify the exit uses only bars `≤ exit_i` and fills at `exit_i+1`.
- Verify the session-end and half-day handling by bar index.
- Verify minute marks are native (1-minute strategy).

## 7. Status logic

- **passed:** the confirmed strategy has a positive net edge after 1 bp, the
  bootstrap CI excludes zero, the edge survives the neighbourhood and placebo
  controls, the correlation is `< 0.60`, and an independent audit passes.
- **retired_overlay_only:** the raw fade is visible but the standalone short
  does not earn its costs or is explained by the controls. The idea only worked
  as a filter on the old base.
- **rejected:** a look-ahead, harness, data, or reproducibility failure that
  cannot be fixed without changing the idea.

The current status is **pending**. No result.json exists until the lead
authorizes the dev run.

## 8. Why the design uses a 10-day SMA but not a 100–250-day gate

The brief forbids QQQ/TQQQ/SPY/NDX against a 100–250-day moving average as the
strategy gate. The weak-tape definition here is a **10-day** SMA plus a 5-day
return; it is a short-term condition, not a slow regime. The strategy is flat
by default and does not hold TQQQ; the 10-day SMA only decides whether a
small gap-up is a candidate for a fade. A 5-day and 20-day version are in the
neighbourhood table, so the result cannot depend on one arbitrary length.

## 9. Implementation note: why a synthetic inverse asset

`research/bt.py` is long-only. The brief allows shorts with borrow cost and
gross ≤2×. To model a short without modifying the engine, the code adds a
synthetic inverse-QQQ column whose **linear** return from the entry open to the
exit open is exactly the negative of QQQ's return over the same interval. The
engine holds it as a long position of size `s`; economically that is a short
QQQ of size `s`. The borrow cost is a small decay in the synthetic price. This
is not a private simulator; `bt.run` still does all fills, bands and marks.
