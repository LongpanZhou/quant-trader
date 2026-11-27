# Repair report — stop-reentry-recovery → v2

**Status:** `passed_dev` (7 of 7 pre-registered checks).
**Development window:** 2016-01-04 → 2023-12-29. **Holdout 2024-2026:**
outside the analysis panel, not inspected.
**Original:** `research/revisit/stop-reentry-recovery/`
**New code:** `strategy.py` · **Pre-registration:** `HYPOTHESIS.md` · **Raw
numbers:** `result.json`

---

## 1. The original: one event, five fills, eight years

The original signal required both

```
r_t   = TQQQ intraday open→close <= -3%
excess = r_t - 3 * QQQ intraday      <= -1pp
```

Development counts (2012 sessions):

| Component | Days |
|---|---:|
| `r_t <= -3%` | 282 |
| `excess <= -1pp` | 3 |
| both | **1** |

The intraday tracking residual `r_t - 3*r_q` has a standard deviation of
**0.1214 pp**. A 1 pp underperformance is **8.3σ**; it is not a signal, it is
the far tail of a very tight distribution. The three days that cleared it were:

| Date | TQQQ intraday | QQQ intraday | Excess | h1 raw | h3 raw | h5 raw |
|---|---:|---:|---:|---:|---:|---:|
| 2020-03-12 | −10.05% | −2.66% | −2.08pp | +9.13% | −17.13% | −23.29% |
| 2020-03-13 | +9.13% | +3.72% | −2.03pp | −8.04% | −2.71% | −12.17% |
| 2020-03-17 | +10.03% | +3.77% | −1.27pp | +8.48% | −2.07% | +20.30% |

Two of the three are **up days**: TQQQ rose 9–10% but lagged 3× QQQ because of
volatility decay. The `r_t <= -3%` leg excludes them, leaving 2020-03-12. The
one event entered on 2020-03-13, the 2% stop fired the same session, and the
+9.13% close was missed. The old development result (1 bp CAGR 1.25%,
DD 1.81%, Sharpe 0.80, 5 fills) is essentially BIL plus one stopped trade; it is
not evidence of a strategy.

The forward **excess** returns after the three days are negative at every
horizon (h3 −9.13/−6.62/−0.52pp; h5 −8.44/−6.30/−1.64pp). The relative
tracking-error overshoot does not reverse. The original mechanism is falsified,
not merely mis-scaled.

## 2. What was changed

The repair keeps the "large downside overshoot" idea but normalizes the drop by
TQQQ's own trailing volatility, which is measurable and regime-adaptive:

```
r_t   = TQQQ_close[d] / TQQQ_open[d] - 1
sd20  = std(r_t[d-20 .. d-1])
z     = r_t / max(sd20, 0.005)          # 0.5pp floor
event = (r_t <= -5.0%) AND (z <= -2.0)
```

Repaired component counts:

| Component | Days |
|---|---:|
| `r_t <= -5%` | 127 |
| `z <= -2` | 89 |
| both | **56** |

**Primary execution:** buy 100% TQQQ at the next session's 09:31 open, sell at
the same session's 15:59 open (one-session hold), otherwise 100% BIL. No stop:
a stop cannot act before a one-session clock exit.

The original 3-session 50%→100% scale-in with a 4% daily-close stop is grid
cell 8, so the structural change is measured, not assumed. (The old 2%
minute-close stop is less than one daily sigma; it stops out a large fraction
of the sample.)

**Why one session:** the reversal is concentrated in the first session. The
correctly aligned event means from the next open are +1.98% (h1), +2.62% (h3)
and +5.15% (h5), i.e. +1.98%/day, +0.87%/day and +1.03%/day. The h1 version also
has a lower drawdown than the full-size h3/h5 structures. The h3/h5 holds add
beta and crash exposure, not edge.

**Alignment:** the signal uses session *d*'s open and close and is placed on
the 15:59 bar of *d*; the fill is the next bar (09:31 of *d+1*). The exit is
placed on the 15:58 bar and filled at the 15:59 open. No 2024+ bar is requested
or read.

## 3. Development result

| Cost | CAGR | Max DD | Sharpe | Sortino | Fills | Turnover | TQQQ exposure | End equity |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 bp | **14.50%** | **17.39%** | **0.96** | 1.41 | 225 | 393× | 2.76% | $294,825 |
| 5 bp | 13.22% | 17.64% | 0.89 | 1.30 | 225 | 373× | 2.76% | $269,450 |
| 10 bp | 11.63% | 18.14% | 0.80 | 1.16 | 225 | 350× | 2.76% | $240,780 |

