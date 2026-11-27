# Volatility-Shock Recovery v2 (VSR-2) — repair report

**Slug:** `dynamic-leverage-throttle-v2`
**Original:** `research/revisit/dynamic-leverage-throttle`
**Status:** **repaired**, development window only (2016-01-04..2023-12-29).
**Marks:** 1-minute, next-open fills, 2% band, 1/5/10 bp.
**Verdict in one line:** the two-stage arm/trigger fix raises the sample from
**6 to 18 independent entries**, keeps a **positive and significant event mean
(+2.37%, p=0.019)**, and produces **CAGR 7.04% / max DD 14.67% / Sharpe 0.84**
at 1 bp. It is an honest repair but a **low-exposure diversifier**, not a
standalone 8%+ return engine; the stricter 10-entry cell does clear the old 8%
hurdle, at the cost of the sample-size repair.

---

## 1. Before / after

| Metric | Original | VSR-2 | Change |
|---|---:|---:|---|
| Independent entries | 6 | **18** | +12 |
| Median hold (sessions) | 14.5 | 10.5 | shorter |
| Average TQQQ weight | 1.17% | **3.41%** | +2.24 pp |
| Time in TQQQ | 4.1% | **10.6%** | +6.5 pp |
| Dev CAGR (1 bp) | 5.24% | **7.04%** | +1.80 pp |
| Max drawdown (1 bp) | 9.16% | **14.67%** | +5.51 pp |
| Sharpe (1 bp) | 1.06 | **0.84** | -0.22 |
| Calmar | 0.57 | 0.48 | -0.09 |
| Event mean | +4.60% | **+2.37%** | thinner |
| Event bootstrap p | 0.000 | **0.019** | still significant |
| Correlation vs 165-day base | 0.108 | **0.138** | still independent |

The original's 6 entries were all positive and its Sharpe was higher, but six
observations are not evidence. The repair trades some per-event edge for a
sample that can be tested. The drawdown rises because the broader set includes
the 2016-01 false start and the 2022 whipsaws, which the strict original
avoided.

### Cost ladder (dev, 1-minute marks)

| Cost | VSR-2 CAGR | VSR-2 max DD | Original CAGR |
|---|---:|---:|---:|
| 1 bp | 7.04% | 14.67% | 5.24% |
| 5 bp | 6.88% | 14.69% | 5.20% |
| 10 bp | 6.62% | 14.72% | 5.14% |

Cost drag is ~0.42 pp from 1 to 10 bp. The strategy is not cost-fragile.

---

## 2. Diagnosis: why the original had only six entries

The original required the shock, the decay and the drawdown on the **same
daily close**. On 2,012 dev sessions:

| Condition | Days | Share |
|---|---:|---:|
| `v20 >= 1.25 v60` (shock) | 303 | 15.1% |
| `v5 <= 0.85 v20` (decay) | 901 | 44.8% |
| `-35% <= dd252 <= -8%` (drawdown) | 518 | 25.7% |
| shock & decay | 133 | 6.6% |
| shock & drawdown | 97 | 4.8% |
| decay & drawdown | 182 | 9.0% |
| **all three** | **32** | **1.59%** |

The 32 days cluster into six episodes: 2016-02, 2018-11, 2019-05, 2020-03/04,
2020-09, 2022-05. By year:

| 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 3 | 0 | 5 | 2 | 21 | 0 | 1 | 0 |

The original state machine traded all six episodes: 2016-02, 2018-11,
2019-05, 2020-03, 2020-09 and 2022-05. The problem is not missed episodes; it
is that the same-close conjunction produces only six episodes in eight years.

2022 is the near-miss: 11 shock-and-drawdown days, but `v5/v20` was near or
above 1.0 on ten of them; only 2022-05-25 had a strong decay (0.54) and became
a joint day. 2021 and 2023 have zero joint days for different reasons: 2021's
drawdowns were shallow (4 days at or below -8%), and 2023 had zero 1.25x shock
days. The conditions are sequential, not simultaneous.

The edge itself is visible at the daily-state level: after the 32 joint days,
forward TQQQ returns average +8.96% over 5 sessions and +16.95% over 10,
versus +0.98% and +1.99% unconditionally. Excluding 2020, the 5-day figure is
+4.56% (n=11) and the 10-day figure +5.06%. The state is real; the conjunction
was throwing it away.

---

## 3. The fix

