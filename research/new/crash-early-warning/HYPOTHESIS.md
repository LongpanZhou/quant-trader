# Crash early-warning overlay on TQQQ — pre-registration

**Slug:** `crash-early-warning`
**Status:** pre-registered before the final 1-minute run.
**Window:** 2016-01-04 → 2023-12-29 only. The 2024-01-01 → 2026-10-23 holdout is
not used, inspected, or returned by any panel in this study; every `bt.panel`
call ends at 2023-12-29.
**Bar:** TQQQ 2016-01-04 → 2023-12-29 is **36.72% CAGR / 82.29% max DD / 0.82
Sharpe** on 1-minute marks. Pass = dev CAGR > 36.72% and max DD < 82.29%
(ideally < 60%). A lower-CAGR but much better Sharpe/Calmar result is reported
as risk-adjusted, not as a pass.

This is a standalone strategy. It does **not** use the 165-day QQQ SMA, the 4%
intraday stop, the old drawdown-regime exit, the old event-risk overlay, the ML
crash classifier, or the overnight-only structure. It has no stop-loss and no
slow moving-average gate.

---

## 1. Mechanism: why a crash can be warned about

TQQQ is a 3× daily-reset Nasdaq-100 fund. Three measurable frictions make a
crash partly predictable from public daily data:

1. **Volatility clusters.** Daily equity volatility is strongly autocorrelated
   (Engle 1982; Bollerslev 1986). A 5-day realised volatility that is 40% above
   its 20-day level is not noise: it is the signature of a regime in which the
   next few days are also likely to be high-volatility. High-vol regimes have
   lower Sharpe and fatter left tails, and for a 3× fund the variance drag
   `3·σ²` rises with σ² (Avellaneda & Zhang 2010; Cheng & Madhavan 2009).
2. **Leverage feedback and daily rebalancing.** A 3× ETF must sell exposure into
   a falling market at the close to restore its 3× target, and buy into a rising
   market. That is mechanical same-direction flow at the close, which can
   amplify multi-day moves (Cheng & Madhavan 2009). The reset also makes TQQQ's
   path dependent: a 10% QQQ drawdown costs TQQQ far more than 30% when the path
   is choppy. A drawdown that is *accelerating* is therefore more dangerous for
   TQQQ than the same drawdown reached slowly.
3. **Overnight gap stress.** A leveraged ETF cannot be stopped through the
   overnight gap. Gaps are where the largest TQQQ losses are realised (2020-03-16:
   TQQQ −34.8% overnight). A cluster of large absolute gaps, or a large negative
   3-day cumulative gap, signals that the risk-off flow is persistent and that
   the next open can jump the position. Overnight and intraday clienteles are
   partly separate (Lou, Polk & Skouras 2019), so gap stress is not just the
   same information as the close-to-close return.

The composite is deliberately **confirmation-based**, not a top call. It waits
for a 5% QQQ drawdown from a 60-day high *and* a drawdown that is still
deepening, then requires one of the two fast stress signals (vol acceleration or
gap stress). This is early relative to the 20–35% QQQ bear markets (the 2020
exit was at QQQ −6.6% from the closing high, before the remaining ~23%), but it
is not a prediction of the exact top. It is a **continuation warning**.

Why this can beat TQQQ: TQQQ's 2016–2023 CAGR is high because 2017, 2019, 2020,
2021 and 2023 compounded strongly. The three large drawdowns (2018 Q4, 2020
COVID, 2022) are where the 82% max DD comes from. If the overlay gives up ~0.8%
of CAGR per year in false alarms but avoids the majority of the 2020 and 2022
declines, the compounded result can be higher with a much lower DD. The bar is
not "beat TQQQ every year"; it is "beat it over the full window with a lower
tail".

## 2. Exact rules

All signals are computed at the close of session `t` from QQQ regular-session
daily bars (open, close), using data through `t` only. Weights are set at that
close and filled at the **next session's open** (`bt.run`, 2% band, next-open
fills). No full-sample statistics are used.

Let `C_t` be the QQQ close and `O_t` the QQQ open of session `t`.

```
r_t      = ln(C_t / C_{t-1})
RV5_t    = stdev(r_{t-4..t}) * sqrt(252)
RV20_t   = stdev(r_{t-19..t}) * sqrt(252)
VA_t     = RV5_t / RV20_t

DD60_t   = C_t / max(C_{t-59..t}) - 1
DD5_t    = DD60_t - DD60_{t-5}          # 5-day drawdown velocity

GAP_t    = O_t / C_{t-1} - 1
GABS3_t  = mean(|GAP_{t-2..t}|)
GABS20_t = mean(|GAP_{t-19..t}|)
GS_t     = GABS3_t / GABS20_t
GAP3_t   = sum(ln(1 + GAP_{t-2..t}))
```