The exposure figure is the fraction of minutes with a TQQQ weight. The
strategy's `bt.stats` "exposure" is ~100% because BIL is a security; that is not
the relevant number here. The strategy is long TQQQ on **56 sessions out of
2012** (2.8%) and in BIL otherwise.

Turnover is high because the 100% target is rebalanced whenever intraday drift
exceeds the 2% band; the 10 bp ladder still leaves 11.6% CAGR, so the result is
not cost-fragile at the requested cost levels.

### Sub-periods

| Period | CAGR | Max DD | Sharpe | TQQQ exposure |
|---|---:|---:|---:|---:|
| 2016-2019 | +12.47% | 13.28% | 0.98 | 2.34% |
| 2020-2021 | +17.63% | 17.39% | 0.85 | 4.35% |
| 2022-2023 | +15.60% | 10.92% | 1.41 | 1.99% |

All three are positive. The 17.39% overall drawdown is a single crash episode
(the same value appears in many grid cells); the half-size variant cuts it to
8.96%. The full yearly path is positive in every calendar year: 9.2%, 7.6%,
21.2%, 12.2%, 22.0%, 13.3%, 21.6%, 9.6% (2016→2023).

## 4. Event study (56 signals)

| Horizon | n | Mean | Median | Win | t | Bootstrap p | Mean ex-top-5 | Excess vs 3×QQQ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| h1 | 56 | **+1.982%** | +1.651% | 71.4% | **2.99** | 0.0006 | +0.947% (t 1.94) | +0.055pp |
| h3 | 56 | +2.616% | +2.054% | 66.1% | 2.29 | 0.0088 | +0.921% (t 0.98) | −0.076pp |
| h5 | 56 | +5.147% | +5.533% | 76.8% | 3.76 | 0.00015 | +3.470% (t 2.73) | −0.185pp |

The h1 bootstrap 95% CI is [+0.74%, +3.32%] and excludes zero. The edge is not
a single-year artifact: h1 means are +3.21% (2016), +1.06% (2017), +1.52%
(2018), +2.56% (2019), +1.90% (2020), +1.58% (2021), +2.95% (2022), +2.50%
(2023). It does weaken when the five best events are removed (+0.95% mean,
t 1.94), so the top tail matters.

**Honest caveat — the edge is mostly beta.** The h1 excess return versus 3× QQQ
is only **+0.055pp**, and at h3/h5 it is negative. Almost all of the +1.98% is
the QQQ rebound (3× ≈ 1.93pp), not TQQQ-specific overshoot. The v2 is therefore
a volatility-normalized **market dip-reversal** signal, not evidence that
leveraged-ETF rebalancing creates an exploitable tracking-error reversal. The
original relative-overshoot claim is dead; the surviving claim is narrower.

## 5. Pre-registered grid and plateau

| # | Cell | Signals | Entries | TQQQ exp. | CAGR | Max DD | Sharpe |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | **primary 5.0% / 2.0σ, h1** | 56 | 56 | 2.76% | **14.50%** | 17.39% | 0.96 |
| 2 | drop 4.0% | 71 | 71 | 3.50% | 14.38% | 17.39% | 0.93 |
| 3 | drop 4.5% | 67 | 67 | 3.30% | 13.99% | 17.39% | 0.91 |
| 4 | drop 6.0% | 43 | 43 | 2.11% | 12.01% | 17.39% | 0.85 |
| 5 | z −1.75 | 70 | 70 | 3.45% | 13.42% | 17.39% | 0.82 |
| 6 | z −2.25 | 43 | 43 | 2.13% | 9.65% | 17.39% | 0.74 |
| 7 | half size | 56 | 56 | 1.38% | 8.07% | 8.96% | 1.04 |
| 8 | original 3-session 50→100, 4% daily stop | 56 | 52 | 5.17% | 3.16% | 39.42% | 0.27 |

The plateau is broad: 43–71 signals and 9.6–14.5% CAGR across the drop/z grid.
There is no sign flip. Cell 8 is the key structural comparison: keeping the
old three-session scale-in and stop produces a higher exposure (5.2%) but less
than a quarter of the CAGR and more than twice the drawdown. The one-session
repair is the source of the improvement, not a lucky threshold.

The half-size cell has the best Sharpe (1.04) and a 9.0% drawdown. The primary
is the 100% version because it uses the signal when it fires; a risk-averse
implementation can use the half-size row without changing the signal.