**Arm** on `v20 >= 1.10 v60` and `-40% <= dd252 <= -5%`. **Trigger** on the
first close within 15 sessions where `v5 <= 0.85 v20` while the drawdown is
still <= -5%. Enter at the next open; size `min(0.75, 0.30/v20)`; exit on vol
normalisation, recovery to -3%, catastrophe, or 60 sessions; 5-session
cooldown.

The decay threshold stays at the original **0.85**. Only the shock and
drawdown thresholds are relaxed one step (1.25 → 1.10, -8% → -5%). The
diagnosis says the timing was the main defect, not the economics; the grid
shows the decay filter is the mechanism.

---

## 4. Dev results

### Headline (18 entries, 1 bp)

| Metric | Value |
|---|---:|
| CAGR | 7.04% |
| Max drawdown | 14.67% |
| Sharpe | 0.84 |
| Sortino | 1.21 |
| Calmar | 0.48 |
| Fills | 199 |
| Turnover | 39.8× |
| Average TQQQ weight | 3.41% |
| Time in TQQQ | 10.6% |
| Correlation vs 165-day base | 0.138 |

### Sub-periods

| Period | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| 2016-2019 | 4.37% | 14.67% | 0.51 |
| 2020-2021 | 11.15% | 3.84% | 1.76 |
| 2022-2023 | 8.47% | 9.69% | 0.94 |

All three are positive. 2020 is not the only driver; 2021, 2022 and 2023 each
contribute, and the 2016-19 period is positive despite the 2016-01 false start.

### Yearly strategy returns

| 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| +2.55% | +0.69% | -1.57% | +16.66% | +9.81% | +12.47% | +8.07% | +8.75% |

2018 is the only negative year (-1.57%). The strategy is in BIL most of the
time, so the yearly numbers are small relative to TQQQ; that is the design.

### Events

- 18 entries, 18 exits, median hold 10.5 sessions.
- Mean episode +2.37%, median +3.16%, hit rate 61.1%.
- One-sided bootstrap p(mean <= 0) = **0.019**.
- Episode returns: -4.21, +5.19, -2.43, -2.90, +6.97, +7.42, +5.48, +3.62,
  +6.02, +5.95, +13.55, +2.70, -5.05, -3.38, -1.37, +0.08, -0.53, +5.52 (%).
