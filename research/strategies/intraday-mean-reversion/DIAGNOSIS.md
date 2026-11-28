# DIAGNOSIS: intraday-mean-reversion (PCSR), tune pass 2026-11-27

**This is post-holdout work.** The lead already ran the holdout once on the frozen
weights. Everything below uses the development window only (2016-01-04 → 2023-12-29).
The panel was loaded with `end=2023-12-29`, and no post-2023 number was computed,
printed or read. Scripts and raw outputs are in `scratch/tune_diag.py`, `scratch/tune_sweep.py`
and `scratch/tune_verify.py`, with their `.json` outputs alongside. The pre-tune files are in `_before_tune/`.

**Decision: UNCHANGED strategy.** The weights are bit-identical to the frozen version:
max |Δw| = 0, and both cut tests show 0 differing rows. I fixed one reporting bug in
`strategy.py`. It did not change the headline, but it did change the dev status gate's p-value from a meaningless
0.0 to 0.068.

## Step 1: spec vs code

| Rule (report §5) | Code | OK |
|---|---|---|
| prev close = last 1-min QQQ close of session k-1 | `prev[1:] = qqq[last[:-1]]` | yes |
| dd_k = min over session k's 1-min closes of close/prev − 1 | `dmin` over `first[k]..last[k]` | yes |
| event if dd_k ≤ −3.0 % (`<=`) | `dmin <= -threshold` | yes |
| entry: weight set at session k's last bar, fills at k+1's first open | `w[b, asset] = sess_w[k+1]` | yes (0 shape errors over 88 held sessions) |
| exit: 0 at k+1's second-to-last bar, fills at the 15:59 open | `w[b-1, asset] = 0` | yes (0 held weights on any second-to-last bar) |
| never overnight; consecutive events are separate trades | flat at b-1, re-enter at b | yes |
| sessions by bar index (half days, short sessions) | `first/last` from dates | yes. Dev has 15 half days (211 bars) and 6 short sessions (340–381 bars), all handled. |
| weights finite, ≥ 0, row sum ≤ 1; no shorts | checked | yes (min 0, max row sum 1.0) |
| no look-ahead | cut test by truncating the 1-min arrays at 2020-03-12 11:07 / 2022-09-13 10:41 | 409,457 and 654,956 bars compared, **0 differ** |

**Bug found (reporting, not weights).** In `session_features`, `F["d"]` holds one date per **bar**,
but `info["event_dates"]` and `event_returns()` indexed it with the **session**
number k. Every "event date" therefore came out as a date in 2016-01-04…12. The evidence is
`result.json → info.event_dates` and `event_study.events`. That had three consequences:

1. `cluster_bootstrap` saw every event within 7 days of the previous one, so it reported **1 cluster**, a degenerate
   CI and `p_mean_le_0 = 0.0`. The pre-registered status gate (p < 0.10) was never really tested.
2. `event_returns` ran over the whole panel, including the 2014–15 warm-up and the holdout. The 109
   "events" in `result.json` mix dev, warm-up and holdout sessions.
3. The fix indexes the per-bar dates with `first[k]` and restricts the event study to triggers and held sessions
   inside the dev window. The corrected dev numbers are 88 events, 43 clusters, mean +0.99 %, median +0.95 %,
   win rate 58 %, **p = 0.068**, 95 % CI [−0.26 %, +2.09 %]. The gate still passes, but only just,
   and the CI includes zero.

Other notes:
- The report's preliminary 17.12 % / 22.24 % came from an older harness (`scratch/dev_eval.py`). That harness
  **held overnight whenever two event sessions were consecutive** (12 pairs on dev). Rebuilding
  that rule on today's harness gives 14.72 % / 22.24 % (variant E below). The rest of the gap is data
  and harness drift: the half-day fix in `bt.load_1m` and the 09:30 vs 15:59 start. `strategy.py` implements the
  spec as written, with no overnight hold, so the 11.31 % headline is the correct one.
