# Cross-market spillover / lead-lag — development report

**Family:** `family-lead-lag-spillover`
**Window:** 2016-01-04 .. 2023-12-29 (development only; 2024-2026 never loaded)
**Engine:** `research/bt.py`, 1-minute marks, next-open fills, 2% band
**Headline cost:** 1 bp; also 0 bp gross, 5 bp and 10 bp
**Verdict:** **NEGATIVE on the family hypothesis — do not promote as a new
family.** The stand-alone 1-session strategy is a decent low-drawdown sleeve,
but it fails the 36.72% CAGR bar, the orthogonalised residual is not
significant, and QQQ's own intraday signal is at least as good. This is
common-factor short-term reversal, not an incremental cross-market spillover.

---

## 1. What was tested

The hypothesis has two layers:

- **Weak / tradable:** SPY's prior-session return negatively predicts QQQ's
  next-session return (common-factor short-horizon reversal).
- **Strong / novel:** the information survives orthogonalising SPY's move to
  QQQ's contemporaneous move. If it does, the effect is a genuine cross-market
  spillover rather than QQQ reversal seen through a proxy.

The close-to-close return decomposes into an overnight gap and an intraday
move. With next-open fills the gap into the next session is not tradable, and
the data show the gap is where most of the *un*tradable predictability sits.
The primary therefore uses **SPY's intraday return, open-to-close**.

### Exact decision clock

```
At the 16:00 ET close of session d:
    spy_open_adj[d] = SPY open[d] * SPY adjclose[d] / SPY close[d]
    s_id[d]         = SPY adjclose[d] / spy_open_adj[d] - 1        # intraday
    z[d]            = s_id[d] / stdev(s_id[d-20 .. d-1], ddof=1)

    event : z[d] <= -0.50
    entry : TQQQ 1.0 at the 09:30 open of session d+1
    exit  : TQQQ 0.0 at the 15:59 open of session d+1
    idle  : BIL 1.0
```

SPY and QQQ both close at 16:00, so `s_id[d]` is fully known before the order.
The first ~20 sessions are warm-up and produce no signal. A run of consecutive
events keeps the position open; the minimum hold is one session. `hold=2`
extends the exit to the 15:59 open of `d+2`.

### Alignment

The QQQ 1-minute calendar is the base. Every one of the 2,012 dev sessions has
a SPY and QQQ daily row (asserted at load). SPY's daily open is multiplied by
the same-day `adjclose/close` factor so the overnight/intraday split is
dividend-consistent. The residual uses a rolling 60-session beta of SPY
intraday on QQQ intraday, estimated strictly through `d-1`.

`bt` executes a target written on bar `i` at bar `i+1`'s open. The weight array
therefore writes the entry target on the 15:59 bar of session `d`; the actual
fill is the next session's 09:30 open, after the 16:00 signal is known. The
15:59 write is bookkeeping, not an earlier decision, and no fill occurs between
the 15:59 bar and the next open.

No 100-250 day trend gate, no volatility targeting, no drawdown/capitulation
event, no calendar window, no opening-range/close-flow signal, no ML, and no
QQQ/SPY ratio-momentum gate.

---

## 2. Headline development results

Primary: `spy_intraday, vol_window=20, thr=0.50, hold=1, BIL idle`.

| cost | CAGR | max DD | Sharpe | Sortino | vol | daily Sharpe | fills | turnover | ending equity |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 bp gross | 32.39% | 35.37% | 0.985 | 1.435 | 34.66% | 1.009 | 1,505 | 6,831x | $939,463 |
| **1 bp** | **29.92%** | **36.57%** | **0.931** | **1.356** | **34.66%** | **0.953** | **1,505** | **6,182x** | **$808,199** |
| 5 bp | 20.48% | 41.16% | 0.712 | 1.036 | 34.66% | 0.729 | 1,505 | 4,206x | $442,663 |
| 10 bp | 9.64% | 46.44% | 0.439 | 0.638 | 34.69% | 0.443 | 1,505 | 2,690x | $208,577 |

