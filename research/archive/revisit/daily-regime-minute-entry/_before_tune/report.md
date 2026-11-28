# Revisit — `daily-regime-minute-entry`: crash continuation as a standalone short

**Status:** spec + code frozen; **backtest results pending** (backtests paused by
instruction). Development window only: 2016-01-04 → 2023-12-29. Holdout
2024-01-02 → 2026-10-23 not inspected.

---

## 1. The idea being extracted

The original strategy is the shared 165-day QQQ base **plus one new idea**:

> A 4% break below the session open in TQQQ, armed when QQQ opens below its
> 20-day MA, predicts **continuation into the close and the night**. Exiting the
> long TQQQ book on that break avoided tail losses.

The genuinely new content is therefore **downside continuation after an intraday
break** — a short-horizon momentum/crash-continuation effect. The 165-day regime
and the long TQQQ book are the shared base and are *not* part of the rebuild.

### What the original evidence says about the effect

From the original agent's event study (`research/agents/daily-regime-minute-entry/`,
ungated 4% stop, 276 events, 2017-2026):

| Horizon | Mean | Median | Share < 0 |
|---|---:|---:|---:|
| break → session close | **−0.269%** | not recorded | ~50% |
| session close → next open | −0.019% | — | — |
| break → next open | **−0.300%** | +0.028% | 50.0% |

The continuation is **intraday**: the night is flat, and the 4% break's mean is
driven by a fat left tail (2020-03-11 −21.6%, 2024-08-02 −13.8%, 2020-02-27
−13.4% …). That says the right trade is a **short from the break to the close**,
not a multi-day short.

---

## 2. Standalone hypothesis (pre-registered)

> **H1.** On 2016-2023, shorting TQQQ from the first 1-minute close at least 4%
> below the session open to the session close (and holding 100% BIL otherwise)
> earns a positive net return after 1 bp fills and a 0.5%/yr borrow fee, with
> max drawdown ≤ 25% and Sharpe ≥ 0.30 on 1-minute marks.
>
> **H2.** Its daily-return correlation with the old 165-day TQQQ/BIL base is
> below 0.60 (expected ≈ 0.0, range −0.1 to +0.1), because the book is in BIL
> on ~90% of sessions and short only on event days (~25-30 per year).
>
> **H3.** The −4% trigger adds information over a random intraday short of the
> same count and holding period: the real strategy's dev CAGR sits above the
> 95th percentile of a 100-draw placebo.

### What would falsify it

1. **No net edge:** mean per-event return ≤ 0 after 1 bp costs and borrow
   (event t-stat < 1.0, bootstrap p(mean ≤ 0) > 0.10).
2. **No standalone return:** dev 1 bp CAGR ≤ BIL buy-and-hold, or Sharpe < 0.30,
   or max drawdown > 25%.
3. **No trigger information:** real dev CAGR ≤ placebo p95 (the −4% signal is
   no better than random intraday timing).
4. **Not robust:** the sign flips at stop = 3% or 5%, or under the ±1-step
   neighbourhood (cover rule, size, MA20 arm).
5. **Not stable:** negative in two of the three dev sub-periods (2016-19,
   2020-21, 2022-23).
6. **Not diversifying:** daily correlation with the 165-day base ≥ 0.60.

If (1)-(3) fail, the effect is real but not harvestable standalone → `rejected`.
If the only obstacle is that no long-only expression exists in this data set and
the synthetic inverse is disallowed → `retired_overlay_only`, stated honestly.

---

## 3. Universe, signal, holding period, sizing

| Item | Rebuild |
|---|---|
| **Universe** | TQQQ (short), BIL (parking), QQQ (signal only). SPY daily is a benchmark only — no 1-minute SPY history exists for 2016-2023. |
| **Base / default** | 100% BIL. No long TQQQ position, no 165-day gate. |
| **Signal** | The first 1-minute TQQQ close at least **4% below the session open** triggers a short. No trend gate in the primary rule (the MA20 arm is a variant only). |
| **Entry** | Next 1-minute open after the trigger (harness next-bar fill). |
| **Exit** | Cover at the 15:59 open (forced), or earlier if TQQQ closes back above the session open (`reclaim`), or on a +2% bounce from the entry (`stop2` variant). One trade per session; no entries after 15:45. |
| **Holding period** | Minutes to a few hours; **never overnight**. |
| **Sizing** | Short notional = 1.0× equity (0.5× variant). Gross ≤ 1.0×; long-only collateral. |
| **Borrow** | 0.5%/yr on the short notional, embedded in the synthetic inverse NAV (charged only while held). |
| **Costs** | 1 bp headline; 5 bp and 10 bp reported. 2% band, next-open fills. |
| **Marks** | 1-minute equity marks. |

