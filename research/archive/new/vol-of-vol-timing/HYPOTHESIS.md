# Vol-of-vol risk-state timing (VVT)

**Slug:** `vol-of-vol-timing`
**Status:** pre-registered hypothesis. Development window only:
**2016-01-04 .. 2023-12-29**. No 2024-2026 data is used anywhere in this
study. This file is written before the final 1-minute run and the 8-cell grid.

---

## 1. The idea

TQQQ is a 3x daily-reset fund. Its compound return is path-dependent:

```
log E[r_TQQQ] ~ 3 mu_QQQ - 3 sigma_QQQ^2
```

so the *level* of volatility is a direct tax on the product, and a volatility
regime that is high but stable is just as damaging as one that is spiky. The
interesting state variable is not only the level; it is whether the volatility
regime is **stable, accelerating, or resolving**.

This strategy holds TQQQ when range-based realised volatility is low and
stable. It de-risks when volatility is high, when volatility accelerates, or
when vol-of-vol rises. It re-risks only when volatility is high but
*decelerating* and vol-of-vol has turned down from its recent peak: the
signature of a forced-deleveraging episode that is ending (a V-recovery), when
TQQQ's daily-reset convexity is highest.

The state definition is deliberately **not** a simple vol target:

- volatility is measured with the **Parkinson range estimator** from daily
  high/low, not close-to-close standard deviation;
- the slow state is a blend of 10-day and 20-day range vol;
- **vol-of-vol** is the coefficient of variation of the 5-day range vol over
  the last 20 days;
- **vol acceleration** is 5-day range vol divided by 20-day range vol;
- the V-recovery trigger requires vol-of-vol to be high but **falling from its
  10-day peak**, and short vol to be no longer accelerating.

## 2. Why vol-of-vol should predict leverage risk

1. **Volatility clusters and mean-reverts.** A 20-day range-vol level is
   persistent, so it can be used to scale exposure. But the *dispersion* of
   short-window vol estimates around that level tells us whether the regime is
   orderly (low vol-of-vol) or in transition (high vol-of-vol).
2. **Leveraged-ETF rebalancing is path-dependent.** In a high-vol, unstable
   tape, TQQQ's daily reset generates volatility drag and gap risk that a 1x
   fund does not have. The same +10%/-10% sequence that leaves QQQ flat costs
   TQQQ roughly 9%. Vol-of-vol is a proxy for that two-sided path risk.
3. **V-recoveries are a distinct state.** After a crash, vol-of-vol peaks,
   then falls while the vol level is still high. That is when forced selling
   is exhausted and the rebound is sharpest. A pure high-vol filter stays out
   and misses it. This is why the strategy uses vol-of-vol *direction* to
   re-risk, not just its level.
4. **Asymmetry.** The cost of being out during a calm uptrend is the foregone
   drift; the cost of being fully long during a vol shock is a permanent
   capital loss in a 3x product. A state that is quick to de-risk and slower
   to re-risk should improve the geometric return even if it gives up some
   arithmetic return.

## 3. Exact rules (all signals at the session close, fills next open)

### Data

- TQQQ 1-minute regular-session bars, 09:30-16:00 ET, from `research/bt.py`.
- Daily high/low are the true session high/low from the daily parquet, read
  with a `date <= 2023-12-29` predicate (no 2024-2026 rows are materialised).
  If a session is missing, the fallback is max/min of that session's 1-minute
  opens/closes.
- All rolling windows use only bars at or before the signal session. The first
  30 sessions (until the 20-day vol and 10-day vov-peak windows are valid) are
  held in BIL; the first target is set at the 2016-02-17 close and fills
  2016-02-18.

### State variables

```
park_d   = sqrt( log(high_d / low_d)^2 / (4 ln 2) )       # daily Parkinson sigma
rv_k     = sqrt(252) * mean(park_d, k)                     # k = 5, 10, 20
sigma_s  = 0.25 * rv_10 + 0.75 * rv_20                     # slow range vol
vov      = std(rv_5, 20) / mean(rv_5, 20)                  # vol-of-vol
vov_peak = max(vov, last 10 sessions)
vov_10   = vov 10 sessions ago
```

### Exposure