- **Entries / exits:** 376 / 376 (nothing open at the end).
- **Average holding period:** 1.34 sessions (504 held sessions).
- **TQQQ exposure:** 25.0% of clock time. The engine's `exposure` field is
  100% because BIL is a held asset; use `tqqq_exposure` for the risky share.
- **Turnover** is start-equity-normalised and therefore inflated by the ~8x
  equity growth; the average fill is ~4.1x the starting equity. 1,505 fills
  over 376 entries is 4.0 fills per entry (TQQQ entry/exit plus the BIL legs).
- **Drawdown window:** daily peak 2022-10-06 to trough 2022-12-16, -30.9% on
  daily closes; the minute-marked max DD is 36.6%.

The headline Sharpe/vol use the repo's minute-bar convention (`252*390`). The
daily-return Sharpe is 0.953, so the result is not a minute-bar artefact.

### Benchmarks on the same panel and window

| | CAGR | max DD | Sharpe | vol | ending equity |
|---|---:|---:|---:|---:|---:|
| TQQQ buy & hold | 36.15% | 82.29% | 0.801 | 66.55% | $1,175,165 |
| QQQ buy & hold | 18.91% | 37.30% | 0.900 | 22.02% | $398,628 |
| Brief TQQQ bar | 36.72% | 82.29% | 0.82 | — | — |

The primary **fails the CAGR bar** (29.92% < 36.72%), **passes the drawdown
bar** (36.57% < 82.29%), and **passes the Sharpe bar** (0.931 > 0.82). It also
fails the CAGR bar even at **0 bp gross** (32.39%).

---

## 3. Subperiods and yearly path

| subperiod | CAGR | max DD | daily Sharpe |
|---|---:|---:|---:|
| 2016-2019 | 24.70% | 29.50% | 0.988 |
| 2020-2021 | 74.45% | 19.40% | 1.592 |
| 2022-2023 | 4.90% | 30.90% | 0.314 |

| year | strategy | TQQQ B&H |
|---|---:|---:|
| 2016 | +24.64% | +18.63% |
| 2017 | +14.76% | +112.96% |
| 2018 | +33.56% | -23.52% |
| 2019 | +8.21% | +130.48% |
| 2020 | +127.87% | +99.82% |
| 2021 | +24.43% | +90.88% |
| 2022 | +4.71% | -79.70% |
| 2023 | +32.18% | +204.89% |

The strategy is positive in every year and every subperiod, but the edge is
concentrated in 2020-2021 and decays sharply in 2022-2023 (4.9% CAGR, 0.314
daily Sharpe). That is a real fragility, not a drawdown artefact: 2022-2023 is
still positive but only barely compensates for the risk.

---

## 4. Parameter plateau

### 4.1 Threshold × holding clock (SPY intraday)

Sharpe (minute convention):

| thr | hold=1 | hold=2 |
|---:|---:|---:|
| 0.25 | 0.751 | 0.795 |
| 0.50 | 0.931 | 0.972 |
| 0.75 | 0.769 | 0.920 |
| 1.00 | 0.870 | 0.693 |

Local neighbours around the centre:

| thr | hold | CAGR | max DD | Sharpe | entries | fills | TQQQ exp |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.40 | 1 | 30.8% | 44.5% | 0.921 | 413 | 1,649 | 28.8% |
| 0.45 | 1 | 31.9% | 44.1% | 0.959 | 397 | 1,585 | 26.9% |
| **0.50** | **1** | **29.9%** | **36.6%** | **0.931** | **376** | **1,505** | **25.0%** |
| 0.55 | 1 | 26.4% | 36.3% | 0.858 | 361 | 1,445 | 23.8% |
| 0.60 | 1 | 26.9% | 39.1% | 0.884 | 344 | 1,377 | 22.2% |
| 0.40 | 2 | 34.0% | 56.4% | 0.842 | 291 | 1,161 | 49.3% |
| 0.45 | 2 | 31.8% | 57.8% | 0.816 | 283 | 1,129 | 46.6% |
| 0.50 | 2 | 41.0% | 49.5% | 0.972 | 276 | 1,105 | 43.8% |
| 0.55 | 2 | 40.8% | 45.0% | 0.976 | 265 | 1,061 | 41.7% |
| 0.60 | 2 | 41.7% | 42.6% | 1.004 | 257 | 1,029 | 39.3% |

