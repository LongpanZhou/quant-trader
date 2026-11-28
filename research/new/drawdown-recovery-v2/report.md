# Drawdown-recovery TQQQ v2 — development report

**Verdict: PASS the development bar, with a caveat that matters.**  On
2016-01-04 .. 2023-12-29 the strategy makes **57.63% CAGR at 43.39% max
drawdown, 1.25 Sharpe, 78.8% average exposure, 27 fills** (1 bp, 1-minute
marks, next-open fills, 2% band).  TQQQ buy-and-hold on the same bars makes
36.15% / 82.29% / 0.80.  The strategy is a **crash circuit breaker**, not a
broad recovery alpha: removing 2022 leaves 75.27% CAGR versus TQQQ's 77.75%,
but with 41.11% drawdown versus 69.89%.  The headline CAGR edge is the 2022
avoidance; the risk reduction is present in every subperiod.

No 2024+ bar entered the panel, any signal or any statistic: `bt.panel`
slices the 1-minute archive at 2023-12-29.  All numbers below are
development-window numbers.

**Full-window note (authorized holdout, added after the development report):**
the 2016-2026 record is **35 fills = 27 dev + 8 holdout**.  The 80.7% average
exposure is **time at 100% TQQQ**, not an 80% position: the weight path is
binary 0/1, so the 2% band never triggers a positive-to-positive rebalance.
The 35 fills are 18 buys + 17 sells; the 17 completed positions average
**126 sessions** (median 90) and each fill moves the whole book.  This is a
low-turnover crash circuit breaker by design, not a high-frequency trader.
See `FILL_AUDIT.md` for the full 35-row table.

---

## 1. Rules

One decision per session at the QQQ close; TQQQ is bought or sold at the next
session's open by `research/bt.py` (2% band, 1 bp headline; 5 and 10 bp
reported).  Idle weight is cash at 0%.  Long-only, weight in {0, 1}.

```
dd20 = q / max(q[-19..0]) - 1
dd60 = q / max(q[-59..0]) - 1
vr   = sigma10(lagged) / sigma60(lagged), annualised
hi10 = max(q[-10..-1])
```

Default state **LONG**.  A position is opened at the first session and after
every recovery.

**LONG -> CASH.**
- Normal position: `dd20 <= -8%` or `dd60 <= -12%`.
- A position entered from a deep cash episode: `dd20 <= -8%` or an 8%
  drawdown from its own post-entry high.  The stale 60-day drawdown is
  ignored until `dd60 > -12%`, otherwise the position would be stopped out
  the day after entry by a drawdown that predates it.
- On exit, `deep = (dd60 <= -12%)`.

**CASH -> LONG.**  `deep` is sticky while in cash.
- deep: re-enter when `vr < 0.60` (volatility contraction).  The 10-day high
  is **not** enough; a 10-day high in a bear market is a bear rally.
- shallow: re-enter when `vr < 0.60` **or** `q > hi10`.

Indicator warmup is QQQ daily closes from 2015-01-02..2015-12-31 only.  The
1-minute panel is physically sliced at 2023-12-29.

The "exit on a 10-session low" branch from the mandate was implemented and
tested.  It is a negative ablation (§6): it exits every ordinary pullback,
raises fills from 27 to 127 and cuts CAGR to 30.37%.

## 2. Headline development result

| Cost | CAGR | Max DD | Sharpe | Sortino | Vol | Exposure | Fills | End equity |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 bp | **57.63%** | **43.39%** | **1.25** | 1.78 | 44.19% | 78.8% | 27 | $3,783,755 |
| 5 bp | 57.41% | 43.48% | 1.25 | 1.77 | 44.19% | 78.8% | 27 | $3,743,111 |
| 10 bp | 57.15% | 43.60% | 1.25 | 1.77 | 44.18% | 78.8% | 27 | $3,692,920 |
| TQQQ B&H | 36.15% | 82.29% | 0.80 | 1.12 | 66.55% | 100% | 1 | $1,175,165 |
| Brief bar | 36.72% | 82.29% | 0.82 | — | — | — | — | — |