```
base = clip( (0.65 - sigma_s) / (0.65 - 0.40), 0, 1 )

# 1. De-risk when volatility is high: base is 1 below 40% annualised,
#    0 above 65%, linear in between.

# 2. Re-risk on deceleration:
if rv_5 < 0.80 * rv_20:
    base = base + (1 - base) * 0.50

# 3. V-recovery: high vol-of-vol that has turned down, with vol not accelerating:
if rv_20 > 0.55 and vov > 0.25 and vov <= 0.95 * vov_peak and rv_5 <= rv_20:
    base = base + (1 - base) * 0.50

# 4. De-risk on acceleration:
if rv_5 > 1.30 * rv_20:
    base = base * 0.70

# 5. De-risk on a vol-of-vol spike:
if vov > 0.45 and vov > 1.20 * vov_10:
    base = base * 0.70

TQQQ weight = clip(base, 0, 1)
BIL weight  = 1 - TQQQ weight
```

The 2% band and next-open fills are the harness defaults. No shorting, no
leverage above 100%, no intraday trades: the strategy decides once per session
at the close and executes at the next open.

### Why these numbers

- 40%/65% annualised range vol are roughly the 55th/86th percentiles of
  TQQQ's 2016-2023 daily range vol (median 36.8%, p90 71%). They are broad
  regime boundaries, not tuned peaks.
- 0.25/0.75 on rv10/rv20 keeps the state slow enough to avoid daily whipsaw
  while giving some weight to the last two weeks.
- 0.80 and 1.30 are symmetric-ish acceleration boundaries (20% below / 30%
  above the 20-day baseline). 0.95 of the 10-day vov peak means "vov has
  actually turned down".
- 0.55 stress threshold is roughly the 74th percentile of rv20; 0.45 vov
  spike is roughly the 97th percentile. The stress threshold is not extreme —
  it is "high vol", not "crisis" — while the vov spike is a tail state.

## 4. Why it should beat TQQQ

TQQQ's 2016-2023 development result is **36.72% CAGR / 82.29% max DD / 0.82
Sharpe** on 1-minute marks. The strategy should beat it because:

- it is fully invested in calm, low-vol uptrends, which is where most of
  TQQQ's drift is earned (2017, 2019, 2021, 2023);
- it cuts exposure before the worst of 2018 Q4 and 2022, when the vol level is
  high and persistent;
- it re-risks into the 2018 and 2020 V-recoveries through the vol-of-vol
  turn-down rule, which a simple vol target misses;
- it never uses leverage above 1x, so the maximum loss per session is bounded
  by TQQQ's own move.

The expected result is **CAGR 40-50%, max DD 45-60%, Sharpe 1.0-1.2**, with
TQQQ exposure 70-78% of sessions. The bar is CAGR > 36.72% and DD < 82.29%;
the strategy should clear both with room to spare, and the interesting question
is whether the DD stays under 60%.

## 5. Falsifiers

The strategy is falsified if any of the following holds:

1. **Headline:** dev CAGR <= 36.72% or max DD >= 82.29% at 1 bp.
2. **Cost:** at 10 bp the CAGR falls below 36.72% (the edge is a
   microstructure artefact).
3. **Vov ablation:** removing the vol-of-vol V-recovery block (rule 3) changes
   CAGR by less than +1 pp, or improves it. Then vol-of-vol is decoration and
   the result is a vol-level ladder.
4. **Acceleration ablation:** removing rules 4-5 does not reduce max DD by at
   least 1 pp. Then the de-risk state is decoration.
5. **Plateau:** any one-step neighbour in the pre-registered grid falls below
   36.72% CAGR or above 65% DD. A knife-edge is not a strategy.
6. **Concentration:** the 2016-2019 or 2022-2023 subperiod has negative CAGR,
   or more than half of the total excess return comes from a single calendar
   year. Then the "state" is one episode.
7. **Beta:** daily correlation to TQQQ is above 0.90 and a static
   exposure-matched TQQQ/BIL mix has a higher Sharpe. Then it is beta, not
   timing.
8. **Whipsaw:** the strategy underperforms a no-trade version with the same
   average exposure after 5 bp costs. Then the state transitions destroy value.

## 6. Pre-registered parameter grid (8 combinations)

All combinations use the same architecture and the same fixed parameters
(`vol_lo=0.40`, `dec_boost=0.50`, `vov_stress=0.55`, `vov_drop=0.95`,
`add=0.50`, `acc_ratio=1.30`, `acc_cut=0.70`, `vov_spike=0.45`,
`vov_rise=1.20`, `vov_cut=0.70`). Only one parameter changes per row.

