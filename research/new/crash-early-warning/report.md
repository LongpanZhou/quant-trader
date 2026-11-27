# Crash early-warning overlay on TQQQ — development report

**Slug:** `crash-early-warning`
**Window:** 2016-01-04 → 2023-12-29 (development only; 2024-2026 never used or inspected)
**Harness:** `research/bt.py`, 1-minute regular-session marks, next-open fills,
2% band, 1 bp headline; 5 bp and 10 bp sensitivity. Long-only, weights ≥ 0,
sum ≤ 1.
**Files:** `HYPOTHESIS.md` (pre-registration), `strategy.py`, `result.json`.

---

## Verdict

**Formal pass on the stated full-window bar, but a qualified one.** At 1 bp the
strategy makes **40.38% CAGR / 54.86% max DD / 0.965 Sharpe**, versus the TQQQ
bar of **36.72% / 82.29% / 0.82**. It still passes at 5 bp
(39.65% / 55.43% / 0.954) and 10 bp (38.73% / 56.14% / 0.940). The max DD is
below the "ideally < 60%" line at every cost level.

The qualification is important: **the return edge is concentrated in 2020**.
Excluding 2020, the same strategy makes 24.7% CAGR with a 53.0% max DD and a
0.72 Sharpe, versus TQQQ's 27.8% / 81.7% / 0.71 ex-2020. So without the COVID
crash the overlay is a **risk-reduction** trade (same Sharpe, 29 pp less DD),
not a CAGR winner. The full-window pass is a crash-hedge payoff, not broad
alpha. The drawdown/Sharpe improvement is robust; the CAGR edge is not
statistically strong against random timing.

| | 1 bp | 5 bp | 10 bp | TQQQ bar |
|---|---:|---:|---:|---:|
| **CAGR** | **40.38%** | **39.65%** | **38.73%** | 36.72% |
| **Max DD** | **54.86%** | **55.43%** | **56.14%** | 82.29% |
| **Sharpe** | **0.965** | **0.954** | **0.940** | 0.82 |
| **Calmar** (CAGR / DD) | **0.736** | **0.715** | **0.690** | 0.446 |
| Sortino | 1.365 | 1.348 | 1.327 | — |
| Volatility | 46.4% | 46.4% | 46.5% | 66.5% |
| Fills | 105 | 105 | 105 | 1 |
| Turnover (× start equity) | 521.8 | 507.7 | 490.7 | ~0 |
| TQQQ weight (average) | 80.8% | 80.8% | 80.8% | 100% |
| Time in BIL | 19.2% | 19.2% | 19.2% | 0% |
| Corr to TQQQ (1m bars) | 0.698 | 0.698 | 0.698 | 1.00 |
| Corr to TQQQ (daily) | 0.697 | 0.697 | 0.697 | 1.00 |
| Ending equity ($100k) | $1,500,525 | $1,438,808 | $1,365,219 | $1,175,283 |

The benchmark measured on the same 1-minute panel is 36.15% CAGR / 82.29% max
DD / 0.801 Sharpe; the task's reference bar is 36.72% / 82.29% / 0.82. The
candidate beats both. The "exposure" field in `bt.stats` is 100% because BIL is
an asset; the economically relevant TQQQ exposure is 80.8% of sessions.

## 1. What the strategy does

Default: 100% TQQQ. At each session close, compute three causal QQQ flags:

- **A — vol acceleration:** `RV5/RV20 > 1.40` and `RV5 > 18%`.
- **B — drawdown acceleration:** QQQ is `>5%` below its 60-day high **and** the
  60-day drawdown has deepened by `>2 pp` over the last 5 sessions.
- **C — gap stress:** the 3-day mean absolute overnight gap is `>1.60×` its
  20-day mean, **or** the 3-day cumulative log gap is `< −1.5%`.