- `report.md` still carries the "PENDING / TBD" header from before the pause. The real numbers are in
  `AUDIT.md` and `result.json`.
- These are not bugs in my folder, but the lead should look at them: `run_holdout.py: bench()` labels the
  symbols the wrong way round (`("TQQQ","QQQ")[col == 1]`), so `benchmarks.holdout_tqqq.symbol == "QQQ"` and
  likewise for the `10y_*` and `5y_*` entries. Only the labels are wrong; the values belong to the right ETF.

## Step 2: the gap to TQQQ (dev, 1 bp)

Strategy: **11.31 % CAGR / 31.47 % DD / 0.58 Sharpe**. TQQQ: 35.98 % / 82.29 %. QQQ: 18.86 % / 37.30 %.
The old 165-day base: 44.77 % / 58.76 %.

**Exposure**

| | value |
|---|---|
| minutes in TQQQ | 4.35 % |
| minutes in BIL | 95.65 % |
| minutes in QQQ / synthetic short | 0 / 0 |
| sessions held | 88 of 2,011 (4.38 %) |
| average gross leverage (TQQQ = 3×) | 0.13× |

**Leverage-matched comparison**

| version | CAGR | DD | Sharpe |
|---|---|---|---|
| PCSR | 11.31 % | 31.47 % | 0.58 |
| static 4.35 % TQQQ / 95.65 % BIL (2 % band) | 3.88 % | 4.69 % | 1.21 |
| same, band 0 (rebalanced every bar) | 3.54 % | 5.44 % | 1.10 |
| 4.36 % TQQQ intraday in every session, flat overnight | 1.86 % | 3.99 % | 0.70 |

The signal adds about 7–9 pp/yr over a static mix at the same average exposure, so it does add something.
It does not win on risk, though. Its drawdown is far larger, because the exposure arrives in 100 % bursts during the most volatile days.
The static mix's Sharpe is inflated by BIL's near-zero volatility.

**Per year (calendar returns)**

| year | PCSR | TQQQ | QQQ | events |
|---|---:|---:|---:|---:|
| 2016 | −3.8 % | +18.6 % | +9.3 % | 7 |
| 2017 | +1.5 % | +118.4 % | +32.6 % | 1 |
| 2018 | +11.1 % | −19.6 % | −0.1 % | 16 |
| 2019 | +13.4 % | +133.1 % | +38.9 % | 5 |
| 2020 | **+99.8 %** | +109.6 % | +48.4 % | 26 |
| 2021 | +6.5 % | +83.0 % | +27.4 % | 5 |
| 2022 | −14.4 % | −79.1 % | −32.5 % | 28 |
| 2023 | +5.0 % | +198.4 % | +54.8 % | 0 |

**Where the gap comes from** (TQQQ log return in points per year on dev, total 30.7):

| component | log-pts/yr | captured by PCSR |
|---|---:|---|
| overnight gaps | **+19.6** | none (never held overnight by design) |
| intraday, on the 88 held sessions | +9.8 | yes |
| intraday, on the other sessions | −2.1 | no (avoided) |
| final 15:59 bar | +3.5 | no |

Of the 202 top-decile TQQQ days, PCSR held 20. Costs and turnover: 353 fills (about 44 a year) and turnover
of about 82× a year. CAGR is 11.80 % at 0 bp, 11.31 % at 1 bp, 9.36 % at 5 bp and 6.97 % at 10 bp, so costs take about 0.5 pp per bp.

**Core signal (88 dev events):** mean next-session TQQQ open→close is +0.99 % against +0.085 % unconditional, with a hit rate of
58–61 %. The cluster bootstrap gives p = 0.068 for mean ≤ 0, and p = 0.078 for the excess over unconditional.
A random-session placebo with the same count gives p = 0.004. By sub-period: 2016–19 +0.71 % (n=29), 2020–21 **+2.61 %**
(n=31), 2022–23 **−0.49 %** (n=28). Drop the Feb–Apr 2020 cluster and the mean falls to **+0.37 %**.

