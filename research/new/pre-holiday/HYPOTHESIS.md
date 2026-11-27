# Pre-holiday TQQQ — hypothesis and pre-registration

**Slug:** `pre-holiday`
**Programme:** new-strategy research, mandate "pre-holiday TQQQ"
**Window:** development only, 2016-01-04 → 2023-12-29. No 2024+ row is read.
**Bar:** TQQQ dev is 36.72% CAGR / 82.29% max DD / 0.82 Sharpe. Pass needs
CAGR > 36.72% **and** max DD < 82.29% (ideally < 60%).

---

## 1. Mechanism

The "pre-holiday effect" (Ariel 1990; Kim & Park 1994; Brockman & Turtle 2003)
is the observation that US equity returns on the last session before an
exchange holiday are positive more often and by more than an average session.
The usual explanations are:

* a short-horizon risk premium for holding inventory into a multi-day closure,
  when no hedging is possible;
* positive pre-holiday sentiment / low liquidity, so a modest flow imbalance
  moves prices;
* the absence of scheduled macro releases and, often, of option expiry.

If the effect is real and large enough, a 3× fund should amplify it: TQQQ is
QQQ daily return × ~3 minus financing and constant-leverage decay, so a
+0.3% QQQ pre-holiday session is roughly +0.9% on TQQQ before decay.

**Causal prior against the mandate.** TQQQ's dev CAGR is a *compounded* 36.72%
over ~2,012 sessions, i.e. about +0.16%/session of log return on average
(equivalent to 0.2095% arithmetic mean close-to-close). Nine holidays a year
give 9–27 held sessions, i.e. 3.6%–10.7% of sessions. To match a fully-invested
TQQQ from 10.7% of sessions the held sessions would have to earn **~11× the
unconditional daily drift**, about +1.8%/session of log return with a 3× fund.
Published pre-holiday premia are of order 10–30 bp per session on the *index*,
i.e. 30–90 bp on TQQQ. That is an order of magnitude short.

This is stated before the run because it is the most likely outcome: the effect
may be real and still be far too small to beat a buy-and-hold 3× fund. The
study is designed to answer both questions separately — (a) is there a
pre-holiday premium, and (b) can any member of this family clear the bar.

## 2. Precise rules

Universe: `QQQ`, `TQQQ`, `BIL` (the shared 1-minute adjusted archive). Signals
use only past data; weights are long-only and sum to 1.

For each **scheduled** NYSE holiday `H` in the dev window:

* `k` = index of the last session strictly before `H`.
* Hold TQQQ for sessions `k-back+1 … k` (`back` ∈ {1,2,3,5}).
* Entry: target set on the last bar of the preceding session, filled at the
  09:30 open of session `k-back+1`.
* Exit (primary, `hold_through`): target set on the last bar of session `k`,
  filled at the 09:30 open of the **first session after the holiday**. With
  next-open fills a daily strategy cannot leave a session at its close, so the
  position necessarily spans the holiday closure. This is the faithful
  implementation of "hold those sessions".
* Exit (alternative, `exit_1559`): target cleared on the penultimate bar of
  session `k`, filled at the 15:59 open, so the holiday gap is not held.
* BIL for the remainder (`1 - w_TQQQ`).

**Volatility filter** (mandated): TQQQ 20-session realised vol of daily log
returns, annualised, compared with its own trailing 252-session quantile.
Gate value is computed through session `k-1` and applied to session `k`:
`w_TQQQ ×= 0.5` when `vol20 > q75`, or `×= 0` when the hard gate is used. While
the trailing window is warming up (<60 sessions) the gate is open.

**Holidays.** Hardcoded, ex-ante scheduled closures only:

