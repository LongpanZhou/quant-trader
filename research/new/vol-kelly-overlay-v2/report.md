# Vol-Spike Reflation v2 — retirement report

**Slug:** `vol-kelly-overlay-v2`
**Original:** `research/revisit/vol-kelly-overlay`
**Status:** **retired.** Development window only (2016-01-04..2023-12-29).
**Marks:** 1-minute, next-open fills, 2% band, 1/5/10 bp.
**Verdict in one line:** the count repair works (11 → 28 entries), but the
event mean is +0.59% with bootstrap **p=0.223**; no cell in the 8-cell grid
reaches p <= 0.10. The core post-spike reflation edge is absent, and forcing 28
trades would be count-chasing, not a repair.

---

## 1. Before / after

| Metric | Original | Count-repair v2 |
|---|---:|---:|
| Independent entries | 11 | **28** |
| Signal days | 15 | 49 |
| Average TQQQ weight | 0.91% | 0.77% |
| Time in TQQQ | 1.59% | 1.39% |
| Dev CAGR (1 bp) | 1.81% | **3.18%** |
| Max drawdown (1 bp) | 19.22% | **12.61%** |
| Sharpe (1 bp) | 0.25 | 0.38 |
| Event mean | +0.01% | **+0.59%** |
| Event bootstrap p | 0.489 | **0.223** |
| Hit rate | 63.6% | 53.6% |
| Correlation vs 165-day base | 0.272 | 0.206 |

The original row is `result.json` of the original rebuild. A direct 1-minute
re-run of the original gives 1.47% / 19.52% / 0.22 (11 entries); the small
difference from the saved result is within the noise of the re-run's
event/timing details. The event-return convention also differs (the original
excludes the entry-day open-to-close, the v2 table includes it). The
count-repair row is the v2 primary.

### Cost ladder (dev, 1-minute marks)

| Cost | Count-repair CAGR | Count-repair max DD |
|---|---:|---:|
| 1 bp | 3.18% | 12.61% |
| 5 bp | 2.85% | 13.03% |
| 10 bp | 2.43% | 13.60% |

Costs are not the problem. The edge is.

---

## 2. Diagnosis: why the original had only 11 entries

On 2,012 dev sessions:

| Condition | Days | Share |
|---|---:|---:|
| spike (`v5/v20 >= 1.50`) | 51 | 2.5% |
| oversold (`dd10 <= -5%`) | 219 | 10.9% |
| up-close | 1,129 | 56.1% |
| spike & oversold | 33 | 1.6% |
| **spike & oversold & up-close** | **15** | **0.7%** |

The state machine turned 15 signal days into 11 entries (consecutive signals
overlap). The average TQQQ weight was 0.91% and the strategy was in TQQQ only
1.59% of the time. The count is low because the RV spike is rare and the
up-close condition removes more than half of the remaining days.

The more damaging finding is that the up-close filter selects the **worse**
subset. Forward 3-session QQQ close-to-close returns after spike & oversold:

| Subset | n | Mean 3-day QQQ | Hit |
|---|---:|---:|---:|
| all | 33 | +0.56% | 64% |
| with up-close | 15 | **-0.12%** | 60% |
| with down-close | 18 | **+1.12%** | 67% |

The "stabilisation" condition buys after the bounce. The first day can continue
up, but the multi-day edge is not stable: the forward 3-day QQQ return is
negative after an up-close and positive after a down-close. In 2020 the
up-close subset produced -7.6% average 3-day TQQQ returns (n=6), and all 2020
signal days averaged -3.9%. The signal is a falling-knife detector in the exact
regime it was designed for.

---

## 3. The repair grid

The repair drops the up-close filter, shortens the hold, and relaxes the spike
ratio. The 8 cells were fixed before the run; all use the same inverse-vol
sizing, vol-normalisation exit and 4% QQQ stop.

| # | spike | dd | hold | up | entries | TQ expo | CAGR | max DD | Sharpe | event mean | event p |
|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | 1.50 | -5% | 3 | yes | 11 | 0.91% | 1.47% | 19.52% | 0.22 | +0.21% | 0.438 |
| 1 | 1.50 | -5% | 3 | no | 12 | 1.05% | 2.60% | 22.57% | 0.31 | +0.96% | 0.251 |
| 2 | 1.50 | -5% | 1 | no | 19 | 0.53% | 0.63% | 18.82% | 0.12 | -0.20% | 0.567 |
| 3 | 1.40 | -5% | 3 | no | 18 | 1.43% | 0.28% | 31.03% | 0.08 | -0.29% | 0.571 |
| 4 | 1.40 | -5% | 1 | no | **28** | 0.77% | **3.18%** | **12.61%** | **0.38** | **+0.59%** | **0.223** |
| 5 | 1.30 | -5% | 3 | no | 28 | 2.28% | 2.52% | 35.39% | 0.25 | +0.50% | 0.307 |
| 6 | 1.40 | -4% | 3 | no | 20 | 1.61% | -0.73% | 31.03% | -0.00 | -0.67% | 0.699 |
| 7 | 1.40 | -6% | 3 | no | 17 | 1.33% | -0.71% | 31.03% | -0.01 | -0.80% | 0.719 |