`score = A + B + C`. Go to **100% BIL** at the next open when
`score ≥ 2` **and** `B = 1`. Re-enter **100% TQQQ** at the next open after a
close at or above the prior **10-session** closing high. No stop-loss, no
165-day SMA, no slow moving-average gate, no full-sample normalisation.

The signal is a **continuation warning**, not a top call: it waits for a 5% QQQ
drawdown and requires drawdown acceleration, then uses vol acceleration or gap
stress as the second vote. In 2020 it exited at QQQ −6.6% from the closing high
(TQQQ −19%), before the remaining ~23% QQQ / ~63% TQQQ decline.

## 2. Yearly returns

Measured on the same 1-minute panel, year-end to year-end; the 2016 base is the
first session of the archive.

| Year | Strategy | TQQQ | Difference | Time in BIL |
|---:|---:|---:|---:|---:|
| 2016 | **−21.6%** | +19.9% | −41.5 pp | 5.6% |
| 2017 | +118.3% | +118.3% | 0.0 pp | 0.0% |
| 2018 | **−38.3%** | −19.6% | −18.7 pp | 27.5% |
| 2019 | +99.1% | +133.1% | −34.0 pp | 12.7% |
| 2020 | **+218.4%** | +109.6% | **+108.8 pp** | 20.9% |
| 2021 | +31.8% | +83.0% | −51.2 pp | 14.3% |
| 2022 | **−33.0%** | −79.1% | **+46.1 pp** | 60.2% |
| 2023 | +153.5% | +198.4% | −44.9 pp | 12.4% |

The shape is exactly what a crash overlay should look like: it gives up 30–50 pp
in bull years (2019, 2021, 2023) and in the choppy 2016/2018 markets, and earns
it back in 2020 (+109 pp relative) and 2022 (+46 pp relative). The full-window
CAGR wins because the 2020 relative gain compounds. It does not beat TQQQ in
most individual years.

## 3. Why early warning is possible

The mechanism is documented and measurable on this sample:

1. **Volatility clusters.** The lag-1 autocorrelation of 5-day realised QQQ
   volatility is **0.924**. Warning days (`score≥2 & B`) are 5.9% of sessions
   and have mean `RV5` of **40.1%** versus **18.7%** unconditionally. High-vol
   days are not random; they arrive in runs.
2. **The warning state has a worse left tail, not a negative mean.** Forward
   10-day TQQQ returns on warning days average **+0.25%** versus **+0.82%** on
   other days, and the share of negative 10-day returns is **42.4%** versus
   **34.0%**. The signal is a risk-state classifier, not a short signal. That is
   why the strategy goes to BIL rather than shorting.
3. **Leverage feedback.** TQQQ's 3× daily reset means a 5% QQQ drawdown is
   roughly a 15% TQQQ drawdown, and the reset forces same-direction rebalancing
   flow at the close (Cheng & Madhavan 2009). The variance drag `3σ²` rises with
   the vol state (Avellaneda & Zhang 2010), so a high-vol, accelerating drawdown
   is more dangerous for TQQQ than the same QQQ move in a calm tape.
4. **Gap stress is separate information.** The largest TQQQ losses are overnight
   gaps (2020-03-16: TQQQ gapped −29.1% and closed −34.8%, a gap the strategy
   cannot stop through). A cluster of large gaps, or a large negative 3-day cumulative gap,
   identifies forced risk-off flow that persists into the next session. Overnight
   and intraday clienteles are partly separate (Lou, Polk & Skouras 2019).

The economic case is asymmetric: the average TQQQ move during a defensive spell
is **−15.0%** when the spell is right and **+9.1%** when it is wrong. A 50% hit
rate is enough because the payoff ratio is about 1.65:1.

## 4. Attribution of the avoided drawdown

Peak-to-trough within the same calendar window, 1-minute marks:

| Episode | TQQQ max DD | Strategy max DD | Avoided | TQQQ return | Strategy return |
|---|---:|---:|---:|---:|---:|
| 2018-08-30 → 2018-12-24 | −56.0% | −52.0% | **+4.0 pp** | −54.5% | −51.0% |
| 2020-02-20 → 2020-03-20 | −72.2% | −20.1% | **+52.1 pp** | −65.8% | −16.4% |
| 2021-11-22 → 2022-12-28 | −82.1% | −54.9% | **+27.2 pp** | −81.2% | −46.9% |

The 2020 episode is the success: the exit on 2020-02-24 (QQQ 212.9, −6.6% from
the closing high; TQQQ −19% from its close high) avoided 52.1 pp of the 72.2 pp TQQQ decline; the strategy lost 16.4%
while TQQQ lost 65.8% over the window. Re-entry on 2020-04-06 (QQQ 189.4) gave
up the first ~15% of the QQQ rebound but kept the rest. The next-open fill path
is not a free lunch: the 2020-02-25 exit filled into a +2.5% opening bounce
(helpful), but the 2020-04-07 re-entry bought a +8.7% gap-up that reversed
−8.5% intraday (costly). Net, the fill path reduced the 2020 gain rather than
inflating it. The 2022 bear is a
partial success: 60.2% of sessions in BIL, 27.2 pp of DD avoided, but the
strategy still lost 46.9% because the 10-day-high re-entry kept buying bear-market
rallies (February, March, May, July, August, September, December). The 2018
episode is a failure of the overlay: only 4.0 pp of a 56.0 pp TQQQ drawdown was
avoided, because the strategy re-entered in the November rally and was hit again.

Defensive-spell statistics (daily marks, 26 spells):

| Statistic | Value |
|---|---:|
| Spells | 26 |
| Median / mean / max length | 14 / 14.8 / 35 sessions |
| Defensive sessions | 386 (19.2%) |
| Spells with TQQQ **up** (false alarms) | **50.0%** |
| Mean TQQQ move in down spells | **−15.0%** |
| Mean TQQQ move in up spells (cost) | **+9.1%** |

The 50% false-alarm rate is the honest number. Measuring the TQQQ move from the
close before the exit signal instead of from the actual entry/exit fills gives a
misleadingly low 19%; with the real fills, half the spells are wrong and the
average wrong spell costs 9.1% of TQQQ upside. The strategy works because the
average right spell avoids 15.0%.

## 5. Robustness

### 5.1 Pre-registered threshold grid (daily marks)

All eight cells use the same B-required, 10-day-high re-entry, BIL defence. The
grid is one-at-a-time neighbours around the core.

| # | Cell | CAGR | Max DD | Sharpe | Fills | TQQQ time |
|---:|---|---:|---:|---:|---:|---:|
| 1 | **core** (VA 1.40, DD −5%, GS 1.60) | **40.00%** | 52.96% | 0.951 | 105 | 80.8% |
| 2 | vol loose (VA 1.20) | 40.00% | 52.96% | 0.951 | 105 | 80.8% |
| 3 | vol tight (VA 1.60) | 40.76% | 52.63% | 0.961 | 105 | 80.9% |
| 4 | dd early (−4%) | 39.56% | 52.96% | 0.951 | 109 | 79.3% |
| 5 | dd late (−7%) | **33.75%** | 53.95% | 0.840 | 93 | 83.9% |
| 6 | gap loose (GS 1.40) | 37.61% | 52.96% | 0.916 | 113 | 80.0% |
| 7 | gap tight (GS 2.00) | 40.54% | 52.96% | 0.956 | 101 | 81.3% |
| 8 | gap-sum loose (−1.0%) | 41.43% | 52.63% | 0.977 | 113 | 79.4% |

**7 of 8 cells pass** the CAGR > 36.72% / DD < 82.29% bar. The max DD is
essentially invariant (52.6–54.0%) across the grid; the CAGR ranges 33.75–41.43%.
The failure is the late drawdown threshold (−7%): waiting for a 7% QQQ drawdown
misses the early part of the 2020 and 2022 exits and costs 6.3 pp of CAGR. The
5% correction level was fixed ex ante as the standard correction threshold, not
chosen by maximising CAGR.
The vol-loose cell is identical to the core: `VA` values that matter are either
above 1.4 or the second vote comes from gap stress, so lowering the vol
threshold adds no entries.