```
2016-01-01 2016-01-18 2016-02-15 2016-03-25 2016-05-30 2016-07-04 2016-09-05 2016-11-24 2016-12-26
2017-01-02 2017-01-16 2017-02-20 2017-04-14 2017-05-29 2017-07-04 2017-09-04 2017-11-23 2017-12-25
2018-01-01 2018-01-15 2018-02-19 2018-03-30 2018-05-28 2018-07-04 2018-09-03 2018-11-22 2018-12-25
2019-01-01 2019-01-21 2019-02-18 2019-04-19 2019-05-27 2019-07-04 2019-09-02 2019-11-28 2019-12-25
2020-01-01 2020-01-20 2020-02-17 2020-04-10 2020-05-25 2020-07-03 2020-09-07 2020-11-26 2020-12-25
2021-01-01 2021-01-18 2021-02-15 2021-04-02 2021-05-31 2021-07-05 2021-09-06 2021-11-25 2021-12-24
2022-01-17 2022-02-21 2022-04-15 2022-05-30 2022-06-20 2022-07-04 2022-09-05 2022-11-24 2022-12-26
2023-01-02 2023-01-16 2023-02-20 2023-04-07 2023-05-29 2023-06-19 2023-07-04 2023-09-04 2023-11-23 2023-12-25
```

73 anchors. `2018-12-05` (Bush day of mourning) is **excluded** — an
unscheduled closure is not knowable in advance. The holiday list was validated
against the panel: it reproduces every weekday gap in 2016–2023 with no
residual, and contains no date that traded.

Half-days come from `bt.HALF_DAYS` (also ex-ante: the NYSE publishes the
13:00-close calendar years ahead).

## 3. Pre-registered grid (8 cells)

| id | back | exit | half-days | vol gate | rationale |
|---|---:|---|---|---|---|
| **G1** | 3 | hold_through | no | 0.5 if vol20 > trailing q75 | **primary**: mandate-faithful, 3-session window + filter |
| G2 | 1 | hold_through | no | none | shortest window (classic "day before") |
| G3 | 2 | hold_through | no | none | middle window |
| G4 | 3 | hold_through | no | none | primary without the filter |
| G5 | 3 | exit_1559 | no | none | pure session exposure, no holiday gap |
| G6 | 3 | hold_through | yes | none | adds the shortened session |
| G7 | 3 | hold_through | no | 0 if vol20 > trailing q50 | hard vol gate |
| G8 | 5 | hold_through | no | none | window-length neighbour |

`G1` and the 8 cells were fixed before the final run. A coarse scan of window
length, exit mode and filter settings *was* run first — the programme requires
a plateau rather than a single cell, and the plausible ranges had to be known.
The primary is the mechanism-faithful cell, **not** the best cell; §5 of
`report.md` discloses which cells were scanned and how.

## 4. Decision rule

* Pass: dev CAGR > 36.72% **and** max DD < 82.29% (target DD < 60%).
* Report the plateau, not the maximum: every cell's CAGR, DD, Sharpe,
  exposure and window count.
* Report the effect separately from the strategy: per-window TQQQ return,
  t-stat, hit rate, drop-best-N sensitivity, and the same statistic for
  random windows of identical length.
* Reject the mandate if either (a) the per-window premium is not
  distinguishable from a random window, or (b) no cell clears the CAGR bar.

## 5. Robustness tests (all pre-registered)

1. **Placebo.** 500 draws of 73 random 3-session blocks (overlaps allowed,
   same count and length); report the percentile of the primary CAGR, DD and
   Sharpe. Plus 28 exposure-matched phase draws (73 non-overlapping 3-session
   blocks per phase).
2. **Neighbour.** Window length `back` 1–7; exit mode `hold_through` vs
   `exit_1559`; ±1 and ±2 sessions around every anchor (shift test, −10…+10);
   with/without half-days.
3. **Cut.** 2016–2019 / 2020–2021 / 2022–2023; leave-one-year-out; drop the
   best 3 and best 5 windows; per-holiday slot.
4. **Cost.** 1 bp headline, 5 bp and 10 bp.
5. **Decomposition.** TQQQ log return split into open→close and close→open
   over the same window, and the same split over all sessions, to test whether
   any apparent pre-holiday profit is holiday-specific or just overnight drift.

## 6. Integrity notes

* Development window only; `bt.panel(..., end="2023-12-29")` never reads a
  2024+ row, and the cache key includes the end date.
* No full-sample normalisation: the vol gate uses a trailing quantile.
* No shorting, no leverage beyond the 1.0 weight cap, no use of QQQ/TQQQ
  relative value, no external data.
* The only files written are the four in this directory.