The count-repair cell (#4) is the best cell on CAGR, drawdown, Sharpe and
event p. It reaches 28 entries and keeps the 2022-23 sub-period positive
(+5.33%). But its event mean is +0.59% with p=0.223, and no cell reaches
p <= 0.10. The original 11-entry version is p=0.438 in the 1-minute re-run (0.489 in the
original `result.json`'s close-to-close convention). Dropping the up-close
filter raises the mean (to +0.96% in #1), but the sample remains too small to
distinguish from zero.

### Sub-periods of the count-repair cell

| Period | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| 2016-2019 | 2.28% | 12.61% | 0.34 |
| 2020-2021 | 2.88% | 12.55% | 0.27 |
| 2022-2023 | 5.33% | 4.07% | 1.12 |

The count repair is not carried by 2020. The 2020-21 sub-period is positive
(+2.88%), and the 2022-23 sub-period is the strongest. The problem is not
breadth; it is the size of the per-event edge relative to its variance.

### Yearly strategy returns (count-repair cell)

| 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| +0.10% | +0.69% | +6.07% | +2.31% | -3.71% | +9.92% | +5.63% | +4.94% |

---

## 4. Event evidence

- 28 entries, 28 exits, median hold 1 session.
- Mean event +0.59%, median +0.50%, hit 53.6%.
- Best +10.02%, worst -6.39%.
- One-sided bootstrap p(mean <= 0) = **0.223**.
- Removing the best event leaves **+4.82%** (the product is not one-event
  dependent).
- The product with 2020 is +15.33%; without 2020 it is **+19.98%**. 2020 was a
  drag, not the driver.
- The edge is not single-event dependent and not 2020-dependent; it is simply
  too small and too noisy.

The 95% bootstrap interval on the mean includes zero. A positive point estimate
of +0.59% on 28 mostly 1-session trades, with a 12.6% drawdown and a 0.38
Sharpe, is not a tradable standalone edge.

---

## 5. Falsifiers

| # | Test | Result |
|---|---|---|
| 1 | Entries >= 15 | **pass** (28) |
| 2 | Net positive at 10 bp | **pass** (2.43% CAGR > 0) |
| 3 | Bootstrap p <= 0.10 | **fail** (0.223) |
| 4 | Not single-event dependent | **pass** (without best +4.82%) |
| 5 | Correlation < 0.60 | **pass** (0.206) |
| 6 | Placebo / random entries | not needed; #3 already fails |
| 7 | 2022-23 positive | **pass** (+5.33%) |
| 8 | Stabilisation adds nothing | **fail** (dropping up-close improves the mean) |
| 9 | Standalone positive | **pass** (3.18% > BIL) |

The decisive failure is #3. The original's core claim was statistical
reflation; the data does not support it. #8 confirms the diagnosis: the
"first up-close" filter is not adding timing information, it is subtracting it.

---

## 6. Why this is a retirement, not a repair

The task allows a retirement when the core edge is absent. The evidence:

1. **The original 11-event mean is zero** (+0.01%, p=0.489).
2. **The count repair's 28-event mean is still zero** (+0.59%, p=0.223).
3. **No cell in the 8-cell grid reaches p <= 0.10.** The best is 0.223.
4. **The up-close filter is harmful**, not merely unhelpful: dropping it at
   the same 3-session hold and 1.50 spike raises the mean from +0.21% to
   +0.96% (row 1, p=0.251). The count-repair cell, which also shortens the
   hold and relaxes the spike, has +0.59% (p=0.223). Neither is significant.
5. **2020 was a drag**, not the source of the P&L. This is not a
   one-crash artefact that a longer sample would rescue.
6. **The signal is a falling-knife detector.** Forward 3-day QQQ returns after
   the spike-and-oversold state are +0.56% overall and -0.12% after an up-close;
   the 2020 up-close subset produced -7.6% average 3-day TQQQ returns (all 2020
   signal days averaged -3.9%). The claimed reflation is not there.

A 28-entry version with a +0.59% mean, a 12.6% drawdown and a 0.38 Sharpe would
be shipped only because it hits a count target. That is exactly what the brief
forbids. Retire it.

---

## 7. What would change the verdict

A genuine reflation edge would need one of:

- a **different measurement** of the spike that leads the rebound rather than
  coinciding with the selloff (e.g. an implied-vol term structure, if a
  point-in-time VIX history were available locally; it is not);
- a **different instrument** with less path dependence than TQQQ (QQQ itself
  also shows no reliable edge in the diagnosis, so this is not a sizing fix);
- a **confirmation signal with genuine information** (the up-close filter is
  the opposite: it selects the worse subset).

None of these is a threshold tweak, and none is supported by the local data.
The honest disposition is `retired`, not a new grid.

---

## 8. Reproducibility

```
$env:PYTHONPATH = "C:/Users/27175/AppData/Local/Temp/opencode/pylibs"
python research/new/vol-kelly-overlay-v2/strategy.py
```

`strategy.py` loads only `bt.panel(("QQQ","TQQQ","BIL"), "2016-01-04",
"2023-12-29", "1min")`, computes within-day 1-minute realised variance from the
session's TQQQ closes, and writes `result.json` with the 8-cell grid, the event
evidence and the falsifier verdict. It never reads a 2024-2026 bar into a
signal. The original `research/revisit/vol-kelly-overlay/` files are untouched.