### Why this is genuinely different from the original

| | Original | Rebuild |
|---|---|---|
| Direction | long TQQQ / BIL | **short TQQQ / BIL** |
| Base | 165-day QQQ SMA | **none (BIL by default)** |
| Signal | armed stop used as an exit | **same break used as the entry** |
| Holding | weeks-months, overnight | **hours, never overnight** |
| Exposure | ~80% of sessions long TQQQ | ~10% of sessions short, ~90% BIL |
| Return driver | equity risk premium + crash avoidance | **intraday crash continuation (convex)** |
| Correlation to old base | 1.00 | **expected ≈ 0.0** |

---

## 4. Engine note: the synthetic −1× TQQQ NAV

`research/bt.py` is long-only (`weights >= 0`, sum ≤ 1), so a short cannot be
expressed directly. The rebuild shorts via a **long position in a synthetic
constant-notional inverse TQQQ NAV**:

```
S_open[t]  = S_close[t-1] * (1 - gap_t  - b/2)
S_close[t] = S_open[t]   * (1 - intra_t - b/2)
gap_t   = open_t/close_{t-1} - 1
intra_t = close_t/open_t - 1
b       = 0.005 / (252*390)          # 0.5%/yr borrow, per bar
```

Holding from `open[i]` to `open[j]` earns exactly the TQQQ short return over
that interval minus borrow. The harness still performs every fill, 2% band
check, slippage charge and 1-minute mark. The only approximation is that the
inverse NAV rebalances each minute (volatility drag ≈ 6 bp over a 300-minute
hold), which is negligible at this horizon.

**If the lead does not accept a synthetic instrument**, there is no way to
express this effect long-only in the available data (no inverse ETF, no VIX, no
options history), and the strategy should be marked `retired_overlay_only`.

---

## 5. Sources and provenance

| Idea / claim | Source | Role | Evidence | Confidence |
|---|---|---|---|---|
| The effect: a large intraday decline is followed by continuation into the close | **Own event study** (`research/agents/daily-regime-minute-entry/stop_events.py`, 276 ungated 4% events) | inspired rule | Break→close mean −0.269%, break→next mean −0.300%; median break→next ≈ 0; fat left tail | high (own data) |
| Intraday trend persists into the last half hour | Gao, Han, Li & Zhou (2018), *Market Intraday Momentum*, JFE 129(2) | supports assumption | The first half-hour return predicts the last half-hour return across major ETFs; intraday momentum is strongest on high-volatility days | medium-high |
| Intraday momentum is linked to hedging demand / short-gamma flow | Baltussen, Da, Lammers & Martens (2021), *Hedging demand and market intraday momentum*, JFE 142(1), doi 10.1016/j.jfineco.2021.04.029 | supports assumption | Across 60+ futures (1974-2020), short-gamma hedging requires trading in the direction of price moves, creating intraday momentum | medium-high |
| Leveraged-ETF rebalancing can amplify late-day moves after large declines | Cheng & Madhavan (2009), *The Dynamics of Leveraged ETF Returns*; Lenkey (2024), *The Market Impact of Leveraged ETFs: A Survey* | supports assumption (contested) | LETF daily rebalancing is sized by the day's return and has been associated with late-day returns/volatility | low-medium |
| Counter-evidence: fund flows offset most LETF rebalancing demand | Ivanov & Lenkey (2018), *Do Leveraged ETFs Really Amplify Late-Day Returns and Volatility?* | tested/rejected mechanism | Flows offset as much as 85% of predicted rebalancing; late-day effects smaller than claimed | — (why the mechanism is only supporting, not the thesis) |
| The overnight is not where the crash continuation lives; the close is | Lou, Polk & Skouras (2019), *A Tug of War: Overnight versus Intraday* (+ own overnight decomp: TQQQ +1,354.8% overnight vs +81.2% intraday, 2017-2026) | supports assumption | Overnight and intraday components have different drivers; the original event study shows the night is flat after a break | high |
| Stop-loss rules work when returns have momentum, not under a random walk | Kaminski & Lo (2014), *When Do Stop-Loss Rules Stop Losses?*, JFM 18 | supports assumption | 0/1 stop rules add value only with momentum/regime shifts; basis for treating the break as a state signal | high |

