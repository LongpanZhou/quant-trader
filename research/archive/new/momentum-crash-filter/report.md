# Momentum with a crash brake on TQQQ — development report

**Slug:** `momentum-crash-filter`
**Window:** 2016-01-04 → 2023-12-29 (development only; 2024-2026 never used or
inspected)
**Harness:** `research/bt.py`, 1-minute regular-session marks, next-open fills,
2% band, 1 bp headline; 5 bp and 10 bp sensitivity. Long-only, weights ≥ 0,
sum ≤ 1.
**Files:** `HYPOTHESIS.md` (pre-registration), `strategy.py`, `result.json`.

---

## Verdict

**Formal pass on the full-window bar, with a clear and honest qualification.**
At 1 bp the strategy makes **42.70% CAGR / 47.57% max DD / 1.005 Sharpe**,
versus the TQQQ bar of **36.72% / 82.29% / 0.82**. It still passes at 5 bp
(41.61% / 48.16% / 0.988) and 10 bp (40.26% / 48.88% / 0.967). The max DD is
below the "ideally < 60%" line at every cost level, and the Calmar ratio is
about twice TQQQ's.

The qualification: **the return edge is a crash-avoidance payoff, not broad
alpha.** The strategy wins 2020 (+57.8 pp vs TQQQ) and 2022 (+58.3 pp) and loses
every other calendar year, badly in 2019 (−80.7 pp) and 2023 (−65.0 pp). The
full-window CAGR wins because avoiding two 70–80% TQQQ drawdowns compounds.
Unlike `crash-early-warning`, the edge is not only 2020: ex-2020 CAGR is
**30.27%** versus TQQQ's **27.84%** on the same exclusion, because 2022 is also
avoided. But ex-2020-and-2022 CAGR is 41.55% versus TQQQ's 72.99%, so the
strategy is not an all-weather replacement for TQQQ.

| | 1 bp | 5 bp | 10 bp | TQQQ bar |
|---|---:|---:|---:|---:|
| **CAGR** | **42.70%** | **41.61%** | **40.26%** | 36.72% |
| **Max DD** | **47.57%** | **48.16%** | **48.88%** | 82.29% |
| **Sharpe** | **1.005** | **0.988** | **0.967** | 0.82 |
| **Calmar** (CAGR / DD) | **0.897** | **0.864** | **0.824** | 0.446 |
| Sortino | 1.414 | 1.390 | 1.360 | — |
| Volatility | 46.1% | 46.1% | 46.1% | 66.5% |
| Fills | 153 | 153 | 153 | 1 |
| Turnover (× start equity) | 746.0 | 715.1 | 678.4 | ~0 |
| TQQQ weight (average) | 79.9% | 79.9% | 79.9% | 100% |
| Time in BIL | 20.1% | 20.1% | 20.1% | 0% |
| Corr to TQQQ (1m bars) | 0.692 | 0.692 | 0.692 | 1.00 |
| Corr to TQQQ (daily) | 0.698 | 0.698 | 0.698 | 1.00 |
| Ending equity ($100k) | $1,709,441 | $1,607,961 | $1,489,540 | $1,175,283 |

The benchmark measured on the same 1-minute panel is 36.15% CAGR / 82.29% max
DD / 0.801 Sharpe; the task's reference bar is 36.72% / 82.29% / 0.82. The
candidate beats both. The `bt.stats` "exposure" field is 100% because BIL is an
asset; the economically relevant TQQQ exposure is **79.9% of sessions**.
Turnover is 746× start equity, higher than the pre-registered ~350× estimate
because every switch is a full-book trade; the 10 bp run still passes at 40.26%
CAGR, so the cost sensitivity is acceptable.

## 1. What the strategy does

At each session close, using QQQ daily bars through that close:

```
r20 = C_t / C_{t-20} - 1
r60 = C_t / C_{t-60} - 1
M   = (r20 > 0) or (r60 > 0)                     # momentum gate

DD20 = C_t / max(C_{t-19..t}) - 1
VA   = RV5 / RV20                                # 5-day / 20-day realised vol
R3   = ln(C_t / C_{t-3})                         # 3-day log return
CRASH = (DD20 < -8%) and ( (VA > 1.50) or (R3 < -6%) )

HI5 = max(C_{t-5..t-1})
```