The three flags:

| Flag | Definition | Role |
|---|---|---|
| **A — vol acceleration** | `VA_t > 1.40` and `RV5_t > 0.18` | fast stress / leverage-decay risk |
| **B — drawdown acceleration** | `DD60_t < -0.05` and `DD5_t < -0.02` | confirmation that the pullback is deepening, not a one-day gap |
| **C — gap stress** | `GS_t > 1.60` or `GAP3_t < -0.015` | overnight / forced-flow stress |

`score_t = A_t + B_t + C_t`.

**Entry to defence:** at the close of `t`, if `score_t >= 2` **and** `B_t = 1`,
sell TQQQ and hold BIL from the next open. (B is mandatory; A or C supplies the
second vote. A one-day gap without drawdown acceleration does not trigger.)

**Re-entry:** while defensive, return to 100% TQQQ at the next open after a
close that is at least the highest close of the **prior 10 sessions**
(`C_t >= max(C_{t-10..t-1})`). This is a price-confirmation rule, not a moving
average. It is deliberately slower than a 5-day high: the 5-day version
re-enters into bear-market rallies and raises the max DD from 53% to 72%.

**Default:** 100% TQQQ. **Defensive:** 100% BIL. No partial sizing, no shorts,
no stop-loss, no intraday timing.

**Warm-up:** the 1-minute archive starts on 2016-01-04, so there is no
pre-2016 data. `RV20`, `DD60` and `GABS20` use `min_periods=10`; the first 10
sessions are default TQQQ. This is a real limitation, not a choice: the January
2016 drawdown is unprotected.

## 3. Why it should beat TQQQ

- It is fully invested in TQQQ in calm and trending markets (81% of sessions in
  the daily screen), so it keeps most of the 2017/2019/2020/2021/2023 upside.
- It exits before the *bulk* of a fast crash, not after it: in 2020 the exit was
  at QQQ −6.6% from the closing high; TQQQ still had ~63% of its 72%
  peak-to-trough decline to go.
- It re-enters on a 10-day closing high, which in 2020 was 2020-04-06 (QQQ 189
  vs the 2020-03-23 low of 164), giving up the first ~15% of the QQQ rebound but
  avoiding the −70% TQQQ crash. The trade is deliberately asymmetric.
- At 1 bp the cost is small: ~105 fills and ~520× turnover over eight years,
  because the strategy switches the whole book only ~26 times.

## 4. Falsifiers (written before the final run)

The hypothesis fails if any of these is true:

1. **Headline failure:** dev 1 bp CAGR ≤ 36.72% or max DD ≥ 82.29%.
2. **Single-episode dependence:** ex-2020 CAGR ≤ 36.72%, or the DD reduction
   disappears when 2020 is removed. (The strategy is allowed to earn a large
   part of its edge in 2020, but not all of it.)
3. **No plateau:** fewer than 6 of the 8 pre-registered grid cells have CAGR >
   36.72% with DD < 82.29%, or the neighbours collapse by more than ~5pp CAGR
   for a one-step threshold change.
4. **No timing value:** a circular-shift placebo that preserves the exact
   defensive-spell lengths and exposure fraction matches the observed max DD.
5. **Look-ahead:** truncating the data at 2018-12-24, 2020-03-12 or 2022-09-13
   changes any weight before the cut.
6. **Old strategy in disguise:** the result is reproduced by the 165-day SMA +
   4% stop, a pure vol target, or the existing drawdown-regime exit.

## 5. Pre-registered parameter grid (8 cells)

One-at-a-time neighbours around the core. Everything else is fixed at the core
value. All cells use the same B-required, 10-day-high re-entry, BIL defence.

| # | Cell | `VA` threshold | `DD60` threshold | `GS` threshold | 3-day gap threshold |
|---:|---|---:|---:|---:|---:|
| 1 | **core** | 1.40 | −5.0% | 1.60 | −1.5% |
| 2 | vol loose | 1.20 | −5.0% | 1.60 | −1.5% |
| 3 | vol tight | 1.60 | −5.0% | 1.60 | −1.5% |
| 4 | dd early | 1.40 | −4.0% | 1.60 | −1.5% |
| 5 | dd late | 1.40 | −7.0% | 1.60 | −1.5% |
| 6 | gap loose | 1.40 | −5.0% | 1.40 | −1.5% |
| 7 | gap tight | 1.40 | −5.0% | 2.00 | −1.5% |
| 8 | gap-sum loose | 1.40 | −5.0% | 1.60 | −1.0% |