The one-session clock has a usable local plateau (0.86-0.96 Sharpe at
0.40-0.60) but is not smooth: 0.75 dips to 0.769 and 0.25 is 0.751. The
two-session clock is smoother at 0.50-0.60 (0.97-1.00) and is the only part of
the plateau that clears the return bar.

### 4.2 Volatility window (primary cell)

| vol window | CAGR | max DD | Sharpe | entries | fills |
|---:|---:|---:|---:|---:|---:|
| 10 | 17.9% | 48.7% | 0.642 | 378 | 1,509 |
| **20** | **29.9%** | **36.6%** | **0.931** | **376** | **1,505** |
| 40 | 31.2% | 32.7% | 0.957 | 362 | 1,449 |
| 60 | 26.3% | 46.3% | 0.842 | 352 | 1,409 |

20-60 is a reasonable plateau; 10 is clearly too noisy. 40 is marginally
better than the pre-registered 20.

### 4.3 Signal construction (at thr=0.50, hold=1)

| signal | CAGR | max DD | Sharpe | daily Sharpe | fills | TQQQ exp |
|---|---:|---:|---:|---:|---:|---:|
| SPY intraday (primary) | 29.9% | 36.6% | 0.931 | 0.953 | 1,505 | 25.0% |
| SPY close-to-close | 21.1% | 64.9% | 0.717 | 0.750 | 1,421 | 23.9% |
| QQQ intraday | 31.5% | 37.8% | 0.968 | 1.000 | 1,525 | 25.3% |
| SPY residual (rz) | 15.7% | 51.2% | 0.597 | 0.603 | 1,541 | 26.8% |

The close-to-close version is much weaker, which is consistent with the
overnight gap being the main locus of the untradable predictability. The
residual version is clearly weaker, which is the central negative result.

---

## 5. Falsifiers and controls

### 5.1 The two that matter

| control | CAGR | max DD | Sharpe | fills | verdict |
|---|---:|---:|---:|---:|---|
| **QQQ's own intraday signal** | **31.5%** | **37.8%** | **0.968** | 1,525 | beats SPY on all three |
| **SPY residual (orthogonalised)** | 15.7% | 51.2% | 0.597 | 1,541 | no edge |

QQQ's own intraday z does at least as well as SPY's (Sharpe 0.968 vs 0.931,
CAGR 31.5% vs 29.9%, DD 37.8% vs 36.6%). The orthogonalised residual is
insignificant on the tradable return: the next-session open-to-close regression
coefficient on `rz_id` is about -2.3 bp per sd with t = -0.84 (HAC, 5 lags).
The close-to-close version, which includes the untradable overnight gap, is
stronger (-5.7 bp per sd, t = -1.83) but still only marginal and not tradable
with next-open fills. The residual-only strategy earns a 0.597 Sharpe and turns
negative at 10 bp. The strong "cross-market beyond QQQ" hypothesis is therefore
**falsified**.

### 5.2 Other controls

| control | CAGR | max DD | Sharpe | entries | fills | note |
|---|---:|---:|---:|---:|---:|---|
| residual confirmation (`res_id<0`) | 25.4% | 35.8% | 0.912 | 274 | 1,097 | lower DD, no Sharpe gain |
| stale signal (one session) | 4.3% | 58.4% | 0.296 | 376 | 1,505 | edge decays |
| no deadband (thr=0) | 26.8% | 58.2% | 0.772 | 504 | 2,017 | worse |
| cash idle instead of BIL | 29.6% | 37.3% | 0.924 | 376 | 752 | halves fills, slightly lower CAGR |

The signal-day event study: TQQQ's next-session open-to-close return averages
**+47.7 bp** on signal days versus **+10.0 bp** unconditional. On the signal
day itself TQQQ averages **-351.9 bp**, so the strategy is buying after a large
intraday decline, not chasing strength.

### 5.3 Holding-clock variants