- Daily-return correlation to TQQQ: **0.667**.
- Worst drawdown: **2018-01-29 -> 2018-04-25, -43.39%**.  TQQQ's drawdown in
  that same window was -33.27%: the worst episode is a whipsaw, not a bear
  market, and the strategy amplified it.
- CAGR is 20.9 pp above the bar and DD is 38.9 pp below the DD bar; the
  result is not a marginal pass.
- The 5 bp and 10 bp results differ by 0.2/0.5 pp: 27 fills over 8 years make
  the strategy almost cost-insensitive.
- Cross-check on daily open-to-open bars: 58.01% CAGR / 40.52% DD, within
  0.4 pp of CAGR and 2.9 pp of DD of the 1-minute result.  The higher 1-minute
  DD is the intraday mark, as expected.

## 3. Yearly returns

| Year | Strategy | TQQQ | Exposure |
|---:|---:|---:|---:|
| 2016 | +16.1% | +19.9% | 81.0% |
| 2017 | +114.5% | +114.5% | 100.0% |
| 2018 | **-3.9%** | **-20.8%** | 69.5% |
| 2019 | +75.1% | +148.2% | 92.4% |
| 2020 | **+129.8%** | **+104.1%** | 69.1% |
| 2021 | +68.6% | +81.1% | 96.4% |
| 2022 | **-26.0%** | **-79.4%** | 23.9% |
| 2023 | +189.5% | +192.0% | 98.0% |

The strategy wins 2017 (tie), 2018, 2020 and 2022, ties 2023, and lags 2016,
2019 and 2021.  2019 is the worst relative year: the December-2018 deep cash
episode ended only on 2019-01-22, so the strategy missed the first leg of the
2019 rebound, and a 5-day May cash episode missed another +15.1% TQQQ pop.
The strategy still made +75% that year.

## 4. Pre-registered grid and plateau

Eight cells, fixed before the reported run.  Centre is cell 2.

| # | dd20 | dd60 | vol | CAGR | Max DD | Sharpe | Exposure | Fills |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 7% | 11% | 0.60 | 38.83% | 42.97% | 1.01 | 72.4% | 37 |
| **2** | **8%** | **12%** | **0.60** | **57.63%** | **43.39%** | **1.25** | **78.8%** | **27** |
| 3 | 9% | 13% | 0.60 | 40.99% | 57.00% | 0.97 | 81.7% | 31 |
| 4 | 10% | 15% | 0.60 | 32.00% | 58.93% | 0.82 | 83.1% | 31 |
| 5 | 8% | 12% | 0.55 | 58.73% | 43.39% | 1.27 | 78.7% | 25 |
| 6 | 8% | 12% | 0.65 | 57.48% | 43.39% | 1.25 | 78.9% | 31 |
| 7 | 7% | 11% | 0.65 | 45.73% | 42.71% | 1.10 | 76.1% | 41 |
| 8 | 9% | 13% | 0.55 | 41.98% | 57.00% | 0.99 | 81.7% | 29 |

**Read of the plateau.**  The vol-ratio direction is flat: 0.55, 0.60 and
0.65 all give 57-59% CAGR at the same 43.39% DD.  The exit-threshold
direction is *not* flat: 7/11, 8/12 and 9/13 all clear the CAGR bar
(38.8%, 57.6%, 41.0%) and the 60% DD target, but 10/15 fails the CAGR bar
(32.0%).  The pass region is a band, not a single cell, but the centre is a
clear local peak: moving one step in either direction costs 17-19 pp of
CAGR.  That is the main overfitting risk in this report.

## 5. Neighbours (not used to choose the centre)