State machine, evaluated at every close and filled at the next open:

- If defensive, re-enter TQQQ when `C_t >= HI5` **and** `r20 > 0`.
- Otherwise, go defensive on `CRASH`.
- Hold TQQQ when `M` is true and the book is not defensive; otherwise hold BIL.

The first 60 sessions (2016-01-04 → 2016-03-28) have no 60-session history in
the archive and are default-long TQQQ. The crash brake is active from session
20, when `DD20` and `VA` are defined. This is a real limitation, not a choice.

The momentum gate is deliberately loose ("either" horizon). Requiring both
horizons was tested on the daily screen and cut CAGR to about 22%: it re-enters
too late after a V-shaped recovery. Using TQQQ itself instead of QQQ for the
momentum signal was also much worse (about 22% CAGR on the daily screen):
3× daily returns are too noisy for a 20/60 gate. QQQ is the signal asset; TQQQ
is the implementation.

## 2. Yearly returns

Measured on the same 1-minute panel, year-end to year-end; the 2016 base is the
first session of the archive.

| Year | Strategy | TQQQ | Difference |
|---:|---:|---:|---:|
| 2016 | **+0.2%** | +19.9% | −19.6 pp |
| 2017 | +101.5% | +118.3% | −16.9 pp |
| 2018 | **−28.1%** | −19.6% | −8.5 pp |
| 2019 | +52.4% | +133.1% | **−80.7 pp** |
| 2020 | **+167.4%** | +109.6% | **+57.8 pp** |
| 2021 | +56.3% | +83.0% | −26.6 pp |
| 2022 | **−20.8%** | −79.1% | **+58.3 pp** |
| 2023 | +133.4% | +198.4% | **−65.0 pp** |

The shape is a crash hedge: it gives up 8.5–80.7 pp in the bull/choppy years
and earns it back in 2020 and 2022. It does not beat TQQQ in any other calendar
year. The full-window CAGR wins because the two crash years are the two largest
relative gains and they compound.

## 3. Drawdown and episode attribution

Peak-to-trough within the same calendar window, 1-minute marks:

| Episode | TQQQ max DD | Strategy max DD | Avoided | TQQQ return | Strategy return |
|---|---:|---:|---:|---:|---:|
| 2018-08-30 → 2018-12-24 | −56.0% | −40.4% | **+15.7 pp** | −54.5% | −39.3% |
| 2020-02-20 → 2020-03-20 | −72.2% | −26.2% | **+46.0 pp** | −65.8% | −23.8% |
| 2021-11-22 → 2022-12-28 | −82.1% | −37.7% | **+44.4 pp** | −81.2% | −26.9% |
| 2023-01-01 → 2023-12-29 | −34.9% | −31.6% | +3.4 pp | +195.9% | +136.4% |

The full-period max DD is **47.57%**, peak **2018-01-29**, trough
**2019-01-23**. It is a 2018 event, not a 2020/2022 event: the strategy's two
big wins are precisely the two episodes where TQQQ's drawdown was worst.

The 2020 exit signal was on 2020-02-25 at QQQ 207.19 (−9.1% from the 20-session
high; TQQQ 10.44), filling at the next open; the re-entry signal was on
2020-04-06 (QQQ 189.45; TQQQ 6.11), also filling at the next open. On the actual
open-to-open fills (2020-02-26 → 2020-04-07), the defensive spell avoided a
−37.4% TQQQ move. The
2022 bear was handled by a sequence of spells: 2022-01-18 → 2022-02-24
(−25.1% TQQQ), 2022-04-14 → 2022-06-23 (−39.0%), 2022-08-29 → 2022-10-21
(−27.9%). The 2018 Q4 episode was only a partial success: the strategy avoided
15.7 pp but still lost 39.3%, because it re-entered the November rally and was
hit again.

### Defensive-spell statistics (daily marks)

