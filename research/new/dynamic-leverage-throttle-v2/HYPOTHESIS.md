# Hypothesis and pre-registration: Volatility-Shock Recovery v2 (VSR-2)

**Slug:** `dynamic-leverage-throttle-v2`
**Original:** `research/revisit/dynamic-leverage-throttle`
**Date:** 2026-11-27
**Status:** repaired candidate, development window only
(2016-01-04..2023-12-29). No 2024-2026 data is used anywhere in this file or
in `strategy.py`.

---

## 1. What the original did

The original VSR bought TQQQ when three conditions held on the same daily
close:

```
v20 >= 1.25 * v60          (a genuine volatility shock)
v5  <= 0.85 * v20          (the shock is already decaying)
-35% <= dd252(QQQ) <= -8%  (fear to recover from, but not a >35% catastrophe)
```

It entered at the next open, sized `min(0.75, 0.30 / v20)`, and held for weeks
until volatility normalised, the drawdown recovered to -3%, volatility
re-accelerated, 60 sessions passed, or a catastrophe stop. The rest was BIL.

The idea was sound: a shock plus its decay is the state in which forced
deleveraging is ending, and TQQQ's convexity should capture the recovery. The
implementation was underpowered.

---

## 2. Diagnosis: the conjunction is too strict in time

On the development window the daily conditions are not rare individually
(2,012 sessions):

| Condition | Days | Share |
|---|---:|---:|
| `v20 >= 1.25 v60` (shock) | 303 | 15.1% |
| `v5 <= 0.85 v20` (decay) | 901 | 44.8% |
| `-35% <= dd252 <= -8%` (drawdown) | 518 | 25.7% |
| shock & decay | 133 | 6.6% |
| shock & drawdown | 97 | 4.8% |
| decay & drawdown | 182 | 9.0% |
| **all three on the same close** | **32** | **1.59%** |

The 32 joint days are not 32 independent events: they cluster into six
episodes: 2016-02, 2018-11, 2019-05, 2020-03/04, 2020-09 and 2022-05. The
original state machine traded all six. By calendar year the joint state is:

| 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 3 | 0 | 5 | 2 | 21 | 0 | 1 | 0 |

The six episodes are the original's six entries. Average TQQQ weight was
**1.17%**, time in TQQQ **4.1%**, and the dev result was CAGR 5.24% / max DD
9.16% / Sharpe 1.06 at 1 bp. Six entries cannot support a claim, however good
the six episodes look.

2022 is the near-miss. There were 11 shock-and-drawdown days, but `v5/v20` was
near or above 1.0 on ten of them; only 2022-05-25 had a strong decay (0.54) and
became a joint day. 2021 and 2023 have zero joint days for different reasons:
2021's drawdowns were shallow (only 4 days at or below -8%), and 2023 had zero
1.25x shock days because its 60-day vol was already elevated.

The economic conditions are sequential:

1. a shock arrives;
2. the market is in a drawdown;
3. the shock starts to decay.

Requiring all three on one close throws away the days between (1) and (3),
which is most of the recovery window.

---

## 3. The repair: arm on the shock, trigger on the decay

V2 keeps the same three ingredients and the same instrument. It separates the
timing:

**Arm** at the close of session `t` when

```
v20_t >= shock_mult * v60_t
dd_crash <= dd252_t <= dd_entry
```

**Trigger** at the first later close `t + j`, `1 <= j <= arm_window`, when

```
v5_t+j <= decay_ratio * v20_t+j
dd252_t+j <= dd_entry          (still in the drawdown)
```

At the next open, buy `w = min(max_weight, target_vol / v20)`. While held,
re-size every 5 sessions and exit on any of:

- `v20 <= 1.05 * v60` (vol normalised);
- `dd252 >= -3%` (recovered);
- `dd252 <= -40%` (catastrophe);
- 60 sessions held (time stop).

After an exit, wait 5 sessions before arming again. No 165-day moving-average
gate, no shorting, no 30% core, no minute stop.

### Primary parameters

| Parameter | Value | Why |
|---|---:|---|
| `shock_mult` | 1.10 | Looser than 1.25; still a 10% vol expansion |
| `dd_entry` | -5% | A real pullback, looser than -8% |
| `decay_ratio` | 0.85 | The original mechanism value; the ablation shows it is essential |
| `arm_window` | 15 sessions | Long enough for the shock to roll over, short enough to stay causal |
| `target_vol` | 30% | Original inverse-vol budget |
| `max_weight` | 0.75 | Original cap |
| `time_stop` | 60 | Original |
| `cooldown` | 5 | Original |