| Variant | CAGR | Max DD | Sharpe | Exposure | Comment |
|---|---:|---:|---:|---:|---|
| centre | 57.63% | 43.39% | 1.25 | 78.8% | — |
| hi_window 5 | 55.59% | 48.39% | 1.21 | 79.8% | shorter confirmation, more whipsaw |
| hi_window 20 | 48.27% | 44.18% | 1.13 | 76.1% | slower recovery, lower CAGR |
| trail 6% | 57.63% | 43.39% | 1.25 | 78.8% | identical; trail never binds in dev |
| trail 10% | 57.63% | 43.39% | 1.25 | 78.8% | identical |
| shallow vol-only | 46.11% | 40.80% | 1.14 | 71.0% | 10-day high adds 11.5 pp |
| shallow hi-only | 57.63% | 43.39% | 1.25 | 78.8% | identical: shallow vol branch never fires |
| deep vol-or-hi | 38.23% | 65.45% | 0.91 | 85.2% | **fails the 60% DD target** |
| start in cash | 60.14% | 43.39% | 1.29 | 78.6% | result does not rely on day-1 exposure |

The deep branch is the load-bearing part.  Replacing "deep = volatility
contraction only" with "volatility contraction or 10-day high" re-enters
2022 bear rallies, raises exposure to 85.2% and DD to 65.45%, and cuts CAGR
to 38.23%.  The shallow branch is the other load-bearing part: removing the
10-day high (shallow vol-only) costs 11.5 pp of CAGR while lowering DD only
2.6 pp.

The trail parameter is inert in dev because the 20-day-high exit always fires
first after a recovery entry.  It is kept as a backstop, not as a tuned
parameter.

## 6. Ablations

| Variant | CAGR | Max DD | Sharpe | Exposure | Fills |
|---|---:|---:|---:|---:|---:|
| centre | 57.63% | 43.39% | 1.25 | 78.8% | 27 |
| + 10-day-low exit | 30.37% | 39.70% | 0.93 | 58.5% | 127 |
| trailing-only exit | 56.20% | 46.59% | 1.20 | 80.2% | 27 |
| no deep/slow branch | 38.23% | 65.45% | 0.91 | 85.2% | 47 |

The 10-day-low exit is the clearest negative result in the mandate: it turns
a 27-fill, 57.6% CAGR strategy into a 127-fill, 30.4% CAGR strategy.  A
10-day low is an ordinary pullback in a bull trend, not a regime break.

Trailing-only exits (8% from the post-entry high, no rolling 20/60-day
trigger) are close -- 56.20% CAGR -- but the DD rises to 46.59%, so the
rolling-drawdown formulation is retained.

## 7. Placebo

Both placebos re-use the exact weight-mapping and simulator.  80 draws each.

| Placebo | Mean CAGR | 95th pct | p(>= 57.63%) |
|---|---:|---:|---:|
| Block permutation of the daily target (20-session blocks) | 26.31% | 45.20% | 0.000 |
| Random circuit breaker, same cash-run lengths, random dates | 28.79% | 49.29% | 0.0125 |

The real result is above the 95th percentile of both nulls.  A random
circuit breaker with the same average cash exposure (about 21%) makes only
28.8% CAGR, so the result is not merely "be out of the market 21% of the
time"; the *timing* of the drawdown exits carries the edge.  The constant-
exposure control makes 32.46% CAGR with a 72.48% DD, which says the same
thing more simply.

## 8. Cut tests and subperiods

| Cut | Strategy CAGR | Strategy DD | TQQQ CAGR | TQQQ DD |
|---|---:|---:|---:|---:|
| ex-2018 | 68.84% | 38.54% | 46.60% | 81.68% |
| ex-2020 | 48.85% | 41.11% | 27.84% | 81.68% |
| ex-2022 | **75.27%** | **41.11%** | **77.75%** | **69.89%** |
| ex-2023 | 44.46% | 41.11% | 21.49% | 81.68% |