| variant | 1 bp CAGR | 1 bp DD | 1 bp Sharpe | 5 bp CAGR | 10 bp CAGR | corr with short-reversal | clears bar? |
|---|---:|---:|---:|---:|---:|---:|---|
| **1 session, intraday (primary)** | 29.9% | 36.6% | 0.931 | 20.5% | 9.6% | 0.487 | no (CAGR) |
| 2 sessions, intraday exits | 41.0% | 49.5% | 0.972 | 33.4% | 24.5% | 0.687 | **yes at 1 bp** |
| 1 session, hold to next open | 41.5% | 39.5% | 1.077 | 31.2% | 19.4% | 0.574 | **yes at 1 bp** |

The two-session and next-open variants clear the brief's bar at 1 bp. They are
not the pre-registered primary, and their extra return is mostly extra
exposure / overnight capture:

- The two-session variant raises TQQQ exposure from 25.0% to 43.8% and its
  correlation with `family-short-reversal` from 0.487 to **0.687**, close to
  the 0.70 redundancy line.
- The next-open variant holds one extra overnight per episode. TQQQ's
  overnight return after held sessions averages +20.0 bp versus +11.1 bp
  unconditional, but QQQ's overnight after held sessions is *lower* than
  unconditional (+1.3 bp vs +4.0 bp). The overnight gain is therefore a
  TQQQ leverage/financing artefact, not a QQQ effect.

Both variants also have a weak 2022-2023: 0.377 and 0.327 daily Sharpe,
respectively.

---

## 6. Placebo / randomisation

Two tests:

1. **Exact circular shift** of the daily signal by 24 non-round offsets
   (13..401 sessions), rebuilt and re-run through `bt`. Real Sharpe 0.931,
   placebo mean 0.275, placebo max 0.693, **p = 0.040**. Real CAGR 29.9%,
   placebo mean 4.0%, placebo max 17.4%.
2. **Random-event placebo:** 1,000 draws of the same number of held sessions
   (504) at random dates, daily open-to-close approximation with 2 bp costs.
   Real daily Sharpe 0.986, placebo mean 0.169, p95 0.643, **p = 0.002**,
   percentile 99.9%.

The timing is special relative to random dates. This does **not** rescue the
family: the QQQ-own-signal control shows the special timing is common-factor
reversal timing, not a unique SPY spillover.

---

## 7. Correlation with current family winners

Daily-return Pearson correlation over the dev window (2,011 overlapping days):

| winner | corr |
|---|---:|
| ratio-froth | 0.274 |
| vol-scaled-crash-stop | 0.346 |
| relative-value-tqqq | 0.428 |
| fomc-opex-window | 0.296 |
| family-session-timing | 0.302 |
| **family-short-reversal** | **0.487** |
| family-rebalance-flow | 0.471 |
| family-intraday-microstructure-day | 0.286 |
| family-ml-microstructure | 0.430 |
| TQQQ buy & hold | 0.492 |

Range versus the nine winners: **0.274 .. 0.487**. No winner exceeds the 0.70
redundancy threshold, but the highest is the existing short-reversal family,
which is exactly the conceptual overlap. The two-session variant reaches 0.687
with short-reversal, i.e. near-redundant.

The winner curves were read from `research/new/curves/*.json` and truncated to
`date <= 2023-12-29` before any return was computed; no 2024-2026 value is used.

---

## 8. Cost and turnover

The strategy is very cost-sensitive because it takes 376 round trips in eight
years and pays four fills per entry (TQQQ and BIL legs):

| cost | CAGR | cost drag vs gross |
|---|---:|---:|
| 0 bp | 32.39% | — |
| 1 bp | 29.92% | -2.47 pp |
| 5 bp | 20.48% | -11.91 pp |
| 10 bp | 9.64% | -22.75 pp |

At 10 bp the CAGR is still positive (9.6%), so the pre-registered cost kill is
not triggered, but the edge is thin. The cash-idle variant halves the fills to
752 and earns 19.1% at 10 bp, which is a cleaner cost profile; it is reported
as a control, not the primary, because the repo convention is BIL idle.

The gross CAGR (32.39%) is still below the 36.72% bar. The primary does not
clear the bar even before costs.

---

## 9. Kill-criteria scorecard