- The gap-inclusive convention (marking the exit at the next open's close)
  raises the mean to +2.60% and lowers p to 0.005; the table uses the
  conservative close-to-close convention for comparability with the original.

---

## 5. Pre-registered 8-cell neighbourhood

All cells: `arm_window=15`, `time_stop=60`, `cooldown=5`, `target_vol=0.30`
unless noted; 1-minute marks, 1 bp.

| # | shock | dd | decay | entries | TQ expo | CAGR | max DD | Sharpe | event mean | event p |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 1.10 | -5% | 0.85 | **18** | 3.41% | 7.04% | 14.67% | 0.84 | +2.37% | 0.019 |
| 1 | 1.15 | -5% | 0.85 | 13 | 2.90% | 6.68% | 12.87% | 0.84 | +2.88% | 0.015 |
| 2 | 1.20 | -5% | 0.85 | 10 | 2.23% | 8.15% | 9.24% | 1.19 | +4.99% | 0.0002 |
| 3 | 1.10 | -4% | 0.85 | 20 | 3.86% | 7.11% | 14.67% | 0.78 | +2.16% | 0.018 |
| 4 | 1.10 | -6% | 0.85 | 16 | 3.12% | 5.86% | 12.87% | 0.73 | +2.09% | 0.044 |
| 5 | 1.10 | -5% | 0.80 | 17 | 3.19% | 7.19% | 14.67% | 0.88 | +2.55% | 0.021 |
| 6 | 1.10 | -5% | 0.85 | 18 | 5.08% | 9.78% | 21.09% | 0.80 | +3.55% | 0.021 |
| 7 | 1.25 | -8% | 0.85 | **7** | 1.52% | 6.88% | 9.16% | 1.21 | +5.87% | 0.000 |

`#6` uses `target_vol=0.45`; `#7` is the strict original-threshold anchor.

**Plateau:** 8/8 cells have positive CAGR; entries range 7-20; median CAGR
7.07%, median Sharpe 0.84. The per-event edge is generally stronger at
stricter thresholds and thinner at broader ones, which is what a real signal
should do. The primary is not the single best cell (the 7-entry anchor has the
best Sharpe; the 10-entry cell has the best CAGR). The 18-entry primary is the
cell that meets the sample-size target while keeping the original decay filter.

**The honest trade-off:** the 10-entry cell (`shock 1.20 / dd -5% / decay
0.85`) clears both old standalone hurdles (CAGR 8.15%, max DD 9.24%, Calmar
0.88, Sharpe 1.19). The 7-entry strict anchor has Calmar 0.75 but CAGR 6.88%,
so it clears the Calmar hurdle only and is underpowered. The 18-entry cell
does not clear 8% CAGR (7.04%) or 0.50 Calmar (0.48), but it is the
statistically usable version. You cannot have both on this data.

---

## 6. Ablations (1-minute marks, 1 bp)

| Variant | Entries | TQ expo | CAGR | max DD | Sharpe | event mean | event p |
|---|---:|---:|---:|---:|---:|---:|---:|
| primary | 18 | 3.41% | 7.04% | 14.67% | 0.84 | +2.37% | 0.019 |
| no decay (`decay=99`) | 24 | 6.88% | 4.98% | 25.45% | 0.41 | +1.34% | 0.144 |
| no shock (`shock=0`) | 56 | 4.38% | 5.52% | 15.23% | 0.61 | +0.75% | 0.033 |
| no drawdown | 47 | 9.16% | 3.34% | 35.69% | 0.31 | +0.44% | 0.291 |

Removing the decay filter doubles the exposure and halves the Sharpe; the
event mean loses significance. Removing the shock triples the entry count but
cuts the event mean to +0.75%. Removing the drawdown is worse still. The three
ingredients are doing work; the decay filter is the mechanism.

---

## 7. Falsifiers

| # | Test | Result |
|---|---|---|
| 1 | Correlation vs 165-day base < 0.60 | **pass** (0.138) |
| 2 | CAGR >= 8% | **fail** (7.04%) |
| 2 | Calmar >= 0.50 | **fail** (0.48) |
| 2 | Max DD <= 35% | **pass** (14.67%) |
| 3 | Entries >= 12 | **pass** (18) |
| 3 | Bootstrap p <= 0.10 | **pass** (0.019) |
| 4 | Not 2020-only; 2016-19 and 2022-23 positive | **pass** (+4.37%, +8.47%) |
| 5 | Decay ablation worse | **pass** (no-decay mean +1.34%, p=0.144, Sharpe 0.41) |
| 6 | Grid plateau positive | **pass** (8/8) |
| 7 | Edge survives 10 bp | **pass** (6.62%) |

The old standalone return hurdles fail. The task's statistical-usability
criteria pass. The verdict is **repaired**, with the caveat that this is a
low-exposure diversifier. If the promotion rule requires the old 8%/0.50
standalone hurdles, promote the 10-entry `shock 1.20 / dd -5%` cell instead and
accept that the 15-entry target is not met.

---

## 8. Risks and caveats

1. **Still a small sample.** 18 entries is testable, not abundant. The
   bootstrap p is 0.019; the 95% interval on the mean is not tight.
2. **Low exposure.** 3.4% average TQQQ weight and 10.6% time in TQQQ. The
   strategy cannot be a standalone return engine; it is a diversifying sleeve
   that sits in BIL most of the time.
3. **2018 is negative.** The 2018-04 entry lost 2.4% and the 2018-10 entry
   lost 2.9%. The strategy is not a bear-market hedge.
4. **Threshold relaxation.** The primary uses shock 1.10 and dd -5%, one to
   two steps looser than the original. The strict anchor exists precisely to
   show what the relaxation buys and costs.
5. **TQQQ path dependence.** The inverse-vol weight shrinks in high vol, but a
   renewed crash after entry can still produce a -5% episode (2022-10).
6. **No 2000/2008 test.** The 1-minute archive starts in 2016; the behaviour in
   a structural bear is inferred, not observed.
7. **No shorting.** The idea is long TQQQ recovery; a short leg would be a
   different strategy with a different borrow/risk model.

---

## 9. Reproducibility

```
$env:PYTHONPATH = "C:/Users/27175/AppData/Local/Temp/opencode/pylibs"
python research/new/dynamic-leverage-throttle-v2/strategy.py
```

`strategy.py` loads only `bt.panel(("QQQ","TQQQ","BIL"), "2016-01-04",
"2023-12-29", "1min")`, computes daily signals from the session closes plus
pre-2016 Yahoo daily closes, and writes `result.json`. It never reads a
2024-2026 bar into a signal. The 8-cell grid and the four ablations are in the
same run. The original `research/revisit/dynamic-leverage-throttle/` files are
untouched.