## 6. Benchmarks, correlation, placebo

| Dev benchmark | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| Strategy (1 bp) | 14.50% | 17.39% | 0.96 |
| TQQQ buy-and-hold | 36.15% | 82.29% | 0.80 |
| QQQ buy-and-hold | 18.91% | 37.30% | 0.90 |
| BIL | 1.39% | 0.24% | 0.92 |
| 165-day QQQ SMA baseline *(reference only)* | 44.76% | 58.76% | 1.03 |

Daily-return correlation with the 165-day baseline is **0.126**. The strategy is
not a repackaged trend base. The placebo (200 random same-size event sets, same
hold and costs) has mean CAGR 1.10%, 95th percentile 5.76%, max 10.28%; the real
14.50% is at the 100th percentile (0/200 draws at or above).

## 7. Verdict

The HYPOTHESIS falsifiers are all satisfied:

1. **Too thin:** 56 entries (≥20).
2. **No forward edge:** h1 mean +1.98%, bootstrap p 0.0006.
3. **One-episode wonder:** ex-top-5 mean +0.95%; all three sub-periods positive.
4. **No risk compensation:** 10 bp CAGR 11.63% > BIL 1.39%.
5. **Cost fragility:** 10 bp CAGR 11.63% is positive and > half the 1 bp CAGR
   (7.25%).
6. **Not a plateau:** the drop/z grid is 43–71 signals and 9.65–14.50% CAGR
   with no sign flip.
7. **Placebo:** 100th percentile (0/200 random-event draws at or above).

The `result.json` `verdict.checks` set (7/7) covers the same ground plus the
drawdown hard bar: max DD 17.39% < the 165-day baseline's 58.76%.

**The fix is honest, but it is a re-specification, not a rescue of the original
mechanism.** The original 1 pp relative-overshoot filter is an ~8σ artifact and
its forward excess returns are negative. The v2 keeps the "buy a large,
unusual TQQQ decline" idea and drops the impossible relative leg; what survives
is a low-exposure, one-session dip-reversal that is mostly QQQ beta. It should
be described that way, not as leveraged-ETF rebalancing alpha.

Caveats a reviewer must keep:

1. **2.76% exposure.** The 14.50% CAGR is earned on a small slice of time; it is
   not comparable to a fully invested equity strategy. The capital is in BIL
   97% of the time.
2. **Top-tail dependence.** Removing the five best events cuts the h1 mean to
   +0.95% (t 1.94). The edge survives but is not broad-based.
3. **One crash drawdown.** The 17.39% DD is a single episode; the half-size
   variant is 8.96%. Position sizing is the main risk decision.
4. **No LETF-specific alpha.** The h1 excess versus 3× QQQ is +0.055pp. The
   strategy times QQQ rebounds; it does not exploit a TQQQ tracking error.
5. **In-sample threshold choice.** The 5%/2σ primary was selected after the
   development event study; the 8-cell grid is the confirmatory plateau, not an
   independent sample. The 2024-2026 holdout is the only untouched test.

No holdout was inspected. The lead's single 2024-2026 run is the next step; it
is a confirmation, not a new search.

## 8. Reproduction

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
python research\new\stop-reentry-recovery-v2\strategy.py
```

Writes `result.json` in this directory. All timings, fills and costs come from
`research/bt.py` (next-open fills, 2% band, 1/5/10 bp).

## Appendix — entry dates (56)

2016-02-08, 2016-09-12, 2016-11-11, 2017-03-22, 2017-05-18, 2017-06-12,
2017-08-18, 2017-12-05, 2018-02-05, 2018-02-06, 2018-02-09, 2018-03-26,
2018-03-28, 2018-06-28, 2018-07-30, 2018-10-11, 2018-10-25, 2018-10-30,
2018-12-06, 2018-12-24, 2019-03-25, 2019-06-04, 2019-08-26, 2019-09-25,
2020-02-03, 2020-02-26, 2020-02-28, 2020-03-04, 2020-03-23, 2020-06-12,
2020-07-14, 2020-09-04, 2020-09-11, 2020-09-24, 2020-10-29, 2020-11-10,
2020-12-10, 2021-01-05, 2021-01-28, 2021-02-26, 2021-03-04, 2021-03-09,
2021-05-11, 2021-12-02, 2021-12-06, 2021-12-17, 2022-01-06, 2022-01-14,
2022-02-24, 2022-04-22, 2022-06-29, 2022-08-29, 2022-09-14, 2022-10-17,
2023-06-08, 2023-08-25.