### 5.2 Re-entry horizon

| Re-entry high | 1 bp CAGR | Max DD | Sharpe | TQQQ time |
|---|---:|---:|---:|---:|
| 10-day (core) | **40.38%** | 54.86% | 0.965 | 80.8% |
| 15-day | 38.57% | **49.74%** | 0.957 | 77.1% |
| 20-day (daily only) | 36.35% | **43.12%** | 0.931 | 73.8% |

The horizon is a monotone risk/return trade-off. The 15-day variant also passes
at 1/5/10 bp (38.57/49.74/0.957, 37.92/50.06/0.946, 37.12/50.66/0.933) with a
lower DD; its ex-2020 CAGR is 21.7%, worse than the core's 24.7%. The 20-day
variant is a risk-adjusted result just below the CAGR bar (36.35% / 43.12% /
0.931). Its Calmar is better than the core's (0.84 vs 0.76), but the CAGR is
below 36.72%, so it is reported as risk-adjusted, not as a pass.

### 5.3 Component attribution (daily)

| Rule | CAGR | Max DD | Sharpe | Fills | TQQQ time |
|---|---:|---:|---:|---:|---:|
| A — vol acceleration only | 20.36% | 67.20% | 0.62 | 193 | 78.5% |
| B — drawdown acceleration only | 31.75% | 50.79% | 0.84 | 137 | 76.9% |
| C — gap stress only | 30.14% | 40.74% | 0.89 | 381 | 59.7% |
| A & B | 31.86% | 75.62% | 0.78 | 65 | 89.2% |
| A & C | 30.89% | 74.20% | 0.77 | 125 | 84.3% |
| **B & C** | **40.76%** | **52.63%** | **0.96** | 105 | 80.9% |
| All three (unanimous) | 36.87% | 76.55% | 0.84 | 49 | 90.8% |
| 2-of-3, no B gate | 36.02% | 52.96% | 0.91 | 169 | 75.6% |
| **Core (2-of-3, B mandatory)** | **40.00%** | **52.96%** | **0.95** | 105 | 80.8% |

The edge is the **drawdown acceleration + gap stress** pair. Vol acceleration
alone is a weak timer (20.4% CAGR); requiring all three is too late (36.9% CAGR,
76.6% DD). The core's 2-of-3-with-B rule is nearly identical to B&C and slightly
more faithful to the mandate because vol acceleration can supply the second
vote. The B gate is worth about +4.0 pp of CAGR and +0.045 Sharpe versus the
same score without B (36.0% / 53.0% / 0.91). That is the single most important
design choice: it filters one-day gap shocks that are not followed by a deeper
drawdown.

### 5.4 Placebo

500 circular shifts of the defensive-day vector, preserving the exact spell
lengths and 19.2% exposure. This tests whether the **timing** matters or whether
the result is just "be out of TQQQ 19% of the time".

| | Observed | Placebo mean | Placebo p5 | Placebo p95 | Observed percentile |
|---|---:|---:|---:|---:|---:|
| CAGR | 40.00% | 27.70% | 11.97% | 44.65% | **87.8th** |
| Max DD | 52.96% | 77.26% | 69.89% | 85.52% | **0.0th** |
| Sharpe | 0.951 | 0.708 | 0.497 | 0.928 | **96.4th** |

**No random shift** has a max DD below 60%; the observed DD is lower than all
500 placebos. The DD/Sharpe improvement is strongly timing-specific. The CAGR
edge is only moderate: 20.6% of random shifts also beat the 36.72% bar, so the
CAGR pass is not statistically special. This matches the ex-2020 result: the
return edge is the 2020 crash payoff; the risk reduction is the robust part.

### 5.5 Cut tests (causality)

