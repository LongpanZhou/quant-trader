# Hypothesis: weekday seasonality — half-sized Friday de-risk

**Slug:** `family-weekday-seasonality`
**Window:** development only, 2016-01-04 .. 2023-12-29, 1-minute marks.
**Bar:** TQQQ dev 36.72% CAGR / 82.29% max DD / 0.82 Sharpe (brief). The
panel's 1 bp TQQQ buy-and-hold is 36.29% / 81.57% / 0.80.
**Status:** pre-registered before the final `strategy.py` run. No 2024+ bar is
loaded anywhere in this directory.

## 1. Claim

The weekday is a real, ex-ante clock. The weekend carries two days of
unpriced information and a risk premium: investors who do not want weekend
exposure reduce it on Friday, and the Friday open-to-Monday-open return should
be weaker and more volatile than the other four sessions. The effect should be
visible in QQQ and amplified in TQQQ, and it should be a *Friday* effect, not a
generic "be out of the market" effect.

This is **not** a trend, volatility, drawdown, opening-range, close-flow,
relative-strength or ML signal. The only input is the calendar day of week.
The decision is known at the previous close.

The claim is tested as a **partial de-risk**, not a full one. The strategy
trades every week, so a full 0/1 Friday switch pays two extra legs per week.
A half-sized Friday de-risk keeps most of the signal while halving the weekly
turnover. The 8-cell grid covers the full range 0-100% Friday exposure so the
reader can see the gross signal and the net-of-cost trade-off.

## 2. Exact rules (centre)

Universe: QQQ (not used in the centre signal), TQQQ (position), cash (idle).
The centre uses cash, not BIL, on the de-risked leg: BIL adds a second leg and
roughly doubles the weekly turnover for a ~1.4%/yr yield on 10% of the book.
The BIL version is reported as a control.

For session `k` (a regular US session):

```
w_tqqq(k) = 0.50   if weekday(k) == Friday
          = 1.00   otherwise
w_cash(k) = 1 - w_tqqq(k)
```

- The Friday/Saturday/Sunday calendar is known at the prior close. The target
  for Friday is set at Thursday's 16:00 close (the 15:59 bar); the target for
  Monday is set at Friday's 16:00 close. Fills are at the next open. The
  harness's next-open rule is used unchanged.
- Idle weight is cash (zero return), not BIL, in the centre. This is a
  deliberate turnover choice; the BIL-idle variant is in the controls.
- The 2% rebalance band is the harness default. Headline cost is 1 bp; 5 bp
  and 10 bp are reported.
- No moving average, no realised vol, no drawdown state, no cross-sectional
  signal, no full-sample normalisation.

## 3. Pre-registered grid (8 cells)

The centre is **Friday weight 50%, other days 100%, cash idle**. The grid is a
single-parameter neighbourhood of Friday exposure, fixed before the final run:

| # | Friday weight | other days | role |
|---:|---:|---:|---|
| 1 | 0% | 100% | full Friday de-risk (gross-max) |
| 2 | 20% | 100% | neighbour |
| 3 | 35% | 100% | neighbour |
| 4 | **50%** | **100%** | **centre** |
| 5 | 65% | 100% | neighbour |
| 6 | 80% | 100% | neighbour |
| 7 | 90% | 100% | neighbour |
| 8 | 100% | 100% | TQQQ control |

Every cell is reported, including the failures. No cell is selected on the
holdout.

The other four weekdays are **controls**, not a search: the same 50% de-risk
applied to Monday, Tuesday, Wednesday and Thursday, plus Monday-only,
Monday+Tuesday, and TQQQ buy-and-hold. The claim is specifically about Friday;
if another weekday produces the same or better result, the Friday story is not
identified.

## 4. Pilot scan disclosure

A coarse scan of the dev window was run before fixing the grid. It covered:

- the five weekday-only long strategies and the five ex-one-weekday
  strategies;
- Friday weights 0 .. 100%;
- cash vs BIL idle.

It showed that the **gross** weekday effect is not the textbook "Monday
weakness": in 2016-2023 Monday is the strongest session (TQQQ open-to-open
mean +76 bp, t = 3.65) and Friday is the weakest (-6.6 bp, t = -0.30), with
Friday also the highest-volatility weekday (70.8% annualised vs 57-68% for the
others). The ex-Friday gross strategy is the most consistent across
sub-periods (2016-2019 and 2020-2023 both beat TQQQ), while ex-Monday is
excellent before 2020 and catastrophic after. The full Friday de-risk is the
gross maximum; the 50% centre is the cost-aware midpoint. The grid above is
the local neighbourhood of that choice. The pilot also produced two rejected
ideas reported in `report.md`:

1. **Monday-only long**: 38.95% daily-approximation CAGR / 39.6% DD / 1.32
   Sharpe before costs, but 15.6% at 10 bp on the 1-minute panel. The weekly
   turnover eats the exposure advantage. It is a control, not the centre.
2. **Full Friday de-risk with BIL idle**: 45.91% at 1 bp but 21.57% at 10 bp.
   The second leg doubles the cost. It is a control, not the centre.

## 5. Falsification criteria

The hypothesis is rejected if any of the following holds on the dev window:

1. Centre 10 bp CAGR <= 36.72% or max DD >= 82.29%.
2. Centre 10 bp CAGR is not above the brief bar by at least 0.25 pp (a tie is
   not a pass).
3. Ex-2020 centre CAGR <= 28.35% (TQQQ ex-2020).
4. The random-weekday placebo beats the centre with p > 0.10.
5. The Friday-weight grid is a spike: the immediate 10 bp neighbours at 35%
   and 65% both fall below 36.72%.
6. At least one of the four other-weekday controls (same 50% de-risk) beats
   the Friday centre on 10 bp CAGR *and* has a lower max DD. If so, the
   "Friday" interpretation is not identified and the family is rejected.
7. The edge is one year: 2020 contributes more than 50% of the centre's total
   log return.

Criterion 6 is the one that separates a weekday effect from a generic
risk-reduction overlay. Criterion 2 is deliberately strict: a 10 bp result
that only ties TQQQ is not a winner.

## 6. What would make this a real holdout candidate

The strategy is long TQQQ four days a week and half-long on Friday. It should
beat TQQQ in drawdowns and in crisis years (2018, 2020, 2022), lag in smooth
bull years (2017, 2019, 2023), and have a lowish correlation to the existing
TQQQ-beta winners but not to TQQQ itself. It is a candidate for the one-shot
holdout only if the 10 bp result clears the bar by a meaningful margin and the
other-weekday controls do not match it. If the 10 bp result is a tie, the
honest verdict is "gross anomaly, not a net winner."