| Statistic | Value |
|---|---:|
| Spells | 38 |
| Median / mean / max length | 6 / 10.6 / 48 sessions |
| Defensive sessions | 404 (20.1%) |
| Spells with TQQQ **up** (false alarms) | **65.8%** |
| Mean TQQQ move in down spells | **−13.5%** |
| Mean TQQQ move in up spells (cost) | **+7.1%** |

The 65.8% false-alarm rate is the honest number. The strategy works because the
right spells are much larger: four of the 38 spells avoided −25% to −39% of
TQQQ, while the average wrong spell cost 7.1%. The geometric asymmetry is what
matters: avoiding a −39% loss is worth 1.64×; missing a +7% gain costs 1.07×.
A handful of large avoided losses dominate many small missed rallies.

### Event study: the crash trigger is a tail filter, not a mean predictor

There are 11 crash triggers in 2,012 sessions (0.55%). Forward TQQQ returns:

| Horizon | Mean after crash | Mean all days | Negative share after | Negative share all | 10th pct after | 10th pct all | Min after | Min all |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 days | +6.4% | +2.0% | 36.4% | 36.0% | −16.6% | −14.1% | −19.3% | −57.5% |
| 20 days | +3.7% | +4.1% | 45.5% | — | **−34.1%** | **−18.1%** | **−50.3%** | −67.5% |

The crash state does **not** have a lower average forward return. It has a much
fatter left tail at 20 days: the 10th percentile is −34.1% versus −18.1%
unconditionally, and the minimum is −50.3%. That is the economic case for the
brake: it is a tail hedge, not a short signal. The 10-day window is too short to
see the full effect; the spell table above is the better attribution.

## 4. Robustness

### 4.1 Pre-registered 8-cell grid (daily marks)

One-at-a-time neighbours around the core; everything else fixed. The grid is a
plateau test, not a search for the best cell.

| # | Cell | CAGR | Max DD | Sharpe | Fills | TQQQ time |
|---:|---|---:|---:|---:|---:|---:|
| 1 | **core** (DD −8%, VA 1.50, loss −6%, re 5) | **42.30%** | 46.53% | 0.984 | 153 | 79.9% |
| 2 | dd early (−6%) | 38.09% | 45.88% | 0.932 | 149 | 78.1% |
| 3 | dd late (−10%) | 38.48% | 48.09% | 0.906 | 165 | 81.4% |
| 4 | vol tight (1.80) | 40.39% | 51.02% | 0.952 | 157 | 80.4% |
| 5 | loss tight (−4%) | **30.84%** | 55.68% | 0.817 | 161 | 78.4% |
| 6 | loss loose (−8%) | 43.97% | 46.53% | 0.996 | 157 | 80.3% |
| 7 | re-entry fast (3) | 43.73% | 49.04% | 0.996 | 153 | 80.3% |
| 8 | re-entry slow (7) | 38.90% | 49.98% | 0.941 | 149 | 78.9% |

**7 of 8 cells pass** the CAGR > 36.72% / DD < 82.29% bar, and all eight have
DD below 56%. The failure is the tight 4% 3-day-loss leg: it exits too often in
ordinary corrections and costs 11.5 pp of CAGR. The core sits in the middle of
the plateau (the seven passing cells are 38.1–44.0% CAGR and 45.9–51.0% DD; the
4% loss failure is 30.8% / 55.7%), not at the maximum. The 6%
3-day-loss threshold was fixed on the daily screen as a "sharp multi-day loss"
(roughly an 18% TQQQ move), not by maximising CAGR.

### 4.2 Wider neighbour table (daily marks)