Rebuilding the signal on data truncated at the session close gives **zero**
weight differences before the cut:

| Cut | Bars compared | Weight differences |
|---|---:|---:|
| 2018-12-24 | 291,367 | 0 |
| 2020-03-12 | 409,752 | 0 |
| 2022-09-13 | 655,277 | 0 |

The signal uses only data through the decision close. No look-ahead.

### 5.6 Ex-year fragility

Daily marks for this decomposition (the 1-minute headline is in the first
table; the ex-2020 1-minute result is the same 24.7% / 53.0%).

| Sample | Strategy CAGR | Strategy DD | Strategy Sharpe | TQQQ CAGR | TQQQ DD | TQQQ Sharpe |
|---|---:|---:|---:|---:|---:|---:|
| Full 2016–2023 | 40.0% | 53.0% | 0.95 | 36.0% | 81.7% | 0.80 |
| Ex-2020 | **24.7%** | 53.0% | 0.72 | **27.8%** | 81.7% | 0.71 |
| Ex-2022 | 55.8% | 53.0% | 1.20 | 77.8% | 69.9% | 1.24 |
| Ex-2020 & 2022 | 38.3% | 53.0% | 0.97 | 73.0% | 58.0% | 1.32 |

This is the clearest statement of what the strategy is. Without 2020 it does
**not** beat TQQQ on CAGR (24.7% vs 27.8%), but it delivers the same Sharpe with
29 pp less drawdown. Without both crash years it badly lags TQQQ on CAGR (38.3%
vs 73.0%) while still cutting the DD. It is a crash hedge, not an all-weather
alpha source.

**This triggers pre-registered falsifier #2** (ex-2020 CAGR ≤ 36.72%). The
stated full-window bar is still met, but the honest description is a
**2020-dependent qualified pass**, not a broad CAGR win. Falsifiers #1, #3, #4,
#5 and #6 are not triggered: the headline passes, 7/8 grid cells pass, the
placebo DD reduction is not matched, the cut tests are identical, and the rule
is not the old SMA/stop strategy.

## 6. Where it fails

1. **V-shaped recoveries.** The 10-day-high re-entry is too slow when the
   recovery starts immediately. 2016 is the worst case: the archive starts
   2016-01-04, so the first 10 sessions are default TQQQ and the January
   drawdown is unprotected; the Brexit exit on 2016-06-27 (QQQ 95.3) re-entered
   on 2016-07-08 (QQQ 102.8), missing an 8% QQQ / ~25% TQQQ rebound. The
   November 2016 Trump rally produced a similar whipsaw. 2016 finished −21.6%
   versus TQQQ +19.9%.
2. **Choppy bear markets.** 2018 is the failure: the strategy exited on
   2018-10-10, re-entered on 2018-11-07, exited again on 2018-11-19, and
   re-entered on 2018-11-28. It avoided only 4.0 pp of the 56.0 pp TQQQ
   drawdown and lost 38.3% versus TQQQ's 19.6%. The 10-day-high rule buys the
   first bear rally, which is often the trap.
3. **Grinding 2022 bear.** The strategy was in BIL 60.2% of the year and still
   lost 33.0% (DD 54.9%). The repeated re-entries in February, March, May, July,
   August, September and December were whipsaws. It avoided 27.2 pp of the
   82.1 pp TQQQ decline, but a 55% drawdown is not a safe profile in absolute
   terms.
4. **False alarms in bull years.** 50% of spells had TQQQ up, average cost
   +9.1%. 2021 (−51.2 pp relative) and 2023 (−44.9 pp relative) are the clearest
   examples. Every de-risking episode in a strong uptrend is a drag.
5. **Late at the top.** The rule needs a 5% QQQ drawdown and a deepening
   drawdown. It cannot sell the top; the first ~19% of TQQQ damage in 2020 and
   ~16% in 2022 was paid before the exit. It also cannot protect the first
   overnight gap of a crash.
