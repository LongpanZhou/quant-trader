# Hypothesis and pre-registration: Vol-Spike Reflation v2 (retirement test)

**Slug:** `vol-kelly-overlay-v2`
**Original:** `research/revisit/vol-kelly-overlay`
**Date:** 2026-11-27
**Status:** development-window repair attempt and retirement test. No
2024-2026 data is used anywhere in this file or in `strategy.py`.

---

## 1. What the original did

The original waited in BIL, then bought a volatility-scaled TQQQ position after
three conditions on the same daily close:

```
v5 / v20 >= 1.50            (5-day vs 20-day within-day 1-minute RV)
QQQ / max(QQQ, 10d) - 1 <= -5%   (oversold)
QQQ_t > QQQ_{t-1}           (the first up-close, "stabilisation")
```

It entered at the next open, sized `clip(0.35 / v20, 0.25, 0.75)`, held for
three sessions, and exited early on `v5/v20 < 1.00` or a 4% QQQ price stop.
The idea: a fast realised-vol spike plus an oversold market mean-reverts, and
TQQQ's daily-reset convexity captures the 1-3 session rebound.

The original result was 11 entries, dev CAGR 1.81%, max DD 19.22%, Sharpe 0.25,
event mean +0.015% (bootstrap p=0.488). Eleven events is below the 15-entry
minimum, and the event mean is indistinguishable from zero.

---

## 2. Diagnosis: the count is low and the edge is absent

On the development window (2,012 sessions):

| Condition | Days | Share |
|---|---:|---:|
| spike (`v5/v20 >= 1.50`) | 51 | 2.5% |
| oversold (`dd10 <= -5%`) | 219 | 10.9% |
| up-close | 1,129 | 56.1% |
| spike & oversold | 33 | 1.6% |
| spike & oversold & up-close | **15** | **0.7%** |

The state machine turned those 15 signal days into 11 entries (some signals
are consecutive and overlap). Average TQQQ weight was 0.91%, time in TQQQ
1.59%. The sample is tiny because the 1-minute-RV spike is already rare and
the up-close filter removes more than half of the remaining days.

The more important finding is that the **up-close filter selects the worse
subset**. Forward 3-session QQQ close-to-close returns after the
spike-and-oversold state:

| Subset | n | Mean 3-day QQQ | Hit |
|---|---:|---:|---:|
| all spike & oversold | 33 | +0.56% | 64% |
| with up-close | 15 | **-0.12%** | 60% |
| with down-close | 18 | **+1.12%** | 67% |

The "stabilisation" condition buys after the bounce. The first day often
continues up (the entry-day open-to-close is positive), but the multi-day edge
is not stable: the forward 3-day QQQ return is negative after an up-close and
positive after a down-close. In 2020 the up-close subset produced -7.6%
average 3-day TQQQ returns (n=6), and all 2020 signal days averaged -3.9%:
the signal is a falling-knife detector in the exact regime it was designed
for.

The core post-spike reflation edge is not visible in the data. The question is
whether a repair can find it, or whether the honest answer is retirement.

---

## 3. Repair hypothesis

The two diagnosed defects are:

1. **The up-close filter is a late-entry artefact.** Dropping it should raise
   the event count and the mean.
2. **The 3-session hold may give back part of the reflation.** The first
   session appears to carry the entry-day move; the grid tests whether a
   1-session hold keeps more of it.

The repair keeps the 1-minute realised-vol measurement, the oversold
condition, the inverse-vol sizing, the vol-normalisation exit and the price
stop. It changes only the entry filter and the hold:

```
signal = (v5/v20 >= spike) & (dd10 <= -dd_x)      # no up-close
hold   = 1 session
size   = clip(0.35 / v20, 0.25, 0.75)
```

The count-repair cell relaxes the spike from 1.50 to 1.40. The grid also tests
1.30 and the original 1.50, plus the 3-session hold, to separate the count
effect from the horizon effect.

### Pre-registered 8-cell grid

| # | spike | dd | hold | up-close | role |
|---:|---:|---:|---:|---|---|
| 0 | 1.50 | -5% | 3 | yes | original |
| 1 | 1.50 | -5% | 3 | no | drop the up filter only |
| 2 | 1.50 | -5% | 1 | no | drop the up filter + short hold |
| 3 | 1.40 | -5% | 3 | no | loosen the spike |
| 4 | 1.40 | -5% | 1 | no | count-repair cell |
| 5 | 1.30 | -5% | 3 | no | looser spike |
| 6 | 1.40 | -4% | 3 | no | shallower drawdown |
| 7 | 1.40 | -6% | 3 | no | deeper drawdown |

All cells use `target_vol=0.35`, `w_min=0.25`, `w_max=0.75`, `stop_x=0.04`,
`exit_ratio=1.00`. The grid is fixed before the run.

---

## 4. Retirement criteria

The original falsifiers are retained. The strategy is retired if any of the
following holds on the count-repair cell:

1. **Too few events:** fewer than 15 entries.
2. **No net expectancy:** the event mean is <= 0 at 10 bp.
3. **Not distinguishable from zero:** one-sided bootstrap p > 0.10.
4. **Single-event dependence:** removing the best event turns the product
   negative.
5. **High correlation:** daily-return correlation with the 165-day base
   >= 0.60.
6. **2022-23 failure:** the 2022-23 sub-period is negative.
7. **No standalone edge:** the 1 bp CAGR is <= BIL.

The up-close filter is diagnosed separately. Dropping it can repair the count
without repairing the edge; that is a finding about the original specification,
not a reason to keep the strategy. The key test is #3. If the count repair
reaches 28 entries but the event mean is still insignificant, the honest
outcome is retirement: the extra trades would be count-chasing, not evidence.

---

## 5. Universe, data and timing

| Item | Choice |
|---|---|
| Signal | QQQ daily close (10-day drawdown); TQQQ within-day 1-minute realised variance |
| Instrument | TQQQ |
| Cash | BIL |
| Data | local adjusted 1-minute QQQ/TQQQ/BIL, 2016-01-04..2023-12-29 |
| RV | sum of squared within-day 1-minute log returns; overnight gaps excluded |
| v5, v20 | `sqrt(252 * mean(RV, 5 or 20))` |
| Signal timing | close of session `t` |
| Fill | next bar's open |
| Holding | 1 or 3 sessions |
| Leverage | max 75% TQQQ; long only; gross <= 1 |

No 165-day moving-average gate in `build_weights`; the baseline is computed
only for correlation. No shorting, no options, no volatility products, no
2024-2026 data.

---

## 6. What is not used

- The old 20-day TQQQ→QQQ vol ladder and the 5% crash throttle.
- The shared 165-day trend gate.
- Kelly or fractional-Kelly sizing; the name is historical.
- Any holdout or full-sample result.
- Forced trades to hit a count target. If the edge is absent, the strategy is
  retired.

---

## 7. Expected outcome

If the reflation mechanism is real, dropping the up-close filter and
shortening the hold should produce 15-30 entries, a positive event mean with
p <= 0.10, and a positive 2022-23. If the 28-entry version has a mean near zero
and p > 0.10, the original 11-entry result was noise and the strategy should be
retired. The report is written to make that call, not to rescue the strategy.