| Subperiod | Strategy CAGR | Strategy DD | TQQQ CAGR | TQQQ DD |
|---|---:|---:|---:|---:|
| 2016-2019 | 44.38% | 43.39% | 48.33% | 58.62% |
| 2020-2021 | 98.07% | 40.76% | 95.24% | 72.74% |
| 2022-2023 | 46.73% | 40.63% | -21.15% | 81.10% |

The ex-2022 cut is the honest one: without 2022 the strategy **slightly
lags** TQQQ's CAGR (75.27% vs 77.75%) but with 28.8 pp less drawdown.  So
the headline CAGR pass is concentrated in 2022, while the DD improvement is
present in every cut.  The subperiod table tells the same story: 2016-2019
lags TQQQ's CAGR by 4 pp (44.38% vs 48.33%) but with 15 pp less drawdown;
2020-2021 and 2022-2023 beat on both.  The strategy is a crash-avoidance
overlay, not a bull-market alpha source.

## 9. Attribution: 13 cash episodes

`cash` means the fill-to-fill period from the exit signal to the re-entry
signal.  TQQQ return is the return that would have been earned if the
strategy had stayed long.

| Exit signal | Re-entry signal | Days | QQQ | TQQQ (avoided) |
|---|---|---:|---:|---:|
| 2016-01-07 | 2016-03-15 | 47 | +2.6% | +1.0% |
| 2018-02-08 | 2018-02-22 | 10 | +9.5% | **+27.1%** |
| 2018-03-23 | 2018-04-11 | 13 | +2.3% | +0.7% |
| 2018-10-11 | 2019-01-18 | 68 | -4.2% | **-25.6%** |
| 2019-05-31 | 2019-06-06 | 5 | +4.1% | +15.1% |
| 2020-02-25 | 2020-04-21 | 40 | -1.8% | **-29.2%** |
| 2020-09-08 | 2020-10-26 | 35 | +4.7% | +0.3% |
| 2020-10-30 | 2020-11-03 | 3 | +6.4% | **+25.0%** |
| 2021-03-03 | 2021-03-15 | 9 | +3.7% | +7.4% |
| 2022-01-18 | 2022-07-13 | 122 | -22.4% | **-61.0%** |
| 2022-08-29 | 2022-09-27 | 21 | -7.9% | **-28.5%** |
| 2022-09-29 | 2022-11-25 | 41 | +3.9% | +5.8% |
| 2022-12-20 | 2023-01-06 | 12 | +0.4% | -2.7% |

Net log TQQQ during cash: **-1.194** (the strategy avoided a 3.3x move, in
log terms).  Five of thirteen cash episodes avoided a loss; eight missed a
rally.  The net is still positive because the avoided losses are much larger
than the missed rallies.  The biggest single cost is 2018-02-08..02-22,
where the strategy exited at the bottom of the February 2018 crash and
missed a +27.1% TQQQ rebound; that is the origin of the 43% 2018 drawdown.
The 2020-10-30..11-03 exit also missed a +25.0% three-day election rally, and
2019-05-31..06-06 missed +15.1%.

The 14 round trips (dates are decision dates; returns are next-open to
next-open):

| Entry signal | Exit signal | Days | Entry type | Exit type | QQQ | TQQQ |
|---|---|---|---:|---|---|---:|---:|
| 2016-01-04 | 2016-01-07 | 3 | initial | drawdown | -4.3% | -11.9% |
| 2016-03-16 | 2018-02-08 | 479 | deep vol | drawdown | +45.6% | **+180.1%** |
| 2018-02-23 | 2018-03-23 | 20 | shallow hi | drawdown | -5.6% | -13.3% |
| 2018-04-12 | 2018-10-11 | 127 | shallow hi | drawdown | +5.0% | +15.6% |
| 2019-01-22 | 2019-05-31 | 90 | deep vol | drawdown | +7.5% | +16.0% |
| 2019-06-07 | 2020-02-25 | 180 | shallow hi | drawdown | +19.8% | +55.7% |
| 2020-04-22 | 2020-09-08 | 96 | deep vol | drawdown | +28.1% | **+104.1%** |
| 2020-10-27 | 2020-10-30 | 3 | deep vol | drawdown | +3.8% | -7.5% |
| 2020-11-04 | 2021-03-03 | 80 | shallow hi | drawdown | +8.0% | +12.2% |
| 2021-03-16 | 2022-01-18 | 213 | shallow hi | drawdown | +16.2% | +49.4% |
| 2022-07-14 | 2022-08-29 | 32 | deep vol | drawdown | +2.1% | +13.4% |
| 2022-09-28 | 2022-09-29 | 1 | deep vol | drawdown | -2.6% | -5.4% |
| 2022-11-28 | 2022-12-20 | 16 | deep vol | drawdown | -6.6% | -13.6% |
| 2023-01-09 | 2023-12-29 | 245 | shallow hi | open | +54.9% | **+189.5%** |