**Verdict.** The shortfall is mainly **structural, from low exposure**. The strategy holds TQQQ 4 % of the
time and never overnight, and overnight is where about two-thirds of TQQQ's dev return sits.
Even a perfect hit rate on 11 events a year could not compound like a 3× ETF held all the time.
Within that limited exposure, the signal itself is **moderate and concentrated**. One cluster (spring 2020)
accounts for most of the CAGR. The edge is negative in 2022–23, and the corrected bootstrap is only marginal (p = 0.068).
It is not a bug: the weights match the spec and pass the cut test. It is not costs either: costs take about 0.5 pp per bp.
What the strategy does offer is diversification. Its correlation with the 165-day base is 0.133, and it sits in BIL
95 % of the time.

## Step 3: variants tried (dev only, 1 bp unless noted)

16 variants in total: the frozen baseline plus 15 new. Sub-period figures are annualised CAGR. Corr is with the 165-day base.

| variant | n | CAGR | DD | Sharpe | 5 bp | 10 bp | 16–19 | 20–21 | 22–23 | corr |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A th 2.0 % | 226 | 6.20 % | 47.3 % | 0.35 | 1.5 % | −4.1 % | −6.3 % | 88.2 % | −23.1 % | 0.21 |
| A th 2.5 % | 149 | 11.08 % | 37.8 % | 0.53 | 7.8 % | 3.9 % | −2.0 % | 54.3 % | 2.7 % | 0.17 |
| **A th 3.0 % (frozen)** | 88 | **11.31 %** | **31.5 %** | **0.58** | 9.4 % | 7.0 % | 5.4 % | 46.0 % | −5.3 % | 0.13 |
| A th 3.5 % | 58 | 8.18 % | 31.5 % | 0.48 | 6.9 % | 5.4 % | 4.9 % | 22.7 % | 1.4 % | 0.12 |
| A th 4.0 % | 35 | 4.41 % | 31.5 % | 0.33 | 3.7 % | 2.8 % | 0.2 % | 12.4 % | 5.3 % | 0.14 |
| B vol-normalised k 1.5σ | 277 | 8.94 % | 45.5 % | 0.45 | 3.1 % | −3.9 % | −4.9 % | 59.9 % | −2.6 % | 0.30 |
| B k 2.0σ | 153 | 8.48 % | 19.1 % | 0.50 | 5.2 % | 1.2 % | 1.6 % | 32.0 % | 1.7 % | 0.22 |
| B k 2.5σ | 88 | 4.09 % | 22.0 % | 0.33 | 2.3 % | 0.0 % | −0.9 % | 21.1 % | −1.3 % | 0.19 |
| B k 3.0σ | 44 | 2.75 % | 18.8 % | 0.29 | 1.9 % | 0.7 % | 4.6 % | −0.9 % | 3.0 % | 0.16 |
| B k 3.5σ | 28 | 1.89 % | 26.5 % | 0.26 | 1.3 % | 0.6 % | 6.5 % | −7.6 % | 3.0 % | 0.11 |
| C exit after 60 min | 88 | 4.95 % | 14.2 % | 0.45 | 3.1 % | 0.9 % | 3.7 % | 12.0 % | 0.9 % | −0.05 |
| C exit after 120 min | 88 | 4.01 % | 27.8 % | 0.33 | 2.2 % | −0.1 % | 1.3 % | 11.3 % | 2.5 % | −0.01 |
| C exit after 210 min | 88 | 10.95 % | 24.1 % | 0.66 | 9.0 % | 6.6 % | 2.4 % | 37.2 % | 5.4 % | −0.00 |
| C exit after 300 min | 88 | 4.41 % | 31.4 % | 0.31 | 2.6 % | 0.3 % | 0.1 % | 14.5 % | 3.7 % | 0.07 |
| D enter at trigger 15:59, hold overnight + next session | 88 | 9.33 % | 38.0 % | 0.45 | 7.7 % | 5.6 % | 4.9 % | 44.7 % | −10.3 % | 0.23 |
| E hold overnight only between consecutive events (old harness) | 88 | 14.72 % | 22.2 % | 0.65 | 13.0 % | 10.8 % | 4.2 % | 54.9 % | 3.0 % | 0.19 |