| criterion | result | pass? |
|---|---|---|
| Activity: >= 100 fills, >= 30 episodes | 1,505 fills, 376 episodes | **pass** |
| 1 bp Sharpe >= 0.82 | 0.931 | **pass** |
| 1 bp CAGR >= 20% | 29.92% | **pass** |
| Positive CAGR at 10 bp | 9.64% | **pass** |
| No negative subperiod CAGR | all three positive | **pass** |
| 2022-2023 daily Sharpe > 0.2 | 0.314 | **pass (barely)** |
| Circular-shift p <= 0.10 | 0.040 | **pass** |
| Random-event p <= 0.10 | 0.002 | **pass** |
| Residual t <= -1.5 | t = -0.84 | **FAIL** |
| SPY not dominated by QQQ's own signal | QQQ Sharpe 0.968 > 0.931 | **FAIL** |
| Max winner corr <= 0.70 | 0.487 (1-session) | **pass** |
| Brief bar: CAGR >= 36.72%, DD <= 82.29%, Sharpe >= 0.82 | 29.92% / 36.57% / 0.931 | **FAIL (CAGR)** |

**Overall: fail.** Two independent failures — the strong cross-market
hypothesis and the headline return bar. The return bar is cleared only by the
two-session or next-open variants, which are exposure/overnight variants of
the same common-factor reversal.

---

## 10. Verdict and recommendation

**Do not promote `family-lead-lag-spillover` as a new family.**

What is true:

- SPY's prior-session intraday decline has a real next-session QQQ/TQQQ bounce:
  +47.7 bp versus +10.0 bp unconditional on TQQQ, 376 episodes over eight
  years, and the timing beats both circular-shift and random-event placebos.
- The stand-alone 1-session TQQQ strategy is a low-drawdown sleeve: 29.9% CAGR,
  36.6% max DD, 0.931 Sharpe, 25% TQQQ exposure at 1 bp. It is not correlated
  above 0.49 with any current winner.
- It is positive in every subperiod and every year.

What is not true:

- The orthogonalised SPY residual has no reliable edge (Sharpe 0.597,
  t = -0.84). The effect is the common factor, not an incremental SPY lead.
- QQQ's own intraday signal is at least as good (0.968 Sharpe, 31.5% CAGR,
  37.8% DD). SPY is a proxy, not a superior information source.
- The pre-registered 1-session clock does not clear the 36.72% CAGR bar even
  gross (32.39%) and is very cost-sensitive.
- The two variants that do clear the bar are not clean tests of the hypothesis:
  the 2-session version is 0.687 correlated with `family-short-reversal` and
  the next-open version harvests an overnight effect that is absent in QQQ.

Recommendation: keep the result as a documented negative. If the lead wants a
low-drawdown diversifying sleeve, the 1-session cash-idle variant (29.6% CAGR,
37.3% DD, 0.924 Sharpe, 752 fills) is the cleanest expression, but it is a
repackaged short-term reversal, not a new family, and it still misses the CAGR
bar.

---

## 11. Limitations

- **Single market pair.** Only SPY/QQQ is available at daily/hourly resolution;
  there is no cross-country or cross-asset test. A broader spillover family
  (e.g. ES/NQ futures, sector ETFs) is not testable with this panel.
- **In-sample sign selection.** The negative sign and the intraday
  decomposition were fixed from the dev-window event study. The holdout is the
  only out-of-sample check and was not touched.
- **Minute vs daily marking.** Headline Sharpe/vol/DD use the repo's minute-bar
  convention; the daily-return Sharpe (0.953) and daily max DD (30.9%) are
  slightly different. Both are reported.
- **Turnover convention.** `turnover` is start-equity-normalised and therefore
  inflated by the ~8x equity growth. The fill count and average trade size are
  more interpretable.
- **The 2022-2023 decay.** The 2022-2023 subperiod is only 4.9% CAGR / 0.314
  daily Sharpe. The holdout may be worse; the family should not be judged on
  the full-window average alone.
- **Winner curves.** The correlation analysis uses the repo's pre-computed
  daily curves, truncated at 2023-12-29. The curves are not regenerated from
  each strategy's code, so a stale curve would contaminate the correlation
  table (the summary stats in the winners' `result.json` were not used).