Five long winners (+180%, +56%, +104%, +49%, +190%) carry the result; the
rest are small losses.  This is a "let the winner run, cut the crash" profile,
not a high-frequency recovery trader.

## 10. Honest verdict and holdout risk

**What is real.**  The drawdown trigger and the two-speed re-entry are
causal, the 5/10 bp sensitivity is negligible, the placebo timing test is
significant, the ex-2018/ex-2020/ex-2023 cuts all beat TQQQ, and the
truncation test at 2022-01-03 reproduces the prior weights exactly.  The
result is not a one-cell artefact: 7/11 and 9/13 clear the CAGR bar and the
60% DD target, and the vol ratio is flat from 0.55 to 0.65.

**What is fragile.**
1. **Only three major crash episodes.**  2018Q4, 2020Q1 and 2022 drive the
   edge (7 of the 14 round trips are classified deep, but the other deep
   entries are small).  The pass is a statement about three macro events, not
   a large sample.  The bootstrap/placebo cannot create more independent
   crashes.
2. **The CAGR edge is 2022.**  Ex-2022 the strategy is 2.5 pp *behind*
   TQQQ's CAGR, though with half the drawdown.  If the holdout has no
   2022-like bear, the headline CAGR will not repeat; the DD reduction is
   the part that should.
3. **The worst DD is a whipsaw.**  2018-01-29 -> 2018-04-25 lost 43.39%,
   versus TQQQ's 33.27% in the same window.  A repeat in the holdout would
   be uncomfortable even though the full-period DD bar is met.
4. **Bull-market whipsaw.**  2019 lagged TQQQ by 73 pp (75.1% vs 148.2%)
   because the deep re-entry waited until 2019-01-22 and the May 2019
   shallow exit missed a fast +15.1% TQQQ pop.  A steady 2024-2026 bull with
   8-10% pullbacks would produce the same pattern.
5. **The centre is a local peak.**  7/11 and 9/13 are 17-19 pp lower.  The
   neighbours pass, but the grid is not a broad plateau in the exit
   dimension.

**Holdout arithmetic.**  The dev multiple is 37.84x ($100k -> $3.78M) versus
TQQQ's 11.75x.  For the full 2016-2026 CAGR to beat 37.54%, the holdout
multiple only has to exceed about 0.83x -- the strategy can lose roughly 17%
over 2024-2026 and still clear the full-period bar.  That is a large cushion
and the main reason this candidate has a real chance.  The failure mode is a
repeat of 2019: a strong, shallow-pullback bull in which the circuit breaker
exits and re-enters higher several times, giving back the cushion.  The
2024-08 and 2025-04 drawdown-recovery pattern is, mechanically, the kind of
event this strategy is designed for; a steady melt-up is not.

**Recommendation to the lead.**  Run the one-shot holdout.  If it passes,
the honest description is "a fast drawdown circuit breaker with a two-speed
recovery re-entry that roughly matches TQQQ's CAGR ex-2022 with about half
the drawdown, and wins the full sample through 2022 avoidance" -- not "a
new source of broad recovery alpha".