6. **2020 concentration.** The full-window CAGR pass is a 2020 payoff. The
   placebo CAGR percentile (87.8th) and the ex-2020 shortfall (24.7% vs 27.8%)
   say the return edge is not broad-based.

## 7. Relation to existing work

Checked `research/revisit` and `research/agents*` (and the parallel
`research/new` mandates) before writing. This is not a copy of any of them:

- **`drawdown-regime` / `revisit/drawdown-regime`:** exits on the *level* of QQQ
  drawdown from a 52-week high on top of the 165-day SMA + 4% stop. This uses
  drawdown *velocity*, vol acceleration and gap stress, has no SMA and no stop.
- **`vol-scaled-crash-stop`:** ATR-scaled 4% intraday stop. This has no stop.
- **`overnight-crash-filter`:** overnight-only / first-hour TQQQ with a 20-day
  vol filter. This holds all day; gap stress is one vote in a composite, not the
  whole strategy.
- **`ml-crash-overlay-winner` / `revisit/ml-crash-overlay-winner`:** walk-forward
  logistic classifier on a 165-day SMA base. This is deterministic, no ML, no
  slow MA.
- **`event-risk-overlay`:** FOMC/CPI/OpEx calendar events. This is price/vol
  based, not calendar based.
- **`stop-reentry-recovery`:** post-4%-stop same-day re-entry. This has no stop
  and no same-day re-entry.
- **`daily-regime-minute-entry`:** 165-day SMA with minute execution. This has
  no slow MA.
- **`research/new/vol-of-vol-timing`:** vol-of-vol risk-state timing with a
  V-recovery re-risk. This uses drawdown acceleration + gap stress + vol
  acceleration and a 10-day price high, not a vol-of-vol state.
- **`research/new/fast-trend-vol`:** fast adaptive trend + vol target. This has
  no trend filter and is default-long TQQQ.
- **`research/new/overnight-drift-filter`:** overnight-only drift. This holds
  overnight and intraday.
- **`research/new/cross-asset-momentum`, `relative-value-tqqq`,
  `macro-event-tqqq`, `orb-tqqq-volume`, `ml-regime-v2`:** different mechanisms;
  none uses this drawdown-acceleration + gap-stress composite.

No code or parameters were copied. The only shared component is `research/bt.py`
for fills and marks, as required.

## 8. Honest verdict

**Pass on the letter of the bar:** 40.38% CAGR > 36.72%, 54.86% max DD < 82.29%
(and < 60%), 0.965 Sharpe > 0.82, at 1/5/10 bp. The signal is causal (cut tests
identical), the grid is a plateau (7/8 cells pass, DD stable at 52.6–54.0%), and
the drawdown reduction is not a random-exposure artifact (0th percentile vs 500
placebo shifts).

**But do not read it as a broad replacement for TQQQ.** The return edge is a
2020 crash-hedge payoff: ex-2020 CAGR is 24.7%, below TQQQ's 27.8%, with the
same Sharpe and 29 pp less DD. The CAGR edge is only 87.8th percentile against
random timing, and 20.6% of random shifts also beat the bar. The strategy
underperforms TQQQ in five of eight calendar years and has a 50% false-alarm
rate on defensive spells. Its correct use is as a **crash overlay / risk-reduction
sleeve on a TQQQ core**, not as a standalone all-weather alpha strategy.

If the priority is the lowest drawdown rather than the full-window CAGR, the
**15-day re-entry variant** is the better risk profile: 38.57% / 49.74% / 0.957
at 1 bp, 37.12% / 50.66% / 0.933 at 10 bp, still above the bar, with a lower DD
but a worse ex-2020 (21.7%). The 10-day core is the better full-window candidate;
the 15-day is the more defensive one.

**Bottom line:** a real, interpretable crash early-warning overlay that clears
the stated development bar and cuts the max drawdown by 27 pp, with a robust
risk improvement but a 2020-concentrated return edge. Report it as a qualified
pass, not a free lunch.