`DD5 < −2.0pp`, `RV5 > 18%`, `min_periods=10`, `enter=2`, B required, 10-day
high re-entry, BIL defence are fixed in all eight cells.

The grid is a **plateau test**, not a search for the best cell. The core
thresholds were chosen from the feature distribution (1.40 ≈ the 88th percentile
of `VA`, 1.60 ≈ the 90th percentile of `GS`) and the standard 5% correction
level, not by maximising CAGR. Daily screening was used to fix the mechanism;
the 1-minute run is the final evaluation and is reported for the core only.

## 6. Expected effect

- 1 bp: CAGR 38–42%, max DD 50–58%, Sharpe 0.93–1.00.
- 5 bp / 10 bp: CAGR 37–41% / 36–40%; the pass should survive 10 bp because
  fills are sparse.
- TQQQ exposure: 78–82% of sessions; BIL 18–22%.
- Yearly shape: strong 2020 and 2022 relative performance; weak 2016 (no
  warm-up) and 2018 (choppy bear with false alarms); bull years 2017/2019/2021/
  2023 below TQQQ because of false alarms and the 10-day-high re-entry lag.
- Correlation to TQQQ: 0.65–0.75 on daily returns (lower than buy-and-hold
  because ~20% of the time is BIL and the overlay avoids some large down days).

## 7. Relation to existing work (checked before writing this)

- `research/agents/daily-regime-minute-entry`, `research/revisit/daily-regime-minute-entry`:
  165-day QQQ SMA + minute entry. Not used here.
- `research/agents2/drawdown-regime` and `research/revisit/drawdown-regime`:
  exits on the *level* of QQQ drawdown from a 52-week high, on top of the 165-day
  SMA + 4% stop. This strategy uses drawdown *velocity* and has no SMA or stop.
- `research/agents2/vol-scaled-crash-stop`: ATR-scaled 4% stop. This strategy
  has no stop.
- `research/agents2/overnight-crash-filter`: overnight-only / first-hour TQQQ
  with a 20-day vol filter. This strategy holds all day and uses gap stress only
  as one vote in a composite.
- `research/agents2/ml-crash-overlay-winner` / `research/revisit/ml-crash-overlay-winner`:
  walk-forward logistic classifier on a 165-day SMA base. This is a deterministic
  three-component rule with no ML and no slow MA.
- `research/agents2/event-risk-overlay`: FOMC/CPI/OpEx calendar events. This is
  price/vol-based, not calendar-based.
- `research/agents2/stop-reentry-recovery`: post-4%-stop re-entry. This has no
  stop and no same-day re-entry.
- `research/new/vol-of-vol-timing`: vol-of-vol risk-state timing with a
  V-recovery re-risk. This uses drawdown acceleration + gap stress + vol
  acceleration and a 10-day price high, not a vol-of-vol state.
- `research/new/fast-trend-vol`: fast adaptive trend + vol target. This has no
  trend filter and is default-long TQQQ.
- `research/new/overnight-drift-filter`: overnight-only drift. This holds
  overnight and intraday.
- `research/new/cross-asset-momentum`, `relative-value-tqqq`, `macro-event-tqqq`,
  `orb-tqqq-volume`, `ml-regime-v2`: different mechanisms; none uses a
  drawdown-acceleration + gap-stress early-warning composite.

No code or parameters are copied from any of them.

## 8. Diagnostics that will be reported

- 1-minute headline at 1/5/10 bp; daily screen for comparison.
- Yearly returns and the 2018/2020/2022 drawdown attribution.
- All 8 grid cells (daily marks), plus the 10/15/20-day re-entry horizon.
- Component-only rules (A, B, C, A&B, A&C, B&C), unanimous 3-of-3, and the
  no-B-gate variant.
- Circular-shift placebo (500 shifts) preserving spell lengths and exposure.
- Cut tests at 2018-12-24, 2020-03-12 and 2022-09-13 (weights before the cut
  must be identical).
- Ex-2020 and ex-2022 CAGR/DD.
- Honest verdict: pass/fail, and whether the edge is crash timing or just
  lower exposure.