**Not used:** the 165-day QQQ/TQQQ/SPY/NDX moving-average gate, the old base
weights, the old MA20-armed long stop. The old `strategy.py` is read only to
recover the event definition and the event study.

---

## 6. Planned tests (all dev-only, to run after authorization)

1. **Headline:** dev 2016-01-04 → 2023-12-29, 1/5/10 bp, 1-minute marks; CAGR,
   max DD, Sharpe, fills, turnover, exposure.
2. **Correlation:** daily returns vs the 165-day baseline (built only as a
   benchmark), vs TQQQ and QQQ buy-and-hold.
3. **Event statistics:** count, mean, median, std, t-stat, bootstrap
   p(mean ≤ 0), hit rate, worst/best event.
4. **Placebo:** 100 random intraday shorts with the same event count and
   holding mechanics; report the real CAGR percentile and the p05/p50/p95.
5. **±1-step neighbourhood:** stop 3% / 4% / 5%; cover `reclaim` / `close` /
   `stop2`; size 0.5 / 1.0; MA20 arm on/off. Parameters chosen from a plateau,
   not the argmax.
6. **Sub-periods:** 2016-19, 2020-21, 2022-23.
7. **Benchmarks:** TQQQ, QQQ, BIL, SPY (daily marks, flagged), and the original
   strategy's own 10y/5y `result.json` numbers (quoted, overlapping holdout).
8. **Costs:** the 1/5/10 bp sensitivity above; borrow included at 0.5%/yr.

### Pre-registered pass bar

`status = passed` only if **all** of:

- dev 1 bp CAGR > BIL dev CAGR;
- dev 1 bp Sharpe ≥ 0.30;
- dev 1 bp max drawdown ≤ 25%;
- event mean t ≥ 1.65 and bootstrap p(mean ≤ 0) ≤ 0.10;
- positive CAGR in ≥ 2 of 3 dev sub-periods;
- daily correlation with the 165-day base < 0.60.

Otherwise `rejected` (effect tested and not harvestable) or, if the only
blocker is the lack of a long-only expression, `retired_overlay_only`.

---

## 7. Results

**PENDING — backtests paused by instruction.** No `result.json` has been
generated. The table below is the schema the authorized run will fill.

| Window | Cost | CAGR | Max DD | Sharpe | Fills |
|---|---|---:|---:|---:|---:|
| dev 2016-2023 | 1 bp | — | — | — | — |
| dev 2016-2023 | 5 bp | — | — | — | — |
| dev 2016-2023 | 10 bp | — | — | — | — |

Correlation vs 165-day base: — (expected ≈ 0.0).
Event count / mean / t: —.

---

## 8. Known risks and limitations

1. **Short-side tail risk.** A V-shaped reversal after the break is the losing
   scenario; the `reclaim` cover is the primary defence, and the `stop2`
   variant is tested as a tighter cap. The 2020 March-April period contains
   both huge continuation days and huge rebound days.
2. **Event concentration.** ~25-35 events/year; the mean is fat-tail driven.
   The bootstrap and the placebo are there to keep this honest.
3. **Synthetic instrument.** See §4. If disallowed, retire.
4. **Borrow and locate.** 0.5%/yr is a conservative borrow fee for TQQQ, but a
   real short also faces margin and recall risk; the strategy is flat at night,
   which limits recall exposure to the session.
5. **No 1-minute SPY.** The SPY benchmark is daily-marked; this is flagged.
6. **No options/VIX data.** A long-vol expression of the same effect cannot be
   tested here; if it could, it would likely dominate the short implementation.
7. **Regime dependence.** The effect may be stronger in high-volatility years
   (2020) than in calm years; the sub-period table is the test.

---

## 9. Reproduction (only after authorization)

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
python research\revisit\daily-regime-minute-entry\strategy.py
```

`strategy.py` writes `result.json` with the dev windows, correlations, event
stats, sub-periods, variants and placebo. The holdout and the overlapping
10y/5y windows are intentionally left null for the lead.