Reading the table, with the ±1-step neighbourhood for each family:

- **Threshold (A):** 3.0 % is a **peak, not a plateau**. Its neighbours give 11.1 % and 8.2 %, but 2.5 % reaches that through
  2020–21 alone, and both 2.0 % and 4.0 % collapse. Every threshold except 4.0 % is driven by 2020–21.
  No threshold wins in all three sub-periods, so there is nothing to move to.
- **Volatility-normalised (B):** this is the natural "capitulation relative to normal" fix. It is worse everywhere on CAGR.
  k = 2.0 has a lower DD (19 %), but its neighbours are 8.9 % / 45 % DD and 4.1 %. That is a peak too. Rejected.
- **Exit timing (C):** the results jump around with no smooth pattern (5.0 / 4.0 / 11.0 / 4.4 / 11.3 % for 60/120/210/300 min/full). That is noise, not a
  reversal that finishes at some identifiable time. Rejected.
- **Overnight entry (D):** a direct test of the "the bounce is really the overnight gap" falsifier. Adding the
  trigger night lowers CAGR and raises DD, and 2022–23 falls to −10 %. This confirms the next-session-only design.
- **E (old-harness rule):** this is the only variant that beats the frozen one on all of CAGR, DD, Sharpe, costs and the three
  sub-periods. **I rejected it as overfitting.** It adds overnight exposure on only the 12 nights where the
  held session was itself a new capitulation. D tests the same kind of night on all 88 events, and it hurts.
  Keeping the subset where overnight happens to help is selection on n = 12, and there is no ±1-step neighbourhood to
  check against. It was also never pre-registered, and I am seeing it after the holdout.
- **Placebo / random control:** 5,000 random draws of 88 sessions, each held for one session, give a mean ≥ the event mean in 0.4 % of
  draws. The signal beats random timing, but the concentration in 2020 means the CAGR stands on few independent clusters.
- **Sizing:** the position is already 100 % TQQQ, with row sum ≤ 1 and no extra leverage allowed. The only remaining
  sizing levers scale down (the pre-registered V6 vol target and V7 cluster cap). They cut return and cannot close the gap.
  Filling the 95 % idle time with QQQ/TQQQ would not come from the idea, and it would raise correlation with the base, so I did not try it.

**Conclusion: no honest improvement exists.** The frozen rule stays.

## Final decision: UNCHANGED (reporting bug fixed)

| dev | before | after |
|---|---|---|
| 1 bp CAGR / DD / Sharpe | 11.31 % / 31.47 % / 0.576 | 11.31 % / 31.47 % / 0.576 |
| 5 bp CAGR / DD | 9.36 % / 31.58 % | 9.36 % / 31.58 % |
| 10 bp CAGR / DD | 6.97 % / 31.72 % | 6.97 % / 31.72 % |
| corr vs 165-day base | 0.133 | 0.133 |
| event study n / clusters / p | 109 / 1 / 0.000 (bug) | 88 / 43 / 0.068 |

`strategy.py` changed only in `info["event_dates"]`, `event_returns()` (session dates, dev-window
filter), the `notes` string and the console print (dev only). I did **not** re-run `main()`. It also computes
the 10y and 5y windows, which overlap the holdout, and the tune brief forbids me from computing those.
So `result.json` is still the lead's file, with the stale `event_study` block. To regenerate it, the
lead should run `strategy.py` and then `run_holdout.py`. The weights are identical, so every window will reproduce the stored numbers.