| Variant | CAGR | Max DD | Sharpe | TQQQ time |
|---|---:|---:|---:|---:|
| **core** | 42.30% | 46.53% | 0.984 | 79.9% |
| momentum buffer −0.5% | **45.24%** | 44.01% | 1.021 | 80.9% |
| momentum buffer −1.0% | **47.09%** | 50.50% | 1.035 | 82.2% |
| momentum buffer −2.0% | 43.51% | 57.05% | 0.975 | 84.1% |
| momentum buffer +1.0% | 37.56% | 43.41% | 0.929 | 77.6% |
| drawdown window 15 | 42.30% | 46.53% | 0.984 | 79.9% |
| drawdown window 30 | 42.30% | 46.53% | 0.984 | 79.9% |
| re-entry 10 | 34.60% | 54.21% | 0.876 | 78.4% |
| re-entry 15 | 33.46% | 56.37% | 0.859 | 78.1% |
| re-entry 20 | 34.45% | 56.37% | 0.876 | 78.1% |
| no re-entry momentum (`r20>0`) | 33.11% | 51.37% | 0.833 | 81.8% |
| no crash brake | 34.69% | 51.37% | 0.837 | 83.4% |

The plateau is broad in the momentum-buffer direction: a small hysteresis band
**improves** CAGR to 45–47% with DD of 44–51% for the −0.5%/−1% cells. The
core's strict zero buffer is the conservative choice, not the maximum. The
re-entry speed is the more sensitive parameter: 10-day and slower re-entries
fall below the bar (33.5–34.6%), while 3 and 7 days both pass (43.7% and 38.9%).
The 5-day reclaim is the design choice that makes the V-shaped 2020 recovery
work. The drawdown window is inert at 15/20/30 because the volatility or
3-day-loss leg almost always occurs inside a >8% drawdown from the 20-day high;
the drawdown condition is a necessary gate but not the discriminating variable.

### 4.3 Component attribution (daily marks)

| Rule | CAGR | Max DD | Sharpe | Fills | TQQQ time |
|---|---:|---:|---:|---:|---:|
| Momentum only (no crash) | 34.69% | 51.37% | 0.837 | 165 | 83.4% |
| Crash only (default long, 5-day reclaim) | 39.32% | **82.59%** | 0.867 | 65 | 94.0% |
| Crash only + `r20>0` re-entry | 38.22% | 72.54% | 0.877 | 45 | 89.1% |
| DD + 3-day loss (no vol leg) | **43.33%** | **43.56%** | 0.993 | 153 | 81.2% |
| DD + vol spike (no loss leg) | **43.78%** | 46.53% | 0.988 | 157 | 80.5% |
| Loss only | 41.53% | 52.38% | 0.973 | 157 | 80.1% |
| Vol only | 31.91% | 41.13% | 0.836 | 277 | 71.1% |
| **Core (momentum + crash)** | **42.30%** | **46.53%** | **0.984** | 153 | 79.9% |

This is the clearest evidence that the combination is the strategy:

- Momentum alone misses the CAGR bar (34.69%).
- Crash alone misses the drawdown point (82.59%, essentially TQQQ's): the
  default-long overlay re-enters every bear-market rally and gets hit again.
- The momentum gate is what avoids the slow 2022 bear; the crash brake is what
  avoids the fast 2020 crash. Neither alone does both.
- Both crash legs work: DD+loss (43.33% / 43.56%) and DD+vol (43.78% / 46.53%)
  are close to the core. The two confirmations are complementary, not redundant.

### 4.4 Placebo (500 circular shifts, daily marks)

The full TQQQ/BIL state vector is shifted by a random amount, preserving the
exact spell lengths and the 20.1% defensive exposure. This tests whether the
timing matters or whether the result is just "be out of TQQQ 20% of the time".

| | Observed | Placebo mean | Placebo p5 | Placebo p95 | Observed percentile |
|---|---:|---:|---:|---:|---:|
| CAGR | 42.30% | 27.50% | 12.88% | 45.30% | **92.0th** |
| Max DD | 46.53% | 77.09% | 69.23% | 86.35% | **0.2th** |
| Sharpe | 0.984 | 0.706 | — | 0.931 | **97.2th** |

The DD reduction is far outside the random-timing distribution: only 1 of 500
shifts has a lower max DD, and only 0.8% have a DD below 60%. The CAGR edge is
weaker: 16.8% of random shifts also beat the 36.72% bar, and the observed CAGR
is only the 92nd percentile. This is consistent with the ex-year evidence: the
**risk reduction is the robust part; the CAGR pass is a crash payoff.** The
placebo's joint "CAGR > bar and DD < 82.29%" share is 16.4%, so the loose DD bar
alone is not a high hurdle; the < 60% DD result is the discriminating outcome.

### 4.5 Cut tests (causality)

Rebuilding the signal on data truncated at the session close gives **zero**
weight differences before the cut:

| Cut | Bars compared | Weight differences |
|---|---:|---:|
| 2018-12-21 | 291,156 | 0 |
| 2020-03-12 | 409,752 | 0 |
| 2022-09-13 | 655,277 | 0 |

The signal uses only data through the decision close. No look-ahead. The first
60 sessions are the only period without a full 60-session momentum history, and
they are explicitly default-long TQQQ.

### 4.6 Ex-year fragility

Daily marks for this decomposition (the 1-minute headline is in the first
table; the 1-minute ex-2020 result is 30.27% / 46.53% / 0.821).

| Sample | Strategy CAGR | Strategy DD | Strategy Sharpe | TQQQ CAGR | TQQQ DD | TQQQ Sharpe |
|---|---:|---:|---:|---:|---:|---:|
| Full 2016–2023 | 42.30% | 46.53% | 0.984 | 35.98% | 81.68% | 0.80 |
| Ex-2020 | **30.27%** | 46.53% | 0.821 | **27.84%** | 81.68% | 0.711 |
| Ex-2022 | 55.02% | 46.53% | 1.167 | **77.75%** | 69.89% | 1.242 |
| Ex-2020 & 2022 | 41.55% | 46.53% | 1.020 | **72.99%** | 57.97% | 1.321 |

The pre-registered falsifier **ex-2020 CAGR ≤ TQQQ ex-2020 CAGR is not
triggered**: 30.27% > 27.84%. That is a genuine improvement over
`crash-early-warning`, whose ex-2020 CAGR was 24.7% versus TQQQ's 27.8%. The
edge is a two-crash-year edge (2020 and 2022), not a one-year edge. But without
both crash years the strategy badly lags TQQQ on CAGR (41.6% vs 73.0%) while
still cutting the DD. It is a crash hedge, not an all-weather alpha source.

## 5. Where it fails

1. **Strong, crash-free bull markets.** 2019 (+52.4% vs +133.1%), 2021 (+56.3%
   vs +83.0%) and 2023 (+133.4% vs +198.4%) are the problem. The momentum gate
   exits during ordinary corrections and re-enters higher; the strategy gives
   up 27–81 pp in those years. If the 2024-2026 holdout is a strong bull with no
   meaningful drawdown, the strategy will lag TQQQ.
2. **Choppy bear markets.** 2018 is the failure: the strategy lost 28.1% versus
   TQQQ's 19.6% and its full-period max DD (47.57%) is the 2018-01 → 2019-01
   path. The 5-day reclaim buys the first bear rally, which is often a trap. The
   2018 Q4 episode avoided only 15.7 pp of a 56.0 pp TQQQ decline.
3. **Warm-up.** The 1-minute archive starts 2016-01-04, so the first 60 sessions
   have no 60-session momentum history and are default-long TQQQ. 2016 finished
   +0.2% versus TQQQ +19.9%; the January 2016 drawdown is effectively
   unprotected by the momentum gate (the crash brake is active from session 20).
4. **False alarms.** 65.8% of defensive spells had TQQQ up, average cost +7.1%.
   The strategy tolerates this because the right spells are much larger (four
   avoided −25% to −39%), but a run of false alarms in a bull market is a
   material drag.
5. **The crash trigger is not a mean-return predictor.** Forward 10-day TQQQ
   returns after a trigger average +6.4% versus +2.0% unconditionally; the
   20-day 10th percentile is what improves (−34.1% vs −18.1%). The filter is a
   tail hedge; it will look wrong most of the time in a V-shaped recovery.
6. **Holdout arithmetic.** With the dev total at 17.09× over 7.98 years, beating
   a 37.54% full 2016-2026 CAGR requires roughly a **23.9% CAGR in the
   2024-2026 holdout** (about 1.83× over 2.8 years). That is plausible if the
   holdout contains a meaningful drawdown, but not guaranteed in a strong,
   calm bull. The dev cushion is real but not infinite.

## 6. Relation to existing work

This is a standalone strategy, not a re-parameterisation of an existing one:

- **`research/new/crash-early-warning`:** default 100% TQQQ, de-risks on a
  3-component score (vol acceleration + drawdown acceleration + gap stress)
  with B mandatory, re-enters on a 10-day high. This strategy has a **20/60
  momentum gate**, no gap-stress component, no drawdown-velocity term, a 5-day
  reclaim, and a 3-day-loss leg. It is not default long: it stands aside on
  negative momentum even without a crash. The state paths and the yearly tables
  are different (crash-early-warning 2020 +218%, 2022 −33%; this strategy 2020
  +167%, 2022 −21%).
- **`research/new/fast-trend-vol`:** 20/50-day EMA trend + vol target + daily
  and intraday crash brakes. No EMA, no vol target, no intraday override; the
  trend signal is total-return momentum.
- **`research/new/vol-of-vol-timing`:** vol-of-vol / Parkinson range risk state.
  No range estimator, no vol-of-vol, no V-recovery re-risk.
- **`research/new/cross-asset-momentum`:** dual momentum across QQQ/SPY/BIL.
  Single signal asset (QQQ), no cross-asset ranking.
- **`research/agents2/drawdown-regime` / `revisit/drawdown-regime`:** exits on
  the level of QQQ drawdown from a 52-week high on top of the 165-day SMA + 4%
  stop. No SMA, no stop; 20-session drawdown plus a fast-stress confirmation.
- **`research/agents2/stop-reentry-recovery`, `vol-scaled-crash-stop`:** stops.
  This has no stop.
- **`research/agents2/overnight-crash-filter`:** overnight-only with a 20-day
  vol filter. Holds all day.
- **`research/agents2/ml-crash-overlay-winner`:** walk-forward logistic
  classifier on a 165-day SMA base. Deterministic rule, no ML, no slow MA.
- **`research/agents2/event-risk-overlay`:** FOMC/CPI/OpEx calendar events. No
  calendar.
- **`research/new/ml-regime-v2`:** walk-forward ML with momentum signs
  (60/100/150). No ML, 20/60 only.

No code or parameters were copied. The only shared component is `research/bt.py`
for fills and marks, as required.

## 7. Honest verdict

**Pass on the letter of the bar:** 42.70% CAGR > 36.72%, 47.57% max DD < 82.29%
(and < 60%), 1.005 Sharpe > 0.82, at 1/5/10 bp. The signal is causal (cut tests
identical), the pre-registered grid is a plateau (7/8 cells pass, all DDs below
56%), and the drawdown reduction is not a random-exposure artifact (0.2th
percentile vs 500 placebo shifts).

**But do not read it as an all-weather replacement for TQQQ.** The return edge
is a 2020/2022 crash-avoidance payoff: the strategy loses every other calendar
year, badly in 2019 and 2023. Ex-2020 CAGR still beats TQQQ (30.3% vs 27.8%),
which is better than `crash-early-warning`, but ex-2020-and-2022 CAGR is 41.6%
versus TQQQ's 73.0%. The CAGR edge is only the 92nd percentile against random
timing, and 16.8% of random shifts also beat the bar; the DD reduction is the
robust, decisive result (0.2th percentile, only 0.8% of placebos below 60% DD).

The strategy's correct use is as a **crash-hedged trend sleeve on a TQQQ
core**, not as a standalone all-weather alpha strategy. For the lead's one-shot
holdout, it is a reasonable candidate: it has a 42.7% dev CAGR, a 47.6% DD, a
genuine two-crash-year edge, and a causal, interpretable signal. It needs about
a 23.9% holdout CAGR to beat the full 2016-2026 37.54% bar; that is likely if
2024-2026 contains a real drawdown, and at risk if it is a calm, strong bull.

**Bottom line:** a real, interpretable momentum-with-crash-brake strategy that
clears the development bar with a 47.6% max DD (35 pp below TQQQ's), at the
cost of a crash-concentrated return edge. Report it as a qualified pass, not a
free lunch.