| # | label | `vol_hi` | `dec_ratio` | `vov_th` | `w10` | `w20` |
|---|-------|---------:|------------:|---------:|------:|------:|
| 0 | primary | 0.65 | 0.80 | 0.25 | 0.25 | 0.75 |
| 1 | vol_hi_lo | **0.62** | 0.80 | 0.25 | 0.25 | 0.75 |
| 2 | vol_hi_hi | **0.68** | 0.80 | 0.25 | 0.25 | 0.75 |
| 3 | dec_lo | 0.65 | **0.78** | 0.25 | 0.25 | 0.75 |
| 4 | dec_hi | 0.65 | **0.82** | 0.25 | 0.25 | 0.75 |
| 5 | vov_hi | 0.65 | 0.80 | **0.30** | 0.25 | 0.75 |
| 6 | blend_lo | 0.65 | 0.80 | 0.25 | **0.20** | **0.80** |
| 7 | blend_hi | 0.65 | 0.80 | 0.25 | **0.30** | **0.70** |

The primary is the mechanism-chosen centre, not the best cell. The grid is a
plateau test: all eight should land in a similar region. If the primary is an
outlier, the state is fragile.

## 7. Ablations and controls (reported, not used for selection)

- **L**: level ladder only (no dec boost, no vov, no cuts).
- **D**: level + deceleration boost.
- **V**: level + vov V-recovery (no dec boost).
- **DV**: level + deceleration + vov (no de-risk cuts).
- **DVC**: primary (all rules).
- **Static mix**: constant TQQQ weight equal to the strategy's average TQQQ
  exposure.
- **Placebo**: shuffle the daily TQQQ weights across sessions (same exposure
  distribution, no timing), 200 draws; and random vov-add days with the same
  count, 200 draws.
- **Cut tests:** 2016-2019, 2020-2021, 2022-2023; leave-one-year-out.
- **Costs:** 1, 5, 10 bp.

## 8. How this differs from the existing vol strategies

- `dynamic-leverage-throttle` (revisit): buys TQQQ **after** a volatility shock
  is decaying **inside a drawdown**, sized inversely to still-elevated vol;
  it is an event/recovery strategy that is out during calm uptrends. VVT is the
  opposite base: it is **long TQQQ in calm low-vol uptrends**, and uses the
  shock state only to decide when to re-risk. It has no drawdown gate, no
  inverse-vol sizing formula, and no 165-day trend gate.
- `vol-kelly-overlay` (revisit): waits for a 1-minute realised-vol spike plus
  an oversold QQQ drawdown plus the first up-close, then holds for 1-3
  sessions. VVT has no 1-minute event trigger, no oversold condition, no fixed
  holding period, and no price stop. It is a persistent daily risk-state
  allocation, not an event trade.
- `risk-parity-hrp` / `vol-scaled-crash-stop`: those are static or stop-based
  allocations; VVT's state is a range-vol level plus the **direction** of
  vol-of-vol, which neither uses.

## 9. Expected failure modes

- **Whipsaw in 2018 and 2021:** the 2% band and daily decisions can still
  trade too often if vol oscillates around 40%. The acceleration cut is
  designed to reduce this, but it may cost more return than it saves.
- **V-recovery timing:** the vov turn-down rule may buy too early in a
  continuing bear (e.g., 2022 bear rallies). The 2022 exposure is expected to
  be low because vov is low, but the few add days could lose money.
- **2022-style persistent high vol:** vol-of-vol is *low* in 2022, so the
  V-recovery block does nothing; only the level ladder protects. If the level
  ladder is too slow, the DD stays high.
- **2016-style calm grind:** the first 30 sessions are flat; if the market
  rallies immediately, the strategy lags. (In this window TQQQ fell 20.9% from
  2016-01-04 to 2016-02-17, so the warmup happened to help; the report
  quantifies it and shows the result excluding it.)

## 10. Result files

`strategy.py` writes `result.json` with:
- dev 1/5/10 bp metrics (CAGR, max DD, Sharpe, Sortino, volatility, exposure,
  TQQQ exposure, fills, turnover, ending equity);
- yearly strategy vs TQQQ returns and average TQQQ weight;
- daily-return correlation to TQQQ and to QQQ;
- the 8-cell grid;
- ablations L/D/V/DV/DVC;
- subperiods and leave-one-year-out;
- static-mix and placebo controls;
- drawdown episodes.

`report.md` interprets them honestly, including the failure modes above.