The primary is not the strictest cell. The strict cell
(`shock 1.25 / dd -8% / decay 0.85`) has 7 entries and a much stronger
per-event edge; the primary is the cell that reaches the 15-40 entry target
without abandoning the decay filter. The grid reports the trade-off.

---

## 4. Pre-registered 8-cell neighbourhood

The grid is fixed before the development run. It moves one step at a time
around the primary; the decay 0.80 and target-vol 0.45 cells are mechanism and
sizing sensitivities, not a search for the best cell.

| # | `shock_mult` | `dd_entry` | `decay_ratio` | other |
|---:|---:|---:|---:|---|
| 0 | 1.10 | -5% | 0.85 | primary |
| 1 | 1.15 | -5% | 0.85 | |
| 2 | 1.20 | -5% | 0.85 | |
| 3 | 1.10 | -4% | 0.85 | |
| 4 | 1.10 | -6% | 0.85 | |
| 5 | 1.10 | -5% | 0.80 | |
| 6 | 1.10 | -5% | 0.85 | `target_vol=0.45` |
| 7 | 1.25 | -8% | 0.85 | strict anchor |

All cells use `arm_window=15`, `time_stop=60`, `cooldown=5`, `max_weight=0.75`.

---

## 5. Promotion criteria

The task's test is statistical usability, not a return target:

1. **Entries:** at least 15 independent entries in 2016-2023.
2. **Event evidence:** mean episode return > 0 with a one-sided bootstrap
   p-value <= 0.10 (10,000 resamples).
3. **Breadth:** the 2016-2019 and 2022-2023 sub-periods are both positive.
4. **Plateau:** at least 6 of the 8 grid cells have positive CAGR.
5. **Independence:** daily-return correlation with the 165-day baseline < 0.60.
6. **Cost:** the edge survives 10 bp.

The original report's standalone hurdles (CAGR >= 8%, Calmar >= 0.50) are
reported but are not the promotion gate: the repaired strategy is a
low-exposure, episodic diversifier, not an always-on return engine. If the
primary misses those hurdles, the report says so and quantifies the strict
cell that clears them.

The strategy is retired if criteria 1-4 fail. A high Sharpe on 7 entries is not
evidence; a 20-entry sample with a positive, significant mean is.

---

## 6. Universe, data and timing

| Item | Choice |
|---|---|
| Signal | QQQ daily close (drawdown); TQQQ daily close (realised vol) |
| Instrument | TQQQ |
| Cash | BIL (earns its own return) |
| Data | local adjusted 1-minute QQQ/TQQQ/BIL, 2016-01-04..2023-12-29 |
| Warm-up | Yahoo daily QQQ/TQQQ closes strictly before 2016-01-04 for the 5/20/60-day vol and 252-day high |
| Signal timing | close of session `t` |
| Fill | next bar's open (09:30 for the first minute of `t+1`) |
| Holding | episodic, days to weeks |
| Leverage | max 75% TQQQ; long only; gross <= 1 |

The `daily_prehistory` function filters `date < first_panel_date`, so the
Yahoo files' 2024-2026 rows are never read into the signal. The panel call
uses `end=2023-12-29`.

---

## 7. What is explicitly not used

- No 165-day moving-average gate in `build_weights`. The baseline function is
  used only to measure correlation.
- No shorting, no leveraged inverse product, no options.
- No 30% permanent core and no armed minute stop.
- No 2024-2026 data, no holdout inspection, no website edits.
- No full-sample tuning: the 8-cell grid is the whole search.

---

## 8. Expected shape (not a target to fit)

If the mechanism is real, the two-stage repair should produce roughly 15-20
entries, an event mean of 1-3%, a dev CAGR of 6-8%, a max DD of 12-16%, a
Sharpe of 0.7-0.9, and correlation below 0.20 with the 165-day base. The grid
should be positive but should show the per-event edge weakening as the entry
set broadens. If the broadened set has no significant positive mean, the
original's 6-entry result is a small-sample artefact and the strategy should be
retired, not defended.
